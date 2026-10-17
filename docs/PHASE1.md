# Phase 1: accounts, resumes and onboarding

Phase 1 adds a Next.js application alongside the existing JobScout watcher and Cloudflare dashboard. It does not replace or migrate legacy application data or connect job ingestion to the new account model. No live AI service is required.

## Run locally

Requirements: Python 3.12+, Node 22+ (CI uses 24), npm, and Docker for local PostgreSQL. Commands run at repository root.

```sh
python3 -m venv .venv
.venv/bin/pip install -r apps/api/requirements.lock
npm ci
cp .env.example .env
# Starts a local database only, bound to loopback. Demo password is not for production.
docker compose -f infrastructure/compose.yaml up -d
.venv/bin/alembic -c apps/api/alembic.ini upgrade head
.venv/bin/uvicorn apps.api.applyos.main:app --host 127.0.0.1 --port 8000
```

In a separate terminal:

```sh
npm run dev:web
```

Open http://localhost:3000. Sign up with your own email and a passphrase of at least 12 characters. No production account or fake job metrics are seeded. Role families are seeded through the initial migration.

For a local-only SQLite fallback instead of Docker, override DATABASE_URL in .env with sqlite:///./data/applyos-dev.db before running migrations and the API. SQLite is for development/testing; production explicitly requires PostgreSQL. Do not point tests at a real account database.

The API loads root .env. Next.js defaults its server-only API_INTERNAL_URL to http://127.0.0.1:8000; configure that variable in apps/web/.env.local for another backend. The browser uses the same-origin /backend proxy; it never receives database or object-storage credentials. WEB_ORIGIN must exactly match the browser origin, including protocol/port. Run migrations as an explicit release step, not on API startup.

## What works

- Email/password signup and sign-in, Argon2id hashes, opaque database-backed sessions with hashed tokens, rotation, expiry and logout revocation.
- Owner-scoped profile, resume/version/download/history, preferences, and dashboard endpoints. Mutation requests require a trusted Origin and session-bound CSRF header. Login throttles are database-backed.
- PDF/DOCX uploads capped at 5 MB, MIME/extension/content validation, private storage keys, and original version downloads. Encrypted/image-only PDFs, unsafe DOCX archives/macros/external relationships and extraction failures are rejected with actionable errors.
- Extraction runs in an isolated process with time/CPU/memory bounds on the Linux runtime. No embedded content or candidate text is executed. Synchronous upload processing runs in the API threadpool; background parsing is future work.
- Deterministic, review-required parsing identifies a conservative skill vocabulary and literal source evidence, groups education/experience/projects/certifications, and leaves unsupported fields blank. Explicit Location: and Graduation: lines can be extracted. This is not an LLM parser: complex layouts and separate employer/date fields may require manual correction.
- Profile review supports adding/removing/editing every section, skill-to-project/experience evidence references, explicit confirmation, revision history, and stale-edit rejection. Uploading another resume never silently replaces the confirmed profile or prior resume snapshot.
- Persisted database role taxonomy and multiple career-path selections, separate soft preferences and explicit nullable hard requirements. Unknown authorization/sponsorship answers remain unknown. These settings are stored for later matching; Phase 1 does not claim to apply them to jobs yet.
- Server-protected onboarding, account settings, resume history, and dashboard. Refresh resumes at the required step. A pending replacement resume requires review before returning to the dashboard.

## Tests and diagnostics

```sh
.venv/bin/ruff check apps/api
.venv/bin/ruff format --check apps/api
.venv/bin/mypy apps/api/applyos
.venv/bin/pytest -q apps/api/tests
.venv/bin/python -m unittest discover -s tests -t .
npm run lint
npm run typecheck
npm run build
npx prettier --check 'apps/web/**/*.{ts,tsx,css,mjs,json}'
npx playwright install chromium
npm run test:e2e
```

Playwright starts isolated API/database/storage and web processes. It uses clearly synthetic resume/account data and does not call ATS, AI or email APIs. To use an existing local compatible Chromium in a constrained environment, set CHROMIUM_EXECUTABLE_PATH. This environment used that fallback because the upstream browser archive download failed. The browser tests include profile review, persistence, preferences, history, download, logout, error handling, protected routes, mobile overflow and dashboard WCAG A/AA automated checks.

For PostgreSQL integration tests, use a dedicated database named applyos_test and set TEST_DATABASE_URL to its psycopg connection URL. Tests drop/rebuild its application schema. Do not provide a production connection. The GitHub Phase 1 workflow runs both SQLite and PostgreSQL tests plus the browser suite; both jobs passed in [run 39042290806](https://github.com/daniel-mek/JobScout/actions/runs/39042290806).

GET /health returns readiness only after schema migration. API responses use request IDs and do not expose raw validation input, stack traces or storage paths. Optional S3 support uses private, server-encrypted objects; the adapter contract is tested with a fake provider. Live S3 and deployment credentials were not tested.

## Deployment and limits

Build apps/web on Vercel with API_INTERNAL_URL set to the independent HTTPS API origin. Set the API's WEB_ORIGIN to the frontend origin. Build the API Dockerfile from repository root: docker build -f apps/api/Dockerfile -t applyos-api . The image runs as a non-root user. Supply production environment variables privately; production validation requires PostgreSQL, HTTPS origin, secure cookies and S3 storage. Apply Alembic migrations with the same release image/configuration before starting API instances.

Review frontend proxy body limits and API ingress rate limits for the chosen hosts. The application IP throttle uses the actual API peer and does not trust arbitrary forwarded headers; a shared frontend proxy may make the IP limit conservative across users. Tune trusted ingress/rate limiting before public rollout. API session/account rate limits remain enforced independently in the database.

This is not a production-readiness certification. Email verification/recovery, account deletion, Gmail/Calendar, background workers, source-policy enforcement, full privacy/security audit, production backups/restores and hosted-service checks belong to later scope or release hardening. No Phase 2 feature is included.
