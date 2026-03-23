from fastapi import APIRouter, Request

from backend.models import ChatRequest, ChatResponse
from backend.services import embeddings, vectorstore, llm

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat_with_video(request: Request, body: ChatRequest):
    collections = request.app.state.collections

    # Retrieve relevant transcript segments via semantic search
    query_embed = embeddings.embed_texts(
        request.app.state.sentence_model, [body.question],
    )[0]
    results = vectorstore.search_transcripts(
        collections["transcripts"], query_embed, n_results=10,
    )

    # Filter to only segments from the requested video
    context_segments = []
    if results["ids"] and results["ids"][0]:
        for i, doc_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i]
            if meta["video_id"] == body.video_id:
                context_segments.append({
                    "text": results["documents"][0][i],
                    "start_time": meta["start_time"],
                    "end_time": meta["end_time"],
                })

    # If no segments found via semantic search, fall back to all segments
    if not context_segments:
        context_segments = vectorstore.get_video_segments(
            collections["transcripts"], body.video_id,
        )[:20]  # limit to first 20 segments

    answer = llm.answer_question(
        body.question, context_segments, body.history,
    )

    sources = [
        {"text": s["text"], "start_time": s["start_time"], "end_time": s["end_time"]}
        for s in context_segments
    ]

    return ChatResponse(answer=answer, sources=sources)
