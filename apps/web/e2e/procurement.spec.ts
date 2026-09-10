import { test, expect } from "@playwright/test";
import type { Comparison, Quote } from "../src/lib/types";
import path from "node:path";
test("buyer reviews, corrects, compares, drafts, approves, and audits", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/login");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Good decisions start here." }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/01-dashboard.png",
    fullPage: true,
  });
  await page.getByRole("link", { name: "Open RFQ-1003", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Industrial Electrical Components" }),
  ).toBeVisible();
  const rfqId = page.url().split("/").pop()!;
  const initial = (await (
    await page.request.get(`/api/rfqs/${rfqId}/comparison`)
  ).json()) as Comparison;
  expect(initial.quotes.length).toBeGreaterThanOrEqual(4);
  expect(new Set(initial.quotes.map((quote) => quote.supplier_name))).toEqual(
    new Set([
      "Atlas Industrial Supply",
      "Meridian Components",
      "Nova Supply Group",
      "Vertex Industrial",
    ]),
  );
  const winner = initial.quotes.find(
    (q) => q.id === initial.recommended_quote_id,
  )!;
  expect(winner.supplier_name).toBe("Meridian Components");
  await page.screenshot({
    path: "test-results/02-comparison.png",
    fullPage: true,
  });
  await page
    .locator(
      `a[href="/quotes/${winner.id}"][aria-label="Review Meridian Components"]`,
    )
    .click();
  await expect(
    page.getByRole("heading", { name: "Meridian Components", exact: true }),
  ).toBeVisible();
  const detail = (await (
    await page.request.get(`/api/quotes/${winner.id}`)
  ).json()) as Quote;
  const relay = detail.line_items.find(
    (l) => l.manufacturer_part_number === "AX-100",
  )!;
  await page
    .getByRole("button", {
      name: `Source for Unit price · ${relay.supplier_sku}`,
      exact: true,
    })
    .click();
  await expect(
    page.getByText("SOURCE EVIDENCE · PAGE 1", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("textbox", {
      name: `Unit price · ${relay.supplier_sku}`,
      exact: true,
    })
    .fill("4.40");
  await page
    .getByRole("button", { name: "Save corrections", exact: true })
    .click();
  await expect
    .poll(async () => {
      const q = await (
        await page.request.get(`/api/quotes/${winner.id}`)
      ).json();
      return q.total;
    })
    .toBe("118580.00");
  await page
    .getByRole("button", { name: "Confirm review", exact: true })
    .click();
  await expect(page.getByText("Reviewed", { exact: true })).toBeVisible();
  await page.screenshot({
    path: "test-results/03-document-review.png",
    fullPage: true,
  });
  await page
    .getByRole("link", { name: "Back to RFQ-1003", exact: true })
    .click();
  await expect(
    page.getByRole("cell", {
      name: "$118,580.00 Shipping $500.00",
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Generate recommendation", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Approve recommendation", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "Draft negotiation email", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByRole("button", { name: "Save draft", exact: true }).click();
  await page
    .getByRole("button", { name: "Mark approved", exact: true })
    .click();
  await expect(
    page.getByRole("dialog").getByText("Approved", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Close", exact: true }).click();
  await page
    .getByRole("button", { name: "Approve recommendation", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Confirm approval", exact: true })
    .click();
  await expect(
    page.getByText("Recommendation approved. Audit event recorded."),
  ).toBeVisible();
  await page.getByRole("link", { name: "Audit Log", exact: true }).click();
  await page
    .getByRole("textbox", { name: "Search Audit log" })
    .fill("RECOMMENDATION_APPROVED");
  await expect(
    page.getByText("RECOMMENDATION APPROVED", { exact: true }).first(),
  ).toBeVisible();
  await page.screenshot({ path: "test-results/04-audit.png", fullPage: true });
  for (const [url, title, file] of [
    ["/inbox", "From quotation to clarity.", "inbox"],
    ["/rfqs", "Requests for quotation", "rfqs"],
    ["/suppliers", "Your supplier network", "suppliers"],
    ["/items", "Item master", "items"],
    ["/purchase-history", "Purchase history", "history"],
    ["/settings", "Make the criteria yours.", "settings"],
  ]) {
    await page.goto(url);
    await expect(
      page.getByRole("heading", { name: title, exact: true }),
    ).toBeVisible();
    await page.screenshot({
      path: `test-results/view-${file}.png`,
      fullPage: true,
    });
  }
  await page.goto("/suppliers");
  await page
    .getByRole("textbox", { name: "Search Your supplier network" })
    .fill("Meridian");
  await page
    .getByRole("link", { name: "Meridian Components", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Meridian Components", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/view-supplier-detail.png",
    fullPage: true,
  });
  await page.goto("/items");
  await page
    .getByRole("textbox", { name: "Search Item master" })
    .fill("AX-100");
  await page.getByRole("link", { name: "AX-100", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "AX-100", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/view-item-detail.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Good decisions start here." }),
  ).toBeVisible();
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    )
    .toBe(true);
  await page.screenshot({
    path: "test-results/view-mobile.png",
    fullPage: true,
  });
  expect(errors).toEqual([]);
  // Restore price after verification so the seeded demo remains reproducible.
  const latest = (await (
    await page.request.get(`/api/quotes/${winner.id}`)
  ).json()) as Quote;
  const metadata = [
    "supplier_name",
    "supplier_email",
    "quote_number",
    "rfq_number",
    "quote_date",
    "expiration_date",
    "currency",
    "payment_terms",
    "shipping_terms",
    "shipping_cost",
    "tax",
    "stated_subtotal",
    "stated_total",
    "notes",
    "confidence",
    "source_references",
    "version",
    "supplier_id",
    "rfq_id",
  ];
  const lineKeys = [
    "id",
    "item_id",
    "supplier_sku",
    "manufacturer_part_number",
    "description",
    "quantity",
    "uom",
    "unit_price",
    "moq",
    "lead_time_days",
    "lead_time_min",
    "delivery_date",
    "stated_line_total",
    "confidence",
    "source_references",
    "price_tiers",
  ];
  const body = {
    ...Object.fromEntries(
      metadata.map((k) => [
        k,
        (latest as unknown as Record<string, unknown>)[k],
      ]),
    ),
    confirm_review: true,
    line_items: latest.line_items.map((l) => ({
      ...Object.fromEntries(
        lineKeys.map((k) => [k, (l as unknown as Record<string, unknown>)[k]]),
      ),
      unit_price: l.id === relay.id ? "4.48" : l.unit_price,
    })),
  };
  expect(
    (
      await page.request.put(`/api/quotes/${winner.id}/review`, {
        data: body,
        headers: { "X-Procurement-Client": "workspace" },
      })
    ).ok(),
  ).toBe(true);
});

test("PDF, XLSX and CSV uploads finish in the real background queue", async ({
  page,
}) => {
  test.skip(
    process.env.E2E_UPLOADS !== "true",
    "Enable when Redis and RQ worker are running.",
  );
  await page.goto("/login");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Good decisions start here." }),
  ).toBeVisible();
  await page.goto("/inbox");
  for (const file of [
    "Upload_Atlas_RFQ1003.pdf",
    "Upload_Meridian_RFQ1003.xlsx",
    "Upload_Nova_RFQ1003.csv",
  ]) {
    const uploadResponse = page.waitForResponse(
      (response) =>
        response.url().endsWith("/api/quotes/upload") &&
        response.request().method() === "POST",
    );
    await page
      .getByLabel("Upload quotations", { exact: true })
      .setInputFiles(path.resolve("../../demo-data/quotes", file));
    const response = await uploadResponse;
    expect([202, 409]).toContain(response.status());
    if (response.status() === 409) {
      expect((await response.json()).detail.message).toContain(
        "already uploaded",
      );
    }
    // Existing uploads may be on later pages after repeated live regression runs.
    await page.getByRole("textbox", { name: "Search inbox" }).fill(file);
    const row = page.getByRole("row").filter({ hasText: file });
    await expect(row).toBeVisible();
    await expect(row.getByText("Complete", { exact: true })).toBeVisible({
      timeout: 60000,
    });
    await row.getByRole("link", { name: "Review", exact: true }).click();
    await expect(
      page.getByRole("button", { name: "Confirm review", exact: true }),
    ).toBeVisible();
    await page.goto("/inbox");
  }
});
