"use client";
import Link from "next/link";
import { useState } from "react";
import {
  ArrowLeft,
  ArrowUpRight,
  CheckCircle2,
  FileText,
  Save,
  ShieldCheck,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api, currency, useResource } from "@/lib/api";
import type { Quote, Line, ListData, Evidence } from "@/lib/types";
import { PageHeader, Status, ErrorState, Loading, Notice } from "./shared";
import { useUser } from "./shell";
import { NewItem } from "./new-item";

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
] as const;
const lineFields = [
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
] as const;
const fieldLabels: Record<string, string> = {
  supplier_name: "Supplier name on quote",
  supplier_email: "Supplier email",
  quote_number: "Quote number",
  rfq_number: "RFQ number on quote",
  quote_date: "Quote date",
  expiration_date: "Expiration date",
  currency: "Currency",
  payment_terms: "Payment terms",
  shipping_terms: "Shipping terms",
  shipping_cost: "Shipping cost",
  tax: "Tax",
  stated_subtotal: "Stated subtotal",
  stated_total: "Stated total",
  notes: "Notes",
  confidence: "Extraction confidence",
  supplier_sku: "Supplier SKU",
  manufacturer_part_number: "Manufacturer part number",
  description: "Description",
  quantity: "Quantity",
  uom: "UOM",
  unit_price: "Unit price",
  moq: "Minimum order quantity",
  lead_time_days: "Lead time (days)",
  lead_time_min: "Minimum lead time",
  delivery_date: "Delivery date",
  stated_line_total: "Stated line total",
};
export function ReviewPage({ id }: { id: string }) {
  const resource = useResource<Quote>(`/quotes/${id}`);
  const [notice, setNotice] = useState("");
  if (resource.error)
    return <ErrorState error={resource.error} retry={resource.reload} />;
  if (!resource.data) return <Loading />;
  return (
    <>
      {notice && <Notice text={notice} onClose={() => setNotice("")} />}
      <ReviewEditor
        key={`${id}-${resource.data.version}`}
        initial={resource.data}
        onSaved={(q) => {
          resource.setData(q);
          setNotice(
            "Review saved. Totals, alerts, and recommendations recalculated.",
          );
        }}
      />
    </>
  );
}
function ReviewEditor({
  initial,
  onSaved,
}: {
  initial: Quote;
  onSaved: (q: Quote) => void;
}) {
  const [quote, setQuote] = useState(initial),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  const [evidence, setEvidence] = useState<Evidence | null>(null),
    [sourceTab, setSourceTab] = useState("original");
  const suppliers = useResource<ListData>("/suppliers?limit=250"),
    items = useResource<ListData>("/items?limit=250"),
    rfqs = useResource<ListData>("/rfqs?limit=250");
  const canEdit = useUser()?.role !== "Viewer";
  function updateLine(index: number, key: keyof Line, value: unknown) {
    setQuote({
      ...quote,
      line_items: quote.line_items.map((l, i) =>
        i === index ? { ...l, [key]: value } : l,
      ),
    });
  }
  async function save(confirm: boolean) {
    setBusy(true);
    setError("");
    const payload = {
      ...Object.fromEntries(metadata.map((k) => [k, quote[k]])),
      version: quote.version,
      supplier_id: quote.supplier_id,
      rfq_id: quote.rfq_id,
      source_references: quote.source_references,
      confirm_review: confirm,
      line_items: quote.line_items.map((l) => ({
        ...Object.fromEntries(lineFields.map((k) => [k, l[k]])),
        id: l.id,
        item_id: l.item_id,
        source_references: l.source_references,
        price_tiers: l.price_tiers,
      })),
    };
    try {
      const saved = await api<Quote>(`/quotes/${quote.id}/review`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      setNotice(
        "Review saved. Totals, alerts, and recommendations recalculated.",
      );
      onSaved(saved);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const previewable = /\.(pdf|png|jpe?g)$/i.test(quote.document.filename);
  return (
    <>
      <Link
        className="back-link"
        href={quote.rfq_id ? `/rfqs/${quote.rfq_id}` : "/inbox"}
      >
        <ArrowLeft size={14} />
        Back to {quote.rfq_number || "inbox"}
      </Link>
      <PageHeader
        eyebrow="DOCUMENT REVIEW"
        title={quote.supplier_name || "Supplier identity needs review"}
        description={`${quote.quote_number} · ${quote.document.filename}`}
      >
        <Status value={quote.review_status} />
        <Button
          variant="outline"
          disabled={busy || !canEdit}
          onClick={() => save(false)}
        >
          <Save size={15} />
          Save corrections
        </Button>
        <Button disabled={busy || !canEdit} onClick={() => save(true)}>
          <CheckCircle2 size={15} />
          Confirm review
        </Button>
      </PageHeader>
      {error && (
        <p className="error-box" role="alert">
          {error}
        </p>
      )}
      {notice && <Notice text={notice} onClose={() => setNotice("")} />}
      <div className="review-trust">
        <ShieldCheck size={16} />
        <span>
          Extraction: <strong>{quote.extraction_provider}</strong> · Select a
          source icon to inspect the original evidence. Calculated values update
          after saving.
        </span>
      </div>
      {quote.extraction_diagnostics?.confidence_band && (
        <div className="review-trust">
          <span>
            Local extraction:{" "}
            <strong>{quote.extraction_diagnostics.confidence_band}</strong> ·{" "}
            {quote.extraction_diagnostics.model}. Human approval required.
          </span>
        </div>
      )}
      {!!quote.extraction_diagnostics?.findings?.length && (
        <details className="review-trust">
          <summary>
            Extraction review findings (
            {quote.extraction_diagnostics.findings.length})
          </summary>
          <ul>
            {quote.extraction_diagnostics.findings.map((finding, index) => (
              <li key={`${finding.code}-${index}`}>
                {finding.field}: {finding.message}
              </li>
            ))}
          </ul>
        </details>
      )}
      <div className="review-layout">
        <section className="document-pane">
          <div className="pane-heading">
            <div>
              <FileText size={16} />
              <strong>Source document</strong>
            </div>
            <a
              href={`/api/documents/${quote.document_id}/file`}
              target="_blank"
              rel="noreferrer"
              aria-label="Open original document"
            >
              <ArrowUpRight size={16} />
            </a>
          </div>
          <div className="source-switch">
            <Button
              size="sm"
              variant={sourceTab === "original" ? "secondary" : "ghost"}
              onClick={() => setSourceTab("original")}
            >
              Original
            </Button>
            <Button
              size="sm"
              variant={sourceTab === "text" ? "secondary" : "ghost"}
              onClick={() => setSourceTab("text")}
            >
              Extracted text
            </Button>
          </div>
          {previewable && sourceTab === "original" ? (
            <iframe
              title="Original supplier quotation"
              src={`/api/documents/${quote.document_id}/file${evidence?.page ? `#page=${evidence.page}` : ""}`}
            />
          ) : (
            <pre className="document-text">
              {quote.document.raw_text ||
                "Raw text unavailable. Open the original document above."}
            </pre>
          )}
          {evidence && (
            <div className="evidence-box">
              <div className="eyebrow">
                SOURCE EVIDENCE · PAGE {evidence.page || "UNKNOWN"}
              </div>
              {evidence.evidence_type === "visual" ? (
                <p>
                  Visual page evidence. Verify this value against the original
                  image; no verbatim quotation is available.
                </p>
              ) : evidence.evidence_type === "missing" ? (
                <p>
                  Source evidence is missing. Verify this value in the original
                  document.
                </p>
              ) : (
                <blockquote>“{evidence.source_text}”</blockquote>
              )}
              <small>
                Original confidence:{" "}
                {(Number(evidence.confidence) * 100).toFixed(0)}%. Evidence is
                preserved when values are corrected.
              </small>
            </div>
          )}
        </section>
        <section className="extraction-pane">
          <div className="pane-heading">
            <strong>Structured quotation</strong>
            <span className="muted">All fields editable</span>
          </div>
          <div className="metadata-form">
            <div className="field">
              <label>
                Matched supplier
                <Select
                  value={quote.supplier_id || "unmatched"}
                  disabled={!canEdit}
                  onValueChange={(v) =>
                    setQuote({
                      ...quote,
                      supplier_id: v === "unmatched" ? null : v,
                    })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="unmatched">
                      Unmatched — select supplier
                    </SelectItem>
                    {suppliers.data?.items.map((s) => (
                      <SelectItem key={s.id} value={s.id}>
                        {String(s.name)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </label>
            </div>
            <div className="field">
              <label>
                Matched RFQ
                <Select
                  value={quote.rfq_id || "unmatched"}
                  disabled={!canEdit}
                  onValueChange={(v) =>
                    setQuote({ ...quote, rfq_id: v === "unmatched" ? null : v })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="unmatched">
                      Unmatched — select RFQ
                    </SelectItem>
                    {rfqs.data?.items.map((r) => (
                      <SelectItem key={r.id} value={r.id}>
                        {String(r.number)} · {String(r.title)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </label>
            </div>
            {metadata.map((key) => (
              <Editable
                key={key}
                label={fieldLabels[key]}
                value={quote[key]}
                disabled={!canEdit}
                evidence={quote.source_references[key]}
                showEvidence={setEvidence}
                onChange={(v) => setQuote({ ...quote, [key]: v })}
              />
            ))}
          </div>
          <div className="extracted-lines">
            {quote.line_items.map((line, index) => (
              <section className="extracted-line" key={line.id}>
                <div className="line-editor-heading">
                  <div>
                    <span className="line-number">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <strong>{line.description}</strong>
                  </div>
                  <span
                    className={
                      Number(line.confidence) < 0.8
                        ? "inline-warning"
                        : "confidence-good"
                    }
                  >
                    {(Number(line.confidence) * 100).toFixed(0)}% confidence
                  </span>
                </div>
                <label className="mapping-label">
                  Internal item mapping
                  <Select
                    value={line.item_id || "unmatched"}
                    disabled={!canEdit}
                    onValueChange={(v) =>
                      updateLine(index, "item_id", v === "unmatched" ? null : v)
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="unmatched">
                        Unmatched — needs confirmation
                      </SelectItem>
                      {items.data?.items.map((i) => (
                        <SelectItem key={i.id} value={i.id}>
                          {String(i.sku)} · {String(i.description)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </label>
                <small className="muted">
                  Match method: {line.match_method}. Confirmed mappings are
                  reused for future quotes.
                </small>
                {!line.item_id && line.candidates && (
                  <div className="suggestions">
                    Possible matches:{" "}
                    {line.candidates.map((c) => (
                      <Button
                        variant="outline"
                        size="sm"
                        key={c.id}
                        onClick={() => updateLine(index, "item_id", c.id)}
                      >
                        {c.sku} ({Math.round(c.confidence * 100)}%)
                      </Button>
                    ))}
                  </div>
                )}
                <div className="line-form">
                  {!line.item_id && canEdit && (
                    <NewItem
                      sku={line.supplier_sku || ""}
                      description={line.description || ""}
                      onCreated={(item) => {
                        items.reload();
                        updateLine(index, "item_id", item.id);
                      }}
                    />
                  )}
                  {lineFields.map((key) => (
                    <Editable
                      key={key}
                      label={`${fieldLabels[key]}${key === "unit_price" ? ` · ${line.supplier_sku}` : ""}`}
                      value={line[key]}
                      disabled={!canEdit}
                      evidence={line.source_references[key]}
                      showEvidence={setEvidence}
                      onChange={(v) =>
                        updateLine(
                          index,
                          key,
                          key === "lead_time_days" || key === "lead_time_min"
                            ? v === null
                              ? null
                              : Number(v)
                            : v,
                        )
                      }
                    />
                  ))}
                </div>
                {line.price_tiers.length > 0 && (
                  <div className="tier-editor">
                    <h3>Quantity price tiers</h3>
                    {line.price_tiers.map((tier, ti) => (
                      <div className="line-form" key={ti}>
                        {(["minimum", "maximum", "unit_price"] as const).map(
                          (key) => (
                            <label key={key}>
                              {key.replace("_", " ")}
                              <Input
                                disabled={!canEdit}
                                value={tier[key] ?? ""}
                                onChange={(e) =>
                                  updateLine(
                                    index,
                                    "price_tiers",
                                    line.price_tiers.map((t, j) =>
                                      j === ti
                                        ? {
                                            ...t,
                                            [key]: e.target.value || null,
                                          }
                                        : t,
                                    ),
                                  )
                                }
                              />
                            </label>
                          ),
                        )}
                      </div>
                    ))}
                    <small>
                      The selected unit price must match the applicable tier for
                      the quoted quantity.
                    </small>
                  </div>
                )}
                <div className="calculated-total">
                  <span>Calculated line total</span>
                  <strong>{currency(line.line_total, quote.currency)}</strong>
                </div>
              </section>
            ))}
          </div>
          <div className="review-totals">
            <div>
              <span>Calculated subtotal</span>
              <strong>{currency(quote.subtotal, quote.currency)}</strong>
            </div>
            <div>
              <span>Evaluated total</span>
              <strong>{currency(quote.total, quote.currency)}</strong>
            </div>
          </div>
        </section>
      </div>
    </>
  );
}
function Editable({
  label,
  value,
  onChange,
  evidence,
  showEvidence,
  disabled,
}: {
  label: string;
  value: unknown;
  onChange: (v: string | null) => void;
  evidence?: Evidence;
  showEvidence: (e: Evidence) => void;
  disabled: boolean;
}) {
  return (
    <div
      className={`field ${evidence && Number(evidence.confidence) < 0.8 ? "low-confidence" : ""}`}
    >
      <div className="field-label">
        <label>
          {label}
          <Input
            aria-label={label}
            disabled={disabled}
            value={value === null || value === undefined ? "" : String(value)}
            onChange={(e) =>
              onChange(e.target.value === "" ? null : e.target.value)
            }
            placeholder="Not provided"
          />
        </label>
        {evidence && (
          <button
            className="evidence-button"
            aria-label={`Source for ${label}`}
            onClick={() => showEvidence(evidence)}
            title={evidence.source_text}
          >
            <FileText size={13} />
          </button>
        )}
      </div>
    </div>
  );
}
