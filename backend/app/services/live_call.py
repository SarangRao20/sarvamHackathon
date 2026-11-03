"""Awaaz Live: one spoken emergency report, carried over a single WebSocket.

A turn is: the caller speaks -> Sarvam Saaras transcribes -> the rule-based extractor
updates what we know -> the assistant asks for whichever fact is still missing ->
Sarvam Bulbul speaks that question. When location, hazard and headcount are all known
(or the caller hangs up) the accumulated transcript is saved as a normal report and
handed to the usual processing pipeline, so a live call lands in the same queue as an
uploaded recording.

The end of a caller's turn is detected from frame energy; the caller can also end it
explicitly with "I've finished speaking", which is what the ``commit`` message is.

Wire protocol: see ``frontend/src/lib/liveCall.ts``. Audio is raw little-endian
signed 16-bit mono PCM at 16 kHz in both directions, which is what the browser's
AudioWorklet produces and what Bulbul is asked to return.
"""
from __future__ import annotations

import array
import asyncio
import io
import logging
import math
import time
import uuid
import wave
from dataclasses import dataclass, field
from typing import Any

from .. import models
from ..db import session_scope
from ..providers.base import ProviderError, ProviderUnavailable
from ..providers.registry import get_stt, get_tts
from ..providers.sarvam import pcm_from_wav
from .extraction import extract
from .pipeline import audit, new_report_id
from .priority import features_from_extraction, label_for, score
from .settings_store import get_config
from .worker import worker

log = logging.getLogger("aapda.live")

RATE = 16000
BYTES_PER_SAMPLE = 2
FRAME_BYTES = 1024                      # 512 samples, ~32 ms — one AudioWorklet frame
SILENCE_RMS = 420.0                     # below this a frame counts as silence
SPEECH_RMS = 900.0                      # above this the caller is considered talking
HANGOVER_FRAMES = 25                    # ~0.8 s of silence closes a turn
MIN_SPEECH_FRAMES = 12                  # ~0.4 s — ignores a cough or a door
MAX_TURN_BYTES = 28 * RATE * BYTES_PER_SAMPLE   # Saaras rejects audio over 30 s
OUT_CHUNK_BYTES = 8192
MAX_TURNS = 8                           # a caller is never kept on the line forever
MAX_CONCURRENT_CALLS = 6                # each live call spends Sarvam credits

#: Questions the assistant asks, per internal language. ``mixed`` (Hinglish) is spoken
#: with the Hindi voice, so it shares the Hindi script.
PROMPTS: dict[str, dict[str, str]] = {
    "hi": {
        "greeting": "नमस्ते। आप किस जगह से बोल रहे हैं और वहाँ क्या हुआ है?",
        "location_missing": "आप कौन से गाँव या इलाके से बोल रहे हैं?",
        "disaster_unknown": "वहाँ क्या हुआ है? पानी भरा है, आग लगी है, या ज़मीन धँसी है?",
        "people_unknown": "वहाँ कितने लोग फँसे हुए हैं?",
        "repeat": "माफ़ कीजिए, आपकी आवाज़ साफ़ नहीं आई। कृपया दोबारा बोलिए।",
        "closing": "आपकी जानकारी दर्ज कर ली गई है। कृपया आधिकारिक आपातकालीन सेवाओं से भी संपर्क करें।",
    },
    "mr": {
        "greeting": "नमस्कार. तुम्ही कोणत्या ठिकाणाहून बोलत आहात आणि तिथे काय झाले आहे?",
        "location_missing": "तुम्ही कोणत्या गावातून किंवा भागातून बोलत आहात?",
        "disaster_unknown": "तिथे काय झाले आहे? पाणी भरले आहे, आग लागली आहे, की जमीन खचली आहे?",
        "people_unknown": "तिथे किती लोक अडकले आहेत?",
        "repeat": "क्षमा करा, तुमचा आवाज स्पष्ट आला नाही. कृपया पुन्हा सांगा.",
        "closing": "तुमची माहिती नोंदवली आहे. कृपया अधिकृत आपत्कालीन सेवांशीही संपर्क साधा.",
    },
    "en": {
        "greeting": "Hello. Where are you calling from, and what has happened there?",
        "location_missing": "Which village or area are you calling from?",
        "disaster_unknown": "What has happened there? Is it flooding, a fire, or a landslide?",
        "people_unknown": "How many people are trapped there?",
        "repeat": "Sorry, I could not hear that clearly. Please say it again.",
        "closing": "Your information has been recorded. Please also contact official emergency services.",
    },
}
PROMPT_LANGUAGES = frozenset(PROMPTS)

