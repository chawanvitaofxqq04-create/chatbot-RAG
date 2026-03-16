import { useState, useRef, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import computerImg from './assets/computer.jpg'; // ตั้งชื่อตัวแปรที่ชอบ

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
  Send, Bot, User, FileUp, Trash2, Database, FileText, Zap, Loader2,
  ChevronDown, ChevronUp, AlertCircle, CheckCircle2, Clock, Sparkles,
  PanelLeft, Code2, Upload, File, FileCode, RefreshCw, X, BookOpen,
  Eye, ExternalLink, Layers,
} from "lucide-react";

// 🌟 อัปเกรด: เพิ่ม LineChart และ Line เข้ามาเพื่อรองรับกราฟเส้น
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip,
  Legend, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line
} from "recharts";

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
  const [sessionId, setSessionId] = useState(generateSessionId);
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
  // 1. เพิ่ม State สำหรับเก็บประวัติและ Session ปัจจุบัน
  const [currentSessionId, setCurrentSessionId] = useState<string | number | null>(null);
  const [history, setHistory] = useState<any[]>([]);

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

    // 🌟🌟 ท่าไม้ตาย (Optimistic Update): ยัดชื่อแชทเข้า Sidebar ทันทีโดยไม่ง้อ Backend!
    setHistory((prev) => {
      // เช็คว่ามีแชทนี้โชว์ใน Sidebar หรือยัง
      const isExist = prev.find((h) => h.id === sessionId);
      if (isExist) return prev; // ถ้ามีแล้ว ไม่ต้องเพิ่มใหม่

      // ถ้าเป็นแชทใหม่ ให้เอาข้อความแรกที่พิมพ์ไปทำเป็นหัวข้อแชท (ตัดคำถ้าเกิน 30 ตัวอักษร)
      const newTitle = text.length > 30 ? text.slice(0, 30) + "..." : text;
      return [{ id: sessionId, title: newTitle }, ...prev];
    });

    // ไฮไลต์ให้รู้ว่าตอนนี้กำลังคุยอยู่ในแชทนี้นะ
    setCurrentSessionId(sessionId);

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

          // ดึงประวัติจากหลังบ้านเพื่อ Sync ข้อมูลให้ชัวร์อีก 1 รอบตอน AI ตอบเสร็จ
          fetchSessions();
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

        // ดึงประวัติเพื่อ Sync ข้อมูล
        fetchSessions();
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

  // 🌐 ฟังก์ชันสำหรับดึงข้อความเก่าจาก Backend
  const fetchMessages = async (sessionId: string | number) => {
    try {
      // ⚠️ ตรงนี้ต้องเปลี่ยน URL ให้ตรงกับ FastAPI ของนายนะ (เช่น http://localhost:8000)
      const response = await fetch(`http://localhost:8000/sessions/${sessionId}/messages`);

      if (!response.ok) {
        throw new Error("ดึงข้อมูลไม่สำเร็จ");
      }

      const data = await response.json(); // หรือ response.json() ขึ้นอยู่กับ library ที่ใช้
      return data; // ควรจะได้ Array ของข้อความ [{role: 'user', content: '...'}, ...]
    } catch (error) {
      console.error("Error fetching messages:", error);
      return []; // ถ้าพลาดให้ส่ง Array ว่างกลับไปก่อน หน้าจอจะได้ไม่ขาว
    }
  };

  const fetchSessions = async () => {
    try {
      const response = await fetch(`http://localhost:8000/sessions`);
      if (!response.ok) throw new Error("ดึงประวัติไม่สำเร็จ");
      const data = await response.json();
      setHistory(data);
    } catch (error) {
      console.error("Error fetching sessions:", error);
    }
  };

  // 3. ส่วนของ useEffect (สั่งให้ทำงานตอนเปิดแอป)
  useEffect(() => {
    fetchSessions();
  }, []);

  // 🔵 แก้ไขพารามิเตอร์ให้รองรับทั้ง string และ number พร้อมจัดการข้อผิดพลาด
  const handleSelectHistory = async (sessionId: string | number) => {
    try {
      // 1. ระบุ Session ID ปัจจุบันที่กำลังดูอยู่
      setCurrentSessionId(sessionId);

      // 2. เรียก API ไปดึงข้อความเก่า (ใส่ Loading สักนิดจะดีมาก)
      const oldMessages = await fetchMessages(sessionId);

      // 3. นำข้อความที่ได้มาเซ็ตลงใน State ของหน้าแชท
      if (oldMessages) {
        setMessages(oldMessages);
      }
    } catch (error) {
      // 🔴 จัดการกรณี API พัง หรือหา Session ไม่เจอ
      console.error("ไม่สามารถดึงข้อมูลแชทเก่าได้:", error);
      alert("เกิดข้อผิดพลาดในการโหลดประวัติการสนทนา");
    }
  };

  const handleNewChat = () => {
    // 1. หยุด Stream ที่อาจจะค้างอยู่
    if (cancelStreamRef.current) {
      cancelStreamRef.current();
      cancelStreamRef.current = null;
    }

    // 2. ปลดล็อกปุ่มส่งข้อความ (รีเซ็ตสถานะโหลด)
    setLoading(false);
    setStreaming(false);
    setError(null);

    // 3. เริ่ม Session ใหม่และล้างหน้าจอ
    setCurrentSessionId(null);
    setSessionId(generateSessionId());
    setMessages([]);

    // 4. (แถม) โฟกัสช่องพิมพ์อัตโนมัติ จะได้พิมพ์ต่อได้เลย
    setTimeout(() => inputRef.current?.focus(), 100);
  };

  return (
    <div className="flex h-screen bg-[#1a237e] text-white overflow-hidden">

      {/* 🔵 Sidebar (โทนสีน้ำเงินเข้ม) */}
      <div className={`${showSidebar ? "w-72" : "w-0"} transition-all duration-300 overflow-hidden bg-[#1a237e] border-r border-[#0f133d] flex flex-col flex-shrink-0 shadow-xl z-20`}>

        {/* Header ของ Sidebar */}
        <div className="p-3 border-b border-[#2c337d] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BookOpen size={15} className="text-indigo-300" />
            <h2 className="font-semibold text-white text-sm">Knowledge Base</h2>
            {documents.length > 0 && (
              <span className="text-xs bg-indigo-500/20 text-white px-1.5 py-0.5 rounded-full">
                {documents.length}
              </span>
            )}
          </div>
          <button onClick={loadDocs} className="text-indigo-300 hover:text-white hover:bg-[#2c337d]/50 transition p-1 rounded" title="Refresh">
            <RefreshCw size={13} />
          </button>
        </div>

        {/* โซน Dropzone ลากไฟล์ */}
        {/* ☁️ โซน Dropzone: ปรับเส้นประให้สว่างและดู Modern ขึ้น */}
        <div className="p-3 border-b border-[#2c337d]">
          <div
            ref={dropZoneRef}
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            /* ✨ ปรับเส้นประเป็น border-indigo-300/50 เพื่อให้สว่างขึ้นชัดเจน */
            className={`relative rounded-xl border-2 border-dashed transition-all duration-300 ${isDragging
              ? "border-white bg-white/20 shadow-[0_0_15px_rgba(165,180,252,0.4)] scale-[1.02]"
              : "border-indigo-300/40 bg-white/5 hover:border-indigo-200 hover:bg-white/10"
              }`}
          >
            <label className="flex flex-col items-center gap-2 px-3 py-5 cursor-pointer">
              {/* ✨ ไอคอนอัปโหลด: ปรับให้สว่างและดูเด่น */}
              <div className={`w-9 h-9 rounded-xl flex items-center justify-center transition-all duration-300 ${isDragging ? "bg-white text-[#1a237e]" : "bg-indigo-500/20 text-indigo-200 border border-indigo-400/30"
                }`}>
                <Upload size={18} className={isDragging ? "animate-bounce" : ""} />
              </div>

              <div className="text-center">
                <p className="text-xs font-semibold text-white tracking-wide">
                  {isDragging ? "ปล่อยเพื่ออัปโหลด" : "ลากไฟล์มาวาง หรือคลิก"}
                </p>
                <p className="text-[10px] text-indigo-300/80 mt-1 font-medium italic">
                  .txt · .md · .csv · .json · .pdf
                </p>
              </div>
              <input type="file" accept=".txt,.md,.csv,.json,.pdf" multiple className="hidden" onChange={handleFileInputChange} />
            </label>
          </div>

          {/* 🟢 ส่วนที่ต้องเพิ่ม: ประวัติการแชท (Chat History) */}
          <div className="p-3 border-b border-[#2c337d] bg-[#151c66]">
            <div className="flex items-center justify-between mb-2 px-1">
              <h3 className="text-xs font-semibold text-indigo-200 flex items-center gap-1.5">
                <Clock size={13} /> ประวัติการค้นหา
              </h3>
              {/* ปุ่มล้างแชทเพื่อเริ่มคุยใหม่ */}
              <button
                onClick={handleNewChat}
                className="text-white hover:bg-indigo-500 bg-indigo-600 px-2 py-0.5 rounded text-[10px] transition"
              >
                + แชทใหม่
              </button>
            </div>

            <div className="space-y-1 max-h-40 overflow-y-auto pr-1 scrollbar-thin">
              {history.length === 0 ? (
                <p className="text-[10px] text-indigo-400/60 italic px-1">ยังไม่มีประวัติ...</p>
              ) : (
                history.map((chat) => (
                  <button
                    key={chat.id}
                    onClick={() => handleSelectHistory(chat.id)}
                    className={`w-full text-left px-2 py-1.5 rounded-md text-xs truncate transition-all ${currentSessionId === chat.id
                      ? "bg-indigo-500 text-white font-medium"
                      : "text-indigo-200 hover:bg-[#2c337d] hover:text-white"
                      }`}
                  >
                    {chat.title}
                  </button>
                ))
              )}
            </div>
          </div>
          {/* 🟢 จบส่วนที่เพิ่ม */}

          {/* คิวอัปโหลด */}
          {uploadQueue.length > 0 && (
            <div className="mt-2 space-y-1.5">
              {uploadQueue.map((u, i) => (
                <div key={i} className={`flex items-center gap-2 px-2.5 py-2 rounded-lg text-xs ${u.status === "uploading" ? "bg-white/10 border border-white/20" : u.status === "done" ? "bg-emerald-500/20 border border-emerald-500/30" : "bg-red-500/20 border border-red-500/30"}`}>
                  {u.status === "uploading" && <Loader2 size={11} className="animate-spin text-white flex-shrink-0" />}
                  {u.status === "done" && <CheckCircle2 size={11} className="text-emerald-400 flex-shrink-0" />}
                  {u.status === "error" && <AlertCircle size={11} className="text-red-400 flex-shrink-0" />}
                  <span className="truncate flex-1 text-white">{u.file}</span>
                  {u.status === "error" && <button onClick={() => setUploadQueue(q => q.filter((_, j) => j !== i))}><X size={10} className="text-red-300" /></button>}
                </div>
              ))}
            </div>
          )}
        </div>


        {/* รายการไฟล์ที่อัปโหลดแล้ว */}
        {/* 🔵 รายการไฟล์ที่อัปโหลดแล้ว: ปรับให้ "สว่าง" และเด่นขึ้น */}
        <div className="flex-1 overflow-y-auto p-3 space-y-2 scrollbar-thin">
          {documents.map((doc) => (
            /* ✨ 1. ตัวกรอบ: ใช้ bg-white/10 (ขาวโปร่งแสง) และ border-indigo-400/50 (ฟ้าสว่าง) */
            <div key={doc.doc_id} className="flex items-center justify-between p-3 bg-white/10 border border-indigo-400/40 hover:border-indigo-400 hover:bg-white/20 rounded-xl transition-all duration-200 group shadow-lg shadow-indigo-900/20">
              <button className="flex items-center gap-3 min-w-0 flex-1 text-left" onClick={() => handleViewDoc(doc.doc_id)}>

                {/* ✨ 2. กล่องไอคอน: ใช้สีฟ้าสว่างตัดกับพื้นหลัง */}
                <div className="w-8 h-8 rounded-lg bg-indigo-500/30 flex items-center justify-center flex-shrink-0 border border-indigo-400/20">
                  <FileText size={14} className="text-indigo-200" />
                </div>

                <div className="min-w-0">
                  {/* ⚪️ 3. ชื่อไฟล์: สีขาวชัดเจน */}
                  <div className="font-semibold text-white truncate text-xs tracking-wide">{doc.doc_id}</div>
                  {/* 🔵 4. จำนวน Chunks: สีฟ้าอ่อน (Indigo-300) */}
                  <div className="text-[10px] text-indigo-300 font-medium mt-0.5">{doc.chunk_count} chunks</div>
                </div>
              </button>

              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
                <button onClick={() => handleDeleteDoc(doc.doc_id)} className="text-indigo-200 hover:text-red-400 p-1.5 transition-colors">
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Main Chat Area ── */}
      {/* ⬜️ ── Main Chat Area (โซนสีขาวสะอาดตา) ── */}
      <div className="flex-1 flex flex-col min-w-0 bg-white">

        {/* Header แชท */}
        {/* 🔵 Header แชท: เปลี่ยนเป็นสีน้ำเงินเข้ม #1a237e และขอบ Medium Blue */}
        <header className="sticky top-0 z-10 px-4 py-2.5 flex items-center justify-between gap-3 bg-[#1a237e] border-b border-[#2c337d] shadow-md">
          <div className="flex items-center gap-3">
            {/* ปุ่มเปิด Sidebar: สีฟ้าอ่อน */}
            <button onClick={() => setShowSidebar(!showSidebar)} className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs text-indigo-300 hover:text-white hover:bg-[#2c337d] transition-colors">
              <PanelLeft size={15} />
            </button>
            <div className="flex items-center gap-2">
              {/* กรอบโลโก้: มีรูปคอมพิวเตอร์ และขอบจางๆ */}
              <div className="w-7 h-7 rounded-lg bg-[#0f133d] flex items-center justify-center shadow-sm overflow-hidden border border-[#2c337d]">
                <img
                  src={computerImg}
                  alt="Logo"
                  className="w-full h-full object-cover"
                />
              </div>
              <div>
                {/* หัวข้อ: สีขาวสะอาด */}
                <h1 className="text-sm font-semibold text-white leading-none">RAG Chatbot</h1>
                {/* คำบรรยาย: สีฟ้าอ่อน indigo-300 */}
                <p className="text-xs text-indigo-300 leading-none mt-0.5">Gemini · RAG · SQL · Agentic</p>
              </div>
            </div>
          </div>

          {/* ── ฝั่งขวาของ Header ── */}
          <div className="flex items-center gap-2">
            {/* กล่อง Mode: พื้นหลังน้ำเงินเข้ม ขอบ Medium Blue */}
            <div className="flex border border-[#2c337d] rounded-lg overflow-hidden bg-[#0f133d]">
              {(Object.keys(modeConfig) as Mode[]).map((m) => {
                const cfg = modeConfig[m];
                const Icon = cfg.icon;
                return (
                  <button
                    key={m}
                    onClick={() => setMode(m)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium transition border-r last:border-r-0 border-[#2c337d] ${mode === m ? "bg-indigo-600 text-white" : "text-indigo-200 hover:bg-[#2c337d]"
                      }`}
                  >
                    <Icon size={12} /> {cfg.label}
                  </button>
                );
              })}
            </div>

            {/* 🟢 สัญลักษณ์ DB Status: ปรับเป็นโทนเรืองแสงบนพื้นมืด */}
            {health && (
              <div
                className={`flex items-center gap-1 text-[10px] px-2.5 py-1.5 rounded-md border shadow-sm ${health.status === "ok"
                  ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
                  : "bg-red-500/20 text-red-400 border-red-500/30"
                  }`}
                title={health.status === "ok" ? "Database Connected" : "Database Error"}
              >
                {health.status === "ok" ? (
                  <CheckCircle2 size={12} className="text-emerald-400" />
                ) : (
                  <AlertCircle size={12} className="text-red-400" />
                )}
                <span className="font-bold uppercase tracking-wide">DB</span>
              </div>
            )}
          </div>
        </header>

        {/* พื้นที่แชทหลัก */}
        <div className="flex-1 overflow-y-auto px-4 py-6 space-y-5 scrollbar-thin">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full min-h-[60vh] space-y-6 fade-in">
              <div className="text-center">
                <h2 className="text-xl font-semibold text-slate-900">ระบบสอบถามข้อมูลเอกสาร</h2>
                <p className="text-sm text-slate-500 mt-1">อัปโหลดเอกสารที่เมนูด้านซ้าย หรือพิมพ์คำถามเพื่อเริ่มต้นใช้งาน</p>
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <MessageBubble key={i} msg={msg} />
          ))}

          {/* 🔵 ส่วน Loading: ปรับสีเป็นโทนน้ำเงินเข้มให้คุมโทน */}
          {loading && (
            <div className="flex gap-3 items-start message-enter">
              {/* ไอคอนบอท: เปลี่ยนจากม่วงเป็นพื้นน้ำเงินจางๆ ไอคอนน้ำเงินเข้ม */}
              <div className="w-7 h-7 rounded-full bg-[#1a237e]/10 border border-[#2c337d]/30 flex items-center justify-center mt-0.5 shadow-sm">
                <Bot size={14} className="text-[#1a237e]" />
              </div>

              {/* กล่อง Loading: เปลี่ยนจากเทาดำเป็นสีขาวขอบน้ำเงิน (หรือจะใช้ bg-[#1a237e] ก็ได้ถ้าชอบเข้มๆ) */}
              <div className="bg-white border border-[#2c337d] rounded-2xl px-4 py-3 shadow-sm">
                <Loader2 size={16} className="animate-spin text-[#1a237e]" />
              </div>
            </div>
          )}

          <div ref={chatEndRef} />
        </div>

        {/* กล่องพิมพ์ข้อความ */}
        {/* ⌨️ กล่องพิมพ์ข้อความ: ปรับตัวหนังสือข้างในเป็นสีดำ (text-black) */}
        <div className="border-t border-[#2c337d] bg-[#1a237e]/95 backdrop-blur-sm p-4">
          <div className="max-w-3xl mx-auto flex gap-2 items-end">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="พิมพ์คำถาม หรือสั่งดึงข้อมูล..."
              /* ✨ ปรับ text-black (ตอนพิมพ์) และ placeholder-slate-600 (ตอนยังไม่พิมพ์) ให้เข้มขึ้น */
              className="flex-1 resize-none bg-white border border-[#3949ab] rounded-xl px-4 py-3 text-sm text-black placeholder-slate-600 focus:outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400 shadow-sm font-medium"
              style={{ maxHeight: "120px" }}
            />
            {/* 🔵 ปุ่มส่ง: ใช้สีน้ำเงินเข้มให้เข้ากับธีมหลัก */}
            {/* 🔵 ปุ่มส่ง: สีน้ำเงินเดิม + ขอบขาวสว่าง + เอฟเฟกต์ Glow */}
            {/* 🔵 ปุ่มส่ง: เอาขอบขาวหนาและ Glow ออก ใช้ขอบสีฟ้าอ่อนจางๆ เพื่อให้ดูคลีนและเข้าชุดกัน */}
            <button
              onClick={handleSend}
              /* ✨ เอา border-2 border-white, shadow-*, hover:shadow-* ออก
                 เพิ่ม border border-indigo-300/40 เพื่อให้ขอบอ่อนโยนลง
                 ปรับสี Hover */
              className="px-4 py-3 bg-[#1a237e] hover:bg-indigo-600 text-white rounded-xl transition-all duration-300 border border-indigo-300/40 hover:border-indigo-300 active:scale-95 flex items-center justify-center shadow-sm"
            >
              <Send size={16} className="text-white" />
            </button>
          </div>
        </div>
      </div>
      {viewingDoc && <DocViewerModal doc={viewingDoc} onClose={() => setViewingDoc(null)} />}
    </div>
  );
}

/* ─── 📊 Data Chart Component (เวอร์ชันแก้ไขเออร์เรอร์แล้ว) ─── */
const MY_CUSTOM_COLORS = ['#818cf8', '#8e71ffff', '#f472b6', '#2dd4bf', '#fbbf24', '#60a5fa'];

function DataChart({ data, type = "bar" }: { data: any[], type?: string }) {
  if (!data || data.length === 0) return null;

  const keys = Object.keys(data[0]);
  const xKey = keys.find(k => typeof data[0][k] === 'string') || keys[0];
  const yKey = keys.find(k => typeof data[0][k] === 'number' || !isNaN(Number(data[0][k]))) || keys[1];

  if (!xKey || !yKey || xKey === yKey) return null;

  const formattedData = data.map(item => ({
    ...item,
    [yKey]: Number(item[yKey])
  }));

  const isPie = type.toLowerCase() === 'pie';
  const isLine = type.toLowerCase() === 'line';

  return (
    <div className="h-64 w-full mt-4 bg-slate-900 border border-slate-700 rounded-xl p-4 overflow-hidden fade-in shadow-lg">
      <div className="text-xs text-slate-400 mb-2 font-medium flex items-center gap-1.5">
        <Zap size={12} className="text-amber-400" />
        {isPie ? 'Pie Chart' : isLine ? 'Line Chart' : 'Bar Chart'} Generated
      </div>
      <ResponsiveContainer width="100%" height="100%">
        {isPie ? (
          <PieChart>
            <Pie data={formattedData} dataKey={yKey} nameKey={xKey} cx="50%" cy="50%" outerRadius={70} label>
              {/* ✨ แก้ไขจุดนี้: ใช้ MY_CUSTOM_COLORS ให้ตรงกับที่ประกาศไว้ข้างบน */}
              {formattedData.map((_, index) => (
                <Cell key={`cell-${index}`} fill={MY_CUSTOM_COLORS[index % MY_CUSTOM_COLORS.length]} />
              ))}
            </Pie>
            <RechartsTooltip contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', borderRadius: '8px' }} />
            <Legend wrapperStyle={{ fontSize: '12px' }} />
          </PieChart>
        ) : isLine ? (
          <LineChart data={formattedData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
            <XAxis dataKey={xKey} stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
            <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
            <RechartsTooltip contentStyle={{ backgroundColor: '#4088fcff', borderColor: '#334155', borderRadius: '8px' }} />
            <Line type="monotone" dataKey={yKey} stroke="#818cf8" strokeWidth={3} dot={{ r: 4, fill: '#818cf8' }} activeDot={{ r: 6 }} />
          </LineChart>
        ) : (
          <BarChart data={formattedData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
            <XAxis dataKey={xKey} stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
            <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
            <RechartsTooltip contentStyle={{ backgroundColor: '#1e293b', borderColor: '#334155', borderRadius: '8px', color: '#f8fafc' }} cursor={{ fill: '#334155', opacity: 0.4 }} />
            <Bar dataKey={yKey} fill="#818cf8" radius={[4, 4, 0, 0]} maxBarSize={50}>
              {/* ✨ แก้ไขจุดนี้ด้วย: ใช้ MY_CUSTOM_COLORS ให้ถูกต้อง */}
              {formattedData.map((_, index) => (
                <Cell key={`cell-${index}`} fill={MY_CUSTOM_COLORS[index % MY_CUSTOM_COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}

function DocViewerModal({ doc, onClose }: { doc: DocContent; onClose: () => void }) {
  const [tab, setTab] = useState<"full" | "chunks">("full");
  const [hasFile, setHasFile] = useState(false);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  useEffect(() => {
    hasOriginalFile(doc.doc_id).then(setHasFile).catch(() => setHasFile(false));
  }, [doc.doc_id]);

  const openOriginal = () => { window.open(getOriginalFileUrl(doc.doc_id), "_blank"); };
  const lineCount = doc.full_text.split("\n").length;
  const charCount = doc.full_text.length;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div className="relative z-10 w-full max-w-4xl h-[85vh] bg-slate-900 border border-slate-700 rounded-2xl flex flex-col shadow-2xl shadow-black/60 fade-in">
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-700 flex-shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center flex-shrink-0">
              <FileText size={15} className="text-indigo-400" />
            </div>
            <div className="min-w-0">
              <h2 className="text-sm font-semibold text-slate-100 truncate">{doc.doc_id}</h2>
              <p className="text-xs text-slate-500">{doc.chunk_count} chunks · {charCount.toLocaleString()} chars</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {hasFile && (
              <button onClick={openOriginal} className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-medium transition">
                <ExternalLink size={12} /> เปิดไฟล์ต้นฉบับ
              </button>
            )}
            <button onClick={onClose} className="text-slate-500 hover:text-slate-200 p-1.5 rounded-lg transition"><X size={16} /></button>
          </div>
        </div>
        <div className="flex border-b border-slate-700 px-5 flex-shrink-0">
          <button onClick={() => setTab("full")} className={`px-3 py-2 text-xs font-medium border-b-2 transition ${tab === "full" ? "border-indigo-400 text-indigo-300" : "border-transparent text-slate-500"}`}>เนื้อหาทั้งหมด</button>
          <button onClick={() => setTab("chunks")} className={`px-3 py-2 text-xs font-medium border-b-2 transition ${tab === "chunks" ? "border-indigo-400 text-indigo-300" : "border-transparent text-slate-500"}`}>Chunks ({doc.chunk_count})</button>
        </div>
        <div className="flex-1 overflow-y-auto p-5 scrollbar-thin">
          {tab === "full" ? (
            <pre className="text-xs text-slate-300 whitespace-pre-wrap font-sans">{doc.full_text}</pre>
          ) : (
            <div className="space-y-3">
              {doc.chunks.map((chunk) => (
                <div key={chunk.chunk_index} className="border border-slate-700 rounded-xl overflow-hidden">
                  <div className="text-xs font-mono text-indigo-400 bg-slate-800 px-3 py-2">#{chunk.chunk_index + 1}</div>
                  <pre className="text-xs text-slate-300 whitespace-pre-wrap p-3 font-sans">{chunk.content}</pre>
                </div>
              ))}
            </div>
          )}
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
    sql: "bg-emerald-500/15 text-emerald-400 border-emerald-500/20",
    rag: "bg-blue-500/15 text-blue-400 border-blue-500/20",
    auto: "bg-violet-500/15 text-violet-400 border-violet-500/20",
  };

  const parseChartData = (codeStr: string) => {
    try {
      const parsed = JSON.parse(codeStr);
      let chartData = Array.isArray(parsed) ? parsed : parsed.data;
      let chartType = parsed.chart_type || (msg.content.toLowerCase().includes('วงกลม') ? 'pie' : msg.content.toLowerCase().includes('เส้น') ? 'line' : 'bar');
      return Array.isArray(chartData) ? { chartData, chartType } : null;
    } catch (e) { return null; }
  };

  // 🌟 จุดที่แก้: ดักจับและซ่อน JSON เพื่อเอามาวาดกราฟโดยเฉพาะ
  let displayContent = msg.content || "";
  const charts: React.ReactNode[] = [];

  if (!isUser && displayContent) {
    // Regex นี้จะดักจับทั้งแบบที่คลุมมาด้วย ```json และแบบที่โผล่มาดื้อๆ ว่า json{...}
    const jsonRegex = /```json\s*([\s\S]*?)```|json\s*({[\s\S]*?})/g;

    displayContent = displayContent.replace(jsonRegex, (match, codeBlock, rawJson) => {
      const targetJson = codeBlock || rawJson;
      if (targetJson) {
        const chart = parseChartData(targetJson);
        if (chart) {
          // ถ้าเป็นกราฟ เอาไปเก็บใน Array แล้ว "ลบข้อความทิ้ง" (return "")
          charts.push(<DataChart key={charts.length} data={chart.chartData} type={chart.chartType} />);
          return "";
        }
      }
      return match; // ถ้าแปลงไม่ได้ ก็ปล่อยไว้เหมือนเดิม
    });
  }

  return (
    <div className={`flex gap-3 message-enter ${isUser ? "justify-end" : "justify-start"}`}>
      {!isUser && (
        /* 🔵 ไอคอนบอท: เปลี่ยนเป็นพื้นน้ำเงินอ่อน ขอบน้ำเงินจางๆ และไอคอนน้ำเงินเข้ม */
        <div className="w-7 h-7 rounded-full bg-blue-50 border border-blue-100 flex items-center justify-center mt-0.5 shadow-sm">
          <Bot size={14} className="text-[#1a237e]" />
        </div>
      )}
      <div className={`max-w-2xl ${isUser ? "" : "flex-1"}`}>

        {/* 🔵 กล่องข้อความ: ฝั่ง User เป็นน้ำเงินเข้ม (#1a237e) / ฝั่ง Bot เป็นสีขาวสะอาดขอบเทา */}
        <div className={`rounded-2xl px-4 py-3 text-sm shadow-sm ${isUser ? "bg-[#1a237e] text-white rounded-br-sm" : "bg-white border border-slate-200 text-slate-900 rounded-bl-sm"}`}>
          {isUser ? (
            <span className="whitespace-pre-wrap">{msg.content}</span>
          ) : (
            <div className="prose-chat text-slate-800">
              {!msg.content ? (
                /* 🔵 อนิเมชันจุด Loading: เปลี่ยนเป็นโทนน้ำเงินเข้มโปร่งแสง */
                <div className="flex gap-1.5 py-2 items-center">
                  <span className="w-1.5 h-1.5 bg-[#1a237e]/60 rounded-full animate-bounce [animation-delay:-0.3s]"></span>
                  <span className="w-1.5 h-1.5 bg-[#1a237e]/60 rounded-full animate-bounce [animation-delay:-0.15s]"></span>
                  <span className="w-1.5 h-1.5 bg-[#1a237e]/60 rounded-full animate-bounce"></span>
                </div>
              ) : (
                <>
                  <ReactMarkdown components={{
                    code({ inline, className, children }: any) {
                      return <code className={className}>{children}</code>;
                    }
                  }}>
                    {displayContent}
                  </ReactMarkdown>

                  {/* 🌟 กราฟต่อท้ายข้อความ */}
                  {charts}
                </>
              )}
            </div>
          )}
        </div>

        {!isUser && (
          <div className="mt-1.5 px-1 space-y-1.5">
            <div className="flex items-center gap-2">
              {/* ป้าย Mode (ปรับตาม modeBadge ที่เราแก้เป็นโทนน้ำเงินไว้ก่อนหน้านี้) */}
              {msg.mode && <span className={`text-[10px] px-1.5 py-0.5 rounded border ${modeBadge[msg.mode]}`}>{msg.mode.toUpperCase()}</span>}
              {msg.latencyMs && <span className="text-[10px] text-slate-400 flex items-center gap-1"><Clock size={10} /> {Math.round(msg.latencyMs)}ms</span>}
            </div>

            {msg.citations && msg.citations.length > 0 && (
              <div>
                {/* 🔵 ปุ่ม Sources: เปลี่ยนเป็นสีน้ำเงินเข้ม */}
                <button onClick={() => setShowCitations(!showCitations)} className="text-xs text-[#1a237e] hover:text-indigo-800 transition-colors flex items-center gap-1 font-medium">
                  <FileText size={11} /> {msg.citations.length} sources {showCitations ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                </button>
                {showCitations && (
                  <div className="mt-1 space-y-1">
                    {msg.citations.map((c, idx) => (
                      /* 🔵 กล่องอ้างอิง: พื้นหลังขาวขุ่น หัวข้อน้ำเงินเข้ม */
                      <div key={idx} className="text-[11px] bg-slate-50 border border-slate-200 p-2 rounded-lg shadow-sm">
                        <div className="font-bold text-[#1a237e]">{c.title || c.id}</div>
                        <div className="text-slate-600 line-clamp-2 mt-0.5">{c.content}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {msg.toolTrace && msg.toolTrace.length > 0 && (
              <div>
                <button onClick={() => setShowTrace(!showTrace)} className="text-xs text-slate-400 hover:text-slate-600 transition-colors flex items-center gap-1">
                  <Code2 size={11} /> Tool trace {showTrace ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                </button>
                {/* 💻 Tool trace: คงสีดำไว้เพื่อให้ JSON อ่านง่ายเหมือนเดิมครับ */}
                {showTrace && <pre className="mt-1 text-[10px] bg-slate-900 p-2.5 rounded-xl border border-slate-800 overflow-x-auto text-slate-300 font-mono shadow-inner">{JSON.stringify(msg.toolTrace, null, 2)}</pre>}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}