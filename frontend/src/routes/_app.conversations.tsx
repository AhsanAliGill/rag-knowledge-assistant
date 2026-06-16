import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { MessageSquare, Trash2, ArrowRight, Calendar, MessageCircle } from "lucide-react";
import { toast } from "sonner";
import { listConversations, deleteConversation, type ConvSummary } from "@/lib/api/conversations";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";

export const Route = createFileRoute("/_app/conversations")({
  head: () => ({ meta: [{ title: "Conversations — Knowledge Assistant" }] }),
  component: ConversationsPage,
});

/* ── World-class neon orbital loader ── */
function NeonLoader() {
  const ring = (inset: number, color: string, glowColor: string, dir: string, dur: string): React.CSSProperties => ({
    position: "absolute",
    inset,
    borderRadius: "50%",
    border: "2.5px solid transparent",
    borderTopColor: color,
    borderRightColor: dir === "cw" ? `${glowColor}55` : "transparent",
    borderLeftColor: dir === "ccw" ? `${glowColor}55` : "transparent",
    boxShadow: `0 0 10px ${glowColor}66`,
    animation: `orbit-${dir} ${dur} linear infinite`,
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "80px 0", gap: 22 }}>
      <div style={{ position: "relative", width: 76, height: 76 }}>
        <div style={ring(0,  "#00F2FE", "#00F2FE", "cw",  "1.4s")} />
        <div style={ring(10, "#F62681", "#F62681", "ccw", "0.95s")} />
        <div style={ring(20, "#A78BFA", "#A78BFA", "cw",  "0.62s")} />
        {/* glowing center dot */}
        <div style={{
          position: "absolute", inset: 30, borderRadius: "50%",
          background: "linear-gradient(135deg, #00F2FE, #F62681)",
          boxShadow: "0 0 14px rgba(0,242,254,0.70), 0 0 28px rgba(246,38,129,0.50)",
          animation: "loader-pulse 1.1s ease-in-out infinite",
        }} />
      </div>

      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 9 }}>
        <p style={{
          color: "#5B5C8A", fontSize: 11, fontWeight: 700,
          letterSpacing: "0.12em", textTransform: "uppercase",
          animation: "loader-text-fade 1.8s ease-in-out infinite",
        }}>
          Loading Conversations
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

