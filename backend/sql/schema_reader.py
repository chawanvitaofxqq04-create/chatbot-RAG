"""
Dynamic database schema reader.
Reads real table structures from PostgreSQL and formats them for AI prompts.
"""
import json
from sqlalchemy import text
from sqlalchemy.engine import Engine


def get_db_schema(engine: Engine, excluded_tables: list[str] | None = None) -> dict:
    """
    Read actual table schema from PostgreSQL.
    Returns dict: { table_name: { columns: [...], row_count: int } }
    """
    excluded_tables = excluded_tables or ["doc_chunks"]

    with engine.connect() as con:
        # Get all user tables
        tables_res = con.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """))
        table_names = [row[0] for row in tables_res if row[0] not in excluded_tables]

        schema = {}
        for table in table_names:
            # Get columns with types and constraints
            cols_res = con.execute(text("""
                SELECT
                    c.column_name,
                    c.data_type,
                    c.character_maximum_length,
                    c.is_nullable,
                    c.column_default,
                    CASE WHEN pk.column_name IS NOT NULL THEN 'PK' ELSE '' END as is_pk,
                    CASE WHEN fk.column_name IS NOT NULL THEN fk.foreign_table_name ELSE '' END as fk_table
                FROM information_schema.columns c
                LEFT JOIN (
                    SELECT kcu.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                        ON tc.constraint_name = kcu.constraint_name
                        AND tc.table_schema = kcu.table_schema
                    WHERE tc.constraint_type = 'PRIMARY KEY'
                      AND tc.table_name = :table
                      AND tc.table_schema = 'public'
                ) pk ON c.column_name = pk.column_name
                LEFT JOIN (
                    SELECT kcu.column_name, ccu.table_name AS foreign_table_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                        ON tc.constraint_name = kcu.constraint_name
                        AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage ccu
                        ON ccu.constraint_name = tc.constraint_name
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                      AND tc.table_name = :table
                      AND tc.table_schema = 'public'
                ) fk ON c.column_name = fk.column_name
                WHERE c.table_name = :table
                  AND c.table_schema = 'public'
                ORDER BY c.ordinal_position
            """), {"table": table})

            columns = []
            for row in cols_res:
                col_info = {
                    "name": row[0],
                    "type": row[1],
                    "nullable": row[3] == "YES",
                    "is_pk": row[5] == "PK",
                    "fk_table": row[6] or None,
                }
                columns.append(col_info)

            # Get row count
            try:
                count_res = con.execute(text(f'SELECT COUNT(*) FROM "{table}"'))
                row_count = count_res.scalar()
            except Exception:
                row_count = 0

            schema[table] = {
                "columns": columns,
                "row_count": row_count,
            }

    return schema


def get_views(engine: Engine) -> list[str]:
    """Get list of available views."""
    with engine.connect() as con:
        res = con.execute(text("""
            SELECT table_name
            FROM information_schema.views
            WHERE table_schema = 'public'
            ORDER BY table_name
        """))
        return [row[0] for row in res]


def format_schema_for_prompt(engine: Engine) -> str:
    """
    Format the full DB schema as a readable string for injection into AI prompts.
    Example output:
        Table: customers (20 rows)
          - customer_id: integer [PK]
          - name: text
          - email: text
          - region: text
          - created_at: timestamp without time zone
        ...
    """
    schema = get_db_schema(engine)
    views = get_views(engine)

    lines = []

    lines.append("=== DATABASE SCHEMA ===\n")

    for table_name, info in schema.items():
        lines.append(f"Table: {table_name} ({info['row_count']:,} rows)")
        for col in info["columns"]:
            flags = []
            if col["is_pk"]:
                flags.append("PK")
            if col["fk_table"]:
                flags.append(f"FK→{col['fk_table']}")
            if not col["nullable"]:
                flags.append("NOT NULL")
            flag_str = f" [{', '.join(flags)}]" if flags else ""
            lines.append(f"  - {col['name']}: {col['type']}{flag_str}")
        lines.append("")

    if views:
        lines.append("=== AVAILABLE VIEWS ===")
        for view in views:
            lines.append(f"  - {view}")
        lines.append("")

    return "\n".join(lines)


def get_allowed_tables(engine: Engine, excluded_tables: list[str] | None = None) -> list[str]:
    """Return list of all queryable table names (excluding system tables)."""
    excluded_tables = excluded_tables or ["doc_chunks"]
    schema = get_db_schema(engine, excluded_tables)
    views = get_views(engine)
    return list(schema.keys()) + views


# ── Thai column descriptions per table ────────────────────────────────────────
# Used by format_schema_as_doc() to annotate columns with human-readable meaning.
_COLUMN_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "applicants": {
        "id":               "รหัสผู้สมัคร (auto)",
        "faculty":          "คณะที่สมัคร เช่น คณะวิศวกรรมศาสตร์และเทคโนโลยีอุตสาหกรรม",
        "level":            "ระดับการศึกษา: ปริญญาตรี / ปริญญาตรีภศเทียบโอน / ประกาศนียบัตรวิชาชีพชั้นสูง",
        "program":          "ชื่อหลักสูตรเต็ม เช่น วศฮบฮภวิศวกรรมเกษตรอัจฉริยะ",
        "program_abbr":     "รหัสย่อหลักสูตร เช่น วศฮบฮ",
        "province_origin":  "จังหวัดภูมิลำเนาของผู้สมัคร เช่น ร้อยเอ็ด สกลนคร",
        "district":         "อำเภอที่อยู่ของผู้สมัคร",
        "subdistrict":      "ตำบลที่อยู่ของผู้สมัคร",
        "school":           "โรงเรียนที่ผู้สมัครจบมา",
        "province_school":  "จังหวัดที่โรงเรียนตั้งอยู่",
        "prefix":           "คำนำหน้าชื่อ: นาย / นางสาว / นาง",
        "first_name":       "ชื่อของผู้สมัคร",
        "last_name":        "นามสกุลของผู้สมัคร",
        "phone":            "เบอร์โทรศัพท์ รูปแบบ 0X-XXXX-XXXX",
        "line_id":          "LINE ID ของผู้สมัคร",
        "facebook":         "Facebook ของผู้สมัคร",
        "academic_year":    "ปีการศึกษาที่สมัคร เช่น 2569",
        "status":           "สถานะการสมัคร: ยืนยันการตรวจสอบแล้ว / รอตรวจสอบ",
        "apply_date":       "วันที่สมัคร รูปแบบ MM/DD/YYYY HH:MM",
        "created_at":       "วันที่บันทึกข้อมูล (auto)",
    },
    "students": {
        "id":           "รหัสนักศึกษา (auto)",
        "name":         "ชื่อนักศึกษา",
        "major":        "สาขาวิชา",
        "gpa":          "เกรดเฉลี่ยสะสม (0.00-4.00)",
        "year":         "ชั้นปีที่",
        "created_at":   "วันที่บันทึก (auto)",
    },
    "courses": {
        "id":           "รหัสวิชา (auto)",
        "code":         "รหัสวิชา เช่น CS101",
        "name":         "ชื่อวิชา",
        "credits":      "หน่วยกิต",
        "department":   "ภาควิชา",
    },
    "enrollments": {
        "id":           "รหัสการลงทะเบียน (auto)",
        "student_id":   "FK → students",
        "course_id":    "FK → courses",
        "semester":     "ภาคการศึกษา เช่น 1/2566",
        "grade":        "เกรดที่ได้",
    },
    "customers": {
        "id":           "รหัสลูกค้า (auto)",
        "name":         "ชื่อลูกค้า",
        "email":        "อีเมล",
        "region":       "ภูมิภาค เช่น North, South",
        "created_at":   "วันที่สมัคร (auto)",
    },
    "products": {
        "id":           "รหัสสินค้า (auto)",
        "name":         "ชื่อสินค้า",
        "category":     "หมวดหมู่สินค้า",
        "price":        "ราคาต่อหน่วย (บาท)",
        "stock":        "จำนวนสต็อก",
    },
    "orders": {
        "id":           "รหัสคำสั่งซื้อ (auto)",
        "customer_id":  "FK → customers",
        "order_date":   "วันที่สั่งซื้อ",
        "total_amount": "ยอดรวม (บาท)",
        "status":       "สถานะ: pending/shipped/delivered/cancelled",
    },
    "order_items": {
        "id":           "รหัสรายการสินค้า (auto)",
        "order_id":     "FK → orders",
        "product_id":   "FK → products",
        "quantity":     "จำนวนที่สั่ง",
        "unit_price":   "ราคาต่อหน่วยขณะสั่ง",
    },
}

# ── Sample values shown per table for AI context ──────────────────────────────
_SAMPLE_VALUES: dict[str, dict[str, str]] = {
    "applicants": {
        "level":         "ปริญญาตรี | ปริญญาตรีภศเทียบโอนอต่อเนื่องษ | ประกาศนียบัตรวิชาชีพชั้นสูง",
        "status":        "ยืนยันการตรวจสอบแล้ว | รอตรวจสอบ",
        "prefix":        "นาย | นางสาว | นาง",
        "academic_year": "2569",
        "province_origin": "ร้อยเอ็ด | สกลนคร | อุดรธานี | สินธุ์ | กุฉินารายณ์",
    },
    "orders": {
        "status": "pending | shipped | delivered | cancelled",
    },
}


def format_schema_as_doc(engine: Engine) -> str:
    """
    Format the full DB schema as a structured, AI-friendly Thai documentation.

    Output includes:
    - Table name + Thai description + row count
    - Each column: name, type, constraints, Thai meaning, sample values
    - FK relationships
    - Available views

    This richer format helps AI understand what data exists and how to query it,
    even when the question is in Thai and column names are in English.
    """
    schema = get_db_schema(engine)
    views = get_views(engine)

    # Fetch sample values for key columns dynamically
    sample_data: dict[str, dict[str, list]] = {}
    with engine.connect() as con:
        for table in schema:
            sample_data[table] = {}
            for col in schema[table]["columns"]:
                col_name = col["name"]
                col_type = col["type"]
                # Only fetch samples for text/varchar columns (not PK, timestamps)
                if col_type in ("text", "character varying") and not col["is_pk"] and col_name != "created_at":
                    try:
                        res = con.execute(text(
                            f'SELECT DISTINCT "{col_name}" FROM "{table}" '
                            f'WHERE "{col_name}" IS NOT NULL AND "{col_name}" != \'\' '
                            f'LIMIT 5'
                        ))
                        vals = [str(r[0]) for r in res if r[0]]
                        if vals:
                            sample_data[table][col_name] = vals
                    except Exception:
                        pass

    lines = []
    lines.append("╔══════════════════════════════════════════════════════════════╗")
    lines.append("║              DATABASE SCHEMA DOCUMENTATION                   ║")
    lines.append("║  (ใช้สำหรับสร้าง SQL query เท่านั้น — อ่านแล้วสร้าง SQL)   ║")
    lines.append("╚══════════════════════════════════════════════════════════════╝")
    lines.append("")

    for table_name, info in schema.items():
        col_descs = _COLUMN_DESCRIPTIONS.get(table_name, {})
        preset_samples = _SAMPLE_VALUES.get(table_name, {})
        row_count = info["row_count"]

        lines.append(f"┌─ TABLE: {table_name}  ({row_count:,} rows)")
        lines.append(f"│")

        for col in info["columns"]:
            col_name = col["name"]
            col_type = col["type"]

            # Build constraint tags
            tags = []
            if col["is_pk"]:
                tags.append("🔑 PK")
            if col["fk_table"]:
                tags.append(f"🔗 FK→{col['fk_table']}")
            if not col["nullable"] and not col["is_pk"]:
                tags.append("NOT NULL")
            tag_str = f"  [{', '.join(tags)}]" if tags else ""

            # Thai description
            desc = col_descs.get(col_name, "")
            desc_str = f"  // {desc}" if desc else ""

            lines.append(f"│  • {col_name}: {col_type}{tag_str}{desc_str}")

            # Sample values (preset takes priority over dynamic)
            samples = preset_samples.get(col_name) or (
                " | ".join(sample_data[table_name].get(col_name, [])[:5])
            )
            if samples and col_name not in ("id", "created_at", "apply_date"):
                lines.append(f"│      ↳ ตัวอย่าง: {samples}")

        # Show FK relationships summary
        fk_cols = [c for c in info["columns"] if c["fk_table"]]
        if fk_cols:
            lines.append(f"│")
            lines.append(f"│  🔗 Relationships:")
            for c in fk_cols:
                lines.append(f"│     {table_name}.{c['name']} → {c['fk_table']}.id")

        lines.append(f"└{'─'*60}")
        lines.append("")

    if views:
        lines.append("┌─ VIEWS (pre-aggregated / summary tables)")
        for v in views:
            lines.append(f"│  • {v}")
        lines.append(f"└{'─'*60}")
        lines.append("")

    lines.append("━" * 64)
    lines.append("QUERY RULES:")
    lines.append("  • SELECT only — no INSERT/UPDATE/DELETE/DROP/ALTER/CREATE")
    lines.append("  • Always include LIMIT (max 200)")
    lines.append("  • Use exact column names shown above")
    lines.append("  • For Thai text filters use LIKE '%keyword%' or = 'exact value'")
    lines.append("  • Aggregate: COUNT(*), SUM(), AVG(), MAX(), MIN()")
    lines.append("  • If result is empty — the data may not exist; say so clearly")
    lines.append("━" * 64)

    return "\n".join(lines)
