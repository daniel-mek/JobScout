# ApplyOS product specification

Imported from the user-provided specification. The exact supplied text is preserved below.

## Repository decisions and precedence

The supplied specification describes the target product, not completed functionality. See [implementation status](IMPLEMENTATION_STATUS.md). Preserve working JobScout features while adding the target architecture incrementally. Discovery remains full-time early-career IT/CS without an assumed graduation year or restored student-program boosts. Historical internships may be truthful resume evidence. Existing deployed names are not renamed in this task. Immediate scope is inspection, permanent documentation, architecture/source policy, health checks, and Phase 1 readiness; Phase 1 has not started.

## Authoritative supplied specification

You are the lead software engineer and technical architect responsible for building a production-quality application called **ApplyOS**, an AI-assisted job discovery, job matching, application tracking, application preparation, and career intelligence platform designed primarily for early-career Computer Science and Information Technology candidates. You are working directly in the repository. Do not merely describe how the application should be built; inspect the repository, modify files, run commands, create migrations, implement features, test the application, fix failures, and maintain documentation. Preserve working code that already exists. If the repository is empty, initialize it. Build the product incrementally, keep the application runnable, and do not sacrifice working functionality to rush later features.

The purpose of ApplyOS is to function as a personal job-search operating system. The core workflow is: **Discover Jobs → Determine Eligibility → Match Against Resume → Explain Match → Prioritize → Prepare Application → User Applies → Track Application → Follow Up → Prepare for Interviews → Analyze Outcomes → Improve Future Recommendations.** The product should optimize for helping the user apply to better opportunities rather than maximizing raw application volume. Do not build an indiscriminate mass-application bot. The user must remain in control of final application submissions, recruiter messages, referral requests, follow-up messages, legal attestations, demographic questions, and other consequential external actions.

The complete product should support authentication; PDF and DOCX resume upload; resume text extraction; structured resume parsing; candidate profile review and editing; evidence linking between skills and resume experience/projects; resume versioning; multiple resume variants; career-path preferences; hard requirements versus soft preferences; editable role families; job ingestion from multiple permitted sources; company-career-site detection; job normalization; provenance; deduplication; job version history; job-description archival subject to source policy; saved searches; scheduled searches; source-health monitoring; early-career classification; requirement extraction; eligibility analysis; resume-to-job matching; explainable Resume Match scores; Application Priority scores; job freshness; scam/quality warning signals; Discover; Saved Jobs; manual job importing; user feedback; preference learning; application Kanban tracking; application status history; immutable job snapshots for applications; notes; deadlines; next actions; reminders; resume tailoring; application packet generation; cover letters; application-question drafting; recruiter/referral outreach drafts; company following; company monitoring; contacts; referrals; skill-gap analysis; application analytics; resume-performance analytics; source analytics; daily job briefs; in-app notifications; notification preferences; optional Gmail integration; optional Google Calendar integration; email-based application-status detection; interview preparation; mock interviews; data export; privacy controls; account deletion; integration disconnection; accessibility; security; observability; continuous integration; and deployment documentation.

Use a monorepo unless an existing architecture makes another structure clearly preferable. A preferred layout is:

apps/
  web/
  api/
  worker/

packages/
  shared/
  ui/
  job_sources/
  matching/
  ai/

docs/
infrastructure/
scripts/

Use a current stable Next.js version, React, TypeScript strict mode, App Router, Tailwind CSS, shadcn/ui or an equivalent mature accessible component system, Zod, and TanStack Query where appropriate for the frontend. Build a modern professional SaaS dashboard. Do not design ApplyOS as a giant chatbot. AI should appear as contextual workflow functionality. Optimize primarily for desktop job-search workflows while maintaining responsive behavior.

Use Python, FastAPI, Pydantic, SQLAlchemy, and Alembic for the backend. Separate routers, services, repositories, and domain/business logic. Do not place significant business logic directly in HTTP route handlers. Use PostgreSQL as the primary database. Support pgvector if useful for semantic similarity. Use relational models for important searchable data; use JSONB selectively rather than turning the entire database into unstructured JSON.

Use Redis and Celery, Dramatiq, RQ, or another mature job-worker system for asynchronous processing. Background jobs will eventually handle resume parsing, job ingestion, scheduled searches, normalization, deduplication, job classification, match recalculation, company monitoring, daily digests, notification generation, and optional email synchronization. Design background tasks to be idempotent where practical and avoid duplicate executions.

Create a file-storage abstraction. Local filesystem storage is acceptable for development, but production should support S3-compatible object storage. Store uploaded resumes, generated variants, exported materials, and permitted archived documents through the abstraction. Never expose arbitrary server filesystem paths.

