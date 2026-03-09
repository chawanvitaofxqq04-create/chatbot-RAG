import json
from google import genai
from google.genai import types

from backend.config import settings
from backend.sql.sql_tool import run_readonly_sql
from backend.sql.schema_reader import format_schema_as_doc, get_allowed_tables
from backend.rag.prompts import SQL_SYSTEM, SQL_ANSWER_SYSTEM, SQL_ANSWER_USER, SQL_SCHEMA_ANSWER


def _make_query_sql_declaration(allowed_tables: list[str]) -> dict:
    """Create the function declaration for the query_sql tool."""
    return {
        "name": "query_sql",
        "description": (
            "Execute a READ-ONLY SELECT query on PostgreSQL and return rows as JSON. "
            f"Allowed tables: {', '.join(allowed_tables)}. "
            "Always include LIMIT."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "sql": {
                    "type": "STRING",
                    "description": "A valid READ-ONLY SELECT SQL query with LIMIT clause.",
                }
            },
            "required": ["sql"],
        },
    }


def _build_schema_summary(schema_text: str) -> str:
    """
    Extract a concise, clean summary from the full schema doc text.
    Keeps only TABLE lines + row counts + column descriptions.
    Used for SCHEMA_OVERVIEW answers.
    """
    lines = []
    for line in schema_text.splitlines():
        stripped = line.strip()
        # Keep table headers, column descriptions, sample value lines
        if (stripped.startswith("┌─ TABLE:") or
                stripped.startswith("│  •") or
                stripped.startswith("│      ↳") or
                stripped.startswith("┌─ VIEWS")):
            lines.append(line)
    return "\n".join(lines)


