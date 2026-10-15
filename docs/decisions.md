# Design decisions

The calls that shaped Scout, and why. Newest at the bottom.

| Date | Decision | Why |
|---|---|---|
| 2026-10-14 | Two data sources: the Simplify + Pitt CSC list and the vanshb03 list (MIT). | vanshb03 had 296 postings Simplify lacked, including every Microsoft row. See `reference-report.md`. |
| 2026-10-14 | IT support, help desk, and information technology titles stay in. | Simplify's README generator drops them; Scout reads the raw JSON so they can count. |
| 2026-10-14 | Page-change watching is a small hash-diff in GitHub Actions, not changedetection.io. | No server to run, $0. |
| 2026-10-14 | Nothing is borrowed from projects that auto-apply, log into job sites, or evade bot detection. | Scout never submits anything; the person always does. |
| 2026-10-14 | Resumes are one JSON file per variant plus one HTML template, rendered by WeasyPrint. No LaTeX. | Easier to read and restyle; the template holds no personal data, so it can be public. |
| 2026-10-14 | Company tiers match on the whole company name (minus Inc, LLC, Corp). | A word match ranked "Apple Bank" as Apple. |
| 2026-10-14 | Role exclusions include firmware, electronics engineering, business intelligence, data engineering, and data analysis. | Early runs surfaced those as software roles. |
| 2026-10-14 | Postings older than 90 days lose 10 points; older than 240 days are dropped. | A 375-day-old posting ranked 13th. The lists keep rows "active" long after they close. |
| 2026-10-14 | Freshman and sophomore programs are worth 45 points, so any exploratory program outranks a plain big-company posting. Campus and student ambassador roles are a target role of their own. | Programs built for first- and second-year students are the highest-value finds, and they are rare. |
| 2026-10-14 | Nine watched program pages (Microsoft, Google, NVIDIA, Apple, Amazon, GitHub Campus Experts). Meta, Notion, and Figma are not watched. | Meta answers HTTP 400 to any server fetch; the others are JavaScript apps with no text to compare. Every chosen page hashed identically on back-to-back fetches. |
| 2026-10-14 | A first `--seed` run marks every existing match as seen. | Otherwise the first live run would push dozens of old postings at once. |
| 2026-10-14 | Dependencies split: `requirements.txt` (PyYAML, used by the cron and tests) and `requirements-resume.txt` (WeasyPrint and friends). | Keeps each Actions run to about a minute. |
| 2026-10-14 | A page counts as changed only when new lines appear. Cloud region strings are stripped as noise. | The first cron run pushed a false alarm: Amazon's page names the AWS region that served it. |
| 2026-10-14 | Postings are read through Workday's public JSON endpoint and Google Careers' HTML, as well as Greenhouse, Lever, and Ashby. "Penultimate year", "rising junior or senior", and similar count as ineligible. | Most big-company postings are on Workday or Google Careers, and some are upperclassmen-only. |
| 2026-10-14 | The dashboard gets data by push from the cron (secret header) and sends phone edits back by pull. | No GitHub token lives on the Worker. |
| 2026-10-14 | The sync sends a named User-Agent. | Cloudflare returns 403 to Python's default User-Agent before the Worker sees the request. |
| 2026-10-14 | Dashboard look: Bowlby One headlines, Rubik body, Titan One wordmark with a bullseye "o", navy outlines with hard shadows, cream cards, one color per page, gold for the main action. Everything lives in `worker/src/tokens.css`. | A playful, poster-like identity that is easy to restyle in one file. |
| 2026-10-15 | Hourly schedule, with the 7:00 PM digest as a once-a-day check inside every run. | GitHub delays and skips scheduled runs; a forced digest schedule once went out at 11 PM. |
| 2026-10-15 | Rotating "latest jobs" carousel cards are stripped from program pages before comparing. | One page swapped its featured job daily and sent a false "page changed" push. |
| 2026-10-15 | A posting that rules you out sinks to the bottom, labeled, never hidden. | An upperclassmen-only posting was ranking third. |
| 2026-10-15 | State lives on a separate `data` branch; `main` holds only code. | Hourly bot commits were burying the real history. |
| 2026-10-15 | Home-screen icons as PNGs plus a web app manifest; gradients and motion that switch off for reduced-motion users. | iOS ignores SVG icons. |
