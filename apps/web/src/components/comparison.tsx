"use client";
import Link from "next/link";
import { useState } from "react";
import {
  ArrowLeft,
  ArrowUpRight,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Download,
  FileText,
  Mail,
  ShieldCheck,
  SlidersHorizontal,
  Star,
  TriangleAlert,
  Users,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, currency, dateLabel, useResource, human } from "@/lib/api";
import type {
  Comparison as ComparisonData,
  Draft,
  Recommendation,
} from "@/lib/types";
import { PageHeader, Status, Loading, ErrorState, Notice } from "./shared";
import { useUser } from "./shell";

export function Comparison({ id }: { id: string }) {
  const { data, error, reload } = useResource<ComparisonData>(
    `/rfqs/${id}/comparison`,
  );
  const rec = useResource<Recommendation>(`/rfqs/${id}/recommendation`);
  const [busy, setBusy] = useState(false),
    [actionError, setActionError] = useState(""),
    [notice, setNotice] = useState("");
  const [draft, setDraft] = useState<Draft | null>(null),
    [approveOpen, setApproveOpen] = useState(false),
    [note, setNote] = useState(
      "Reviewed quotation, item mappings, and evaluated costs.",
    );
  const [tab, setTab] = useState("comparison");
  const [draftKind, setDraftKind] = useState("Negotiation");
  const canEdit = useUser()?.role !== "Viewer";
  if (error) return <ErrorState error={error} retry={reload} />;
  if (!data) return <Loading />;
  const winner = data.quotes.find((q) => q.id === data.recommended_quote_id),
    rfq = data.rfq;
  async function action(fn: () => Promise<void>) {
    setBusy(true);
    setActionError("");
    try {
      await fn();
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function generate() {
    const r = await api<Recommendation>(`/rfqs/${id}/recommendation`, {
      method: "POST",
    });
    rec.setData(r);
    setNotice("Recommendation saved with its calculation snapshot.");
  }
  return (
    <>
      <Link className="back-link" href="/rfqs">
        <ArrowLeft size={14} />
        All RFQs
      </Link>
      <PageHeader
        eyebrow={`${rfq.number} / SUPPLIER COMPARISON`}
        title={rfq.title}
        description="Compare the full picture. Make the decision with confidence."
      >
        <Button variant="outline" asChild>
          <Link href="/inbox">
            <Download size={15} />
            Add quotation
          </Link>
        </Button>
        <Status value={rfq.status} />
      </PageHeader>
      <div className="rfq-meta">
        <span>
          <CalendarDays size={16} />
          <span>
            Required delivery{" "}
            <strong>{dateLabel(rfq.required_delivery)}</strong>
          </span>
        </span>
        <span>
          <Users size={16} />
          <span>
            Suppliers invited <strong>{rfq.supplier_count}</strong>
          </span>
        </span>
        <span>
          <FileText size={16} />
          <span>
            Quotes received <strong>{data.quotes.length}</strong>
          </span>
        </span>
        <span className="meta-right">
          {rfq.currency} · All costs calculated by Accord
        </span>
      </div>
      {actionError && (
        <div className="error-box" role="alert">
          {actionError}
        </div>
      )}
      {notice && <Notice text={notice} onClose={() => setNotice("")} />}
      <Tabs value={tab} onValueChange={setTab}>
        <div className="comparison-toolbar">
          <TabsList>
            <TabsTrigger value="comparison">Supplier comparison</TabsTrigger>
            <TabsTrigger value="analysis">
              Analysis & risks{" "}
              <span className="tab-count">
                {data.quotes.reduce((n, q) => n + q.alerts.length, 0)}
              </span>
            </TabsTrigger>
            <TabsTrigger value="decision">Decision record</TabsTrigger>
          </TabsList>
          <Button variant="ghost" size="sm" asChild>
            <Link href="/settings">
              <SlidersHorizontal size={14} />
              Scoring criteria
            </Link>
          </Button>
        </div>
        <TabsContent value="comparison">
          <Card className="comparison-card">
            <div className="comparison-caption">
              <strong>Quote comparison</strong>
              <span>
                <i className="legend-dot" />
                Best value <i className="legend-dot amber" />
                Requires attention
              </span>
            </div>
            <div className="table-scroll">
              <table className="comparison-table">
                <thead>
                  <tr>
                    <th className="requirement-col">
                      <span className="eyebrow">REQUESTED ITEMS</span>
                      <p>{data.requirements.length} items · Full scope</p>
                    </th>
                    {data.quotes.map((q) => (
                      <th
                        key={q.id}
                        className={q.id === winner?.id ? "recommended-col" : ""}
                      >
                        <div className="supplier-label">
                          {q.id === winner?.id ? (
                            <span className="recommended-label">
                              <Star size={12} />
                              BEST OVERALL
                            </span>
                          ) : q.fastest ? (
                            <span className="fastest-label">
                              <Clock3 size={12} />
                              FASTEST DELIVERY
                            </span>
                          ) : (
                            <span className="neutral-label">
                              SUPPLIER QUOTE
                            </span>
                          )}
                        </div>
                        <strong>{q.supplier_name}</strong>
                        <Link href={`/quotes/${q.id}`}>
                          Review source <ArrowUpRight size={12} />
                        </Link>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.requirements.map((r) => (
                    <tr key={r.id}>
                      <td>
                        <span className="sku">{r.sku}</span>
                        <strong>{r.description}</strong>
                        <small>
                          {Number(r.quantity).toLocaleString()} {r.uom} required
                        </small>
                      </td>
                      {data.quotes.map((q) => {
                        const l = q.lines.find((l) => l.item_id === r.item_id);
                        return (
                          <td
                            key={q.id}
                            className={
                              q.id === winner?.id ? "recommended-col" : ""
                            }
                          >
                            {l ? (
                              <>
                                <div
                                  className={`unit-price ${q.id === winner?.id ? "best-price" : ""}`}
                                >
                                  {currency(l.unit_price, q.currency)}
                                  <small>/ {l.uom}</small>
                                </div>
                                <p className="line-amount">
                                  {currency(l.line_total, q.currency)}{" "}
                                  <span>line total</span>
                                </p>
                                <div className="line-facts">
                                  <span>
                                    {l.lead_time_days === null
                                      ? "Lead time missing"
                                      : `${l.lead_time_days} days`}
                                  </span>
                                  <span>
                                    MOQ {Number(l.moq).toLocaleString()}
                                  </span>
                                </div>
                                {l.history?.change &&
                                  q.alerts.some(
                                    (a) =>
                                      a.code === "PRICE_INCREASE" &&
                                      a.message.startsWith(
                                        `${l.sku || l.supplier_sku}:`,
                                      ),
                                  ) && (
                                    <Link
                                      href={`/quotes/${q.id}`}
                                      className="inline-warning"
                                    >
                                      <TriangleAlert size={12} />+
                                      {(Number(l.history.change) * 100).toFixed(
                                        1,
                                      )}
                                      % vs history
                                    </Link>
                                  )}
                                {l.moq &&
                                  Number(l.moq) > Number(r.quantity) && (
                                    <span className="inline-warning">
                                      <TriangleAlert size={12} />
                                      MOQ exceeds requirement
                                    </span>
                                  )}
                              </>
                            ) : (
                              <span className="inline-warning">
                                Missing item
                              </span>
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                  <tr className="summary-row">
                    <td>
                      <strong>Evaluated total</strong>
                      <small>Includes shipping + tax</small>
                    </td>
                    {data.quotes.map((q) => (
                      <td
                        key={q.id}
                        className={q.id === winner?.id ? "recommended-col" : ""}
                      >
                        <strong>{currency(q.total, q.currency)}</strong>
                        <small>
                          Shipping {currency(q.shipping_cost, q.currency)}
                        </small>
                      </td>
                    ))}
                  </tr>
                  <tr className="score-row">
                    <td>
                      <strong>Supplier score</strong>
                      <small>Weighted score out of 100</small>
                    </td>
                    {data.quotes.map((q) => (
                      <td
                        key={q.id}
                        className={q.id === winner?.id ? "recommended-col" : ""}
                      >
                        <div className="score-value">
                          <strong>
                            {q.score ? Number(q.score).toFixed(1) : "—"}
                          </strong>
                          <span>/ 100</span>
                          {q.id === winner?.id && <CheckCircle2 size={17} />}
                        </div>
                        <div className="score-track">
                          <i style={{ width: `${q.score || 0}%` }} />
                        </div>
                        <small>
                          {q.eligible
                            ? "Meets critical requirements"
                            : "Resolve blocking findings"}
                        </small>
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
          </Card>
          <div className="supplier-cards">
            {data.quotes.map((q) => (
              <Card
                key={q.id}
                className={`supplier-summary ${q.id === winner?.id ? "winner" : ""}`}
              >
                <div className="supplier-summary-title">
                  <div className="supplier-monogram">
                    {(q.supplier_name || "?").slice(0, 1)}
                  </div>
                  <strong>{q.supplier_name}</strong>
                  <Link
                    href={`/quotes/${q.id}`}
                    aria-label={`Review ${q.supplier_name}`}
                  >
                    <ArrowUpRight size={16} />
                  </Link>
                </div>
                <div className="summary-cost">
                  {currency(q.total, q.currency)}
                  <span>{q.lead_time_days} day lead time</span>
                </div>
                {q.alerts.length ? (
                  <div className="summary-findings">
                    {q.alerts.slice(0, 2).map((a, i) => (
                      <p key={i}>
                        <TriangleAlert size={13} />
                        {a.message}
                      </p>
                    ))}
                  </div>
                ) : (
                  <p className="all-clear">
                    <CheckCircle2 size={14} />
                    Pricing and requirements aligned
                  </p>
                )}
                <Link href={`/quotes/${q.id}`} className="review-link">
                  {q.review_status === "Reviewed"
                    ? "View reviewed quote"
                    : "Review extracted quote"}
                  <ChevronRight size={14} />
                </Link>
              </Card>
            ))}
          </div>
        </TabsContent>
        <TabsContent value="analysis">
          <Card className="section-card">
            <div className="section-heading">
              <div>
                <h2>How suppliers are evaluated</h2>
                <p>
                  Deterministic factors, calculated {dateLabel(data.as_of)}.
                  Critical requirements act as eligibility gates.
                </p>
              </div>
            </div>
            <div className="analysis-grid">
              {data.quotes.map((q) => (
                <div key={q.id}>
                  <h3>{q.supplier_name}</h3>
                  {Object.entries(q.factors).map(([k, v]) => (
                    <div className="factor-row" key={k}>
                      <span>{human(k)}</span>
                      <strong>
                        {v} / {data.weights[k]}
                      </strong>
                    </div>
                  ))}
                  <p className="muted">
                    Reliability based on {q.historical_orders} completed
                    historical purchases. No history uses a neutral 50% factor.
                  </p>
                  <div className="analysis-findings">
                    {q.alerts.map((a, i) => (
                      <div key={i}>
                        <Status
                          value={
                            a.severity === "blocking"
                              ? "Needs Review"
                              : "Warning"
                          }
                        />
                        <strong>{human(a.code)}</strong>
                        <p>{a.message}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </TabsContent>
        <TabsContent value="decision">
          <Card className="section-card">
            <div className="section-heading">
              <div>
                <h2>Decision record</h2>
                <p>
                  Saved recommendations retain their original inputs and scoring
                  weights.
                </p>
              </div>
            </div>
            <div className="decision-body">
              {rec.data ? (
                <>
                  <Status value={rec.data.status} />
                  <p>{rec.data.explanation}</p>
                  <small>
                    Snapshot revision {rec.data.revision} · Current RFQ revision{" "}
                    {rfq.revision}
                  </small>
                </>
              ) : (
                <p>
                  No recommendation has been saved yet. Generate one after
                  comparing suppliers.
                </p>
              )}
              <p className="muted">
                Approval records an internal procurement decision. It does not
                award business, create a purchase order, or send an email.
              </p>
              <Link href="/audit-events" className="section-link">
                Open audit trail <ArrowUpRight size={14} />
              </Link>
            </div>
          </Card>
        </TabsContent>
      </Tabs>
      <section className="recommendation-panel">
        <div className="recommendation-icon">
          <ShieldCheck size={25} />
        </div>
        <div className="recommendation-main">
          <div className="eyebrow">RECOMMENDED SUPPLIER</div>
          <h2>
            {winner?.supplier_name || "Review required before recommendation"}
          </h2>
          <p>{data.explanation}</p>
          {winner && (
            <div className="recommendation-checks">
              <span>
                <Check size={14} />
                Complete item coverage
              </span>
              <span>
                <Check size={14} />
                Meets delivery target
              </span>
              <span>
                <Check size={14} />
                No MOQ conflicts
              </span>
            </div>
          )}
          <div className="recommendation-actions">
            <Select value={draftKind} onValueChange={setDraftKind}>
              <SelectTrigger
                className="draft-kind"
                aria-label="Supplier email purpose"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[
                  "Negotiation",
                  "Missing Information",
                  "Updated Lead Time",
                  "Revised Pricing",
                  "Follow-Up",
                ].map((kind) => (
                  <SelectItem value={kind} key={kind}>
                    {kind}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button
              disabled={!canEdit || busy || !winner}
              onClick={() => action(generate)}
            >
              Generate recommendation
            </Button>
            <Button
              variant="outline"
              disabled={!canEdit || busy || !winner}
              onClick={() =>
                action(async () => {
                  setDraft(
                    await api<Draft>("/email-drafts", {
                      method: "POST",
                      body: JSON.stringify({
                        quote_id: winner!.id,
                        kind: draftKind,
                      }),
                    }),
                  );
                })
              }
            >
              <Mail size={15} />
              {draftKind === "Negotiation"
                ? "Draft negotiation email"
                : "Draft supplier email"}
            </Button>
            <Button
              variant="outline"
              disabled={
                !canEdit ||
                busy ||
                !rec.data ||
                rec.data.status === "Stale" ||
                rec.data.status === "Approved"
              }
              onClick={() => setApproveOpen(true)}
            >
              <CheckCircle2 size={15} />
              Approve recommendation
            </Button>
            <Button
              variant="ghost"
              disabled={!canEdit || busy || !winner}
              onClick={() =>
                action(async () => {
                  await api(`/quotes/${winner!.id}/preferred`, {
                    method: "POST",
                  });
                  setNotice("Supplier marked preferred.");
                })
              }
            >
              Mark preferred
            </Button>
          </div>
        </div>
        <div className="savings-panel">
          <span>Potential savings</span>
          <strong>{currency(data.potential_savings, rfq.currency)}</strong>
          <small>vs. highest comparable quote</small>
          <Button variant="link" onClick={() => setTab("analysis")}>
            View analysis <ArrowUpRight size={13} />
          </Button>
        </div>
      </section>
      <p className="source-footnote">
        <ShieldCheck size={13} />
        Every price links to a source. Review the recommended quotation before
        approving. {data.savings_basis}
      </p>
      <Dialog open={!!draft} onOpenChange={(open) => !open && setDraft(null)}>
        <DialogContent className="draft-dialog">
          <DialogHeader>
            <DialogTitle>Supplier communication draft</DialogTitle>
            <DialogDescription>
              Edit and approve internally. This application does not send
              emails.
            </DialogDescription>
          </DialogHeader>
          {draft && (
            <>
              <label>
                Subject
                <Input
                  value={draft.subject}
                  onChange={(e) =>
                    setDraft({ ...draft, subject: e.target.value })
                  }
                />
              </label>
              <label>
                Message
                <Textarea
                  className="draft-text"
                  value={draft.body}
                  onChange={(e) => setDraft({ ...draft, body: e.target.value })}
                />
              </label>
              <Status value={draft.status} />
              <DialogFooter>
                <Button
                  variant="outline"
                  onClick={() =>
                    action(async () => {
                      await navigator.clipboard.writeText(draft.body);
                      setNotice("Draft copied to clipboard.");
                    })
                  }
                >
                  Copy draft
                </Button>
                <Button
                  variant="outline"
                  disabled={busy}
                  onClick={() =>
                    action(async () => {
                      setDraft(
                        await api<Draft>(`/email-drafts/${draft.id}`, {
                          method: "PUT",
                          body: JSON.stringify({
                            subject: draft.subject,
                            body: draft.body,
                            status: "Draft",
                          }),
                        }),
                      );
                      setNotice("Draft saved.");
                    })
                  }
                >
                  Save draft
                </Button>
                <Button
                  disabled={busy}
                  onClick={() =>
                    action(async () => {
                      setDraft(
                        await api<Draft>(`/email-drafts/${draft.id}`, {
                          method: "PUT",
                          body: JSON.stringify({
                            subject: draft.subject,
                            body: draft.body,
                            status: "Approved",
                          }),
                        }),
                      );
                      setNotice("Email draft approved internally.");
                    })
                  }
                >
                  Mark approved
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
      <Dialog open={approveOpen} onOpenChange={setApproveOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Approve this recommendation?</DialogTitle>
            <DialogDescription>
              Record your team’s decision for {winner?.supplier_name}. This
              creates no purchase order or supplier commitment.
            </DialogDescription>
          </DialogHeader>
          <label>
            Review note
            <Textarea value={note} onChange={(e) => setNote(e.target.value)} />
          </label>
          {winner?.review_status !== "Reviewed" && (
            <p className="error-box">
              Review and confirm the recommended quotation first.{" "}
              <Link href={`/quotes/${winner?.id}`}>Open quote review</Link>
            </p>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setApproveOpen(false)}>
              Cancel
            </Button>
            <Button
              disabled={busy || winner?.review_status !== "Reviewed"}
              onClick={() =>
                action(async () => {
                  await api("/approvals", {
                    method: "POST",
                    body: JSON.stringify({
                      recommendation_id: rec.data!.id,
                      note,
                    }),
                  });
                  setApproveOpen(false);
                  setNotice("Recommendation approved. Audit event recorded.");
                  rec.reload();
                  reload();
                })
              }
            >
              Confirm approval
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