/* ── Single conversation card ── */
function ConvCard({ conv, idx, onDelete, onOpen }: {
  conv: ConvSummary; idx: number; onDelete: () => void; onOpen: () => void;
}) {
  return (
    <div
      style={{
        background: "linear-gradient(135deg, rgba(255,255,255,0.90) 0%, rgba(237,233,254,0.82) 100%)",
        backdropFilter: "blur(20px)",
        WebkitBackdropFilter: "blur(20px)",
        border: "1px solid rgba(196,181,253,0.45)",
        borderRadius: 18,
        overflow: "hidden",
        boxShadow: "0 4px 20px rgba(124,58,237,0.10)",
        transition: "transform 0.30s cubic-bezier(0.34,1.56,0.64,1), box-shadow 0.30s, border-color 0.30s",
        animation: `conv-card-enter 0.45s ease-out ${idx * 0.07}s both`,
        display: "flex", flexDirection: "column",
      } as React.CSSProperties}
      onMouseEnter={(e) => {
        const el = e.currentTarget;
        el.style.transform = "translateY(-5px) scale(1.016)";
        el.style.boxShadow = "0 18px 48px rgba(124,58,237,0.20), 0 0 24px rgba(0,242,254,0.10)";
        el.style.borderColor = "rgba(196,181,253,0.75)";
      }}
      onMouseLeave={(e) => {
        const el = e.currentTarget;
        el.style.transform = "translateY(0) scale(1)";
        el.style.boxShadow = "0 4px 20px rgba(124,58,237,0.10)";
        el.style.borderColor = "rgba(196,181,253,0.45)";
      }}
    >
      {/* Gradient accent top stripe */}
      <div style={{ height: 3, background: "linear-gradient(90deg, #00F2FE, #A78BFA 50%, #F62681)", flexShrink: 0 }} />

      <div style={{ padding: "16px 18px 18px", display: "flex", flexDirection: "column", flex: 1 }}>
        {/* Icon + delete row */}
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12, marginBottom: 12 }}>
          <div style={{
            width: 42, height: 42, borderRadius: 13, flexShrink: 0,
            background: "linear-gradient(135deg, rgba(0,242,254,0.13), rgba(167,139,250,0.13))",
            border: "1px solid rgba(0,242,254,0.30)",
            display: "flex", alignItems: "center", justifyContent: "center",
            boxShadow: "0 0 10px rgba(0,242,254,0.14)",
          }}>
            <MessageSquare style={{ width: 18, height: 18, color: "#00F2FE" }} />
          </div>

          <button
            onClick={(e) => { e.stopPropagation(); onDelete(); }}
            title="Delete conversation"
            style={{
              padding: 7, borderRadius: 9, border: "none", background: "transparent",
              color: "rgba(155,163,194,0.60)", cursor: "pointer",
              transition: "all 0.20s", display: "flex", alignItems: "center",
            }}
            onMouseEnter={(e) => {
              const el = e.currentTarget;
              el.style.color = "#F62681";
              el.style.background = "rgba(246,38,129,0.10)";
              el.style.boxShadow = "0 0 10px rgba(246,38,129,0.22)";
              el.style.transform = "scale(1.12)";
            }}
            onMouseLeave={(e) => {
              const el = e.currentTarget;
              el.style.color = "rgba(155,163,194,0.60)";
              el.style.background = "transparent";
              el.style.boxShadow = "none";
              el.style.transform = "scale(1)";
            }}
          >
            <Trash2 style={{ width: 15, height: 15 }} />
          </button>
        </div>

        {/* Title */}
        <h3 className="line-clamp-2" style={{ fontSize: 14, fontWeight: 600, color: "#1A1B41", lineHeight: 1.55, marginBottom: 8 }}>
          {conv.title}
        </h3>

        {/* Date */}
        <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 14 }}>
          <Calendar style={{ width: 11, height: 11, color: "#9BA3C2", flexShrink: 0 }} />
          <span style={{ fontSize: 11, color: "#9BA3C2", letterSpacing: "0.02em" }}>
            {new Date(conv.updated_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}
          </span>
        </div>

        {/* Open button */}
        <div style={{ borderTop: "1px solid rgba(196,181,253,0.35)", paddingTop: 14 }}>
          <button
            onClick={onOpen}
            style={{
              display: "inline-flex", alignItems: "center", gap: 7,
              padding: "8px 18px", borderRadius: 22,
              background: "linear-gradient(135deg, #00F2FE, #F62681)",
              color: "#fff", fontSize: 12, fontWeight: 700, letterSpacing: "0.03em",
              border: "none", cursor: "pointer",
              boxShadow: "0 0 10px rgba(0,242,254,0.32), 0 0 22px rgba(246,38,129,0.22)",
              transition: "all 0.28s cubic-bezier(0.34,1.56,0.64,1)",
            }}
            onMouseEnter={(e) => {
              const el = e.currentTarget;
              el.style.boxShadow = "0 0 20px rgba(0,242,254,0.60), 0 0 40px rgba(246,38,129,0.38), 0 5px 18px rgba(0,0,0,0.18)";
              el.style.transform = "translateY(-2px) scale(1.06)";
            }}
            onMouseLeave={(e) => {
              const el = e.currentTarget;
              el.style.boxShadow = "0 0 10px rgba(0,242,254,0.32), 0 0 22px rgba(246,38,129,0.22)";
              el.style.transform = "translateY(0) scale(1)";
            }}
          >
            Open Chat
            <ArrowRight style={{ width: 13, height: 13 }} />
          </button>
        </div>
      </div>
    </div>
  );
}

