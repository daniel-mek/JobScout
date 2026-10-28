import { Shell } from "@/components/shell";
import { DiscoverySetup } from "@/components/discovery-setup";
import { z } from "zod";
import { SavedDiscoverySearches } from "@/components/saved-discovery-searches";
import { DiscoveryWorkspace } from "@/components/discovery-workspace";
import { discoverySchema } from "@/lib/discovery-contracts";
import { discoveryStatusSchema } from "@/lib/jobs-contracts";
import { requireUser, serverApi } from "@/lib/server";
import { rolesSchema } from "@/lib/contracts";

export default async function Discover({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const user = await requireUser();
  const values = await searchParams;
  const query: Record<string, string> = {};
  const allowed = new Set([
    "view",
    "title",
    "company",
    "location",
    "arrangement",
    "employment_type",
    "role_family",
    "source",
    "recommendation",
    "early_career",
    "min_match",
    "min_priority",
    "min_salary",
    "currency",
    "freshness_days",
    "saved",
    "reviewed",
    "offset",
  ]);
  for (const [key, value] of Object.entries(values))
    if (allowed.has(key) && typeof value === "string" && value)
      query[key] = value;
  const [data, roles, searches, status] = await Promise.all([
    serverApi(`/discover?${new URLSearchParams(query)}`, discoverySchema),
    serverApi("/role-families", rolesSchema),
    // Independent requests start together; keep the response tuple aligned below.
    serverApi(
      "/discovery-searches",
      z.array(
        z.object({
          id: z.string(),
          name: z.string(),
          filters: z.record(
            z.string(),
            z.union([z.string(), z.number(), z.boolean()]),
          ),
        }),
      ),
    ),
    serverApi("/discovery-status", discoveryStatusSchema),
  ]);
  return (
    <Shell email={user.email} active="discover">
      <DiscoverySetup status={status} />
      <SavedDiscoverySearches initial={searches} query={query} />
      <DiscoveryWorkspace
        key={new URLSearchParams(query).toString()}
        data={data}
        query={query}
        roles={roles}
        emptyCatalog={status.jobs === 0}
      />
    </Shell>
  );
}
