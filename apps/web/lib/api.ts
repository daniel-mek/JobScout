import { z } from "zod";

export async function api<T>(
  path: string,
  schema: z.ZodType<T>,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  const csrf = document.cookie
    .split("; ")
    .find((x) => x.startsWith("applyos_csrf="))
    ?.split("=")[1];
  if (csrf) headers.set("X-CSRF-Token", decodeURIComponent(csrf));
  if (init.body && !(init.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  let response: Response;
  try {
    response = await fetch(`/backend${path}`, {
      ...init,
      headers,
      credentials: "same-origin",
      cache: "no-store",
    });
  } catch {
    throw new Error("The server is unavailable. Please try again.");
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const error = z.object({ detail: z.string() }).safeParse(body);
    throw new Error(
      error.success
        ? error.data.detail
        : "The request could not be completed. Please try again.",
    );
  }
  const parsed = schema.safeParse(body);
  if (!parsed.success)
    throw new Error(
      "The server returned an unexpected response. Please reload.",
    );
  return parsed.data;
}
