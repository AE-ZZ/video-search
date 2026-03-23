import subprocess
import json
from pathlib import Path

from backend.config import AUDIO_DIR, FRAMES_DIR, FRAME_SAMPLE_INTERVAL


def get_video_duration(video_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            str(video_path),
        ],
        capture_output=True, text=True,
    )
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def extract_audio(video_path: Path, video_id: str) -> Path:
    output_path = AUDIO_DIR / f"{video_id}.wav"
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(video_path),
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            str(output_path),
        ],
        capture_output=True, check=True,
    )
    return output_path


def extract_frames(video_path: Path, video_id: str) -> list[tuple[Path, float]]:
    """Extract frames at fixed intervals. Returns list of (frame_path, timestamp)."""
    frame_dir = FRAMES_DIR / video_id
    frame_dir.mkdir(parents=True, exist_ok=True)

    fps = 1.0 / FRAME_SAMPLE_INTERVAL
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(video_path),
            "-vf", f"fps={fps}",
            "-q:v", "2",
            str(frame_dir / "frame_%04d.jpg"),
        ],
        capture_output=True, check=True,
    )

    frames = []
    for frame_path in sorted(frame_dir.glob("frame_*.jpg")):
        # frame_0001.jpg -> index 0 -> timestamp 0*interval
        idx = int(frame_path.stem.split("_")[1]) - 1
        timestamp = idx * FRAME_SAMPLE_INTERVAL
        frames.append((frame_path, timestamp))

    return frames
