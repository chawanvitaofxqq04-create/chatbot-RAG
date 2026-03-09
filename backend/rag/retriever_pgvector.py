from sqlalchemy import text
from sqlalchemy.engine import Engine

from backend.config import settings
from backend.rag.ingest import embed_texts


def embed_query(query: str) -> list[float]:
    """Embed a single query for retrieval."""
    vecs = embed_texts([query], task_type="RETRIEVAL_QUERY")
    return vecs[0]


def retrieve_top_k(
    engine: Engine,
    query: str,
    k: int | None = None,
) -> list[dict]:
    """Retrieve top-k most similar document chunks from pgvector."""
    k = k or settings.top_k
    qvec = embed_query(query)

    rows = []
    with engine.begin() as con:
        res = con.execute(
            text("""
                SELECT
                    chunk_id,
                    doc_id,
                    chunk_index,
                    content,
                    metadata,
                    1 - (embedding <=> :qvec) AS cosine_similarity
                FROM doc_chunks
                ORDER BY embedding <=> :qvec
                LIMIT :k
            """),
            {"qvec": str(qvec), "k": k},
        )
        for r in res:
            rows.append(dict(r._mapping))

    return rows
