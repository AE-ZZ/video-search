import uuid
import shutil
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Request, BackgroundTasks

from backend.config import VIDEOS_DIR
from backend.models import IngestResponse, IngestStatus
from backend.services import video_processing, transcription, embeddings, visual, vectorstore, llm

router = APIRouter(tags=["ingest"])


def _process_video(request_state, video_id: str, video_path: Path, filename: str):
    """Background task to process an uploaded video."""
    status = request_state.ingest_status
    try:
        status[video_id] = {"status": "processing", "progress": "Extracting audio..."}
        duration = video_processing.get_video_duration(video_path)
        audio_path = video_processing.extract_audio(video_path, video_id)

        status[video_id]["progress"] = "Transcribing audio..."
        segments = transcription.transcribe(request_state.whisper_model, audio_path)

        status[video_id]["progress"] = "Generating text embeddings..."
        texts = [s["text"] for s in segments]
        text_embeds = embeddings.embed_texts(request_state.sentence_model, texts) if texts else []

        status[video_id]["progress"] = "Storing transcript segments..."
        collections = request_state.collections
        vectorstore.add_transcript_segments(
            collections["transcripts"], video_id, filename, segments, text_embeds,
        )

        status[video_id]["progress"] = "Extracting frames..."
        frames = video_processing.extract_frames(video_path, video_id)

        status[video_id]["progress"] = "Generating visual embeddings..."
        if frames:
            frame_paths = [f[0] for f in frames]
            # Process in batches of 32
            all_frame_embeds = []
            for i in range(0, len(frame_paths), 32):
                batch = frame_paths[i:i + 32]
                batch_embeds = visual.embed_images(
                    request_state.clip_model,
                    request_state.clip_preprocess,
                    batch,
                )
                all_frame_embeds.extend(batch_embeds)

            vectorstore.add_frame_embeddings(
                collections["frames"], video_id, filename, frames, all_frame_embeds,
            )

        status[video_id]["progress"] = "Generating summary..."
        full_transcript = " ".join(s["text"] for s in segments)
        try:
            summary = llm.summarize_transcript(full_transcript)
        except Exception:
            summary = "Summary unavailable (set OPENAI_API_KEY to enable)."

        summary_embed = embeddings.embed_texts(
            request_state.sentence_model, [full_transcript],
        )[0] if full_transcript else [0.0] * 384

        vectorstore.add_video_summary(
            collections["summaries"], video_id, filename,
            full_transcript, summary, duration, summary_embed,
        )

        status[video_id] = {
            "status": "completed",
            "progress": "Done",
            "segment_count": len(segments),
            "frame_count": len(frames),
            "duration": duration,
        }

    except Exception as e:
        status[video_id] = {"status": "failed", "error": str(e)}


@router.post("/ingest", response_model=IngestStatus)
async def ingest_video(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    video_id = uuid.uuid4().hex[:12]
    video_path = VIDEOS_DIR / f"{video_id}_{file.filename}"

    with open(video_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    request.app.state.ingest_status[video_id] = {
        "status": "processing",
        "progress": "Queued",
    }

    background_tasks.add_task(
        _process_video, request.app.state,
        video_id, video_path, file.filename,
    )

    return IngestStatus(video_id=video_id, status="processing", progress="Queued")


@router.get("/ingest/{video_id}/status", response_model=IngestStatus)
async def get_ingest_status(video_id: str, request: Request):
    status = request.app.state.ingest_status.get(video_id)
    if not status:
        return IngestStatus(video_id=video_id, status="not_found")
    return IngestStatus(
        video_id=video_id,
        status=status.get("status", "unknown"),
        progress=status.get("progress"),
        error=status.get("error"),
    )
