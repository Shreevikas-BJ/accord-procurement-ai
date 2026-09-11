import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import type { Quote } from "../src/lib/types";

test("evidence-gated local extraction, missing fields, unusual instructions and buyer provenance", async ({
  page,
}) => {
  test.skip(
    process.env.E2E_LOCAL_RELIABILITY !== "true",
    "Requires the isolated reliability lab and real Ollama",
  );
  test.setTimeout(900000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/login");
  await page.getByLabel("Email address").fill("buyer@reliability.example");
  await page.getByLabel("Password", { exact: true }).fill("Demo2026!accord");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Good decisions start here." }),
  ).toBeVisible();
  const root = path.resolve(__dirname, "../../../benchmark-data");
  const files = [
    "documents/synthetic-001-standard_table.pdf",
    "documents/synthetic-002-supplier_sku_and_mpn.scan.pdf",
    "documents/synthetic-003-comma_thousands.png",
    "documents/synthetic-005-lead_time_range.xlsx",
    "documents/synthetic-006-weeks.csv",
    "reliability/documents/reliability-013-missing_quantity.xlsx",
    "reliability/documents/reliability-006-injection.pdf",
  ];
  const evidence: unknown[] = [];
  for (const [index, filename] of files.entries()) {
    await page.goto("/inbox");
    const uploaded = page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/quotes/upload") &&
        r.request().method() === "POST",
    );
    await page
      .getByLabel("Upload quotations")
      .setInputFiles(path.join(root, filename));
    const upload = await uploaded;
    expect([202, 409]).toContain(upload.status());
    const body = await upload.json();
    const id = upload.status() === 202 ? body.id : body.detail.document_id;
    let document: {
      status: string;
      stage?: string;
      quote_id?: string;
      error?: string;
    } = { status: "New" };
    await expect
      .poll(
        async () => {
          document = await (
            await page.request.get(`/api/documents/${id}`)
          ).json();
          return document.status;
        },
        { timeout: 240000, intervals: [1500] },
      )
      .not.toMatch(/^(New|Processing)$/);
    expect(document.quote_id, JSON.stringify(document)).toBeTruthy();
    const quote = (await (
      await page.request.get(`/api/quotes/${document.quote_id}`)
    ).json()) as Quote;
    expect(quote.extraction_provider).toBe("local");
    expect(quote.extraction_diagnostics?.fallback).toBe(false);
    expect(quote.extraction_diagnostics?.model).toBe("qwen2.5vl:7b");
    // A fresh tenant prevents old Phase 2 quotes satisfying this acceptance check.
    expect(
      (quote.extraction_diagnostics as { pipeline_version?: string })
        ?.pipeline_version,
    ).toBe("local-2.5.2");
    await page.goto(`/quotes/${quote.id}`);
    await expect(
      page.getByRole("button", { name: "Save corrections", exact: true }),
    ).toBeVisible();
    const line = quote.line_items[0];
    if (index < 5) {
      expect(line.supplier_sku).toBeTruthy();
      expect(line.source_references.unit_price?.evidence_strength).toBe(
        "strong",
      );
      await page
        .getByRole("button", {
          name: `Source for Unit price · ${line.supplier_sku}`,
          exact: true,
        })
        .click();
      await expect(
        page.getByText("Supported by source.", { exact: false }),
      ).toBeVisible();
    } else if (index === 5) {
      expect(line.quantity).toBeNull();
      expect(Number(line.moq)).toBe(500);
      expect(quote.total).toBeNull();
      expect(quote.extraction_diagnostics?.needs_review).toBe(true);
    } else {
      expect(quote.extraction_diagnostics?.needs_review).toBe(true);
      expect(
        quote.extraction_diagnostics?.findings?.some(
          (f) => f.code === "DOCUMENT_INSTRUCTION_TEXT_DETECTED",
        ),
      ).toBe(true);
      expect(line.moq === null || Number(line.moq) === 500).toBe(true);
      expect(line.unit_price === null || Number(line.unit_price) === 4.72).toBe(
        true,
      );
    }
    if (index === 0) {
      await page
        .getByLabel(`Unit price · ${line.supplier_sku}`, { exact: true })
        .fill("1.35");
      await page.getByLabel("Shipping cost", { exact: true }).fill("12");
      await page.getByLabel("Tax", { exact: true }).fill("0");
      const saving = page.waitForResponse(
        (r) =>
          r.url().endsWith(`/api/quotes/${quote.id}/review`) &&
          r.request().method() === "PUT",
      );
      await page
        .getByRole("button", { name: "Save corrections", exact: true })
        .click();
      const response = await saving;
      expect(response.ok()).toBe(true);
      const saved = (await response.json()) as Quote;
      expect(Number(saved.total)).toBe(39);
      expect(saved.line_items[0].source_references).toEqual(
        line.source_references,
      );
      await page.screenshot({
        path: "test-results/phase25-correction.png",
        fullPage: true,
      });
      await page
        .getByLabel(`Unit price · ${line.supplier_sku}`, { exact: true })
        .fill("1.25");
      const restoring = page.waitForResponse(
        (r) =>
          r.url().endsWith(`/api/quotes/${quote.id}/review`) &&
          r.request().method() === "PUT",
      );
      await page
        .getByRole("button", { name: "Save corrections", exact: true })
        .click();
      expect((await restoring).ok()).toBe(true);
    }
    if (index >= 5) {
      await page
        .getByText(/critical fields need inspection|Extraction review findings/)
        .click();
      await page.screenshot({
        path: `test-results/phase25-safety-${index}.png`,
        fullPage: true,
      });
    }
    evidence.push({
      filename,
      upload_status: upload.status(),
      document_id: id,
      quote_id: quote.id,
      diagnostics: quote.extraction_diagnostics,
      original_quote: quote,
    });
  }
  await page.goto("/settings");
  await expect(page.getByText("LOCAL AI", { exact: true })).toBeVisible();
  await expect(
    page.getByText("Ollama · Available", { exact: true }),
  ).toBeVisible();
  expect(errors).toEqual([]);
  fs.mkdirSync("test-results", { recursive: true });
  fs.writeFileSync(
    "test-results/phase25-ui.json",
    JSON.stringify(evidence, null, 2),
  );
});