Implement secure authentication. At minimum support email-based authentication and architect it so Google OAuth can later be added. Hash passwords securely. Implement protected routes, ownership checks, sign-up, sign-in, sign-out, session management, and correct authorization. A user must never gain access to another user's resume, candidate profile, saved jobs, applications, contacts, notifications, or AI artifacts by changing an identifier.

Create an LLM provider abstraction rather than tightly coupling the product to one model provider. It should conceptually support operations such as parse_resume, parse_job, classify_job, compare_resume_job, explain_match, suggest_resume_changes, generate_cover_letter, generate_application_answers, generate_outreach, generate_interview_questions, and evaluate_mock_interview_answer. Anthropic Claude may be the initial provider, but the system must not depend exclusively on one vendor. Programmatically consumed AI responses must use structured schemas and be validated through Pydantic or an equivalent validation layer. Malformed model output must fail safely.

Truthfulness is a critical system rule. ApplyOS must never fabricate employers, experience, responsibilities, employment dates, projects, technologies, skills, certifications, education, achievements, numerical results, or years of experience. AI may rewrite truthful content, reorder sections, emphasize relevant evidence, improve phrasing, and suggest that the user provide missing information, but it must never invent qualifications. Significant generated candidate claims should be traceable to confirmed candidate evidence.

During onboarding, support the flow: **Welcome → Sign Up / Sign In → Upload Resume → Parse Resume → Review Candidate Profile → Choose Career Paths → Configure Job Preferences → Configure Hard Requirements → Dashboard.** Onboarding state must persist across refreshes. Completed users should go directly to the dashboard; incomplete users should resume at the correct step.

Support PDF and DOCX uploads. Validate MIME type, extension, and maximum file size. Separate resume text extraction from AI resume parsing. Create a ResumeTextExtractor and ResumeParser abstraction. Extract structured fields including name, general location, education, professional experience, internships, projects, skills, programming languages, frameworks, databases, cloud platforms, operating systems, developer/IT tools, certifications, graduation date, and experience duration where sensible. If no AI API key is configured, provide deterministic development/demo parsing so tests and local development do not depend on live model calls.

After parsing, never silently trust the result. Display a profile-review page telling the user: “We extracted the following information from your resume. Review it before we use it for job matching.” Allow editing, adding, deleting, and correcting education, experiences, projects, skills, certifications, location, graduation date, and related structured information. The reviewed profile becomes the confirmed candidate profile.

Create reusable CandidateProfile, Education, Experience, Project, Skill, CandidateSkill, Certification, Resume, ResumeVersion, CareerPreference, JobSearchPreference, and HardRequirement models. Resume-derived skills should optionally include confidence and evidence linking them back to experiences or projects. Preserve resume history. A newly uploaded master resume should create a new version and trigger profile review rather than silently replacing the previous confirmed state.

Initial editable career-role families should include Software Engineering, Software Development, IT / Systems, Cloud / DevOps, Cybersecurity, Networking, Data, QA / Testing, Technical Support, Application Support, and Technology Programs. Support multiple role-family selections. Do not permanently hardcode the taxonomy into frontend conditionals; persist it in the database and allow future expansion.

Separate hard requirements from soft preferences. Hard requirements determine whether a job is removed or strongly flagged. Preferences affect ranking. Hard requirements may include maximum requested experience, whether clearance-required jobs are allowed, whether contract jobs are allowed, relocation constraints, geographic constraints, and optional sponsorship/work-authorization constraints supplied by the user. Soft preferences may include remote/hybrid/on-site, preferred locations, minimum preferred salary, desired industries, preferred companies, and role-family preference. Never infer a hard filter automatically from user behavior.

Build job ingestion around documented, permitted data sources. Do not design ApplyOS around arbitrary scraping. Create a formal SourceRegistry and SourcePolicy system. Each source configuration should include identifier, display name, category, official documentation URL, policy/terms URL when available, retrieval method, credential requirements, attribution requirements, source-link requirements, rate-limit configuration, description-storage policy, redistribution policy, enabled state, compliance status, last policy-review date, and adapter version. Supported compliance statuses should include APPROVED, NEEDS_REVIEW, and DISABLED. Only APPROVED automated sources may run scheduled ingestion.

Prioritize these source types:

**Tier 1: Official ATS/public employer posting APIs.** Implement adapters for Greenhouse public Job Board API, Lever public Postings API, Ashby public Job Posting API, and SmartRecruiters public Posting API. Use only publicly listed external jobs. Do not access private/internal recruiting data. Before implementing each source, consult its current official documentation rather than guessing endpoint behavior.

**Tier 2: Government/official databases.** Support the official USAJOBS API. If required credentials are missing, keep the adapter present but return a configuration-required health state rather than breaking the application.

