"""Opt-in tests against live HTTP, PostgreSQL, Redis, RQ and mounted files.

Run on a demo stack: RUN_DOCKER_INTEGRATION=true pytest integration -q.
These tests create audit entries and verification documents, never send email.
"""

import hashlib
import io
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timezone
from decimal import Decimal

import httpx
import pytest
from redis import Redis
from reportlab.pdfgen.canvas import Canvas
from rq import Queue, Worker
from rq.job import Job, Callback
from sqlalchemy import select, text, func, inspect
from sqlalchemy.exc import IntegrityError

from app.config import DEMO_PATH, REDIS_URL
from app.db import SessionLocal, engine
from app.models import Document, Quote, Item, Approval, AuditEvent, DocumentExtraction
from app.pipeline import job_failed
from app.providers import LocalStorageProvider
from app.schemas import QuoteExtraction, LineItemExtraction
from app.seed import sid
from integration.job_probe import timeout_document_job

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DOCKER_INTEGRATION") != "true", reason="Requires a live demo Docker stack"
)
RFQ = sid("rfq-3")


@pytest.fixture(scope="module")
def clients():
    result = {}
    for role, email in {
        "buyer": "buyer@apex.example",
        "admin": "admin@apex.example",
        "viewer": "viewer@apex.example",
        "isolated": "viewer@isolated.example",
    }.items():
        client = httpx.Client(base_url="http://web:3000/api", headers={"X-Procurement-Client": "workspace"}, timeout=30)
        response = client.post("/auth/login", json={"email": email, "password": "Demo2026!accord"})
        assert response.status_code == 200, response.text
        assert "httponly" in response.headers["set-cookie"].lower()
        assert "samesite=strict" in response.headers["set-cookie"].lower()
        result[role] = client
    yield result
    for client in result.values():
        client.close()


def response_json(response, status=200):
    assert response.status_code == status, response.text
    return response.json()


def wait_document(client, id):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        data = response_json(client.get(f"/documents/{id}"))
        if data["status"] not in ("New", "Processing"):
            return data
        time.sleep(0.2)
    pytest.fail(f"Document {id} stuck: {data}")


def upload(client, name, content, mime):
    response = client.post("/quotes/upload", files={"file": (name, content, mime)})
    if response.status_code == 409:
        return wait_document(client, response.json()["detail"]["document_id"])
    return wait_document(client, response_json(response, 202)["id"])


def synthetic_pdf():
    output = io.BytesIO()
    canvas = Canvas(output)
    canvas.drawString(72, 700, "Synthetic unknown quotation " + uuid.uuid4().hex)
    canvas.drawString(72, 675, "Unlisted Supplier. Manual review required. No fixture available.")
    canvas.save()
    return output.getvalue()


def review_payload(detail):
    payload = {k: detail[k] for k in QuoteExtraction.model_fields if k != "line_items"}
    payload.update(
        version=detail["version"], supplier_id=detail["supplier_id"], rfq_id=detail["rfq_id"], confirm_review=True
    )
    payload["line_items"] = [
        {**{k: line[k] for k in LineItemExtraction.model_fields}, "id": line["id"], "item_id": line["item_id"]}
        for line in detail["line_items"]
    ]
    return payload


