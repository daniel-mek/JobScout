import Link from "next/link";
import { z } from "zod";
import { Shell } from "@/components/shell";
import { requireUser, onboardingState, serverApi } from "@/lib/server";
import { resumeSchema } from "@/lib/contracts";
export default async function Settings() {
  const user = await requireUser();
  const state = await onboardingState();
  const versions = await serverApi("/resumes", z.array(resumeSchema));
  return (
    <Shell email={user.email} active="settings">
      <div className="dashboard-heading">
        <p className="eyebrow">Always in your control</p>
        <h1>
          Your profile & settings<span>.</span>
        </h1>
        <p>{user.email}</p>
      </div>
      {!state.complete && (
        <div className="notice">
          Your setup is in progress.{" "}
          <Link href="/onboarding">Continue where you left off.</Link>
        </div>
      )}
      <div className="settings-grid">
        {[
          [
            "review",
            "Confirmed profile",
            "Review education, experience, skills, and evidence.",
          ],
          [
            "paths",
            "Career paths",
            "Choose the role families that interest you.",
          ],
          [
            "preferences",
            "Soft preferences",
            "Locations, arrangements, salary, and industries.",
          ],
          [
            "requirements",
            "Hard requirements",
            "Your explicitly chosen boundaries.",
          ],
        ].map(([step, title, text]) => (
          <Link
            className="panel settings-link"
            href={`/onboarding?edit=${step}`}
            key={step}
          >
            <h2>{title} ↗</h2>
            <p>{text}</p>
          </Link>
        ))}
      </div>
      <div className="section-heading">
        <h2>Master resume history</h2>
        <Link href="/onboarding?edit=upload">Upload a new version ↗</Link>
      </div>
      <p className="hint">
        Previous uploads and their first confirmed profile snapshot stay
        preserved. A new upload always requires review.
      </p>
      {versions.length ? (
        <div className="resume-list">
          {versions.map((v) => (
            <div className="resume-row" key={v.id}>
              <div>
                <strong>{v.filename}</strong>
                <p>
                  Version {v.version} ·{" "}
                  {new Date(v.created_at).toLocaleDateString("en-US", {
                    timeZone: "UTC",
                  })}{" "}
                  · {Math.ceil(v.size_bytes / 1024)} KB
                </p>
              </div>
              <span className="pill">
                {v.confirmed ? "Reviewed" : "Needs review"}
              </span>
              <a
                className="secondary small button-link"
                href={`/backend/resumes/${v.id}/download`}
              >
                Download
              </a>
            </div>
          ))}
        </div>
      ) : (
        <p>No resume uploaded yet.</p>
      )}
    </Shell>
  );
}
