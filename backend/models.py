from pydantic import BaseModel


class IngestResponse(BaseModel):
    video_id: str
    filename: str
    duration: float
    segment_count: int
    frame_count: int


class IngestStatus(BaseModel):
    video_id: str
    status: str  # "processing", "completed", "failed"
    progress: str | None = None
    error: str | None = None


class SearchResult(BaseModel):
    video_id: str
    video_filename: str
    score: float
    start_time: float | None = None
    end_time: float | None = None
    text: str | None = None
    frame_path: str | None = None
    timestamp: float | None = None
    match_type: str  # "exact", "semantic", "visual"


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]


class ChatRequest(BaseModel):
    video_id: str
    question: str
    history: list[dict] = []


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict] = []


class VideoInfo(BaseModel):
    video_id: str
    filename: str
    duration: float
    summary: str | None = None
    segment_count: int = 0
    frame_count: int = 0
