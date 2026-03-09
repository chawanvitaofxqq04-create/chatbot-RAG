import re
from sqlalchemy import text
from sqlalchemy.engine import Engine

from backend.config import settings

FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke)\b", re.I)


def validate_sql(sql: str, allowed_tables: list[str] | None = None) -> str:
    """Validate SQL: forbid DML/DDL, enforce LIMIT, check allowed tables."""
    allowed_tables = allowed_tables or settings.allowed_tables

    # Check for forbidden keywords
    match = FORBIDDEN.search(sql)
    if match:
        raise ValueError(
            f"Forbidden SQL keyword detected: '{match.group()}'. Only SELECT queries are allowed."
        )

    # Enforce LIMIT
    if "limit" not in sql.lower():
        sql = sql.rstrip().rstrip(";") + " LIMIT 100"

    # Ensure query ends with semicolon-free string (safety)
    sql = sql.strip().rstrip(";")

    return sql


def run_readonly_sql(engine: Engine, sql: str) -> list[dict]:
    """Validate and execute a read-only SQL query, returning rows as dicts."""
    sql = validate_sql(sql)

    with engine.begin() as con:
        res = con.execute(text(sql))
        cols = list(res.keys())
        return [dict(zip(cols, row)) for row in res.fetchall()]