def test_postgresql_schema_numeric_and_constraints():
    assert engine.dialect.name == "postgresql", "Never substitute SQLite for this suite"
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) == "0001"
        assert conn.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
        for table, minimum in {
            "suppliers": 50,
            "items": 250,
            "purchase_history": 2000,
            "rfqs": 5,
            "quotes": 20,
        }.items():
            assert conn.scalar(text(f"SELECT count(*) FROM {table}")) >= minimum
        assert isinstance(conn.scalar(text("SELECT unit_price FROM quote_items LIMIT 1")), Decimal)
        assert conn.scalar(text("SELECT current_timestamp")).tzinfo is not None
    schema = inspect(engine)
    assert schema.get_foreign_keys("quote_items")
    assert any(i["column_names"] == ["organization_id"] for i in schema.get_indexes("quotes"))
    with SessionLocal() as db:
        with pytest.raises(IntegrityError), db.begin_nested():
            db.add(
                Item(
                    organization_id=str(uuid.uuid4()),
                    sku="INVALID-FK",
                    manufacturer_part_number="INVALID",
                    description="Constraint test",
                    category="Test",
                    uom="EA",
                )
            )
            db.flush()
        item = Item(
            organization_id=sid("org"),
            sku="VERIFY-" + uuid.uuid4().hex,
            manufacturer_part_number="VERIFY",
            description="Rollback-only CRUD",
            category="Test",
            uom="EA",
        )
        # Use the seeded organization's actual ID; no assumed UUID convention.
        item.organization_id = db.scalar(select(Item.organization_id))
        db.add(item)
        db.flush()
        item.description = "Updated transaction"
        db.flush()
        assert db.get(Item, item.id).description == "Updated transaction"
        db.delete(item)
        db.flush()
        db.rollback()


def test_redis_worker_and_readiness(clients):
    health = response_json(httpx.get("http://api:8000/health"))
    assert health["database"] == "postgresql"
    redis = Redis.from_url(REDIS_URL)
    assert redis.ping()
    workers = Worker.all(connection=redis)
    assert any("documents" in w.queue_names() and w.last_heartbeat for w in workers)


