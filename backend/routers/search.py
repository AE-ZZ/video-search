from fastapi import APIRouter, Query, Request

from backend.models import SearchResponse, SearchResult
from backend.services import embeddings, visual, vectorstore

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResponse)
async def search(
    request: Request,
    q: str = Query(..., min_length=1),
    type: str = Query("text", pattern="^(text|visual|all)$"),
    text_threshold: float = Query(0.3, ge=0, le=1),
    semantic_threshold: float = Query(0.5, ge=0, le=1),
    visual_threshold: float = Query(0.25, ge=0, le=1),
    semantic: bool = Query(True),
):
    collections = request.app.state.collections
    results = []

    if type in ("text", "all"):
        query_embed = embeddings.embed_texts(request.app.state.sentence_model, [q])[0]
        search_results = vectorstore.search_transcripts(
            collections["transcripts"], query_embed, n_results=100,
        )

        if search_results["ids"] and search_results["ids"][0]:
            q_lower = q.lower()
            for i, doc_id in enumerate(search_results["ids"][0]):
                meta = search_results["metadatas"][0][i]
                distance = search_results["distances"][0][i]
                score = 1.0 - distance
                text = search_results["documents"][0][i]

                is_exact = text and q_lower in text.lower()

                if is_exact:
                    boosted_score = min(score + 0.2, 1.0)
                    if boosted_score < text_threshold:
                        continue
                    results.append(SearchResult(
                        video_id=meta["video_id"],
                        video_filename=meta["video_filename"],
                        score=round(boosted_score, 4),
                        start_time=meta["start_time"],
                        end_time=meta["end_time"],
                        text=text,
                        match_type="exact",
                    ))
                elif semantic:
                    if score < semantic_threshold:
                        continue
                    results.append(SearchResult(
                        video_id=meta["video_id"],
                        video_filename=meta["video_filename"],
                        score=round(score, 4),
                        start_time=meta["start_time"],
                        end_time=meta["end_time"],
                        text=text,
                        match_type="semantic",
                    ))

    if type in ("visual", "all"):
        query_embed = visual.embed_text_query(
            request.app.state.clip_model,
            request.app.state.clip_tokenizer,
            q,
        )
        frame_results = vectorstore.search_frames(
            collections["frames"], query_embed, n_results=100,
        )

        if frame_results["ids"] and frame_results["ids"][0]:
            for i, doc_id in enumerate(frame_results["ids"][0]):
                meta = frame_results["metadatas"][0][i]
                distance = frame_results["distances"][0][i]
                score = 1.0 - distance
                if score < visual_threshold:
                    continue
                results.append(SearchResult(
                    video_id=meta["video_id"],
                    video_filename=meta["video_filename"],
                    score=round(score, 4),
                    timestamp=meta["timestamp"],
                    frame_path=f"/api/library/{meta['video_id']}/frames/{int(meta['timestamp'])}",
                    match_type="visual",
                ))

    results.sort(key=lambda r: r.score, reverse=True)

    return SearchResponse(query=q, results=results)
