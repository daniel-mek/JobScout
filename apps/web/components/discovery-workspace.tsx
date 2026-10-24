"use client";
import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { z } from "zod";
import { api } from "@/lib/api";
import { discoverySchema, reviewSchema } from "@/lib/discovery-contracts";
type Data = z.infer<typeof discoverySchema>;
const reasons = [
  "TOO_FAR",
  "WRONG_ROLE",
  "TOO_SENIOR",
  "SALARY_TOO_LOW",
  "CONTRACT",
  "CLEARANCE_REQUIRED",
  "COMPANY",
  "INDUSTRY",
  "ALREADY_APPLIED",
  "OTHER",
];

export function ReviewControls({
  id,
  initial,
}: {
  id: string;
  initial: z.infer<typeof reviewSchema> | null;
}) {
  const [review, setReview] = useState(initial);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [reason, setReason] = useState(initial?.reason || "OTHER");
  const router = useRouter();
  async function update(body: object) {
    setBusy(true);
    setMessage("");
    try {
      setReview(
        await api(`/jobs/${id}/review`, reviewSchema, {
          method: "PUT",
          body: JSON.stringify(body),
        }),
      );
      setMessage("Job preferences saved.");
      if ("saved" in body || "feedback" in body || "reviewed" in body)
        router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div>
      <div className="job-buttons">
        <button
          disabled={busy}
          onClick={() => void update({ saved: !review?.saved })}
        >
          {review?.saved ? "Unsave" : "Save job"}
        </button>
        <button
          disabled={busy}
          onClick={() => void update({ feedback: "INTERESTED" })}
        >
          Interested
        </button>
        <button
          disabled={busy}
          onClick={() => void update({ reviewed: !review?.reviewed })}
        >
          {review?.reviewed ? "Mark unreviewed" : "Mark reviewed"}
        </button>
        <label>
          Dismiss reason
          <select value={reason} onChange={(e) => setReason(e.target.value)}>
            {reasons.map((r) => (
              <option key={r}>{r}</option>
            ))}
          </select>
        </label>
        <button
          disabled={busy}
          onClick={() => void update({ feedback: "NOT_INTERESTED", reason })}
        >
          Not interested
        </button>
        {review?.feedback && (
          <button
            disabled={busy}
            onClick={() => void update({ feedback: "CLEAR" })}
          >
            Undo feedback
          </button>
        )}
      </div>
      {review?.saved && (
        <section>
          <h3>Saved notes & deadline</h3>
          <p>
            Saved with listing version {review.job_revision} on{" "}
            {review.saved_at?.slice(0, 10)}
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const values = new FormData(e.currentTarget);
              void update({
                notes: values.get("notes"),
                deadline: values.get("deadline") || null,
              });
            }}
          >
            <label htmlFor={`notes-${id}`}>Notes</label>
            <textarea
              id={`notes-${id}`}
              name="notes"
              defaultValue={review.notes}
              maxLength={6000}
            />
            <label htmlFor={`deadline-${id}`}>Optional deadline</label>
            <input
              id={`deadline-${id}`}
              type="date"
              name="deadline"
              defaultValue={review.deadline || ""}
            />
            <button disabled={busy}>Save notes</button>
          </form>
        </section>
      )}
      <p role="status">{message}</p>
    </div>
  );
}

