import { useState, useRef, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import {
  sendChat,
  streamChat,
  ingestFile,
  listDocuments,
  deleteDocument,
  healthCheck,
  getDocumentContent,
  getOriginalFileUrl,
  hasOriginalFile,
  type Citation,
  type DocInfo,
  type DocContent,
} from "./api";
import {
  Send,
  Bot,
  User,
  FileUp,
  Trash2,
  Database,
  FileText,
  Zap,
  Loader2,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  CheckCircle2,
  Clock,
  Sparkles,
  PanelLeft,
  Code2,
  Upload,
  File,
  FileCode,
  RefreshCw,
  X,
  BookOpen,
  Eye,
  ExternalLink,
  Layers,
} from "lucide-react";

interface UploadStatus {
  file: string;
  status: "uploading" | "done" | "error";
  chunks?: number;
  error?: string;
}

type Mode = "auto" | "rag" | "sql";

interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  toolTrace?: Record<string, unknown>[];
  latencyMs?: number;
  mode?: Mode;
}

function generateSessionId(): string {
  return `session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<Mode>("auto");
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [useStream, setUseStream] = useState(true);
  const [sessionId] = useState(generateSessionId);
  const [showSidebar, setShowSidebar] = useState(false);
  const [documents, setDocuments] = useState<DocInfo[]>([]);
  const [health, setHealth] = useState<{ status: string; db: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploadQueue, setUploadQueue] = useState<UploadStatus[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [viewingDoc, setViewingDoc] = useState<DocContent | null>(null);
  const [viewLoading, setViewLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const cancelStreamRef = useRef<(() => void) | null>(null);
  const dropZoneRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(() => {
    healthCheck()
      .then(setHealth)
      .catch(() => setHealth({ status: "error", db: "unreachable" }));
  }, []);

  const loadDocs = useCallback(async () => {
    try {
      const docs = await listDocuments();
      setDocuments(docs);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    if (showSidebar) loadDocs();
  }, [showSidebar, loadDocs]);

  // Auto-open sidebar when switching to RAG mode
  useEffect(() => {
    if (mode === "rag") setShowSidebar(true);
  }, [mode]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || loading || streaming) return;

    setInput("");
    setError(null);
    const userMsg: Message = { role: "user", content: text, mode };
    setMessages((prev) => [...prev, userMsg]);

    if (useStream) {
      setStreaming(true);
      let assistantContent = "";
      const assistantMsg: Message = { role: "assistant", content: "", mode };
      setMessages((prev) => [...prev, assistantMsg]);

      cancelStreamRef.current = streamChat(
        text,
        sessionId,
        mode,
        5,
        (token) => {
          assistantContent += token;
          setMessages((prev) => {
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...updated[updated.length - 1],
              content: assistantContent,
            };
            return updated;
          });
        },
        (data) => {
          setMessages((prev) => {
            const updated = [...prev];
            const last = updated[updated.length - 1];
            updated[updated.length - 1] = {
              ...last,
              content: data.answer_text || last.content,
              citations: data.citations,
              toolTrace: data.tool_trace,
            };
            return updated;
          });
          setStreaming(false);
        },
        (err) => {
          setError(err);
          setStreaming(false);
        }
      );
    } else {
      setLoading(true);
      try {
        const resp = await sendChat(text, sessionId, mode);
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: resp.answer_text,
            citations: resp.citations,
            toolTrace: resp.tool_trace,
            latencyMs: resp.latency_ms,
            mode,
          },
        ]);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const uploadFiles = useCallback(async (files: File[]) => {
    const allowed = files.filter(f =>
      /\.(txt|md|csv|pdf|json|docx?)$/i.test(f.name)
    );
    if (!allowed.length) return;

    for (const file of allowed) {
      const docId = file.name.replace(/\.[^.]+$/, "");
      setUploadQueue(q => [...q, { file: file.name, status: "uploading" }]);
      try {
        const resp = await ingestFile(file, docId);
        setUploadQueue(q => q.map(u =>
          u.file === file.name
            ? { ...u, status: "done", chunks: resp.chunks_inserted }
            : u
        ));
        await loadDocs();
      } catch (err: unknown) {
        setUploadQueue(q => q.map(u =>
          u.file === file.name
            ? { ...u, status: "error", error: err instanceof Error ? err.message : "failed" }
            : u
        ));
      }
    }
    // Clear done items after 4s
    setTimeout(() => {
      setUploadQueue(q => q.filter(u => u.status === "uploading"));
    }, 4000);
  }, [loadDocs]);

  const handleFileInputChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    e.target.value = "";
    await uploadFiles(files);
  };

  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const files = Array.from(e.dataTransfer.files);
    await uploadFiles(files);
  }, [uploadFiles]);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    if (!dropZoneRef.current?.contains(e.relatedTarget as Node)) {
      setIsDragging(false);
    }
  };

  const handleDeleteDoc = async (docId: string) => {
    if (!confirm(`ลบเอกสาร "${docId}" ออกจากระบบ?`)) return;
    try {
      await deleteDocument(docId);
      loadDocs();
    } catch (err: unknown) {
      alert(`Delete failed: ${err instanceof Error ? err.message : err}`);
    }
  };

  const handleViewDoc = useCallback(async (docId: string) => {
    setViewLoading(true);
    try {
      const content = await getDocumentContent(docId);
      setViewingDoc(content);
    } catch (err) {
      alert(`Cannot load document: ${err instanceof Error ? err.message : err}`);
    } finally {
      setViewLoading(false);
    }
  }, []);

  const getFileIcon = (docId: string) => {
    if (/csv/i.test(docId)) return <Database size={12} className="text-emerald-400" />;
    if (/md/i.test(docId) || /readme/i.test(docId)) return <FileCode size={12} className="text-amber-400" />;
    if (/json/i.test(docId)) return <FileCode size={12} className="text-cyan-400" />;
    return <File size={12} className="text-indigo-400" />;
  };

  const modeConfig = {
    auto: { label: "Auto", icon: Zap, color: "bg-purple-600", desc: "Agentic routing" },
    rag: { label: "RAG", icon: FileText, color: "bg-blue-600", desc: "Document search" },
    sql: { label: "SQL", icon: Database, color: "bg-green-600", desc: "Database query" },
  };

  return (
    <div className="flex h-screen bg-slate-900 text-slate-100 overflow-hidden">

      {/* ── Sidebar: RAG Documents ── */}
      <div
        className={`${
          showSidebar ? "w-72" : "w-0"
        } transition-all duration-300 overflow-hidden bg-slate-800 border-r border-slate-700 flex flex-col flex-shrink-0`}
      >
        {/* Header */}
        <div className="p-3 border-b border-slate-700 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BookOpen size={15} className="text-indigo-400" />
            <h2 className="font-semibold text-slate-100 text-sm">Knowledge Base</h2>
            {documents.length > 0 && (
              <span className="text-xs bg-indigo-500/20 text-indigo-300 px-1.5 py-0.5 rounded-full">
                {documents.length}
              </span>
            )}
          </div>
          <button
            onClick={loadDocs}
            className="text-slate-500 hover:text-slate-300 transition p-1 rounded"
            title="Refresh"
          >
            <RefreshCw size={13} />
          </button>
        </div>

        {/* Drop Zone */}
        <div className="p-3 border-b border-slate-700">
          <div
            ref={dropZoneRef}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            className={`relative rounded-xl border-2 border-dashed transition-all duration-200 ${
              isDragging
                ? "border-indigo-400 bg-indigo-500/10"
                : "border-slate-600 hover:border-indigo-500/50 hover:bg-slate-700/30"
            }`}
          >
            <label className="flex flex-col items-center gap-1.5 px-3 py-4 cursor-pointer">
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center transition ${
                isDragging ? "bg-indigo-500/20" : "bg-slate-700"
              }`}>
                <Upload size={16} className={isDragging ? "text-indigo-400" : "text-slate-400"} />
              </div>
              <div className="text-center">
                <p className="text-xs font-medium text-slate-300">
                  {isDragging ? "วางไฟล์ที่นี่" : "ลากไฟล์มาวาง หรือคลิก"}
                </p>
                <p className="text-xs text-slate-600 mt-0.5">.txt · .md · .csv · .json · .pdf</p>
              </div>
              <input
                type="file"
                accept=".txt,.md,.csv,.json,.pdf"
                multiple
                className="hidden"
                onChange={handleFileInputChange}
              />
            </label>
          </div>

          {/* Upload Queue */}
          {uploadQueue.length > 0 && (
            <div className="mt-2 space-y-1.5">
              {uploadQueue.map((u, i) => (
                <div key={i} className={`flex items-center gap-2 px-2.5 py-2 rounded-lg text-xs ${
                  u.status === "uploading" ? "bg-indigo-500/10 border border-indigo-500/20"
                  : u.status === "done"     ? "bg-emerald-500/10 border border-emerald-500/20"
                  : "bg-red-500/10 border border-red-500/20"
                }`}>
                  {u.status === "uploading" && <Loader2 size={11} className="animate-spin text-indigo-400 flex-shrink-0" />}
                  {u.status === "done"      && <CheckCircle2 size={11} className="text-emerald-400 flex-shrink-0" />}
                  {u.status === "error"     && <AlertCircle size={11} className="text-red-400 flex-shrink-0" />}
                  <span className={`truncate flex-1 ${
                    u.status === "uploading" ? "text-indigo-300"
                    : u.status === "done" ? "text-emerald-300"
                    : "text-red-300"
                  }`}>
                    {u.file}
                  </span>
                  {u.status === "uploading" && <span className="text-slate-500">กำลัง embed...</span>}
                  {u.status === "done"      && <span className="text-emerald-500">{u.chunks} chunks</span>}
                  {u.status === "error"     && (
                    <button onClick={() => setUploadQueue(q => q.filter((_, j) => j !== i))}>
                      <X size={10} className="text-red-400" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Document List */}
        <div className="flex-1 overflow-y-auto p-3 space-y-1.5 scrollbar-thin">
          {documents.length === 0 ? (
            <div className="text-center mt-8 space-y-3 px-4">
              <FileUp size={28} className="mx-auto text-slate-700" />
              <div>
                <p className="text-xs font-medium text-slate-500">ยังไม่มีเอกสาร</p>
                <p className="text-xs text-slate-700 mt-1">
                  อัปโหลดไฟล์เพื่อให้ RAG ตอบคำถามจากเนื้อหาในเอกสาร
                </p>
              </div>
            </div>
          ) : (
            <>
              <p className="text-xs text-slate-600 px-1 mb-2">
                {documents.reduce((s, d) => s + d.chunk_count, 0).toLocaleString()} chunks รวม
              </p>
              {documents.map((doc) => (
                <div
                  key={doc.doc_id}
                  className="flex items-center justify-between p-2.5 bg-slate-700/40 hover:bg-slate-700/70 rounded-lg transition group"
                >
                  <button
                    className="flex items-center gap-2 min-w-0 flex-1 text-left"
                    onClick={() => handleViewDoc(doc.doc_id)}
                    title="คลิกเพื่ออ่านเนื้อหา"
                  >
                    <div className="w-6 h-6 rounded-md bg-slate-700 flex items-center justify-center flex-shrink-0">
                      {getFileIcon(doc.doc_id)}
                    </div>
                    <div className="min-w-0">
                      <div className="font-medium text-slate-200 group-hover:text-indigo-300 truncate text-xs leading-tight transition">
                        {doc.doc_id}
                      </div>
                      <div className="text-xs text-slate-600">
                        {doc.chunk_count} chunks
                      </div>
                    </div>
                  </button>
                  <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition flex-shrink-0">
                    <button
                      onClick={() => handleViewDoc(doc.doc_id)}
                      className="text-slate-500 hover:text-indigo-400 p-1 transition"
                      title="อ่านเนื้อหา"
                    >
                      {viewLoading ? <Loader2 size={12} className="animate-spin" /> : <Eye size={12} />}
                    </button>
                    <button
                      onClick={() => handleDeleteDoc(doc.doc_id)}
                      className="text-slate-500 hover:text-red-400 p-1 transition"
                      title="ลบเอกสาร"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                </div>
              ))}
            </>
          )}
        </div>

        {/* Footer hint */}
        <div className="p-3 border-t border-slate-700">
          <p className="text-xs text-slate-700 text-center">
            เปลี่ยนเป็น mode <span className="text-indigo-400 font-medium">RAG</span> เพื่อถามจากเอกสาร
          </p>
        </div>
      </div>

      {/* ── Main Chat Area ── */}
      <div className="flex-1 flex flex-col min-w-0">

        {/* Glass Topbar */}
        <header className="topbar-glass sticky top-0 z-10 px-4 py-2.5 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowSidebar(!showSidebar)}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs transition ${
                showSidebar
                  ? "text-amber-400 bg-slate-700"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-700"
              }`}
            >
              <PanelLeft size={15} />
            </button>

            {/* Logo */}
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow">
                <Sparkles size={14} className="text-white" />
              </div>
              <div>
                <h1 className="text-sm font-semibold text-slate-100 leading-none">RAG Chatbot</h1>
                <p className="text-xs text-slate-500 leading-none mt-0.5">Gemini · RAG · SQL · Agentic</p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Mode tabs */}
            <div className="flex border-b-0 border border-slate-700 rounded-lg overflow-hidden">
              {(Object.keys(modeConfig) as Mode[]).map((m) => {
                const cfg = modeConfig[m];
                const Icon = cfg.icon;
                const active = mode === m;
                return (
                  <button
                    key={m}
                    onClick={() => setMode(m)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium transition border-r last:border-r-0 border-slate-700 ${
                      active
                        ? "bg-indigo-600 text-white"
                        : "bg-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-700"
                    }`}
                  >
                    <Icon size={12} />
                    {cfg.label}
                  </button>
                );
              })}
            </div>

            {/* Stream toggle */}
            <div
              onClick={() => setUseStream(!useStream)}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs text-slate-400 hover:text-slate-200 hover:bg-slate-700 cursor-pointer transition select-none"
            >
              <div
                className={`relative w-7 h-3.5 rounded-full transition-colors ${
                  useStream ? "bg-indigo-500" : "bg-slate-600"
                }`}
              >
                <div
                  className={`absolute top-0.5 w-2.5 h-2.5 rounded-full bg-white shadow transition-transform ${
                    useStream ? "translate-x-3.5" : "translate-x-0.5"
                  }`}
                />
              </div>
              Stream
            </div>

            {/* Health indicator */}
            {health && (
              <div
                className={`flex items-center gap-1 text-xs px-2 py-1 rounded-md ${
                  health.status === "ok"
                    ? "text-emerald-400 bg-emerald-400/10"
                    : "text-red-400 bg-red-400/10"
                }`}
              >
                {health.status === "ok" ? (
                  <CheckCircle2 size={12} />
                ) : (
                  <AlertCircle size={12} />
                )}
                DB
              </div>
            )}
          </div>
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-6 space-y-5 scrollbar-thin">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full min-h-[60vh] space-y-6 fade-in">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/25">
                <Sparkles size={28} className="text-white" />
              </div>
              <div className="text-center">
                <h2 className="text-xl font-semibold text-slate-100">RAG Chatbot Workshop</h2>
                <p className="text-sm text-slate-400 mt-1">Upload documents and ask questions in Thai or English</p>
              </div>
              <div className="grid grid-cols-3 gap-3 max-w-xl">
                {(Object.keys(modeConfig) as Mode[]).map((m) => {
                  const cfg = modeConfig[m];
                  const Icon = cfg.icon;
                  return (
                    <button
                      key={m}
                      onClick={() => setMode(m)}
                      className={`flex flex-col items-center gap-2 p-4 rounded-xl border transition ${
                        mode === m
                          ? "border-indigo-500 bg-indigo-500/10 text-indigo-300"
                          : "border-slate-700 bg-slate-800/60 text-slate-400 hover:border-slate-600 hover:text-slate-200"
                      }`}
                    >
                      <Icon size={20} />
                      <span className="text-xs font-semibold">{cfg.label}</span>
                      <span className="text-xs text-slate-500 text-center leading-tight">{cfg.desc}</span>
                    </button>
                  );
                })}
              </div>
              <p className="text-xs text-slate-600">เลือก mode แล้วเริ่มถามได้เลย</p>
            </div>
          )}

          {messages.map((msg, i) => (
            <MessageBubble key={i} msg={msg} />
          ))}

          {/* Typing indicator */}
          {(loading || (streaming && messages[messages.length - 1]?.content === "")) && (
            <div className="flex gap-3 items-start message-enter">
              <div className="w-7 h-7 rounded-full bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Bot size={14} className="text-indigo-400" />
              </div>
              <div className="bg-slate-800 border border-slate-700 rounded-2xl px-4 py-3">
                <div className="flex items-center gap-1">
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 text-red-400 text-sm px-4 py-3 bg-red-400/10 border border-red-400/20 rounded-xl">
              <AlertCircle size={15} />
              {error}
            </div>
          )}

          <div ref={chatEndRef} />
        </div>

        {/* Input Area */}
        <div className="border-t border-slate-700 bg-slate-800/80 backdrop-blur-sm p-4">
          <div className="max-w-3xl mx-auto">
            <div className="flex gap-2 items-end">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={
                  mode === "sql"
                    ? "ถามเกี่ยวกับข้อมูลในฐานข้อมูล เช่น ผู้สมัคร นักศึกษา สินค้า..."
                    : mode === "rag"
                    ? "ถามเกี่ยวกับเอกสารที่ upload..."
                    : "ถามอะไรก็ได้ — ระบบจะเลือก source ที่เหมาะสม..."
                }
                rows={1}
                className="flex-1 resize-none bg-slate-700 border border-slate-600 rounded-xl px-4 py-3 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition scrollbar-thin"
                disabled={loading || streaming}
                style={{ maxHeight: "120px", overflowY: "auto" }}
                onInput={(e) => {
                  const t = e.currentTarget;
                  t.style.height = "auto";
                  t.style.height = Math.min(t.scrollHeight, 120) + "px";
                }}
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || loading || streaming}
                className="px-4 py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl disabled:opacity-40 disabled:cursor-not-allowed transition flex items-center gap-1.5 font-medium text-sm flex-shrink-0"
              >
                {loading || streaming ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <Send size={16} />
                )}
              </button>
            </div>
            <div className="flex items-center justify-between mt-2 px-1">
              <span className="text-xs text-slate-600">
                <span className="text-slate-500 font-medium">{modeConfig[mode].label}</span>
                {" — "}{modeConfig[mode].desc}
              </span>
              <span className="text-xs text-slate-700">Enter ส่ง · Shift+Enter ขึ้นบรรทัด</span>
            </div>
          </div>
        </div>
      </div>

      {/* ── Doc Viewer Modal ── */}
      {viewingDoc && (
        <DocViewerModal doc={viewingDoc} onClose={() => setViewingDoc(null)} />
      )}
    </div>
  );
}

