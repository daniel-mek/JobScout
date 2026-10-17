import Link from "next/link";
import { redirect } from "next/navigation";
import {
  ArrowUpRight,
  CheckCircle2,
  FileText,
  Compass,
  Sparkles,
} from "lucide-react";
import { Shell } from "@/components/shell";
import { requireUser, onboardingState, serverApi } from "@/lib/server";
import { dashboardSchema, rolesSchema } from "@/lib/contracts";
export default async function Dashboard() {
  const user = await requireUser();
  const state = await onboardingState();
  if (!state.complete) redirect("/onboarding");
  const data = await serverApi("/dashboard", dashboardSchema);
  const roles = await serverApi("/role-families", rolesSchema);
  const profile = data.profile.profile;
  return (
    <Shell email={user.email}>
      <section className="dashboard-heading">
        <p className="eyebrow">One clear step at a time</p>
        <h1>
          You’ve got a foundation
          {profile?.name ? `, ${profile.name.split(" ")[0]}` : ""}
          <span>.</span>
        </h1>
        <p>
          Here’s where your next chapter begins. Your experience and search
          settings are ready.
        </p>
      </section>
      <div className="ready-banner">
        <CheckCircle2 />
        <div>
          <strong>Profile reviewed. Direction set.</strong>
          <p>
            You’re in control of what comes next. Your original resume is
            preserved.
          </p>
        </div>
        <Link href="/onboarding?edit=review">
          Review profile <ArrowUpRight size={16} />
        </Link>
      </div>
      <div className="dashboard-cards">
        <article className="panel">
          <div className="panel-icon">
            <FileText size={21} />
          </div>
          <p className="eyebrow">Your experience</p>
          <h2>{profile?.skills.length || 0} confirmed skills</h2>
          <p>
            {data.resume_versions} resume version
            {data.resume_versions !== 1 ? "s" : ""} · profile revision{" "}
            {data.profile.revision}
          </p>
          <Link href="/onboarding?edit=review">
            Keep your story current <ArrowUpRight size={15} />
          </Link>
        </article>
        <article className="panel">
          <div className="panel-icon">
            <Compass size={21} />
          </div>
          <p className="eyebrow">Your direction</p>
          <h2>
            {state.role_ids.length} career path
            {state.role_ids.length !== 1 ? "s" : ""}
          </h2>
          <p>
            {roles
              .filter((r) => state.role_ids.includes(r.id))
              .map((r) => r.name)
              .join(" · ")}
          </p>
          <Link href="/onboarding?edit=paths">
            Refine your direction <ArrowUpRight size={15} />
          </Link>
        </article>
      </div>
      <div className="section-heading">
        <h2>Your next useful steps</h2>
        <span className="pill">Foundation complete</span>
      </div>
      <div className="next-actions">
        <Link href="/onboarding?edit=upload">
          <span className="action-number">01</span>
          <div>
            <strong>Keep your master resume up to date</strong>
            <p>Upload a new version whenever your experience changes.</p>
          </div>
          <ArrowUpRight />
        </Link>
        <Link href="/onboarding?edit=preferences">
          <span className="action-number">02</span>
          <div>
            <strong>Make your preferences feel right</strong>
            <p>Review location, work arrangement, and salary preferences.</p>
          </div>
          <ArrowUpRight />
        </Link>
        <Link href="/onboarding?edit=requirements">
          <span className="action-number">03</span>
          <div>
            <strong>Check your must-haves</strong>
            <p>
              Keep hard requirements separate from things you simply prefer.
            </p>
          </div>
          <ArrowUpRight />
        </Link>
      </div>
      <aside className="phase-note">
        <Sparkles size={20} />
        <div>
          <strong>A considered start.</strong>
          <p>
            This workspace currently covers your account, resume, reviewed
            profile, and preferences. Personalized job discovery and application
            workflows will connect in later phases. Your existing JobScout tools
            remain separate.
          </p>
        </div>
      </aside>
    </Shell>
  );
}
