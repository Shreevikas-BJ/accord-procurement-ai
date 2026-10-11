import { expect, test } from "@playwright/test";
import path from "node:path";

test("supplier email becomes an evidence-backed RFQ quote", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  test.skip(
    process.env.E2E_EMAIL !== "true",
    "Enable when the API, Redis, and RQ worker are running.",
  );
  await page.goto("/login");
  await page.waitForLoadState("networkidle");
  const loginResponsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/auth/login") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  expect((await loginResponsePromise).status()).toBe(200);
  await page.goto("/inbox");
  const responsePromise = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/emails/upload") &&
      response.request().method() === "POST",
  );
  await page
    .getByLabel("Import EML email")
    .setInputFiles(
      path.resolve("../../demo-data/emails/Atlas_RFQ1003_Revised.eml"),
    );
  const response = await responsePromise;
  expect(response.status()).toBe(202);
  const emailId = (await response.json()).id as string;
  await page.goto(`/emails/${emailId}`);
  await expect(
    page.getByRole("heading", {
      name: "RE: RFQ-1003 Revised Quote #ATL-EMAIL-28",
    }),
  ).toBeVisible();
  await expect(page.locator(".identity-card dd").first()).toHaveText(
    "Atlas Industrial Supply",
    { timeout: 60000 },
  );
  await expect(page.getByText(/RFQ-1003 · Industrial Electrical/)).toBeVisible();
  await expect(page.getByText("Atlas_RFQ1003_Revised.csv")).toBeVisible();
  const quoteLink = page.getByRole("link", { name: "Review structured quote" });
  await expect(quoteLink).toBeVisible();

  const detail = await page.request.get(`/api/emails/${emailId}`);
  expect(detail.ok()).toBe(true);
  const email = await detail.json();
  const confirmation = await page.request.post(
    `/api/emails/${emailId}/fields/confirm`,
    {
      data: { field: "line_items.0.unit_price", value: "4.48" },
      headers: { "X-Procurement-Client": "workspace" },
    },
  );
  expect(confirmation.ok()).toBe(true);
  const comparison = await page.request.get(`/api/rfqs/${email.rfq_id}/comparison`);
  const payload = await comparison.json();
  expect(payload.quotes.some((quote: { id: string }) => quote.id === email.quote_id)).toBe(true);
  const audit = await page.request.get("/api/audit-events?search=EMAIL_FIELD_CONFIRMED");
  expect((await audit.json()).total).toBeGreaterThan(0);
  await page.screenshot({ path: "test-results/email-intake.png", fullPage: true });
  expect(errors).toEqual([]);
});
