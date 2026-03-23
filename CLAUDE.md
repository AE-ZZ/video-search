# Video Search App

## Rules
- Always share the implementation plan for review and get explicit approval before writing any code.
- Use the `.venv` Python environment (`.venv/bin/python`), not the system Python.
- Use `uv` for package management.

## Tech Stack
- **Backend**: FastAPI + Uvicorn
- **Frontend**: Vanilla HTML/JS/CSS (served by FastAPI StaticFiles)
- **Transcription**: faster-whisper (large-v3)
- **Visual search**: OpenCLIP (ViT-B-32)
- **Text embeddings**: sentence-transformers (all-MiniLM-L6-v2)
- **Vector DB**: ChromaDB (persistent, cosine similarity)
- **LLM**: OpenAI API (gpt-4o-mini) for summarization and Q&A
- **Video processing**: FFmpeg

## Project Structure
```
backend/
├── main.py, config.py, models.py
├── routers/   (ingest, search, chat, videos)
└── services/  (transcription, visual, embeddings, vectorstore, llm, video_processing)
frontend/
├── index.html, style.css, app.js
```

## Running
```bash
export OPENAI_API_KEY=...   # or set in .env
.venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
