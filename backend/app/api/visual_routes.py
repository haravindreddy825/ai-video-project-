from pathlib import Path
from typing import Any
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.storage import InsufficientDiskSpaceError, StorageManager
from app.db.session import get_db
from app.engines.visuals.planner import ScriptToVisualPlanner
from app.engines.visuals.scene_manager import VisualSceneManager
from app.engines.visuals.schemas import (
    VisualAssetResponse,
    VisualGenerateRequest,
    VisualSceneCreateRequest,
    VisualSceneReorderRequest,
    VisualSceneResponse,
    VisualSceneUpdateRequest,
)
from app.models.entities import AudioTrack, Project, VisualAsset, VisualScene

visual_router = APIRouter()
storage = StorageManager()
scene_mgr = VisualSceneManager(storage)


def _scene_to_dict(scene: VisualScene) -> dict[str, Any]:
    return {
        "order_index": scene.order_index,
        "start_ms": scene.start_ms,
        "end_ms": scene.end_ms,
        "sentence_text": scene.sentence_text,
        "main_concept": scene.main_concept,
        "keywords": scene.keywords_json or [],
        "visual_format": scene.visual_format,
        "visual_description": scene.visual_description,
        "title_text": scene.title_text,
        "body_bullets": scene.body_bullets_json or [],
        "diagram_spec": scene.diagram_spec_json or {},
        "animation_style": scene.animation_style,
        "transition_style": scene.transition_style,
    }


async def _record_assets(
    db: AsyncSession, project_id: str, scene_id: str, rendered: dict[str, Any]
) -> None:
    for atype, key in (
        ("rendered_png", "image_path"),
        ("animated_mp4", "video_path"),
        ("svg_diagram", "svg_path"),
    ):
        path = rendered.get(key)
        if path:
            db.add(
                VisualAsset(
                    project_id=project_id,
                    scene_id=scene_id,
                    asset_type=atype,
                    file_path=path,
                    width=1080,
                    height=960,
                    metadata_json={"generator": rendered["generator_used"]},
                )
            )


@visual_router.post(
    "/api/v1/projects/{project_id}/visuals/generate",
    response_model=list[VisualSceneResponse],
    status_code=status.HTTP_201_CREATED,
    tags=["Visuals"],
)
async def generate_project_visuals(
    project_id: str,
    payload: VisualGenerateRequest,
    db: AsyncSession = Depends(get_db),
) -> list[VisualScene]:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        storage.ensure_disk_budget()
    except InsufficientDiskSpaceError as exc:
        raise HTTPException(status_code=507, detail=str(exc)) from exc

    track = await db.get(AudioTrack, payload.audio_id)
    if not track or track.project_id != project_id:
        raise HTTPException(status_code=404, detail="Audio track not found in project")

    planned = ScriptToVisualPlanner.plan_scenes(
        track.alignment_json,
        track.script_intelligence_json,
        track.duration_sec,
    )

    created_scenes: list[VisualScene] = []
    for item in planned:
        scene = VisualScene(
            id=str(uuid.uuid4()),
            project_id=project_id,
            audio_id=payload.audio_id,
            order_index=item["order_index"],
            start_ms=item["start_ms"],
            end_ms=item["end_ms"],
            sentence_text=item["sentence_text"],
            main_concept=item["main_concept"],
            keywords_json=item["keywords"],
            visual_format=item["visual_format"],
            visual_description=item["visual_description"],
            title_text=item["title_text"],
            body_bullets_json=item["body_bullets"],
            diagram_spec_json=item["diagram_spec"],
            animation_style=item["animation_style"],
            transition_style=item["transition_style"],
        )
        rendered = scene_mgr.render_scene_assets(
            project_id=project_id,
            scene_id=scene.id,
            scene_dict=item,
            use_comfyui=payload.use_comfyui,
            render_video=payload.render_video,
            fps=payload.fps,
        )
        scene.generator_used = rendered["generator_used"]
        scene.image_path = rendered["image_path"]
        scene.video_path = rendered["video_path"]
        db.add(scene)
        await db.flush()
        await _record_assets(db, project_id, scene.id, rendered)
        created_scenes.append(scene)

    await db.commit()
    for s in created_scenes:
        await db.refresh(s)
    return created_scenes


