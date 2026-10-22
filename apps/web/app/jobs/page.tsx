import { z } from "zod";
import { Shell } from "@/components/shell";
import { JobsWorkspace } from "@/components/jobs-workspace";
import { requireUser, serverApi } from "@/lib/server";
import {
  jobSchema,
  sourceSchema,
  policySchema,
  runSchema,
  searchSchema,
} from "@/lib/jobs-contracts";

export default async function JobsPage() {
  const user = await requireUser();
  const [jobs, sources, policies, runs, searches] = await Promise.all([
    serverApi("/jobs", z.array(jobSchema)),
    serverApi("/sources", z.array(sourceSchema)),
    serverApi("/source-registry", z.array(policySchema)),
    serverApi("/search-runs", z.array(runSchema)),
    serverApi("/saved-searches", z.array(searchSchema)),
  ]);
  return (
    <Shell email={user.email} active="jobs">
      <JobsWorkspace initial={{ jobs, sources, policies, runs, searches }} />
    </Shell>
  );
}
