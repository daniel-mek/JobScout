import { z } from "zod";

export const statuses = [
  "SAVED",
  "PREPARING",
  "APPLIED",
  "ONLINE_ASSESSMENT",
  "RECRUITER_SCREEN",
  "INTERVIEW",
  "FINAL_INTERVIEW",
  "OFFER",
  "REJECTED",
  "WITHDRAWN",
] as const;
export type Status = (typeof statuses)[number];
export const statusLabel = (value: string) =>
  value.toLowerCase().replaceAll("_", " ");
const match = z
  .object({
    result: z.object({
      resume_match: z.number(),
      application_priority: z.number(),
      eligibility: z.string(),
      recommendation: z.string(),
      explanation: z
        .object({
          strong_matches: z.array(z.string()),
          partial_matches: z.array(z.string()),
          missing_qualifications: z.array(z.string()),
          eligibility_warnings: z.array(z.string()),
          experience_fit: z.string(),
          education_fit: z.string(),
          recommended_action: z.string(),
        })
        .optional(),
    }),
    calculated_at: z.string(),
    profile_revision: z.number(),
    resume_version_id: z.string().nullable(),
    algorithm_version: z.string(),
  })
  .nullable();
export const applicationSchema = z.object({
  id: z.string(),
  job_id: z.string(),
  title: z.string(),
  company: z.string(),
  status: z.enum(statuses),
  revision: z.number(),
  created_at: z.string(),
  updated_at: z.string(),
  applied_at: z.string().nullable(),
  resume_version_id: z.string().nullable(),
  next_action: z.string(),
  next_action_date: z.string().nullable(),
  follow_up_days: z.number(),
  due_date: z.string().nullable(),
  follow_up_suggestion: z.string().nullable(),
  application_url: z.string(),
  match,
});
export const applicationListSchema = z.object({
  total: z.number(),
  offset: z.number(),
  limit: z.number(),
  as_of: z.string(),
  items: z.array(applicationSchema),
});
export const applicationDetailSchema = applicationSchema.extend({
  resume: z
    .object({ id: z.string(), version: z.number(), filename: z.string() })
    .nullable(),
  snapshots: z.array(
    z.object({
      stage: z.string(),
      job_revision: z.number(),
      created_at: z.string(),
      restriction: z.string().nullable(),
      match,
      data: z.object({
        title: z.string(),
        company: z.string(),
        application_url: z.string(),
        location: z.string().nullable().optional(),
        description: z.string().nullable().optional(),
        responsibilities: z.string().nullable().optional(),
        requirements: z.string().nullable().optional(),
        sources: z.array(
          z.object({ attribution: z.string(), url: z.string() }),
        ),
      }),
    }),
  ),
  history: z.array(
    z.object({
      previous_status: z.string().nullable(),
      new_status: z.string(),
      created_at: z.string(),
      source: z.string(),
      note: z.string(),
    }),
  ),
  events: z.array(
    z.object({
      id: z.string(),
      kind: z.string(),
      text: z.string(),
      due_date: z.string().nullable(),
      completed_at: z.string().nullable(),
      created_at: z.string(),
    }),
  ),
});
export type Application = z.infer<typeof applicationSchema>;
export type ApplicationDetail = z.infer<typeof applicationDetailSchema>;
