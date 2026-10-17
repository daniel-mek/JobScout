import { z } from "zod";
const education = z.object({
  institution: z.string(),
  degree: z.string(),
  graduation_date: z.string(),
  evidence: z.string(),
});
const experience = z.object({
  employer: z.string(),
  title: z.string(),
  dates: z.string(),
  description: z.string(),
  evidence: z.string(),
});
const project = z.object({
  name: z.string(),
  description: z.string(),
  technologies: z.string(),
  evidence: z.string(),
});
const skill = z.object({
  name: z.string(),
  category: z.enum([
    "language",
    "framework",
    "database",
    "cloud",
    "operating_system",
    "tool",
    "other",
  ]),
  evidence: z.string(),
  evidence_ref: z.string(),
  confidence: z.number().nullable(),
});
const certification = z.object({
  name: z.string(),
  issuer: z.string(),
  date: z.string(),
  evidence: z.string(),
});
export const profileSchema = z.object({
  name: z.string(),
  location: z.string(),
  graduation_date: z.string(),
  summary: z.string(),
  education: z.array(education),
  experience: z.array(experience),
  projects: z.array(project),
  skills: z.array(skill),
  certifications: z.array(certification),
});
export type Profile = z.infer<typeof profileSchema>;
export const resumeSchema = z.object({
  id: z.string(),
  version: z.number(),
  filename: z.string(),
  size_bytes: z.number(),
  mime_type: z.string(),
  created_at: z.string(),
  parser: z.string(),
  confirmed: z.boolean(),
});
export type Resume = z.infer<typeof resumeSchema>;
export const preferencesSchema = z.object({
  locations: z.array(z.string()),
  arrangements: z.array(z.enum(["REMOTE", "HYBRID", "ONSITE"])),
  minimum_salary: z.number().nullable(),
  currency: z.enum(["USD", "CAD", "EUR", "GBP"]),
  industries: z.array(z.string()),
  companies: z.array(z.string()),
});
export type Preferences = z.infer<typeof preferencesSchema>;
export const requirementsSchema = z.object({
  max_requested_experience: z.number().nullable(),
  allow_clearance: z.boolean().nullable(),
  allow_contract: z.boolean().nullable(),
  allow_relocation: z.boolean().nullable(),
  countries: z.array(z.string()),
  needs_sponsorship: z.boolean().nullable(),
  authorized_to_work: z.boolean().nullable(),
});
export type Requirements = z.infer<typeof requirementsSchema>;
export const steps = [
  "upload",
  "review",
  "paths",
  "preferences",
  "requirements",
] as const;
export type Step = (typeof steps)[number];
export const stateSchema = z.object({
  next_step: z.enum([...steps, "complete"]),
  complete: z.boolean(),
  latest_resume: resumeSchema.nullable(),
  profile_revision: z.number(),
  role_ids: z.array(z.string()),
  preferences: preferencesSchema.nullable(),
  requirements: requirementsSchema.nullable(),
});
export type OnboardingState = z.infer<typeof stateSchema>;
export const userSchema = z.object({ id: z.string(), email: z.string() });
export const rolesSchema = z.array(
  z.object({ id: z.string(), name: z.string() }),
);
export const detailSchema = z.object({
  resume: resumeSchema,
  draft: profileSchema,
  extracted_text: z.string(),
  confirmed_profile: profileSchema.nullable().optional(),
});
export const currentProfileSchema = z.object({
  revision: z.number(),
  profile: profileSchema.nullable(),
  resume_version_id: z.string().optional(),
});
export const dashboardSchema = z.object({
  account: z.object({ email: z.string() }),
  onboarding: stateSchema,
  profile: currentProfileSchema,
  resume_versions: z.number(),
  notice: z.string(),
});