#: Sarvam tag -> the internal language the prompts and acknowledgements are written in.
DETECTED_TO_INTERNAL = {"hi-IN": "hi", "mr-IN": "mr", "en-IN": "en"}


def prompts_for(language: str | None) -> dict[str, str]:
    return PROMPTS[language if language in PROMPT_LANGUAGES else "hi"]


#: Calls currently on the line, newest last. The Situation Room polls these so a
#: dispatcher can watch a report being built while the caller is still speaking.
ACTIVE: dict[str, "LiveCall"] = {}


def active_summaries() -> list[dict[str, Any]]:
    return [call.summary() for call in list(ACTIVE.values())]


def frame_rms(frame: bytes) -> float:
    """Root-mean-square amplitude of one PCM frame, 0 for an empty or odd-length frame."""
    if len(frame) < BYTES_PER_SAMPLE:
        return 0.0
    samples = array.array("h")
    samples.frombytes(frame[: len(frame) - (len(frame) % BYTES_PER_SAMPLE)])
    if not samples:
        return 0.0
    return math.sqrt(sum(float(s) * s for s in samples) / len(samples))


def pcm_to_wav(pcm: bytes, rate: int = RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(BYTES_PER_SAMPLE)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


@dataclass
class CallFacts:
    """What the dashboard shows filling in while the caller is still talking."""

    place: str | None = None
    disaster: str | None = None
    people: int | None = None
    priority: str | None = None
    score: float | None = None
    report_id: str | None = None
    needs_review: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "place": self.place, "disaster": self.disaster, "people": self.people,
            "priority": self.priority, "score": self.score,
            "report_id": self.report_id, "needs_review": self.needs_review,
        }


@dataclass
class CallState:
    """Everything one in-flight call knows about itself."""

    language: str | None = None          # internal code: hi | mr | en | mixed
    turns: list[str] = field(default_factory=list)
    facts: CallFacts = field(default_factory=CallFacts)
    extraction: dict[str, Any] | None = None
    asked: set[str] = field(default_factory=set)

    @property
    def transcript(self) -> str:
        return " ".join(self.turns).strip()

    def next_question(self) -> str | None:
        """The first still-missing fact we have not already asked about."""
        for key, known in (
            ("location_missing", self.facts.place),
            ("disaster_unknown", self.facts.disaster),
            ("people_unknown", self.facts.people),
        ):
            if not known and key not in self.asked:
                return key
        return None


def update_facts(state: CallState) -> dict[str, Any]:
    """Re-run extraction and priority over everything said so far."""
    ext = extract(state.transcript).model_dump()
    state.extraction = ext

    loc = ext.get("location") or {}
    people = ext.get("people_affected") or {}
    disaster = ext.get("disaster_type")

    state.facts.place = loc.get("place_name") or loc.get("landmark")
    state.facts.disaster = disaster if disaster not in (None, "unknown") else None
    state.facts.people = people.get("count")
    state.facts.needs_review = bool(ext.get("requires_human_review", True))

    with session_scope() as db:
        cfg = get_config(db)
    scored = score(features_from_extraction(ext), cfg)
    state.facts.priority = scored.get("label") or label_for(scored.get("score", 0.0), cfg["thresholds"])
    state.facts.score = scored.get("score")

    detected = ext.get("language")
    if state.language is None and detected and detected != "unknown":
        state.language = detected
    return ext


