import Link from "next/link";
import {
  LayoutDashboard,
  Settings2,
  ArrowUpRight,
  Compass,
  Bookmark,
  Bell,
  CalendarDays,
  ListChecks,
  Search,
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
          {[
            {
              href: "/discover",
              key: "discover",
              label: "Discover",
              icon: Compass,
            },
            {
              href: "/saved-jobs",
              key: "saved",
              label: "Saved jobs",
              icon: Bookmark,
            },
            {
              href: "/applications",
              key: "applications",
              label: "Applications",
              icon: ListChecks,
            },
            {
              href: "/brief",
              key: "brief",
              label: "Daily brief",
              icon: CalendarDays,
            },
            {
              href: "/notifications",
              key: "notifications",
              label: "Notifications",
              icon: Bell,
            },
            {
              href: "/jobs",
              key: "jobs",
              label: "Jobs & sources",
              icon: BriefcaseBusiness,
            },
            {
              href: "/dashboard",
              key: "dashboard",
              label: "Dashboard",
              icon: LayoutDashboard,
            },
            {
              href: "/settings",
              key: "settings",
              label: "Profile & settings",
              icon: Settings2,
            },
          ].map(({ href, key, label, icon: Icon }) => (
            <Link
              key={key}
              href={href}
              aria-current={active === key ? "page" : undefined}
            >
              <Icon size={18} aria-hidden="true" /> {label}
            </Link>
          ))}
        </nav>
        <div className="sidebar-note">
          <Search size={20} aria-hidden="true" />
          <div>
            <strong>A focused search</strong>
            <p>Find your fit. Save your shortlist. Keep moving.</p>
          </div>
        </div>
        <div className="account">
          <span className="avatar">{email[0].toUpperCase()}</span>
          <span>{email}</span>
        </div>
        <Logout />
      </aside>
      <main id="main" className="dashboard-main">
        <header className="topbar">
          <span>
            WORKSPACE <span className="topbar-divider">/</span>{" "}
            {active === "saved"
              ? "Saved jobs"
              : active === "jobs"
                ? "Jobs & sources"
                : active === "settings"
                  ? "Profile & settings"
                  : active === "brief"
                    ? "Daily brief"
                    : active.charAt(0).toUpperCase() + active.slice(1)}
          </span>
          <Link href="/settings">
            Your profile <ArrowUpRight size={15} />
          </Link>
        </header>
        {children}
      </main>
    </div>
  );
}
