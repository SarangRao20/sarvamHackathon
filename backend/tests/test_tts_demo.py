from app.providers.base import SpeechResult


class FakeTTS:
    def synthesize(self, text, language):
        assert text.startswith("सूचना:")
        assert language == "hi"
        return SpeechResult(b"demo wav", "audio/wav", "sarvam-bulbul", "real", "meera", "hi-IN")


def test_demo_voice_preview_uses_bulbul_and_returns_audio(client, monkeypatch):
    from app.api import system

    monkeypatch.setattr(system, "get_tts", lambda: FakeTTS())
    response = client.get("/api/demo/voice-preview")

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content == b"demo wav"


def test_demo_voice_preview_reports_unavailable_tts(client):
    response = client.get("/api/demo/voice-preview")

    assert response.status_code == 503
