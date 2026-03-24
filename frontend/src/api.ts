export interface Citation {
  id: string;
  title?: string;
  content?: string;
  cosine_similarity?: number;
}

export interface ChatResponse {
  answer_text: string;
  citations: Citation[];
  tool_trace: Record<string, unknown>[];
  latency_ms: number;
  session_id: string;
}

export interface IngestResponse {
  doc_id: string;
  chunks_inserted: number;
}

export interface DocInfo {
  doc_id: string;
  chunk_count: number;
}

const BASE = "https://chatbot-rag-h6oj.onrender.com";

export async function sendChat(
  message: string,
  sessionId: string,
  mode: "rag" | "sql" | "auto" = "auto",
  topK: number = 5
): Promise<ChatResponse> {
  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      mode,
      top_k: topK,
    }),
  });
  if (!res.ok) throw new Error(`Chat failed: ${res.statusText}`);
  return res.json();
}

export function streamChat(
  message: string,
  sessionId: string,
  mode: "rag" | "sql" | "auto" = "auto",
  topK: number = 5,
  onToken: (token: string) => void,
  onDone: (data: { answer_text?: string; citations?: Citation[]; tool_trace?: Record<string, unknown>[] }) => void,
  onError: (err: string) => void
): () => void {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch(`${BASE}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message,
          session_id: sessionId,
          mode,
          top_k: topK,
        }),
        signal: controller.signal,
      });

      if (!res.ok) {
        onError(`Stream failed: ${res.statusText}`);
        return;
      }

      const reader = res.body?.getReader();
      if (!reader) {
        onError("No response body");
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            const eventType = line.slice(7).trim();
            continue;
          }
          if (line.startsWith("data: ")) {
            const data = line.slice(6);
            // Determine event type from the previous event line
            // SSE format: event: X\ndata: Y\n\n
            // We need to track the current event type
            try {
              const parsed = JSON.parse(data);
              if (parsed.citations !== undefined || parsed.answer_text !== undefined) {
                onDone(parsed);
              } else if (parsed.intent !== undefined) {
                // trace event, ignore for now
              }
            } catch {
              // Plain text token
              onToken(data);
            }
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== "AbortError") {
        onError(err.message);
      }
    }
  })();

  return () => controller.abort();
}

export async function ingestText(
  docId: string,
  content: string,
  chunkSize: number = 600,
  overlap: number = 100
): Promise<IngestResponse> {
  const res = await fetch(`${BASE}/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      doc_id: docId,
      content,
      chunk_size: chunkSize,
      overlap,
    }),
  });
  if (!res.ok) throw new Error(`Ingest failed: ${res.statusText}`);
  return res.json();
}

export async function ingestFile(
  file: File,
  docId: string,
  chunkSize: number = 600,
  overlap: number = 100
): Promise<IngestResponse> {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("doc_id", docId);
  fd.append("chunk_size", String(chunkSize));
  fd.append("overlap", String(overlap));

  const res = await fetch(`${BASE}/ingest/file`, { method: "POST", body: fd });
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail ?? detail; } catch { /* ignore */ }
    throw new Error(detail);
  }
  return res.json();
}

export interface DocContent {
  doc_id: string;
  filename: string;
  chunk_count: number;
  full_text: string;
  chunks: { chunk_index: number; content: string; metadata: Record<string, unknown> }[];
}

export async function getDocumentContent(docId: string): Promise<DocContent> {
  const res = await fetch(`${BASE}/documents/${encodeURIComponent(docId)}/content`);
  if (!res.ok) throw new Error(`Failed to load document: ${res.statusText}`);
  return res.json();
}

export function getOriginalFileUrl(docId: string): string {
  return `${BASE}/documents/${encodeURIComponent(docId)}/file`;
}

export async function hasOriginalFile(docId: string): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/documents/${encodeURIComponent(docId)}/file`, {
      headers: { Range: "bytes=0-0" },
    });
    return res.ok || res.status === 206;
  } catch {
    return false;
  }
}

export async function listDocuments(): Promise<DocInfo[]> {
  const res = await fetch(`${BASE}/documents`);
  if (!res.ok) throw new Error(`List docs failed: ${res.statusText}`);
  return res.json();
}

export async function deleteDocument(docId: string): Promise<void> {
  const res = await fetch(`${BASE}/documents/${encodeURIComponent(docId)}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`Delete failed: ${res.statusText}`);
}

export async function healthCheck(): Promise<{ status: string; db: string }> {
  const res = await fetch(`${BASE}/health`);
  return res.json();
}
