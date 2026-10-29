import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("discovery saves notes and deadlines, filters, feedback undo and notification preferences persist", async ({
  page,
}) => {
  await page.goto("/signup");
  await page
    .getByLabel("Email address")
    .fill(`discovery-${Date.now()}@example.com`);
  await page
    .getByLabel("Password", { exact: true })
    .fill("A test-only passphrase 42");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/onboarding/);
  await page.goto("/discover");
  await expect(
    page.getByRole("heading", { name: "Let’s build your opportunity list" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Add your first job" }),
  ).toHaveAttribute("href", "/jobs#add-job");
  await expect(
    page.getByRole("heading", { name: "No listings match this view" }),
  ).toHaveCount(0);
  await page.goto("/jobs");
  await page
    .getByLabel("Job URL", { exact: true })
    .fill("https://example.com/discovery");
  await page
    .getByLabel("Job title", { exact: true })
    .fill("Junior Python Engineer");
  await page.getByLabel("Company", { exact: true }).fill("Example Discovery");
  await page.getByRole("button", { name: "Save manual job" }).click();
  await expect(page).toHaveURL(/jobs\/[a-f0-9-]+/);
  await page.goto("/discover");
  await expect(
    page.getByRole("heading", { name: "Junior Python Engineer" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Save job", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Unsave", exact: true }),
  ).toBeVisible();
  await page.goto("/saved-jobs");
  await expect(
    page.getByRole("heading", { name: "Saved notes & deadline" }),
  ).toBeVisible();
  await page
    .getByLabel("Notes", { exact: true })
    .fill("Check the original qualifications");
  await page.getByLabel("Optional deadline").fill("2026-11-12");
  await page.getByRole("button", { name: "Save notes" }).click();
  await expect(page.getByRole("status")).toContainText("Job preferences saved");
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Saved notes & deadline" }),
  ).toBeVisible();
  await expect(page.getByLabel("Notes", { exact: true })).toHaveValue(
    "Check the original qualifications",
  );
  await expect(page.getByLabel("Optional deadline")).toHaveValue("2026-11-12");
  await page.getByText("Dismiss job", { exact: true }).click();
  await page
    .getByRole("button", { name: "Not interested", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Undo feedback" }),
  ).toBeVisible();
  await page.goto("/discover");
  await expect(page.getByText(/No listings match/)).toBeVisible();
  await page.goto("/saved-jobs");
  await page.getByRole("button", { name: "Undo feedback" }).click();
  await expect(page.getByRole("button", { name: "Undo feedback" })).toHaveCount(
    0,
  );
  await page.goto("/discover");
  await expect(
    page.getByLabel("Minimum match", { exact: true }),
  ).not.toBeVisible();
  await page.getByText("More filters", { exact: false }).click();
  await expect(page.getByLabel("Minimum match", { exact: true })).toBeVisible();
  await page.getByText("More filters", { exact: false }).click();
  await page.getByLabel("Title", { exact: true }).fill("Missing title");
  await page.getByRole("button", { name: "Apply filters" }).click();
  await expect(page).toHaveURL(/title=Missing/);
  await expect(page.getByText(/No listings match/)).toBeVisible();
  await page.getByRole("link", { name: "Reset filters" }).click();
  await expect(
    page.getByRole("heading", { name: "Junior Python Engineer" }),
  ).toBeVisible();
  expect(
    (await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze())
      .violations,
  ).toEqual([]);
  await page.goto("/notifications");
  await page.goto("/discover");
  await page
    .getByLabel("Search name", { exact: true })
    .fill("My discovery filters");
  await page.getByRole("button", { name: "Save current filters" }).click();
  await expect(
    page.getByRole("link", { name: "My discovery filters" }),
  ).toBeVisible();
  await page.goto("/notifications");
  await page.getByText("Notification preferences", { exact: true }).click();
  await page.getByLabel("FRESH OPPORTUNITY", { exact: true }).uncheck();
  await page
    .getByRole("button", { name: "Save notification preferences" })
    .click();
  await expect(page.getByRole("status")).toContainText(
    "Notification preferences saved",
  );
  await page.reload();
  await page.getByText("Notification preferences", { exact: true }).click();
  await expect(
    page.getByLabel("FRESH OPPORTUNITY", { exact: true }),
  ).not.toBeChecked();
  await page.goto("/brief");
  await expect(
    page.getByRole("heading", { name: "Daily job brief" }),
  ).toBeVisible();
});
