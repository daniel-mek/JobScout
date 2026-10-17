# Deployment

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

