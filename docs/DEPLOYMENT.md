# Deployment

## Hosted checkpoint, 2026-10-27

Production deployment `dpl_3wN6P76v2pteotmQM7DNVky7LCAL` is READY at https://jobscout-peach.vercel.app, code `14c13d0579a59782c2a6b6e72d930ac620a95789`. The project uses repository-root Services configuration and production HTTPS/secure-cookie/private-Blob settings. `Dockerfile.api` is at the repository root so Vercel's container build includes the full monorepo context. An explicit root rewrite fixes homepage routing.

The user approved initialization. The previously empty database was migrated atomically through Phase 5 using the authenticated Neon query editor. Its prepared-statement interface required one DO block, omitting transaction wrappers and the Alembic INSERT RETURNING output; rejected attempts rolled back. Verification returned Alembic `3e91abf9209b` and 11 role families. Editor read-only mode was restored. No migrations run automatically on future deployments.

Live checks: homepage and login HTTP 200; API health HTTP 200 with database ready; anonymous auth/me HTTP 401; synthetic test-account signup and authenticated onboarding render succeeded in local Chrome. A synthetic-resume browser upload stalled before attachment, so live Blob write/read, anonymous Blob denial, resume parsing/download and the full hosted application journey remain unverified. Persistent Redis/Celery deployment, backup/restore and production monitoring remain pending. This checkpoint supersedes the earlier empty-database/paused-hosting notes below; it is not a claim of full production readiness.

## Vercel setup, 2026-10-22

The user authorized hosting the application and provisioning its dependencies. The `jobscout` project in the `daniel-mekhail` workspace has a private `jobscout-resumes` Blob store and a free `jobscout-db` Neon PostgreSQL database in US East (`iad1`). Neon is connected to Production only. The database was inspected and has no public tables. The initial Alembic migration has been generated for review; execution is pending explicit approval of the SQL editor's write-mode confirmation. No live application deployment is verified yet.

`vercel.json` prepares a Vercel Services deployment (currently beta): the Next.js service retains `apps/web` as its service root, while the Python service builds the existing non-root API Dockerfile from the repository root. This is an explicitly authorized hosting adaptation of the original separate-host recommendation; API, storage, and database abstractions remain portable. Future persistent workers are still outside frontend request execution.

Vercel project Root Directory must be the repository root, with framework detection delegated to Services. Set these Production variables before deployment: `ENVIRONMENT=production`, `COOKIE_SECURE=true`, `STORAGE_BACKEND=vercel_blob`, `PORT=8000`, `MAX_UPLOAD_BYTES=4194304`, and `NEXT_PUBLIC_MAX_UPLOAD_BYTES=4194304`. Neon supplies `DATABASE_URL`; standard PostgreSQL URLs are normalized to the installed psycopg driver. Blob supplies server-only credentials. The API derives the canonical HTTPS origin from `VERCEL_PROJECT_PRODUCTION_URL` unless `WEB_ORIGIN` is explicit. The web service receives `API_INTERNAL_URL` through its runtime service binding, not a build-time hostname.

Top-level ingress routes `/backend/*` to the API, whose service rewrite strips that prefix; all other routes go to Next.js. Keep deployment protection enabled while verification is incomplete. Hosted uploads use a 4 MiB ceiling below Vercel's 4.5 MB request-body limit; local defaults remain 5 MiB. Do not connect preview builds to the production database. A separate preview database/store is required before preview application testing.

Apply migrations once through a reviewed release step, using the unpooled connection or the authenticated Neon SQL editor. For the brand-new empty database only, generate the initial transactional script with `DATABASE_URL=postgresql+psycopg://offline:offline@localhost/offline ENVIRONMENT=test alembic -c apps/api/alembic.ini upgrade head --sql`; verify its Alembic version and eleven role families afterward. Do not rerun the initial CREATE TABLE script on an existing database. No migrations run automatically during API startup or frontend builds.

