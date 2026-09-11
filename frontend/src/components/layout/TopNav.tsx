import { NavLink } from "react-router-dom";
import { Landmark, ShieldCheck, User } from "lucide-react";
import { cn } from "@/lib/cn";

const customerLinks = [{ to: "/customer", label: "My Applications", end: true }];
const underwriterLinks = [{ to: "/review", label: "Review Queue", end: true }];

function NavItem({ to, label, end }: { to: string; label: string; end?: boolean }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) =>
        cn(
          "rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
          isActive ? "bg-brand-50 text-brand-700" : "text-ink-600 hover:bg-ink-100 hover:text-ink-900"
        )
      }
    >
      {label}
    </NavLink>
  );
}

export function TopNav({ mode }: { mode: "customer" | "underwriter" }) {
  const links = mode === "customer" ? customerLinks : underwriterLinks;
  return (
    <header className="sticky top-0 z-10 border-b border-ink-100 bg-white/90 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 sm:px-6">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-brand-600 text-white">
              <Landmark className="h-4 w-4" />
            </div>
            <span className="text-sm font-bold tracking-tight text-ink-900">LendAI</span>
          </div>
          <nav className="hidden items-center gap-1 sm:flex">
            {links.map((l) => (
              <NavItem key={l.to} {...l} />
            ))}
          </nav>
        </div>

        <div className="flex items-center gap-2">
          <div className="hidden rounded-lg bg-ink-100 p-0.5 text-xs font-medium sm:flex">
            <NavLink
              to="/customer"
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-1.5 rounded-md px-2.5 py-1.5 transition-colors",
                  isActive || mode === "customer" ? "bg-white text-ink-900 shadow-sm" : "text-ink-500"
                )
              }
            >
              <User className="h-3.5 w-3.5" /> Customer
            </NavLink>
            <NavLink
              to="/review"
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-1.5 rounded-md px-2.5 py-1.5 transition-colors",
                  isActive || mode === "underwriter" ? "bg-white text-ink-900 shadow-sm" : "text-ink-500"
                )
              }
            >
              <ShieldCheck className="h-3.5 w-3.5" /> Underwriter
            </NavLink>
          </div>
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-ink-800 text-xs font-semibold text-white">
            {mode === "customer" ? "AP" : "UW"}
          </div>
        </div>
      </div>
    </header>
  );
}
