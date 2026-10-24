import { Shell } from "@/components/shell";
import { DiscoveryWorkspace } from "@/components/discovery-workspace";
import { discoverySchema } from "@/lib/discovery-contracts";
import { requireUser, serverApi } from "@/lib/server";
import { rolesSchema } from "@/lib/contracts";

export default async function SavedJobs({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const user = await requireUser();
  const values = await searchParams;
  const query: Record<string, string> = {};
  for (const [key, value] of Object.entries(values))
    if (typeof value === "string" && value && key !== "limit")
      query[key] = value;
  query.saved = "true";
  const [data, roles] = await Promise.all([
    serverApi(`/discover?${new URLSearchParams(query)}`, discoverySchema),
    serverApi("/role-families", rolesSchema),
  ]);
  return (
    <Shell email={user.email} active="saved">
      <DiscoveryWorkspace
        key={new URLSearchParams(query).toString()}
        data={data}
        query={query}
        roles={roles}
        saved
      />
    </Shell>
  );
}
