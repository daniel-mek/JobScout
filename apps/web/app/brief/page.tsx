import Link from "next/link";
import { z } from "zod";
import { Shell } from "@/components/shell";
import { requireUser, serverApi } from "@/lib/server";
export default async function Brief() {
  const user = await requireUser();
  const data = await serverApi(
    "/daily-brief",
    z.object({
      date: z.string(),
      notice: z.string(),
      sections: z.record(
        z.string(),
        z.array(
          z.object({
            id: z.string(),
            title: z.string(),
            company: z.string(),
            sources: z.array(
              z.object({ attribution: z.string(), url: z.string() }),
            ),
          }),
        ),
      ),
    }),
  );
  return (
    <Shell email={user.email} active="brief">
      <h1>Daily job brief</h1>
      <p>
        {data.date} UTC · {data.notice}
      </p>
      {Object.entries(data.sections).map(([section, jobs]) => (
        <section className="panel job-history" key={section}>
          <h2>{section.replaceAll("_", " ")}</h2>
          {jobs.length ? (
            jobs.map((job) => (
              <p key={job.id}>
                <Link href={`/jobs/${job.id}`}>
                  {job.title} · {job.company}
                </Link>
                {job.sources.map((source, i) => (
                  <span key={i}>
                    {" "}
                    ·{" "}
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {source.attribution}
                    </a>
                  </span>
                ))}
              </p>
            ))
          ) : (
            <p>No qualifying jobs in this section today.</p>
          )}
        </section>
      ))}
    </Shell>
  );
}