Before marking hosting complete, verify the remote build, database readiness, signup/login/logout, CSRF rejection, upload/review/persistence, owner-authorized private downloads, and direct anonymous Blob denial. Record the actual deployment URL and evidence here. Backups/restore tests, operational alerting, and later product phases remain separate work.

## Current implementation

The existing dashboard is a Cloudflare Worker, not a Next.js application. Its npm project is worker/; npm ci installs the lockfile, npm run dev starts Wrangler, npm run deploy publishes it. The Python watcher runs through GitHub Actions and writes state to a separate data branch.

No deployment is performed by this documentation update. Existing hosted resources and secrets are unverified. Before publishing the legacy Worker, replace/verify the namespace binding and upstream GH_REPO in worker/wrangler.toml; do not deploy into someone else's namespace or dispatch their repository.

Legacy configuration:
- Worker secrets: DASH_PASSWORD, SESSION_SECRET, INGEST_SECRET; optional GH_DISPATCH_TOKEN and NTFY_TOPIC.
- GitHub Actions secrets: NTFY_TOPIC for normal alert/persistence behavior, SCOUT_URL and SCOUT_INGEST_SECRET for dashboard sync.
- Private local settings: me/dashboard.env and optional me/ntfy-topic.txt. Never commit them.

Follow [operations](OPERATIONS.md) for commands and the dry-run behavior when NTFY_TOPIC is absent.

## Phase 1 deployment target

| Component | Target | Required validation |
| --- | --- | --- |
| apps/web | Vercel project rooted at apps/web | Next.js build, public backend URL, protected routes, environment isolation |
| apps/api | Independent HTTPS FastAPI service/container | Health/readiness, database connectivity, authorization, CORS/session/CSRF configuration |
| apps/worker | Persistent Python worker and scheduler outside frontend serverless | Redis connectivity, locks, retries, idempotency, graceful shutdown |
| Database | Managed PostgreSQL | Reviewed Alembic migrations, least privilege, backups, tested restore |
| Queue | Managed Redis | Private connectivity, credentials, retention/eviction settings |
| Files | S3-compatible private object storage | Owner authorization, signed access, lifecycle/retention/deletion |

Phase 1 provides apps/api/Dockerfile, infrastructure/compose.yaml for local PostgreSQL, Alembic migrations, API /health, and a buildable Next.js workspace. See [PHASE1.md](PHASE1.md). No background worker is introduced before its phase. Actual Vercel/API/database/storage provisioning and hosted health checks have not been performed.

## Environment contract to introduce

Phase 1 includes .env.example and server-side configuration validation. Planned server-only categories: DATABASE_URL, session/cryptographic secrets, storage configuration, and later REDIS_URL, ANTHROPIC_API_KEY or other LLM credentials, Google OAuth secrets, USAJOBS credentials, ADZUNA_APP_ID/ADZUNA_APP_KEY. Only intentionally public browser configuration, such as a backend API base URL, may use NEXT_PUBLIC_*.

Separate development, preview and production databases, queues, storage and signing keys. Choose secret delivery per service; do not pass backend secrets to Vercel's browser build.

## Migration and release runbook

1. Back up legacy JSON/KV and target database/object storage privately; record restore procedure.
2. Test migrations against representative non-production data and verify ownership mapping. Do not fabricate history.
3. Run unit/integration/security/end-to-end checks and schema compatibility checks.
4. Deploy additive API/database changes, then web; enable workers only after migrations and source approval gates pass.
5. Verify readiness, authentication, file ownership, scheduled jobs, source health, and the real user journey.
6. Roll back application images if needed; handle database rollback through reviewed forward fixes or an explicitly tested restore, never blind downgrade.
7. Document backup retention, object lifecycle, credentials rotation, alerts and restoration evidence.

Production readiness requires operational evidence, not just a passing build. Hosting accounts and service provisioning are future deployment work.

