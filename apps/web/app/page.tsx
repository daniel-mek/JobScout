import { redirect } from "next/navigation";
import { requireUser, onboardingState } from "@/lib/server";
export default async function Home() {
  await requireUser();
  const state = await onboardingState();
  redirect(state.complete ? "/dashboard" : "/onboarding");
}
