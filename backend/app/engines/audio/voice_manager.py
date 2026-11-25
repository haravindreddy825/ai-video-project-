from app.engines.audio.schemas import VoicePreset


class VoiceManager:
    """Manages supported Kokoro-82M voice presets and validates selections."""

    PRESETS: list[VoicePreset] = [
        VoicePreset(
            id="af_heart",
            name="Heart (US Female)",
            gender="female",
            accent="American English",
            description="Warm, clear, engaging educational presenter voice.",
        ),
        VoicePreset(
            id="af_bella",
            name="Bella (US Female)",
            gender="female",
            accent="American English",
            description="Bright, articulate voice suited for explainers.",
        ),
        VoicePreset(
            id="af_sarah",
            name="Sarah (US Female)",
            gender="female",
            accent="American English",
            description="Calm, authoritative instructional tone.",
        ),
        VoicePreset(
            id="af_nicole",
            name="Nicole (US Female)",
            gender="female",
            accent="American English",
            description="Soft, steady narration voice.",
        ),
        VoicePreset(
            id="am_adam",
            name="Adam (US Male)",
            gender="male",
            accent="American English",
            description="Deep, clear male presenter voice.",
        ),
        VoicePreset(
            id="am_michael",
            name="Michael (US Male)",
            gender="male",
            accent="American English",
            description="Energetic, conversational male voice.",
        ),
        VoicePreset(
            id="bf_emma",
            name="Emma (UK Female)",
            gender="female",
            accent="British English",
            description="Crisp British academic narration voice.",
        ),
        VoicePreset(
            id="bm_george",
            name="George (UK Male)",
            gender="male",
            accent="British English",
            description="Measured British documentary presenter voice.",
        ),
    ]

    @classmethod
    def list_presets(cls) -> list[VoicePreset]:
        return cls.PRESETS

    @classmethod
    def validate_voice_id(cls, voice_id: str) -> str:
        valid_ids = {p.id for p in cls.PRESETS}
        if voice_id not in valid_ids:
            raise ValueError(
                f"Unknown voice_id '{voice_id}'. Supported presets: {sorted(valid_ids)}"
            )
        return voice_id
