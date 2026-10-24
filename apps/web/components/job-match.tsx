"use client";

import { useState } from "react";
import { z } from "zod";
import { api } from "@/lib/api";

const schema = z.object({
  algorithm_version: z.string(),
  profile_revision: z.number(),
  result: z.object({
    eligibility: z.string(),
    early_career: z.string(),
    resume_match: z.number(),
    application_priority: z.number(),
    recommendation: z.string(),
    components: z.record(z.string(), z.number()),
    priority_components: z.record(z.string(), z.number()),
    weights: z.record(z.string(), z.number()),
    priority_weights: z.record(z.string(), z.number()),
    explanation: z.object({
      strong_matches: z.array(z.string()),
      partial_matches: z.array(z.string()),
      missing_qualifications: z.array(z.string()),
      eligibility_warnings: z.array(z.string()),
      experience_fit: z.string(),
      education_fit: z.string(),
      location_fit: z.string(),
      recommended_action: z.string(),
    }),
  }),
});

export function JobMatch({ id }: { id: string }) {
  const [match, setMatch] = useState<z.infer<typeof schema> | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function calculate() {
    setBusy(true);
    setError("");
    try {
      setMatch(await api(`/jobs/${id}/match`, schema, { method: "POST" }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not calculate match.");
    } finally {
      setBusy(false);
    }
  }
  const result = match?.result;
  return (
    <section className="panel job-history">
      <h2>Your match</h2>
      <p>
        Deterministic evidence-based assessment. Unknown components use a
        neutral 50; scores are provisional, not interview probabilities.
      </p>
      <button disabled={busy} onClick={() => void calculate()}>
        {busy ? "Calculating…" : "Calculate current match"}
      </button>
      {error && <p role="alert">{error}</p>}
      {result && (
        <div aria-live="polite">
          <h3>
            Resume Match: {result.resume_match}/100 · Application Priority:{" "}
            {result.application_priority}/100
          </h3>
          <p>
            {result.eligibility} · {result.early_career} ·{" "}
            {result.recommendation}
          </p>
          <h3>Eligibility warnings</h3>
          {result.explanation.eligibility_warnings.map((line, i) => (
            <p key={i}>{line}</p>
          ))}
          <h3>Strong matches</h3>
          {result.explanation.strong_matches.map((line, i) => (
            <p key={i}>{line}</p>
          ))}
          <h3>Partial matches</h3>
          {result.explanation.partial_matches.map((line, i) => (
            <p key={i}>{line}</p>
          ))}
          <h3>Missing qualifications</h3>
          {result.explanation.missing_qualifications.map((line, i) => (
            <p key={i}>{line}</p>
          ))}
          <p>{result.explanation.experience_fit}</p>
          <p>{result.explanation.education_fit}</p>
          <p>{result.explanation.location_fit}</p>
          <p>{result.explanation.recommended_action}</p>
          <details>
            <summary>Score breakdown and versions</summary>
            <p>
              Profile revision {match.profile_revision} ·{" "}
              {match.algorithm_version}
            </p>
            <h3>Resume components</h3>
            {Object.entries(result.components).map(([key, value]) => (
              <p key={key}>
                {key}: {value} · weight {result.weights[key]}%
              </p>
            ))}
            <h3>Priority components</h3>
            {Object.entries(result.priority_components).map(([key, value]) => (
              <p key={key}>
                {key}: {value} · weight {result.priority_weights[key]}%
              </p>
            ))}
          </details>
        </div>
      )}
    </section>
  );
}
