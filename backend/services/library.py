"""Library manager: coordinates scanning, processing queue, and status tracking."""

import logging
import threading
from pathlib import Path

from backend.config import VIDEO_EXTENSIONS
from backend.services import video_processing, transcription, embeddings, visual, vectorstore, llm
from backend.services.watcher import file_id_from_path, scan_library

logger = logging.getLogger(__name__)


class LibraryManager:
    def __init__(self, app_state):
        self.app_state = app_state
        self._queue = []
        self._lock = threading.Lock()
        self._processing = False
        # video_id -> {status, progress, filename, file_path, mtime, ...}
        self.video_status = {}

    def initial_scan(self, library_path: str):
        """Compare files on disk with ChromaDB. Queue new/modified files."""
        files = scan_library(library_path)
        collections = self.app_state.collections
        summaries_col = collections["summaries"]

        # Get all processed video IDs and their metadata
        existing = summaries_col.get(include=["metadatas"])
        processed = {}
        for i, vid_id in enumerate(existing["ids"]):
            meta = existing["metadatas"][i]
            processed[vid_id] = meta

        # Mark all existing as processed
        for vid_id, meta in processed.items():
            self.video_status[vid_id] = {
                "status": "processed",
                "filename": meta.get("video_filename", "unknown"),
                "file_path": meta.get("file_path", ""),
                "mtime": meta.get("mtime", 0),
            }

        # Check each file on disk
        for f in files:
            vid_id = f["video_id"]
            if vid_id in processed:
                stored_mtime = processed[vid_id].get("mtime", 0)
                if f["mtime"] > stored_mtime:
                    # File was modified — re-process
                    logger.info(f"File modified, re-processing: {f['filename']}")
                    self._remove_video_data(vid_id)
                    self._enqueue(f)
                else:
                    # Already processed and up to date
                    self.video_status[vid_id]["file_path"] = f["file_path"]
            else:
                # New file
                logger.info(f"New file found: {f['filename']}")
                self._enqueue(f)

        # Check for deleted files (in DB but not on disk)
        disk_ids = {f["video_id"] for f in files}
        for vid_id in list(processed.keys()):
            if vid_id not in disk_ids:
                logger.info(f"File removed from disk, cleaning up: {vid_id}")
                self._remove_video_data(vid_id)
                self.video_status.pop(vid_id, None)

    def process_file(self, file_path: str):
        """Called by watcher when a file is created/modified."""
        path = Path(file_path)
        if not path.exists() or path.suffix.lower() not in VIDEO_EXTENSIONS:
            return
        stat = path.stat()
        vid_id = file_id_from_path(file_path)

        # Check if already processed with same mtime
        existing = self.video_status.get(vid_id)
        if existing and existing.get("status") == "processed" and existing.get("mtime", 0) >= stat.st_mtime:
            return

        # If modified, remove old data first
        if existing:
            self._remove_video_data(vid_id)

        self._enqueue({
            "file_path": file_path,
            "filename": path.name,
            "mtime": stat.st_mtime,
            "size": stat.st_size,
            "video_id": vid_id,
        })

    def remove_file(self, file_path: str):
        """Called by watcher when a file is deleted."""
        vid_id = file_id_from_path(file_path)
        self._remove_video_data(vid_id)
        self.video_status.pop(vid_id, None)

    def get_all_status(self) -> list[dict]:
        """Return status of all known videos."""
        result = []
        for vid_id, info in self.video_status.items():
            result.append({"video_id": vid_id, **info})
        return result

    def _enqueue(self, file_info: dict):
        vid_id = file_info["video_id"]
        self.video_status[vid_id] = {
            "status": "pending",
            "progress": "Queued",
            "filename": file_info["filename"],
            "file_path": file_info["file_path"],
            "mtime": file_info["mtime"],
        }
        with self._lock:
            # Avoid duplicate queue entries
            if not any(f["video_id"] == vid_id for f in self._queue):
                self._queue.append(file_info)
        self._start_worker()

    def _start_worker(self):
        with self._lock:
            if self._processing:
                return
            self._processing = True
        threading.Thread(target=self._worker_loop, daemon=True).start()

    def _worker_loop(self):
        while True:
            with self._lock:
                if not self._queue:
                    self._processing = False
                    return
                file_info = self._queue.pop(0)

            self._process_single(file_info)

    def _process_single(self, file_info: dict):
        vid_id = file_info["video_id"]
        file_path = Path(file_info["file_path"])
        filename = file_info["filename"]
        mtime = file_info["mtime"]

        try:
            self.video_status[vid_id] = {
                "status": "processing", "progress": "Extracting audio...",
                "filename": filename, "file_path": str(file_path), "mtime": mtime,
            }

            duration = video_processing.get_video_duration(file_path)
            audio_path = video_processing.extract_audio(file_path, vid_id)

            self.video_status[vid_id]["progress"] = "Transcribing audio..."
            segments = transcription.transcribe(self.app_state.whisper_model, audio_path)

            self.video_status[vid_id]["progress"] = "Generating text embeddings..."
            texts = [s["text"] for s in segments]
            text_embeds = embeddings.embed_texts(self.app_state.sentence_model, texts) if texts else []

            self.video_status[vid_id]["progress"] = "Storing transcript segments..."
            collections = self.app_state.collections
            vectorstore.add_transcript_segments(
                collections["transcripts"], vid_id, filename, segments, text_embeds,
            )

            self.video_status[vid_id]["progress"] = "Extracting frames..."
            frames = video_processing.extract_frames(file_path, vid_id)

            self.video_status[vid_id]["progress"] = "Generating visual embeddings..."
            if frames:
                frame_paths = [f[0] for f in frames]
                all_frame_embeds = []
                for i in range(0, len(frame_paths), 32):
                    batch = frame_paths[i:i + 32]
                    batch_embeds = visual.embed_images(
                        self.app_state.clip_model,
                        self.app_state.clip_preprocess,
                        batch,
                    )
                    all_frame_embeds.extend(batch_embeds)

                vectorstore.add_frame_embeddings(
                    collections["frames"], vid_id, filename, frames, all_frame_embeds,
                )

            self.video_status[vid_id]["progress"] = "Generating summary..."
            full_transcript = " ".join(s["text"] for s in segments)
            try:
                summary = llm.summarize_transcript(full_transcript)
            except Exception:
                summary = "Summary unavailable (set OPENAI_API_KEY to enable)."

            summary_embed = embeddings.embed_texts(
                self.app_state.sentence_model, [full_transcript],
            )[0] if full_transcript else [0.0] * 384

            vectorstore.add_video_summary(
                collections["summaries"], vid_id, filename,
                full_transcript, summary, duration, summary_embed,
                file_path=str(file_path), mtime=mtime,
            )

            self.video_status[vid_id] = {
                "status": "processed",
                "filename": filename,
                "file_path": str(file_path),
                "mtime": mtime,
                "duration": duration,
                "segment_count": len(segments),
                "frame_count": len(frames),
            }
            logger.info(f"Processed: {filename}")

        except Exception as e:
            logger.error(f"Failed to process {filename}: {e}")
            self.video_status[vid_id] = {
                "status": "failed",
                "error": str(e),
                "filename": filename,
                "file_path": str(file_path),
                "mtime": mtime,
            }

    def _remove_video_data(self, video_id: str):
        vectorstore.delete_video(self.app_state.collections, video_id)
