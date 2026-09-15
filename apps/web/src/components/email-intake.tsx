"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  FileUp,
  Mail,
  Paperclip,
  RefreshCw,
  Search,
  ShieldCheck,
} from "lucide-react";
import { api, dateLabel, useResource } from "@/lib/api";
import type { ListData, ProcurementEmail } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ErrorState, Loading, Empty, PageHeader, Status } from "./shared";
import { useUser } from "./shell";

export function EmlUploadButton({ onQueued }: { onQueued?: () => void }) {
  const input = useRef<HTMLInputElement>(null);
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const canEdit = useUser()?.role !== "Viewer";
  async function upload(file?: File) {
    if (!file) return;
    setBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const result = await api<{ id: string }>("/emails/upload", {
        method: "POST",
        body: form,
      });
      onQueued?.();
      router.push(`/emails/${result.id}`);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Button
        variant="outline"
        disabled={!canEdit || busy}
        onClick={() => input.current?.click()}
      >
        <FileUp size={16} />
        {busy ? "Importing…" : "Import .eml"}
      </Button>
      <input
        ref={input}
        hidden
        aria-label="Import EML email"
        type="file"
        accept=".eml,message/rfc822"
        onChange={(event) => {
          void upload(event.target.files?.[0]);
          event.target.value = "";
        }}
      />
    </>
  );
}

