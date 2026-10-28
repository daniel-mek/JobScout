import Link from "next/link";
import { z } from "zod";
import { discoveryStatusSchema } from "@/lib/jobs-contracts";

export function DiscoverySetup({
  status,
}: {
  status: z.infer<typeof discoveryStatusSchema>;
}) {
  if (status.jobs > 0) return null;
  return (
    <section
      className="panel job-history"
      aria-labelledby="discovery-setup-title"
    >
      <p className="eyebrow">Get started</p>
      <h2 id="discovery-setup-title">Let’s build your opportunity list</h2>
      <p>
        Your workspace has no imported jobs yet. Connect an employer’s career
        page or add a listing you found elsewhere.
      </p>
      <ol>
        <li>
          <strong>Add a job or employer.</strong> Paste a job link and its
          details, or connect a supported employer board.
        </li>
        <li>
          <strong>Import listings.</strong>{" "}
          {status.ready_sources > 0
            ? `${status.ready_sources} connected sources are ready to sync.`
            : status.connected_sources > 0
              ? "Your connected sources are waiting for setup or access review. You can add jobs manually in the meantime."
              : "No employer sources are connected yet. Automatic imports become available after source access is reviewed."}
        </li>
        <li>
          <strong>Review your matches.</strong> Open an imported job to
          calculate its match, save it, or prepare an application.
        </li>
      </ol>
      <div className="job-buttons">
        <Link className="button-link" href="/jobs#add-job">
          Add your first job
        </Link>
        <Link href="/jobs#connect-source">Connect an employer</Link>
      </div>
    </section>
  );
}
