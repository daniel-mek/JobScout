import "server-only";
import { cache } from "react";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { z } from "zod";
import { stateSchema, userSchema } from "./contracts";

export async function serverApi<T>(
  path: string,
  schema: z.ZodType<T>,
): Promise<T> {
  const jar = await cookies();
  const response = await fetch(
    `${process.env.API_INTERNAL_URL || "http://127.0.0.1:8000"}${path}`,
    {
      headers: { cookie: jar.toString() },
      cache: "no-store",
      signal: AbortSignal.timeout(10000),
    },
  );
  if (response.status === 401) redirect("/login");
  if (!response.ok)
    throw new Error("The server could not complete your request.");
  return schema.parse(await response.json());
}
export const requireUser = cache(async () => serverApi("/auth/me", userSchema));
export async function onboardingState() {
  return serverApi("/onboarding", stateSchema);
}
