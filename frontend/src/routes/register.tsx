import { createFileRoute, useNavigate, Link } from "@tanstack/react-router";
import { useState } from "react";
import { Mail, Lock, User, Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { registerApi } from "@/lib/api/auth";

export const Route = createFileRoute("/register")({ component: RegisterPage });

function RegisterPage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      await registerApi(username, email, password);
      toast.success("Account created! Please sign in.");
      await navigate({ to: "/login" });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  const inputStyle = {
    background: "rgba(255,255,255,0.45)",
    border: "1px solid rgba(255,255,255,0.60)",
  };

  const onFocus = (e: React.FocusEvent<HTMLInputElement>) => {
    e.target.style.boxShadow = "0 0 0 2px rgba(0,242,254,0.35)";
    e.target.style.borderColor = "#00F2FE";
  };
  const onBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    e.target.style.boxShadow = "none";
    e.target.style.borderColor = "rgba(255,255,255,0.60)";
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <div
            className="h-16 w-16 rounded-2xl flex items-center justify-center mb-5 neon-gradient"
            style={{ background: "linear-gradient(135deg, #F62681 0%, #00F2FE 100%)" }}
          >
            <Sparkles className="h-8 w-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-[#1A1B41]">Create your account</h1>
          <p className="text-sm mt-1.5" style={{ color: "#5B5C8A" }}>Start exploring your knowledge base</p>
        </div>

        <div className="glass-strong rounded-2xl p-7">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-xs font-semibold uppercase tracking-wide mb-2 block" style={{ color: "#5B5C8A" }}>
                Username
              </label>
              <div className="relative">
                <User className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4" style={{ color: "#5B5C8A" }} />
                <input
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="john_doe"
                  required
                  className="w-full rounded-xl pl-10 pr-3 py-2.5 text-sm text-[#1A1B41] placeholder:text-[#9BA3C2] focus:outline-none transition-all"
                  style={inputStyle}
                  onFocus={onFocus}
                  onBlur={onBlur}
                />
              </div>
            </div>
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
                  style={inputStyle}
                  onFocus={onFocus}
                  onBlur={onBlur}
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
                  placeholder="At least 8 characters"
                  required
                  minLength={8}
                  className="w-full rounded-xl pl-10 pr-3 py-2.5 text-sm text-[#1A1B41] placeholder:text-[#9BA3C2] focus:outline-none transition-all"
                  style={inputStyle}
                  onFocus={onFocus}
                  onBlur={onBlur}
                />
              </div>
            </div>
            <div className="pt-1">
              <button
                type="submit"
                disabled={loading}
                className="w-full flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed text-white px-4 py-2.5 rounded-xl text-sm font-semibold active:scale-95 transition-all neon-gradient"
                style={{ background: "linear-gradient(135deg, #F62681 0%, #00F2FE 100%)" }}
              >
                {loading && <Loader2 className="h-4 w-4 animate-spin" />}
                {loading ? "Creating account…" : "Create account"}
              </button>
            </div>
          </form>
          <div className="mt-5 text-xs text-center" style={{ color: "#5B5C8A" }}>
            Already have an account?{" "}
            <Link to="/login" className="font-semibold hover:underline" style={{ color: "#00F2FE" }}>
              Sign in
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
