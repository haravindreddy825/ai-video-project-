from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.storage import StorageManager
from app.db.session import get_db
from app.engines.video_gen.providers.base import ProviderNotConfiguredError
from app.engines.video_gen.providers.registry import VideoProviderRegistry
from app.engines.video_gen.schemas import AspectRatio, FlowDuration, VideoGenRequest
from app.engines.video_gen.storyboard import FlowStoryboardPlanner
from app.engines.video_gen.timeline_assembler import FlowTimelineAssembler
from app.models.entities import FlowCharacter, FlowProject, FlowScene

flow_router = APIRouter()
storage = StorageManager()
registry = VideoProviderRegistry()


class FlowCharacterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: str
    appearance_prompt: str
    reference_image_path: Optional[str]


class FlowSceneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    flow_project_id: str
    order_index: int
    duration_sec: int
    scene_prompt: str
    narration_text: str
    camera_motion: str
    character_ids_json: Optional[list[str]] = None
    first_frame_path: Optional[str] = None
    last_frame_path: Optional[str] = None
    video_clip_path: Optional[str] = None
    variation_index: int
    version: int
    history_json: Optional[list[dict[str, Any]]] = None
    provider_used: Optional[str] = None
    status: str
    error_message: Optional[str] = None


class FlowProjectCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    prompt: str = Field(..., min_length=5)
    aspect_ratio: AspectRatio = "16:9"
    target_duration_sec: FlowDuration = 120
    visual_style: str = "cinematic"
    quality: Literal["lite", "fast", "standard"] = "lite"
    provider: Literal["veo_3_1", "comfyui_wan2_1"] = "veo_3_1"
    voice_id: str = "af_heart"
    character_ids: list[str] = Field(default_factory=list)


class FlowProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    prompt: str
    aspect_ratio: str
    target_duration_sec: int
    visual_style: str
    quality: str
    provider: str
    voice_id: str
    bgm_path: Optional[str] = None
    sfx_path: Optional[str] = None
    status: str
    final_mp4_path: Optional[str] = None
    duration_sec: float
    error_message: Optional[str] = None


class FlowProjectDetailResponse(FlowProjectResponse):
    scenes: list[FlowSceneResponse] = Field(default_factory=list)


class FlowSceneUpdate(BaseModel):
    scene_prompt: Optional[str] = None
    narration_text: Optional[str] = None
    duration_sec: Optional[int] = Field(default=None, ge=4, le=16)
    camera_motion: Optional[str] = None
    character_ids: Optional[list[str]] = None


@flow_router.get("/api/v1/flow/providers", tags=["Flow Studio"])
async def list_flow_providers():
    return [c.model_dump() for c in registry.list_capabilities()]


@flow_router.post(
    "/api/v1/flow/characters",
    response_model=FlowCharacterResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Flow Studio"],
)
async def create_flow_character(
    name: str = Form(...),
    description: str = Form(""),
    appearance_prompt: str = Form(""),
    image: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
) -> FlowCharacter:
    rel_img: str | None = None
    if image is not None:
        ext = Path(image.filename or "char.png").suffix.lower()
        if ext not in storage.ALLOWED_IMAGE_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Unsupported image extension {ext}")
        dest_dir = storage.inputs_dir / "flow_characters"
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f"{uuid.uuid4().hex}{ext}"
        dest.write_bytes(await image.read())
        rel_img = str(dest.relative_to(storage.root)).replace("\\", "/")

    char = FlowCharacter(
        name=name,
        description=description,
        appearance_prompt=appearance_prompt or description or name,
        reference_image_path=rel_img,
    )
    db.add(char)
    await db.commit()
    await db.refresh(char)
    return char


@flow_router.get(
    "/api/v1/flow/characters",
    response_model=list[FlowCharacterResponse],
    tags=["Flow Studio"],
)
async def list_flow_characters(db: AsyncSession = Depends(get_db)) -> list[FlowCharacter]:
    res = await db.execute(select(FlowCharacter).order_by(FlowCharacter.created_at.desc()))
    return list(res.scalars().all())


@flow_router.get("/api/v1/flow/characters/{char_id}/image", tags=["Flow Studio"])
async def get_flow_character_image(char_id: str, db: AsyncSession = Depends(get_db)):
    char = await db.get(FlowCharacter, char_id)
    if not char or not char.reference_image_path:
        raise HTTPException(status_code=404, detail="Character image not found")
    path = (storage.root / char.reference_image_path).resolve()
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image missing on disk")
    return FileResponse(str(path))


@flow_router.delete(
    "/api/v1/flow/characters/{char_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Flow Studio"],
)
async def delete_flow_character(char_id: str, db: AsyncSession = Depends(get_db)) -> None:
    char = await db.get(FlowCharacter, char_id)
    if not char:
        raise HTTPException(status_code=404, detail="Character not found")
    await db.delete(char)
    await db.commit()