def save_report(state: CallState) -> str | None:
    """Persist the call as a normal report and queue it for the usual pipeline."""
    transcript = state.transcript
    if not transcript:
        return None
    report_id = new_report_id()
    with session_scope() as db:
        rep = models.Report(
            id=report_id,
            source="live_call",
            is_synthetic=False,
            language_hint=state.language if state.language in PROMPT_LANGUAGES else None,
            status="queued",
            review_reasons=[],
            transcript=transcript,
            transcript_source="sarvam_saaras",
            transcript_provider="sarvam-saaras",
            transcript_provider_mode="real",
        )
        db.add(rep)
        audit(db, "report", report_id, "created",
              new={"source": "live_call", "turns": len(state.turns), "chars": len(transcript)})
    worker.enqueue(report_id)
    state.facts.report_id = report_id
    return report_id


class TurnBuffer:
    """Collects caller audio and decides, from frame energy, when a turn has ended."""

    def __init__(self) -> None:
        self._pcm = bytearray()
        self._speech_frames = 0
        self._silence_frames = 0
        self._started = False

    def add(self, frame: bytes) -> bool:
        """Append one frame. Returns True when the turn looks complete."""
        self._pcm.extend(frame)
        rms = frame_rms(frame)
        if rms >= SPEECH_RMS:
            self._started = True
            self._speech_frames += 1
            self._silence_frames = 0
        elif rms < SILENCE_RMS:
            if self._started:
                self._silence_frames += 1
        if len(self._pcm) >= MAX_TURN_BYTES:
            return True
        return self._started and self._speech_frames >= MIN_SPEECH_FRAMES and self._silence_frames >= HANGOVER_FRAMES

    @property
    def has_speech(self) -> bool:
        return self._speech_frames >= MIN_SPEECH_FRAMES

    def take(self) -> bytes:
        pcm = bytes(self._pcm)
        self._pcm.clear()
        self._speech_frames = self._silence_frames = 0
        self._started = False
        return pcm