function ConversationsPage() {
  const navigate = useNavigate();
  const [convs, setConvs] = useState<ConvSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [toDelete, setToDelete] = useState<ConvSummary | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    listConversations()
      .then(setConvs)
      .catch(() => toast.error("Failed to load conversations"))
      .finally(() => setLoading(false));
  }, []);

  const handleDelete = async () => {
    if (!toDelete) return;
    setDeleting(true);
    try {
      await deleteConversation(toDelete.id);
      setConvs((prev) => prev.filter((c) => c.id !== toDelete.id));
      toast.success("Conversation deleted");
      setToDelete(null);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl">
      {/* Header */}
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 4 }}>
            <h1 className="text-2xl font-bold text-[#1A1B41]">Conversations</h1>
            {!loading && convs.length > 0 && (
              <span style={{
                fontSize: 11, fontWeight: 700, color: "#fff",
                padding: "2px 11px", borderRadius: 20, letterSpacing: "0.06em",
                background: "linear-gradient(135deg, #00F2FE, #F62681)",
                boxShadow: "0 0 10px rgba(0,242,254,0.38)",
              }}>
                {convs.length}
              </span>
            )}
          </div>
          <p className="text-sm" style={{ color: "#5B5C8A" }}>Revisit your previous chats with the knowledge base.</p>
        </div>
      </header>

      {/* Body */}
      {loading ? (
        <NeonLoader />
      ) : convs.length === 0 ? (
        /* Empty state */
        <div style={{
          background: "rgba(255,255,255,0.88)",
          backdropFilter: "blur(20px)",
          WebkitBackdropFilter: "blur(20px)",
          border: "1px solid rgba(196,181,253,0.40)",
          borderRadius: 20,
          padding: "64px 24px",
          display: "flex", flexDirection: "column", alignItems: "center", textAlign: "center",
          boxShadow: "0 8px 32px rgba(124,58,237,0.10)",
        } as React.CSSProperties}>
          <div style={{
            width: 76, height: 76, borderRadius: 22,
            background: "linear-gradient(135deg, rgba(0,242,254,0.14), rgba(246,38,129,0.14))",
            border: "1.5px solid rgba(196,181,253,0.50)",
            display: "flex", alignItems: "center", justifyContent: "center",
            marginBottom: 18,
            boxShadow: "0 0 24px rgba(0,242,254,0.18)",
            animation: "float-icon 3s ease-in-out infinite",
          }}>
            <MessageCircle style={{ width: 34, height: 34, color: "#A78BFA" }} />
          </div>
          <h3 style={{ fontSize: 17, fontWeight: 700, color: "#1A1B41", marginBottom: 6 }}>No conversations yet</h3>
          <p style={{ fontSize: 13, color: "#9BA3C2", marginBottom: 22, maxWidth: 260 }}>
            Start a new chat to see your history here.
          </p>
          <button
            onClick={() => navigate({ to: "/chat" })}
            style={{
              display: "inline-flex", alignItems: "center", gap: 8,
              padding: "10px 26px", borderRadius: 26,
              background: "linear-gradient(135deg, #00F2FE, #F62681)",
              color: "#fff", fontSize: 13, fontWeight: 700, border: "none", cursor: "pointer",
              boxShadow: "0 0 14px rgba(0,242,254,0.44), 0 0 30px rgba(246,38,129,0.28)",
              transition: "all 0.28s cubic-bezier(0.34,1.56,0.64,1)",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.transform = "translateY(-2px) scale(1.05)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.transform = "translateY(0) scale(1)"; }}
          >
            <MessageSquare style={{ width: 15, height: 15 }} />
            Start a Chat
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {convs.map((c, idx) => (
            <ConvCard
              key={c.id}
              conv={c}
              idx={idx}
              onDelete={() => setToDelete(c)}
              onOpen={() => navigate({ to: "/chat", search: { id: c.id } })}
            />
          ))}
        </div>
      )}

      {/* Delete dialog */}
      <Dialog open={!!toDelete} onOpenChange={(o) => !o && setToDelete(null)}>
        <DialogContent className="glass-opaque border-0 text-[#1A1B41]" style={{ borderRadius: 20 }}>
          <DialogHeader>
            <DialogTitle style={{ color: "#1A1B41", fontSize: 17, fontWeight: 700 }}>Delete conversation?</DialogTitle>
            <DialogDescription style={{ color: "#5B5C8A", marginTop: 6, lineHeight: 1.65 }}>
              "<span style={{ color: "#1A1B41", fontWeight: 600 }}>{toDelete?.title}</span>" will be permanently removed and cannot be recovered.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter style={{ marginTop: 4, gap: 8 }}>
            <button
              onClick={() => setToDelete(null)}
              style={{
                padding: "9px 20px", borderRadius: 13, fontSize: 13, fontWeight: 600, cursor: "pointer",
                background: "rgba(255,255,255,0.80)", border: "1px solid rgba(196,181,253,0.50)", color: "#1A1B41",
                transition: "all 0.20s",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.borderColor = "rgba(196,181,253,0.80)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.borderColor = "rgba(196,181,253,0.50)"; }}
            >
              Cancel
            </button>
            <button
              onClick={handleDelete}
              disabled={deleting}
              style={{
                display: "flex", alignItems: "center", gap: 7,
                padding: "9px 20px", borderRadius: 13, fontSize: 13, fontWeight: 600, cursor: "pointer",
                background: "rgba(246,38,129,0.10)", border: "1px solid rgba(246,38,129,0.35)", color: "#F62681",
                transition: "all 0.20s", opacity: deleting ? 0.55 : 1,
              }}
              onMouseEnter={(e) => {
                if (!deleting) {
                  e.currentTarget.style.background = "rgba(246,38,129,0.16)";
                  e.currentTarget.style.boxShadow = "0 0 10px rgba(246,38,129,0.20)";
                }
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "rgba(246,38,129,0.10)";
                e.currentTarget.style.boxShadow = "none";
              }}
            >
              {deleting && (
                <div style={{
                  width: 13, height: 13, borderRadius: "50%",
                  border: "2px solid rgba(246,38,129,0.25)",
                  borderTopColor: "#F62681",
                  animation: "orbit-cw 0.7s linear infinite",
                }} />
              )}
              Delete
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
