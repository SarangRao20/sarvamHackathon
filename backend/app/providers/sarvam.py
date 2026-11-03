"""Sarvam AI speech adapters: Saaras (speech-to-text) and Bulbul (text-to-speech).

API reference: https://docs.sarvam.ai

Both adapters share one retry policy: transient failures (429, 5xx, timeouts, network
errors) are retried with exponential backoff; everything else raises immediately so a
bad request surfaces instead of being retried three times.
"""
from __future__ import annotations

import base64
import io
import logging
import time
import wave
from pathlib import Path
from typing import Any, Callable

import httpx

from ..config import settings
from .base import ProviderError, ProviderUnavailable, SpeechResult, TranscriptionResult

log = logging.getLogger("aapda.providers.sarvam")

#: Sarvam Saaras accepts these ``language_code`` values. ``unknown`` asks the model to
#: detect the language itself, which is what the live call and uploads use by default.
AUTO_DETECT = "unknown"
STT_LANGUAGES = frozenset({
    AUTO_DETECT,
    "hi-IN", "bn-IN", "kn-IN", "ml-IN", "mr-IN", "od-IN", "pa-IN", "ta-IN", "te-IN",
    "en-IN", "gu-IN", "as-IN", "ur-IN", "ne-IN", "kok-IN", "ks-IN", "sd-IN", "sa-IN",
    "sat-IN", "mni-IN", "brx-IN", "mai-IN", "doi-IN",
})

#: Short internal language hints -> Sarvam BCP-47 tags. Anything not listed (including
#: ``None``, ``"auto"`` and ``"mixed"``) falls through to auto-detection.
LANGUAGE_TAGS = {
    "hi": "hi-IN", "mr": "mr-IN", "en": "en-IN", "bn": "bn-IN", "gu": "gu-IN",
    "kn": "kn-IN", "ml": "ml-IN", "or": "od-IN", "pa": "pa-IN", "ta": "ta-IN",
    "te": "te-IN", "as": "as-IN", "ur": "ur-IN", "ne": "ne-IN", "sa": "sa-IN",
}

#: Bulbul v3 voices, one per language. Keyed by the Sarvam tag so a language detected
#: by Saaras can be answered in the same language without a second mapping step.
BULBUL_VOICES = {
    "hi-IN": "aditya", "mr-IN": "neha", "en-IN": "ritu", "ta-IN": "pooja",
    "te-IN": "rohan", "kn-IN": "simran", "ml-IN": "kavya", "gu-IN": "amit",
    "bn-IN": "dev", "pa-IN": "ishita",
}
TTS_FALLBACK = ("hi-IN", "aditya")

STT_MODEL = "saaras:v3"
TTS_MODEL = "bulbul:v3"
TRANSIENT_STATUS = frozenset({429, 500, 502, 503, 504})


def stt_language_code(language: str | None) -> str:
    """Map an internal language hint to a Saaras ``language_code``.

    Unrecognised hints become auto-detection rather than a silent default, so a caller
    speaking Tamil is never transcribed as if they were speaking Hindi.
    """
    if not language:
        return AUTO_DETECT
    if language in STT_LANGUAGES:
        return language
    return LANGUAGE_TAGS.get(language, AUTO_DETECT)


def tts_voice(language: str | None) -> tuple[str, str]:
    """Return the ``(language_code, speaker)`` Bulbul should speak with."""
    tag = language if language in BULBUL_VOICES else LANGUAGE_TAGS.get(language or "", "")
    if tag in BULBUL_VOICES:
        return tag, BULBUL_VOICES[tag]
    return TTS_FALLBACK


def pcm_from_wav(data: bytes) -> tuple[bytes, int]:
    """Strip the RIFF header off Bulbul's response. Returns ``(pcm_s16le, sample_rate)``."""
    with wave.open(io.BytesIO(data)) as w:
        return w.readframes(w.getnframes()), w.getframerate()


