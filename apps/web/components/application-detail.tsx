"use client";
import Link from "next/link";
import { useState } from "react";
import { api } from "@/lib/api";
import { Resume } from "@/lib/contracts";
import {
  ApplicationDetail as Detail,
  applicationDetailSchema,
  statuses,
  statusLabel,
} from "@/lib/application-contracts";

const stamp = (value: string) =>
  new Date(value).toLocaleString("en-US", { timeZone: "UTC" }) + " UTC";

export function ApplicationDetail({
  initial,
  resumes,
}: {
  initial: Detail;
  resumes: Resume[];
}) {
  const [row, setRow] = useState(initial);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [target, setTarget] = useState(row.status);
  async function save(path: string, method: string, body?: object) {
    setBusy(true);
    setMessage("");
    try {
      const result = await api(
        `/applications/${row.id}${path}`,
        applicationDetailSchema,
        { method, body: body ? JSON.stringify(body) : undefined },
      );
      setRow(result);
      setTarget(result.status);
      setMessage("Application saved.");
    } catch (e) {
      setMessage(
        e instanceof Error ? e.message : "Could not save application.",
      );
    } finally {
      setBusy(false);
    }
  }
  const timeline = [
    ...row.history.map((h, i) => ({
      key: `status-${i}`,
      at: h.created_at,
      label: `${h.previous_status ? `${statusLabel(h.previous_status)} → ` : ""}${statusLabel(h.new_status)}`,
      text: h.note,
      source: h.source,
    })),
    ...row.events.map((e) => ({
      key: e.id,
      at: e.created_at,
      label: statusLabel(e.kind),
      text: e.text,
      source: "USER",
    })),
  ].sort((a, b) => a.at.localeCompare(b.at));
  return (
    <>
      <Link href="/applications">← Applications</Link>
      <section className="dashboard-heading">
        <p className="eyebrow">{row.company}</p>
        <h1>{row.title}</h1>
        <p className="application-status">{statusLabel(row.status)}</p>
        <p>
          Applied: {row.applied_at ? stamp(row.applied_at) : "Not yet recorded"}
        </p>
        <a href={row.application_url} target="_blank" rel="noopener noreferrer">
          Open application listing ↗
        </a>
      </section>
      <p role="status" aria-live="polite">
        {message}
      </p>
      {row.follow_up_suggestion && (
        <aside className="panel application-attention">
          <h2>{row.follow_up_suggestion}</h2>
          <p>
            No activity has been recorded for {row.follow_up_days} days. Review
            the timeline before reaching out.
          </p>
        </aside>
      )}
      <div className="dashboard-cards">
        <section className="panel">
          <h2>Update status</h2>
          <form
            className="application-form"
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              void save("/status", "POST", {
                expected_revision: row.revision,
                status: target,
                note: f.get("note"),
                resume_version_id: f.get("resume") || null,
                confirm_applied: f.get("confirm") === "on",
              });
            }}
          >
            <label htmlFor="application-status">New status</label>
            <select
              id="application-status"
              value={target}
              onChange={(e) => setTarget(e.target.value as Detail["status"])}
            >
              {statuses.map((s) => (
                <option key={s} value={s}>
                  {statusLabel(s)}
                </option>
              ))}
            </select>
            {target === "APPLIED" && !row.applied_at && (
              <>
                <label htmlFor="application-resume">Resume used</label>
                <select
                  id="application-resume"
                  name="resume"
                  required
                  defaultValue=""
                >
                  <option value="" disabled>
                    Choose the version you submitted
                  </option>
                  {resumes
                    .filter((r) => r.confirmed)
                    .map((r) => (
                      <option key={r.id} value={r.id}>
                        Version {r.version} · {r.filename}
                      </option>
                    ))}
                </select>
                {!resumes.some((r) => r.confirmed) && (
                  <p>
                    <Link href="/settings">Upload and confirm a resume</Link>{" "}
                    before recording submission.
                  </p>
                )}
                <label className="checkbox-label">
                  <input name="confirm" type="checkbox" required />I submitted
                  this application myself.
                </label>
              </>
            )}
            <label htmlFor="application-status-note">
              Status note (optional)
            </label>
            <textarea
              id="application-status-note"
              name="note"
              maxLength={6000}
            />
            <button disabled={busy || target === row.status}>
              {target === "APPLIED" && !row.applied_at
                ? "Mark as Applied"
                : "Save status"}
            </button>
          </form>
        </section>
        <section className="panel">
          <h2>Next action</h2>
          <form
            className="application-form"
            key={`${row.next_action}-${row.next_action_date}-${row.follow_up_days}`}
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              void save("/action", "PUT", {
                expected_revision: row.revision,
                next_action: f.get("action"),
                next_action_date: f.get("date") || null,
                follow_up_days: Number(f.get("days")),
              });
            }}
          >
            <label htmlFor="next-action">What’s next?</label>
            <input
              id="next-action"
              name="action"
              maxLength={500}
              defaultValue={row.next_action}
            />
            <label htmlFor="next-action-date">Next action date</label>
            <input
              id="next-action-date"
              type="date"
              name="date"
              defaultValue={row.next_action_date || ""}
            />
            <label htmlFor="follow-up-days">
              Suggest follow-up after inactivity (days)
            </label>
            <input
              id="follow-up-days"
              type="number"
              name="days"
              min={1}
              max={90}
              required
              defaultValue={row.follow_up_days}
            />
            <p>
              Suggestions appear while Applied. You decide whether to contact
              anyone.
            </p>
            <button disabled={busy}>Save next action</button>
          </form>
        </section>
        <section className="panel">
          <h2>Notes & deadlines</h2>
          <form
            className="application-form"
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              void save("/events", "POST", {
                kind: f.get("kind"),
                text: f.get("text"),
                due_date: f.get("due") || null,
              });
            }}
          >
            <label htmlFor="event-kind">Entry type</label>
            <select id="event-kind" name="kind">
              <option value="NOTE">Note</option>
              <option value="ASSESSMENT">Assessment deadline</option>
              <option value="INTERVIEW">Interview</option>
              <option value="APPLICATION_DEADLINE">Application deadline</option>
              <option value="FOLLOW_UP">Follow-up</option>
              <option value="OTHER">Other deadline</option>
            </select>
            <label htmlFor="event-text">Note or event details</label>
            <textarea id="event-text" name="text" maxLength={6000} required />
            <label htmlFor="event-due">Due date (required for deadlines)</label>
            <input id="event-due" name="due" type="date" />
            <button disabled={busy}>Add entry</button>
          </form>
          <ul className="application-events">
            {row.events
              .filter((e) => e.due_date)
              .map((e) => (
                <li key={e.id}>
                  <strong>{statusLabel(e.kind)}</strong>
                  <p>
                    {e.text} · {e.due_date}{" "}
                    {e.completed_at ? "· Completed" : ""}
                  </p>
                  <button
                    disabled={busy}
                    onClick={() =>
                      void save(
                        `/events/${e.id}?completed=${!e.completed_at}`,
                        "PATCH",
                      )
                    }
                  >
                    {e.completed_at ? "Reopen deadline" : "Complete deadline"}
                  </button>
                </li>
              ))}
          </ul>
        </section>
        <section className="panel">
          <h2>Resume used</h2>
          {row.resume ? (
            <p>
              Version {row.resume.version} · {row.resume.filename}{" "}
              <a href={`/backend/resumes/${row.resume.id}/download`}>
                Download resume
              </a>
            </p>
          ) : (
            <p>
              Choose the resume version when you mark this application as
              applied.
            </p>
          )}
          <h2>
            Match at {row.applied_at ? "application" : "preparation"} time
          </h2>
          {row.match ? (
            <>
              <p>
                Resume Match {row.match.result.resume_match}/100 · Application
                Priority {row.match.result.application_priority}/100
              </p>
              <p>
                {statusLabel(row.match.result.recommendation)} ·{" "}
                {statusLabel(row.match.result.eligibility)}
              </p>
              <p>
                Calculated {stamp(row.match.calculated_at)} · Profile version{" "}
                {row.match.profile_revision}
              </p>
              {row.match.result.explanation && (
                <>
                  <h3>Evidence & cautions</h3>
                  <ul>
                    {[
                      ...row.match.result.explanation.strong_matches,
                      ...row.match.result.explanation.partial_matches,
                      ...row.match.result.explanation.missing_qualifications,
                      ...row.match.result.explanation.eligibility_warnings,
                    ].map((text, i) => (
                      <li key={i}>{text}</li>
                    ))}
                  </ul>
                  <p>{row.match.result.explanation.experience_fit}</p>
                  <p>{row.match.result.explanation.education_fit}</p>
                  <p>{row.match.result.explanation.recommended_action}</p>
                </>
              )}
            </>
          ) : (
            <p>
              No permitted match was recorded for this snapshot.{" "}
              <Link href={`/jobs/${row.job_id}`}>View the current match</Link>.
            </p>
          )}
          <p>
            Contacts and generated materials will be available in later phases.
          </p>
        </section>
      </div>
      <section className="panel job-history">
        <h2>Timeline</h2>
        <ol className="application-timeline">
          {timeline.map((e) => (
            <li key={e.key}>
              <strong>{e.label}</strong>
              <p>
                <time dateTime={e.at}>{stamp(e.at)}</time> ·{" "}
                {e.source === "USER" ? "Recorded by you" : e.source}
              </p>
              {e.text && <p className="job-text">{e.text}</p>}
            </li>
          ))}
        </ol>
      </section>
      <section className="panel job-history">
        <h2>Archived job snapshots</h2>
        <p>
          Captured when tracking begins, preparation begins, and on first
          submission. Source storage restrictions apply to these archives.
        </p>
        {row.snapshots.map((s) => (
          <details key={s.stage} open>
            <summary>
              {statusLabel(s.stage)} · Listing version {s.job_revision} ·{" "}
              {stamp(s.created_at)}
            </summary>
            <h3>
              {s.data.title} · {s.data.company}
            </h3>
            <p>{s.data.location || "Location unknown"}</p>
            {s.restriction && (
              <p className="application-attention">{s.restriction}</p>
            )}
            <p className="job-text">
              {s.data.description ||
                "Description unavailable: no permitted description was captured."}
            </p>
            {s.data.responsibilities && (
              <p className="job-text">{s.data.responsibilities}</p>
            )}
            {s.data.requirements && (
              <p className="job-text">{s.data.requirements}</p>
            )}
            <a
              href={s.data.application_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Original application URL ↗
            </a>
            <ul>
              {s.data.sources.map((source, i) => (
                <li key={i}>
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {source.attribution} ↗
                  </a>
                </li>
              ))}
            </ul>
          </details>
        ))}
      </section>
    </>
  );
}
