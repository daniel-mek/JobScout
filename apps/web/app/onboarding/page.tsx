import { redirect } from "next/navigation";
import { Onboarding } from "@/components/onboarding";
import { requireUser, onboardingState, serverApi } from "@/lib/server";
import {
  currentProfileSchema,
  detailSchema,
  rolesSchema,
  steps,
  type Step,
} from "@/lib/contracts";
export default async function OnboardingPage({
  searchParams,
}: {
  searchParams: Promise<{ edit?: string }>;
}) {
  await requireUser();
  const state = await onboardingState();
  const query = await searchParams;
  const edit = steps.includes(query.edit as Step)
    ? (query.edit as Step)
    : undefined;
  if (state.complete && !edit) redirect("/dashboard");
  const next = state.next_step === "complete" ? "upload" : state.next_step;
  const step =
    edit && (state.complete || steps.indexOf(edit) <= steps.indexOf(next))
      ? edit
      : next;
  const roles = await serverApi("/role-families", rolesSchema);
  let detail =
    step === "review" && state.latest_resume
      ? await serverApi(`/resumes/${state.latest_resume.id}`, detailSchema)
      : null;
  if (detail?.resume.confirmed) {
    const current = await serverApi("/profile", currentProfileSchema);
    if (current.profile) detail = { ...detail, draft: current.profile };
  }
  return (
    <Onboarding
      key={`${step}:${state.latest_resume?.id}:${state.profile_revision}`}
      state={state}
      step={step}
      roles={roles}
      detail={detail}
    />
  );
}
