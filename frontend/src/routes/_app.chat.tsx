import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import {
  PenSquare, Send, Bot, ChevronDown, ChevronUp, Clock, Database, Loader2, Sparkles, MessageCircle,
} from "lucide-react";
import { z } from "zod";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { listConversations, getConversation, type ConvSummary } from "@/lib/api/conversations";
import { streamQuery, type SourceChunk } from "@/lib/api/query";

const chatSearchSchema = z.object({ id: z.string().optional() });

export const Route = createFileRoute("/_app/chat")({
  head: () => ({ meta: [{ title: "Chat — Knowledge Assistant" }] }),
  validateSearch: chatSearchSchema,
  component: ChatPage,
});

/* ── Full neon orbital loader (main chat area) ── */
function NeonLoader() {
  const ring = (inset: number, color: string, glowColor: string, dir: string, dur: string): React.CSSProperties => ({
    position: "absolute", inset, borderRadius: "50%",
    border: "2.5px solid transparent",
    borderTopColor: color,
    borderRightColor: dir === "cw" ? `${glowColor}55` : "transparent",
    borderLeftColor: dir === "ccw" ? `${glowColor}55` : "transparent",
    boxShadow: `0 0 10px ${glowColor}66`,
    animation: `orbit-${dir} ${dur} linear infinite`,
  });
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 22, padding: "60px 0" }}>
      <div style={{ position: "relative", width: 76, height: 76 }}>
        <div style={ring(0,  "#00F2FE", "#00F2FE", "cw",  "1.4s")} />
        <div style={ring(10, "#F62681", "#F62681", "ccw", "0.95s")} />
        <div style={ring(20, "#A78BFA", "#A78BFA", "cw",  "0.62s")} />
        <div style={{
          position: "absolute", inset: 30, borderRadius: "50%",
          background: "linear-gradient(135deg, #00F2FE, #F62681)",
          boxShadow: "0 0 14px rgba(0,242,254,0.70), 0 0 28px rgba(246,38,129,0.50)",
          animation: "loader-pulse 1.1s ease-in-out infinite",
        }} />
      </div>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 9 }}>
        <p style={{ color: "#5B5C8A", fontSize: 11, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase", animation: "loader-text-fade 1.8s ease-in-out infinite" }}>
          Loading Messages
        </p>
        <div style={{ display: "flex", gap: 6 }}>
          {(["#00F2FE", "#A78BFA", "#F62681"] as const).map((col, i) => (
            <div key={col} style={{
              width: 5, height: 5, borderRadius: "50%", background: col,
              boxShadow: `0 0 7px ${col}cc`,
              animation: `loader-pulse 0.9s ease-in-out ${i * 0.22}s infinite`,
            }} />
          ))}
        </div>
      </div>
    </div>
  );
}

/* ── Mini neon loader (sidebar) ── */
function NeonLoaderMini() {
  const ring = (inset: number, color: string, glowColor: string, dir: string, dur: string): React.CSSProperties => ({
    position: "absolute", inset, borderRadius: "50%",
    border: "2px solid transparent",
    borderTopColor: color,
    borderRightColor: dir === "cw" ? `${glowColor}55` : "transparent",
    borderLeftColor: dir === "ccw" ? `${glowColor}55` : "transparent",
    boxShadow: `0 0 7px ${glowColor}55`,
    animation: `orbit-${dir} ${dur} linear infinite`,
  });
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12, padding: "28px 0" }}>
      <div style={{ position: "relative", width: 44, height: 44 }}>
        <div style={ring(0,  "#00F2FE", "#00F2FE", "cw",  "1.4s")} />
        <div style={ring(7,  "#F62681", "#F62681", "ccw", "0.95s")} />
        <div style={ring(14, "#A78BFA", "#A78BFA", "cw",  "0.62s")} />
        <div style={{
          position: "absolute", inset: 18, borderRadius: "50%",
          background: "linear-gradient(135deg, #00F2FE, #F62681)",
          boxShadow: "0 0 8px rgba(0,242,254,0.70)",
          animation: "loader-pulse 1.1s ease-in-out infinite",
        }} />
      </div>
      <div style={{ display: "flex", gap: 4 }}>
        {(["#00F2FE", "#A78BFA", "#F62681"] as const).map((col, i) => (
          <div key={col} style={{
            width: 4, height: 4, borderRadius: "50%", background: col,
            boxShadow: `0 0 5px ${col}cc`,
            animation: `loader-pulse 0.9s ease-in-out ${i * 0.22}s infinite`,
          }} />
        ))}
      </div>
    </div>
  );
}

interface ChatMsg {
  role: "user" | "assistant";
  content: string;
  sources?: SourceChunk[];
  latency_ms?: number;
  chunks_retrieved?: number;
  streaming?: boolean;
}

