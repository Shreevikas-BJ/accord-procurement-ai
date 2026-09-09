"use client";
import Link from "next/link";
import { useState } from "react";
import {
  ArrowDownUp,
  ArrowLeft,
  ArrowUpRight,
  ChevronLeft,
  ChevronRight,
  Search,
  Upload,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useResource, api, currency, human, dateLabel } from "@/lib/api";
import type { ListData, Row } from "@/lib/types";
import {
  PageHeader,
  Loading,
  ErrorState,
  Status,
  Empty,
  Notice,
} from "./shared";
import { useUser } from "./shell";
const configs: Record<
  string,
  { title: string; description: string; columns: [string, string][] }
> = {
  rfqs: {
    title: "Requests for quotation",
    description: "Every sourcing event, from first quote to reviewed decision.",
    columns: [
      ["number", "RFQ"],
      ["title", "Project"],
      ["required_delivery", "Required delivery"],
      ["response_count", "Responses"],
      ["status", "Status"],
    ],
  },
  suppliers: {
    title: "Your supplier network",
    description:
      "Relationships, sourcing categories, and performance in one place.",
    columns: [
      ["name", "Supplier"],
      ["category", "Category"],
      ["currency", "Currency"],
      ["payment_terms", "Terms"],
      ["preferred_supplier", "Preferred"],
      ["status", "Status"],
    ],
  },
  items: {
    title: "Item master",
    description: "A shared vocabulary for every supplier quotation.",
    columns: [
      ["sku", "Internal SKU"],
      ["description", "Description"],
      ["manufacturer_part_number", "Manufacturer part"],
      ["category", "Category"],
      ["uom", "UOM"],
    ],
  },
  "purchase-history": {
    title: "Purchase history",
    description:
      "Your historical purchasing data powers every price comparison.",
    columns: [
      ["po_number", "PO number"],
      ["date", "Date"],
      ["supplier_name", "Supplier"],
      ["sku", "Item"],
      ["quantity", "Quantity"],
      ["uom", "UOM"],
      ["unit_price", "Unit price"],
      ["total", "Total"],
      ["lead_time_days", "Lead time"],
    ],
  },
  "audit-events": {
    title: "Audit log",
    description:
      "Who changed what, when, and why. A durable record of every decision.",
    columns: [
      ["created_at", "Timestamp"],
      ["action", "Action"],
      ["entity_type", "Entity"],
      ["entity_id", "Record ID"],
      ["actor_name", "Actor"],
    ],
  },
};
export function Catalog({ kind }: { kind: string }) {
  const [selectedEvent, setSelectedEvent] = useState<Row | null>(null);
  const [search, setSearch] = useState(""),
    [page, setPage] = useState(1),
    [status, setStatus] = useState("all"),
    [direction, setDirection] = useState("desc"),
    [message, setMessage] = useState("");
  const user = useUser();
  const config = configs[kind];
  const resource = useResource<ListData>(
    `/${kind}?search=${encodeURIComponent(search)}&page=${page}&limit=20&status=${status === "all" ? "" : encodeURIComponent(status)}&direction=${direction}`,
  );
  return (
    <>
      <PageHeader
        eyebrow="PROCUREMENT WORKSPACE"
        title={config.title}
        description={config.description}
      >
        {kind === "rfqs" && (
          <Button asChild>
            <Link href="/inbox">
              <Upload size={15} />
              Upload quotes
            </Link>
          </Button>
        )}
        {kind === "purchase-history" && user?.role === "Admin" && (
          <label className="upload-button">
            <Upload size={15} />
            Import CSV
            <input
              type="file"
              accept=".csv"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                const form = new FormData();
                form.append("file", file);
                try {
                  const r = await api<{ imported: number }>(
                    "/purchase-history/import",
                    { method: "POST", body: form },
                  );
                  setMessage(
                    `${r.imported} rows imported. Procurement analysis refreshed.`,
                  );
                  resource.reload();
                } catch (e) {
                  setMessage((e as Error).message);
                }
              }}
            />
          </label>
        )}
      </PageHeader>
      {message && <Notice text={message} onClose={() => setMessage("")} />}
      <Card className="section-card">
        <div className="filter-toolbar">
          <div className="search-field">
            <Search size={16} />
            <Input
              aria-label={`Search ${config.title}`}
              value={search}
              placeholder={`Search ${kind === "audit-events" ? "actions or entities" : config.title.toLowerCase()}…`}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
            />
          </div>
          {kind === "rfqs" && (
            <Select
              value={status}
              onValueChange={(v) => {
                setStatus(v);
                setPage(1);
              }}
            >
              <SelectTrigger className="filter-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[
                  "all",
                  "Draft",
                  "Open",
                  "Quotes Received",
                  "Under Review",
                  "Awarded",
                  "Closed",
                ].map((s) => (
                  <SelectItem key={s} value={s}>
                    {s === "all" ? "All statuses" : s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          <Button
            variant="outline"
            onClick={() => setDirection(direction === "desc" ? "asc" : "desc")}
          >
            <ArrowDownUp size={14} />
            {direction === "desc" ? "Newest first" : "Oldest first"}
          </Button>
          <span className="muted">{resource.data?.total ?? "…"} records</span>
        </div>
        {resource.error ? (
          <ErrorState error={resource.error} retry={resource.reload} />
        ) : !resource.data ? (
          <Loading />
        ) : resource.data.items.length === 0 ? (
          <Empty
            title="No matching records"
            text="Try a different search or filter."
          />
        ) : (
          <div className="table-scroll">
            <table className="data-table catalog-table">
              <thead>
                <tr>
                  {config.columns.map(([key, label]) => (
                    <th key={key}>{label}</th>
                  ))}
                  {["rfqs", "suppliers", "items"].includes(kind) && <th />}
                  {kind === "audit-events" && <th>Details</th>}
                </tr>
              </thead>
              <tbody>
                {resource.data.items.map((row) => (
                  <tr key={row.id}>
                    {config.columns.map(([key], i) => (
                      <td key={key}>
                        {["status", "review_status"].includes(key) ? (
                          <Status value={String(row[key])} />
                        ) : key === "action" ? (
                          <span className="audit-action">
                            {human(row[key])}
                          </span>
                        ) : key === "preferred_supplier" ? (
                          row[key] ? (
                            "Preferred"
                          ) : (
                            "—"
                          )
                        ) : key === "created_at" ? (
                          new Date(String(row[key])).toLocaleString()
                        ) : ["date", "required_delivery"].includes(key) ? (
                          dateLabel(row[key])
                        ) : ["unit_price", "total"].includes(key) ? (
                          currency(row[key], String(row.currency || "USD"))
                        ) : i === 0 &&
                          ["rfqs", "suppliers", "items"].includes(kind) ? (
                          <Link
                            className="row-link"
                            href={`/${kind}/${row.id}`}
                          >
                            <strong>{String(row[key] ?? "—")}</strong>
                          </Link>
                        ) : ["entity_id", "user_id"].includes(key) ? (
                          <code title={String(row[key])}>
                            {String(row[key] ?? "System").slice(0, 8)}
                          </code>
                        ) : (
                          String(row[key] ?? "—")
                        )}
                      </td>
                    ))}
                    {["rfqs", "suppliers", "items"].includes(kind) && (
                      <td>
                        <Link
                          aria-label={`Open ${row.name || row.number || row.sku}`}
                          href={`/${kind}/${row.id}`}
                        >
                          <ArrowUpRight size={15} />
                        </Link>
                      </td>
                    )}
                    {kind === "audit-events" && (
                      <td>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setSelectedEvent(row)}
                        >
                          Inspect change
                        </Button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="pagination">
          <span>
            Page {page} of{" "}
            {Math.max(1, Math.ceil((resource.data?.total || 0) / 20))}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
          >
            <ChevronLeft size={14} />
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={page * 20 >= (resource.data?.total || 0)}
            onClick={() => setPage(page + 1)}
          >
            Next
            <ChevronRight size={14} />
          </Button>
        </div>
      </Card>
      <Dialog
        open={!!selectedEvent}
        onOpenChange={(open) => !open && setSelectedEvent(null)}
      >
        <DialogContent className="draft-dialog">
          <DialogHeader>
            <DialogTitle>{human(selectedEvent?.action)}</DialogTitle>
            <DialogDescription>
              Original and updated values are retained with the acting user and
              timestamp.
            </DialogDescription>
          </DialogHeader>
          {selectedEvent && (
            <>
              <p>
                {new Date(String(selectedEvent.created_at)).toLocaleString()} ·{" "}
                {String(selectedEvent.user_id || "System")}
              </p>
              {(["old_value", "new_value", "details"] as const).map((key) => (
                <section key={key}>
                  <h3>{human(key)}</h3>
                  <pre className="audit-json">
                    {JSON.stringify(selectedEvent[key], null, 2) || "No value"}
                  </pre>
                </section>
              ))}
            </>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
interface Detail extends Row {
  history: Row[];
  quotes?: Row[];
  contacts?: Row[];
  aliases?: string[];
  metrics?: {
    spend_by_currency: Record<string, string>;
    order_count: number;
    average_lead_time: string;
    on_time_orders: number;
  };
}
export function DetailPage({ kind, id }: { kind: string; id: string }) {
  const { data, error, reload } = useResource<Detail>(`/${kind}/${id}`);
  if (error) return <ErrorState error={error} retry={reload} />;
  if (!data) return <Loading />;
  return (
    <>
      <Link className="back-link" href={`/${kind}`}>
        <ArrowLeft size={14} />
        All {kind}
      </Link>
      <PageHeader
        eyebrow={kind === "suppliers" ? "SUPPLIER PROFILE" : "ITEM PROFILE"}
        title={String(data.name || data.sku)}
        description={String(data.description || data.category)}
      />
      {data.metrics && (
        <div className="metrics-grid">
          <Card className="metric">
            <span>Historical spend</span>
            <strong>
              {Object.entries(data.metrics.spend_by_currency)
                .map(([c, v]) => currency(v, c))
                .join(" · ")}
            </strong>
            <small>All recorded purchases</small>
          </Card>
          <Card className="metric">
            <span>Purchase orders</span>
            <strong>{data.metrics.order_count}</strong>
          </Card>
          <Card className="metric">
            <span>Average lead time</span>
            <strong>
              {Number(data.metrics.average_lead_time).toFixed(0)}{" "}
              <small>days</small>
            </strong>
          </Card>
          <Card className="metric">
            <span>On-time orders</span>
            <strong>{data.metrics.on_time_orders}</strong>
          </Card>
        </div>
      )}
      <Card className="section-card">
        <div className="section-heading">
          <h2>Overview</h2>
        </div>
        <div className="profile-overview">
          {Object.entries(data)
            .filter(
              ([k, v]) =>
                !["id", "organization_id", "created_at"].includes(k) &&
                ["string", "number", "boolean"].includes(typeof v),
            )
            .map(([k, v]) => (
              <div key={k}>
                <small>{human(k)}</small>
                <strong>{String(v)}</strong>
              </div>
            ))}
          {data.aliases && (
            <div>
              <small>Aliases</small>
              <strong>{data.aliases.join(", ") || "None"}</strong>
            </div>
          )}
          {data.contacts?.map((c) => (
            <div key={c.id}>
              <small>{String(c.name)}</small>
              <strong>{String(c.email)}</strong>
            </div>
          ))}
        </div>
      </Card>
      {data.quotes && (
        <Card className="section-card">
          <div className="section-heading">
            <h2>Recent quotations</h2>
          </div>
          <div className="profile-quotes">
            {data.quotes.map((q) => (
              <Link key={q.id} href={`/quotes/${q.id}`}>
                <FileQuote
                  number={String(q.quote_number)}
                  status={String(q.review_status)}
                />
              </Link>
            ))}
          </div>
        </Card>
      )}
      <Card className="section-card">
        <div className="section-heading">
          <div>
            <h2>Purchase history & pricing</h2>
            <p>
              Most recent recorded purchases. Prices retain their original
              currency.
            </p>
          </div>
        </div>
        {data.history.length ? (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>PO NUMBER</th>
                  <th>DATE</th>
                  <th>QUANTITY</th>
                  <th>UNIT PRICE</th>
                  <th>LEAD TIME</th>
                  <th>EXPECTED</th>
                  <th>ACTUAL</th>
                </tr>
              </thead>
              <tbody>
                {data.history.map((h) => (
                  <tr key={h.id}>
                    <td>{String(h.po_number)}</td>
                    <td>{dateLabel(h.date)}</td>
                    <td>
                      {Number(h.quantity).toLocaleString()} {String(h.uom)}
                    </td>
                    <td>{currency(h.unit_price, String(h.currency))}</td>
                    <td>{String(h.lead_time_days)} days</td>
                    <td>{dateLabel(h.expected_delivery)}</td>
                    <td>{dateLabel(h.actual_delivery)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty
            title="No purchasing history"
            text="Import purchase data to power historical analysis."
          />
        )}
      </Card>
    </>
  );
}
function FileQuote({ number, status }: { number: string; status: string }) {
  return (
    <>
      <strong>{number}</strong>
      <Status value={status} />
      <ArrowUpRight size={14} />
    </>
  );
}