**Tier 3: Approved job-data aggregators.** Support Adzuna as an optional credentialed source. Require server-side credentials and never expose secrets in frontend code. Support Remotive as an optional remote-job source only if current attribution, linking, and redistribution requirements are satisfied. Provider-specific attribution and storage rules must be enforced programmatically rather than treated as informal documentation.

**Tier 4: Company career sites.** Create a CareerSiteDetector. Given a company-career URL, first detect whether it is Greenhouse, Lever, Ashby, or SmartRecruiters. Then check for an official company jobs API, official RSS/Atom/XML/JSON feed, or publicly served schema.org JobPosting JSON-LD. Only consider generic HTML retrieval when the page is public, no login or CAPTCHA bypass is required, no anti-bot evasion is used, provider/site rules permit it, and rate limits are conservative. Unsupported sources must gracefully fall back to manual import.

Do not build automated scraping adapters for LinkedIn, Indeed, ZipRecruiter, Glassdoor, or similar restricted platforms unless a legitimate official API, licensed data agreement, approved partner integration, or user-authorized connector is later configured. Links from those sources may be saved manually where appropriate, but ApplyOS must not depend on scraping them.

Do not assume a universal public Workday API exists for arbitrary employers. Generic Workday automated ingestion should remain NEEDS_REVIEW unless an employer-specific compliant method is verified. Do not build a default reverse-engineered Workday scraper. Manual import must work even when automatic ingestion is unavailable.

If ApplyOS cannot determine that a source's automated access is permitted, fail closed. Mark it NEEDS_REVIEW or DISABLED rather than silently enabling it.

Create a reusable JobSourceAdapter interface with methods conceptually similar to source_name, search, get_job, normalize, and health_check. Keep provider-specific code isolated in individual adapters. The rest of the product should operate only on normalized internal job models.

Create Company, JobPosting, JobPostingVersion, JobSource, JobSourceRecord, SourceHealth, RoleFamily, SearchTitle, SavedSearch, and SearchRun models. A normalized JobPosting should support title, normalized title, company, location, country, remote/hybrid/on-site classification, employment type, salary minimum and maximum, currency, job description, responsibilities, requirements, minimum and maximum experience if known, education requirements, clearance requirements, work-authorization information, posted_at, discovered_at, last_seen_at, canonical application URL, and active/inactive state. Do not invent missing values.

Store provenance for every imported job: provider, source job identifier, source URL, retrieval timestamp, provider-posted date where supplied, last seen time, and permitted raw/normalized source data. The application should always be able to explain where a listing came from.

Normalize company names, job titles, location, work arrangement, employment type, salary, and dates while preserving original source values. Use stable enums such as FULL_TIME, PART_TIME, CONTRACT, INTERNSHIP, TEMPORARY, UNKNOWN and REMOTE, HYBRID, ONSITE, UNKNOWN.

Implement job deduplication. Use high-confidence signals such as provider identifiers and canonical application URLs first, followed by normalized company, normalized title, location, posting date, and description similarity. Embeddings may be used as an additional signal. Never merge jobs solely because titles are similar. One canonical JobPosting may contain multiple JobSourceRecords. Prefer the employer-hosted direct application URL when a verified equivalent employer source exists, but never invent one.

Version meaningful posting changes including description, salary, requirements, location, application URL, and active status. Do not create unnecessary versions for timestamp-only updates. Archive enough posting information for Saved Jobs and applications to retain the posting even after the external source disappears, subject to each source's storage policy.

Implement secure manual job importing through a “+ Add Job” experience. Accept a URL, identify a supported ATS/provider if possible, retrieve only permitted public content, normalize it, deduplicate it, and return the canonical job. When automatic parsing is unavailable, offer a manual form for title, company, location, description, and application URL. Secure all server-side URL fetching against SSRF. Do not allow fetching localhost, loopback, private IPv4 ranges, private IPv6 ranges, link-local addresses, cloud metadata endpoints, internal hostnames, or unsafe redirect targets. Re-check redirect destinations.

Implement saved searches based on role family, search title, location, work arrangement, employment type, minimum match later, freshness, and enabled sources. Background execution should invoke only approved source adapters, normalize results, deduplicate them, persist versions, and record SearchRun metrics. Track jobs found, inserted, deduplicated, provider failures, start/end times, and status. Provider failures must be isolated so one broken source cannot break the entire search.

Track source health, including healthy, degraded, configuration required, policy review required, and unavailable. Track last success, last failure, and relevant rate-limit state. Use conservative per-provider throttling, retry behavior, and backoff.

Implement a dedicated job requirement extraction layer. Create JobRequirement and JobSkill models that distinguish required from preferred qualifications and retain original evidence text and confidence. Parse required skills, preferred skills, experience, education, certifications, clearance, work authorization, location, and other requirements. Low-confidence interpretation must remain uncertain rather than becoming fact.

