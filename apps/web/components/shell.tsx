import Link from "next/link";
import {
  LayoutDashboard,
  Settings2,
  ArrowUpRight,
  Sprout,
  BriefcaseBusiness,
} from "lucide-react";
import { Logout } from "./logout";
export function Shell({
  children,
  email,
  active = "dashboard",
}: {
  children: React.ReactNode;
  email: string;
  active?: string;
}) {
  return (
    <div className="app-layout">
      <aside className="app-sidebar">
        <Link href="/" className="wordmark">
          apply<span>os</span>
          <i>↗</i>
        </Link>
        <p className="eyebrow">Your workspace</p>
        <nav aria-label="Main navigation">
          <Link
            href="/applications"
            aria-current={active === "applications" ? "page" : undefined}
          >
            Applications
          </Link>
          <Link
            href="/discover"
            aria-current={active === "discover" ? "page" : undefined}
          >
            Discover
          </Link>
          <Link
            href="/saved-jobs"
            aria-current={active === "saved" ? "page" : undefined}
          >
            Saved jobs
          </Link>
          <Link
            href="/brief"
            aria-current={active === "brief" ? "page" : undefined}
          >
            Daily brief
          </Link>
          <Link
            href="/notifications"
            aria-current={active === "notifications" ? "page" : undefined}
          >
            Notifications
          </Link>
          <Link
            aria-current={active === "jobs" ? "page" : undefined}
            href="/jobs"
          >
            <BriefcaseBusiness size={18} /> Jobs & sources
          </Link>
          <Link
            aria-current={active === "dashboard" ? "page" : undefined}
            href="/dashboard"
          >
            <LayoutDashboard size={18} /> Dashboard
          </Link>
          <Link
            aria-current={active === "settings" ? "page" : undefined}
            href="/settings"
          >
            <Settings2 size={18} /> Profile & settings
          </Link>
        </nav>
        <div className="sidebar-note">
          <Sprout size={22} />
          <p>
            Thoughtful steps.
            <br />
            Better opportunities.
          </p>
        </div>
        <div className="account">
          <span className="avatar">{email[0].toUpperCase()}</span>
          <span>{email}</span>
        </div>
        <Logout />
      </aside>
      <main id="main" className="dashboard-main">
        <header className="topbar">
          <span>YOUR NEXT CHAPTER</span>
          <Link href="/settings">
            Your profile <ArrowUpRight size={15} />
          </Link>
        </header>
        {children}
      </main>
    </div>
  );
}
