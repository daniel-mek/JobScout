# /interview - build or update the master profile, then rebuild the resumes

You are updating the candidate's ground truth. Nothing in this command invents a fact. Arguments (`$ARGUMENTS`) are optional: a topic to focus on ("internship dates", "new project"), or empty for a full pass.

## Step 1: Read, in this order, and do not re-read later

1. `me/README.md`
2. `me/master_profile.md` (ground truth; note every **[confirm]** flag and every `[bracket]`)
3. `me/voice.md`
4. `me/resumes/*.json` (the three resume variants: SWE, PM, IT)

If `me/master_profile.md` does not exist, say so and stop. The profile is written by the candidate first, not generated.

## Step 2: Collect every question first, then ask them as ONE numbered list

Build the list from, in this order:
- every **[confirm]** flag and `[bracket]` in the profile that the focus covers (all of them on a full pass);
- facts the resumes need that the profile lacks (a missing date, number, tool, or outcome);
- anything in a resume JSON that is not supported by the profile (this should never happen; if it does, it is the first question).

Rules for the list:
- One question per line, specific, with the current value shown ("Internship dates are 08/2025 to 03/2026 in the profile, marked estimated. Exact months?").
- Never ask something the profile already answers.
- Never ask them to fill voluntary self-identification fields; they fill those in themselves.
- Keep it under 10 questions. If there are more, ask the 10 that block a resume and list the rest as "later".

Then stop and wait for their answers. Do not draft anything in the meantime.

## Step 3: Write the answers back, in the same turn they give them

- Update `me/master_profile.md`: replace the **[confirm]** flag or `[bracket]` with the confirmed fact. A fact that only lives in chat is treated as unsupported next session and stripped, so it must land in the file now.
- If a fact changes something in a resume JSON, update every variant that carries it.
- Keep their writing rules: no em or en dashes, their full legal name in professional text, never "co-" for work they did alone.

## Step 4: Rebuild and check

```bash
.venv/bin/python scout/build_resume.py me/resumes/swe.json me/resumes/pm.json me/resumes/it.json
```

Every variant must print `[OK]` (one page) with the text-layer line clean. If one is two pages, trim the lowest-relevance bullet for that variant, never the font below 10pt, and rebuild.

Render each PDF to an image (`pdftoppm -r 70 -png`) into the scratchpad and look at it with the Read tool before presenting. Then show them the three PDFs (SendUserFile when they are on their phone).

## Step 5: Report

Three lines: what changed in the profile, which resumes changed and why, and anything still marked **[confirm]**. No restating the files.