Normalize conservative skill aliases such as JS → JavaScript, Postgres → PostgreSQL, and Amazon Web Services → AWS. Avoid aggressive synonym mapping that produces false matches.

Build an early-career classifier with labels NEW_GRAD, TRUE_ENTRY_LEVEL, EARLY_CAREER, REASONABLE_REACH, MID_LEVEL, SENIOR, and UNKNOWN. Use the full posting rather than only the title. Positive signals include 0 years, 0–1 years, 0–2 years, internship experience accepted, recent graduate, new graduate, junior, associate, engineer I, and rotational program. Negative signals include 4+ years, 5+ years, senior, lead, principal, staff, architect, and manager. Deterministic obvious rules should run before AI-based interpretation. If a title says “entry level” but the description requires 5+ years, the requirements should dominate.

Build eligibility statuses ELIGIBLE, ELIGIBLE_WITH_WARNING, UNKNOWN, and INELIGIBLE. Evaluate user hard requirements. Examples include clearance, explicit experience caps, employment type, geographic restrictions, and work-authorization requirements. Unknown source information must remain UNKNOWN and must not be guessed.

Maintain two separate scores:

**Resume Match** answers: “How qualified is this user for this job?” Initial configurable weights may be Skills 35%, Experience 20%, Role Relevance 15%, Education 10%, Location 10%, Preferences 5%, and Other Qualifications 5%. The final score should be deterministic from structured component scores. AI may help interpret semantic relationships but must not simply invent an overall score.

**Application Priority** answers: “How worthwhile is it to apply now?” Initial configurable weighting may be Resume Match 55%, Freshness 15%, Early-Career Suitability 10%, Location/Work Arrangement 5%, Salary Preference 5%, Company/User Preference 5%, and Source/Application Quality 5%. Ineligible jobs should have priority strongly capped. Freshness must never override hard disqualification.

Candidate skill evidence should matter. A skill backed by multiple confirmed experiences/projects may carry stronger evidence than a bare keyword. Personal projects must not be converted into fabricated years of professional experience.

Classify recommendations as EXCELLENT_MATCH, STRONG_APPLY, APPLY, REASONABLE_REACH, LONG_SHOT, or SKIP. Missing a preferred qualification should be treated differently from missing a required qualification. Small gaps should not automatically eliminate otherwise appropriate early-career roles.

Every match result must be explainable. Show Strong Matches, Partial Matches, Missing Qualifications, Experience Fit, Education Fit, Location Fit, Eligibility Warnings, and Recommended Action. Never claim the user possesses a qualification absent from confirmed profile evidence.

Create versioned JobMatch records linking user, canonical job, candidate profile version, resume version, scoring algorithm version, component scores, Resume Match score, Application Priority score, recommendation class, explanation, and calculated timestamp. Recalculate when the profile changes, resume changes, preferences change, hard requirements change, job requirements change, or scoring algorithm version changes. Do not synchronously recalculate thousands of jobs in a foreground request; use workers.

Build a professional `/discover` experience. Default sort should be Application Priority descending. Job cards should show company, title, location, arrangement, salary if known, posted age when known, discovered age, Resume Match, Application Priority, early-career label, recommendation, and source count. Provide actions for Save, Not Interested, View Match, and Open Application. Support views such as For You, Fresh Opportunities, Excellent Matches, Reasonable Reaches, Recently Discovered, and later Followed Companies.

Support Discover filters for role family, title, company, location, remote/hybrid/on-site, employment type, salary, minimum match, minimum priority, recommendation, early-career category, freshness, source, review state, and saved state. Use database-driven pagination. Preserve useful filtering in URL query state where practical.

Build `/jobs/[id]` with job overview, company, location, arrangement, salary, employment type, posted/discovered times, application URL, source list, archived description, Resume Match, Application Priority, Why You Match, Strong Matches, Partial Matches, Missing Skills, Experience Fit, Education Fit, Eligibility, Why You Should Apply, and Priority Breakdown. Do not bury important warnings.

Build `/saved-jobs`. Track saved_at, notes, optional deadline, and the relevant job version. Unsaving must not delete canonical job records. Track explicit Interested and Not Interested feedback. Negative-reason options may include Too Far, Wrong Role, Too Senior, Salary Too Low, Contract, Clearance Required, Company, Industry, Already Applied, and Other. Feedback should influence learned preferences modestly but never silently become a hard filter.

Track explicit job review state. Saving or dismissing a job may count as reviewed. Avoid fragile browser-time heuristics.

Generate a Daily Job Brief. Sections may include New Excellent Matches, New Strong Applies, Fresh Reasonable Reaches, Jobs from Followed Companies later, and Jobs Needing Review. Do not fill the brief with low-quality jobs just to reach an arbitrary count.