export function DiscoveryWorkspace({
  data,
  query,
  roles,
  saved = false,
}: {
  data: Data;
  query: Record<string, string>;
  roles: { id: string; name: string }[];
  saved?: boolean;
}) {
  const next = (offset: number) => {
    const parameters = new URLSearchParams(query);
    parameters.set("offset", String(offset));
    return `${saved ? "/saved-jobs" : "/discover"}?${parameters}`;
  };
  return (
    <>
      <section className="dashboard-heading">
        <p className="eyebrow">Your opportunity list</p>
        <h1>{saved ? "Saved jobs" : "Discover"}</h1>
        <p>
          {data.total} listings · Scores reflect their recorded calculation
          time. Background matching refreshes them when the worker runs.
        </p>
      </section>
      <form className="panel" method="get">
        <div className="jobs-tools">
          <label>
            View
            <select name="view" defaultValue={query.view || "for_you"}>
              {[
                ["for_you", "For You"],
                ["fresh", "Fresh Opportunities"],
                ["excellent", "Excellent Matches"],
                ["reach", "Reasonable Reaches"],
                ["recent", "Recently Discovered"],
              ].map(([v, label]) => (
                <option key={v} value={v}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          {[
            ["title", "Title"],
            ["company", "Company"],
            ["location", "Location"],
          ].map(([name, label]) => (
            <label key={name}>
              {label}
              <input
                name={name}
                defaultValue={query[name] || ""}
                maxLength={200}
              />
            </label>
          ))}
          {(
            [
              [
                "source",
                "Source provider",
                [
                  "manual",
                  "greenhouse",
                  "lever",
                  "ashby",
                  "smartrecruiters",
                  "usajobs",
                  "adzuna",
                ],
              ],
              [
                "recommendation",
                "Recommendation",
                [
                  "EXCELLENT_MATCH",
                  "STRONG_APPLY",
                  "APPLY",
                  "REASONABLE_REACH",
                  "LONG_SHOT",
                  "SKIP",
                ],
              ],
              [
                "early_career",
                "Early-career category",
                [
                  "NEW_GRAD",
                  "TRUE_ENTRY_LEVEL",
                  "EARLY_CAREER",
                  "REASONABLE_REACH",
                  "MID_LEVEL",
                  "SENIOR",
                  "UNKNOWN",
                ],
              ],
            ] as const
          ).map(([name, label, options]) => (
            <label key={name}>
              {label}
              <select name={name} defaultValue={query[name] || ""}>
                <option value="">Any</option>
                {options.map((option) => (
                  <option key={option} value={option}>
                    {option.replaceAll("_", " ")}
                  </option>
                ))}
              </select>
            </label>
          ))}
          <label>
            Role family
            <select name="role_family" defaultValue={query.role_family || ""}>
              <option value="">All roles</option>
              {roles.map((role) => (
                <option key={role.id} value={role.id}>
                  {role.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Work arrangement
            <select name="arrangement" defaultValue={query.arrangement || ""}>
              <option value="">Any arrangement</option>
              {["REMOTE", "HYBRID", "ONSITE"].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </label>
          <label>
            Employment type
            <select
              name="employment_type"
              defaultValue={query.employment_type || ""}
            >
              <option value="">Any employment</option>
              {["FULL_TIME", "PART_TIME", "CONTRACT", "TEMPORARY"].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </select>
          </label>
          {[
            ["min_match", "Minimum match", 100],
            ["min_priority", "Minimum priority", 100],
            ["min_salary", "Minimum annual salary", 10000000],
            ["freshness_days", "Posted within days", 365],
          ].map(([name, label, max]) => (
            <label key={String(name)}>
              {label}
              <input
                type="number"
                name={String(name)}
                min={0}
                max={Number(max)}
                defaultValue={query[String(name)] || ""}
              />
            </label>
          ))}
          <label>
            Salary currency
            <input
              name="currency"
              defaultValue={query.currency || "USD"}
              maxLength={3}
            />
          </label>
          <label>
            Review state
            <select name="reviewed" defaultValue={query.reviewed || ""}>
              <option value="">Any review state</option>
              <option value="true">Reviewed</option>
              <option value="false">Unreviewed</option>
            </select>
          </label>
          {!saved && (
            <label>
              Saved state
              <select name="saved" defaultValue={query.saved || ""}>
                <option value="">Any saved state</option>
                <option value="true">Saved</option>
                <option value="false">Not saved</option>
              </select>
            </label>
          )}
        </div>
        <button>Apply filters</button>{" "}
        <Link href={saved ? "/saved-jobs" : "/discover"}>Reset filters</Link>
      </form>
      {!data.items.length && (
        <p>
          No listings match these filters. Import jobs or adjust the filters;
          unknown scores are not fabricated.
        </p>
      )}
      {data.items.map((job) => (
        <article className="panel job-history" key={job.id}>
          <p className="eyebrow">{job.company}</p>
          <h2>
            <Link href={`/jobs/${job.id}`}>{job.title}</Link>
          </h2>
          <p>
            {job.location || "Location unknown"} ·{" "}
            {job.arrangement || "Arrangement unknown"} ·{" "}
            {job.employment_type || "Employment unknown"} ·{" "}
            {job.active ? "Active" : "Archived"}
          </p>
          <p>
            Posted{" "}
            {job.posted_at
              ? `${Math.max(0, Math.floor((Date.parse(data.as_of) - Date.parse(job.posted_at)) / 86400000))} days ago (${job.posted_at.slice(0, 10)})`
              : "unknown"}{" "}
            · Discovered{" "}
            {Math.max(
              0,
              Math.floor(
                (Date.parse(data.as_of) - Date.parse(job.discovered_at)) /
                  86400000,
              ),
            )}{" "}
            days ago ({job.discovered_at.slice(0, 10)}) · {job.sources.length}{" "}
            sources
          </p>
          <p>
            Salary {job.salary_min ?? "unknown"} – {job.salary_max ?? "unknown"}{" "}
            {job.currency || ""} {job.salary_period || ""}
          </p>
          {job.match ? (
            <>
              <p>
                Resume Match {job.match.resume_match}/100 · Application Priority{" "}
                {job.match.application_priority}/100
              </p>
              <p>
                {job.match.early_career} · {job.match.recommendation} ·{" "}
                {job.match.eligibility}
              </p>
              <p>
                Calculated {job.match_calculated_at?.slice(0, 19)} UTC
                {!job.match_profile_current &&
                  " · Profile changed; recalculation pending"}
              </p>
            </>
          ) : (
            <p>Match pending. Open View Match to calculate this job now.</p>
          )}
          <p>
            <Link href={`/jobs/${job.id}`}>View Match</Link> ·{" "}
            <a
              href={job.application_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Open Application ↗
            </a>
          </p>
          <p>
            {job.sources.map((source, i) => (
              <span key={i}>
                {i > 0 ? " · " : ""}
                <a href={source.url} target="_blank" rel="noopener noreferrer">
                  {source.attribution}
                </a>
              </span>
            ))}
          </p>
          <ReviewControls id={job.id} initial={job.review} />
        </article>
      ))}
      <div className="job-buttons">
        {data.offset > 0 && (
          <Link href={next(Math.max(0, data.offset - 25))}>Previous</Link>
        )}
        {data.offset + data.items.length < data.total && (
          <Link href={next(data.offset + 25)}>Next</Link>
        )}
      </div>
    </>
  );
}
