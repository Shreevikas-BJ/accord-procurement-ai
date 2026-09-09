"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";
import {
  Layers3,
  LayoutDashboard,
  Inbox,
  Files,
  Building2,
  Boxes,
  History,
  ScrollText,
  Settings2,
  LogOut,
  ChevronDown,
  Search,
  Menu,
  ShieldCheck,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";
const UserContext = createContext<User | null>(null);
export const useUser = () => useContext(UserContext);
const links = [
  ["/", "Dashboard", LayoutDashboard],
  ["/inbox", "Inbox", Inbox],
  ["/rfqs", "RFQs", Files],
  ["/suppliers", "Suppliers", Building2],
  ["/items", "Items", Boxes],
  ["/purchase-history", "Purchase History", History],
  ["/audit-events", "Audit Log", ScrollText],
  ["/settings", "Settings", Settings2],
] as const;
export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname(),
    router = useRouter();
  const [user, setUser] = useState<User | null>(null),
    [error, setError] = useState(""),
    [mobile, setMobile] = useState(false);
  useEffect(() => {
    api<User>("/auth/me")
      .then(setUser)
      .catch(() => router.replace("/login"));
  }, [router]);
  if (!user)
    return (
      <div className="boot">
        <Layers3 size={32} />
        <p>Opening your workspace…</p>
      </div>
    );
  return (
    <UserContext.Provider value={user}>
      <div className="app-shell">
        <aside className={`sidebar ${mobile ? "open" : ""}`}>
          <Link href="/" className="brand">
            <Layers3 size={27} />
            accord
          </Link>
          <div className="company">
            <div className="company-monogram">A</div>
            <div>
              <strong>{user.organization.replace(" Manufacturing", "")}</strong>
              <span>Procurement workspace</span>
            </div>
            <ChevronDown size={14} />
          </div>
          <div className="nav-label">WORKSPACE</div>
          <nav>
            {links.map(([href, label, Icon]) => (
              <Link
                onClick={() => setMobile(false)}
                className={
                  path === href || (href !== "/" && path.startsWith(href))
                    ? "active"
                    : ""
                }
                key={href}
                href={href}
              >
                <Icon size={18} />
                {label}
                {label === "Inbox" && <span className="nav-dot" />}
              </Link>
            ))}
          </nav>
          <div className="sidebar-bottom">
            <div className="local-note">
              <ShieldCheck size={16} />
              <div>
                <strong>Local workspace</strong>
                <span>Your data stays with you</span>
              </div>
            </div>
            <div className="user">
              <div className="avatar">
                {user.name
                  .split(" ")
                  .map((n) => n[0])
                  .join("")}
              </div>
              <div>
                <strong>{user.name}</strong>
                <span>{user.role}</span>
              </div>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Sign out"
                onClick={async () => {
                  try {
                    await api("/auth/logout", { method: "POST" });
                    router.replace("/login");
                  } catch (e) {
                    setError((e as Error).message);
                  }
                }}
              >
                <LogOut size={16} />
              </Button>
            </div>
          </div>
        </aside>
        <div className="main-column">
          <header className="topbar">
            <Button
              className="mobile-toggle"
              variant="ghost"
              size="icon"
              aria-label="Toggle navigation"
              onClick={() => setMobile(!mobile)}
            >
              {mobile ? <X /> : <Menu />}
            </Button>
            <span>
              {user.organization} <span className="slash">/</span> Procurement
            </span>
            <div className="topbar-right">
              <Link href="/rfqs" className="search-shortcut">
                <Search size={15} /> Find an RFQ <kbd>⌕</kbd>
              </Link>
              <Link href="/settings" className="mode-badge">
                ● <Mode />
              </Link>
            </div>
          </header>
          {error && (
            <p className="error-box" role="alert">
              {error}
            </p>
          )}
          <main className="workspace">{children}</main>
          <footer className="workspace-footer">
            Accord Procurement{" "}
            <span>
              Analysis informed by source documents. Decisions owned by your
              team.
            </span>
          </footer>
        </div>
      </div>
    </UserContext.Provider>
  );
}
function Mode() {
  const [mode, setMode] = useState("");
  useEffect(() => {
    api<{ ai_mode: string }>("/settings/scoring")
      .then((s) => setMode(s.ai_mode))
      .catch(() => setMode("unavailable"));
  }, []);
  return (
    <>
      {mode === "demo"
        ? "DEMO MODE"
        : mode === "local"
          ? "LOCAL AI"
          : mode === "api"
            ? "HOSTED AI"
            : "PROVIDER STATUS"}
    </>
  );
}