Create in-app Notifications. Initial types may include NEW_HIGH_MATCH_JOB, FRESH_OPPORTUNITY, SAVED_SEARCH_COMPLETE, FOLLOWED_COMPANY_JOB, APPLICATION_REMINDER, ASSESSMENT_DEADLINE, INTERVIEW_REMINDER, and EMAIL_STATUS_SUGGESTION. Allow read/unread state and notification preferences.

Create an application tracker using statuses SAVED, PREPARING, APPLIED, ONLINE_ASSESSMENT, RECRUITER_SCREEN, INTERVIEW, FINAL_INTERVIEW, OFFER, REJECTED, and WITHDRAWN. Create Application and ApplicationStatusHistory models. Each transition should retain previous status, new status, timestamp, source, and optional note. Never store only the latest state.

From a job page, provide “Prepare Application.” This creates a PREPARING application. The actual external application should still be completed by the user. Afterward provide “Mark as Applied,” recording applied_at and the selected resume version. Prevent accidental duplicate active applications to the same canonical posting.

When application preparation begins, and definitely when marked applied, create an immutable application-linked snapshot/version of the job subject to source-policy storage rules. The user must retain the relevant job description even if the external posting later changes or disappears.

Build `/applications` with both Kanban and table/list views. Kanban must support drag-and-drop plus an accessible non-drag menu alternative. The list should support company, role, status, applied date, match, next action, and due date. Application detail should show status, timeline, match at application time, archived job, resume used, notes, deadlines, next action, URL, contacts, and generated materials.

Support chronological notes, generalized ApplicationEvent/deadline records, next-action text and date, upcoming assessment deadlines, interviews, application deadlines, and deterministic follow-up suggestions. For example, an APPLIED application with no subsequent activity for a configurable number of days may generate “Consider following up.” Never contact an employer automatically.

Provide CSV export of application tracking data without exposing unnecessary internal database identifiers.

Build resume management under `/resumes`. Keep a Master Resume plus variants. Suggested variants include General, Software Engineering, IT / Systems, Cloud / DevOps, Cybersecurity, and Data, while allowing custom variants. Every variant should reference a master ResumeVersion and maintain version history.

Build an explicit CandidateClaimValidator. Before generated resume bullets, cover-letter claims, application answers, recruiter messages, or interview talking points are accepted as factual claims, verify their support from confirmed candidate profile evidence, master resume, or confirmed projects/experience. Unsupported claims must be rejected or marked as requiring user confirmation.

Implement a Tailor Resume workflow displaying a diff for each proposed change: Current, Suggested, Reason, Evidence. Allow Accept, Reject, and Edit. Never silently modify the user's master resume. Permitted rewriting includes stronger verbs, clearer phrasing, reordering, condensing, and relevant emphasis. Forbidden behavior includes inventing employers, skills, metrics, responsibilities, certifications, technologies, projects, or years of experience.

Recommend the best resume variant for each job and explain why. For example, a Cloud / DevOps variant may be recommended when the posting emphasizes Azure, scripting, Linux, and infrastructure, but only if those things actually appear in the user's evidence.

Implement “Generate Application Packet.” Generate and persist the recommended resume variant, job-specific resume changes, cover letter, Why This Company, Why This Role, Tell Us About Yourself, skills to emphasize, projects to emphasize, likely application questions, recruiter outreach draft, and interview talking points. Every output must remain grounded.

Create AIArtifact records including artifact type, provider, model, prompt version, source profile version, source resume version, source job version, content, and creation timestamp. Do not silently overwrite generated artifacts when source data changes. Instead support explicit regeneration.

Generate concise role-specific cover letters that do not merely repeat the resume. Do not invent current company facts. Application answers and salary-response suggestions should clearly be drafts. Recruiter, employee, alumni, referral, follow-up, and thank-you messages must never be sent without user approval.

Build `/companies`. Each company should show relevant active jobs, saved jobs, applications, contacts, notes, and follow status. Allow Follow and Unfollow. Company monitoring must reuse existing approved SourceRegistry adapters. Do not create a new unsafe scraper merely because a user follows a company. Unsupported career sites should show monitoring unavailable while allowing the URL to be stored manually.

Build `/contacts`. Store name, company, role, email, profile URL, relationship type, notes, and status. Relationship types may include Recruiter, Hiring Manager, Employee, Alumni, Friend, Referral Contact, and Other. Contact statuses may include NOT_CONTACTED, MESSAGE_DRAFTED, MESSAGE_SENT, RESPONDED, REFERRAL_REQUESTED, and REFERRAL_RECEIVED. Track ContactInteraction events such as message, email, call, meeting, and note. Allow linking contacts to companies and applications.

Track referrals as requested, pending, received, or declined. Generate outreach drafts but never send automatically.

