import Link from "next/link";
import { JobMatch } from "@/components/job-match";
import { Shell } from "@/components/shell";
import { requireUser, serverApi } from "@/lib/server";
import { jobDetailSchema } from "@/lib/jobs-contracts";

export default async function JobPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const user = await requireUser();
  const { id } = await params;
  const job = await serverApi(
    `/jobs/${encodeURIComponent(id)}`,
    jobDetailSchema,
  );
  return (
    <Shell email={user.email} active="jobs">
      <JobMatch id={job.id} />
      <Link href="/jobs">← All jobs & sources</Link>
      <section className="dashboard-heading">
        <p className="eyebrow">{job.company}</p>
        <h1>{job.title}</h1>
        <p>
          {job.location || "Location unknown"} ·{" "}
          {job.arrangement || "Work arrangement unknown"} ·{" "}
          {job.active ? "Active" : "Archived"}
        </p>
        <a
          className="button-link"
          href={job.application_url}
          target="_blank"
          rel="noopener noreferrer"
        >
          Open original listing ↗
        </a>
      </section>
      <div className="dashboard-cards">
        <article className="panel">
          <h2>Listing details</h2>
          <p>
            Employment: {job.employment_type || "Unknown"} · Posted:{" "}
            {job.posted_at
              ? new Date(job.posted_at).toLocaleDateString("en-US", {
                  timeZone: "UTC",
                })
              : "Unknown"}
          </p>
          <p>
            Salary: {job.data.salary_min ?? "Unknown"} –{" "}
            {job.data.salary_max ?? "Unknown"} {job.data.currency || ""}{" "}
            {job.data.salary_period || ""}
          </p>
          <h3>Description</h3>
          <p className="job-text">
            {job.data.description ||
              "Description unavailable. Open the original listing; some sources permit metadata and links only."}
          </p>
          {job.data.responsibilities && (
            <>
              <h3>Responsibilities</h3>
              <p className="job-text">{job.data.responsibilities}</p>
            </>
          )}
          {job.data.requirements && (
            <>
              <h3>Requirements</h3>
              <p className="job-text">{job.data.requirements}</p>
            </>
          )}
        </article>
        <article className="panel">
          <h2>Where this came from</h2>
          {job.provenance.map((source, i) => (
            <div className="source-entry" key={`${source.provider}-${i}`}>
              <strong>{source.attribution}</strong>
              <p>Provider ID: {source.external_id}</p>
              <a
                href={source.source_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                View source ↗
              </a>
              <p>
                Retrieved{" "}
                {new Date(source.retrieved_at).toLocaleString("en-US", {
                  timeZone: "UTC",
                })}{" "}
                UTC
              </p>
              <p>
                Last seen{" "}
                {new Date(source.last_seen_at).toLocaleString("en-US", {
                  timeZone: "UTC",
                })}{" "}
                UTC · {source.active ? "Active" : "No longer listed"}
              </p>
              <p>Description storage: {source.description_storage}</p>
            </div>
          ))}
        </article>
      </div>
      <section className="panel job-history">
        <h2>Version history</h2>
        <p>
          Changes to listing content or availability create a version. Retrieval
          timestamps do not.
        </p>
        {job.versions.map((version) => (
          <details key={version.version}>
            <summary>
              Version {version.version} ·{" "}
              {new Date(version.created_at).toLocaleString("en-US", {
                timeZone: "UTC",
              })}{" "}
              UTC · {version.data.active ? "Active" : "Archived"}
            </summary>
            <h3>{version.data.title}</h3>
            <p className="job-text">
              {version.data.description ||
                "No archived description permitted or supplied."}
            </p>
            {version.data.requirements && (
              <p className="job-text">{version.data.requirements}</p>
            )}
          </details>
        ))}
      </section>
    </Shell>
  );
}
