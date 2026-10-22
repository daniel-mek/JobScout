# Source policy

## Enforcement contract

Only an enabled APPROVED source may perform automated ingestion. NEEDS_REVIEW means permission, retention, attribution, or implementation evidence is incomplete; DISABLED means prohibited/unconfigured access must not run. A public endpoint alone is not permission to retain or redistribute descriptions.

Phase 2 implements runtime SourceRegistry/SourcePolicy controls in the authenticated app; see [PHASE2.md](PHASE2.md). Automated defaults remain unapproved. Approval is scoped to explicit board IDs and is only recorded by the operator command. Legacy scout fetchers retain separate configuration; this does not certify or disable them. They are not exposed through the account API.

Each registry entry must retain identifier, display name/category, official documentation URL, policy/terms URL, retrieval method, credential requirements, attribution/source-link obligations, rate configuration, description-storage and redistribution rules, enabled flag, compliance status, last policy-review date, reviewer evidence, and adapter version. Unknown obligations must remain explicit, never inferred approval.

## Inventory and review evidence

Official API documentation for the four ATS providers was inspected on 2026-10-16 and rechecked during Phase 2 on 2026-10-22. This is a technical documentation review; terms, employer-specific permissions, retention and redistribution review remain incomplete. Consequently no new production registry entry is declared APPROVED here.

| Source | Current code | Official reference / policy review target | Registry/review status |
| --- | --- | --- | --- |
| Greenhouse | Public board list reader | https://docs.greenhouse.io/job-board | NEEDS_REVIEW: runtime gated; usage/storage approval pending |
| Lever | Public postings reader | https://github.com/lever/postings-api | NEEDS_REVIEW: runtime gated; usage/storage approval pending |
| Ashby | Public board reader with isListed filtering | https://developers.ashbyhq.com/docs/public-job-posting-api | NEEDS_REVIEW: runtime gated; usage/storage approval pending |
| SmartRecruiters | Public list/detail adapter; approval pending | https://developers.smartrecruiters.com/docs/posting-api | NEEDS_REVIEW: public adapter/pagination tested; terms approval pending |
| Simplify new-graduate community feed | Enabled in legacy watcher | https://github.com/SimplifyJobs/New-Grad-Positions | NEEDS_REVIEW: review source licensing and downstream storage/redistribution |
| USAJOBS | Optional credentialed adapter; configuration/approval pending | https://developer.usajobs.gov/ | NEEDS_REVIEW; credentials required before activation |
| Adzuna | Optional credentialed adapter; configuration/approval pending | https://developer.adzuna.com/ | NEEDS_REVIEW; credentials and attribution/storage terms required |
| Remotive | Disabled: public terms prohibit signup-gated listings | https://remotive.com/remote-jobs/api | DISABLED; signup-gated listings conflict with public terms |
| Workday / Eightfold | Legacy posting-detail code exists | Employer-specific official method must be verified | NEEDS_REVIEW; no universal Workday API assumed |
| Generic company HTML / JSON-LD / feeds | Legacy HTML fallback separate; new generic policy remains review-only | Each employer's official documentation and terms | NEEDS_REVIEW by employer; manual import fallback |
| LinkedIn, Indeed, ZipRecruiter, Glassdoor | No approved ingestion adapter | Official agreement or authorized connector would be required | DISABLED for automated scraping |
| Internship/community internship feeds | Removed from discovery defaults | Not part of current product discovery scope | DISABLED |

Reference URLs are discovery/review starting points, not evidence of completed terms review. Optional-provider technical references were checked in Phase 2; actual usage/storage permission still needs review. No credentialed source or live ingestion was tested in this assessment.

## Adapter and data rules

Use public external jobs only. Never call application-submission APIs, private recruiting APIs, internal destinations, or bypass login/CAPTCHA/anti-bot measures. Prefer supported ATS detection, documented employer feeds, then permitted public JobPosting JSON-LD. Unknown sites fall back to a manual form.

Persist provenance and source identifiers for every canonical job. Prefer verified employer application links. Provider date and retrieval time are distinct. Preserve missing values as unknown. Source failures must be isolated and surfaced as source health.

Source policy must control raw data, full descriptions, snapshots, generated summaries, exports, and application-linked archives. If storage is prohibited or unverified, retain only permitted metadata/link and explain that description archival is unavailable. Do not use an application snapshot to bypass retention restrictions.

Conservative throttling is per provider/employer, with configured concurrency, bounded backoff, Retry-After handling and isolated health states. Do not invent universal rate limits. Re-review terms on adapter changes, policy changes, and before activation.

## Required verification before enabling automation

Test approval gating, disabled credentials, attribution and original links in every display/export, retention enforcement, public-only results, malformed responses, empty feeds, provider isolation, retry limits and source-health reporting. All URL retrieval must use the SSRF controls in SECURITY.md and revalidate redirects. Record approved evidence and adapter version with the policy decision.

