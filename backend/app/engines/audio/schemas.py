from typing import Literal, Optional
from pydantic import BaseModel, Field


class VoicePreset(BaseModel):
    id: str
    name: str
    gender: Literal["female", "male"]
    accent: str
    language: str = "en"
    description: str


class WordTiming(BaseModel):
    word: str
    start_ms: int = Field(..., ge=0)
    end_ms: int = Field(..., ge=0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class PauseSegment(BaseModel):
    after_sentence_index: int = Field(..., ge=0)
    start_ms: int = Field(..., ge=0)
    end_ms: int = Field(..., ge=0)
    duration_ms: int = Field(..., ge=0)


class SentenceTiming(BaseModel):
    index: int = Field(..., ge=0)
    text: str
    start_ms: int = Field(..., ge=0)
    end_ms: int = Field(..., ge=0)
    words: list[WordTiming] = Field(default_factory=list)


class AlignmentValidation(BaseModel):
    audio_duration_ms: int
    last_word_end_ms: int
    word_count_expected: int
    word_count_transcribed: int
    coverage_ratio: float
    monotonic_ok: bool
    within_duration_ok: bool
    passed: bool
    warnings: list[str] = Field(default_factory=list)


class AlignmentResult(BaseModel):
    language: str = "en"
    full_transcript: str
    audio_duration_sec: float
    sentences: list[SentenceTiming] = Field(default_factory=list)
    words: list[WordTiming] = Field(default_factory=list)
    pauses: list[PauseSegment] = Field(default_factory=list)
    validation: AlignmentValidation


class SentenceInstruction(BaseModel):
    index: int
    text: str
    sentence_type: Literal["question", "explanation", "example", "conclusion", "statement"]
    emotion: Literal["curious", "enthusiastic", "serious", "calm", "neutral"]
    facial_expression: str
    hand_gesture: str
    head_movement: str
    highlight_words: list[str] = Field(default_factory=list)


class ScriptIntelligenceResult(BaseModel):
    original_script: str
    total_sentences: int
    estimated_speaking_rate_wpm: float
    sentences: list[SentenceInstruction] = Field(default_factory=list)


class AudioGenerateRequest(BaseModel):
    script_id: Optional[str] = None
    script_text: Optional[str] = Field(default=None, min_length=5)
    voice_id: str = "af_heart"
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    volume: float = Field(default=1.0, ge=0.1, le=2.0)
    auto_align: bool = True


class AudioAlignRequest(BaseModel):
    model_size: Optional[str] = None
    language: str = "en"


class AudioTrackResponse(BaseModel):
    id: str
    project_id: str
    script_id: Optional[str]
    voice_config_id: Optional[str]
    engine: str
    voice_id: str
    speed: float
    volume: float
    status: str
    progress_pct: int
    audio_file_path: Optional[str]
    sample_rate: int
    duration_sec: float
    original_script_text: str
    alignment_json: Optional[dict] = None
    script_intelligence_json: Optional[dict] = None
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}