def sql_rag_answer(engine, question: str) -> dict:
    """
    Use Gemini function calling to:
    1. Read real DB schema dynamically
    2. Generate SQL based on schema + question
    3. Execute SQL
    4. Synthesize a natural language answer from results

    Returns dict with keys: answer_text, sql, results, tool_trace
    """
    client = genai.Client(api_key=settings.gemini_api_key)
    tool_trace = []

    # ── Step 1: Read real DB schema as structured doc ────────────────────
    try:
        schema_text = format_schema_as_doc(engine)
        allowed_tables = get_allowed_tables(engine)
        tool_trace.append({"tool": "schema_reader", "tables": allowed_tables})
    except Exception as e:
        schema_text = "(ไม่สามารถอ่าน schema ได้)"
        allowed_tables = settings.allowed_tables
        tool_trace.append({"tool": "schema_reader", "error": str(e)})

    # ── Step 2: AI generates SQL via function calling ─────────────────────
    system_prompt = SQL_SYSTEM.format(schema=schema_text)

    tools = [types.Tool(function_declarations=[_make_query_sql_declaration(allowed_tables)])]
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        tools=tools,
        temperature=0.0,
    )

    contents = [types.Content(role="user", parts=[types.Part(text=question)])]

    resp = client.models.generate_content(
        model=settings.chat_model,
        contents=contents,
        config=config,
    )

    candidate = resp.candidates[0]
    parts = candidate.content.parts

    function_call = None
    for part in parts:
        if hasattr(part, "function_call") and part.function_call:
            function_call = part.function_call
            break

    if not function_call:
        # Model returned text — may be SQL as text, CANNOT_QUERY, SCHEMA_OVERVIEW, or clarification
        answer_text = "".join(p.text for p in parts if hasattr(p, "text") and p.text).strip()

        # Handle SCHEMA_OVERVIEW — answer from schema doc directly, no SQL needed
        if answer_text.strip().startswith("SCHEMA_OVERVIEW"):
            tool_trace.append({"tool": "schema_overview"})
            schema_summary = _build_schema_summary(schema_text)
            overview_prompt = SQL_SCHEMA_ANSWER.format(schema_summary=schema_summary)
            overview_config = types.GenerateContentConfig(temperature=0.3)
            overview_resp = client.models.generate_content(
                model=settings.chat_model,
                contents=[types.Content(role="user", parts=[types.Part(text=overview_prompt)])],
                config=overview_config,
            )
            return {
                "answer_text": overview_resp.text or "ไม่สามารถสรุปได้",
                "sql": None,
                "results": None,
                "tool_trace": tool_trace,
            }

        # Handle explicit CANNOT_QUERY signal
        if answer_text.strip().startswith("CANNOT_QUERY"):
            tool_trace.append({"tool": "cannot_query", "reason": answer_text})
            return {
                "answer_text": "คำถามนี้ไม่เกี่ยวกับข้อมูลในฐานข้อมูล กรุณาถามเกี่ยวกับผู้สมัคร นักศึกษา สินค้า หรือคำสั่งซื้อแทนครับ",
                "sql": None,
                "results": None,
                "tool_trace": tool_trace,
            }

        # Fallback: detect if response is a bare SQL SELECT statement and execute it
        sql_candidate = answer_text.strip().rstrip(";")
        if sql_candidate.upper().startswith("SELECT"):
            tool_trace.append({"tool": "sql_fallback", "note": "model returned SQL as text", "sql": sql_candidate})
            try:
                results = run_readonly_sql(engine, sql_candidate)
                tool_trace.append({"tool": "sql_execute", "rows_returned": len(results)})

                row_count = len(results)
                display_results = results[:50] if row_count > 50 else results
                results_json = json.dumps(display_results, ensure_ascii=False, default=str, indent=2)

                answer_prompt = SQL_ANSWER_USER.format(
                    question=question,
                    sql=sql_candidate,
                    row_count=row_count,
                    results=results_json,
                )
                answer_config = types.GenerateContentConfig(
                    system_instruction=SQL_ANSWER_SYSTEM,
                    temperature=0.3,
                )
                answer_resp = client.models.generate_content(
                    model=settings.chat_model,
                    contents=[types.Content(role="user", parts=[types.Part(text=answer_prompt)])],
                    config=answer_config,
                )
                tool_trace.append({"tool": "sql_answer_synthesis", "input_rows": row_count})
                return {
                    "answer_text": answer_resp.text or "ไม่สามารถสรุปคำตอบได้",
                    "sql": sql_candidate,
                    "results": results,
                    "tool_trace": tool_trace,
                }
            except Exception as e:
                tool_trace.append({"tool": "sql_fallback_execute", "error": str(e)})

        return {
            "answer_text": answer_text or "ไม่สามารถสร้าง SQL ได้ กรุณาถามคำถามให้ชัดเจนขึ้น",
            "sql": None,
            "results": None,
            "tool_trace": tool_trace,
        }

    sql = function_call.args.get("sql", "").strip()
    tool_trace.append({"tool": "sql_generate", "sql": sql})

    # ── Step 3: Execute the SQL ───────────────────────────────────────────
    try:
        results = run_readonly_sql(engine, sql)
        tool_trace.append({"tool": "sql_execute", "rows_returned": len(results)})
    except Exception as e:
        tool_trace.append({"tool": "sql_execute", "error": str(e)})
        return {
            "answer_text": f"เกิดข้อผิดพลาดในการ query ข้อมูล: {str(e)}",
            "sql": sql,
            "results": None,
            "tool_trace": tool_trace,
        }

    # ── Step 4: AI synthesizes natural language answer from results ───────
    row_count = len(results)

    # Limit results size to avoid token overflow (keep first 50 rows for large results)
    display_results = results[:50] if row_count > 50 else results
    results_json = json.dumps(display_results, ensure_ascii=False, default=str, indent=2)

    answer_prompt = SQL_ANSWER_USER.format(
        question=question,
        sql=sql,
        row_count=row_count,
        results=results_json,
    )

    answer_config = types.GenerateContentConfig(
        system_instruction=SQL_ANSWER_SYSTEM,
        temperature=0.3,
    )

    answer_resp = client.models.generate_content(
        model=settings.chat_model,
        contents=[types.Content(role="user", parts=[types.Part(text=answer_prompt)])],
        config=answer_config,
    )

    answer_text = answer_resp.text or "ไม่สามารถสรุปคำตอบได้"
    tool_trace.append({"tool": "sql_answer_synthesis", "input_rows": row_count})

    return {
        "answer_text": answer_text,
        "sql": sql,
        "results": results,
        "tool_trace": tool_trace,
    }
