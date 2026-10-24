"use client";
import Link from "next/link";
import { useState } from "react";
import { z } from "zod";
import { api } from "@/lib/api";
const schema = z.object({
  id: z.string(),
  name: z.string(),
  filters: z.record(z.string(), z.union([z.string(), z.number(), z.boolean()])),
});
export function SavedDiscoverySearches({
  initial,
  query,
}: {
  initial: z.infer<typeof schema>[];
  query: Record<string, string>;
}) {
  const [items, setItems] = useState(initial);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <section className="panel job-history">
      <h2>Saved discovery searches</h2>
      <form
        onSubmit={async (event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          setBusy(true);
          try {
            const item = await api("/discovery-searches", schema, {
              method: "POST",
              body: JSON.stringify({ name: form.get("name"), filters: query }),
            });
            setItems((values) => [...values, item]);
            setMessage("Search saved.");
          } catch (e) {
            setMessage(
              e instanceof Error ? e.message : "Could not save search.",
            );
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          Search name
          <input name="name" required maxLength={120} />
        </label>
        <button disabled={busy}>Save current filters</button>
      </form>
      <p role="status">{message}</p>
      {items.map((item) => (
        <p key={item.id}>
          <Link
            href={`/discover?${new URLSearchParams(Object.fromEntries(Object.entries(item.filters).map(([key, value]) => [key, String(value)])))}`}
          >
            {item.name}
          </Link>{" "}
          <button
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await api(
                  `/discovery-searches/${item.id}`,
                  z.object({ deleted: z.boolean() }),
                  { method: "DELETE" },
                );
                setItems((values) => values.filter((x) => x.id !== item.id));
              } catch (e) {
                setMessage(
                  e instanceof Error ? e.message : "Could not delete search.",
                );
              } finally {
                setBusy(false);
              }
            }}
          >
            Delete {item.name}
          </button>
        </p>
      ))}
    </section>
  );
}
