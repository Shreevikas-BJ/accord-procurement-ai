from sqlalchemy import select
from app.models import Quote, Item
from app.seed import sid
from app.schemas import QuoteExtraction, LineItemExtraction


def review_payload(detail):
    fields = set(QuoteExtraction.model_fields) - {"line_items"}
    data = {k: detail[k] for k in fields}
    data.update(
        version=detail["version"], supplier_id=detail["supplier_id"], rfq_id=detail["rfq_id"], confirm_review=True
    )
    data["line_items"] = [
        {**{k: row[k] for k in LineItemExtraction.model_fields}, "id": row["id"], "item_id": row["item_id"]}
        for row in detail["line_items"]
    ]
    return data


def test_authentication_required(client):
    assert client.get("/dashboard").status_code == 401
    assert client.post("/auth/login", json={"email": "buyer@apex.example", "password": "incorrect"}).status_code == 401


def test_session_cookie_and_logout(buyer):
    assert "procurement_session" in buyer.cookies
    assert buyer.get("/auth/me").json()["role"] == "Buyer"
    assert buyer.post("/auth/logout").status_code == 200
    assert buyer.get("/dashboard").status_code == 401


def test_viewer_write_prohibited(client):
    client.post("/auth/login", json={"email": "viewer@apex.example", "password": "Demo2026!accord"})
    assert client.post(f"/rfqs/{sid('rfq-3')}/recommendation").status_code == 403
    assert client.post("/quotes/paste", json={"subject": "a", "text": "Supplier quotation " * 4}).status_code == 403


def test_tenant_isolation_for_all_business_surfaces(client, db):
    quote = db.scalar(select(Quote).where(Quote.rfq_id == sid("rfq-3")))
    client.post("/auth/login", json={"email": "viewer@isolated.example", "password": "Demo2026!accord"})
    for path in [
        f"/rfqs/{sid('rfq-3')}",
        f"/quotes/{quote.id}",
        f"/documents/{quote.document_id}",
        f"/documents/{quote.document_id}/file",
        f"/suppliers/{sid('supplier-0')}",
        f"/items/{sid('item-0')}",
    ]:
        assert client.get(path).status_code == 404
    for path in ["/suppliers", "/items", "/rfqs", "/purchase-history", "/quotes", "/documents", "/alerts"]:
        assert client.get(path).json()["total"] == 0


def test_foreign_item_in_review_rejected(buyer, db):
    db.add(
        Item(
            id=sid("foreign-item"),
            organization_id=sid("other-org"),
            sku="SECRET",
            manufacturer_part_number="SECRET",
            description="Foreign item",
            category="Private",
        )
    )
    db.commit()
    q = db.scalar(select(Quote).where(Quote.rfq_id == sid("rfq-3")))
    payload = review_payload(buyer.get(f"/quotes/{q.id}").json())
    payload["line_items"][0]["item_id"] = sid("foreign-item")
    assert buyer.put(f"/quotes/{q.id}/review", json=payload).status_code == 404


def test_review_recalculates_ranking_and_invalidates_snapshot(buyer, db):
    rfq = sid("rfq-3")
    original = buyer.get(f"/rfqs/{rfq}/comparison").json()
    qid = original["recommended_quote_id"]
    recommendation = buyer.post(f"/rfqs/{rfq}/recommendation").json()
    detail = buyer.get(f"/quotes/{qid}").json()
    payload = review_payload(detail)
    line = next(row for row in payload["line_items"] if row["manufacturer_part_number"] == "AX-100")
    line["unit_price"] = "20.00"
    response = buyer.put(f"/quotes/{qid}/review", json=payload)
    assert response.status_code == 200, response.text
    updated = buyer.get(f"/rfqs/{rfq}/comparison").json()
    quote = next(q for q in updated["quotes"] if q["id"] == qid)
    assert quote["total"] == "196580.00"
    assert updated["recommended_quote_id"] != qid
    assert (
        buyer.post(
            "/approvals", json={"recommendation_id": recommendation["id"], "note": "Reviewed details"}
        ).status_code
        == 409
    )
    assert buyer.put(f"/quotes/{qid}/review", json=payload).status_code == 409
    assert buyer.get("/audit-events?search=FIELD_CORRECTED").json()["total"] > 0


def test_approval_requires_review_and_records_actor(buyer, db):
    rfq = sid("rfq-3")
    rec = buyer.post(f"/rfqs/{rfq}/recommendation").json()
    assert buyer.post("/approvals", json={"recommendation_id": rec["id"], "note": "Reviewed"}).status_code == 409
    q = buyer.get(f"/quotes/{rec['quote_id']}").json()
    assert buyer.put(f"/quotes/{q['id']}/review", json=review_payload(q)).status_code == 200
    rec = buyer.post(f"/rfqs/{rfq}/recommendation").json()
    result = buyer.post("/approvals", json={"recommendation_id": rec["id"], "note": "Reviewed source and costs."})
    assert result.status_code == 201, result.text
    assert result.json()["approved_by"] == sid("Buyer")
    assert buyer.post("/approvals", json={"recommendation_id": rec["id"], "note": "Again"}).status_code == 409
    events = buyer.get("/audit-events?search=RECOMMENDATION_APPROVED").json()["items"]
    assert len(events) == 1 and events[0]["user_id"] == sid("Buyer")


def test_draft_generation_is_persisted_and_never_sends(buyer):
    rfq = buyer.get(f"/rfqs/{sid('rfq-3')}/comparison").json()
    response = buyer.post("/email-drafts", json={"quote_id": rfq["recommended_quote_id"], "kind": "Negotiation"})
    assert response.status_code == 201
    row = response.json()
    assert "does not constitute an order" in row["body"] and row["status"] == "Draft"
    assert (
        buyer.put(
            f"/email-drafts/{row['id']}",
            json={"subject": row["subject"], "body": "Please confirm delivery availability.", "status": "Approved"},
        ).status_code
        == 200
    )
    assert buyer.get("/email-drafts").json()[0]["status"] == "Approved"


def test_scoring_permissions_and_validation(buyer, client):
    assert buyer.put("/settings/scoring", json={}).status_code == 403
    buyer.post("/auth/login", json={"email": "admin@apex.example", "password": "Demo2026!accord"})
    data = {
        "organization_name": "Apex",
        "currency": "USD",
        "price_weight": 60,
        "lead_time_weight": 25,
        "reliability_weight": 15,
        "fit_weight": 10,
        "anomaly_threshold": ".1",
    }
    assert buyer.put("/settings/scoring", json=data).status_code == 422
    data["price_weight"] = 50
    assert buyer.put("/settings/scoring", json=data).status_code == 200


def test_csrf_header_and_origin(buyer):
    assert buyer.post("/auth/logout", headers={"X-Procurement-Client": ""}).status_code == 403
    assert buyer.post("/auth/logout", headers={"Origin": "https://evil.example"}).status_code == 403


def test_search_and_pagination(buyer):
    assert buyer.get("/suppliers?search=Meridian").json()["total"] == 1
    assert buyer.get("/items?limit=20&page=2").json()["page"] == 2
    assert buyer.get("/items?limit=99999").status_code == 422
    assert buyer.get("/items?search=%27%20OR%201%3D1--").status_code == 200
