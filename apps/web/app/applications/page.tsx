import { Shell } from "@/components/shell";
import { ApplicationBoard } from "@/components/application-board";
import { applicationListSchema, statuses } from "@/lib/application-contracts";
import { requireUser, serverApi } from "@/lib/server";

export default async function Applications({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const user = await requireUser();
  const raw = await searchParams;
  const filters: Record<string, string> = {};
  if (typeof raw.company === "string")
    filters.company = raw.company.slice(0, 200);
  if (typeof raw.role === "string") filters.role = raw.role.slice(0, 300);
  if (typeof raw.status === "string" && statuses.some((s) => s === raw.status))
    filters.status = raw.status;
  if (typeof raw.offset === "string" && /^\d{1,7}$/.test(raw.offset))
    filters.offset = raw.offset;
  const query = new URLSearchParams(filters).toString();
  const data = await serverApi(`/applications?${query}`, applicationListSchema);
  return (
    <Shell email={user.email} active="applications">
      <section className="dashboard-heading">
        <p className="eyebrow">One opportunity at a time</p>
        <h1>Applications</h1>
        <p>Your pipeline, next steps and application history.</p>
      </section>
      <ApplicationBoard key={query} data={data} filters={filters} />
    </Shell>
  );
}
