import { createFileRoute, useNavigate, Link } from "@tanstack/react-router";
import { useState } from "react";
import { Mail, Lock, Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { loginApi } from "@/lib/api/auth";

export const Route = createFileRoute("/login")({ component: LoginPage });

function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const user = await loginApi(email, password);
      localStorage.setItem("user", JSON.stringify(user));
      await navigate({ to: "/dashboard" });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <div
            className="h-16 w-16 rounded-2xl flex items-center justify-center mb-5 neon-gradient"
            style={{ background: "linear-gradient(135deg, #00F2FE 0%, #F62681 100%)" }}
          >
            <Sparkles className="h-8 w-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-[#1A1B41]">Welcome back</h1>
          <p className="text-sm mt-1.5" style={{ color: "#5B5C8A" }}>Sign in to Knowledge Assistant</p>
        </div>

        <div className="glass-strong rounded-2xl p-7">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-xs font-semibold uppercase tracking-wide mb-2 block" style={{ color: "#5B5C8A" }}>
                Email
              </label>
              <div className="relative">
                <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4" style={{ color: "#5B5C8A" }} />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  required
                  className="w-full rounded-xl pl-10 pr-3 py-2.5 text-sm text-[#1A1B41] placeholder:text-[#9BA3C2] focus:outline-none transition-all"
                  style={{
                    background: "rgba(255,255,255,0.45)",
                    border: "1px solid rgba(255,255,255,0.60)",
                  }}
                  onFocus={(e) => { e.target.style.boxShadow = "0 0 0 2px rgba(0,242,254,0.35)"; e.target.style.borderColor = "#00F2FE"; }}
                  onBlur={(e) => { e.target.style.boxShadow = "none"; e.target.style.borderColor = "rgba(255,255,255,0.60)"; }}
                />
              </div>
            </div>
            <div>
              <label className="text-xs font-semibold uppercase tracking-wide mb-2 block" style={{ color: "#5B5C8A" }}>
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4" style={{ color: "#5B5C8A" }} />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Your password"
                  required
                  className="w-full rounded-xl pl-10 pr-3 py-2.5 text-sm text-[#1A1B41] placeholder:text-[#9BA3C2] focus:outline-none transition-all"
                  style={{
                    background: "rgba(255,255,255,0.45)",
                    border: "1px solid rgba(255,255,255,0.60)",
                  }}
                  onFocus={(e) => { e.target.style.boxShadow = "0 0 0 2px rgba(0,242,254,0.35)"; e.target.style.borderColor = "#00F2FE"; }}
                  onBlur={(e) => { e.target.style.boxShadow = "none"; e.target.style.borderColor = "rgba(255,255,255,0.60)"; }}
                />
              </div>
            </div>
            <div className="pt-1">
              <button
                type="submit"
                disabled={loading}
                className="w-full flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed text-white px-4 py-2.5 rounded-xl text-sm font-semibold active:scale-95 transition-all neon-gradient"
                style={{ background: "linear-gradient(135deg, #00F2FE 0%, #F62681 100%)" }}
              >
                {loading && <Loader2 className="h-4 w-4 animate-spin" />}
                {loading ? "Signing in…" : "Sign in"}
              </button>
            </div>
          </form>
          <div className="mt-5 text-xs text-center" style={{ color: "#5B5C8A" }}>
            Don't have an account?{" "}
            <Link to="/register" className="font-semibold hover:underline" style={{ color: "#F62681" }}>
              Create one
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
