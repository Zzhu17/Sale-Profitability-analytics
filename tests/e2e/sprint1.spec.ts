import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

import { expect, test } from "@playwright/test";

const fixture = resolve("tests/fixtures/synthetic/invoices.csv");

test("upload, profile, propose, and approve a synthetic mapping", async ({ page }) => {
  const source = await readFile(fixture, "utf8");
  const uniqueRow = `INV-E2E-${Date.now()},CUST-SYN-001,2025-04-01,Paid,25.00`;

  await page.goto("/");
  await page.getByLabel("Source file").setInputFiles({
    name: "invoices.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(`${source.trimEnd()}\n${uniqueRow}\n`),
  });
  await page.getByRole("button", { name: "Upload" }).click();

  await expect(page.getByTestId("job-status")).toHaveText("awaiting_mapping");
  await expect(page.getByRole("heading", { name: "invoices 6 rows" })).toBeVisible();
  await expect(page.getByText(/invoice_id · 0 empty · 6 distinct/)).toBeVisible();

  await page.getByLabel("Source field").selectOption("invoice_id");
  await page.getByLabel("Canonical field").fill("invoice_id");
  await page.getByLabel("Author").fill("ci-analyst@example.com");
  await page.getByRole("button", { name: "Create draft" }).click();

  await expect(page.getByRole("status")).toHaveText("Draft mapping proposal created.");
  await expect(page.getByText(/invoices v1.*draft.*ci-analyst@example.com/)).toBeVisible();

  page.once("dialog", (dialog) => dialog.accept("ci-reviewer@example.com"));
  await page.getByRole("button", { name: "Approve" }).click();

  await expect(page.getByRole("status")).toHaveText("Mapping version 1 approved.");
  await expect(page.getByText(/invoices v1.*approved.*ci-analyst@example.com/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve" })).toHaveCount(0);
});