@flow_router.post(
    "/api/v1/flow/projects",
    response_model=FlowProjectDetailResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Flow Studio"],
)
async def create_flow_project(
    payload: FlowProjectCreate, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    proj = FlowProject(
        title=payload.title,
        prompt=payload.prompt,
        aspect_ratio=payload.aspect_ratio,
        target_duration_sec=payload.target_duration_sec,
        visual_style=payload.visual_style,
        quality=payload.quality,
        provider=payload.provider,
        voice_id=payload.voice_id,
        status="storyboard_ready",
    )
    db.add(proj)
    await db.flush()

    appearances: list[str] = []
    if payload.character_ids:
        for cid in payload.character_ids:
            ch = await db.get(FlowCharacter, cid)
            if ch:
                appearances.append(f"{ch.name}: {ch.appearance_prompt}")

    cap = registry.get(payload.provider).get_capabilities()
    planned = FlowStoryboardPlanner.generate_storyboard(
        prompt=payload.prompt,
        target_duration_sec=payload.target_duration_sec,
        clip_duration_sec=cap.max_clip_duration_sec,
        visual_style=payload.visual_style,
        character_appearances=appearances,
    )

    scenes: list[FlowScene] = []
    for item in planned:
        sc = FlowScene(
            flow_project_id=proj.id,
            order_index=item["order_index"],
            duration_sec=item["duration_sec"],
            scene_prompt=item["scene_prompt"],
            narration_text=item["narration_text"],
            camera_motion=item["camera_motion"],
            character_ids_json=payload.character_ids,
            status="planned",
        )
        db.add(sc)
        scenes.append(sc)

    await db.commit()
    await db.refresh(proj)
    for sc in scenes:
        await db.refresh(sc)

    return {**FlowProjectResponse.model_validate(proj).model_dump(), "scenes": scenes}


@flow_router.get(
    "/api/v1/flow/projects",
    response_model=list[FlowProjectResponse],
    tags=["Flow Studio"],
)
async def list_flow_projects(db: AsyncSession = Depends(get_db)) -> list[FlowProject]:
    res = await db.execute(select(FlowProject).order_by(FlowProject.created_at.desc()))
    return list(res.scalars().all())


@flow_router.get(
    "/api/v1/flow/projects/{project_id}",
    response_model=FlowProjectDetailResponse,
    tags=["Flow Studio"],
)
async def get_flow_project(
    project_id: str, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    proj = await db.get(FlowProject, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Flow project not found")
    res = await db.execute(
        select(FlowScene)
        .where(FlowScene.flow_project_id == project_id)
        .order_by(FlowScene.order_index.asc(), FlowScene.variation_index.asc())
    )
    scenes = list(res.scalars().all())
    return {**FlowProjectResponse.model_validate(proj).model_dump(), "scenes": scenes}


@flow_router.post("/api/v1/flow/projects/{project_id}/upload-media", tags=["Flow Studio"])
async def upload_flow_media(
    project_id: str,
    kind: Literal["bgm", "sfx"] = Query(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    proj = await db.get(FlowProject, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Flow project not found")
    rel = await storage.save_voice_sample(f"flow_{project_id}", file)
    if kind == "bgm":
        proj.bgm_path = rel
    else:
        proj.sfx_path = rel
    await db.commit()
    return {"kind": kind, "path": rel}


@flow_router.patch(
    "/api/v1/flow/scenes/{scene_id}",
    response_model=FlowSceneResponse,
    tags=["Flow Studio"],
)
async def update_flow_scene(
    scene_id: str, payload: FlowSceneUpdate, db: AsyncSession = Depends(get_db)
) -> FlowScene:
    sc = await db.get(FlowScene, scene_id)
    if not sc:
        raise HTTPException(status_code=404, detail="Flow scene not found")
    updates = payload.model_dump(exclude_unset=True)
    if "character_ids" in updates:
        sc.character_ids_json = updates.pop("character_ids")
    for k, v in updates.items():
        setattr(sc, k, v)
    await db.commit()
    await db.refresh(sc)
    return sc


@flow_router.post(
    "/api/v1/flow/scenes/{scene_id}/upload-frame",
    response_model=FlowSceneResponse,
    tags=["Flow Studio"],
)
async def upload_scene_frame(
    scene_id: str,
    kind: Literal["first", "last"] = Query("first"),
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> FlowScene:
    sc = await db.get(FlowScene, scene_id)
    if not sc:
        raise HTTPException(status_code=404, detail="Flow scene not found")
    rel, _, _ = await storage.save_character_image(f"flow_{sc.flow_project_id}", image)
    if kind == "first":
        sc.first_frame_path = rel
    else:
        sc.last_frame_path = rel
    await db.commit()
    await db.refresh(sc)
    return sc


@flow_router.post(
    "/api/v1/flow/scenes/{scene_id}/variations",
    response_model=list[FlowSceneResponse],
    tags=["Flow Studio"],
)
async def create_scene_variations(
    scene_id: str, count: int = Query(default=2, ge=1, le=3), db: AsyncSession = Depends(get_db)
) -> list[FlowScene]:
    orig = await db.get(FlowScene, scene_id)
    if not orig:
        raise HTTPException(status_code=404, detail="Flow scene not found")

    created: list[FlowScene] = []
    angles = ["dramatic low-angle lighting", "golden hour close-up", "wide cinematic reveal"]
    for i in range(count):
        var = FlowScene(
            flow_project_id=orig.flow_project_id,
            order_index=orig.order_index,
            duration_sec=orig.duration_sec,
            scene_prompt=f"{orig.scene_prompt} [Variation: {angles[i % len(angles)]}]",
            narration_text=orig.narration_text,
            camera_motion=orig.camera_motion,
            character_ids_json=orig.character_ids_json,
            variation_index=orig.variation_index + i + 1,
            status="planned",
        )
        db.add(var)
        created.append(var)
    await db.commit()
    for v in created:
        await db.refresh(v)
    return created


@flow_router.post(
    "/api/v1/flow/scenes/{scene_id}/generate",
    response_model=FlowSceneResponse,
    tags=["Flow Studio"],
)
async def generate_flow_scene_clip(
    scene_id: str, db: AsyncSession = Depends(get_db)
) -> FlowScene:
    sc = await db.get(FlowScene, scene_id)
    if not sc:
        raise HTTPException(status_code=404, detail="Flow scene not found")
    proj = await db.get(FlowProject, sc.flow_project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Flow project not found")

    provider = registry.get(proj.provider)
    ref_paths: list[Path] = []
    for cid in sc.character_ids_json or []:
        ch = await db.get(FlowCharacter, cid)
        if ch and ch.reference_image_path:
            ref_paths.append((storage.root / ch.reference_image_path).resolve())

    if sc.video_clip_path:
        hist = list(sc.history_json or [])
        hist.append(
            {
                "version": sc.version,
                "video_clip_path": sc.video_clip_path,
                "scene_prompt": sc.scene_prompt,
                "saved_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        sc.history_json = hist
        flag_modified(sc, "history_json")
        sc.version += 1

    out_mp4 = (
        storage.outputs_dir
        / f"flow_{proj.id}"
        / "clips"
        / f"{sc.id}_v{sc.version}.mp4"
    )

    try:
        req = VideoGenRequest(
            prompt=sc.scene_prompt,
            duration_sec=sc.duration_sec,
            aspect_ratio=proj.aspect_ratio,  # type: ignore[arg-type]
            quality=proj.quality,
            first_frame_path=(storage.root / sc.first_frame_path).resolve()
            if sc.first_frame_path
            else None,
            last_frame_path=(storage.root / sc.last_frame_path).resolve()
            if sc.last_frame_path
            else None,
            reference_image_paths=ref_paths,
            output_mp4_path=out_mp4,
        )
        result = provider.generate_clip(req)
        sc.video_clip_path = str(result.output_mp4_path.relative_to(storage.root)).replace("\\", "/")
        if result.last_frame_path:
            sc.last_frame_path = str(result.last_frame_path.relative_to(storage.root)).replace("\\", "/")
        sc.provider_used = result.provider_id
        sc.status = "completed"
        sc.error_message = None
        await db.commit()
        await db.refresh(sc)
        return sc
    except ProviderNotConfiguredError as exc:
        sc.status = "failed"
        sc.error_message = str(exc)
        await db.commit()
        raise HTTPException(status_code=424, detail=str(exc)) from exc
    except Exception as exc:
        sc.status = "failed"
        sc.error_message = str(exc)
        await db.commit()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@flow_router.post(
    "/api/v1/flow/scenes/{scene_id}/extend",
    response_model=FlowSceneResponse,
    tags=["Flow Studio"],
)
async def extend_flow_scene_clip(
    scene_id: str,
    extension_prompt: str = Form("Continue the scene smoothly with natural motion."),
    db: AsyncSession = Depends(get_db),
) -> FlowScene:
    sc = await db.get(FlowScene, scene_id)
    if not sc or not sc.video_clip_path:
        raise HTTPException(status_code=404, detail="Generated scene clip not found to extend")
    proj = await db.get(FlowProject, sc.flow_project_id)
    assert proj is not None

    provider = registry.get(proj.provider)
    ext_scene = FlowScene(
        flow_project_id=proj.id,
        order_index=sc.order_index + 1,
        duration_sec=sc.duration_sec,
        scene_prompt=f"[Continuation] {extension_prompt}",
        narration_text=extension_prompt,
        camera_motion=sc.camera_motion,
        character_ids_json=sc.character_ids_json,
        first_frame_path=sc.last_frame_path,
        status="planned",
    )
    db.add(ext_scene)
    await db.flush()

    out_mp4 = storage.outputs_dir / f"flow_{proj.id}" / "clips" / f"{ext_scene.id}_ext.mp4"
    try:
        res = provider.generate_clip(
            VideoGenRequest(
                prompt=ext_scene.scene_prompt,
                duration_sec=ext_scene.duration_sec,
                aspect_ratio=proj.aspect_ratio,  # type: ignore[arg-type]
                quality=proj.quality,
                first_frame_path=(storage.root / sc.last_frame_path).resolve()
                if sc.last_frame_path
                else None,
                source_video_path=(storage.root / sc.video_clip_path).resolve(),
                output_mp4_path=out_mp4,
            )
        )
        ext_scene.video_clip_path = str(res.output_mp4_path.relative_to(storage.root)).replace("\\", "/")
        ext_scene.provider_used = res.provider_id
        ext_scene.status = "completed"
        await db.commit()
        await db.refresh(ext_scene)
        return ext_scene
    except ProviderNotConfiguredError as exc:
        ext_scene.status = "failed"
        ext_scene.error_message = str(exc)
        await db.commit()
        raise HTTPException(status_code=424, detail=str(exc)) from exc


@flow_router.get("/api/v1/flow/scenes/{scene_id}/preview", tags=["Flow Studio"])
async def preview_flow_scene(scene_id: str, db: AsyncSession = Depends(get_db)):
    sc = await db.get(FlowScene, scene_id)
    if not sc or not sc.video_clip_path:
        raise HTTPException(status_code=404, detail="Scene clip not generated yet")
    path = (storage.root / sc.video_clip_path).resolve()
    if not path.exists():
        raise HTTPException(status_code=404, detail="Clip missing on disk")
    return FileResponse(str(path), media_type="video/mp4")


@flow_router.post(
    "/api/v1/flow/projects/{project_id}/assemble",
    response_model=FlowProjectResponse,
    tags=["Flow Studio"],
)
async def assemble_flow_project(
    project_id: str,
    include_subtitles: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
) -> FlowProject:
    proj = await db.get(FlowProject, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Flow project not found")

    res = await db.execute(
        select(FlowScene)
        .where(FlowScene.flow_project_id == project_id, FlowScene.status == "completed")
        .order_by(FlowScene.order_index.asc())
    )
    ready_scenes = list(res.scalars().all())
    if not ready_scenes:
        raise HTTPException(
            status_code=400,
            detail="No completed AI video clips found. Generate scene clips first.",
        )

    clip_paths = [(storage.root / s.video_clip_path).resolve() for s in ready_scenes if s.video_clip_path]
    narration = " ".join(s.narration_text for s in ready_scenes if s.narration_text).strip() or proj.prompt
    out_mp4 = storage.outputs_dir / f"flow_{proj.id}" / f"final_{proj.id}.mp4"

    stats = FlowTimelineAssembler(storage).assemble(
        project_id=proj.id,
        clip_paths=clip_paths,
        narration_script=narration,
        aspect_ratio=proj.aspect_ratio,
        voice_id=proj.voice_id,
        output_mp4=out_mp4,
        bgm_path=(storage.root / proj.bgm_path).resolve() if proj.bgm_path else None,
        sfx_path=(storage.root / proj.sfx_path).resolve() if proj.sfx_path else None,
        include_subtitles=include_subtitles,
    )
    proj.final_mp4_path = str(out_mp4.relative_to(storage.root)).replace("\\", "/")
    proj.duration_sec = float(stats["duration_sec"])
    proj.status = "completed"
    await db.commit()
    await db.refresh(proj)
    return proj


@flow_router.get("/api/v1/flow/projects/{project_id}/preview", tags=["Flow Studio"])
async def preview_flow_final(project_id: str, db: AsyncSession = Depends(get_db)):
    proj = await db.get(FlowProject, project_id)
    if not proj or not proj.final_mp4_path:
        raise HTTPException(status_code=404, detail="Final video not assembled yet")
    path = (storage.root / proj.final_mp4_path).resolve()
    return FileResponse(str(path), media_type="video/mp4")


@flow_router.get("/api/v1/flow/projects/{project_id}/download", tags=["Flow Studio"])
async def download_flow_final(project_id: str, db: AsyncSession = Depends(get_db)):
    proj = await db.get(FlowProject, project_id)
    if not proj or not proj.final_mp4_path:
        raise HTTPException(status_code=404, detail="Final video not assembled yet")
    path = (storage.root / proj.final_mp4_path).resolve()
    return FileResponse(str(path), media_type="video/mp4", filename=f"flow_{project_id}.mp4")
