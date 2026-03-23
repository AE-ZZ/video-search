# Video Search

A local webapp that lets you search through your video files by transcript, visual content, and conversational Q&A — powered by Whisper, CLIP, and GPT.

## What does this app do?

Point this app at a folder of videos on your computer, and it turns them into a searchable library. Here's what you can do:

- **Search by words** — Find the exact moment someone says something in any video. Search for "climate change" and get every clip where it's mentioned, with timestamps. It also understands meaning, so searching "video games" will match segments that mention "Nintendo" or "Playstation".
- **Search by visuals** — Describe what you're looking for ("Eiffel Tower", "a dog on a beach", "whiteboard with diagrams") and the app finds the frames in your videos that match, down to the second.
- **Get video summaries** — Each video is automatically summarized into key points so you can quickly understand what it covers without watching the whole thing.
- **Ask questions** — Open any video and chat with it. Ask "What did they say about pricing?" and get an answer with timestamp references you can click to jump straight to that moment.

Everything runs locally on your machine except for the AI summaries and Q&A (which use OpenAI's API). Your videos never leave your computer. Just set a folder path, and the app automatically processes every video it finds — including new ones you add later.

## Core Models

| Model | Type | Purpose | Details |
|-------|------|---------|---------|
| **Whisper large-v3** | Speech-to-Text | Transcribes video audio into timestamped text segments | Runs locally via `faster-whisper`, CPU with int8 quantization |
| **CLIP ViT-B/32** | Vision-Language | Embeds video frames and text queries into a shared vector space for visual search | Runs locally via `open-clip-torch`, pretrained on LAION-2B |
| **all-MiniLM-L6-v2** | Text Embedding | Embeds transcript segments and search queries for semantic text search | Runs locally via `sentence-transformers`, 384-dim vectors |
| **GPT-4o-mini** | LLM | Generates video summaries and answers Q&A questions with timestamp citations | Requires OpenAI API key |

### Vector Database

**ChromaDB** — a lightweight, file-persistent vector database with three collections:

| Collection | Stores | Embedding Source | Dimensions |
|---|---|---|---|
| `transcript_segments` | Timestamped transcript text | Sentence-Transformers | 384-dim |
| `frame_embeddings` | Video frame vectors | CLIP | 512-dim |
| `video_summaries` | Full transcripts + summaries | Sentence-Transformers | 384-dim |

### How they work together

```
Video Library (auto-scanned)
  │
  ├─ Audio ──► Whisper ──► Transcript segments (timestamped)
  │                              │
  │                              ├─► Sentence-Transformers ──► Text embeddings ──► ChromaDB
  │                              │
  │                              └─► GPT-4o-mini ──► Summary
  │
  └─ Frames ──► CLIP (image encoder) ──► Visual embeddings ──► ChromaDB

Search Query
  │
  ├─ Text search ──► Sentence-Transformers ──► query ChromaDB transcripts
  │
  └─ Visual search ──► CLIP (text encoder) ──► query ChromaDB frames
```

## Features

- **Automatic video library management** — Point to a folder; new, modified, and deleted videos are detected and processed automatically via filesystem watcher
- **Transcript search (exact + semantic)** — Search for exact words or semantically similar concepts (e.g., "video games" matches "Nintendo", "Playstation")
- **Visual search** — Describe what you're looking for (e.g., "a red car", "person on stage") and find matching video frames via CLIP
- **Video summarization** — Auto-generated bullet-point summaries from transcriptions
- **Q&A chat** — Ask questions about a video's content; answers include timestamp citations
- **Click-to-seek** — Click any search result or transcript segment to jump to that moment in the video
- **Live processing status** — See which videos are processed, processing, or pending in real time

## Prerequisites

- Python 3.11+
- FFmpeg (for audio/frame extraction)
- An OpenAI API key (for summaries and Q&A)

## Setup

```bash
# Clone / navigate to the project
cd /path/to/Playground

# Create a virtual environment and install dependencies
uv venv
uv pip install fastapi "uvicorn[standard]" python-multipart faster-whisper \
    open-clip-torch sentence-transformers chromadb openai pillow python-dotenv watchdog

# Set your OpenAI API key in .env
echo "OPENAI_API_KEY=sk-proj-your-key-here" > .env

# (Optional) Pre-configure your video library path
echo "VIDEO_LIBRARY_PATH=/path/to/your/videos" >> .env
```

## Usage

### 1. Start the server

```bash
.venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

On first start, ML models will be downloaded automatically (~1-2 GB total). Subsequent starts load from cache.

### 2. Open the app

Go to [http://localhost:8000](http://localhost:8000) in your browser.

### 3. Set your video library

On first launch, the app shows a setup screen asking for the folder containing your videos. Enter the path and the system will:

1. Recursively scan the folder for video files (`.mp4`, `.mkv`, `.avi`, `.mov`, `.webm`, `.flv`)
2. Automatically start processing each video (transcription, frame extraction, embeddings, summarization)
3. Begin watching the folder for changes — new files are auto-processed, modified files are re-processed, deleted files are cleaned up

The library path is saved to `.env` so it persists across restarts. You can change it anytime from the header bar in the UI.

### 4. Search your videos

Type a query in the search bar and choose a search type:

| Type | What it does | Example |
|------|-------------|---------|
| **Transcript** | Searches what was *said* in videos (exact + semantic) | "machine learning", "talking about food" |
| **Visual** | Searches what *appears* in video frames | "a cat", "whiteboard with diagrams" |
| **All** | Combined search across both | Any query |

Click any result to jump to that exact moment in the video.

### 5. Explore a video

Click a processed video in the library to open the detail view with three tabs:

- **Summary** — AI-generated bullet-point overview
- **Transcript** — Full timestamped transcript; click any segment to seek
- **Chat** — Ask questions like "What was discussed about X?" and get answers with timestamp references

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/settings` | Get current settings (library path) |
| `POST` | `/api/settings` | Set/update video library path |
| `GET` | `/api/library` | List all videos with processing status |
| `GET` | `/api/library/{video_id}/stream` | Stream video file |
| `GET` | `/api/library/{video_id}/frames/{timestamp}` | Get a frame image |
| `GET` | `/api/search?q=...&type=text\|visual\|all` | Search across videos |
| `GET` | `/api/videos/{video_id}` | Get video detail (summary + transcript) |
| `POST` | `/api/chat` | Q&A chat about a specific video |
| `POST` | `/api/ingest` | Upload and process a single video file |
| `GET` | `/api/ingest/{video_id}/status` | Poll upload processing progress |

## Project Structure

```
backend/
├── main.py                  # FastAPI app, model loading, watcher lifecycle
├── config.py                # Paths, model names, settings
├── models.py                # Pydantic request/response schemas
├── routers/
│   ├── settings.py          # Library path configuration
│   ├── library.py           # Video library listing, streaming, frames
│   ├── ingest.py            # Single video upload + processing
│   ├── search.py            # Text and visual search
│   ├── chat.py              # Q&A with RAG retrieval
│   └── videos.py            # Video detail, summary, transcript
├── services/
│   ├── library.py           # Library manager (scan, queue, process, track)
│   ├── watcher.py           # Filesystem watcher (watchdog)
│   ├── video_processing.py  # FFmpeg audio/frame extraction
│   ├── transcription.py     # Whisper transcription
│   ├── embeddings.py        # Sentence-transformer embeddings
│   ├── visual.py            # CLIP image/text encoding
│   ├── vectorstore.py       # ChromaDB (3 collections)
│   └── llm.py               # OpenAI GPT for summary + Q&A
└── data/                    # Processed data (auto-created)
    ├── audio/               # Extracted audio (WAV)
    ├── frames/              # Extracted frame images
    └── chroma_db/           # Persistent vector database

frontend/
├── index.html               # Single-page app
├── style.css                # Dark theme UI
└── app.js                   # Client-side logic
```

## Configuration

Settings in `.env`:

```bash
OPENAI_API_KEY=sk-proj-...       # Required for summaries and Q&A
VIDEO_LIBRARY_PATH=/path/to/videos  # Set via UI or manually
```

Model settings in `backend/config.py`:

```python
WHISPER_MODEL = "large-v3"      # Options: tiny, base, small, medium, large-v3
CLIP_MODEL = "ViT-B-32"         # Larger: ViT-L-14 (slower but more accurate)
SENTENCE_MODEL = "all-MiniLM-L6-v2"
FRAME_SAMPLE_INTERVAL = 2       # Extract 1 frame every N seconds
```

Smaller Whisper models (`tiny`, `base`) are faster but less accurate. `large-v3` gives the best transcription quality.
