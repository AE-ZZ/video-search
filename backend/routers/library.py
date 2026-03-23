from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from backend.config import FRAMES_DIR, FRAME_SAMPLE_INTERVAL

router = APIRouter(tags=["library"])


@router.get("/library")
async def list_library(request: Request):
    """List all videos in the library with their processing status."""
    manager = request.app.state.library_manager
    return manager.get_all_status()


@router.get("/library/{video_id}/stream")
async def stream_video(video_id: str, request: Request):
    """Stream a video file from the library."""
    manager = request.app.state.library_manager
    info = manager.video_status.get(video_id)
    if not info or not info.get("file_path"):
        return {"error": "Video not found"}

    file_path = Path(info["file_path"])
    if not file_path.exists():
        return {"error": "Video file not found on disk"}

    # Guess media type from extension
    ext = file_path.suffix.lower()
    media_types = {
        ".mp4": "video/mp4", ".mkv": "video/x-matroska",
        ".avi": "video/x-msvideo", ".mov": "video/quicktime",
        ".webm": "video/webm", ".flv": "video/x-flv",
    }
    return FileResponse(file_path, media_type=media_types.get(ext, "video/mp4"))


@router.get("/library/{video_id}/frames/{timestamp}")
async def get_frame(video_id: str, timestamp: int):
    """Get a frame image at a specific timestamp."""
    frame_dir = FRAMES_DIR / video_id
    frame_idx = (timestamp // FRAME_SAMPLE_INTERVAL) + 1
    frame_path = frame_dir / f"frame_{frame_idx:04d}.jpg"

    if frame_path.exists():
        return FileResponse(frame_path, media_type="image/jpeg")

    frames = sorted(frame_dir.glob("frame_*.jpg"))
    if frames:
        return FileResponse(frames[0], media_type="image/jpeg")

    return {"error": "Frame not found"}
