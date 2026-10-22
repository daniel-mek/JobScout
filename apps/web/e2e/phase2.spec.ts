import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("manual job import persists with provenance, versions and source health", async ({
  page,
}) => {
  await page.goto("/signup");
  await page.getByLabel("Email address").fill(`jobs-${Date.now()}@example.com`);
  await page
    .getByLabel("Password", { exact: true })
    .fill("A test-only passphrase 42");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/onboarding/);
  await page.goto("/jobs");
  await page
    .getByLabel("Job URL", { exact: true })
    .fill("https://careers.example.com/software-101");
  await page.getByRole("button", { name: "Import supported link" }).click();
  await expect(page.getByText(/No reviewed API or feed/)).toBeVisible();
  await page
    .getByLabel("Job title", { exact: true })
    .fill("Junior Software Engineer");
  await page.getByLabel("Company", { exact: true }).fill("Example Systems");
  await page.getByLabel("Location (optional)").fill("New York, NY");
  await page
    .getByLabel("Description (optional)")
    .fill(
      "Build Python services with PostgreSQL. Two years of experience preferred.",
    );
  await page.getByRole("button", { name: "Save manual job" }).click();
  await expect(page).toHaveURL(/jobs\/[a-f0-9-]+/);
  await expect(
    page.getByRole("heading", { name: "Junior Software Engineer" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Where this came from" }),
  ).toBeVisible();
  await expect(page.getByText("Manual import", { exact: true })).toBeVisible();
  await page.reload();
  await page.getByText(/Version 1 ·/).click();
  await expect(
    page
      .getByText(
        "Build Python services with PostgreSQL. Two years of experience preferred.",
      )
      .last(),
  ).toBeVisible();
  expect(
    (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze())
      .violations,
  ).toEqual([]);
  await page.getByRole("link", { name: "← All jobs & sources" }).click();
  await page
    .getByLabel("Career page URL (optional)")
    .fill("https://jobs.lever.co/example");
  await page.getByRole("button", { name: "Detect board" }).click();
  await expect(
    page.getByLabel("Board identifier / search keyword"),
  ).toHaveValue("example");
  await page.getByLabel("Company / search name").fill("Example Systems");
  await page.getByRole("button", { name: "Add source", exact: true }).click();
  await expect(
    page.getByText(/lever · example · policy: NEEDS_REVIEW/),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Sync source", exact: true })
    .first()
    .click();
  await expect(
    page.getByText("0 listings · source not approved", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Save search", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Run saved search" }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("link", { name: /Junior Software Engineer/ }),
  ).toBeVisible();
  expect(
    (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze())
      .violations,
  ).toEqual([]);
});
