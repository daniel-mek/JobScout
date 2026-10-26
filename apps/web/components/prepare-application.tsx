"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { applicationDetailSchema } from "@/lib/application-contracts";

export function PrepareApplication({ jobId }: { jobId: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function prepare() {
    setBusy(true);
    setError("");
    try {
      const row = await api("/applications", applicationDetailSchema, {
        method: "POST",
        body: JSON.stringify({ job_id: jobId }),
      });
      router.push(`/applications/${row.id}`);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not prepare application.",
      );
      setBusy(false);
    }
  }
  return (
    <section className="panel application-prep">
      <h2>Track this opportunity</h2>
      <p>
        Prepare an application and keep a snapshot of the listing. Complete the
        external submission yourself, then record it here.
      </p>
      <button disabled={busy} onClick={() => void prepare()}>
        Prepare Application
      </button>
      {error && <p role="alert">{error}</p>}
    </section>
  );
}
