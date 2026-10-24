import { z } from "zod";
import Link from "next/link";
import { Shell } from "@/components/shell";
import { Notifications } from "@/components/notifications";
import { requireUser, serverApi } from "@/lib/server";
export default async function NotificationPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const user = await requireUser();
  const query = await searchParams;
  const offset = Math.max(0, Math.min(1000000, Number(query.offset) || 0));
  const unread = query.unread === "true";
  const notification = z.object({
    id: z.string(),
    kind: z.string(),
    job_id: z.string().nullable(),
    created_at: z.string(),
    read: z.boolean(),
  });
  const preference = z.object({
    disabled_types: z.array(z.string()),
    available_types: z.array(z.string()),
  });
  const [items, preferences] = await Promise.all([
    serverApi(
      `/notifications?offset=${offset}&unread=${unread}`,
      z.array(notification),
    ),
    serverApi("/notification-preferences", preference),
  ]);
  return (
    <Shell email={user.email} active="notifications">
      <Notifications
        key={`${offset}-${unread}`}
        initial={items}
        preferences={preferences}
      />
      <p>
        <Link href="/notifications">All notifications</Link> ·{" "}
        <Link href="/notifications?unread=true">Unread notifications</Link>
      </p>
      {offset > 0 && (
        <Link
          href={`/notifications?offset=${Math.max(0, offset - 50)}&unread=${unread}`}
        >
          Previous notifications
        </Link>
      )}
      {items.length === 50 && (
        <Link href={`/notifications?offset=${offset + 50}&unread=${unread}`}>
          Next notifications
        </Link>
      )}
    </Shell>
  );
}
