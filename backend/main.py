"""
RAG Chatbot Workshop — FastAPI Backend
Endpoints: /chat, /chat/stream, /ingest, /health
"""

import json
import time
import asyncio
import os
import mimetypes
from pathlib import Path
from collections import defaultdict
from contextlib import asynccontextmanager

# Directory to store original uploaded files
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from sse_starlette.sse import EventSourceResponse
from google import genai
from google.genai import types

from backend.config import settings
from backend.rag.ingest import ingest_document
from backend.rag.retriever_pgvector import retrieve_top_k
from backend.rag.prompts import RAG_SYSTEM, RAG_USER
from backend.agent.graph import run_agent

# ─── Database engine ─────────────────────────────────────────────────
engine = create_engine(settings.db_url, pool_size=5, max_overflow=10)

# ─── Simple in-memory session store ─────────────────────────────────
sessions: dict[str, list[dict]] = defaultdict(list)
MAX_HISTORY = 10


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify DB connection and Create Tables
    try:
        with engine.begin() as con:  # ใช้ begin() เพื่อให้มัน Commit คำสั่งอัตโนมัติ
            # 1. เช็คการเชื่อมต่อ
            con.execute(text("SELECT 1"))
            
            # 2. สร้างตาราง chat_sessions
            con.execute(text("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id VARCHAR(100) PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            
            # 3. สร้างตาราง chat_messages
            con.execute(text("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id SERIAL PRIMARY KEY,
                    session_id VARCHAR(100) REFERENCES chat_sessions(id) ON DELETE CASCADE,
                    role VARCHAR(20) NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
        print("✓ Database connected & Tables created successfully!")
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
    yield
    engine.dispose()


app = FastAPI(
    title="RAG Chatbot API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    # ต้องใส่ลิงก์ Vercel ของบอสเข้าไปตรงนี้ (ห้ามมี / ปิดท้าย)
    allow_origins=[
        "http://localhost:5173", 
        "https://chatbot-rag-azure.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request / Response Models ───────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    mode: str = Field(default="auto", pattern="^(rag|sql|auto)$")
    top_k: int = Field(default=5, ge=1, le=20)


class Citation(BaseModel):
    id: str
    title: str | None = None
    content: str | None = None
    cosine_similarity: float | None = None


class ChatResponse(BaseModel):
    answer_text: str
    citations: list[Citation] = []
    tool_trace: list[dict] = []
    latency_ms: float = 0
    session_id: str = ""


class IngestRequest(BaseModel):
    doc_id: str
    content: str
    metadata: dict = {}
    chunk_size: int = 600
    overlap: int = 100


class IngestResponse(BaseModel):
    doc_id: str
    chunks_inserted: int


# ─── Endpoints ───────────────────────────────────────────────────────
@app.get("/health")
async def health():
    try:
        with engine.connect() as con:
            con.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        return {"status": "degraded", "db": str(e)}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Non-streaming chat endpoint using the Agentic RAG pipeline."""
    start = time.time()

    # Add user message to session history
    sessions[req.session_id].append({"role": "user", "content": req.message})

    # Run the agent
    result = run_agent(engine, req.message, mode=req.mode)

    # Add assistant response to session history
    sessions[req.session_id].append({
        "role": "assistant",
        "content": result["answer_text"],
    })

    # Trim history
    if len(sessions[req.session_id]) > MAX_HISTORY * 2:
        sessions[req.session_id] = sessions[req.session_id][-(MAX_HISTORY * 2):]

    return ChatResponse(
        answer_text=result["answer_text"],
        citations=[Citation(**c) for c in result.get("citations", [])],
        tool_trace=result.get("tool_trace", []),
        latency_ms=result.get("latency_ms", (time.time() - start) * 1000),
        session_id=req.session_id,
    )


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """Streaming chat endpoint using SSE."""

    async def event_generator():
        # Add user message to session history
        sessions[req.session_id].append({"role": "user", "content": req.message})

        # Step 1: Run retrieval and routing (non-streaming part)
        from backend.agent.graph import (
            AgentState,
            route_intent,
            retrieve_docs,
            query_sql_node,
            evaluate_context,
            rewrite_query,
            fallback_answer,
            MAX_REWRITE_ITERATIONS,
        )

        state = AgentState(
            original_question=req.message,
            current_question=req.message,
        )

        # Route
        if req.mode == "rag":
            state.intent = "docs"
        elif req.mode == "sql":
            state.intent = "sql"
        else:
            state = route_intent(state)

        yield {"event": "trace", "data": json.dumps({"intent": state.intent})}

        # Unknown intent: return early
        if state.intent == "unknown":
            yield {
                "event": "done",
                "data": json.dumps({
                    "answer_text": "คำถามนี้ไม่เกี่ยวกับข้อมูลในระบบ กรุณาถามเกี่ยวกับผู้สมัคร นักศึกษา สินค้า คำสั่งซื้อ หรือโครงสร้างฐานข้อมูลครับ",
                    "citations": [],
                    "tool_trace": state.tool_trace,
                }, ensure_ascii=False),
            }
            return

        # SQL intent: bypass evaluate/rewrite — sql_rag_answer handles all cases internally
        if state.intent == "sql":
            state = query_sql_node(state, engine)

        else:
            # Docs / mixed: retrieve → evaluate → rewrite loop
            while not state.done and state.iteration <= MAX_REWRITE_ITERATIONS:
                if state.intent in ("docs", "mixed"):
                    state = retrieve_docs(state, engine)
                if state.intent == "mixed":
                    state = query_sql_node(state, engine)

                state = evaluate_context(state)

                relevance = state.evaluation.get("relevance", 0)
                sufficiency = state.evaluation.get("sufficiency", 0)

                if relevance >= 1 and sufficiency >= 1:
                    break
                elif state.iteration < MAX_REWRITE_ITERATIONS:
                    state = rewrite_query(state)
                    state = route_intent(state)
                    # If rewrite changed intent to sql, handle immediately
                    if state.intent == "sql":
                        state = query_sql_node(state, engine)
                        break
                else:
                    state = fallback_answer(state)
                    yield {
                        "event": "done",
                        "data": json.dumps({
                            "answer_text": state.answer_text,
                            "citations": [],
                            "tool_trace": state.tool_trace,
                        }, ensure_ascii=False),
                    }
                    return

        # SQL intent — not streamable, return full answer
        if state.intent == "sql" and state.sql_result:
            answer = state.sql_result.get("answer_text", "")
            sessions[req.session_id].append({"role": "assistant", "content": answer})
            yield {
                "event": "done",
                "data": json.dumps({
                    "answer_text": answer,
                    "citations": [{"id": "sql_query", "title": "SQL Query", "content": state.sql_result.get("sql", "")}] if state.sql_result.get("sql") else [],
                    "tool_trace": state.tool_trace,
                }, ensure_ascii=False),
            }
            return

        # Step 2: Stream the answer generation
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
                }
                for i, c in enumerate(state.context_chunks)
            ]
        else:
            context = "(ไม่มีบริบท)"
            citations = []

        prompt = RAG_USER.format(question=state.original_question, context=context)

        client = genai.Client(api_key=settings.gemini_api_key)
        config = types.GenerateContentConfig(
            system_instruction=RAG_SYSTEM,
            temperature=0.2,
        )

        full_answer = ""
        response = client.models.generate_content_stream(
            model=settings.chat_model,
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=config,
        )

        for chunk in response:
            if chunk.text:
                full_answer += chunk.text
                yield {"event": "token", "data": chunk.text}
                await asyncio.sleep(0)  # yield control

        sessions[req.session_id].append({"role": "assistant", "content": full_answer})

        yield {
            "event": "done",
            "data": json.dumps({
                "citations": citations,
                "tool_trace": state.tool_trace,
            }, ensure_ascii=False),
        }

    return EventSourceResponse(event_generator())


@app.post("/ingest", response_model=IngestResponse)
async def ingest(req: IngestRequest):
    """Ingest a document: chunk, embed, and store in pgvector."""
    try:
        count = ingest_document(
            engine=engine,
            doc_id=req.doc_id,
            content=req.content,
            metadata=req.metadata,
            chunk_size=req.chunk_size,
            overlap=req.overlap,
        )
        return IngestResponse(doc_id=req.doc_id, chunks_inserted=count)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingest/file", response_model=IngestResponse)
async def ingest_file(
    file: UploadFile = File(...),
    doc_id: str = Form(...),
    chunk_size: int = Form(600),
    overlap: int = Form(100),
):
    """Ingest a text file: read, chunk, embed, and store."""
    try:
        raw = await file.read()
        filename = (file.filename or "").lower()

        # Detect PDF by filename extension OR magic bytes (%PDF-)
        is_pdf = filename.endswith(".pdf") or raw[:5] == b"%PDF-"

        if is_pdf:
            import io
            import logging
            from pypdf import PdfReader
            from pypdf.errors import PdfStreamError, PdfReadError
            try:
                reader = PdfReader(io.BytesIO(raw), strict=False)
                pages = [page.extract_text() or "" for page in reader.pages]
                content = "\n\n".join(p for p in pages if p.strip())
            except (PdfStreamError, PdfReadError, Exception) as pdf_err:
                logging.error(f"PDF parse error for {file.filename}: {pdf_err}")
                raise ValueError(f"ไม่สามารถอ่าน PDF ได้: {pdf_err}")
            if not content.strip():
                raise ValueError("PDF ไม่มีข้อความที่อ่านได้ (อาจเป็น PDF สแกน/รูปภาพ)")
        else:
            # Try encodings in order: utf-8-sig (BOM), utf-16, utf-8, TIS-620 Thai, latin-1
            content: str | None = None
            for enc in ("utf-8-sig", "utf-16", "utf-8", "tis-620", "cp874", "latin-1"):
                try:
                    content = raw.decode(enc)
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
            if content is None:
                raise ValueError("ไม่สามารถอ่านไฟล์ได้ — encoding ไม่รองรับ")
        # Save original file to disk (keep original bytes)
        # Truncate filename to avoid OSError: File name too long
        import hashlib
        orig_filename = file.filename or f"{doc_id}.bin"
        safe_name = orig_filename.replace("/", "_").replace("\\", "_")
        
        # Limit total filename length to 200 chars (safe for most filesystems)
        # Format: {doc_id_truncated}__{filename_truncated}.{ext}
        name_part, ext = os.path.splitext(safe_name)
        doc_id_short = doc_id[:80] if len(doc_id) > 80 else doc_id
        name_short = name_part[:80] if len(name_part) > 80 else name_part
        
        # Add hash suffix to ensure uniqueness if truncated
        file_hash = hashlib.md5(f"{doc_id}{orig_filename}".encode()).hexdigest()[:8]
        final_name = f"{doc_id_short}__{name_short}_{file_hash}{ext}"
        
        dest = UPLOAD_DIR / final_name
        dest.write_bytes(raw)

        count = ingest_document(
            engine=engine,
            doc_id=doc_id,
            content=content,
            metadata={"filename": orig_filename},
            chunk_size=chunk_size,
            overlap=overlap,
        )
        return IngestResponse(doc_id=doc_id, chunks_inserted=count)
    except HTTPException:
        raise
    except Exception as e:
        import traceback, logging
        logging.error(f"ingest/file error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents")
async def list_documents():
    """List all ingested document IDs and their chunk counts."""
    with engine.connect() as con:
        res = con.execute(
            text("SELECT doc_id, COUNT(*) as chunk_count FROM doc_chunks GROUP BY doc_id ORDER BY doc_id")
        )
        return [dict(r._mapping) for r in res]


@app.get("/documents/{doc_id}/file")
async def download_document_file(doc_id: str):
    """Download the original uploaded file for a document."""
    # Find the stored file (format: {doc_id}__{original_filename})
    matches = list(UPLOAD_DIR.glob(f"{doc_id}__*"))
    if not matches:
        raise HTTPException(status_code=404, detail=f"Original file for '{doc_id}' not found")
    filepath = matches[0]
    orig_name = filepath.name[len(doc_id) + 2:]  # strip "{doc_id}__" prefix
    media_type = mimetypes.guess_type(orig_name)[0] or "application/octet-stream"
    return FileResponse(
        path=str(filepath),
        filename=orig_name,
        media_type=media_type,
    )


@app.get("/documents/{doc_id}/content")
async def get_document_content(doc_id: str):
    """Return all chunks for a document, ordered by chunk_index."""
    with engine.connect() as con:
        res = con.execute(
            text("""
                SELECT chunk_index, content, metadata
                FROM doc_chunks
                WHERE doc_id = :doc_id
                ORDER BY chunk_index
            """),
            {"doc_id": doc_id},
        )
        rows = [dict(r._mapping) for r in res]
        if not rows:
            raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")
        full_text = "\n\n".join(r["content"] for r in rows)
        filename = rows[0].get("metadata", {}).get("filename", doc_id) if rows else doc_id
        return {
            "doc_id": doc_id,
            "filename": filename,
            "chunk_count": len(rows),
            "chunks": rows,
            "full_text": full_text,
        }


@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Delete all chunks for a given document."""
    with engine.begin() as con:
        res = con.execute(
            text("DELETE FROM doc_chunks WHERE doc_id = :doc_id"),
            {"doc_id": doc_id},
        )
        return {"doc_id": doc_id, "deleted_chunks": res.rowcount}

# ─── 🕒 ส่วนที่เพิ่มใหม่: ระบบประวัติการสนทนา ───────────────────────────

@app.get("/sessions")
async def get_all_sessions():
    """ดึงรายชื่อ Session ID ทั้งหมดที่มีการคุยกันไว้"""
    # ในที่นี้เราดึงจากตัวแปร sessions ที่เป็น In-memory
    history_list = []
    for s_id, msgs in sessions.items():
        # สร้างหัวข้อแชทจากข้อความแรกที่คุย
        first_msg = msgs[0]["content"][:30] + "..." if msgs else "แชทใหม่"
        history_list.append({
            "id": s_id,
            "title": first_msg,
            "created_at": "เพิ่งคุยเมื่อกี้" # ในอนาคตค่อยเก็บเวลาจริงลง DB
        })
    
    # ถ้ายังไม่มีประวัติเลย ให้ส่งค่าว่างกลับไป
    return history_list

@app.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    """ดึงข้อความทั้งหมดใน Session นั้นๆ มาแสดงในหน้าแชท"""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="ไม่พบประวัติการแชทนี้")
    
    return sessions[session_id]

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
