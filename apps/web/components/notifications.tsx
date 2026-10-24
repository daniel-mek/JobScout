"use client";
import Link from "next/link";
import { useState } from "react";
import { z } from "zod";
import { api } from "@/lib/api";
type NotificationItem = {
  id: string;
  kind: string;
  job_id: string | null;
  created_at: string;
  read: boolean;
};
const preferenceSchema = z.object({
  disabled_types: z.array(z.string()),
  available_types: z.array(z.string()),
});
export function Notifications({
  initial,
  preferences,
}: {
  initial: NotificationItem[];
  preferences: z.infer<typeof preferenceSchema>;
}) {
  const [items, setItems] = useState(initial);
  const [disabled, setDisabled] = useState(preferences.disabled_types);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <>
      <h1>Notifications</h1>
      <p role="status">{message}</p>
      <details className="panel">
        <summary>Notification preferences</summary>
        <p>Choose which updates appear in your inbox.</p>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            try {
              await api("/notification-preferences", preferenceSchema, {
                method: "PUT",
                body: JSON.stringify(disabled),
              });
              setMessage("Notification preferences saved.");
            } catch (e) {
              setMessage(e instanceof Error ? e.message : "Could not save.");
            } finally {
              setBusy(false);
            }
          }}
        >
          {preferences.available_types.map((kind) => (
            <label key={kind}>
              <input
                type="checkbox"
                checked={!disabled.includes(kind)}
                onChange={(event) =>
                  setDisabled((values) =>
                    event.target.checked
                      ? values.filter((x) => x !== kind)
                      : [...values, kind],
                  )
                }
              />
              {kind.replaceAll("_", " ")}
            </label>
          ))}
          <button disabled={busy}>Save notification preferences</button>
        </form>
      </details>
      {!items.length && <p>No notifications yet.</p>}
      {items.map((item) => (
        <article className="panel job-history" key={item.id}>
          <h2>{item.kind.replaceAll("_", " ")}</h2>
          <p>
            {item.created_at.slice(0, 19)} UTC · {item.read ? "Read" : "Unread"}
          </p>
          {item.job_id && <Link href={`/jobs/${item.job_id}`}>View job</Link>}{" "}
          <button
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await api(
                  `/notifications/${item.id}?read=${!item.read}`,
                  z.object({ id: z.string(), read: z.boolean() }),
                  { method: "PATCH" },
                );
                setItems((values) =>
                  values.map((x) =>
                    x.id === item.id ? { ...x, read: !x.read } : x,
                  ),
                );
              } catch (e) {
                setMessage(
                  e instanceof Error ? e.message : "Could not update.",
                );
              } finally {
                setBusy(false);
              }
            }}
          >
            {item.read ? "Mark unread" : "Mark read"}
          </button>
        </article>
      ))}
    </>
  );
}
