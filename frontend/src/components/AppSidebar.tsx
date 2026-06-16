import { Link, useRouterState, useNavigate } from "@tanstack/react-router";
import {
  LayoutDashboard, FileText, MessageSquare, MessagesSquare, BarChart3,
  Settings, LogOut, Menu, X, Sparkles,
} from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { logoutApi } from "@/lib/api/auth";

const allNav = [
  { to: "/dashboard",     label: "Dashboard",     icon: LayoutDashboard, adminOnly: false },
  { to: "/documents",     label: "Documents",     icon: FileText,        adminOnly: true  },
  { to: "/chat",          label: "Chat",          icon: MessageSquare,   adminOnly: false },
  { to: "/conversations", label: "Conversations", icon: MessagesSquare,  adminOnly: false },
  { to: "/evaluations",   label: "Evaluations",   icon: BarChart3,       adminOnly: false },
];

function SidebarBody({ onNavigate }: { onNavigate?: () => void }) {
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  const raw = localStorage.getItem("user");
  const user = raw ? (JSON.parse(raw) as { username: string; email: string; role: string }) : null;
  const initials = user?.username?.slice(0, 2).toUpperCase() ?? "??";
  const isAdmin = user?.role === "admin";
  const navItems = allNav.filter((n) => !n.adminOnly || isAdmin);

  function handleLogout() {
    logoutApi();
    navigate({ to: "/login" });
  }

  const itemClass = (active: boolean) =>
    cn(
      "flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150",
      active
        ? "bg-white/15 text-[#00F2FE] border border-white/20 neon-cyan"
        : "text-white/70 hover:bg-white/8 hover:text-white",
    );

  return (
    <div className="flex h-full flex-col" style={{ background: "linear-gradient(180deg, #1A1B41 0%, #2D1B4E 60%, #1A1B41 100%)" }}>
      {/* Brand */}
      <div className="px-5 py-5 border-b border-white/10">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl flex items-center justify-center neon-cyan" style={{ background: "linear-gradient(135deg, #00F2FE, #0099FF)" }}>
            <Sparkles className="h-4 w-4 text-white" />
          </div>
          <div>
            <div className="text-sm font-bold text-white tracking-tight">Knowledge</div>
            <div className="text-[10px] font-semibold tracking-widest uppercase -mt-0.5" style={{ color: "#00F2FE" }}>
              Assistant
            </div>
          </div>
        </div>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {navItems.map((n) => {
          const active = pathname.startsWith(n.to);
          return (
            <Link key={n.to} to={n.to} onClick={onNavigate} className={itemClass(active)}>
              <n.icon className="h-4 w-4" />
              <span>{n.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="px-3 pb-2">
        <Link
          to="/settings"
          onClick={onNavigate}
          className={itemClass(pathname.startsWith("/settings"))}
        >
          <Settings className="h-4 w-4" />
          <span>Settings</span>
        </Link>
      </div>

      {/* User */}
      <div className="border-t border-white/10 p-3">
        <div className="flex items-center gap-3 px-1">
          <div
            className="h-8 w-8 rounded-full flex items-center justify-center text-xs font-bold text-white shrink-0 neon-gradient"
            style={{ background: "linear-gradient(135deg, #00F2FE, #F62681)" }}
          >
            {initials}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium text-white truncate">{user?.username ?? "—"}</div>
            <div className="text-xs truncate" style={{ color: "#00F2FE" }}>{user?.email ?? "—"}</div>
          </div>
          <button
            onClick={handleLogout}
            className="p-1.5 rounded-lg text-white/50 hover:text-white hover:bg-white/10 transition-colors"
            aria-label="Log out"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

export function AppSidebar() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <aside className="hidden md:block fixed inset-y-0 left-0 w-60 z-30">
        <SidebarBody />
      </aside>

      <button
        onClick={() => setOpen(true)}
        className="md:hidden fixed top-4 left-4 z-40 p-2 rounded-lg text-white shadow-md neon-magenta"
        style={{ background: "linear-gradient(135deg, #F62681, #00F2FE)" }}
        aria-label="Open menu"
      >
        <Menu className="h-5 w-5" />
      </button>

      {open && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div className="absolute inset-0 bg-[#1A1B41]/60 backdrop-blur-sm" onClick={() => setOpen(false)} />
          <div className="relative w-60 h-full">
            <button
              onClick={() => setOpen(false)}
              className="absolute top-4 right-4 z-10 p-1.5 rounded-md text-white/60 hover:text-white hover:bg-white/10"
            >
              <X className="h-4 w-4" />
            </button>
            <SidebarBody onNavigate={() => setOpen(false)} />
          </div>
        </div>
      )}
    </>
  );
}
