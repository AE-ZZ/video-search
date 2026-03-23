import chromadb

from backend.config import CHROMA_DIR


def init_vectorstore():
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    collections = {
        "transcripts": client.get_or_create_collection(
            name="transcript_segments",
            metadata={"hnsw:space": "cosine"},
        ),
        "frames": client.get_or_create_collection(
            name="frame_embeddings",
            metadata={"hnsw:space": "cosine"},
        ),
        "summaries": client.get_or_create_collection(
            name="video_summaries",
            metadata={"hnsw:space": "cosine"},
        ),
    }

    return client, collections


def add_transcript_segments(
    collection, video_id: str, filename: str,
    segments: list[dict], embeddings: list[list[float]],
):
    if not segments:
        return
    collection.add(
        ids=[f"{video_id}_seg_{i}" for i in range(len(segments))],
        documents=[s["text"] for s in segments],
        embeddings=embeddings,
        metadatas=[
            {
                "video_id": video_id,
                "video_filename": filename,
                "start_time": s["start"],
                "end_time": s["end"],
            }
            for s in segments
        ],
    )


def add_frame_embeddings(
    collection, video_id: str, filename: str,
    frames: list[tuple], embeddings: list[list[float]],
):
    if not frames:
        return
    collection.add(
        ids=[f"{video_id}_frame_{i}" for i in range(len(frames))],
        documents=[""] * len(frames),  # no text for frames
        embeddings=embeddings,
        metadatas=[
            {
                "video_id": video_id,
                "video_filename": filename,
                "timestamp": float(ts),
                "frame_path": str(path),
            }
            for path, ts in frames
        ],
    )


def add_video_summary(
    collection, video_id: str, filename: str,
    full_transcript: str, summary: str, duration: float,
    embedding: list[float],
    file_path: str = "", mtime: float = 0,
):
    collection.add(
        ids=[video_id],
        documents=[full_transcript],
        embeddings=[embedding],
        metadatas=[{
            "video_id": video_id,
            "video_filename": filename,
            "duration": duration,
            "summary": summary,
            "file_path": file_path,
            "mtime": mtime,
        }],
    )


def search_transcripts(collection, query_embedding: list[float], n_results: int = 20):
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )
    return results


def search_transcripts_exact(collection, query: str, n_results: int = 20):
    """Get all segments containing the query string."""
    results = collection.get(
        where_document={"$contains": query.lower()},
        include=["documents", "metadatas"],
        limit=n_results,
    )
    return results


def search_frames(collection, query_embedding: list[float], n_results: int = 20):
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["metadatas", "distances"],
    )
    return results


def get_video_segments(collection, video_id: str) -> list[dict]:
    results = collection.get(
        where={"video_id": video_id},
        include=["documents", "metadatas"],
    )
    segments = []
    for doc, meta in zip(results["documents"], results["metadatas"]):
        segments.append({"text": doc, **meta})
    segments.sort(key=lambda s: s["start_time"])
    return segments


def get_video_summary(collection, video_id: str) -> dict | None:
    results = collection.get(
        ids=[video_id],
        include=["documents", "metadatas"],
    )
    if results["ids"]:
        return {
            "transcript": results["documents"][0],
            **results["metadatas"][0],
        }
    return None


def delete_video(collections: dict, video_id: str):
    """Remove all data for a video from all collections."""
    for name, col in collections.items():
        try:
            existing = col.get(where={"video_id": video_id})
            if existing["ids"]:
                col.delete(ids=existing["ids"])
        except Exception:
            pass
