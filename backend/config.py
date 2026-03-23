import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
VIDEOS_DIR = DATA_DIR / "videos"
AUDIO_DIR = DATA_DIR / "audio"
FRAMES_DIR = DATA_DIR / "frames"
CHROMA_DIR = DATA_DIR / "chroma_db"

for d in [VIDEOS_DIR, AUDIO_DIR, FRAMES_DIR, CHROMA_DIR]:
    d.mkdir(parents=True, exist_ok=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
VIDEO_LIBRARY_PATH = os.getenv("VIDEO_LIBRARY_PATH", "")

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv"}

# Model settings
WHISPER_MODEL = "large-v3"  # tiny, base, small, medium, large-v3
CLIP_MODEL = "ViT-B-32"
CLIP_PRETRAINED = "laion2b_s34b_b79k"
SENTENCE_MODEL = "all-MiniLM-L6-v2"

# Processing settings
FRAME_SAMPLE_INTERVAL = 2  # extract 1 frame every N seconds
