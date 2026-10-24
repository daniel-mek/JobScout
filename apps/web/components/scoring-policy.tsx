"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import {
  scoringSchema,
  ScoringPolicy as Policy,
} from "@/lib/scoring-contracts";

export function ScoringPolicy({ initial }: { initial: Policy }) {
  const [policy, setPolicy] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      const result = await api("/scoring-policy", scoringSchema, {
        method: "PUT",
        body: JSON.stringify({
          expected_revision: policy.revision,
          weights: policy.weights,
          priority_weights: policy.priority_weights,
        }),
      });
      setPolicy(result);
      setMessage(
        "Scoring weights saved. Current matches refresh on calculation or the next worker cycle.",
      );
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Could not save scoring weights.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <details className="panel job-history">
      <summary>Scoring weights</summary>
      <p>
        Each group must total 100. Unknown facts remain neutral and hard
        disqualification always caps priority, regardless of weights.
      </p>
      <form onSubmit={(event) => void save(event)}>
        {(["weights", "priority_weights"] as const).map((group) => (
          <fieldset key={group}>
            <legend>
              {group === "weights" ? "Resume Match" : "Application Priority"}
            </legend>
            {Object.entries(policy[group]).map(([key, value]) => (
              <label key={key}>
                {group === "weights" ? "Resume" : "Priority"} {key}
                <input
                  required
                  type="number"
                  min={0}
                  max={100}
                  step={1}
                  value={value}
                  onChange={(event) =>
                    setPolicy((previous) => ({
                      ...previous,
                      [group]: {
                        ...previous[group],
                        [key]: Number(event.target.value),
                      },
                    }))
                  }
                />
              </label>
            ))}
            <p>
              Total:{" "}
              {Object.values(policy[group]).reduce(
                (sum, value) => sum + value,
                0,
              )}
            </p>
          </fieldset>
        ))}
        <button disabled={busy}>Save scoring weights</button>
        <p role="status">{message}</p>
      </form>
    </details>
  );
}
