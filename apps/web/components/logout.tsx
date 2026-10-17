"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { z } from "zod";
import { api } from "@/lib/api";
export function Logout() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <div>
      <button
        className="secondary small"
        disabled={busy}
        onClick={async () => {
          setBusy(true);
          try {
            await api("/auth/logout", z.object({ ok: z.boolean() }), {
              method: "POST",
            });
            router.replace("/login");
            router.refresh();
          } catch {
            setError("Could not sign out. Try again.");
            setBusy(false);
          }
        }}
      >
        {busy ? "Signing out…" : "Sign out"}
      </button>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
