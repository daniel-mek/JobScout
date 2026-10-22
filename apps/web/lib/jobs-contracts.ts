import { z } from "zod";

export const jobSchema = z.object({
  id: z.string(),
  title: z.string(),
  company: z.string(),
  location: z.string().nullable(),
  country: z.string().nullable(),
  arrangement: z.string().nullable(),
  employment_type: z.string().nullable(),
  application_url: z.string(),
  active: z.boolean(),
  posted_at: z.string().nullable(),
  discovered_at: z.string(),
  last_seen_at: z.string(),
  revision: z.number(),
  sources: z.array(z.object({ attribution: z.string(), url: z.string() })),
});
export type Job = z.infer<typeof jobSchema>;
export const sourceSchema = z.object({
  id: z.string(),
  provider: z.string(),
  company: z.string(),
  board: z.string(),
  url: z.string(),
  enabled: z.boolean(),
  policy_status: z.string(),
  health: z.object({
    state: z.string(),
    code: z.string(),
    last_success: z.string().nullable(),
    last_failure: z.string().nullable(),
    next_run_at: z.number(),
    last_count: z.number(),
  }),
});
export type Source = z.infer<typeof sourceSchema>;
export const policySchema = z.object({
  id: z.string(),
  display_name: z.string(),
  status: z.string(),
  enabled: z.boolean(),
  documentation_url: z.string(),
  terms_url: z.string(),
  attribution: z.string(),
  description_storage: z.string(),
  redistribution: z.string(),
  evidence: z.string(),
  reviewed_at: z.string().nullable(),
  adapter_version: z.string(),
  adapter_available: z.boolean(),
  credentials: z.array(z.string()),
  approved_boards: z.array(z.string()),
  rate_limit: z.object({
    min_interval_seconds: z.number(),
    run_interval_seconds: z.number(),
    max_pages: z.number(),
  }),
});
export type Policy = z.infer<typeof policySchema>;
export const runSchema = z.object({
  id: z.string(),
  state: z.string(),
  started_at: z.string(),
  finished_at: z.string().nullable(),
  results: z.array(
    z.object({
      source_id: z.string(),
      state: z.string(),
      code: z.string(),
      count: z.number(),
    }),
  ),
});
export type Run = z.infer<typeof runSchema>;
export const searchSchema = z.object({
  id: z.string(),
  name: z.string(),
  source_ids: z.array(z.string()),
});
export type SavedSearch = z.infer<typeof searchSchema>;
const postingData = z.object({
  title: z.string(),
  description: z.string().nullable(),
  requirements: z.string().nullable(),
  responsibilities: z.string().nullable(),
  salary_min: z.number().nullable(),
  salary_max: z.number().nullable(),
  currency: z.string().nullable(),
  salary_period: z.string().nullable(),
  active: z.boolean().optional(),
});
export const jobDetailSchema = jobSchema.extend({
  data: postingData,
  provenance: z.array(
    z.object({
      provider: z.string(),
      attribution: z.string(),
      source_url: z.string(),
      external_id: z.string(),
      retrieved_at: z.string(),
      posted_at: z.string().nullable(),
      last_seen_at: z.string(),
      active: z.boolean(),
      description_storage: z.string(),
    }),
  ),
  versions: z.array(
    z.object({
      version: z.number(),
      created_at: z.string(),
      data: postingData,
    }),
  ),
});
