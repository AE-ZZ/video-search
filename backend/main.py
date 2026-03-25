import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend import config
from backend.services.transcription import load_whisper_model
from backend.services.visual import load_clip_model
from backend.services.embeddings import load_sentence_model
from backend.services.vectorstore import init_vectorstore
from backend.services.library import LibraryManager
from backend.services.watcher import start_watcher
from backend.services import llm
from backend.routers import ingest, search, chat, videos, settings, library, explain

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


if os.getenv("LOCAL_LLM", "").lower() in ("1", "true", "yes"):
    config.USE_LOCAL_LLM = True


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize LLM backend
    if config.USE_LOCAL_LLM:
        llm.init_local()
    else:
        llm.init_openai()

    # Load all ML models at startup
    app.state.whisper_model = load_whisper_model()
    app.state.clip_model, app.state.clip_preprocess, app.state.clip_tokenizer = load_clip_model()
    app.state.sentence_model = load_sentence_model()
    app.state.chroma_client, app.state.collections = init_vectorstore()
    app.state.ingest_status = {}

    # Initialize library manager
    manager = LibraryManager(app.state)
    app.state.library_manager = manager

    # If library path is configured, scan and start watching
    app.state.watcher = None
    if config.VIDEO_LIBRARY_PATH:
        logger.info(f"Library path configured: {config.VIDEO_LIBRARY_PATH}")
        manager.initial_scan(config.VIDEO_LIBRARY_PATH)
        app.state.watcher = start_watcher(
            config.VIDEO_LIBRARY_PATH,
            process_callback=manager.process_file,
            remove_callback=manager.remove_file,
        )

    yield

    # Shutdown watcher
    if app.state.watcher:
        app.state.watcher.stop()
        app.state.watcher.join()


app = FastAPI(title="Video Search", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(settings.router, prefix="/api")
app.include_router(library.router, prefix="/api")
app.include_router(ingest.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(explain.router, prefix="/api")
app.include_router(videos.router, prefix="/api")

# Serve frontend
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
