from pathlib import Path
from faster_whisper import WhisperModel

from backend.config import WHISPER_MODEL


def load_whisper_model() -> WhisperModel:
    return WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")


def transcribe(model: WhisperModel, audio_path: Path) -> list[dict]:
    """Transcribe audio and return timestamped segments."""
    segments, _info = model.transcribe(str(audio_path), beam_size=5)

    results = []
    for seg in segments:
        results.append({
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
        })

    return results
