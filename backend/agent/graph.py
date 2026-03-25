"""
Agentic RAG: Router → Retrieve/SQL → Evaluate → Answer/Rewrite

State-based workflow with loop limit for query rewriting.
"""

import json
import time
from dataclasses import dataclass, field

from google import genai
from google.genai import types
from sqlalchemy.engine import Engine

from backend.config import settings
from backend.rag.retriever_pgvector import retrieve_top_k
from backend.rag.prompts import (
    RAG_SYSTEM,
    RAG_USER,
    ROUTE_SYSTEM,
    EVALUATE_SYSTEM,
    REWRITE_SYSTEM,
)
from backend.sql.function_calling_sql import sql_rag_answer
# ตัวอย่างการเพิ่มในไฟล์ที่บอสใช้รวม Tools
from backend.sql.sql_tool import create_bar_chart

tools = [
    # ... tools เดิมที่มีอยู่ ...,
    create_bar_chart
]

MAX_REWRITE_ITERATIONS = 2


@dataclass
class AgentState:
    """Tracks the state of the agentic RAG workflow."""
    original_question: str = ""
    current_question: str = ""
    intent: str = "unknown"         # sql | docs | mixed | unknown
    context_chunks: list = field(default_factory=list)
    sql_result: dict | None = None
    evaluation: dict | None = None  # {"relevance": int, "sufficiency": int}
    answer_text: str = ""
    citations: list = field(default_factory=list)
    tool_trace: list = field(default_factory=list)
    iteration: int = 0
    done: bool = False
    latency_ms: float = 0


def _get_client() -> genai.Client:
    return genai.Client(api_key=settings.gemini_api_key)


# ─── Node: Route Intent ─────────────────────────────────────────────
def route_intent(state: AgentState) -> AgentState:
    """Classify the user question as sql / docs / mixed / unknown."""
    client = _get_client()

    config = types.GenerateContentConfig(
        system_instruction=ROUTE_SYSTEM,
        temperature=0.0,
    )

    resp = client.models.generate_content(
        model=settings.chat_model,
        contents=[types.Content(role="user", parts=[types.Part(text=state.current_question)])],
        config=config,
    )

    intent_raw = (resp.text or "unknown").strip().lower()
    # Normalize to allowed values
    if intent_raw in ("sql", "docs", "mixed", "unknown"):
        state.intent = intent_raw
    else:
        state.intent = "unknown"

    state.tool_trace.append({"node": "route_intent", "intent": state.intent})
    return state


# ─── Node: Retrieve Documents (Vector Search) ───────────────────────
def retrieve_docs(state: AgentState, engine: Engine) -> AgentState:
    """Retrieve top-k chunks from pgvector."""
    chunks = retrieve_top_k(engine, state.current_question)
    state.context_chunks = chunks
    state.tool_trace.append({
        "node": "retrieve_docs",
        "chunks_found": len(chunks),
    })
    return state


# ─── Node: Query SQL ────────────────────────────────────────────────
def query_sql_node(state: AgentState, engine: Engine) -> AgentState:
    """Use function calling to generate and execute SQL."""
    result = sql_rag_answer(engine, state.current_question)
    state.sql_result = result
    state.tool_trace.append({
        "node": "query_sql",
        "sql": result.get("sql"),
        "rows": len(result.get("results") or []),
    })
    return state


# ─── Node: Evaluate Context Quality ─────────────────────────────────
def evaluate_context(state: AgentState) -> AgentState:
    """Judge the quality of retrieved context."""
    client = _get_client()

    # Build context summary for evaluation
    if state.intent in ("docs", "mixed") and state.context_chunks:
        context_summary = "\n".join(
            f"[Chunk {i}]: {c['content'][:200]}"
            for i, c in enumerate(state.context_chunks)
        )
    elif state.intent == "sql" and state.sql_result:
        sql_rows = state.sql_result.get("results") or []
        context_summary = json.dumps(
            sql_rows[:5],
            ensure_ascii=False,
            default=str,
        )
    else:
        context_summary = "(ไม่มีบริบท)"

    prompt = f"""คำถาม: {state.current_question}

บริบทที่ได้มา:
{context_summary}

ให้คะแนนตามเกณฑ์ที่กำหนด"""

    config = types.GenerateContentConfig(
        system_instruction=EVALUATE_SYSTEM,
        temperature=0.0,
    )

    resp = client.models.generate_content(
        model=settings.chat_model,
        contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
        config=config,
    )

    try:
        raw = resp.text.strip()
        # Extract JSON from response
        if "{" in raw:
            json_str = raw[raw.index("{"):raw.rindex("}") + 1]
            state.evaluation = json.loads(json_str)
        else:
            state.evaluation = {"relevance": 1, "sufficiency": 1}
    except Exception:
        state.evaluation = {"relevance": 1, "sufficiency": 1}

    state.tool_trace.append({"node": "evaluate", "evaluation": state.evaluation})
    return state


# ─── Node: Rewrite Query ────────────────────────────────────────────
def rewrite_query(state: AgentState) -> AgentState:
    """Rewrite the query for better retrieval."""
    client = _get_client()

    prompt = f"""คำถามเดิม: {state.current_question}

บริบทที่ได้มาไม่เพียงพอ กรุณาเขียนคำถามใหม่ที่ชัดเจนกว่าเดิม"""

    config = types.GenerateContentConfig(
        system_instruction=REWRITE_SYSTEM,
        temperature=0.3,
    )

    resp = client.models.generate_content(
        model=settings.chat_model,
        contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
        config=config,
    )

    new_query = (resp.text or state.current_question).strip()
    state.current_question = new_query
    state.iteration += 1
    state.tool_trace.append({
        "node": "rewrite_query",
        "iteration": state.iteration,
        "new_query": new_query,
    })
    return state


