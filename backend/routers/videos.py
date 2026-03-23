from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from backend.config import VIDEOS_DIR, FRAMES_DIR
from backend.models import VideoInfo
from backend.services import vectorstore

router = APIRouter(tags=["videos"])


@router.get("/videos", response_model=list[VideoInfo])
async def list_videos(request: Request):
    collections = request.app.state.collections
    summaries_col = collections["summaries"]

    all_data = summaries_col.get(include=["metadatas"])
    videos = []
    for i, vid_id in enumerate(all_data["ids"]):
        meta = all_data["metadatas"][i]

        # Count segments and frames
        try:
            segs = collections["transcripts"].get(where={"video_id": vid_id})
            seg_count = len(segs["ids"])
        except Exception:
            seg_count = 0

        try:
            frms = collections["frames"].get(where={"video_id": vid_id})
            frame_count = len(frms["ids"])
        except Exception:
            frame_count = 0

        videos.append(VideoInfo(
            video_id=vid_id,
            filename=meta.get("video_filename", "unknown"),
            duration=meta.get("duration", 0.0),
            summary=meta.get("summary"),
            segment_count=seg_count,
            frame_count=frame_count,
        ))

    return videos


@router.get("/videos/{video_id}")
async def get_video_detail(video_id: str, request: Request):
    collections = request.app.state.collections
    summary = vectorstore.get_video_summary(collections["summaries"], video_id)
    if not summary:
        return {"error": "Video not found"}

    segments = vectorstore.get_video_segments(collections["transcripts"], video_id)

    return {
        "video_id": video_id,
        "filename": summary.get("video_filename"),
        "duration": summary.get("duration"),
        "summary": summary.get("summary"),
        "transcript": segments,
    }


@router.get("/videos/{video_id}/stream")
async def stream_video(video_id: str):
    """Serve video file with range request support."""
    for path in VIDEOS_DIR.glob(f"{video_id}_*"):
        return FileResponse(
            path,
            media_type="video/mp4",
            filename=path.name,
        )
    return {"error": "Video file not found"}


@router.get("/frames/{video_id}/{timestamp}")
async def get_frame(video_id: str, timestamp: int):
    frame_dir = FRAMES_DIR / video_id
    # Find closest frame to timestamp
    from backend.config import FRAME_SAMPLE_INTERVAL
    frame_idx = (timestamp // FRAME_SAMPLE_INTERVAL) + 1
    frame_path = frame_dir / f"frame_{frame_idx:04d}.jpg"

    if frame_path.exists():
        return FileResponse(frame_path, media_type="image/jpeg")

    # Fallback: try to find any frame
    frames = sorted(frame_dir.glob("frame_*.jpg"))
    if frames:
        return FileResponse(frames[0], media_type="image/jpeg")

    return {"error": "Frame not found"}
