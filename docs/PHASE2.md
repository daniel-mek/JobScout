# Phase 2: sources and ingestion

The authenticated `/jobs` workspace provides manual import, employer board detection/setup, on-demand ingestion, source health, saved source searches and run diagnostics. Job details show original links, attribution, normalized fields, provenance, active/archive state and version history. Companies, jobs, sources, searches and history are owner-scoped relational records; no legacy private data is migrated.

## Sources

`packages/job_sources` supplies the reusable JobSourceAdapter/SourceRegistry, normalized Posting, provider readers and HTTPS transport. Persisted SourcePolicy controls each owner's JobSource configuration.

- Greenhouse/Ashby public boards, global/EU Lever pagination, and unauthenticated SmartRecruiters public list/detail endpoints are implemented. Ashby excludes unlisted jobs. SmartRecruiters uses the returned application link rather than its API-detail `ref`. No application-submission operations exist.
- Optional USAJOBS/Adzuna search adapters report `configuration_required` when credentials are absent. Server settings mask secrets; registry/provenance excludes them. Adzuna predicted salary is not represented as employer-stated salary.
- Remotive stays disabled: its [published terms](https://remotive.com/remote-jobs/api) prohibit signup-gated listings, conflicting with this workspace. Workday/generic sites remain review/manual only. Restricted platforms have no scraping adapters.
- Detection recognizes exact supported ATS hosts without fetching submitted pages. No employer-specific feed/JSON-LD integration has been approved/configured; those sites return manual fallback. Feed discovery remains unavailable until a permitted employer integration is configured.
- URL import uses only registered, approved ATS boards. Unsupported/unconfigured/unapproved or missing listings return explicit fallback. Manual import needs title, company and URL; absent fields remain unknown. Manual import never makes network requests.
- Automated discovery excludes internship titles/types. The legacy full-time IT/CS watcher is preserved separately. Requirements extraction, eligibility and personalization belong to Phase 3; imported boards are not ranked yet.

## Policy and transport

No external source is approved by default. Every network run checks enabled state, APPROVED status, explicit board scope, adapter availability and credentials. Account routes cannot approve sources. Operator review records evidence, terms, attribution, description permission and board IDs; `*` requires provider-wide permission evidence. The command records a completed review rather than performing one:

```sh
.venv/bin/python -m apps.api.applyos.source_policy --help
```

Credentials may be supplied privately through `.env`/server variables (see `.env.example`), never `NEXT_PUBLIC_*`. Public documentation is not a grant of storage/redistribution permission.

Requests use fixed adapter host allowlists, public-address DNS validation, numeric-address-pinned connections with hostname-verified TLS, same-host redirects, GET-only operations and bounded responses/retries/time. Mixed public/private DNS answers fail closed. Submitted URLs reject unsafe schemes, credentials, ports, literal private addresses and internal names. Stored links are never fetched. Legacy `scout/posting.py` is not exposed.

PostgreSQL owner advisory locks and consistently ordered provider row locks serialize writes/runs. Provider intervals, per-source cooldowns and bounded backoff persist across processes. Failures are isolated in source health/run results; raw exceptions and credential URLs are not retained.

Unknown/prohibited storage strips description and requirement content before insertion into live jobs, source records and versions. Raw payloads are never stored. Operator policy tightening purges restricted live and historical content. All data requires owner authorization; there is no public redistribution/export route. List/detail views show attribution and source links.

## Data lifecycle

Provider/board identifiers and canonical application URLs lead deduplication. Known tracking parameters are removed, identifying queries preserved. Secondary merging requires the same normalized company/title/location, identical substantial description and provider dates within seven days. Titles alone never merge. Multiple source records can refer to a job; losing one source does not archive a job another source still lists. Verified ATS application destinations can replace aggregator redirects; links are never manufactured.

Content/availability changes create versions; retrieval/provider-date changes alone do not. Provenance keeps identifiers, original URL, retrieval time, provider date and last seen separately.

Runs are synchronous and bounded: Lever resumes after four 100-row pages, SmartRecruiters after five public details. Last-seen timestamps spanning a complete cycle protect earlier pages from archival. Only completion of an employer cycle archives missing records; partial/failed/search-API responses never do. Greenhouse/Ashby responses are bounded to 4 MiB and 5,000 normalized rows. Oversized/malformed responses preserve existing records and report failure. Changes in provider ordering between pages remain a pagination limitation; later complete cycles reconcile them.

SavedSearch/SearchTitle/SearchRun models and authenticated routes persist manual source searches, titles and diagnostics. Saved source searches have UI controls. Rich filtering belongs to Phase 4; durable queues/schedules belong to Phase 7. A process crash rolls back the synchronous run transaction.

## Migration and verification

Revision `98c00bbaf877` adds the new tables and a frozen policy inventory. Apply through the existing Alembic release procedure, never startup/build automation. API container builds include the shared adapter package.

```sh
.venv/bin/alembic -c apps/api/alembic.ini upgrade head
.venv/bin/ruff check apps/api packages/job_sources
.venv/bin/ruff format --check apps/api packages/job_sources
.venv/bin/mypy apps/api/applyos
.venv/bin/pytest -q apps/api/tests
npm run lint
npm run typecheck
npm run build
npm run test:e2e
```

Local evidence: 56 API/unit/integration cases pass on SQLite, including Phase 1 regressions, policy scope/gating, ownership/CSRF, missing credentials, manual fallback, DNS pinning/redirect limits, public-only normalization, pagination/cycle archival, dedupe, version suppression and retention purge. Migration upgrade/check/downgrade/upgrade and offline PostgreSQL generation pass. Ruff/mypy and frontend lint/typecheck/build pass. Legacy suite: 163 run, 161 pass, two unchanged private-fixture skips.

Local Chrome cannot launch inside the macOS execution sandbox. Native file-watcher limits also affect dev startup; `E2E_PRODUCTION=1 npm run test:e2e` after a build avoids watchers. GitHub CI run 39728392243 passed 55 tests each on SQLite and native PostgreSQL, all four Playwright flows (46.3 seconds), frontend/static/build checks and legacy regressions. A final normalization regression adds the 56th local test; subsequent CI verifies that follow-up. Browser coverage includes import persistence, original provenance, version history, policy-blocked source sync, saved searches and WCAG A/AA checks.

Live provider calls, actual policy approvals, optional credentials and deployed behavior remain externally unverified. Hosting stays paused. Phase 3 is not implemented by this change.