# ─── Node: Generate Answer ──────────────────────────────────────────
def generate_answer(state: AgentState) -> AgentState:
    """Generate final answer with citations from context."""
    client = _get_client()

    # For SQL intent, use the SQL RAG answer directly
    if state.intent == "sql" and state.sql_result:
        state.answer_text = state.sql_result.get("answer_text", "")
        state.citations = []
        if state.sql_result.get("sql"):
            state.citations.append({
                "id": "sql_query",
                "title": "SQL Query",
                "content": state.sql_result["sql"],
            })
        state.done = True
        return state

    # For docs / mixed intent, use RAG
    if state.context_chunks:
        context = "\n\n".join(
            f"[CIT{i}] (doc_id={c['doc_id']}, chunk={c['chunk_index']}):\n{c['content']}"
            for i, c in enumerate(state.context_chunks)
        )
        citations = [
            {
                "id": f"CIT{i}",
                "title": f"{c['doc_id']} (chunk {c['chunk_index']})",
                "content": c["content"][:200],
                "cosine_similarity": float(c.get("cosine_similarity", 0)),
            }
            for i, c in enumerate(state.context_chunks)
        ]
    else:
        context = "(ไม่มีบริบท)"
        citations = []

    prompt = RAG_USER.format(question=state.original_question, context=context)

    config = types.GenerateContentConfig(
        system_instruction=RAG_SYSTEM,
        temperature=0.2,
    )

    resp = client.models.generate_content(
        model=settings.chat_model,
        contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
        config=config,
    )

    state.answer_text = resp.text or "ไม่สามารถสร้างคำตอบได้"
    state.citations = citations

    # If mixed, append SQL result too
    if state.intent == "mixed" and state.sql_result:
        sql_answer = state.sql_result.get("answer_text", "")
        if sql_answer:
            state.answer_text += f"\n\n**ข้อมูลจากฐานข้อมูล:**\n{sql_answer}"
        if state.sql_result.get("sql"):
            state.citations.append({
                "id": "sql_query",
                "title": "SQL Query",
                "content": state.sql_result["sql"],
            })

    state.done = True
    return state


# ─── Node: Fallback ─────────────────────────────────────────────────
def fallback_answer(state: AgentState) -> AgentState:
    """Fallback when loop limit is reached or no evidence found."""
    state.answer_text = (
        "ไม่มีข้อมูลเพียงพอที่จะตอบคำถามนี้ได้ "
        "กรุณาลองถามคำถามที่เฉพาะเจาะจงมากขึ้น หรือระบุรายละเอียดเพิ่มเติม"
    )
    state.citations = []
    state.done = True
    state.tool_trace.append({"node": "fallback", "reason": "loop_limit_or_no_evidence"})
    return state


# ─── Orchestrator: Run the Agent Graph ───────────────────────────────
def run_agent(engine: Engine, question: str, mode: str = "auto") -> dict:
    """
    Run the agentic RAG pipeline.

    mode: "rag" | "sql" | "auto"
    Returns: {answer_text, citations, tool_trace, latency_ms}
    """
    start = time.time()

    state = AgentState(
        original_question=question,
        current_question=question,
    )

    # Step 1: Route intent (or use forced mode)
    if mode == "rag":
        state.intent = "docs"
        state.tool_trace.append({"node": "route_intent", "intent": "docs", "forced": True})
    elif mode == "sql":
        state.intent = "sql"
        state.tool_trace.append({"node": "route_intent", "intent": "sql", "forced": True})
    else:
        state = route_intent(state)

    # Unknown intent: return early with a helpful message
    # Unknown intent: return early with a helpful message
    if state.intent == "unknown":
        state.answer_text = (
            "คำถามนี้อาจจะอยู่นอกเหนือข้อมูลที่ผมมีครับ "
            "กรุณาถามเกี่ยวกับ สินค้าไอที สเปกคอมพิวเตอร์ ออเดอร์การสั่งซื้อ หรือนโยบายการเคลมสินค้านะครับ"
        )
        state.citations = []
        state.done = True
        state.tool_trace.append({"node": "unknown_intent", "reason": "out_of_scope"})

    # SQL intent: bypass evaluate/rewrite — sql_rag_answer handles all cases internally
    elif state.intent == "sql":
        state = query_sql_node(state, engine)
        state = generate_answer(state)
    else:
        # Docs / mixed: retrieve → evaluate → rewrite loop
        while not state.done and state.iteration <= MAX_REWRITE_ITERATIONS:
            # Step 2: Retrieve based on intent
            if state.intent in ("docs", "mixed"):
                state = retrieve_docs(state, engine)
            if state.intent == "mixed":
                state = query_sql_node(state, engine)

            # Step 3: Evaluate context quality
            state = evaluate_context(state)

            relevance = state.evaluation.get("relevance", 0)
            sufficiency = state.evaluation.get("sufficiency", 0)

            # Step 4: Decide — good enough or rewrite?
            if relevance >= 1 and sufficiency >= 1:
                state = generate_answer(state)
            elif state.iteration < MAX_REWRITE_ITERATIONS:
                state = rewrite_query(state)
                # Re-route after rewrite
                state = route_intent(state)
                # If rewrite changed intent to sql, hand off immediately
                if state.intent == "sql":
                    state = query_sql_node(state, engine)
                    state = generate_answer(state)
                    break
            else:
                state = fallback_answer(state)

    # Safety net: if still not done after loop
    if not state.done:
        state = fallback_answer(state)

    state.latency_ms = (time.time() - start) * 1000

    return {
        "answer_text": state.answer_text,
        "citations": state.citations,
        "tool_trace": state.tool_trace,
        "latency_ms": round(state.latency_ms, 1),
    }
