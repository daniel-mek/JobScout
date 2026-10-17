# Architecture

## Decision and scope

Assessed 2026-10-17 against commit 366005b18d8f28a866ce9f17ba1cd249cca39c38. ApplyOS is the target product; JobScout is the current repository and runtime. Phase 1 now implements apps/web and apps/api beside the legacy runtime. See PHASE1.md for commands and validation limits.

Preserve the working Python watcher and Cloudflare dashboard while introducing the specification's application incrementally. The current single-user architecture is useful but cannot substitute for authenticated, owner-scoped relational application data.

## Current system

| Area | Implementation |
| --- | --- |
| Collection | scout/listings.py and scout/boards.py: Simplify new-graduate JSON, Greenhouse, Lever, Ashby |
| Matching | scout/career.py, matching.py, scoring.py: title signals, configured IT/CS filters, one rule-based score |
| Availability | scout/eligibility.py and posting.py: cached closed/open-page checks; available does not imply candidate eligibility |
| Scheduling | GitHub Actions scout workflow, hourly with two UTC hours omitted; concurrency group; ntfy alerts and evening digest |
| State | JSON in a separate data branch; Workers KV mirrors dashboard state |
| Dashboard | worker/src/index.js, server-rendered HTML/CSS/JavaScript, shared-password session |
| Applications | scout/tracker.py and dashboard: saved/prepped/applied stages, history, notes/next action; JSON merge |
| Preparation | Claude Code commands plus JSON-to-PDF resume/letter builders and voice checks |
| Private data | gitignored me/ profile and resume variants; generated kits uploaded to private dashboard storage |

The legacy code retains its own requirements and worker/ npm project. Phase 1 adds a root npm workspace/lockfile, Next.js 16 / React 19 / strict TypeScript / Tailwind, a FastAPI application, SQLAlchemy relational profile records, Alembic migrations, and local/S3 file-storage implementations. PostgreSQL is the primary target and production-enforced; SQLite is a local/test fallback. No Redis queue or future-phase worker is scaffolded.

## Target boundaries

| Path | Responsibility | When introduced |
| --- | --- | --- |
| apps/web | Next.js App Router, strict TypeScript, accessible React dashboard, validated API client | Phase 1 |
| apps/api | FastAPI, Pydantic schemas, services/repositories, SQLAlchemy, Alembic; authoritative ownership and business rules | Phase 1 |
| apps/worker | Persistent Python worker and scheduler using Redis with Celery | Only when asynchronous work is introduced |
| packages/shared | OpenAPI-generated TypeScript contracts and stable shared domain definitions; Python validates independently | As needed |
| packages/ui | Reusable accessible UI components | As needed |
| packages/job_sources | Isolated approved-source adapters and policy enforcement | Phase 2 |
| packages/matching | Deterministic extraction/eligibility/scoring logic | Phase 3 |
| packages/ai | Provider-neutral, schema-validated AI operations and claim evidence | Phase-appropriate operations only |
| infrastructure, scripts | Local services, deployment and migration tooling | Incrementally |

Use PostgreSQL for searchable, owner-scoped entities and immutable versions. JSONB is for bounded provider data, not a replacement for relational ownership and indexes. Do not add pgvector until a measured matching need exists. Use local private file storage in development behind an abstraction; S3-compatible storage and short-lived authenticated access in production.

Browser traffic uses HTTPS to the API. Prefer same-origin routing or an explicit minimal CORS allowlist; choose cookie/session and CSRF behavior together. Authentication and ownership belong in API services/repositories, never solely in frontend routing. Server secrets stay out of browser bundles.

Keep worker execution outside frontend serverless requests. Jobs must eventually have idempotency keys, per-search locking, bounded retries, and source throttling. Database transactions own status transitions and event history.

## Reuse and migration rules

- Port normalized adapter behavior and fixtures; add provenance, policies, employment metadata and description evidence rather than discarding existing readers.
- Reuse tracker states through an explicit mapping. Preserve existing history and dates; do not fabricate missing timestamps or prior states.
- Keep the existing score labeled as a legacy ranking until separate Resume Match and Application Priority calculations are implemented.
- Keep CLI preparation available. Prompt instructions are useful guidance, not the required programmatic CandidateClaimValidator.
- Do not turn legacy posting.py into a public URL-fetch endpoint. First implement policy gating and redirect/DNS-safe SSRF protection.
- Make any legacy JSON/KV import a dry-run, owner-assigned, idempotent migration with backups. Do not put candidate data into the public code repository.
- Select and lock supported stable dependency versions when scaffolding Phase 1. Do not label uninstalled future tooling as a runnable development command.

## Phase 1 acceptance boundary

Implemented account/session/ownership foundations, migrations, a protected dashboard shell, PDF/DOCX validation and isolated extraction, deterministic parsing and validation, profile review/versioning, role preferences/hard requirements, and persisted onboarding. The API owns authentication with Argon2id, revocable opaque sessions and trusted-origin/session-bound CSRF; the Next.js same-origin proxy forwards requests without exposing backend credentials. Two-user isolation and browser persistence are tested. Native PostgreSQL integration passed in GitHub CI; live object-storage and hosted deployment verification remain release work. Do not implement later-phase ingestion, scoring, or Gmail features during Phase 1.

