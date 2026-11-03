"""Provider selection and status reporting (Sarvam AI only)."""
from __future__ import annotations

from ..config import settings
from .base import ProviderUnavailable, SpeechToText, TextToSpeech
from .mock_stt import MockFixtureSTT
from .sarvam import SarvamSTT, SarvamTTS


def get_stt(mode_override: str | None = None) -> SpeechToText:
    """Select STT provider: sarvam or mock."""
    mode = (mode_override or settings.stt_provider or "auto").lower()

    if mode == "sarvam":
        return SarvamSTT()
    if mode == "mock":
        return MockFixtureSTT()
    if mode == "auto":
        if settings.sarvam_api_key:
            try:
                return SarvamSTT()
            except ProviderUnavailable:
                pass
        return MockFixtureSTT()

    raise ValueError(f"unknown STT provider mode: {mode}")


def get_tts(mode_override: str | None = None) -> TextToSpeech | None:
    """Select TTS provider: sarvam or none."""
    mode = (mode_override or settings.tts_provider or "auto").lower()

    if mode == "none":
        return None
    if mode == "sarvam":
        try:
            return SarvamTTS()
        except ProviderUnavailable:
            return None
    if mode == "auto":
        if settings.sarvam_api_key:
            try:
                return SarvamTTS()
            except ProviderUnavailable:
                pass
        return None

    raise ValueError(f"unknown TTS provider mode: {mode}")


def provider_status(stt_mode: str | None = None, tts_mode: str | None = None) -> dict:
    sarvam_key = bool(settings.sarvam_api_key)
    stt = get_stt(stt_mode)
    tts = get_tts(tts_mode)
    return {
        "sarvam_api_key_configured": sarvam_key,
        "sarvam_base_url": settings.sarvam_base_url,
        "speech_to_text": {
            "active": stt.name if stt else None,
            "mode": stt.mode if stt else "unavailable",
            "note": (
                "Sarvam Saaras STT active" if (stt and stt.name == "sarvam-saaras") else
                "Mock STT (offline fixture lookup only)."
            ),
        },
        "extraction": {
            "active": "rule-based",
            "mode": "rule_based",
            "note": "Offline rule-based entity extraction (keywords, patterns, geography).",
        },
        "text_to_speech": {
            "active": tts.name if tts else None,
            "mode": tts.mode if tts else "unavailable",
            "note": (
                "Sarvam Bulbul TTS active" if (tts and tts.name == "sarvam-bulbul") else
                "Text-only acknowledgements (configure SARVAM_API_KEY for voice)."
            ),
        },
    }
