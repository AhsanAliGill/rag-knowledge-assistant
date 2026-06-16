import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";
import type { UserInfo } from "@/lib/api/auth";

export const Route = createFileRoute("/_app/settings")({
  head: () => ({ meta: [{ title: "Settings — Knowledge Assistant" }] }),
  component: SettingsPage,
});

const services = [
  { name: "Groq LLM", detail: "llama-3.3-70b-versatile" },
  { name: "OpenRouter", detail: "text-embedding-3-large" },
  { name: "Qdrant Vector DB", detail: "rag_documents collection" },
  { name: "Cohere Reranker", detail: "rerank-english-v3.0" },
  { name: "PostgreSQL", detail: "Primary database" },
];

const ragConfig: [string, string][] = [
  ["Embedding dimensions", "3072"],
  ["Dense retrieval (k)", "20 results"],
  ["Sparse retrieval (k)", "20 results"],
  ["Dense weight in fusion", "60%"],
  ["Rerank top-n", "8 chunks"],
  ["Context token budget", "3,500 tokens"],
  ["Max upload size", "50 MB"],
  ["Max pages per PDF", "500 pages"],
];

function getStoredUser(): UserInfo | null {
  try {
    const raw = localStorage.getItem("user");
    return raw ? (JSON.parse(raw) as UserInfo) : null;
  } catch {
    return null;
  }
}

function getInitials(username: string): string {
  const parts = username.trim().split(/[\s._-]+/);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return username.slice(0, 2).toUpperCase();
}

function SettingsPage() {
  const stored = getStoredUser();
  const [username, setUsername] = useState(stored?.username ?? "");
  const [email, setEmail] = useState(stored?.email ?? "");

  const initials = getInitials(username || "U");

  function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (stored) {
      const updated: UserInfo = { ...stored, username, email };
      localStorage.setItem("user", JSON.stringify(updated));
    }
    toast.success("Profile updated");
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <header>
        <h1 className="text-2xl font-bold text-[#1A1B41]">Settings</h1>
        <p className="text-sm text-[#5B5C8A] mt-1">
          Manage your profile, integrations, and RAG configuration.
        </p>
      </header>

      {/* Profile */}
      <section className="glass rounded-xl p-6">
        <h2 className="text-sm font-semibold text-[#1A1B41] mb-4">Profile</h2>
        <div className="flex items-center gap-4 pb-5 border-b border-purple-100">
          <div className="h-16 w-16 rounded-full flex items-center justify-center text-xl font-bold text-white neon-gradient" style={{ background: "linear-gradient(135deg, #00F2FE, #F62681)" }}>
            {initials}
          </div>
          <div className="flex-1">
            <div className="text-base font-semibold text-[#1A1B41]">{username || "—"}</div>
            <div className="text-sm text-[#5B5C8A]">{email || "—"}</div>
          </div>
          {stored?.is_active && (
            <span className="text-xs font-semibold px-2.5 py-1 rounded-full border bg-emerald-50 text-emerald-600 border-emerald-200">
              Active
            </span>
          )}
        </div>
        <form
          onSubmit={handleSave}
          className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-5"
        >
          <div>
            <label className="text-xs font-semibold text-[#5B5C8A] uppercase tracking-wide mb-2 block">
              Username
            </label>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full glass-strong rounded-xl px-3 py-2.5 text-sm text-[#1A1B41] focus:outline-none transition-all"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-[#5B5C8A] uppercase tracking-wide mb-2 block">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full glass-strong rounded-xl px-3 py-2.5 text-sm text-[#1A1B41] focus:outline-none transition-all"
            />
          </div>
          <div className="md:col-span-2">
            <button
              type="submit"
              className="text-white px-5 py-2.5 rounded-xl text-sm font-semibold active:scale-95 transition-all neon-gradient" style={{ background: "linear-gradient(135deg, #00F2FE, #F62681)" }}
            >
              Save Changes
            </button>
          </div>
        </form>
      </section>

      {/* API Services */}
      <section className="glass rounded-xl p-6">
        <h2 className="text-sm font-semibold text-[#1A1B41] mb-4">API Services</h2>
        <div className="divide-y divide-purple-100">
          {services.map((s) => (
            <div key={s.name} className="flex items-center justify-between py-3 first:pt-0 last:pb-0">
              <div className="flex items-center gap-3">
                <span className="h-2 w-2 rounded-full bg-emerald-400" />
                <div>
                  <div className="text-sm font-medium text-[#1A1B41]">{s.name}</div>
                  <div className="text-xs text-[#9BA3C2]">{s.detail}</div>
                </div>
              </div>
              <span className="text-xs font-semibold px-2.5 py-1 rounded-full border bg-emerald-50 text-emerald-600 border-emerald-200">
                Connected
              </span>
            </div>
          ))}
        </div>
        <p className="text-xs text-[#9BA3C2] mt-4">API keys are managed server-side.</p>
      </section>

      {/* RAG Configuration */}
      <section className="glass rounded-xl p-6">
        <h2 className="text-sm font-semibold text-[#1A1B41] mb-4">RAG Configuration</h2>
        <dl className="divide-y divide-purple-100">
          {ragConfig.map(([k, v]) => (
            <div key={k} className="flex items-center justify-between py-3 first:pt-0 last:pb-0">
              <dt className="text-sm text-[#5B5C8A]">{k}</dt>
              <dd className="text-sm font-semibold text-[#1A1B41] font-mono">{v}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}
