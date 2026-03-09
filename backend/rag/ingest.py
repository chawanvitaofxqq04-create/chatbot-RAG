import uuid
from google import genai
from google.genai.types import EmbedContentConfig
from sqlalchemy import text
from sqlalchemy.engine import Engine

from backend.config import settings


def get_genai_client() -> genai.Client:
    return genai.Client(api_key=settings.gemini_api_key)


EMBED_BATCH_SIZE = 100  # Gemini API limit: at most 100 requests per batch

def embed_texts(
    texts: list[str],
    model: str | None = None,
    output_dim: int | None = None,
    task_type: str = "RETRIEVAL_DOCUMENT",
) -> list[list[float]]:
    """Embed a list of texts using Gemini embeddings API (batched, max 100 per call)."""
    client = get_genai_client()
    model = model or settings.embedding_model
    output_dim = output_dim or settings.embed_dim

    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[i : i + EMBED_BATCH_SIZE]
        resp = client.models.embed_content(
            model=model,
            contents=batch,
            config=EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=output_dim,
            ),
        )
        all_embeddings.extend(e.values for e in resp.embeddings)
    return all_embeddings


def sanitize_text(text: str) -> str:
    """Remove NUL bytes and other control chars that PostgreSQL rejects."""
    # Remove NUL (0x00) — psycopg2 rejects these outright
    text = text.replace("\x00", "")
    # Remove other non-printable control chars except tab/newline/carriage-return
    import re
    text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return text


def chunk_text(
    text_content: str,
    chunk_size: int = 600,
    overlap: int = 100,
) -> list[str]:
    """Split text into overlapping chunks by character count."""
    chunks = []
    start = 0
    while start < len(text_content):
        end = start + chunk_size
        chunks.append(text_content[start:end])
        start = end - overlap
    return chunks


def ingest_document(
    engine: Engine,
    doc_id: str,
    content: str,
    metadata: dict | None = None,
    chunk_size: int = 600,
    overlap: int = 100,
) -> int:
    """Chunk a document, embed chunks, and insert into pgvector."""
    metadata = metadata or {}
    content = sanitize_text(content)
    chunks = chunk_text(content, chunk_size, overlap)

    if not chunks:
        return 0

    vectors = embed_texts(chunks)

    with engine.begin() as con:
        for i, (chunk_text_content, vec) in enumerate(zip(chunks, vectors)):
            chunk_id = str(uuid.uuid4())
            import json

            con.execute(
                text("""
                    INSERT INTO doc_chunks (chunk_id, doc_id, chunk_index, content, metadata, embedding)
                    VALUES (:chunk_id, :doc_id, :chunk_index, :content, CAST(:metadata AS jsonb), :embedding)
                """),
                {
                    "chunk_id": chunk_id,
                    "doc_id": doc_id,
                    "chunk_index": i,
                    "content": chunk_text_content,
                    "metadata": json.dumps(
                        {**metadata, "doc_id": doc_id, "chunk_index": i},
                        ensure_ascii=False,
                    ),
                    "embedding": str(vec),
                },
            )

    return len(chunks)
