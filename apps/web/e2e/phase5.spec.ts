import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { execFileSync } from "node:child_process";
import path from "node:path";

const root = path.resolve(__dirname, "../../..");
const resume = execFileSync(
  process.env.API_PYTHON || path.join(root, ".venv/bin/python"),
  [
    "-c",
    `import io,sys
from docx import Document
b=io.BytesIO();d=Document()
for line in ['Taylor Example','Education','Example University','Skills','Python, PostgreSQL, Linux','Projects','Built a Python service with PostgreSQL.']: d.add_paragraph(line)
d.save(b);sys.stdout.buffer.write(b.getvalue())`,
  ],
);

test("application preparation, submission, snapshots, deadlines, Kanban and CSV persist", async ({
  page,
}) => {
  test.setTimeout(90000);
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/signup");
  await page
    .getByLabel("Email address")
    .fill(`applications-${Date.now()}@example.com`);
  await page
    .getByLabel("Password", { exact: true })
    .fill("A test-only passphrase 42");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/onboarding/);
  await page.getByLabel("Choose your resume").setInputFiles({
    name: "example.docx",
    mimeType:
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    buffer: resume,
  });
  await page.getByRole("button", { name: "Save & continue" }).click();
  await page.getByLabel("I reviewed this profile").check();
  await page
    .getByRole("button", { name: "Confirm profile & continue" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Choose your direction." }),
  ).toBeVisible();
  await page.goto("/jobs");
  await page
    .getByLabel("Job URL", { exact: true })
    .fill("https://example.com/phase5");
  await page
    .getByLabel("Job title", { exact: true })
    .fill("Junior Platform Engineer");
  await page
    .getByLabel("Company", { exact: true })
    .fill("Example Applications");
  await page
    .getByLabel("Description (optional)")
    .fill("Original Python job description.");
  await page.getByRole("button", { name: "Save manual job" }).click();
  await expect(page).toHaveURL(/jobs\/[a-f0-9-]+/);
  const jobUrl = page.url();
  await page
    .getByRole("button", { name: "Prepare Application", exact: true })
    .click();
  await expect(page).toHaveURL(/applications\/[a-f0-9-]+/);
  const applicationUrl = page.url();
  await expect(
    page.getByText("Original Python job description.", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("New status").selectOption("APPLIED");
  await page
    .getByLabel("Resume used", { exact: true })
    .selectOption({ index: 1 });
  await page.getByLabel("I submitted this application myself.").check();
  await page
    .getByLabel("Status note (optional)")
    .fill("Submitted through employer website");
  await page
    .getByRole("button", { name: "Mark as Applied", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText("Application saved.");
  await expect(
    page.getByRole("link", { name: "Download resume" }),
  ).toBeVisible();
  await page.getByLabel("What’s next?").fill("Review assessment instructions");
  await page.getByLabel("Next action date", { exact: true }).fill("2026-11-15");
  await page.getByRole("button", { name: "Save next action" }).click();
  await expect(page.getByRole("status")).toContainText("Application saved.");
  await page.getByLabel("Entry type").selectOption("NOTE");
  await page
    .getByLabel("Note or event details")
    .fill("Read original qualifications carefully");
  await page.getByRole("button", { name: "Add entry" }).click();
  await expect(
    page.getByText("Read original qualifications carefully", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("Entry type").selectOption("ASSESSMENT");
  await page
    .getByLabel("Note or event details")
    .fill("Finish online assessment");
  await page.getByLabel("Due date (required for deadlines)").fill("2026-11-10");
  await page.getByRole("button", { name: "Add entry" }).click();
  await expect(
    page.getByRole("button", { name: "Complete deadline" }),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("What’s next?")).toHaveValue(
    "Review assessment instructions",
  );
  await expect(
    page.getByText("Submitted through employer website", { exact: true }),
  ).toBeVisible();
  expect(
    (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze())
      .violations,
  ).toEqual([]);
  await page.getByRole("button", { name: "Complete deadline" }).click();
  await expect(
    page.getByRole("button", { name: "Reopen deadline" }),
  ).toBeVisible();
  await page.goto("/applications");
  await page
    .getByLabel("Move Junior Platform Engineer", { exact: true })
    .selectOption("INTERVIEW");
  await expect(
    page.getByLabel("Move Junior Platform Engineer", { exact: true }),
  ).toHaveValue("INTERVIEW");
  await expect(page.getByRole("status")).toContainText("moved to interview.");
  await expect(
    page.getByLabel("Move Junior Platform Engineer", { exact: true }),
  ).toBeEnabled();
  // Drag from the card padding, away from nested links and the native select.
  const card = page.locator(".pipeline-card");
  await card.dragTo(page.getByRole("region", { name: "offer", exact: true }), {
    sourcePosition: { x: 12, y: 12 },
  });
  await expect(
    page.getByLabel("Move Junior Platform Engineer", { exact: true }),
  ).toHaveValue("OFFER");
  await page.getByRole("button", { name: "List view", exact: true }).click();
  await expect(page.getByRole("table")).toContainText(
    "Review assessment instructions",
  );
  expect(
    (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze())
      .violations,
  ).toEqual([]);
  const csv = await page.request.get("/backend/applications/export.csv");
  expect(csv.ok()).toBeTruthy();
  expect(await csv.text()).toContain("Junior Platform Engineer");
  expect(await csv.text()).toContain("Read original qualifications carefully");
  await page.goto(jobUrl);
  await page
    .getByRole("button", { name: "Prepare Application", exact: true })
    .click();
  await expect(page).toHaveURL(applicationUrl);
  await expect(page.getByLabel("New status")).toHaveValue("OFFER");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  expect(errors).toEqual([]);
});