@pytest.mark.parametrize(
    "name,mime",
    [
        ("Upload_Atlas_RFQ1003.pdf", "application/pdf"),
        ("Upload_Meridian_RFQ1003.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        ("Upload_Nova_RFQ1003.csv", "text/csv"),
    ],
)
def test_known_document_pipeline_and_private_storage(clients, name, mime):
    content = (DEMO_PATH / "quotes" / name).read_bytes()
    doc = upload(clients["buyer"], name, content, mime)
    assert doc["stage"] == "Complete", doc
    assert doc["quote_id"] and doc["raw_text"]
    quote = response_json(clients["buyer"].get(f"/quotes/{doc['quote_id']}"))
    assert quote["supplier_id"] and all(line["item_id"] for line in quote["line_items"])
    assert len(quote["line_items"]) == 3 and Decimal(quote["total"]) > 0
    for line in quote["line_items"]:
        evidence = line["source_references"]["unit_price"]
        assert evidence["document_id"] == doc["id"] and evidence["page"] >= 1 and evidence["source_text"]
        assert Decimal(line["confidence"]) > 0
    source = clients["buyer"].get(f"/documents/{doc['id']}/file")
    assert source.status_code == 200 and source.content == content
    with SessionLocal() as db:
        stored = db.get(Document, doc["id"])
        assert stored.sha256 == hashlib.sha256(content).hexdigest()
        assert stored.storage_key.startswith(stored.organization_id + "/")
        assert LocalStorageProvider().path(stored.storage_key).read_bytes() == content
        extraction = db.scalar(select(DocumentExtraction).where(DocumentExtraction.document_id == doc["id"]))
        assert extraction.provider == "demo"
        assert db.scalar(select(func.count()).select_from(Quote).where(Quote.document_id == doc["id"])) == 1
    assert doc["quote_id"] in [
        q["id"] for q in response_json(clients["buyer"].get(f"/rfqs/{RFQ}/comparison"))["quotes"]
    ]


@pytest.mark.parametrize(
    "name,mime", [("Scanned_Vertex_RFQ1004.png", "image/png"), ("Scanned_Vertex_RFQ1004.pdf", "application/pdf")]
)
def test_tesseract_image_and_scanned_pdf(clients, name, mime):
    content = (DEMO_PATH / "quotes" / name).read_bytes()
    doc = upload(clients["buyer"], name, content, mime)
    assert doc["stage"] == "Complete", doc
    assert "OCR" in doc["raw_text"] and "Vertex" in doc["raw_text"] and "AX-100" in doc["raw_text"]
    assert doc["quote_id"]


def test_unknown_pdf_no_fabrication_retry_and_filename(clients):
    doc = upload(clients["buyer"], "../../unknown-" + uuid.uuid4().hex + ".pdf", synthetic_pdf(), "application/pdf")
    assert doc["status"] == "Needs Review" and doc["stage"] == "Review Required"
    assert not doc["quote_id"] and "no extraction fixture" in doc["error"]
    assert "Synthetic unknown" in doc["raw_text"]
    assert "/" not in doc["filename"] and "\\" not in doc["filename"]
    response_json(clients["buyer"].post(f"/documents/{doc['id']}/retry"), 202)
    retried = wait_document(clients["buyer"], doc["id"])
    assert retried["status"] == "Needs Review" and not retried["quote_id"]


def test_corrupt_parser_failure_reaches_review(clients):
    doc = upload(clients["buyer"], "corrupt.pdf", b"%PDF-1.7\n" + uuid.uuid4().hex.encode(), "application/pdf")
    assert doc["status"] == "Needs Review" and doc["error"] and not doc["quote_id"]


def test_rq_timeout_callback_and_recovery(clients):
    doc = upload(clients["buyer"], "timeout-probe.pdf", synthetic_pdf(), "application/pdf")
    with SessionLocal() as db:
        row = db.get(Document, doc["id"])
        org = row.organization_id
        row.status, row.stage = "New", "Queued"
        db.commit()
    queue = Queue("documents", connection=Redis.from_url(REDIS_URL))
    job = queue.enqueue(timeout_document_job, doc["id"], org, job_timeout=1, on_failure=Callback(job_failed))
    failed = wait_document(clients["buyer"], doc["id"])
    assert failed["status"] == "Error" and failed["stage"] == "Worker failed", failed
    deadline = time.monotonic() + 10
    while not Job.fetch(job.id, connection=queue.connection).is_failed and time.monotonic() < deadline:
        time.sleep(0.1)
    assert Job.fetch(job.id, connection=queue.connection).is_failed
    response_json(clients["buyer"].post(f"/documents/{doc['id']}/retry"), 202)
    assert wait_document(clients["buyer"], doc["id"])["stage"] == "Review Required"


def test_roles_sessions_and_tenant_isolation(clients):
    buyer, viewer, isolated = (clients[k] for k in ("buyer", "viewer", "isolated"))
    assert response_json(buyer.get("/auth/me"))["role"] == "Buyer"
    assert buyer.get("/users").status_code == 403
    assert clients["admin"].get("/users").status_code == 200
    assert viewer.post(f"/rfqs/{RFQ}/recommendation").status_code == 403
    assert (
        viewer.post("/quotes/paste", json={"subject": "Denied", "text": "Not permitted to upload this."}).status_code
        == 403
    )
    quote = response_json(buyer.get(f"/rfqs/{RFQ}/comparison"))["quotes"][0]
    q = response_json(buyer.get(f"/quotes/{quote['id']}"))
    for route in [
        f"/rfqs/{RFQ}",
        f"/quotes/{q['id']}",
        f"/documents/{q['document_id']}",
        f"/documents/{q['document_id']}/file",
        f"/suppliers/{q['supplier_id']}",
        f"/items/{q['line_items'][0]['item_id']}",
    ]:
        assert isolated.get(route).status_code == 404, route
    for route in ["/suppliers", "/items", "/rfqs", "/quotes", "/documents", "/purchase-history"]:
        assert response_json(isolated.get(route))["total"] == 0
    assert response_json(isolated.get("/audit-events", params={"search": "QUOTE_EXTRACTED"}))["total"] == 0
    assert all(
        e["organization_id"] == response_json(isolated.get("/auth/me"))["organization_id"]
        for e in response_json(isolated.get("/audit-events"))["items"]
    )


def test_concurrent_correction_stale_approval_and_decision(clients):
    buyer = clients["buyer"]
    initial = response_json(buyer.get(f"/rfqs/{RFQ}/comparison"))
    qid = initial["recommended_quote_id"]
    detail = response_json(buyer.get(f"/quotes/{qid}"))
    original = review_payload(detail)
    payload = review_payload(detail)
    relay = next(line for line in payload["line_items"] if line["manufacturer_part_number"] == "AX-100")
    relay["unit_price"] = str(Decimal(relay["unit_price"]) - Decimal("0.08"))
    stale = response_json(buyer.post(f"/rfqs/{RFQ}/recommendation"), 201)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: buyer.put(f"/quotes/{qid}/review", json=payload), range(2)))
        assert sorted(r.status_code for r in responses) == [200, 409]
        corrected = response_json(buyer.get(f"/quotes/{qid}"))
        assert Decimal(corrected["total"]) == Decimal(detail["total"]) - Decimal("400.00")
        assert corrected["source_references"] == detail["source_references"]
        assert (
            buyer.post("/approvals", json={"recommendation_id": stale["id"], "note": "Stale decision"}).status_code
            == 409
        )
        current = response_json(buyer.post(f"/rfqs/{RFQ}/recommendation"), 201)
        assert current["quote_id"] == qid
        approval = response_json(
            buyer.post(
                "/approvals", json={"recommendation_id": current["id"], "note": "Docker PostgreSQL verification"}
            ),
            201,
        )
        draft = response_json(buyer.post("/email-drafts", json={"quote_id": qid, "kind": "Negotiation"}), 201)
        edited = response_json(
            buyer.put(
                f"/email-drafts/{draft['id']}",
                json={
                    "subject": draft["subject"],
                    "body": draft["body"] + "\nReviewed internally.",
                    "status": "Approved",
                },
            )
        )
        assert edited["status"] == "Approved"
        with SessionLocal() as db:
            stored = db.get(Approval, approval["id"])
            assert stored.approved_by == response_json(buyer.get("/auth/me"))["id"]
            assert stored.created_at.astimezone(timezone.utc).tzinfo is not None
            assert db.scalar(
                select(AuditEvent).where(
                    AuditEvent.entity_id == current["id"], AuditEvent.action == "RECOMMENDATION_APPROVED"
                )
            )
    finally:
        latest = response_json(buyer.get(f"/quotes/{qid}"))
        original["version"] = latest["version"]
        response_json(buyer.put(f"/quotes/{qid}/review", json=original))


