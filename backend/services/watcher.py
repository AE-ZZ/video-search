import hashlib
import logging
import threading
import time
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from backend.config import VIDEO_EXTENSIONS

logger = logging.getLogger(__name__)


class VideoLibraryHandler(FileSystemEventHandler):
    """Watches a directory for video file changes and queues processing."""

    def __init__(self, process_callback, remove_callback):
        self.process_callback = process_callback
        self.remove_callback = remove_callback
        # Debounce: track last event time per file to avoid duplicate triggers
        self._pending = {}
        self._lock = threading.Lock()
        self._debounce_seconds = 5

    def _is_video(self, path: str) -> bool:
        return Path(path).suffix.lower() in VIDEO_EXTENSIONS

    def on_created(self, event):
        if event.is_directory or not self._is_video(event.src_path):
            return
        self._schedule(event.src_path)

    def on_modified(self, event):
        if event.is_directory or not self._is_video(event.src_path):
            return
        self._schedule(event.src_path)

    def on_moved(self, event):
        if event.is_directory:
            return
        if self._is_video(event.src_path):
            self.remove_callback(event.src_path)
        if self._is_video(event.dest_path):
            self._schedule(event.dest_path)

    def on_deleted(self, event):
        if event.is_directory or not self._is_video(event.src_path):
            return
        self.remove_callback(event.src_path)

    def _schedule(self, file_path: str):
        """Debounce: wait before processing to handle rapid writes."""
        with self._lock:
            self._pending[file_path] = time.time()

        def _check():
            time.sleep(self._debounce_seconds)
            with self._lock:
                last = self._pending.get(file_path, 0)
            if time.time() - last >= self._debounce_seconds - 0.5:
                with self._lock:
                    self._pending.pop(file_path, None)
                logger.info(f"Processing triggered for: {file_path}")
                self.process_callback(file_path)

        threading.Thread(target=_check, daemon=True).start()


def file_id_from_path(file_path: str) -> str:
    """Generate a stable video_id from the absolute file path."""
    return hashlib.md5(file_path.encode()).hexdigest()[:12]


def scan_library(library_path: str) -> list[dict]:
    """Scan library folder recursively for video files. Returns list of file info dicts."""
    root = Path(library_path)
    if not root.is_dir():
        return []

    files = []
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
            stat = path.stat()
            files.append({
                "file_path": str(path),
                "filename": path.name,
                "mtime": stat.st_mtime,
                "size": stat.st_size,
                "video_id": file_id_from_path(str(path)),
            })
    return files


def start_watcher(library_path: str, process_callback, remove_callback) -> Observer:
    """Start watching a directory for video file changes."""
    handler = VideoLibraryHandler(process_callback, remove_callback)
    observer = Observer()
    observer.schedule(handler, library_path, recursive=True)
    observer.start()
    logger.info(f"Watching library: {library_path}")
    return observer