Create Reminder records attachable to applications, contacts, companies, or jobs. Support due date, completed state, snooze, notes, and dashboard surfacing.

Implement durable SavedSearch scheduling. At minimum support MANUAL, EVERY_6_HOURS, and DAILY. Prevent overlapping executions for the same search through locking/idempotency. Respect per-source rate limits. Store last_run, next_run, last_success, and last_failure. Support daily in-app Job Brief generation.

Build `/insights` with Overview, Skills, Applications, Resumes, Sources, and Roles. Calculate applications, interviews, offers, rejections, active/no-response, application-to-interview rate, and interview-to-offer rate. Support date ranges and breakdowns by role family, resume variant, source, location, and match-score range. Always show sample sizes. Do not imply causation from correlations.

Build skill-gap analysis across otherwise promising jobs. Rank missing required and preferred skills separately. Use wording such as “Docker was missing from your confirmed profile in 23 otherwise promising jobs.” Never claim learning one technology guarantees jobs.

Track resume performance using applications, interviews, offers, and rates per resume variant. Flag low sample sizes. Track source analytics including discovered, saved, applied, and interviewed counts. Do not equate a high-volume source with a high-quality source.

Implement recommendation learning from explicit Interested/Not Interested feedback, saves, applications, withdrawals, and outcomes. Explicit preferences must outweigh inferred behavior. Inferred preferences may modestly affect ranking but must never silently become hard filters. Add a setting called “Use activity to improve recommendations” and allow disabling it. When learning materially changes a recommendation, provide an explanation such as “Slightly boosted because you frequently save Cloud / DevOps roles.”

Support optional Gmail integration using supported Google OAuth APIs and least-privilege scopes. Encrypt OAuth tokens at rest and never log them. Allow disconnecting and revoking local credentials. Classify job-search emails into APPLICATION_CONFIRMATION, ASSESSMENT, INTERVIEW_REQUEST, REJECTION, OFFER, RECRUITER_MESSAGE, FOLLOW_UP, or OTHER. Use deterministic logic where obvious and structured AI classification where helpful.

Attempt to associate emails with applications cautiously using company, job title, sender/domain, application date, and message text. If confidence is low, ask the user. By default, email-derived status changes should be suggestions rather than automatic mutations. Extract assessment/interview deadlines cautiously and show evidence before creating events/reminders if uncertain.

Support optional Google Calendar integration. Allow reading relevant recruiting events where authorized and creating interview events after user confirmation. Never modify unrelated events. Use incremental synchronization where supported rather than repeatedly downloading full mailbox/calendar history.

Build Interview Mode under `/applications/[id]/interview`, primarily for RECRUITER_SCREEN, INTERVIEW, and FINAL_INTERVIEW applications. Include Company Brief, Role Brief, Best Talking Points, Likely Questions, Questions to Ask Employer, Mock Interview, and Interview Notes. Use the immutable application-linked job snapshot as the role source. Separate job-derived facts, stored company data, and optional external current research. Never invent current company facts.

Select talking points only from confirmed candidate evidence. Generate behavioral, technical, resume-specific, project-specific, and role-specific questions. For IT roles, include troubleshooting; software roles may include programming/system design where appropriate; cloud roles may include infrastructure; networking, security, data, QA, and other categories should adapt accordingly. Do not assume all CS jobs use LeetCode-style interviews.

Store mock interview sessions, questions, answers, feedback, and timestamps. After an answer show What Was Strong, What Could Improve, Missing Details, and Suggested Structure. Use STAR for behavioral answers when appropriate. Never invent a better story; if a metric or outcome is missing, say the answer could be strengthened if the user has a specific result.

Support interview notes before and after interviews, including questions asked, people met, reflection, and follow-up needs. Generate thank-you drafts when requested but never automatically send them.

Create JobQualityAssessment with LOW_RISK, POTENTIAL_CONCERN, HIGH_CONCERN, and UNKNOWN. Potential signals include unclear employer identity, employer/application-domain mismatch, commission-only language, unusually broad salary, duplicate posting across unrelated locations, vague description, repeated reposting, staffing-agency ambiguity, and staleness. Never label a posting definitely fraudulent from weak heuristics. Prefer user-facing wording such as “Potential concern” and show reasons.

Implement privacy controls. Allow users to export important account data, delete uploaded resumes, disconnect integrations, delete application data where appropriate, and delete their account. Account deletion should remove/revoke OAuth credentials and handle files, AI artifacts, contacts, applications, reminders, and other owned data according to documented retention behavior.

Implement observability through structured backend logging, worker logging, request/correlation IDs, job-source health, background-job failure visibility, search-run diagnostics, and error-reporting hooks. Never log passwords, OAuth tokens, secrets, or unnecessary raw resume contents.

