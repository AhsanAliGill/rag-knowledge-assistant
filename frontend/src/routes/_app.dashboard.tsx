import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { FileText, CheckCircle, MessagesSquare, BarChart3, ArrowRight, Loader2 } from "lucide-react";
import { StatusBadge } from "@/components/StatusBadge";
import { listDocuments, type DocRead } from "@/lib/api/documents";
import { listConversations, type ConvSummary } from "@/lib/api/conversations";
import { listEvaluations } from "@/lib/api/evaluations";

export const Route = createFileRoute("/_app/dashboard")({
  head: () => ({ meta: [{ title: "Dashboard — Knowledge Assistant" }] }),
  component: DashboardPage,
});

function fmtBytes(b: number) {
  if (b < 1024) return `${b} B`;
  if (b < 1048576) return `${(b / 1024).toFixed(0)} KB`;
  return `${(b / 1048576).toFixed(1)} MB`;
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

const STATS = [
  { label: "Total Documents", key: "docs",     icon: FileText,       accent: "#00F2FE", glow: "neon-cyan"     },
  { label: "Ready to Query",  key: "ready",    icon: CheckCircle,    accent: "#7C3AED", glow: "neon-violet"   },
  { label: "Conversations",   key: "convs",    icon: MessagesSquare, accent: "#F62681", glow: "neon-magenta"  },
  { label: "Evaluations Run", key: "evals",    icon: BarChart3,      accent: "#00F2FE", glow: "neon-cyan"     },
] as const;

function DashboardPage() {
  const [docs, setDocs] = useState<DocRead[]>([]);
  const [convs, setConvs] = useState<ConvSummary[]>([]);
  const [evalCount, setEvalCount] = useState(0);
  const [loading, setLoading] = useState(true);

  const raw = localStorage.getItem("user");
  const user = raw ? (JSON.parse(raw) as { username: string }) : null;

  useEffect(() => {
    Promise.all([
      listDocuments().then((r) => setDocs(r.documents)).catch(() => {}),
      listConversations().then(setConvs).catch(() => {}),
      listEvaluations().then((r) => setEvalCount(r.total)).catch(() => {}),
    ]).finally(() => setLoading(false));
  }, []);

  const values: Record<string, number> = {
    docs: docs.length,
    ready: docs.filter((d) => d.status === "ready").length,
    convs: convs.length,
    evals: evalCount,
  };

  return (
    <div className="space-y-8 max-w-7xl">
      <header>
        <p className="text-sm font-semibold mb-1" style={{ color: "#F62681" }}>
          {user ? `Welcome back, ${user.username}` : "Welcome back"}
        </p>
        <h1 className="text-2xl font-bold text-[#1A1B41]">Dashboard</h1>
        <p className="text-sm mt-1" style={{ color: "#5B5C8A" }}>Overview of your knowledge base and activity.</p>
      </header>

      {/* Stat cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {STATS.map((s) => (
          <div key={s.label} className={`glass rounded-xl p-5 transition-all hover:scale-[1.02] ${s.glow}`}>
            <div className="flex items-center justify-between mb-4">
              <div
                className="h-10 w-10 rounded-xl flex items-center justify-center"
                style={{ background: `${s.accent}22`, border: `1px solid ${s.accent}44` }}
              >
                <s.icon className="h-5 w-5" style={{ color: s.accent }} />
              </div>
            </div>
            <div className="text-3xl font-bold text-[#1A1B41]">
              {loading ? <Loader2 className="h-6 w-6 animate-spin" style={{ color: s.accent }} /> : values[s.key]}
            </div>
            <div className="text-sm mt-1" style={{ color: "#5B5C8A" }}>{s.label}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Documents */}
        <div className="lg:col-span-2 glass rounded-xl overflow-hidden">
          <div className="px-6 py-4 flex items-center justify-between" style={{ borderBottom: "1px solid rgba(196,181,253,0.40)" }}>
            <h2 className="text-sm font-semibold text-[#1A1B41]">Recent Documents</h2>
            <Link
              to="/documents"
              className="text-xs flex items-center gap-1 font-semibold hover:underline"
              style={{ color: "#F62681" }}
            >
              View all <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          {loading ? (
            <div className="flex items-center justify-center py-8 gap-2" style={{ color: "#9BA3C2" }}>
              <Loader2 className="h-4 w-4 animate-spin" />
              <span className="text-sm">Loading…</span>
            </div>
          ) : docs.length === 0 ? (
            <div className="px-6 py-8 text-sm text-center" style={{ color: "#9BA3C2" }}>No documents yet</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="text-xs" style={{ color: "#5B5C8A", background: "rgba(255,255,255,0.15)" }}>
                <tr>
                  <th className="text-left font-medium px-6 py-2.5">Filename</th>
                  <th className="text-left font-medium px-3 py-2.5">Status</th>
                  <th className="text-left font-medium px-3 py-2.5">Pages</th>
                  <th className="text-left font-medium px-3 py-2.5">Size</th>
                  <th className="text-left font-medium px-6 py-2.5">Uploaded</th>
                </tr>
              </thead>
              <tbody>
                {docs.slice(0, 5).map((d) => (
                  <tr key={d.doc_id} className="transition-colors" style={{ borderTop: "1px solid rgba(196,181,253,0.30)" }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(196,181,253,0.15)")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                  >
                    <td className="px-6 py-3 text-[#1A1B41] truncate max-w-[260px]">{d.filename}</td>
                    <td className="px-3 py-3"><StatusBadge status={d.status} /></td>
                    <td className="px-3 py-3" style={{ color: "#5B5C8A" }}>{d.page_count ?? "—"}</td>
                    <td className="px-3 py-3" style={{ color: "#5B5C8A" }}>{fmtBytes(d.size_bytes)}</td>
                    <td className="px-6 py-3" style={{ color: "#9BA3C2" }}>{fmtDate(d.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Recent Conversations */}
        <div className="glass rounded-xl overflow-hidden">
          <div className="px-6 py-4 flex items-center justify-between" style={{ borderBottom: "1px solid rgba(196,181,253,0.40)" }}>
            <h2 className="text-sm font-semibold text-[#1A1B41]">Recent Conversations</h2>
            <Link
              to="/conversations"
              className="text-xs flex items-center gap-1 font-semibold hover:underline"
              style={{ color: "#00F2FE" }}
            >
              View all <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
          {convs.length === 0 ? (
            <div className="px-6 py-8 text-sm text-center" style={{ color: "#9BA3C2" }}>No conversations yet</div>
          ) : (
            <ul>
              {convs.slice(0, 6).map((c) => (
                <li key={c.id} style={{ borderTop: "1px solid rgba(196,181,253,0.30)" }}>
                  <Link
                    to="/chat"
                    search={{ id: c.id }}
                    className="flex items-center justify-between px-6 py-3 group transition-colors"
                    style={{ color: "inherit" }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(196,181,253,0.15)")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                  >
                    <div className="min-w-0">
                      <div className="text-sm text-[#1A1B41] truncate">{c.title}</div>
                      <div className="text-xs mt-0.5" style={{ color: "#9BA3C2" }}>{fmtDate(c.updated_at)}</div>
                    </div>
                    <ArrowRight className="h-4 w-4 shrink-0 transition-colors" style={{ color: "#C4B5FD" }} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
