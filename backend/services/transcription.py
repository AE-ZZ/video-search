from pathlib import Path
from pywhispercpp.model import Model

from backend.config import WHISPER_MODEL


def load_whisper_model() -> Model:
    return Model(WHISPER_MODEL)


def transcribe(model: Model, audio_path: Path) -> list[dict]:
    """Transcribe audio and return timestamped segments."""
    segments = model.transcribe(str(audio_path))

    results = []
    for seg in segments:
        results.append({
            "start": round(seg.t0 / 100, 2),  # centiseconds to seconds
            "end": round(seg.t1 / 100, 2),
            "text": seg.text.strip(),
        })

    return results
