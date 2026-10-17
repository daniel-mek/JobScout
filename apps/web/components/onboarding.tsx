"use client";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useState } from "react";
import { ArrowUpRight, Check, FileText, UploadCloud } from "lucide-react";
import { api } from "@/lib/api";
import {
  detailSchema,
  stateSchema,
  steps,
  type OnboardingState,
  type Preferences,
  type Requirements,
  type Step,
  type Profile,
} from "@/lib/contracts";
import { ProfileEditor } from "./profile-editor";

const labels = {
  upload: "Bring your resume",
  review: "Make it yours",
  paths: "Choose your direction",
  preferences: "Set your preferences",
  requirements: "Draw your boundaries",
};
const subtitles = {
  upload: "Start with what you’ve already accomplished.",
  review: "Your story, with every detail in the right place.",
  paths: "Choose the work you want to grow into.",
  preferences: "What would your ideal opportunity look like?",
  requirements: "Tell us what an opportunity must respect.",
};
const list = (value: FormDataEntryValue | null) =>
  String(value || "")
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);
const tri = (value: FormDataEntryValue | null) =>
  value === "yes" ? true : value === "no" ? false : null;
function Choice({
  name,
  label,
  value,
}: {
  name: string;
  label: string;
  value: boolean | null;
}) {
  return (
    <label>
      {label}
      <select
        name={name}
        defaultValue={value === null ? "unknown" : value ? "yes" : "no"}
      >
        <option value="unknown">Not specified</option>
        <option value="yes">Yes</option>
        <option value="no">No</option>
      </select>
    </label>
  );
}
export function Onboarding({
  state,
  step,
  roles,
  detail,
}: {
  state: OnboardingState;
  step: Step;
  roles: { id: string; name: string }[];
  detail: { draft: Profile; extracted_text: string } | null;
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState(state.role_ids);
  const index = steps.indexOf(step);
  const prefs: Preferences = state.preferences || {
    locations: [],
    arrangements: [],
    minimum_salary: null,
    currency: "USD",
    industries: [],
    companies: [],
  };
  const hard: Requirements = state.requirements || {
    max_requested_experience: null,
    allow_clearance: null,
    allow_contract: null,
    allow_relocation: null,
    countries: [],
    needs_sponsorship: null,
    authorized_to_work: null,
  };
  async function submit(e: React.SubmitEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    setBusy(true);
    const form = new FormData(e.currentTarget);
    try {
      if (step === "upload") {
        const file = form.get("resume");
        if (!(file instanceof File) || !file.size)
          throw new Error("Choose a PDF or DOCX first.");
        if (file.size > 5 * 1024 * 1024)
          throw new Error("Choose a file smaller than 5 MB.");
        const body = new FormData();
        body.set("file", file);
        await api("/resumes", detailSchema, { method: "POST", body });
      } else if (step === "paths") {
        await api("/career-preferences", stateSchema, {
          method: "PUT",
          body: JSON.stringify({ role_ids: selected }),
        });
      } else if (step === "preferences") {
        await api("/preferences", stateSchema, {
          method: "PUT",
          body: JSON.stringify({
            locations: list(form.get("locations")),
            arrangements: form.getAll("arrangement"),
            minimum_salary: form.get("salary")
              ? Number(form.get("salary"))
              : null,
            currency: form.get("currency"),
            industries: list(form.get("industries")),
            companies: list(form.get("companies")),
          }),
        });
      } else if (step === "requirements") {
        await api("/requirements", stateSchema, {
          method: "PUT",
          body: JSON.stringify({
            max_requested_experience: form.get("max_experience")
              ? Number(form.get("max_experience"))
              : null,
            allow_clearance: tri(form.get("clearance")),
            allow_contract: tri(form.get("contract")),
            allow_relocation: tri(form.get("relocation")),
            countries: list(form.get("countries")).map((s) => s.toUpperCase()),
            needs_sponsorship: tri(form.get("sponsorship")),
            authorized_to_work: tri(form.get("authorization")),
          }),
        });
      }
      const fresh = await api("/onboarding", stateSchema);
      if (fresh.complete) {
        await api("/onboarding/complete", stateSchema, { method: "POST" });
        router.replace("/dashboard");
        router.refresh();
      } else {
        router.replace("/onboarding");
        router.refresh();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Please try again.");
      setBusy(false);
    }
  }
  return (
    <div className="onboarding-layout">
      <aside className="onboarding-sidebar">
        <Link href="/" className="wordmark">
          apply<span>os</span>
          <i>↗</i>
        </Link>
        <div>
          <p className="eyebrow">Your starting point</p>
          <h2>
            A stronger search
            <br />
            starts here.
          </h2>
          <p>Take a few minutes to set a foundation that feels like you.</p>
        </div>
        <ol className="steps">
          {steps.map((s, i) => (
            <li
              key={s}
              className={i === index ? "active" : i < index ? "done" : ""}
              aria-current={i === index ? "step" : undefined}
            >
              <span>
                {i < index ? (
                  <Check size={15} />
                ) : (
                  String(i + 1).padStart(2, "0")
                )}
              </span>
              {labels[s]}
            </li>
          ))}
        </ol>
        <div className="sidebar-note">
          <FileText size={19} />
          <p>
            Your original resume stays intact. Every upload is a new version.
          </p>
        </div>
      </aside>
      <main id="main" className="onboarding-main">
        <header className="onboarding-header">
          <p className="eyebrow">Your profile / Step {index + 1} of 5</p>
          <Link href="/settings">
            Account & settings <ArrowUpRight size={14} />
          </Link>
        </header>
        <div className="form-heading">
          <h1>
            {labels[step]}
            <span>.</span>
          </h1>
          <p>{subtitles[step]}</p>
        </div>
        {step === "review" && detail && state.latest_resume ? (
          <ProfileEditor
            initial={detail.draft}
            extractedText={detail.extracted_text}
            revision={state.profile_revision}
            versionId={state.latest_resume.id}
          />
        ) : (
          <form className="stack" onSubmit={submit}>
            {step === "upload" && (
              <>
                <div className="upload-zone">
                  <div className="upload-icon">
                    <UploadCloud size={30} />
                  </div>
                  <h3>A good place to begin.</h3>
                  <p>
                    Upload your master resume. You’ll review everything we
                    extract.
                  </p>
                  <label className="file-label">
                    Choose your resume
                    <input
                      name="resume"
                      type="file"
                      accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                      required
                    />
                  </label>
                  <small>
                    PDF or DOCX · up to 5 MB · text-based, without macros or
                    external document links
                  </small>
                </div>
                <div className="notice">
                  We use a conservative development parser. It may leave fields
                  blank or group entries. You’ll be able to correct everything
                  before it becomes your profile.
                </div>
                {state.latest_resume && (
                  <p className="hint">
                    Current master: {state.latest_resume.filename}, version{" "}
                    {state.latest_resume.version}. Its confirmed profile remains
                    saved until you review the new upload.
                  </p>
                )}
              </>
            )}
            {step === "paths" && (
              <>
                <p className="hint">
                  Choose one or more. You can change these later.
                </p>
                <div className="role-grid">
                  {roles.map((role) => (
                    <label
                      className={`role-choice ${selected.includes(role.id) ? "selected" : ""}`}
                      key={role.id}
                    >
                      <input
                        type="checkbox"
                        checked={selected.includes(role.id)}
                        onChange={(e) =>
                          setSelected(
                            e.target.checked
                              ? [...selected, role.id]
                              : selected.filter((id) => id !== role.id),
                          )
                        }
                      />
                      <span>{role.name}</span>
                      <Check size={17} />
                    </label>
                  ))}
                </div>
              </>
            )}
            {step === "preferences" && (
              <>
                <div className="notice">
                  These are soft preferences. They influence future ranking and
                  won’t silently become hard filters.
                </div>
                <fieldset>
                  <legend>Work arrangement</legend>
                  <div className="inline-checks">
                    {["REMOTE", "HYBRID", "ONSITE"].map((v) => (
                      <label className="check" key={v}>
                        <input
                          type="checkbox"
                          name="arrangement"
                          value={v}
                          defaultChecked={prefs.arrangements.includes(
                            v as (typeof prefs.arrangements)[number],
                          )}
                        />
                        {v === "ONSITE"
                          ? "On site"
                          : v === "HYBRID"
                            ? "Hybrid"
                            : "Remote"}
                      </label>
                    ))}
                  </div>
                </fieldset>
                <label>
                  Preferred locations
                  <input
                    name="locations"
                    defaultValue={prefs.locations.join(", ")}
                    placeholder="Jersey City, New York, US remote"
                  />
                  <span className="hint">Separate locations with commas.</span>
                </label>
                <div className="field-grid">
                  <label>
                    Preferred minimum annual salary
                    <input
                      name="salary"
                      type="number"
                      min={0}
                      max={10000000}
                      defaultValue={prefs.minimum_salary ?? ""}
                      placeholder="Optional"
                    />
                  </label>
                  <label>
                    Currency
                    <select name="currency" defaultValue={prefs.currency}>
                      {["USD", "CAD", "EUR", "GBP"].map((v) => (
                        <option key={v}>{v}</option>
                      ))}
                    </select>
                  </label>
                </div>
                <label>
                  Preferred industries
                  <input
                    name="industries"
                    defaultValue={prefs.industries.join(", ")}
                    placeholder="Optional, separated by commas"
                  />
                </label>
                <label>
                  Preferred companies
                  <input
                    name="companies"
                    defaultValue={prefs.companies.join(", ")}
                    placeholder="Optional, separated by commas"
                  />
                </label>
              </>
            )}
            {step === "requirements" && (
              <>
                <div className="notice">
                  Hard requirements can exclude or strongly flag jobs once
                  matching is connected. Nothing is inferred from your resume or
                  behavior. Leave anything uncertain as “Not specified.”
                </div>
                <div className="field-grid">
                  <label>
                    Maximum experience a job may request (years)
                    <input
                      type="number"
                      name="max_experience"
                      min={0}
                      max={50}
                      defaultValue={hard.max_requested_experience ?? ""}
                      placeholder="No cap specified"
                    />
                  </label>
                  <label>
                    Allowed countries
                    <input
                      name="countries"
                      defaultValue={hard.countries.join(", ")}
                      placeholder="US, CA (optional)"
                    />
                  </label>
                  <Choice
                    name="clearance"
                    label="Include clearance-required jobs?"
                    value={hard.allow_clearance}
                  />
                  <Choice
                    name="contract"
                    label="Include contract jobs?"
                    value={hard.allow_contract}
                  />
                  <Choice
                    name="relocation"
                    label="Are you open to relocation?"
                    value={hard.allow_relocation}
                  />
                  <Choice
                    name="sponsorship"
                    label="Do you need employer sponsorship?"
                    value={hard.needs_sponsorship}
                  />
                  <Choice
                    name="authorization"
                    label="Are you authorized to work in your target country?"
                    value={hard.authorized_to_work}
                  />
                </div>
                <p className="hint">
                  These are your search settings, not legal attestations. You’ll
                  answer employer questions yourself.
                </p>
              </>
            )}
            {error && (
              <p className="error" role="alert">
                {error}
              </p>
            )}
            <div className="form-footer">
              <small>Saved to your account when you continue.</small>
              <button
                disabled={busy || (step === "paths" && selected.length === 0)}
              >
                {busy
                  ? "Saving…"
                  : step === "requirements"
                    ? "Finish setup"
                    : "Save & continue"}
                <ArrowUpRight size={17} />
              </button>
            </div>
          </form>
        )}
      </main>
    </div>
  );
}
