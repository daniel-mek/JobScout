import { z } from "zod";
import { jobSchema } from "./jobs-contracts";
export const reviewSchema = z.object({
  saved: z.boolean(),
  saved_at: z.string().nullable(),
  reviewed: z.boolean(),
  notes: z.string(),
  deadline: z.string().nullable(),
  feedback: z.string().nullable(),
  reason: z.string().nullable(),
  job_revision: z.number(),
});
const resultSchema = z.object({
  resume_match: z.number(),
  application_priority: z.number(),
  recommendation: z.string(),
  early_career: z.string(),
  eligibility: z.string(),
});
export const discoverySchema = z.object({
  total: z.number(),
  as_of: z.string(),
  offset: z.number(),
  items: z.array(
    jobSchema.extend({
      match: resultSchema.nullable(),
      match_calculated_at: z.string().nullable(),
      match_profile_current: z.boolean(),
      review: reviewSchema.nullable(),
      salary_min: z.number().nullable(),
      salary_max: z.number().nullable(),
      currency: z.string().nullable(),
      salary_period: z.string().nullable(),
    }),
  ),
});