/* ─── Doc Viewer Modal ──────────────────────────────────────── */
function DocViewerModal({ doc, onClose }: { doc: DocContent; onClose: () => void }) {
  const [tab, setTab] = useState<"full" | "chunks">("full");
  const [hasFile, setHasFile] = useState(false);

  // Close on Escape key
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  // Check if original file exists
  useEffect(() => {
    hasOriginalFile(doc.doc_id).then(setHasFile).catch(() => setHasFile(false));
  }, [doc.doc_id]);

  const openOriginal = () => {
    window.open(getOriginalFileUrl(doc.doc_id), "_blank");
  };

  const lineCount = doc.full_text.split("\n").length;
  const charCount = doc.full_text.length;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />

      {/* Panel */}
      <div className="relative z-10 w-full max-w-4xl h-[85vh] bg-slate-900 border border-slate-700 rounded-2xl flex flex-col shadow-2xl shadow-black/60 fade-in">

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-700 flex-shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center flex-shrink-0">
              <FileText size={15} className="text-indigo-400" />
            </div>
            <div className="min-w-0">
              <h2 className="text-sm font-semibold text-slate-100 truncate">{doc.doc_id}</h2>
              <p className="text-xs text-slate-500">
                {doc.chunk_count} chunks · {charCount.toLocaleString()} chars · {lineCount.toLocaleString()} lines
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {hasFile && (
              <button
                onClick={openOriginal}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-medium transition"
                title="เปิดไฟล์ต้นฉบับ"
              >
                <ExternalLink size={12} />
                เปิดไฟล์ต้นฉบับ
              </button>
            )}
            <button
              onClick={onClose}
              className="text-slate-500 hover:text-slate-200 hover:bg-slate-700 p-1.5 rounded-lg transition"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-slate-700 px-5 flex-shrink-0">
          <button
            onClick={() => setTab("full")}
            className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 transition ${
              tab === "full"
                ? "border-indigo-400 text-indigo-300"
                : "border-transparent text-slate-500 hover:text-slate-300"
            }`}
          >
            <FileText size={12} /> เนื้อหาทั้งหมด
          </button>
          <button
            onClick={() => setTab("chunks")}
            className={`flex items-center gap-1.5 px-3 py-2 text-xs font-medium border-b-2 transition ${
              tab === "chunks"
                ? "border-indigo-400 text-indigo-300"
                : "border-transparent text-slate-500 hover:text-slate-300"
            }`}
          >
            <Layers size={12} /> Chunks ({doc.chunk_count})
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto scrollbar-thin p-5">
          {tab === "full" ? (
            <pre className="text-xs text-slate-300 whitespace-pre-wrap leading-relaxed font-sans">
              {doc.full_text}
            </pre>
          ) : (
            <div className="space-y-3">
              {doc.chunks.map((chunk) => (
                <div key={chunk.chunk_index} className="border border-slate-700 rounded-xl overflow-hidden">
                  <div className="flex items-center gap-2 px-3 py-2 bg-slate-800 border-b border-slate-700">
                    <span className="text-xs font-mono text-indigo-400 bg-indigo-500/10 px-1.5 py-0.5 rounded">
                      #{chunk.chunk_index + 1}
                    </span>
                    <span className="text-xs text-slate-600">{chunk.content.length} chars</span>
                  </div>
                  <pre className="text-xs text-slate-300 whitespace-pre-wrap leading-relaxed p-3 font-sans">
                    {chunk.content}
                  </pre>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-slate-700 flex items-center justify-between flex-shrink-0">
          <span className="text-xs text-slate-500">
            {doc.filename !== doc.doc_id
              ? <span>ไฟล์ต้นฉบับ: <span className="text-slate-300 font-medium">{doc.filename}</span></span>
              : <span className="text-slate-600">ไม่มีข้อมูลชื่อไฟล์ต้นฉบับ</span>
            }
            {!hasFile && <span className="ml-2 text-slate-700">(ไม่มีไฟล์ต้นฉบับ — ingest ผ่าน API โดยตรง)</span>}
          </span>
          <div className="flex items-center gap-2">
            {hasFile && (
              <button
                onClick={openOriginal}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg transition"
              >
                <ExternalLink size={11} />
                ดาวน์โหลดไฟล์
              </button>
            )}
            <button
              onClick={onClose}
              className="text-xs px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded-lg transition"
            >
              ปิด
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── Message Bubble ──────────────────────────────────────────── */
function MessageBubble({ msg }: { msg: Message }) {
  const [showTrace, setShowTrace] = useState(false);
  const [showCitations, setShowCitations] = useState(false);
  const isUser = msg.role === "user";

  const modeBadge: Record<string, string> = {
    sql:  "bg-emerald-500/15 text-emerald-400 border-emerald-500/20",
    rag:  "bg-blue-500/15 text-blue-400 border-blue-500/20",
    auto: "bg-violet-500/15 text-violet-400 border-violet-500/20",
  };

  return (
    <div className={`flex gap-3 message-enter ${ isUser ? "justify-end" : "justify-start" }`}>

      {/* Bot avatar */}
      {!isUser && (
        <div className="w-7 h-7 rounded-full bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center flex-shrink-0 mt-0.5">
          <Bot size={14} className="text-indigo-400" />
        </div>
      )}

      <div className={`max-w-2xl ${ isUser ? "" : "flex-1" }`}>
        {/* Bubble */}
        <div
          className={`rounded-2xl px-4 py-3 text-sm ${
            isUser
              ? "bg-indigo-600 text-white rounded-br-sm"
              : "bg-slate-800 border border-slate-700 text-slate-100 rounded-bl-sm"
          }`}
        >
          {isUser ? (
            <span className="whitespace-pre-wrap">{msg.content}</span>
          ) : (
            <div className="prose-chat">
              <ReactMarkdown>{msg.content || ""}</ReactMarkdown>
            </div>
          )}
        </div>

        {/* Footer: meta info */}
        {!isUser && (
          <div className="mt-1.5 px-1 space-y-1.5">
            {/* Mode badge + latency */}
            <div className="flex items-center gap-2 flex-wrap">
              {msg.mode && (
                <span className={`inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded border ${
                  modeBadge[msg.mode] ?? modeBadge.auto
                }`}>
                  {msg.mode === "sql" ? <Database size={10} /> : msg.mode === "rag" ? <FileText size={10} /> : <Zap size={10} />}
                  {msg.mode.toUpperCase()}
                </span>
              )}
              {msg.latencyMs != null && (
                <span className="inline-flex items-center gap-1 text-xs text-slate-600">
                  <Clock size={10} /> {Math.round(msg.latencyMs)}ms
                </span>
              )}
            </div>

            {/* Citations */}
            {msg.citations && msg.citations.length > 0 && (
              <div>
                <button
                  onClick={() => setShowCitations(!showCitations)}
                  className="flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300 transition"
                >
                  <FileText size={11} />
                  {msg.citations.length} source(s)
                  {showCitations ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                </button>
                {showCitations && (
                  <div className="mt-1 space-y-1 fade-in">
                    {msg.citations.map((c) => (
                      <div key={c.id} className="text-xs bg-slate-800 border border-indigo-500/20 rounded-lg p-2.5">
                        <div className="font-semibold text-indigo-300">{c.title || c.id}</div>
                        {c.content && (
                          <div className="mt-0.5 text-slate-400 line-clamp-2">{c.content}</div>
                        )}
                        {c.cosine_similarity != null && (
                          <div className="text-slate-600 mt-0.5">
                            Similarity: {(c.cosine_similarity * 100).toFixed(1)}%
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Tool trace */}
            {msg.toolTrace && msg.toolTrace.length > 0 && (
              <div>
                <button
                  onClick={() => setShowTrace(!showTrace)}
                  className="flex items-center gap-1 text-xs text-slate-600 hover:text-amber-400 transition"
                >
                  <Code2 size={11} />
                  Tool trace ({msg.toolTrace.length})
                  {showTrace ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                </button>
                {showTrace && (
                  <pre className="mt-1 text-xs bg-slate-900 border border-slate-700 rounded-lg p-3 overflow-x-auto max-h-48 text-slate-400 font-mono scrollbar-thin fade-in">
                    {JSON.stringify(msg.toolTrace, null, 2)}
                  </pre>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* User avatar */}
      {isUser && (
        <div className="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center flex-shrink-0 mt-0.5">
          <User size={14} className="text-white" />
        </div>
      )}
    </div>
  );
}
