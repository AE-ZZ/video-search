# Video Search

A local webapp that lets you search through your video files by transcript, visual content, and conversational Q&A — powered by whisper.cpp, CLIP, and GPT.

## What does this app do?

Point this app at a folder of videos on your computer, and it turns them into a searchable library. Here's what you can do:

- **Search by words** — Find the exact moment someone says something in any video. Search for "climate change" and get every clip where it's mentioned, with timestamps. It also understands meaning, so searching "video games" will match segments that mention "Nintendo" or "Playstation".
- **Search by visuals** — Describe what you're looking for ("Eiffel Tower", "a dog on a beach", "whiteboard with diagrams") and the app finds the frames in your videos that match, down to the second.
- **Get video summaries** — Each video is automatically summarized into key points so you can quickly understand what it covers without watching the whole thing.
- **Ask questions** — Open any video and chat with it. Ask "What did they say about pricing?" and get an answer with timestamp references you can click to jump straight to that moment.

Everything runs locally on your machine except for the AI summaries and Q&A (which use OpenAI's API). Your videos never leave your computer. Just set a folder path, and the app automatically processes every video it finds — including new ones you add later.

## Core Models

| Model | Type | Device | Purpose |
|-------|------|--------|---------|
| **whisper.cpp large-v3-turbo** | Speech-to-Text | Metal GPU | Transcribes video audio into timestamped text segments. ~45x faster than CPU-based alternatives on Apple Silicon. |
| **CLIP ViT-B/32** | Vision-Language | MPS GPU | Embeds video frames and text queries into a shared vector space for visual search. Runs locally via `open-clip-torch`. |
| **all-MiniLM-L6-v2** | Text Embedding | MPS GPU | Embeds transcript segments and search queries for semantic text search. Runs locally via `sentence-transformers`, 384-dim vectors. |
| **GPT-4o-mini** | LLM | Cloud | Generates video summaries, Q&A, and match explanations. Default mode. |
| **Qwen3.5-9B-MLX-4bit** | LLM (text) | Apple Silicon | Local alternative for summaries, Q&A, and text match explanations. Used in local LLM mode. |
| **Qwen3-VL-8B-Instruct-4bit** | LLM (vision) | Apple Silicon | Local alternative for visual match explanations. Describes frame content and explains relevance. Used in local LLM mode. |

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
  ├─ Audio ──► whisper.cpp (Metal) ──► Transcript segments (timestamped)
  │                                         │
  │                                         ├─► Sentence-Transformers (MPS) ──► Text embeddings ──► ChromaDB
  │                                         │
  │                                         └─► GPT-4o-mini ──► Summary
  │
  └─ Frames ──► CLIP image encoder (MPS) ──► Visual embeddings ──► ChromaDB

Search Query
  │
  ├─ Text search ──► Sentence-Transformers ──► query ChromaDB transcripts
  │
  └─ Visual search ──► CLIP text encoder ──► query ChromaDB frames
```

## Features

- **Automatic video library management** — Point to a folder; new, modified, and deleted videos are detected and processed automatically via filesystem watcher
- **Transcript search (exact + semantic)** — Search for exact words or semantically similar concepts (e.g., "video games" matches "Nintendo", "Playstation")
- **Visual search** — Describe what you're looking for (e.g., "a red car", "person on stage") and find matching video frames via CLIP
- **Video summarization** — Auto-generated bullet-point summaries from transcriptions
- **Q&A chat** — Ask questions about a video's content; answers include timestamp citations
- **Explain matches** — For semantic and visual results, click "Explain" to get a GPT-powered explanation of why the result matches your query. Visual explanations use GPT-4o-mini vision to describe the frame content. Explanations are cached so repeat views are instant.
- **Click-to-seek** — Click any search result or transcript segment to jump to that moment in the video, with the transcript auto-scrolling to the matching segment
- **Live processing status** — See which videos are processed, processing, or pending in real time
- **Grouped search results** — Results are grouped by video file; click a video to expand and see all matching moments
- **Adjustable search thresholds** — Fine-tune relevance via the Advanced panel (see below)

## Prerequisites

- Python 3.11+
- FFmpeg (for audio/frame extraction)
- An OpenAI API key (for summaries and Q&A) — **OR** use local LLM mode (no API key needed)
- macOS with Apple Silicon recommended (Metal GPU acceleration for whisper.cpp and MPS for CLIP/sentence-transformers)

## Setup

```bash
# Clone / navigate to the project
cd /path/to/Playground

# Create a virtual environment and install dependencies
uv venv
uv pip install fastapi "uvicorn[standard]" python-multipart \
    open-clip-torch sentence-transformers chromadb openai pillow python-dotenv watchdog mlx-lm mlx-vlm

# Install whisper.cpp with Metal GPU support
GGML_METAL=1 uv pip install git+https://github.com/absadiki/pywhispercpp

# Set your OpenAI API key in .env (skip if using local LLM mode)
echo "OPENAI_API_KEY=sk-proj-your-key-here" > .env

# (Optional) Pre-configure your video library path
echo "VIDEO_LIBRARY_PATH=/path/to/your/videos" >> .env

# (Optional) Enable local LLM mode (no API key needed)
echo "LOCAL_LLM=1" >> .env
```

## Usage

### 1. Start the server

```bash
# OpenAI mode (default — requires OPENAI_API_KEY)
.venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Local LLM mode (fully offline, no API key needed)
LOCAL_LLM=1 .venv/bin/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

On first start, ML models will be downloaded automatically. In local LLM mode, this includes Qwen3.5-9B (~5.6 GB) and Qwen3-VL-8B (~3.2 GB) in addition to whisper.cpp, CLIP, and sentence-transformers. Subsequent starts load from cache.

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

**Search results are grouped by video** — each video shows as a collapsible card with the number of matches. Click to expand and see individual hits with thumbnails and timestamps. Click any hit to jump to that moment in the video.

Visual results within 5 seconds of each other are deduplicated to reduce noise.

### 5. Advanced search settings

Click **Advanced** below the search bar to reveal:

| Setting | Default | Description |
|---------|---------|-------------|
| **Semantic matches** | On | Toggle whether to include semantically similar results (not just exact word matches) |
| **Exact threshold** | 0.30 | Minimum similarity score for exact text matches |
| **Semantic threshold** | 0.50 | Minimum similarity score for semantic matches (higher = stricter, fewer but more relevant results) |
| **Visual threshold** | 0.25 | Minimum similarity score for visual matches (CLIP scores are naturally lower than text scores) |

Only results above the threshold are returned — no forced padding with irrelevant matches.

### 6. Explore a video

Click a processed video in the library to open the detail view with tabs:

- **Summary** — AI-generated bullet-point overview
- **Transcript** — Full timestamped transcript; click any segment to seek. Opens scrolled to the matching segment when coming from search results.
- **Explanation** — (only when opened from a semantic/visual search result) Shows why the result matched your query. Uses GPT-4o-mini vision for visual matches.
- **Chat** — Ask questions like "What was discussed about X?" and get answers with timestamp references

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/settings` | Get current settings (library path) |
| `POST` | `/api/settings` | Set/update video library path |
| `GET` | `/api/library` | List all videos with processing status |
| `GET` | `/api/library/{video_id}/stream` | Stream video file |
| `GET` | `/api/library/{video_id}/frames/{timestamp}` | Get a frame image |
| `GET` | `/api/search?q=...&type=...&semantic=...&text_threshold=...&semantic_threshold=...&visual_threshold=...` | Search across videos |
| `POST` | `/api/explain` | Explain why search results match the query (supports text and vision) |
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
│   ├── search.py            # Text and visual search with thresholds
│   ├── explain.py           # GPT-powered match explanations (text + vision)
│   ├── chat.py              # Q&A with RAG retrieval
│   └── videos.py            # Video detail, summary, transcript
├── services/
│   ├── library.py           # Library manager (scan, queue, process, track)
│   ├── watcher.py           # Filesystem watcher (watchdog)
│   ├── video_processing.py  # FFmpeg audio/frame extraction
│   ├── transcription.py     # whisper.cpp transcription (Metal GPU)
│   ├── embeddings.py        # Sentence-transformer embeddings (MPS)
│   ├── visual.py            # CLIP image/text encoding (MPS)
│   ├── vectorstore.py       # ChromaDB (3 collections)
│   └── llm.py               # LLM service (OpenAI or local MLX, auto-switches via LOCAL_LLM)
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
OPENAI_API_KEY=sk-proj-...          # Required in OpenAI mode
VIDEO_LIBRARY_PATH=/path/to/videos  # Set via UI or manually
LOCAL_LLM=1                         # Set to use local models instead of OpenAI
```

### LLM modes

| Mode | Set by | LLM for text | LLM for vision | API key needed |
|------|--------|-------------|----------------|----------------|
| **OpenAI** (default) | `LOCAL_LLM` unset | GPT-4o-mini | GPT-4o-mini | Yes |
| **Local** | `LOCAL_LLM=1` | Qwen3.5-9B-MLX-4bit (~5.6 GB) | Qwen3-VL-8B-Instruct-4bit (~3.2 GB) | No |

Total RAM for local mode: ~11 GB (both LLMs + Whisper + CLIP + sentence-transformers). Fits on 16 GB machines.

### Other model settings

In `backend/config.py`:

```python
WHISPER_MODEL = "large-v3-turbo"   # Options: tiny, base, small, medium, large-v3, large-v3-turbo
CLIP_MODEL = "ViT-B-32"           # Larger: ViT-L-14 (slower but more accurate)
SENTENCE_MODEL = "all-MiniLM-L6-v2"
FRAME_SAMPLE_INTERVAL = 2         # Extract 1 frame every N seconds
```

`large-v3-turbo` is recommended — same quality as `large-v3` but significantly faster. Smaller models (`tiny`, `base`) trade accuracy for speed.
