from sentence_transformers import SentenceTransformer

from backend.config import SENTENCE_MODEL


def load_sentence_model() -> SentenceTransformer:
    return SentenceTransformer(SENTENCE_MODEL)


def embed_texts(model: SentenceTransformer, texts: list[str]) -> list[list[float]]:
    embeddings = model.encode(texts, normalize_embeddings=True)
    return embeddings.tolist()
