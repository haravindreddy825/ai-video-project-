from typing import Any, Literal, Optional
from pydantic import BaseModel, Field

VisualFormat = Literal[
    "illustration",
    "infographic",
    "diagram",
    "flowchart",
    "chart",
    "text_animation",
    "icon_callout",
    "example",
    "comparison",
    "step_by_step",
]

AnimationStyle = Literal["fade_in", "slide_up", "kinetic_highlight", "step_reveal"]
TransitionStyle = Literal["crossfade", "slide_left", "cut"]


class VisualGenerateRequest(BaseModel):
    audio_id: str
    use_comfyui: bool = False
    render_video: bool = True
    fps: int = Field(default=25, ge=15, le=30)


class VisualSceneCreateRequest(BaseModel):
    audio_id: str
    order_index: int = Field(default=0, ge=0)
    start_ms: int = Field(..., ge=0)
    end_ms: int = Field(..., gt=0)
    sentence_text: str
    main_concept: str = "Core Concept"
    keywords: list[str] = Field(default_factory=list)
    visual_format: VisualFormat = "text_animation"
    visual_description: str = ""
    title_text: str = ""
    body_bullets: list[str] = Field(default_factory=list)
    diagram_spec: Optional[dict[str, Any]] = None
    animation_style: AnimationStyle = "slide_up"
    transition_style: TransitionStyle = "crossfade"


class VisualSceneUpdateRequest(BaseModel):
    title_text: Optional[str] = None
    sentence_text: Optional[str] = None
    main_concept: Optional[str] = None
    visual_format: Optional[VisualFormat] = None
    visual_description: Optional[str] = None
    body_bullets: Optional[list[str]] = None
    diagram_spec: Optional[dict[str, Any]] = None
    start_ms: Optional[int] = Field(default=None, ge=0)
    end_ms: Optional[int] = Field(default=None, gt=0)
    animation_style: Optional[AnimationStyle] = None
    transition_style: Optional[TransitionStyle] = None


class VisualSceneReorderRequest(BaseModel):
    scene_ids: list[str] = Field(..., min_length=1)


class VisualSceneResponse(BaseModel):
    id: str
    project_id: str
    audio_id: str
    order_index: int
    start_ms: int
    end_ms: int
    sentence_text: str
    main_concept: str
    keywords_json: Optional[list[str]] = None
    visual_format: str
    visual_description: str
    title_text: str
    body_bullets_json: Optional[list[str]] = None
    diagram_spec_json: Optional[dict[str, Any]] = None
    animation_style: str
    transition_style: str
    generator_used: str
    image_path: Optional[str] = None
    video_path: Optional[str] = None
    approved: bool

    model_config = {"from_attributes": True}


class VisualAssetResponse(BaseModel):
    id: str
    project_id: str
    scene_id: Optional[str]
    asset_type: str
    file_path: str
    width: int
    height: int
    metadata_json: Optional[dict[str, Any]] = None

    model_config = {"from_attributes": True}