Audit and protect authentication, authorization, IDOR, CSRF, XSS, SQL injection, SSRF, file uploads, OAuth, redirects, CORS, rate limiting, and secrets handling. Use safe defaults.

Build accessible interfaces. Support keyboard navigation, semantic HTML, labels, useful focus states, ARIA where appropriate, sufficient contrast, and non-drag alternatives to Kanban drag-and-drop. Error messages should be associated with inputs.

Provide meaningful user-facing error states for resume parse failure, AI-provider failure, source unavailability, policy-disabled sources, invalid job URLs, expired OAuth credentials, background-task failures, no job matches, and rate-limit situations. Never expose raw stack traces to users.

Build the desktop navigation with Dashboard, Discover, Saved Jobs, Applications, Companies, Contacts, Resumes, Insights, Notifications, and Settings. Dashboard should answer “What should I do today?” through Today's Best Jobs, Applications Requiring Action, Application Pipeline, Weekly Progress, Skill Insight, Recent Notifications, and later Contacts/Followed Companies requiring attention. Never show fake production metrics as though they belong to the real user.

Create realistic seed/demo data. Local development and CI must not depend on production ATS APIs, Gmail, Calendar, Anthropic, or other external services. Mock external services in automated tests. Demo content must be clearly labeled.

Use `.env.example` and document every environment variable, including required, optional, and development-only categories. Never commit secrets. Potential variables may include DATABASE_URL, REDIS_URL, file/object-storage configuration, ANTHROPIC_API_KEY, Google OAuth credentials, USAJOBS credentials, ADZUNA_APP_ID, ADZUNA_APP_KEY, and appropriate frontend API/base URLs.

The recommended deployment architecture is: **Vercel for `apps/web` only**, a separate service capable of running FastAPI for `apps/api`, a separate persistent worker service for `apps/worker`, managed PostgreSQL, managed Redis, and S3-compatible object storage. The frontend communicates with FastAPI over HTTPS. Do not force the background worker into Vercel serverless execution. Maintain deployment-provider abstraction where possible; do not hardcode the rest of the backend to a single hosting vendor unless explicitly instructed.

For Vercel, preserve the monorepo and deploy `apps/web` as the Vercel project root. Configure the Next.js project to consume a production backend API URL through environment configuration. Ensure secrets such as database credentials, Anthropic keys, Google client secrets, USAJOBS credentials, and Adzuna secrets are never exposed in `NEXT_PUBLIC_` variables. Only intentionally public browser configuration may use `NEXT_PUBLIC_*`.

Provide production-capable Dockerfiles for the API and worker where appropriate. Document web deployment, API deployment, worker deployment, scheduler behavior, PostgreSQL, Redis, object storage, environment variables, database migrations, health checks, backup recommendations, and restore considerations.

Create and maintain these permanent repository documents:

- `CLAUDE.md`
- `docs/PRODUCT_SPEC.md`
- `docs/ARCHITECTURE.md`
- `docs/SOURCE_POLICY.md`
- `docs/SECURITY.md`
- `docs/IMPLEMENTATION_STATUS.md`
- `docs/DEPLOYMENT.md`
- `docs/OPERATIONS.md`
- `README.md`

`CLAUDE.md` should tell future Claude Code sessions to read the permanent product documentation first, preserve architecture, use the source policy, run tests, avoid implementing future work prematurely, and treat PRODUCT_SPEC.md as authoritative.

`docs/IMPLEMENTATION_STATUS.md` should maintain status for major features using NOT_STARTED, IN_PROGRESS, COMPLETE, PARTIAL, or BLOCKED.

Implement the project incrementally in these phases:

**Phase 1:** foundation, authentication, resume upload, parsing, candidate-profile review, preferences, hard requirements, dashboard shell.

**Phase 2:** SourceRegistry, compliant ATS/API integrations, company-career-site detection, job ingestion, normalized job data, provenance, deduplication, versioning, archival, manual job import, source health.

**Phase 3:** requirement extraction, skill normalization, early-career classification, hard eligibility, Resume Match, Application Priority, explanations, recalculation.

**Phase 4:** polished Discover, filters, Fresh Opportunities, Saved Jobs, feedback, saved searches, Daily Job Brief, notification foundation.

**Phase 5:** application tracking, Kanban/list views, status history, immutable job snapshot, notes, deadlines, next actions, follow-up suggestions, CSV export.

**Phase 6:** resume variants, claim validation, resume tailoring, diff approvals, application packets, cover letters, application answers, outreach drafts, AI artifact versioning.

**Phase 7:** followed companies, compliant company monitoring, contacts, interactions, referrals, reminders, durable search scheduling, Daily Brief scheduling, notification preferences.

**Phase 8:** career intelligence, skill gaps, application analytics, resume analytics, source analytics, role analytics, bounded preference learning.

