import { z } from "zod";
export const scoringSchema = z.object({
  revision: z.number(),
  weights: z.record(z.string(), z.number()),
  priority_weights: z.record(z.string(), z.number()),
});
export type ScoringPolicy = z.infer<typeof scoringSchema>;