def test_purchase_history_import_atomicity(clients):
    admin = clients["admin"]
    content = (
        (DEMO_PATH / "imports" / "purchase-history.csv")
        .read_text()
        .replace("PO-IMPORT-001", "PO-VERIFY-" + uuid.uuid4().hex)
    )
    before = response_json(admin.get("/purchase-history"))["total"]

    def send():
        return admin.post("/purchase-history/import", files={"file": ("history.csv", content, "text/csv")})

    assert response_json(send(), 201)["imported"] == 1
    assert send().status_code == 409
    assert response_json(admin.get("/purchase-history"))["total"] == before + 1


def test_audit_events_and_no_processing_left(clients):
    for action in [
        "QUOTE_UPLOADED",
        "QUOTE_EXTRACTED",
        "FIELD_CORRECTED",
        "SUPPLIER_MATCHED",
        "ITEM_MATCH_CONFIRMED",
        "RECOMMENDATION_GENERATED",
        "RECOMMENDATION_APPROVED",
        "EMAIL_DRAFT_GENERATED",
    ]:
        events = response_json(clients["buyer"].get("/audit-events", params={"search": action}))
        assert events["total"] > 0 and all(e["action"] == action for e in events["items"])
    with SessionLocal() as db:
        assert (
            db.scalar(select(func.count()).select_from(Document).where(Document.status.in_(["New", "Processing"]))) == 0
        )
