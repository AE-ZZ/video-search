from fastapi import APIRouter, Query, Request

from backend.models import SearchResponse, SearchResult
from backend.services import embeddings, visual, vectorstore

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResponse)
async def search(
    request: Request,
    q: str = Query(..., min_length=1),
    type: str = Query("text", pattern="^(text|visual|all)$"),
    n: int = Query(20, ge=1, le=100),
):
    collections = request.app.state.collections
    results = []

    if type in ("text", "all"):
        # Semantic search
        query_embed = embeddings.embed_texts(request.app.state.sentence_model, [q])[0]
        semantic = vectorstore.search_transcripts(
            collections["transcripts"], query_embed, n_results=n,
        )

        if semantic["ids"] and semantic["ids"][0]:
            for i, doc_id in enumerate(semantic["ids"][0]):
                meta = semantic["metadatas"][0][i]
                distance = semantic["distances"][0][i]
                score = 1.0 - distance  # cosine distance to similarity
                results.append(SearchResult(
                    video_id=meta["video_id"],
                    video_filename=meta["video_filename"],
                    score=round(score, 4),
                    start_time=meta["start_time"],
                    end_time=meta["end_time"],
                    text=semantic["documents"][0][i],
                    match_type="semantic",
                ))

        # Exact search - check if query appears literally in results
        q_lower = q.lower()
        for r in results:
            if r.text and q_lower in r.text.lower():
                r.match_type = "exact"
                r.score = min(r.score + 0.2, 1.0)  # boost exact matches

    if type in ("visual", "all"):
        # CLIP text-to-image search
        query_embed = visual.embed_text_query(
            request.app.state.clip_model,
            request.app.state.clip_tokenizer,
            q,
        )
        frame_results = vectorstore.search_frames(
            collections["frames"], query_embed, n_results=n,
        )

        if frame_results["ids"] and frame_results["ids"][0]:
            for i, doc_id in enumerate(frame_results["ids"][0]):
                meta = frame_results["metadatas"][0][i]
                distance = frame_results["distances"][0][i]
                score = 1.0 - distance
                results.append(SearchResult(
                    video_id=meta["video_id"],
                    video_filename=meta["video_filename"],
                    score=round(score, 4),
                    timestamp=meta["timestamp"],
                    frame_path=f"/api/library/{meta['video_id']}/frames/{int(meta['timestamp'])}",
                    match_type="visual",
                ))

    # Sort by score descending
    results.sort(key=lambda r: r.score, reverse=True)

    return SearchResponse(query=q, results=results[:n])
