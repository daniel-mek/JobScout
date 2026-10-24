# Phase 3: matching and eligibility

Implemented deterministic requirement/skill extraction with original evidence, required/preferred/uncertain distinctions, conservative aliases, description-led early-career classification, explicit hard-conflict checks, separate weighted Resume Match/Application Priority, capped priority on disqualification, recommendation classes and explanations. Projects are never treated as professional years. Scores are provisional assessments, not interview probabilities.

JobRequirement, JobSkill and versioned owner-scoped JobMatch records persist through migration `5a54a22dd98b`. POST `/jobs/{id}/match` calculates one job after profile confirmation with session/CSRF authorization. The job page displays scores, warnings, evidence gaps, breakdowns and version references. Input fingerprints include job/profile/resume/settings/algorithm and freshness date; changed inputs create a new record. Repeating identical inputs reuses the record. Source-retention tightening deletes derived extraction/match evidence too.

Only explicit YYYY-MM ranges in confirmed experience contribute tenure. Overlaps are merged; projects, education, internships, invalid/future dates and ambiguous year-only dates are not silently converted into professional years. Ambiguous history leaves the duration comparison unknown. Literal degree level/subject and named certifications are compared with confirmed records; alternative/equivalent degrees remain uncertain. Credential matching does not independently verify validity or expiry. Neutral 50 components are disclosed. No AI interpretation or external submissions occur. Role relevance uses confirmed experience-title overlap.

Required/preferred section headings carry to following clauses; negation remains uncertain. Required experience dominates junior titles; senior titles cannot receive an entry-level label from incidental low-year requirements. Geographic checks normalize explicit countries; unknown countries stay unknown. Remote does not imply worldwide eligibility. Contract exclusions, experience caps, explicit required relocation, sponsorship exclusions and authorization conflicts are enforced. Citizenship is never inferred from work authorization. Unparsed constrained clauses require review. Salary preference needs matching currency and an explicit annual period; no annualization is invented. Projects are not tenure. Hard conflicts/archive cap priority at 10; mid/senior jobs cap at 35.

Settings now offers persisted per-owner scoring weights with optimistic revision checks; each group must include all components totaling 100. Migration `a6dc6576627d` adds ScoringPolicy. Policy changes, career role selections, source quality and freshness also invalidate match hashes. Hard caps always override custom weights.

## Persistent worker

Celery/Redis worker code is in `apps/worker/matching.py`, outside frontend requests. One beat scheduler reconciles every five minutes, paging at most 50 eligible job IDs per task, then queues individual calculations. Each task rereads current inputs. This recovers missed changes and broker outages; unchanged inputs reuse versions. Messages carry IDs only. PostgreSQL owner locks and unique hashes make duplicate delivery safe. Deleted/unreviewed records terminate cleanly. Transient database/broker failures retry with bounded backoff; later reconciliation provides recovery. No foreground request scans the catalog.

Local Compose supplies private Redis with AOF. Deployed broker storage must be durable and non-evicting; AOF every second may lose the final second, recovered by reconciliation. Keep one beat instance. API containers include the worker but do not start it automatically. No production worker/Redis resource is provisioned here.

```sh
docker compose -f infrastructure/compose.yaml up -d db redis
.venv/bin/alembic -c apps/api/alembic.ini upgrade head
# Run worker and beat in separate terminals after migrations:
.venv/bin/celery -A apps.worker.matching:app worker --queues=matching --concurrency=2 --loglevel=WARNING
.venv/bin/celery -A apps.worker.matching:app beat --schedule=data/matching-beat --loglevel=WARNING
```

Set server-only REDIS_URL privately. One-job calculation works without the worker; bulk recalculation requires the worker and beat. Phase 4 discovery has not started. Hosting remains paused.

Local verification: 84 API/unit/integration cases pass, with one real Redis worker case skipped without TEST_REDIS_URL. Ruff/mypy, frontend lint/typecheck/build and dependency consistency pass. Legacy tests pass (163 cases, two unchanged private-fixture skips). Browser downloads and local system package installation are unavailable here. CI supplies native PostgreSQL, Redis, a real worker process and Chromium; full remote verification is pending at this revision. The browser flow covers imports, matching, seniority warnings, persisted scoring edits and WCAG A/AA. Live provider calls and deployed behavior remain externally unverified.

Final verification: [CI 40051693369](https://github.com/daniel-mek/JobScout/actions/runs/40051693369), code commit `76e0e5ee2fa2b41799eaf2768d857c5e5b6dfa6b`, passed 85 cases on SQLite and 85 on native PostgreSQL, with no API skips and actual Redis/worker execution in both runs. All four browser flows passed (39.0 seconds), including scoring edits/persistence and WCAG A/AA checks. Frontend/static/build, migration upgrade/check/downgrade/upgrade, offline SQL generation and legacy checks passed. Separate legacy workflow 40051693416 passed. Production npm audit found zero known vulnerabilities. This supersedes the pending-CI checkpoint above. Phase 3 implementation and scoped verification are complete; production deployment and provider approvals remain outside this result.
