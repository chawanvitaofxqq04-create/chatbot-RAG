import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    db_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg2://app:app@localhost:5432/ragdb",
        )
    )
    embedding_model: str = field(
        default_factory=lambda: os.getenv("EMBED_MODEL", "gemini-embedding-001")
    )
    chat_model: str = field(
        default_factory=lambda: os.getenv("CHAT_MODEL", "gemini-2.5-flash")
    )
    embed_dim: int = field(
        default_factory=lambda: int(os.getenv("EMBED_DIM", "768"))
    )
    top_k: int = field(default_factory=lambda: int(os.getenv("TOP_K", "5")))

    # SQL RAG safety
    allowed_tables: list = field(
        default_factory=lambda: [
            "customers",
            "products",
            "orders",
            "order_items",
            "students",
            "courses",
            "enrollments",
            "sales_summary",
            "top_products",
            "student_summary",
            "applicants",
        ]
    )


settings = Settings()
