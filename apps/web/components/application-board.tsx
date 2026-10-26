"use client";
import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { z } from "zod";
import { api } from "@/lib/api";
import {
  Application,
  Status,
  applicationDetailSchema,
  applicationListSchema,
  statuses,
  statusLabel,
} from "@/lib/application-contracts";

export function ApplicationBoard({
  data,
  filters,
}: {
  data: z.infer<typeof applicationListSchema>;
  filters: Record<string, string>;
}) {
  const [mode, setMode] = useState("board");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const router = useRouter();
  async function move(row: Application, status: Status) {
    if (row.status === status || busy) return;
    if (status === "APPLIED" && !row.applied_at) {
      router.push(`/applications/${row.id}`);
      return;
    }
    setBusy(true);
    setMessage("");
    try {
      await api(`/applications/${row.id}/status`, applicationDetailSchema, {
        method: "POST",
        body: JSON.stringify({ expected_revision: row.revision, status }),
      });
      setMessage(`${row.title} moved to ${statusLabel(status)}.`);
      router.refresh();
    } catch (e) {
      setMessage(
        e instanceof Error ? e.message : "Could not move application.",
      );
    } finally {
      setBusy(false);
    }
  }
  const pageLink = (offset: number) =>
    `/applications?${new URLSearchParams({ ...filters, offset: String(offset) })}`;
  function menu(row: Application) {
    return (
      <label className="status-menu">
        Move {row.title}
        <select
          aria-label={`Move ${row.title}`}
          disabled={busy}
          value={row.status}
          onChange={(e) => void move(row, e.target.value as Status)}
        >
          {statuses.map((s) => (
            <option key={s} value={s}>
              {statusLabel(s)}
            </option>
          ))}
        </select>
      </label>
    );
  }
  return (
    <>
      <form className="application-filters" action="/applications">
        <label>
          Company
          <input
            name="company"
            defaultValue={filters.company || ""}
            maxLength={200}
          />
        </label>
        <label>
          Role
          <input
            name="role"
            defaultValue={filters.role || ""}
            maxLength={300}
          />
        </label>
        <label>
          Status
          <select name="status" defaultValue={filters.status || ""}>
            <option value="">All statuses</option>
            {statuses.map((s) => (
              <option key={s} value={s}>
                {statusLabel(s)}
              </option>
            ))}
          </select>
        </label>
        <button>Filter applications</button>
        <Link href="/applications">Reset</Link>
      </form>
      <div className="job-buttons">
        <button
          aria-pressed={mode === "board"}
          onClick={() => setMode("board")}
        >
          Kanban view
        </button>
        <button aria-pressed={mode === "list"} onClick={() => setMode("list")}>
          List view
        </button>
        <a
          className="button-link"
          href="/backend/applications/export.csv"
          download
        >
          Export CSV
        </a>
      </div>
      <p role="status" aria-live="polite">
        {message}
      </p>
      <p>
        {data.total} applications · Showing{" "}
        {data.items.length ? data.offset + 1 : 0}–
        {data.offset + data.items.length}. Use each card’s move menu with a
        keyboard, or drag cards between columns. New submissions are confirmed
        on the application page.
      </p>
      {data.items.length === 0 && (
        <section className="panel">
          <h2>No applications here yet</h2>
          <p>Open a job and choose Prepare Application to start tracking.</p>
          <Link href="/discover">Explore opportunities</Link>
        </section>
      )}
      {mode === "board" ? (
        <div className="application-board" aria-label="Application pipeline">
          {statuses.map((s) => (
            <section
              className="pipeline-column"
              key={s}
              aria-label={statusLabel(s)}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                const row = data.items.find(
                  (r) => r.id === e.dataTransfer.getData("text/plain"),
                );
                if (row) void move(row, s);
              }}
            >
              <h2>
                {statusLabel(s)}{" "}
                <span>{data.items.filter((r) => r.status === s).length}</span>
              </h2>
              {data.items
                .filter((r) => r.status === s)
                .map((row) => (
                  <article
                    key={row.id}
                    className="pipeline-card"
                    draggable={!busy}
                    onDragStart={(e) =>
                      e.dataTransfer.setData("text/plain", row.id)
                    }
                  >
                    <p className="eyebrow">{row.company}</p>
                    <h3>
                      <Link href={`/applications/${row.id}`}>{row.title}</Link>
                    </h3>
                    <p>
                      Match: {row.match?.result.resume_match ?? "Not recorded"}
                    </p>
                    {row.next_action && <p>{row.next_action}</p>}
                    {row.due_date && <p>Due {row.due_date}</p>}
                    {row.follow_up_suggestion && (
                      <p className="application-attention">
                        {row.follow_up_suggestion}
                      </p>
                    )}
                    {menu(row)}
                  </article>
                ))}
            </section>
          ))}
        </div>
      ) : (
        <div className="application-table">
          <table>
            <caption>Application tracking</caption>
            <thead>
              <tr>
                {[
                  "Company",
                  "Role",
                  "Status",
                  "Applied",
                  "Match",
                  "Next action",
                  "Due",
                ].map((h) => (
                  <th scope="col" key={h}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.items.map((r) => (
                <tr key={r.id}>
                  <td>{r.company}</td>
                  <th scope="row">
                    <Link href={`/applications/${r.id}`}>{r.title}</Link>
                  </th>
                  <td>{menu(r)}</td>
                  <td>{r.applied_at?.slice(0, 10) || "Not applied"}</td>
                  <td>{r.match?.result.resume_match ?? "Not recorded"}</td>
                  <td>{r.next_action || r.follow_up_suggestion || "—"}</td>
                  <td>{r.due_date || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <nav className="job-buttons" aria-label="Application pages">
        {data.offset > 0 && (
          <Link href={pageLink(Math.max(0, data.offset - data.limit))}>
            Previous applications
          </Link>
        )}
        {data.offset + data.limit < data.total && (
          <Link href={pageLink(data.offset + data.limit)}>
            Next applications
          </Link>
        )}
      </nav>
    </>
  );
}
