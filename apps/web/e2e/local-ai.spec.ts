import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import type { Quote } from "../src/lib/types";

test("local Qwen extracts five unknown formats through Inbox and preserves correction evidence", async ({
  page,
}) => {
  test.skip(
    process.env.E2E_LOCAL_AI !== "true",
    "Opt-in real Ollama test; requires evaluation lab seed",
  );
  test.setTimeout(900000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/login");
  await page.getByLabel("Email address").fill("buyer@evaluation.example");
  await page.getByLabel("Password", { exact: true }).fill("Demo2026!accord");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Good decisions start here." }),
  ).toBeVisible();
  await page.goto("/settings");
  await expect(page.getByText("LOCAL AI", { exact: true })).toBeVisible();
  await expect(page.getByText("qwen2.5vl:7b", { exact: true })).toBeVisible();
  await expect(
    page.getByText("Ollama · Available", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/local-settings.png",
    fullPage: true,
  });
  const root = path.resolve(__dirname, "../../../benchmark-data");
  const files = [
    "synthetic-001-standard_table.pdf",
    "synthetic-002-supplier_sku_and_mpn.scan.pdf",
    "synthetic-003-comma_thousands.png",
    "synthetic-005-lead_time_range-v21.xlsx",
    "synthetic-006-weeks.csv",
  ];
  const results: unknown[] = [];
  for (const [index, filename] of files.entries()) {
    await page.goto("/inbox");
    const response = page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/quotes/upload") &&
        r.request().method() === "POST",
    );
    await page
      .getByLabel("Upload quotations")
      .setInputFiles(
        path.join(
          root,
          filename.includes("-v21") ? "ui-documents" : "documents",
          filename,
        ),
      );
    const upload = await response;
    expect([202, 409]).toContain(upload.status());
    const body = await upload.json();
    const documentId =
      upload.status() === 202 ? body.id : body.detail.document_id;
    let document: {
      stage: string;
      status: string;
      quote_id?: string;
      error?: string;
    } = { stage: "", status: "" };
    await expect
      .poll(
        async () => {
          document = await (
            await page.request.get(`/api/documents/${documentId}`)
          ).json();
          return document.status;
        },
        { timeout: 180000, intervals: [2000] },
      )
      .not.toMatch(/^(New|Processing)$/);
    expect(document.stage, JSON.stringify(document)).toBe("Complete");
    expect(document.quote_id).toBeTruthy();
    const row = page.getByRole("row").filter({ hasText: filename });
    await expect(row.getByText("Complete", { exact: true })).toBeVisible();
    await row.getByRole("link", { name: "Review" }).click();
    let quote = (await (
      await page.request.get(`/api/quotes/${document.quote_id}`)
    ).json()) as Quote;
    expect(quote.extraction_provider).toBe("local");
    expect(quote.extraction_diagnostics?.fallback).toBe(false);
    expect(quote.extraction_diagnostics?.model).toBe("qwen2.5vl:7b");
    const truthName = filename
      .replace("-v21", "")
      .replace(/\.(scan\.pdf|pdf|png|xlsx|csv)$/, ".json");
    const truth = JSON.parse(
      fs.readFileSync(path.join(root, "ground-truth", truthName), "utf8"),
    );
    const observedSupplier = quote.supplier_name;
    const missingCosts = ["shipping_cost", "tax"].filter(
      (field) => quote[field as "shipping_cost" | "tax"] === null,
    );
    // A failed prior test may have saved the intentional price edit before restoration.
    if (
      index === 0 &&
      upload.status() === 409 &&
      Number(quote.line_items[0].unit_price) ===
        Number(truth.line_items[0].unit_price) + 0.1
    ) {
      await page
        .getByLabel(`Unit price · ${quote.line_items[0].supplier_sku}`, {
          exact: true,
        })
        .fill(String(truth.line_items[0].unit_price));
      const restored = page.waitForResponse(
        (r) =>
          r.url().endsWith(`/api/quotes/${quote.id}/review`) &&
          r.request().method() === "PUT",
      );
      await page
        .getByRole("button", { name: "Save corrections", exact: true })
        .click();
      expect((await restored).ok()).toBe(true);
      quote = await (await page.request.get(`/api/quotes/${quote.id}`)).json();
    }
    if (quote.supplier_name !== truth.supplier_name) {
      // Keep the observed model error in the artifact and verify a real buyer correction.
      expect(quote.extraction_diagnostics?.needs_review).toBe(true);
      await page
        .getByLabel("Supplier name on quote", { exact: true })
        .fill(truth.supplier_name);
      const correctedSupplier = page.waitForResponse(
        (r) =>
          r.url().endsWith(`/api/quotes/${quote.id}/review`) &&
          r.request().method() === "PUT",
      );
      await page
        .getByRole("button", { name: "Save corrections", exact: true })
        .click();
      expect((await correctedSupplier).ok()).toBe(true);
      const savedSupplier = await (
        await page.request.get(`/api/quotes/${quote.id}`)
      ).json();
      expect(savedSupplier.supplier_name).toBe(truth.supplier_name);
    }
    expect(quote.currency).toBe(truth.currency);
    expect(quote.line_items).toHaveLength(truth.line_items.length);
    for (const expected of truth.line_items) {
      const line = quote.line_items.find(
        (l) => l.supplier_sku === expected.supplier_sku,
      )!;
      expect(line).toBeTruthy();
      expect(Number(line.quantity)).toBe(Number(expected.quantity));
      expect(Number(line.unit_price)).toBe(Number(expected.unit_price));
    }
    const line = quote.line_items[0];
    expect(line.source_references.unit_price.evidence_type).not.toBe("missing");
    await page
      .getByRole("button", {
        name: `Source for Unit price · ${line.supplier_sku}`,
        exact: true,
      })
      .click();
    await expect(page.getByText(/SOURCE EVIDENCE · PAGE/)).toBeVisible();
    await page.screenshot({
      path: `test-results/local-review-${index + 1}.png`,
      fullPage: true,
    });
    if (index === 0) {
      const corrected = Number(truth.line_items[0].unit_price) + 0.1;
      // Unknown costs must remain null until the buyer enters the amounts printed in the source.
      await page
        .getByLabel("Shipping cost", { exact: true })
        .fill(String(truth.shipping_cost));
      await page.getByLabel("Tax", { exact: true }).fill(String(truth.tax));
      await page
        .getByLabel(`Unit price · ${line.supplier_sku}`, { exact: true })
        .fill(corrected.toFixed(2));
      const correctionResponse = page.waitForResponse(
        (r) =>
          r.url().endsWith(`/api/quotes/${quote.id}/review`) &&
          r.request().method() === "PUT",
      );
      await page
        .getByRole("button", { name: "Save corrections", exact: true })
        .click();
      const correction = await correctionResponse;
      expect(correction.ok()).toBe(true);
      await expect(
        page.getByText(
          "Review saved. Totals, alerts, and recommendations recalculated.",
        ),
      ).toBeVisible();
      const saved = (await correction.json()) as Quote;
      expect(Number(saved.total)).toBeCloseTo(
        corrected * Number(line.quantity) +
          Number(truth.shipping_cost) +
          Number(truth.tax),
        2,
      );
      expect(saved.line_items[0].source_references).toEqual(
        line.source_references,
      );
      await page.screenshot({
        path: "test-results/local-corrected.png",
        fullPage: true,
      });
      await page
        .getByLabel(`Unit price · ${line.supplier_sku}`, { exact: true })
        .fill(Number(truth.line_items[0].unit_price).toFixed(2));
      await page
        .getByRole("button", { name: "Save corrections", exact: true })
        .click();
      await expect
        .poll(async () =>
          Number(
            (await (await page.request.get(`/api/quotes/${quote.id}`)).json())
              .line_items[0].unit_price,
          ),
        )
        .toBe(Number(truth.line_items[0].unit_price));
    }
    results.push({
      filename,
      documentId,
      quoteId: quote.id,
      extraction: quote.extraction_diagnostics,
      uploadStatus: upload.status(),
      observedSupplier,
      expectedSupplier: truth.supplier_name,
      missingCosts,
    });
  }
  expect(errors).toEqual([]);
  fs.writeFileSync(
    "test-results/local-ai-evidence.json",
    JSON.stringify(results, null, 2),
  );
});
