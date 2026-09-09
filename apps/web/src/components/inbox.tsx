"use client";
import Link from "next/link";
import { useState } from "react";
import {
  UploadCloud,
  FileText,
  ArrowUpRight,
  Mail,
  RefreshCw,
  Search,
  Inbox as InboxIcon,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { api, useResource, dateLabel } from "@/lib/api";
import type { ListData, Draft } from "@/lib/types";
import { PageHeader, Status, ErrorState, Loading, Empty } from "./shared";
import { useUser } from "./shell";
export function Inbox() {
  const [search, setSearch] = useState(""),
    [page, setPage] = useState(1),
    [rfq, setRfq] = useState("auto"),
    [drag, setDrag] = useState(false),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState(""),
    [paste, setPaste] = useState(false),
    [subject, setSubject] = useState(""),
    [text, setText] = useState("");
  const docs = useResource<ListData>(
      `/documents?limit=20&page=${page}&search=${encodeURIComponent(search)}`,
      2000,
    ),
    rfqs = useResource<ListData>("/rfqs?limit=100"),
    drafts = useResource<Draft[]>("/email-drafts");
  const canEdit = useUser()?.role !== "Viewer";
  async function upload(files: FileList | null) {
    if (!files) return;
    setBusy(true);
    setMessage("");
    const outcomes = [];
    for (const file of Array.from(files)) {
      const form = new FormData();
      form.append("file", file);
      if (rfq !== "auto") form.append("rfq_id", rfq);
      try {
        await api("/quotes/upload", { method: "POST", body: form });
        outcomes.push(`${file.name}: queued`);
      } catch (e) {
        outcomes.push(`${file.name}: ${(e as Error).message}`);
      }
    }
    setMessage(outcomes.join("\n"));
    setBusy(false);
    docs.reload();
  }
  return (
    <>
      <PageHeader
        eyebrow="DOCUMENT INBOX"
        title="From quotation to clarity."
        description="Upload supplier documents or paste an email. We’ll prepare them for your review."
      >
        <Button
          variant="outline"
          disabled={!canEdit}
          onClick={() => setPaste(true)}
        >
          <Mail size={16} />
          Paste supplier email
        </Button>
      </PageHeader>
      <Card
        className={`dropzone ${drag ? "dragging" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          if (canEdit) void upload(e.dataTransfer.files);
        }}
      >
        <div className="upload-cloud">
          <UploadCloud size={30} />
        </div>
        <div>
          <h2>
            {busy
              ? "Uploading your documents…"
              : "Drop supplier quotations here"}
          </h2>
          <p>PDF, XLSX, CSV, PNG, JPG, or TXT · Up to 15 MB each</p>
          <small>Upload 3–5 quotations for one RFQ to compare suppliers.</small>
        </div>
        <div className="upload-controls">
          <Select value={rfq} onValueChange={setRfq}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="auto">Identify RFQ from document</SelectItem>
              {rfqs.data?.items.map((r) => (
                <SelectItem key={r.id} value={r.id}>
                  {String(r.number)} · {String(r.title)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <label className={`upload-button ${!canEdit ? "disabled" : ""}`}>
            <UploadCloud size={16} />
            Browse files
            <input
              aria-label="Upload quotations"
              type="file"
              multiple
              accept=".pdf,.xlsx,.csv,.png,.jpg,.jpeg,.txt"
              disabled={busy || !canEdit}
              onChange={(e) => {
                void upload(e.target.files);
                e.target.value = "";
              }}
            />
          </label>
        </div>
      </Card>
      {message && (
        <pre className="upload-message" role="status">
          {message}
        </pre>
      )}
      <div className="demo-inbox-note">
        <FileText size={16} />
        <p>
          <strong>Trying the demo?</strong> Use the files named{" "}
          <code>Upload_*</code> in <code>demo-data/quotes</code>. Other
          documents require local AI or manual entry. Existing documents are
          detected as duplicates.
        </p>
      </div>
      <Tabs defaultValue="documents">
        <TabsList>
          <TabsTrigger value="documents">Documents</TabsTrigger>
          <TabsTrigger value="drafts">
            Email drafts{" "}
            <span className="tab-count">{drafts.data?.length || 0}</span>
          </TabsTrigger>
        </TabsList>
        <TabsContent value="documents">
          <Card className="section-card">
            <div className="filter-toolbar">
              <div className="search-field">
                <Search size={16} />
                <Input
                  aria-label="Search inbox"
                  placeholder="Search documents or processing status…"
                  value={search}
                  onChange={(e) => {
                    setSearch(e.target.value);
                    setPage(1);
                  }}
                />
              </div>
              <span className="muted">
                {docs.data?.total || 0} documents · Live processing status
              </span>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Refresh inbox"
                onClick={docs.reload}
              >
                <RefreshCw size={16} />
              </Button>
            </div>
            {docs.error ? (
              <ErrorState error={docs.error} retry={docs.reload} />
            ) : !docs.data ? (
              <Loading />
            ) : docs.data.items.length === 0 ? (
              <Empty title="Your inbox is clear" />
            ) : (
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>SUPPLIER / DOCUMENT</th>
                      <th>RFQ</th>
                      <th>RECEIVED</th>
                      <th>PROCESSING</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {docs.data.items.map((d) => (
                      <tr key={d.id}>
                        <td>
                          <div className="document-row">
                            <div className="file-icon">
                              <FileText size={20} />
                            </div>
                            <div>
                              <strong>{String(d.supplier_name)}</strong>
                              <small>{String(d.filename)}</small>
                            </div>
                          </div>
                        </td>
                        <td>{String(d.rfq_number || "Unmatched")}</td>
                        <td>{dateLabel(d.created_at)}</td>
                        <td>
                          <Status value={String(d.status)} />
                          <small className="stage-label">
                            {String(d.stage)}
                          </small>
                          {Boolean(d.error) && (
                            <small className="inline-warning">
                              {String(d.error)}
                            </small>
                          )}
                        </td>
                        <td>
                          <Button asChild variant="ghost" size="sm">
                            <Link
                              href={
                                d.quote_id
                                  ? `/quotes/${d.quote_id}`
                                  : `/documents/${d.id}`
                              }
                            >
                              Review
                              <ArrowUpRight size={14} />
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
                disabled={page * 20 >= (docs.data?.total || 0)}
                onClick={() => setPage(page + 1)}
              >
                Next
              </Button>
            </div>
          </Card>
        </TabsContent>
        <TabsContent value="drafts">
          <Card className="section-card">
            <div className="section-heading">
              <h2>Saved supplier communication</h2>
              <p>Drafts are never sent automatically.</p>
            </div>
            {drafts.data?.length ? (
              drafts.data.map((d) => <DraftCard key={d.id} draft={d} />)
            ) : (
              <Empty
                title="No drafts yet"
                text="Generate a negotiation or follow-up draft from an RFQ comparison."
              />
            )}
          </Card>
        </TabsContent>
      </Tabs>
      <Dialog open={paste} onOpenChange={setPaste}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Paste supplier email</DialogTitle>
            <DialogDescription>
              The message is saved as a source document and queued for
              extraction. You can attach its quotation using the same RFQ above.
            </DialogDescription>
          </DialogHeader>
          <label>
            Subject
            <Input
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
            />
          </label>
          <label>
            Email text
            <Textarea
              className="draft-text"
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          </label>
          <DialogFooter>
            <Button
              disabled={busy || subject.length < 1 || text.length < 20}
              onClick={async () => {
                setBusy(true);
                try {
                  await api("/quotes/paste", {
                    method: "POST",
                    body: JSON.stringify({
                      subject,
                      text,
                      rfq_id: rfq === "auto" ? null : rfq,
                    }),
                  });
                  setPaste(false);
                  setMessage("Supplier email saved and queued.");
                  docs.reload();
                } catch (e) {
                  setMessage((e as Error).message);
                } finally {
                  setBusy(false);
                }
              }}
            >
              Save and process
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
function DraftCard({ draft }: { draft: Draft }) {
  const [body, setBody] = useState(draft.body),
    [message, setMessage] = useState("");
  const canEdit = useUser()?.role !== "Viewer";
  return (
    <div className="draft-card">
      <h3>{draft.subject}</h3>
      <Status value={draft.status} />
      <Textarea
        aria-label="Saved email draft"
        value={body}
        readOnly={!canEdit}
        onChange={(e) => setBody(e.target.value)}
      />
      <Button
        disabled={!canEdit}
        variant="outline"
        onClick={async () => {
          try {
            await api(`/email-drafts/${draft.id}`, {
              method: "PUT",
              body: JSON.stringify({
                subject: draft.subject,
                body,
                status: "Draft",
              }),
            });
            setMessage("Draft saved.");
          } catch (e) {
            setMessage((e as Error).message);
          }
        }}
      >
        Save changes
      </Button>
      <p role="status">{message}</p>
    </div>
  );
}
export function DocumentPage({ id }: { id: string }) {
  const resource = useResource<{
    filename: string;
    raw_text: string;
    error: string;
    status: string;
    stage: string;
    quote_id: string | null;
  }>(`/documents/${id}`, 2000);
  const [json, setJson] = useState(
      JSON.stringify(
        {
          supplier_name: "",
          quote_number: "",
          rfq_number: "RFQ-1003",
          currency: "USD",
          quote_date: "2026-09-09",
          expiration_date: null,
          shipping_cost: null,
          tax: null,
          confidence: "1",
          line_items: [
            {
              supplier_sku: "",
              description: "",
              quantity: null,
              uom: "EA",
              unit_price: null,
              moq: null,
              lead_time_days: null,
              confidence: "1",
            },
          ],
        },
        null,
        2,
      ),
    ),
    [message, setMessage] = useState("");
  const canEdit = useUser()?.role !== "Viewer";
  if (resource.error)
    return <ErrorState error={resource.error} retry={resource.reload} />;
  if (!resource.data) return <Loading />;
  const doc = resource.data;
  return (
    <>
      <PageHeader
        eyebrow="SOURCE DOCUMENT"
        title={doc.filename}
        description={doc.stage}
      >
        <Status value={doc.status} />
        <Button asChild variant="outline">
          <a
            href={`/api/documents/${id}/file`}
            target="_blank"
            rel="noreferrer"
          >
            Open original
          </a>
        </Button>
      </PageHeader>
      {doc.quote_id ? (
        <Card className="empty-state">
          <CheckStatus />
          <h2>Quotation is ready for review</h2>
          <Button asChild>
            <Link href={`/quotes/${doc.quote_id}`}>Open structured quote</Link>
          </Button>
        </Card>
      ) : (
        <>
          <p className="error-box">
            {doc.error ||
              "Processing is in progress. This page updates automatically."}
          </p>
          <Button
            disabled={!canEdit || doc.status === "Processing"}
            variant="outline"
            onClick={async () => {
              try {
                await api(`/documents/${id}/retry`, { method: "POST" });
                resource.reload();
              } catch (e) {
                setMessage((e as Error).message);
              }
            }}
          >
            <RefreshCw size={15} />
            Retry processing
          </Button>
          <div className="manual-grid">
            <Card className="section-card">
              <div className="section-heading">
                <h2>Extracted source text</h2>
              </div>
              <pre className="document-text">
                {doc.raw_text ||
                  "No text extracted. Refer to the original file."}
              </pre>
            </Card>
            <Card className="section-card">
              <div className="section-heading">
                <div>
                  <h2>Manual quote entry</h2>
                  <p>
                    Enter only values verified in the document. Unknown values
                    remain null.
                  </p>
                </div>
              </div>
              <div className="manual-editor">
                <Textarea
                  aria-label="Manual quote JSON"
                  value={json}
                  onChange={(e) => setJson(e.target.value)}
                  readOnly={!canEdit}
                />
                <Button
                  disabled={!canEdit || doc.status === "Processing"}
                  onClick={async () => {
                    try {
                      const result = await api<{ quote_id: string }>(
                        `/documents/${id}/manual`,
                        {
                          method: "POST",
                          body: JSON.stringify(JSON.parse(json)),
                        },
                      );
                      setMessage(
                        `Quote created. Open the review above (${result.quote_id.slice(0, 8)}).`,
                      );
                      resource.reload();
                    } catch (e) {
                      setMessage((e as Error).message);
                    }
                  }}
                >
                  Create structured quote
                </Button>
                <p role="status">{message}</p>
              </div>
            </Card>
          </div>
        </>
      )}
    </>
  );
}
function CheckStatus() {
  return <InboxIcon size={28} />;
}