function ChatPage() {
  const search = Route.useSearch();
  const [convs, setConvs] = useState<ConvSummary[]>([]);
  const [loadingConvs, setLoadingConvs] = useState(true);
  const [activeId, setActiveId] = useState<string | null>(search.id ?? null);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [loadingMsgs, setLoadingMsgs] = useState(false);
  const [isNew, setIsNew] = useState(!search.id);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const msgCache = useRef<Map<string, ChatMsg[]>>(new Map());

  useEffect(() => {
    listConversations()
      .then((list) => {
        setConvs(list);
        if (!activeId && list.length > 0 && !isNew) setActiveId(list[0].id);
        list.slice(0, 5).forEach((c) => {
          if (msgCache.current.has(c.id)) return;
          getConversation(c.id)
            .then((conv) => {
              msgCache.current.set(
                c.id,
                conv.messages.map((m) => ({ role: m.role as "user" | "assistant", content: m.content })),
              );
            })
            .catch(() => {});
        });
      })
      .catch(() => {})
      .finally(() => setLoadingConvs(false));
  }, []);

  useEffect(() => {
    if (!activeId) return;
    if (sending) return;
    if (msgCache.current.has(activeId)) {
      setMessages(msgCache.current.get(activeId)!);
      return;
    }
    setLoadingMsgs(true);
    setMessages([]);
    getConversation(activeId)
      .then((conv) => {
        const loaded = conv.messages.map((m) => ({
          role: m.role as "user" | "assistant",
          content: m.content,
        }));
        msgCache.current.set(activeId, loaded);
        setMessages(loaded);
      })
      .catch(() => toast.error("Failed to load conversation"))
      .finally(() => setLoadingMsgs(false));
  }, [activeId, sending]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    const q = draft.trim();
    if (!q || sending) return;
    setDraft("");
    setSending(true);
    if (isNew) setIsNew(false);

    const userMsg: ChatMsg = { role: "user", content: q };
    setMessages((prev) => {
      const next = [...prev, userMsg];
      if (activeId) msgCache.current.set(activeId, next);
      return next;
    });

    const assistantPlaceholder: ChatMsg = { role: "assistant", content: "", streaming: true };
    setMessages((prev) => [...prev, assistantPlaceholder]);

    let convId = activeId;
    let sources: SourceChunk[] = [];
    let latency_ms: number | undefined;
    let chunks_retrieved: number | undefined;

    try {
      for await (const event of streamQuery(q, activeId ?? undefined)) {
        if (event.type === "start") {
          convId = event.conversation_id;
          if (!activeId) {
            const now = new Date().toISOString();
            const newConv: ConvSummary = {
              id: event.conversation_id,
              title: q.slice(0, 80),
              created_at: now,
              updated_at: now,
            };
            setConvs((prev) => [newConv, ...prev]);
            setActiveId(event.conversation_id);
            setIsNew(false);
          }
        } else if (event.type === "meta") {
          sources = event.sources;
          chunks_retrieved = event.chunks_retrieved;
        } else if (event.type === "token") {
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last && last.role === "assistant") {
              next[next.length - 1] = { ...last, content: last.content + event.content };
            }
            return next;
          });
        } else if (event.type === "done") {
          latency_ms = event.latency_ms;
        } else if (event.type === "error") {
          throw new Error(event.message);
        }
      }

      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last.role === "assistant") {
          next[next.length - 1] = { ...last, sources, latency_ms, chunks_retrieved, streaming: false };
        }
        if (convId) msgCache.current.set(convId, next);
        return next;
      });

      if (convId && !activeId) {
        listConversations().then(setConvs).catch(() => {});
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Query failed");
      setMessages((prev) => prev.slice(0, -2));
    } finally {
      setSending(false);
    }
  };

  const selectConv = (id: string) => { setActiveId(id); setIsNew(false); };
  const startNew = () => { setActiveId(null); setMessages([]); setIsNew(true); };
  const activeConv = convs.find((c) => c.id === activeId);

  return (
    <div className="-m-6 md:-m-8 md:ml-0 h-[calc(100vh-0px)] md:h-screen flex">
      {/* Conversation sidebar */}
      <aside className="w-72 hidden md:flex flex-col" style={{ background: "rgba(255,255,255,0.88)", backdropFilter: "blur(20px)", WebkitBackdropFilter: "blur(20px)", borderRight: "1px solid rgba(196,181,253,0.40)" }}>
        <div className="p-4" style={{ borderBottom: "1px solid rgba(196,181,253,0.35)" }}>
          <button
            onClick={startNew}
            className="w-full text-white px-4 py-2 rounded-xl text-sm font-semibold active:scale-95 transition-all flex items-center justify-center gap-2 neon-gradient"
            style={{ background: "linear-gradient(135deg, #00F2FE, #F62681)" }}
          >
            <PenSquare className="h-4 w-4" />
            New Chat
          </button>
        </div>
        <div className="flex-1 overflow-y-auto py-2">
          {loadingConvs ? (
            <NeonLoaderMini />
          ) : convs.length === 0 ? (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center", padding: "32px 16px", gap: 10 }}>
              <div style={{
                width: 48, height: 48, borderRadius: 14, flexShrink: 0,
                background: "linear-gradient(135deg, rgba(0,242,254,0.12), rgba(246,38,129,0.12))",
                border: "1.5px solid rgba(196,181,253,0.45)",
                display: "flex", alignItems: "center", justifyContent: "center",
                boxShadow: "0 0 16px rgba(0,242,254,0.12)",
                animation: "float-icon 3s ease-in-out infinite",
              }}>
                <MessageCircle style={{ width: 22, height: 22, color: "#A78BFA" }} />
              </div>
              <p style={{ fontSize: 12, fontWeight: 600, color: "#1A1B41", margin: 0 }}>No chats yet</p>
              <p style={{ fontSize: 11, color: "#9BA3C2", margin: 0, lineHeight: 1.5 }}>
                Type a question below to start your first conversation.
              </p>
            </div>
          ) : null}
          {convs.map((c) => {
            const isActive = !isNew && c.id === activeId;
            return (
              <button
                key={c.id}
                onClick={() => selectConv(c.id)}
                className={cn(
                  "w-full text-left px-4 py-3 transition-all border-r-2",
                  isActive ? "border-r-[#00F2FE]" : "border-r-transparent",
                )}
                style={isActive
                  ? { background: "rgba(0,242,254,0.10)", borderLeft: "2px solid #00F2FE" }
                  : undefined
                }
                onMouseEnter={(e) => { if (!isActive) e.currentTarget.style.background = "rgba(196,181,253,0.18)"; }}
                onMouseLeave={(e) => { if (!isActive) e.currentTarget.style.background = "transparent"; }}
              >
                <div className="text-sm truncate" style={{ color: isActive ? "#00F2FE" : "#1A1B41", fontWeight: isActive ? 600 : 400 }}>
                  {c.title}
                </div>
                <div className="text-xs mt-0.5" style={{ color: "#9BA3C2" }}>
                  {new Date(c.updated_at).toLocaleDateString()}
                </div>
              </button>
            );
          })}
        </div>
      </aside>

      {/* Conversation area */}
      <div className="flex-1 flex flex-col min-w-0">
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 md:p-8">
          {isNew || (!activeId && messages.length === 0) ? (
            <div className="h-full flex flex-col items-center justify-center text-center">
              <div
                className="h-16 w-16 rounded-2xl flex items-center justify-center mb-4 neon-gradient"
                style={{ background: "linear-gradient(135deg, rgba(0,242,254,0.25), rgba(246,38,129,0.25))", border: "1px solid rgba(255,255,255,0.40)" }}
              >
                <Sparkles className="h-8 w-8" style={{ color: "#F62681" }} />
              </div>
              <h2 className="text-lg font-semibold text-[#1A1B41]">Ask anything about your documents</h2>
              <p className="text-sm mt-2 max-w-sm" style={{ color: "#5B5C8A" }}>
                Get instant answers backed by citations from your knowledge base.
              </p>
            </div>
          ) : loadingMsgs ? (
            <div className="h-full flex items-center justify-center">
              <NeonLoader />
            </div>
          ) : (
            <div className="max-w-3xl mx-auto space-y-6">
              {activeConv && (
                <div className="text-center pb-4" style={{ borderBottom: "1px solid rgba(196,181,253,0.40)" }}>
                  <h2 className="text-sm font-medium" style={{ color: "#5B5C8A" }}>{activeConv.title}</h2>
                </div>
              )}
              {messages.map((m, i) => (
                <MessageBubble key={i} message={m} />
              ))}
            </div>
          )}
        </div>

        {/* Composer */}
        <div className="p-4" style={{ background: "rgba(255,255,255,0.88)", backdropFilter: "blur(20px)", WebkitBackdropFilter: "blur(20px)", borderTop: "1px solid rgba(196,181,253,0.40)" }}>
          <div className="max-w-3xl mx-auto flex items-end gap-2">
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
              }}
              rows={1}
              placeholder="Ask a question about your documents…"
              disabled={sending}
              className="flex-1 rounded-xl px-4 py-3 text-sm text-[#1A1B41] placeholder:text-[#9BA3C2] focus:outline-none resize-none disabled:opacity-50 transition-all"
              style={{
                background: "rgba(255,255,255,0.75)",
                border: "1px solid rgba(196,181,253,0.50)",
              }}
              onFocus={(e) => { e.target.style.boxShadow = "0 0 0 2px rgba(0,242,254,0.30)"; e.target.style.borderColor = "#00F2FE"; }}
              onBlur={(e) => { e.target.style.boxShadow = "none"; e.target.style.borderColor = "rgba(255,255,255,0.50)"; }}
            />
            <button
              onClick={handleSend}
              disabled={!draft.trim() || sending}
              className="text-white p-3 rounded-xl active:scale-95 transition-all disabled:opacity-40 disabled:cursor-not-allowed neon-gradient"
              style={{ background: "linear-gradient(135deg, #00F2FE, #F62681)" }}
            >
              {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMsg }) {
  const [open, setOpen] = useState(false);
  if (message.role === "user") {
    return (
      <div className="flex justify-end animate-in fade-in slide-in-from-bottom-2 duration-300">
        <div
          className="max-w-[70%] rounded-2xl rounded-tr-sm px-4 py-3 text-white text-sm neon-gradient"
          style={{ background: "linear-gradient(135deg, #00F2FE, #F62681)" }}
        >
          {message.content}
        </div>
      </div>
    );
  }
  return (
    <div className="flex gap-3 animate-in fade-in slide-in-from-bottom-2 duration-300">
      <Avatar />
      <div className="max-w-[80%] space-y-2">
        <div
          className="glass rounded-2xl rounded-tl-sm px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap text-[#1A1B41]"
        >
          {message.content || (
            message.streaming && (
              <div className="flex items-center gap-1">
                <Dot delay={0} /><Dot delay={150} /><Dot delay={300} />
              </div>
            )
          )}
          {message.streaming && message.content && (
            <span className="inline-block w-0.5 h-4 ml-0.5 animate-pulse" style={{ background: "#00F2FE" }} />
          )}
        </div>
        {!message.streaming && message.sources && message.sources.length > 0 && (
          <div className="space-y-2">
            <button
              onClick={() => setOpen((v) => !v)}
              className="text-xs flex items-center gap-1 transition-colors hover:underline"
              style={{ color: "#5B5C8A" }}
            >
              {open ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
              {message.sources.length} source{message.sources.length === 1 ? "" : "s"}
            </button>
            {open && (
              <div className="space-y-2 animate-in fade-in slide-in-from-top-1 duration-200">
                {message.sources.map((s, i) => (
                  <div key={i} className="glass rounded-lg p-3 text-xs">
                    <div className="flex items-start justify-between gap-2 mb-1.5">
                      <div className="min-w-0">
                        <div className="text-[#1A1B41] font-medium truncate">
                          {s.corpus_name ?? s.doc_id ?? "Source"}
                        </div>
                        {s.section_path && (
                          <div className="mt-0.5 truncate" style={{ color: "#9BA3C2" }}>{s.section_path}</div>
                        )}
                      </div>
                      {s.page_num && (
                        <span
                          className="px-2 py-0.5 rounded text-[10px] font-medium shrink-0"
                          style={{ background: "rgba(255,255,255,0.40)", border: "1px solid rgba(255,255,255,0.50)", color: "#5B5C8A" }}
                        >
                          Page {s.page_num}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 mb-2">
                      <div className="flex-1 h-1 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.30)" }}>
                        <div
                          className="h-full transition-all duration-500"
                          style={{ width: `${s.relevance_score * 100}%`, background: "linear-gradient(90deg, #00F2FE, #F62681)" }}
                        />
                      </div>
                      <span className="text-[10px]" style={{ color: "#9BA3C2" }}>
                        {(s.relevance_score * 100).toFixed(0)}%
                      </span>
                    </div>
                    <p className="line-clamp-3" style={{ color: "#5B5C8A" }}>{s.text_excerpt}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        {!message.streaming && (message.latency_ms || message.chunks_retrieved) && (
          <div className="flex items-center gap-3 text-xs px-1" style={{ color: "#9BA3C2" }}>
            {message.latency_ms && (
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {message.latency_ms}ms
              </span>
            )}
            {message.chunks_retrieved != null && (
              <span className="flex items-center gap-1">
                <Database className="h-3 w-3" />
                {message.chunks_retrieved} chunks
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function Avatar() {
  return (
    <div
      className="h-8 w-8 rounded-full flex items-center justify-center shrink-0 neon-cyan"
      style={{ background: "linear-gradient(135deg, #00F2FE, #0099FF)" }}
    >
      <Bot className="h-4 w-4 text-white" />
    </div>
  );
}

function Dot({ delay }: { delay: number }) {
  return (
    <span
      className="h-1.5 w-1.5 rounded-full animate-bounce"
      style={{ background: "rgba(0,242,254,0.60)", animationDelay: `${delay}ms` }}
    />
  );
}