@visual_router.get(
    "/api/v1/projects/{project_id}/visuals/scenes",
    response_model=list[VisualSceneResponse],
    tags=["Visuals"],
)
async def list_visual_scenes(
    project_id: str, db: AsyncSession = Depends(get_db)
) -> list[VisualScene]:
    result = await db.execute(
        select(VisualScene)
        .where(VisualScene.project_id == project_id)
        .order_by(VisualScene.order_index.asc())
    )
    return list(result.scalars().all())


@visual_router.post(
    "/api/v1/projects/{project_id}/visuals/scenes",
    response_model=VisualSceneResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Visuals"],
)
async def create_visual_scene(
    project_id: str,
    payload: VisualSceneCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> VisualScene:
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    scene = VisualScene(
        id=str(uuid.uuid4()),
        project_id=project_id,
        audio_id=payload.audio_id,
        order_index=payload.order_index,
        start_ms=payload.start_ms,
        end_ms=payload.end_ms,
        sentence_text=payload.sentence_text,
        main_concept=payload.main_concept,
        keywords_json=payload.keywords,
        visual_format=payload.visual_format,
        visual_description=payload.visual_description,
        title_text=payload.title_text or payload.main_concept,
        body_bullets_json=payload.body_bullets or [payload.sentence_text],
        diagram_spec_json=payload.diagram_spec or {},
        animation_style=payload.animation_style,
        transition_style=payload.transition_style,
    )
    rendered = scene_mgr.render_scene_assets(
        project_id=project_id,
        scene_id=scene.id,
        scene_dict=_scene_to_dict(scene),
        render_video=True,
    )
    scene.generator_used = rendered["generator_used"]
    scene.image_path = rendered["image_path"]
    scene.video_path = rendered["video_path"]
    db.add(scene)
    await db.flush()
    await _record_assets(db, project_id, scene.id, rendered)
    await db.commit()
    await db.refresh(scene)
    return scene


@visual_router.patch(
    "/api/v1/visuals/scenes/{scene_id}",
    response_model=VisualSceneResponse,
    tags=["Visuals"],
)
async def update_visual_scene(
    scene_id: str,
    payload: VisualSceneUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> VisualScene:
    scene = await db.get(VisualScene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Visual scene not found")

    updates = payload.model_dump(exclude_unset=True)
    if "body_bullets" in updates:
        scene.body_bullets_json = updates.pop("body_bullets")
    if "diagram_spec" in updates:
        scene.diagram_spec_json = updates.pop("diagram_spec")
    for k, v in updates.items():
        setattr(scene, k, v)

    rendered = scene_mgr.render_scene_assets(
        project_id=scene.project_id,
        scene_id=scene.id,
        scene_dict=_scene_to_dict(scene),
        render_video=True,
    )
    scene.image_path = rendered["image_path"]
    scene.video_path = rendered["video_path"]
    await db.commit()
    await db.refresh(scene)
    return scene


@visual_router.post(
    "/api/v1/visuals/scenes/{scene_id}/regenerate",
    response_model=VisualSceneResponse,
    tags=["Visuals"],
)
async def regenerate_visual_scene(
    scene_id: str,
    use_comfyui: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> VisualScene:
    scene = await db.get(VisualScene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Visual scene not found")

    rendered = scene_mgr.render_scene_assets(
        project_id=scene.project_id,
        scene_id=scene.id,
        scene_dict=_scene_to_dict(scene),
        use_comfyui=use_comfyui,
        render_video=True,
    )
    scene.generator_used = rendered["generator_used"]
    scene.image_path = rendered["image_path"]
    scene.video_path = rendered["video_path"]
    await _record_assets(db, scene.project_id, scene.id, rendered)
    await db.commit()
    await db.refresh(scene)
    return scene


@visual_router.post(
    "/api/v1/visuals/scenes/{scene_id}/replace-image",
    response_model=VisualSceneResponse,
    tags=["Visuals"],
)
async def replace_scene_image(
    scene_id: str,
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> VisualScene:
    scene = await db.get(VisualScene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Visual scene not found")

    ext = Path(image.filename or "custom.png").suffix.lower()
    if ext not in storage.ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported image extension: {ext}")

    scene_dir = storage.outputs_dir / scene.project_id / "visuals" / scene.id
    scene_dir.mkdir(parents=True, exist_ok=True)
    custom_path = scene_dir / f"custom_upload{ext}"
    custom_path.write_bytes(await image.read())

    try:
        with Image.open(custom_path) as im:
            im.verify()
    except Exception as exc:
        custom_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Invalid image: {exc}") from exc

    rendered = scene_mgr.render_scene_assets(
        project_id=scene.project_id,
        scene_id=scene.id,
        scene_dict=_scene_to_dict(scene),
        render_video=True,
        custom_inset_path=custom_path,
    )
    scene.generator_used = "custom_upload"
    scene.image_path = rendered["image_path"]
    scene.video_path = rendered["video_path"]
    await _record_assets(db, scene.project_id, scene.id, rendered)
    await db.commit()
    await db.refresh(scene)
    return scene


@visual_router.post(
    "/api/v1/projects/{project_id}/visuals/scenes/reorder",
    response_model=list[VisualSceneResponse],
    tags=["Visuals"],
)
async def reorder_visual_scenes(
    project_id: str,
    payload: VisualSceneReorderRequest,
    db: AsyncSession = Depends(get_db),
) -> list[VisualScene]:
    result = await db.execute(
        select(VisualScene).where(VisualScene.project_id == project_id)
    )
    scenes_by_id = {s.id: s for s in result.scalars().all()}
    for idx, sid in enumerate(payload.scene_ids):
        if sid not in scenes_by_id:
            raise HTTPException(status_code=404, detail=f"Scene {sid} not found in project")
        scenes_by_id[sid].order_index = idx
    await db.commit()

    ordered = sorted(scenes_by_id.values(), key=lambda s: s.order_index)
    return ordered


@visual_router.post(
    "/api/v1/visuals/scenes/{scene_id}/approve",
    response_model=VisualSceneResponse,
    tags=["Visuals"],
)
async def approve_visual_scene(
    scene_id: str, db: AsyncSession = Depends(get_db)
) -> VisualScene:
    scene = await db.get(VisualScene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Visual scene not found")
    scene.approved = True
    await db.commit()
    await db.refresh(scene)
    return scene


@visual_router.get("/api/v1/visuals/scenes/{scene_id}/preview", tags=["Visuals"])
async def preview_visual_scene(
    scene_id: str,
    kind: str = Query(default="image", pattern="^(image|video)$"),
    db: AsyncSession = Depends(get_db),
):
    scene = await db.get(VisualScene, scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Visual scene not found")

    rel = scene.image_path if kind == "image" else scene.video_path
    if not rel:
        raise HTTPException(status_code=404, detail=f"Scene {kind} not available")
    path = (storage.root / rel).resolve()
    if not path.exists():
        raise HTTPException(status_code=404, detail="Asset missing on disk")
    media = "image/png" if kind == "image" else "video/mp4"
    return FileResponse(str(path), media_type=media)


@visual_router.get(
    "/api/v1/projects/{project_id}/visuals/assets",
    response_model=list[VisualAssetResponse],
    tags=["Visuals"],
)
async def list_project_visual_assets(
    project_id: str, db: AsyncSession = Depends(get_db)
) -> list[VisualAsset]:
    result = await db.execute(
        select(VisualAsset).where(VisualAsset.project_id == project_id)
    )
    return list(result.scalars().all())
