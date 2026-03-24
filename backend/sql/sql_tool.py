import re
from sqlalchemy import text
from sqlalchemy.engine import Engine
from backend.config import settings

# --- 1. เพิ่มการ Import จากไฟล์ utils ที่บอสเพิ่งสร้าง ---
from backend.utils import resilient_retry 

FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke)\b", re.I)

def validate_sql(sql: str, allowed_tables: list[str] | None = None) -> str:
    # ... (โค้ดส่วนนี้เหมือนเดิมครับ ไม่ต้องแก้ไขอะไร) ...
    allowed_tables = allowed_tables or settings.allowed_tables
    match = FORBIDDEN.search(sql)
    if match:
        raise ValueError(f"Forbidden SQL keyword detected: '{match.group()}'. Only SELECT queries are allowed.")
    if "limit" not in sql.lower():
        sql = sql.rstrip().rstrip(";") + " LIMIT 100"
    sql = sql.strip().rstrip(";")
    return sql

# --- 2. วางตัวดักจับ Error ไว้ที่นี่ (จุดที่ติดต่อกับ DB จริงๆ) ---
@resilient_retry(max_attempts=3, delay=2) 
def run_readonly_sql(engine: Engine, sql: str) -> list[dict]:
    """Validate and execute a read-only SQL query, returning rows as dicts."""
    sql = validate_sql(sql)

    # จุดนี้คือจุดที่เสี่ยงพังที่สุดถ้า DB Restart
    with engine.begin() as con:
        res = con.execute(text(sql))
        cols = list(res.keys())
        return [dict(zip(cols, row)) for row in res.fetchall()]