class _SarvamClient:
    """Shared credentials, timeout and retry policy for the Sarvam REST endpoints."""

    mode = "real"
    label = "Sarvam"

    def __init__(self, api_key: str | None = None, base_url: str | None = None,
                 timeout_s: float | None = None, max_retries: int | None = None,
                 transport: httpx.BaseTransport | None = None):
        self._api_key = api_key if api_key is not None else settings.sarvam_api_key
        self.base_url = (base_url or settings.sarvam_base_url).rstrip("/")
        self.timeout_s = 30.0 if timeout_s is None else timeout_s
        self.max_retries = 2 if max_retries is None else max_retries
        self._transport = transport
        if not self._api_key:
            raise ProviderUnavailable("SARVAM_API_KEY is not configured")

    def _post(self, path: str, send: Callable[[httpx.Client], httpx.Response]) -> dict[str, Any]:
        attempt = 0
        with httpx.Client(timeout=self.timeout_s, transport=self._transport) as client:
            while True:
                attempt += 1
                try:
                    resp = send(client)
                except httpx.TimeoutException as exc:
                    err = ProviderError(f"{self.label} timed out after {self.timeout_s}s", transient=True)
                    err.__cause__ = exc
                except httpx.HTTPError as exc:
                    err = ProviderError(f"{self.label} network error: {type(exc).__name__}", transient=True)
                    err.__cause__ = exc
                else:
                    if resp.status_code == 200:
                        try:
                            body = resp.json()
                        except ValueError as exc:
                            raise ProviderError(f"{self.label} returned a non-JSON response") from exc
                        if not isinstance(body, dict):
                            raise ProviderError(f"{self.label} response was not a JSON object")
                        return body
                    err = ProviderError(
                        self._error_message(resp),
                        transient=resp.status_code in TRANSIENT_STATUS,
                        status_code=resp.status_code,
                    )
                log.warning("%s %s attempt %d failed: %s", self.label, path, attempt, err)
                if not err.transient or attempt > self.max_retries:
                    raise err
                time.sleep(min(1.0 * (1.5 ** (attempt - 1)), 5.0))

    def _error_message(self, resp: httpx.Response) -> str:
        detail = ""
        try:
            body = resp.json()
            if isinstance(body, dict):
                e = body.get("error") or body.get("detail") or body.get("message")
                detail = e.get("message", "") if isinstance(e, dict) else str(e or "")
        except ValueError:
            pass
        hint = {
            400: "invalid audio format or parameters",
            401: "invalid or missing api-subscription-key",
            403: "insufficient credits or permissions",
            413: "payload too large",
            429: "rate limit exceeded",
        }.get(resp.status_code, "provider error")
        return f"{self.label} HTTP {resp.status_code}: {hint}" + (f" — {detail[:200]}" if detail else "")


class SarvamSTT(_SarvamClient):
    """Sarvam Saaras speech-to-text."""

    label = "Sarvam Saaras STT"
    name = "sarvam-saaras"

    def transcribe(self, audio_path: Path, mime_type: str, language: str | None) -> TranscriptionResult:
        with audio_path.open("rb") as fh:
            return self._transcribe((audio_path.name, fh.read(), mime_type), language)

    def transcribe_bytes(self, audio: bytes, language: str | None, filename: str = "call.wav",
                         mime_type: str = "audio/wav") -> TranscriptionResult:
        """Transcribe audio already in memory — used by the live call, which never writes a file."""
        return self._transcribe((filename, audio, mime_type), language)

    def _transcribe(self, file_part: tuple[str, bytes, str], language: str | None) -> TranscriptionResult:
        code = stt_language_code(language)
        body = self._post(
            "/speech-to-text",
            lambda client: client.post(
                f"{self.base_url}/speech-to-text",
                headers={"api-subscription-key": self._api_key},
                data={"model": STT_MODEL, "language_code": code},
                files={"file": file_part},
            ),
        )
        transcript = body.get("transcript")
        if not isinstance(transcript, str):
            raise ProviderError("Sarvam Saaras STT response has no transcript field")
        return TranscriptionResult(
            transcript=transcript,
            provider=self.name,
            mode=self.mode,
            language_code=body.get("language_code") or (None if code == AUTO_DETECT else code),
            request_id=body.get("request_id"),
            raw=body,
        )


class SarvamTTS(_SarvamClient):
    """Sarvam Bulbul text-to-speech."""

    label = "Sarvam Bulbul TTS"
    name = "sarvam-bulbul"

    def synthesize(self, text: str, language: str, sample_rate: int | None = None) -> SpeechResult:
        lang_code, speaker = tts_voice(language)
        payload: dict[str, Any] = {
            "inputs": [text],
            "target_language_code": lang_code,
            "speaker": speaker,
            "model": TTS_MODEL,
            "enable_preprocessing": True,
        }
        if sample_rate:
            payload["speech_sample_rate"] = sample_rate
        body = self._post(
            "/text-to-speech",
            lambda client: client.post(
                f"{self.base_url}/text-to-speech",
                headers={"api-subscription-key": self._api_key},
                json=payload,
            ),
        )
        audios = body.get("audios")
        if not (isinstance(audios, list) and audios and isinstance(audios[0], str)):
            raise ProviderError("Sarvam Bulbul TTS response contained no audio")
        try:
            wav = base64.b64decode(audios[0])
        except (ValueError, TypeError) as exc:
            raise ProviderError("Sarvam Bulbul TTS audio was not valid base64") from exc
        return SpeechResult(
            audio=wav,
            content_type="audio/wav",
            provider=self.name,
            mode=self.mode,
            voice=speaker,
            language_code=lang_code,
        )