export function EmailIntakePanel() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const emails = useResource<ListData>(
    `/emails?limit=20&page=${page}&search=${encodeURIComponent(search)}`,
    2000,
  );
  return (
    <Card className="section-card">
      <div className="filter-toolbar">
        <div className="search-field">
          <Search size={16} />
          <Input
            aria-label="Search procurement emails"
            placeholder="Search sender or subject…"
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
          />
        </div>
        <span className="muted">
          {emails.data?.total || 0} emails · Local processing only
        </span>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Refresh procurement emails"
          onClick={emails.reload}
        >
          <RefreshCw size={16} />
        </Button>
      </div>
      {emails.error ? (
        <ErrorState error={emails.error} retry={emails.reload} />
      ) : !emails.data ? (
        <Loading />
      ) : emails.data.items.length === 0 ? (
        <Empty
          title="No supplier emails yet"
          text="Import an .eml file or paste a supplier message to begin."
        />
      ) : (
        <div className="table-scroll">
          <table className="data-table email-table">
            <thead>
              <tr>
                <th>SENDER / SUBJECT</th>
                <th>TYPE</th>
                <th>RFQ</th>
                <th>ATTACHMENTS</th>
                <th>STATUS</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {emails.data.items.map((row) => (
                <tr key={row.id}>
                  <td>
                    <div className="email-sender">
                      <span className="mail-avatar">
                        <Mail size={16} />
                      </span>
                      <div>
                        <strong>{String(row.supplier_name || row.sender_email)}</strong>
                        <small>{String(row.subject)}</small>
                        <time>{dateLabel(String(row.sent_at || row.created_at))}</time>
                      </div>
                    </div>
                  </td>
                  <td>{String(row.email_type).replaceAll("_", " ")}</td>
                  <td>{row.rfq_id ? "Matched" : "Unmatched"}</td>
                  <td>
                    <Paperclip size={14} /> {Number(row.attachment_count || 0)}
                  </td>
                  <td>
                    <Status value={String(row.status)} />
                  </td>
                  <td>
                    <Button asChild variant="ghost" size="sm">
                      <Link href={`/emails/${row.id}`}>
                        Open <ArrowUpRight size={14} />
                      </Link>
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="pagination">
        <span>Page {page}</span>
        <Button
          variant="outline"
          size="sm"
          disabled={page === 1}
          onClick={() => setPage(page - 1)}
        >
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={page * 20 >= (emails.data?.total || 0)}
          onClick={() => setPage(page + 1)}
        >
          Next
        </Button>
      </div>
    </Card>
  );
}

export function EmailDetailPage({ id }: { id: string }) {
  const email = useResource<ProcurementEmail>(`/emails/${id}`, 2000);
  const [message, setMessage] = useState("");
  const canEdit = useUser()?.role !== "Viewer";
  if (email.error)
    return <ErrorState error={email.error} retry={email.reload} />;
  if (!email.data) return <Loading />;
  const data = email.data;
  return (
    <>
      <PageHeader
        eyebrow="PROCUREMENT EMAIL"
        title={data.subject}
        description={`${data.sender_name || data.sender_email} · ${dateLabel(data.sent_at || data.created_at)}`}
      >
        <Status value={data.status} />
        {data.quote_id && (
          <Button asChild>
            <Link href={`/quotes/${data.quote_id}`}>Review structured quote</Link>
          </Button>
        )}
      </PageHeader>
      {data.status_reason && (
        <div className="email-review-banner">
          <AlertTriangle size={18} />
          <div>
            <strong>Buyer review required</strong>
            <p>{data.status_reason}</p>
          </div>
        </div>
      )}
      <div className="email-detail-grid">
        <Card className="section-card email-message-card">
          <div className="email-header-grid">
            <span>FROM</span>
            <strong>{data.sender_name || "Unknown sender"}</strong>
            <small>{data.sender_email || "Missing From header"}</small>
            <span>TO</span>
            <p>{data.recipient_emails.join(", ") || "Not provided"}</p>
            <span>MESSAGE ID</span>
            <code>{data.message_id || "Generated from content hash"}</code>
          </div>
          <div className="clean-email-body">
            <h2>Current message</h2>
            <pre>{data.normalized_body || "No readable message body."}</pre>
          </div>
          {data.quoted_history && (
            <details className="quoted-history">
              <summary>Quoted thread history</summary>
              <pre>{data.quoted_history}</pre>
            </details>
          )}
        </Card>
        <div className="email-side-stack">
          <Card className="section-card identity-card">
            <div className="section-heading">
              <div>
                <h2>Matched context</h2>
                <p>Identity and RFQ links stay tenant-scoped.</p>
              </div>
              <ShieldCheck size={18} />
            </div>
            <dl>
              <dt>Supplier</dt>
              <dd>{data.supplier?.name || "Review required"}</dd>
              <dt>Supplier status</dt>
              <dd>
                <Status value={data.supplier?.status || "UNMATCHED"} />
              </dd>
              <dt>RFQ</dt>
              <dd>{data.rfq ? `${data.rfq.number} · ${data.rfq.title}` : "Unmatched"}</dd>
              <dt>Email type</dt>
              <dd>{data.email_type.replaceAll("_", " ")}</dd>
            </dl>
            {canEdit && data.supplier?.status === "NEW_UNVERIFIED" && (
              <Button
                variant="outline"
                onClick={async () => {
                  try {
                    await api(`/emails/${id}/supplier`, {
                      method: "POST",
                      body: JSON.stringify({ action: "VERIFY" }),
                    });
                    setMessage("Supplier verified.");
                    email.reload();
                  } catch (error) {
                    setMessage((error as Error).message);
                  }
                }}
              >
                <CheckCircle2 size={15} /> Verify supplier
              </Button>
            )}
          </Card>
          <Card className="section-card">
            <div className="section-heading">
              <div>
                <h2>Attachments</h2>
                <p>PDF, XLSX, CSV, and TXT use the document pipeline.</p>
              </div>
            </div>
            {data.attachments.length ? (
              <div className="attachment-list">
                {data.attachments.map((attachment) => (
                  <a
                    key={attachment.id}
                    href={`/api/emails/${id}/attachments/${attachment.id}/file`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <Paperclip size={15} />
                    <span>
                      <strong>{attachment.filename}</strong>
                      <small>
                        {attachment.status.replaceAll("_", " ")} ·{" "}
                        {Math.ceil(attachment.size / 1024)} KB
                      </small>
                    </span>
                  </a>
                ))}
              </div>
            ) : (
              <p className="muted">No attachments.</p>
            )}
          </Card>
        </div>
      </div>
      {data.conflicts.length > 0 && (
        <Card className="section-card conflict-card">
          <div className="section-heading">
            <div>
              <h2>Field conflicts</h2>
              <p>Email and attachment evidence differ. No value was silently replaced.</p>
            </div>
            <AlertTriangle size={18} />
          </div>
          <div className="conflict-list">
            {data.conflicts.map((conflict) => (
              <div key={conflict.id}>
                <strong>{conflict.field}</strong>
                <span>Email: {conflict.email_value?.value}</span>
                <span>Attachment: {conflict.attachment_value?.value}</span>
                <Status value={conflict.resolution} />
              </div>
            ))}
          </div>
        </Card>
      )}
      <div className="email-lower-grid">
        <Card className="section-card">
          <div className="section-heading">
            <div>
              <h2>Thread timeline</h2>
              <p>Earlier values remain available as revision history.</p>
            </div>
          </div>
          <div className="timeline-list">
            {data.timeline.map((entry) => (
              <Link key={entry.email_id} href={`/emails/${entry.email_id}`}>
                <time>{dateLabel(entry.sent_at || data.created_at)}</time>
                <span>
                  <strong>{entry.type.replaceAll("_", " ")}</strong>
                  <small>{entry.subject}</small>
                </span>
                <Status value={entry.status} />
              </Link>
            ))}
          </div>
        </Card>
        <Card className="section-card">
          <div className="section-heading">
            <div>
              <h2>Source evidence</h2>
              <p>Accepted values retain their exact email or attachment source.</p>
            </div>
          </div>
          <div className="email-evidence-list">
            {data.evidence.length ? (
              data.evidence.map((evidence) => (
                <details key={evidence.id}>
                  <summary>
                    <span>{evidence.field}</span>
                    <strong>{evidence.value?.value ?? "Missing"}</strong>
                    <Status value={evidence.decision_status} />
                  </summary>
                  <blockquote>{evidence.source_snippet}</blockquote>
                  <small>{evidence.source_type.replaceAll("_", " ")}</small>
                </details>
              ))
            ) : (
              <Empty title="No accepted quote evidence" />
            )}
          </div>
        </Card>
      </div>
      <p role="status">{message}</p>
    </>
  );
}
