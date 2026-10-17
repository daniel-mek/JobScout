"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { currentProfileSchema, type Profile } from "@/lib/contracts";

const groups = {
  education: {
    title: "Education",
    fields: {
      institution: "Institution",
      degree: "Degree / field of study",
      graduation_date: "Graduation date",
      evidence: "Source evidence",
    },
  },
  experience: {
    title: "Experience",
    fields: {
      employer: "Employer",
      title: "Title",
      dates: "Dates",
      description: "Responsibilities and achievements",
      evidence: "Source evidence",
    },
  },
  projects: {
    title: "Projects",
    fields: {
      name: "Project name",
      description: "Description",
      technologies: "Technologies",
      evidence: "Source evidence",
    },
  },
  skills: {
    title: "Skills",
    fields: {
      name: "Skill",
      category: "Category",
      evidence: "Source evidence",
      evidence_ref: "Evidence link (experience:0 or project:0)",
    },
  },
  certifications: {
    title: "Certifications",
    fields: {
      name: "Certification",
      issuer: "Issuer",
      date: "Date",
      evidence: "Source evidence",
    },
  },
} as const;
type Group = keyof typeof groups;
const empty = {
  education: { institution: "", degree: "", graduation_date: "", evidence: "" },
  experience: {
    employer: "",
    title: "",
    dates: "",
    description: "",
    evidence: "",
  },
  projects: { name: "", description: "", technologies: "", evidence: "" },
  skills: {
    name: "",
    category: "other" as const,
    evidence: "",
    evidence_ref: "",
    confidence: null,
  },
  certifications: { name: "", issuer: "", date: "", evidence: "" },
};
export function ProfileEditor({
  initial,
  revision,
  versionId,
  extractedText,
}: {
  initial: Profile;
  revision: number;
  versionId: string;
  extractedText: string;
}) {
  const router = useRouter();
  const [profile, setProfile] = useState(initial);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  function change(group: Group, index: number, field: string, value: string) {
    setProfile((p) => ({
      ...p,
      [group]: p[group].map((item, i) =>
        i === index ? { ...item, [field]: value } : item,
      ),
    }));
  }
  function remove(group: Group, index: number) {
    setProfile((p) => {
      const next = { ...p, [group]: p[group].filter((_, i) => i !== index) };
      if (group === "experience" || group === "projects") {
        const kind = group === "projects" ? "project" : "experience";
        next.skills = p.skills.map((s) => {
          if (!s.evidence_ref.startsWith(kind + ":")) return s;
          const n = Number(s.evidence_ref.split(":")[1]);
          return {
            ...s,
            evidence_ref: n === index ? "" : `${kind}:${n > index ? n - 1 : n}`,
          };
        });
      }
      return next;
    });
  }
  async function save(e: React.SubmitEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/profile", currentProfileSchema, {
        method: "PUT",
        body: JSON.stringify({
          expected_revision: revision,
          resume_version_id: versionId,
          profile,
          confirmed: true,
        }),
      });
      router.replace("/onboarding");
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save.");
      setBusy(false);
    }
  }
  return (
    <form onSubmit={save} className="stack">
      <div className="notice">
        We extracted the following information from your resume. Review it
        before we use it for job matching. The development parser groups literal
        text; fill in blank fields and split combined entries where needed.
      </div>
      <details className="source">
        <summary>Read extracted resume text</summary>
        <pre>{extractedText}</pre>
      </details>
      <div className="field-grid">
        <label>
          Full name
          <input
            value={profile.name}
            onChange={(e) => setProfile({ ...profile, name: e.target.value })}
            maxLength={200}
          />
        </label>
        <label>
          General location
          <input
            value={profile.location}
            onChange={(e) =>
              setProfile({ ...profile, location: e.target.value })
            }
            maxLength={200}
          />
        </label>
        <label>
          Graduation date
          <input
            value={profile.graduation_date}
            onChange={(e) =>
              setProfile({ ...profile, graduation_date: e.target.value })
            }
            placeholder="Month and year, if applicable"
            maxLength={80}
          />
        </label>
      </div>
      <label>
        Professional summary
        <textarea
          value={profile.summary}
          onChange={(e) => setProfile({ ...profile, summary: e.target.value })}
          maxLength={6000}
        />
      </label>
      {(Object.keys(groups) as Group[]).map((group) => (
        <section key={group} className="review-section">
          <div className="section-heading">
            <h3>{groups[group].title}</h3>
            <button
              type="button"
              className="secondary small"
              onClick={() =>
                setProfile((p) => ({
                  ...p,
                  [group]: [...p[group], { ...empty[group] }],
                }))
              }
            >
              <Plus size={15} /> Add{" "}
              {group === "education"
                ? "education"
                : group === "experience"
                  ? "experience"
                  : group === "projects"
                    ? "project"
                    : group === "skills"
                      ? "skill"
                      : "certification"}
            </button>
          </div>
          {profile[group].length === 0 && (
            <p className="hint">
              Nothing extracted. Add information only if it’s part of your
              experience.
            </p>
          )}
          {profile[group].map((item, index) => (
            <fieldset key={index} className="record">
              <legend>
                {groups[group].title} {index + 1}
              </legend>
              <div className="record-fields">
                {Object.entries(groups[group].fields).map(([field, label]) => {
                  const value = String(
                    (item as unknown as Record<string, unknown>)[field] ?? "",
                  );
                  return (
                    <label key={field}>
                      {label}
                      {field === "category" ? (
                        <select
                          value={value}
                          onChange={(e) =>
                            change(group, index, field, e.target.value)
                          }
                        >
                          {[
                            "language",
                            "framework",
                            "database",
                            "cloud",
                            "operating_system",
                            "tool",
                            "other",
                          ].map((v) => (
                            <option key={v} value={v}>
                              {v.replace("_", " ")}
                            </option>
                          ))}
                        </select>
                      ) : ["description", "evidence"].includes(field) ? (
                        <textarea
                          value={value}
                          onChange={(e) =>
                            change(group, index, field, e.target.value)
                          }
                          maxLength={field === "evidence" ? 4000 : 6000}
                        />
                      ) : (
                        <input
                          value={value}
                          onChange={(e) =>
                            change(group, index, field, e.target.value)
                          }
                          maxLength={
                            field === "technologies"
                              ? 500
                              : field === "evidence_ref"
                                ? 80
                                : 200
                          }
                        />
                      )}
                    </label>
                  );
                })}
              </div>
              <button
                type="button"
                className="text-button danger"
                aria-label={`Remove ${group} ${index + 1}`}
                onClick={() => remove(group, index)}
              >
                <Trash2 size={14} /> Remove
              </button>
            </fieldset>
          ))}
        </section>
      ))}
      <label className="check">
        <input type="checkbox" required /> I reviewed this profile and confirm
        it accurately represents my experience.
      </label>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <button disabled={busy}>
        {busy ? "Saving your profile…" : "Confirm profile & continue"}
      </button>
    </form>
  );
}
