from fastapi import APIRouter, Request
from pydantic import BaseModel

from backend.config import FRAMES_DIR, FRAME_SAMPLE_INTERVAL
from backend.services import llm

router = APIRouter(tags=["explain"])


class ExplainItem(BaseModel):
    video_id: str
    match_type: str  # "exact", "semantic", "visual"
    text: str | None = None
    start_time: float | None = None
    end_time: float | None = None
    timestamp: float | None = None


class ExplainRequest(BaseModel):
    query: str
    items: list[ExplainItem]


class ExplainResult(BaseModel):
    explanation: str
    match_type: str
    text: str | None = None
    start_time: float | None = None
    end_time: float | None = None
    timestamp: float | None = None


class ExplainResponse(BaseModel):
    results: list[ExplainResult]


@router.post("/explain", response_model=ExplainResponse)
async def explain_matches(body: ExplainRequest):
    results = []

    for item in body.items:
        try:
            if item.match_type in ("exact", "semantic"):
                explanation = llm.explain_text_match(
                    query=body.query,
                    text=item.text or "",
                    start_time=item.start_time or 0,
                    end_time=item.end_time or 0,
                )
            elif item.match_type == "visual":
                # Find the frame file on disk
                ts = item.timestamp or 0
                frame_idx = (int(ts) // FRAME_SAMPLE_INTERVAL) + 1
                frame_path = FRAMES_DIR / item.video_id / f"frame_{frame_idx:04d}.jpg"
                explanation = llm.explain_visual_match(
                    query=body.query,
                    frame_path=str(frame_path),
                    timestamp=ts,
                )
            else:
                explanation = "Unknown match type."
        except Exception as e:
            explanation = f"Explanation unavailable: {e}"

        results.append(ExplainResult(
            explanation=explanation,
            match_type=item.match_type,
            text=item.text,
            start_time=item.start_time,
            end_time=item.end_time,
            timestamp=item.timestamp,
        ))

    return ExplainResponse(results=results)
