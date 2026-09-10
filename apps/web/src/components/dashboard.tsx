"use client";
import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  Upload,
  TrendingDown,
  Clock3,
  CircleCheck,
  TriangleAlert,
  Files,
  Inbox,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useResource, currency, dateLabel, human } from "@/lib/api";
import type { Dashboard as DashboardData } from "@/lib/types";
import { PageHeader, Status, Loading, ErrorState, SectionLink } from "./shared";
export function Dashboard() {
  const { data, error, reload } = useResource<DashboardData>("/dashboard");
  if (error) return <ErrorState error={error} retry={reload} />;
  if (!data) return <Loading />;
  const m = data.metrics,
    showcase = data.rfqs.find((r) => r.number === "RFQ-1003");
  return (
    <>
      <PageHeader
        eyebrow="YOUR PROCUREMENT OVERVIEW"
        title="Good decisions start here."
        description="A clear view of your quotes, priorities, and opportunities."
      >
        <Button asChild>
          <Link href="/inbox">
            <Upload size={16} />
            Upload quotations
          </Link>
        </Button>
      </PageHeader>
      <div className="metrics-grid">
        {[
          [Files, "Open RFQs", m.open_rfqs, "Active sourcing events"],
          [
            Inbox,
            "Quotes received",
            m.quotes_received,
            "Across your open RFQs",
          ],
          [
            TriangleAlert,
            "Needs review",
            m.needs_review,
            "Ready for your attention",
          ],
          [
            TrendingDown,
            "Potential savings",
            currency(m.potential_savings, m.currency),
            "Versus highest comparable quotes",
          ],
        ].map(([Icon, label, value, description], i) => {
          const MetricIcon = Icon as typeof Files;
          return (
            <Card
              className={`metric ${i === 3 ? "savings" : ""}`}
              key={String(label)}
            >
              <div className="metric-label">
                {String(label)}
                <MetricIcon size={17} />
              </div>
              <strong>{String(value)}</strong>
              <small>{String(description)}</small>
            </Card>
          );
        })}
      </div>
      <div className="overview-strip">
        <span>
          <Clock3 size={15} />
          <strong>{m.awaiting_response}</strong> supplier responses pending
        </span>
        <span>
          <CircleCheck size={15} />
          <strong>{m.processing_seconds ?? "—"}s</strong> average processing
          time
        </span>
        <span className="muted">Calculated from your workspace data</span>
      </div>
      {showcase && (
        <Link href={`/rfqs/${showcase.id}`} className="showcase-banner">
          <div className="banner-icon">
            <Files size={25} />
          </div>
          <div>
            <div className="eyebrow">READY TO COMPARE · {showcase.number}</div>
            <h2>One RFQ. Four perspectives. A clearer decision.</h2>
            <p>
              {showcase.title} · {showcase.response_count} supplier responses ·
              Delivery {dateLabel(showcase.required_delivery)}
            </p>
          </div>
          <span>
            Open comparison <ArrowRight size={18} />
          </span>
        </Link>
      )}
      <div className="dashboard-columns">
        <Card className="section-card">
          <div className="section-heading">
            <div>
              <h2>Active sourcing</h2>
              <p>Your latest requests for quotation</p>
            </div>
            <SectionLink href="/rfqs">View all RFQs</SectionLink>
          </div>
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>RFQ / PROJECT</th>
                  <th>RESPONSES</th>
                  <th>STATUS</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {data.rfqs.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <Link className="row-link" href={`/rfqs/${r.id}`}>
                        <small>{r.number}</small>
                        <strong>{r.title}</strong>
                      </Link>
                    </td>
                    <td>
                      <div className="responses">
                        <strong>{r.response_count}</strong>
                        <span>/ {r.supplier_count}</span>
                        <div className="response-bars">
                          {Array.from({ length: r.supplier_count }, (_, i) => (
                            <i
                              key={i}
                              className={i < r.response_count ? "filled" : ""}
                            />
                          ))}
                        </div>
                      </div>
                    </td>
                    <td>
                      <Status value={r.status} />
                    </td>
                    <td>
                      <Link
                        href={`/rfqs/${r.id}`}
                        aria-label={`Open ${r.number}`}
                      >
                        <ArrowUpRight size={16} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
        <Card className="section-card">
          <div className="section-heading">
            <div>
              <h2>Needs your attention</h2>
              <p>Findings grounded in quote data</p>
            </div>
            <span className="count-badge">{data.alerts.length}</span>
          </div>
          <div className="alert-list">
            {data.alerts.slice(0, 5).map((a, i) => (
              <Link
                href={`/quotes/${a.quote_id}`}
                className="alert-item"
                key={i}
              >
                <div
                  className={`alert-icon ${a.severity === "blocking" ? "orange" : ""}`}
                >
                  <TriangleAlert size={17} />
                </div>
                <div>
                  <strong>{a.supplier_name}</strong>
                  <p>{a.message}</p>
                  <small>{human(a.code)}</small>
                </div>
                <ArrowUpRight size={14} />
              </Link>
            ))}
          </div>
        </Card>
      </div>
      <Card className="section-card activity-card">
        <div className="section-heading">
          <div>
            <h2>Recent activity</h2>
            <p>A traceable record of every important change</p>
          </div>
          <SectionLink href="/audit-events">View audit log</SectionLink>
        </div>
        <div className="activity-list">
          {data.activity.slice(0, 5).map((a) => (
            <div key={a.id}>
              <div className="activity-dot" />
              <strong>{human(a.action)}</strong>
              <span>{human(a.entity_type)}</span>
              <time>{new Date(String(a.created_at)).toLocaleString()}</time>
            </div>
          ))}
        </div>
      </Card>
    </>
  );
}
