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
async function signup(page: import("@playwright/test").Page) {
  await page.goto("/signup");
  await page
    .getByLabel("Email address")
    .fill(`browser-${Date.now()}@example.com`);
  await page
    .getByLabel("Password", { exact: true })
    .fill("A test-only passphrase 42");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/onboarding/);
}
test("onboarding persists, profile edits and settings survive, upload keeps history", async ({
  page,
}) => {
  await signup(page);
  await expect(
    page.getByRole("heading", { name: "Bring your resume." }),
  ).toBeVisible();
  await page.getByLabel("Choose your resume").setInputFiles({
    name: "example-resume.docx",
    mimeType:
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    buffer: resume,
  });
  await page.getByRole("button", { name: "Save & continue" }).click();
  await expect(
    page.getByRole("heading", { name: "Make it yours." }),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Full name", { exact: true })).toHaveValue(
    "Taylor Example",
  );
  await page.getByLabel("General location").fill("Jersey City, NJ");
  await page
    .getByLabel("Graduation date", { exact: true })
    .first()
    .fill("May 2026");
  await page.getByRole("button", { name: "Add skill", exact: true }).click();
  await page
    .getByLabel("Skill", { exact: true })
    .last()
    .fill("Troubleshooting");
  await page.getByLabel("I reviewed this profile").check();
  await page
    .getByRole("button", { name: "Confirm profile & continue" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Choose your direction." }),
  ).toBeVisible();
  await page.getByLabel("Software Engineering", { exact: true }).check();
  await page.getByLabel("IT / Systems", { exact: true }).check();
  await page.getByRole("button", { name: "Save & continue" }).click();
  await expect(
    page.getByRole("heading", { name: "Set your preferences." }),
  ).toBeVisible();
  await page.getByLabel("Preferred locations").fill("Jersey City, New York");
  await page.getByLabel("Remote", { exact: true }).check();
  await page.getByRole("button", { name: "Save & continue" }).click();
  await expect(
    page.getByRole("heading", { name: "Draw your boundaries." }),
  ).toBeVisible();
  await page.getByLabel("Include contract jobs?").selectOption("no");
  await page.getByLabel("Allowed countries").fill("US");
  await page.getByRole("button", { name: "Finish setup" }).click();
  await expect(page).toHaveURL(/dashboard/);
  await expect(
    page.getByRole("heading", { name: "4 confirmed skills" }),
  ).toBeVisible();
  expect(
    (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze())
      .violations,
  ).toEqual([]);
  await page.screenshot({ path: "/tmp/applyos-dashboard.png", fullPage: true });
  await page.reload();
  await expect(page).toHaveURL(/dashboard/);
  await page.goto("/settings");
  await expect(
    page.getByText("example-resume.docx", { exact: true }),
  ).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download", exact: true }).click();
  expect((await download).suggestedFilename()).toBe("resume-v1.docx");
  await page.goto("/onboarding?edit=requirements");
  await expect(page.getByLabel("Include contract jobs?")).toHaveValue("no");
  await page.goto("/onboarding?edit=upload");
  await page.getByLabel("Choose your resume").setInputFiles({
    name: "updated.docx",
    mimeType:
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    buffer: resume,
  });
  await page.getByRole("button", { name: "Save & continue" }).click();
  await expect(
    page.getByRole("heading", { name: "Make it yours." }),
  ).toBeVisible();
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/onboarding/);
  await page.goto("/settings");
  await expect(
    page.getByText("example-resume.docx", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("updated.docx", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/login/);
  await page.goto("/settings");
  await expect(page).toHaveURL(/login/);
});
test("invalid uploads show an error without advancing; mobile layout stays usable", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signup(page);
  await page.getByLabel("Choose your resume").setInputFiles({
    name: "not-real.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("not a PDF"),
  });
  await page.getByRole("button", { name: "Save & continue" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText(
    "Could not extract",
  );
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Bring your resume." }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({ path: "/tmp/applyos-mobile.png", fullPage: true });
});
test("protected routes and authorization reject an unrelated session", async ({
  page,
  context,
}) => {
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/login/);
  await signup(page);
  const csrf = (await context.cookies()).find(
    (c) => c.name === "applyos_csrf",
  )?.value;
  const response = await page.request.put("/backend/profile", {
    headers: { origin: "http://localhost:3000", "x-csrf-token": csrf || "" },
    data: {
      expected_revision: 0,
      resume_version_id: "someone-elses-id",
      profile: {},
      confirmed: true,
    },
  });
  expect(response.status()).toBe(404);
  const rejected = await page.request.put("/backend/preferences", {
    headers: { origin: "https://evil.example" },
    data: {},
  });
  expect(rejected.status()).toBe(403);
});