**Phase 9:** optional Gmail and Google Calendar integrations, email classification, application association, status suggestions, assessment/interview deadlines, incremental sync.

**Phase 10:** Interview Mode, job/company brief, grounded talking points, question generation, mock interviews, interview feedback, interview notes, thank-you drafts.

**Phase 11:** job-quality warnings, privacy controls, source-compliance visibility, observability, accessibility, error UX, dependency/security review, product hardening.

**Phase 12:** comprehensive specification audit, dead-UI audit, authorization audit, AI-grounding audit, source-policy audit, database/index audit, performance pass, security pass, CI, production deployment readiness, full end-to-end workflow verification.

Do not implement all phases simultaneously. Work through them sequentially unless explicitly instructed otherwise. Do not implement features from future phases simply because their eventual schema is known. Add only the minimum forward-compatible foundation necessary for the current phase.

At the beginning of every phase: inspect the repository; read CLAUDE.md, PRODUCT_SPEC.md, ARCHITECTURE.md, SOURCE_POLICY.md, SECURITY.md, and IMPLEMENTATION_STATUS.md; briefly state what exists; identify relevant architectural constraints; and state the implementation approach.

At the end of every phase: run formatting, frontend linting, TypeScript type checking, Python lint/static checks, unit tests, integration tests, applicable Playwright tests, and previous-phase regression tests. Fix failures before declaring completion. Do not disable, skip, weaken, or delete legitimate tests just to obtain a passing build. Update IMPLEMENTATION_STATUS.md and relevant documentation.

Testing must include unit tests for deterministic business logic; integration tests for backend/application flows; and Playwright coverage for major end-to-end workflows. Critical test cases include authentication, ownership authorization, upload validation, structured parser validation, onboarding persistence, normalization, provider adapters through mocked HTTP, provider failure isolation, SourcePolicy gating, SSRF protection, deduplication, job versioning, early-career contradictions, eligibility, required-versus-preferred skill handling, score calculations, priority caps, evidence grounding, saved jobs, feedback, application status history, application job snapshots, reminder behavior, resume master immutability, unsupported claim rejection, AI output validation, preference-learning bounds, Gmail association confidence, interview grounding, privacy deletion, and cross-user data protection.

CI must never depend on live external APIs. Configure GitHub Actions or equivalent CI to run appropriate frontend linting, TypeScript checks, Python checks, unit tests, integration tests, and Playwright if practical.

During the final audit, search the repository for TODO, FIXME, HACK, placeholder, temporary, not implemented, coming soon, dead buttons, routes without functionality, fake production data, forms that do not persist, unbounded queries, N+1 database behavior, duplicate AI calls, repeated resume parsing, unnecessary recalculation, insecure URL fetches, missing authorization, and unhandled errors. Fix legitimate gaps.

At final completion, verify this user journey end to end:

Create account  
→ Upload resume  
→ Parse and correct candidate profile  
→ Select career paths  
→ Configure preferences and hard requirements  
→ Run permitted job searches  
→ Ingest jobs from multiple supported sources  
→ Normalize and deduplicate results  
→ View personalized job matches  
→ Understand why a job matches  
→ Save a job  
→ Provide feedback on another job  
→ Tailor a resume  
→ Generate an application packet  
→ Prepare an application  
→ Open the employer application page  
→ Mark the application as applied  
→ Track next action/deadline  
→ Move the application through hiring stages  
→ Add a contact/referral  
→ Receive reminders  
→ Prepare for an interview  
→ Conduct a mock interview  
→ Record interview notes  
→ View application, resume, source, and skill analytics.

The final specification audit must classify every significant requirement as COMPLETE, PARTIAL, NOT_IMPLEMENTED, BROKEN, or BLOCKED_EXTERNALLY. Do not call something complete simply because a database model or component exists; trace actual end-to-end behavior.

Do not claim the product is production-ready merely because it builds. Production readiness requires passing tests, verified authorization, safe source access, SSRF protections, secure uploads, protected secrets, compliant integrations, stable deployment, worker/scheduler operation, healthy database migrations, error handling, observability, backup documentation, and a successful end-to-end user flow.

Your immediate task when receiving this specification is:

1. Inspect the repository.
2. Determine what currently exists.
3. Create or update CLAUDE.md and the permanent docs listed above so this specification is preserved inside the repository.
4. Establish the architecture and SourcePolicy.
5. Identify existing development commands, package managers, frameworks, and configuration.
6. Run an initial health check of the repository.
7. Report any conflicts or blockers.
8. Tell me whether the repository is ready for Phase 1.
9. Do not begin later phases until instructed.

Once ready, implement phases sequentially, keep the system tested after every phase, and treat this document as the authoritative product specification.