class LiveCall:
    """Drives one call: owns the transport-agnostic turn logic and the Sarvam calls."""

    def __init__(self, send_json, send_bytes, call_id: str | None = None) -> None:
        self.id = call_id or uuid.uuid4().hex[:8]
        self._send_json = send_json
        self._send_bytes = send_bytes
        self.state = CallState()
        self.buffer = TurnBuffer()
        self.speaking = asyncio.Event()
        self.speaking.set()                 # not speaking == safe to listen
        self.finished = False
        self._stt = None
        self._tts = None
        self.current_state = "connecting"
        self.started_at = time.time()
        self.ended_at: float | None = None
        self.turns_history: list[dict[str, Any]] = []
        self.asking_for: str | None = None
        self.last_response_ms: float | None = None

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "language": self.state.language or "hi",
            "state": self.current_state,
            "started_at": int(self.started_at * 1000),
            "ended_at": int(self.ended_at * 1000) if self.ended_at else None,
            "turns": list(self.turns_history),
            "facts": self.state.facts.as_dict(),
            "asking_for": self.asking_for,
            "last_response_ms": self.last_response_ms,
        }

    async def _update_state(self, new_state: str) -> None:
        self.current_state = new_state
        await self._send_json({"type": "state", "state": new_state})

    # -- provider access -------------------------------------------------------
    def open_providers(self) -> str | None:
        """Returns a message to show the caller when speech is only partly available."""
        try:
            self._stt = get_stt()
        except ProviderUnavailable as exc:
            raise ProviderError(f"speech-to-text unavailable: {exc}") from exc
        if getattr(self._stt, "name", "") != "sarvam-saaras":
            return ("Sarvam speech-to-text is not configured, so this call cannot be "
                    "transcribed. Set SARVAM_API_KEY and start a new call.")
        self._tts = get_tts()
        if self._tts is None:
            return "Sarvam text-to-speech is not configured, so questions appear as text only."
        return None

    # -- one turn --------------------------------------------------------------
    async def transcribe(self, pcm: bytes) -> tuple[str, float]:
        started = time.monotonic()
        wav = pcm_to_wav(pcm)
        result = await asyncio.to_thread(self._stt.transcribe_bytes, wav, self.state.language)
        elapsed_ms = (time.monotonic() - started) * 1000
        if result.language_code and self.state.language is None:
            self.state.language = DETECTED_TO_INTERNAL.get(result.language_code, "hi")
        return (result.transcript or "").strip(), elapsed_ms

    async def speak(self, text: str) -> float:
        """Send one spoken line, then wait for the browser to finish playing it."""
        self.turns_history.append({"speaker": "assistant", "text": text, "at": int(time.time() * 1000)})
        await self._send_json({"type": "assistant", "text": text})
        if self._tts is None:
            return 0.0
        started = time.monotonic()
        try:
            speech = await asyncio.to_thread(
                self._tts.synthesize, text, self.state.language or "hi", RATE)
            pcm, rate = pcm_from_wav(speech.audio)
        except ProviderError as exc:
            log.warning("live tts failed: %s", exc)
            await self._send_json({"type": "notice", "message": "The spoken reply could not be generated."})
            return (time.monotonic() - started) * 1000
        elapsed_ms = (time.monotonic() - started) * 1000
        if rate != RATE:   # the browser plays everything back at RATE
            log.warning("bulbul returned %d Hz, expected %d", rate, RATE)

        self.speaking.clear()
        await self._update_state("speaking")
        await self._send_json({"type": "audio_start"})
        for i in range(0, len(pcm), OUT_CHUNK_BYTES):
            await self._send_bytes(pcm[i:i + OUT_CHUNK_BYTES])
        await self._send_json({"type": "audio_end"})
        return elapsed_ms

    async def listen(self) -> None:
        await self._update_state("listening")

    async def handle_turn(self, pcm: bytes) -> None:
        """Transcribe one caller turn, update the facts, and ask the next question."""
        turn_started = time.monotonic()
        await self._update_state("thinking")

        try:
            text, stt_ms = await self.transcribe(pcm)
        except ProviderError as exc:
            log.warning("live stt failed: %s", exc)
            await self._send_json({"type": "notice", "message": "That turn could not be transcribed."})
            await self.listen()
            return

        prompts = prompts_for(self.state.language)
        if not text:
            await self.speak(prompts["repeat"])
            return

        self.turns_history.append({"speaker": "caller", "text": text, "at": int(time.time() * 1000)})
        await self._send_json({"type": "caller", "text": text})
        self.state.turns.append(text)
        update_facts(self.state)
        prompts = prompts_for(self.state.language)   # language may have just been detected

        question = self.state.next_question()
        self.asking_for = question
        await self._send_json({
            "type": "facts",
            "facts": self.state.facts.as_dict(),
            "asking_for": question,
        })

        if question is None or len(self.state.turns) >= MAX_TURNS:
            reply_ms = await self.speak(prompts["closing"])
            await self._emit_metrics(turn_started, stt_ms, reply_ms)
            await self.finish()
            return

        self.state.asked.add(question)
        reply_ms = await self.speak(prompts[question])
        await self._emit_metrics(turn_started, stt_ms, reply_ms)

    async def _emit_metrics(self, turn_started: float, stt_ms: float, reply_ms: float) -> None:
        total_ms = round((time.monotonic() - turn_started) * 1000)
        self.last_response_ms = total_ms
        await self._send_json({
            "type": "metrics",
            "stt_ms": round(stt_ms),
            "reply_ms": round(reply_ms),
            "total_ms": total_ms,
        })

    # -- lifecycle -------------------------------------------------------------
    async def start(self, language: str | None) -> None:
        if language in PROMPT_LANGUAGES:
            self.state.language = language
        notice = self.open_providers()
        if notice:
            await self._send_json({"type": "notice", "message": notice})
        await self.speak(prompts_for(self.state.language)["greeting"])

    async def finish(self) -> None:
        if self.finished:
            return
        self.finished = True
        self.ended_at = time.time()
        self.current_state = "ended"
        report_id = await asyncio.to_thread(save_report, self.state)
        if report_id:
            await self._send_json({"type": "facts", "facts": self.state.facts.as_dict(), "asking_for": None})
        await self._send_json({"type": "done", "report_id": report_id})
        await self._send_json({"type": "state", "state": "ended"})
