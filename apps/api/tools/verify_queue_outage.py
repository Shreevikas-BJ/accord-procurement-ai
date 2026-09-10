"""Opt-in controlled Redis outage probe. Stop Redis before 'down', restore before 'recover'."""

import json
import sys
import time
import uuid
from pathlib import Path
import httpx

STATE = Path("/tmp/accord-queue-outage.json")


def main(mode):
    with httpx.Client(base_url="http://api:8000", headers={"X-Procurement-Client": "workspace"}, timeout=30) as client:
        response = client.post("/auth/login", json={"email": "buyer@apex.example", "password": "Demo2026!accord"})
        assert response.status_code == 200, response.text
        if mode == "down":
            assert client.get("/health").status_code == 503
            response = client.post(
                "/quotes/paste",
                json={
                    "subject": "Redis outage probe",
                    "text": "Unknown synthetic quotation for recovery verification " + uuid.uuid4().hex,
                },
            )
            assert response.status_code == 202, response.text
            id = response.json()["id"]
            doc = client.get(f"/documents/{id}").json()
            assert doc["status"] == "Error" and doc["stage"] == "Queue unavailable", doc
            assert client.get(f"/documents/{id}/file").status_code == 200
            STATE.write_text(json.dumps({"id": id}))
            print(
                json.dumps(
                    {"result": "PASS", "health": 503, "document": id, "stage": doc["stage"], "source_saved": True}
                )
            )
        elif mode == "recover":
            assert client.get("/health").status_code == 200
            id = json.loads(STATE.read_text())["id"]
            assert client.post(f"/documents/{id}/retry").status_code == 202
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                doc = client.get(f"/documents/{id}").json()
                if doc["status"] not in ("New", "Processing"):
                    break
                time.sleep(0.2)
            assert doc["status"] == "Needs Review" and doc["stage"] == "Review Required" and not doc["quote_id"], doc
            print(
                json.dumps(
                    {
                        "result": "PASS",
                        "health": 200,
                        "document": id,
                        "retry_processed": True,
                        "fabricated_quote": False,
                    }
                )
            )
        else:
            raise ValueError("Expected down or recover")


if __name__ == "__main__":
    main(sys.argv[1])
