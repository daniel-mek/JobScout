import { z } from "zod";
import { ApplicationDetail } from "@/components/application-detail";
import { Shell } from "@/components/shell";
import { applicationDetailSchema } from "@/lib/application-contracts";
import { resumeSchema } from "@/lib/contracts";
import { requireUser, serverApi } from "@/lib/server";

export default async function ApplicationPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const user = await requireUser();
  const { id } = await params;
  const [row, resumes] = await Promise.all([
    serverApi(
      `/applications/${encodeURIComponent(id)}`,
      applicationDetailSchema,
    ),
    serverApi("/resumes", z.array(resumeSchema)),
  ]);
  return (
    <Shell email={user.email} active="applications">
      <ApplicationDetail key={id} initial={row} resumes={resumes} />
    </Shell>
  );
}
