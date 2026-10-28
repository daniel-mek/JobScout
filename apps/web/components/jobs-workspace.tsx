"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { z } from "zod";
import { api } from "@/lib/api";
import {
  Job,
  Source,
  Policy,
  Run,
  SavedSearch,
  jobSchema,
  sourceSchema,
  policySchema,
  runSchema,
  searchSchema,
  jobDetailSchema,
} from "@/lib/jobs-contracts";

type Workspace = {
  jobs: Job[];
  sources: Source[];
  policies: Policy[];
  runs: Run[];
  searches: SavedSearch[];
};
const providers = [
  "greenhouse",
  "lever",
  "ashby",
  "smartrecruiters",
  "usajobs",
  "adzuna",
] as const;
const detection = z.object({
  provider: z.string(),
  board: z.string(),
  supported: z.boolean(),
});
const importResult = z.object({
  status: z.string(),
  job_id: z.string().optional(),
  reason: z.string().optional(),
});

export function JobsWorkspace({ initial }: { initial: Workspace }) {
  const [data, setData] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [url, setUrl] = useState("");
  const [provider, setProvider] = useState<string>("greenhouse");
  const [board, setBoard] = useState("");
  const [sourceURL, setSourceURL] = useState("");
  const [offset, setOffset] = useState(0);
  const router = useRouter();
  function importBlocker(source: Source) {
    if (!source.enabled)
      return "This employer is paused. Enable it to import listings.";
    const policy = data.policies.find((p) => p.id === source.provider);
    if (
      !policy?.enabled ||
      policy.status !== "APPROVED" ||
      !policy.approved_boards.some(
        (board) => board === "*" || board === source.board,
      )
    )
      return "Imports are waiting for source access review. Add individual jobs manually while review is pending.";
    if (source.health.state === "configuration_required")
      return "This source needs server credentials before it can import listings.";
    return "";
  }

  async function refresh(page = offset) {
    const [jobs, sources, policies, runs, searches] = await Promise.all([
      api(`/jobs?offset=${page}`, z.array(jobSchema)),
      api("/sources", z.array(sourceSchema)),
      api("/source-registry", z.array(policySchema)),
      api("/search-runs", z.array(runSchema)),
      api("/saved-searches", z.array(searchSchema)),
    ]);
    setData({ jobs, sources, policies, runs, searches });
    setOffset(page);
  }
  async function perform(work: () => Promise<void>) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await work();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Please try again.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <section className="dashboard-heading">
        <p className="eyebrow">Build your opportunity list</p>
        <h1>
          Jobs & sources<span>.</span>
        </h1>
        <p>
          Import a listing, connect an employer board, and see where every
          detail came from.
        </p>
      </section>
      <div aria-live="polite">
        {message && <p className="ready-banner">{message}</p>}
      </div>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <div className="jobs-tools" aria-busy={busy}>
        <section className="panel" id="add-job">
          <h2>Add a job</h2>
          <p>Try a supported employer link, or enter the details yourself.</p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void perform(async () => {
                const result = await api("/jobs/import-url", importResult, {
                  method: "POST",
                  body: JSON.stringify({ url }),
                });
                if (result.job_id) router.push(`/jobs/${result.job_id}`);
                else
                  setMessage(result.reason || "Enter the job details below.");
                await refresh();
              });
            }}
          >
            <label>
              Job URL
              <input
                required
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                maxLength={2000}
              />
            </label>
            <button className="button secondary" disabled={busy}>
              Import supported link
            </button>
          </form>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const form = new FormData(e.currentTarget);
              void perform(async () => {
                const job = await api("/jobs/manual", jobDetailSchema, {
                  method: "POST",
                  body: JSON.stringify({
                    application_url: url,
                    title: form.get("title"),
                    company: form.get("company"),
                    location: form.get("location") || null,
                    description: form.get("description") || null,
                    employment_type: form.get("employment_type") || null,
                  }),
                });
                router.push(`/jobs/${job.id}`);
              });
            }}
          >
            <label>
              Job title
              <input name="title" required maxLength={300} />
            </label>
            <label>
              Company
              <input name="company" required maxLength={200} />
            </label>
            <label>
              Location (optional)
              <input name="location" maxLength={300} />
            </label>
            <label>
              Description (optional)
              <textarea name="description" rows={5} maxLength={60000} />
            </label>
            <label>
              Employment type
              <select name="employment_type" defaultValue="">
                <option value="">Unknown</option>
                <option>Full-time</option>
                <option>Part-time</option>
                <option>Contract</option>
              </select>
            </label>
            <p className="field-hint">
              Use content you are permitted to keep. Your manual imports stay in
              your account.
            </p>
            <button className="button primary" disabled={busy || !url}>
              Save manual job
            </button>
          </form>
        </section>
        <section className="panel" id="connect-source">
          <h2>Connect an employer source</h2>
          <p>Sources need an approved policy before they can fetch listings.</p>
          <label>
            Career page URL (optional)
            <input
              type="url"
              value={sourceURL}
              onChange={(e) => setSourceURL(e.target.value)}
              maxLength={2000}
            />
          </label>
          <button
            className="button secondary"
            disabled={busy || !sourceURL}
            onClick={() =>
              void perform(async () => {
                const result = await api("/career-sites/detect", detection, {
                  method: "POST",
                  body: JSON.stringify({ url: sourceURL }),
                });
                if (result.supported) {
                  setProvider(result.provider);
                  setBoard(result.board);
                  setMessage(
                    "Employer board detected. Add the company name below.",
                  );
                } else
                  setMessage(
                    "Monitoring is unavailable for this site. Use manual job import.",
                  );
              })
            }
          >
            Detect board
          </button>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const form = new FormData(e.currentTarget);
              void perform(async () => {
                await api("/sources", sourceSchema, {
                  method: "POST",
                  body: JSON.stringify({
                    provider,
                    board,
                    company: form.get("company"),
                    url: sourceURL,
                  }),
                });
                setMessage(
                  "Employer connected. Check its import readiness below; connecting alone does not import jobs.",
                );
                await refresh();
              });
            }}
          >
            <label>
              Provider
              <select
                value={provider}
                onChange={(e) => {
                  setProvider(e.target.value);
                  setSourceURL("");
                }}
              >
                {providers.map((p) => (
                  <option key={p}>{p}</option>
                ))}
              </select>
            </label>
            <label>
              Board identifier / search keyword
              <input
                required
                maxLength={100}
                value={board}
                onChange={(e) => setBoard(e.target.value)}
                pattern="(eu:)?[A-Za-z0-9_-]{1,100}"
              />
            </label>
            <label>
              Company / search name
              <input name="company" required maxLength={200} />
            </label>
            <p className="field-hint">
              USAJOBS and Adzuna use a keyword and server credentials. Board IDs
              come from the employer’s public ATS URL.
            </p>
            <button className="button primary" disabled={busy}>
              Add source
            </button>
          </form>
        </section>
      </div>
      <section className="panel job-history">
        <h2>Your sources</h2>
        {!data.sources.length && (
          <p>
            No employer sources connected yet. Manual import works while source
            review is pending.
          </p>
        )}
        {data.sources.map((source) => (
          <div className="source-entry" key={source.id}>
            <strong>{source.company}</strong>
            <p>
              {source.provider} · {source.board} · policy:{" "}
              {source.policy_status}
            </p>
            <p>
              Health: {source.health.state.replaceAll("_", " ")} ·{" "}
              {source.health.code.replaceAll("_", " ")} · Last count:{" "}
              {source.health.last_count}
            </p>
            {source.provider !== "manual" && importBlocker(source) && (
              <p>{importBlocker(source)}</p>
            )}
            {source.health.last_success && (
              <p>
                Last success:{" "}
                {new Date(source.health.last_success).toLocaleString("en-US", {
                  timeZone: "UTC",
                })}{" "}
                UTC
              </p>
            )}
            <div className="job-buttons">
              <button
                className="button secondary"
                disabled={
                  busy ||
                  !!importBlocker(source) ||
                  source.provider === "manual"
                }
                onClick={() =>
                  void perform(async () => {
                    const result = await api("/search-runs", runSchema, {
                      method: "POST",
                      body: JSON.stringify({ source_ids: [source.id] }),
                    });
                    setMessage(
                      result.results
                        .map(
                          (r) =>
                            `${r.count} listings · ${r.code.replaceAll("_", " ")}`,
                        )
                        .join("; "),
                    );
                    await refresh(0);
                  })
                }
              >
                Sync source
              </button>
              {source.provider !== "manual" && (
                <button
                  className="button secondary"
                  disabled={busy}
                  onClick={() =>
                    void perform(async () => {
                      await api(
                        `/sources/${source.id}?enabled=${!source.enabled}`,
                        sourceSchema,
                        { method: "PATCH" },
                      );
                      await refresh();
                    })
                  }
                >
                  {source.enabled ? "Pause" : "Resume"}
                </button>
              )}
              {source.provider !== "manual" && (
                <button
                  className="button secondary"
                  disabled={busy}
                  onClick={() =>
                    void perform(async () => {
                      await api("/saved-searches", searchSchema, {
                        method: "POST",
                        body: JSON.stringify({
                          name: source.company,
                          source_ids: [source.id],
                        }),
                      });
                      setMessage("Search saved. Run it manually below.");
                      await refresh();
                    })
                  }
                >
                  Save search
                </button>
              )}
            </div>
          </div>
        ))}
      </section>
      <section className="panel job-history">
        <h2>Imported jobs</h2>
        {!data.jobs.length && (
          <p>No jobs on this page. Add a job above to start your list.</p>
        )}
        {data.jobs.map((job) => (
          <article className="job-row" key={job.id}>
            <div>
              <Link href={`/jobs/${job.id}`}>
                <strong>{job.title}</strong>
              </Link>
              <p>
                {job.company} · {job.location || "Location unknown"}
              </p>
              <p>
                Source:{" "}
                {job.sources.map((source, i) => (
                  <span key={i}>
                    {i ? " · " : ""}
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {source.attribution} ↗
                    </a>
                  </span>
                ))}
              </p>
            </div>
            <span className="pill">
              {job.active ? "Active" : "Archived"} · v{job.revision}
            </span>
          </article>
        ))}
        <div className="job-buttons">
          <button
            className="button secondary"
            disabled={busy || offset === 0}
            onClick={() =>
              void perform(() => refresh(Math.max(0, offset - 30)))
            }
          >
            Previous jobs
          </button>
          <button
            className="button secondary"
            disabled={busy || data.jobs.length < 30}
            onClick={() => void perform(() => refresh(offset + 30))}
          >
            Next jobs
          </button>
        </div>
      </section>
      <section className="panel job-history">
        <h2>Saved searches & recent runs</h2>
        <p>
          Searches run when you request them. Scheduling comes in a later phase.
        </p>
        {data.searches.map((search) => (
          <div className="source-entry" key={search.id}>
            <strong>{search.name}</strong>{" "}
            <button
              className="button secondary"
              disabled={busy}
              onClick={() =>
                void perform(async () => {
                  await api(`/saved-searches/${search.id}/run`, runSchema, {
                    method: "POST",
                  });
                  await refresh(0);
                })
              }
            >
              Run saved search
            </button>
          </div>
        ))}
        {data.runs.slice(0, 10).map((run) => (
          <p key={run.id}>
            {new Date(run.started_at).toLocaleString("en-US", {
              timeZone: "UTC",
            })}{" "}
            UTC · {run.state} ·{" "}
            {run.results.map((r) => r.code.replaceAll("_", " ")).join(", ")}
          </p>
        ))}
      </section>
      <details className="panel job-history">
        <summary>Source registry & review evidence</summary>
        <p>
          Only enabled, approved sources can run. Unknown storage permissions
          keep descriptions out of live records and history.
        </p>
        {data.policies.map((policy) => (
          <div className="source-entry" key={policy.id}>
            <strong>
              {policy.display_name} · {policy.status}
            </strong>
            <p>{policy.evidence}</p>
            <p>
              Description storage: {policy.description_storage} ·
              Redistribution: {policy.redistribution} · Attribution:{" "}
              {policy.attribution}
            </p>
            <p>
              Approved boards: {policy.approved_boards.join(", ") || "None"} ·
              Adapter v{policy.adapter_version} · Reviewed:{" "}
              {policy.reviewed_at || "Pending"} · Credentials:{" "}
              {policy.credentials.join(", ") || "None"}
            </p>
            {policy.documentation_url && (
              <a
                href={policy.documentation_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                Official documentation ↗
              </a>
            )}
            {policy.terms_url && (
              <>
                {" "}
                ·{" "}
                <a
                  href={policy.terms_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Reviewed terms ↗
                </a>
              </>
            )}
          </div>
        ))}
      </details>
    </>
  );
}
