"""Apply documented human source review corrections to evaluation labels only.

The two demo scans omit fields their demo fixture supplies. Never reward guessing
those values in a real extraction benchmark. Original demo fixtures stay intact.
"""

import json
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "benchmark-data"
manifest_path = root / "manifest.json"
manifest = json.loads(manifest_path.read_text())
for entry in manifest:
    if entry["id"] == "demo-Scanned_Vertex_RFQ1004-pdf":
        entry["format"] = "scan.pdf"
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
audit = []
for kind in ("pdf", "png"):
    identifier = "demo-Scanned_Vertex_RFQ1004-" + kind
    path = root / "ground-truth" / (identifier + ".json")
    value = json.loads(path.read_text())
    for index, line in enumerate(value["line_items"]):
        for field in (
            "uom",
            "lead_time_days",
            "lead_time_min",
            "delivery_date",
            "description",
            "manufacturer_part_number",
        ):
            original = line.get(field)
            if original is not None:
                audit.append(
                    {
                        "document_id": identifier,
                        "field": f"line_items.{index}.{field}",
                        "original_demo_label": original,
                        "evaluation_label": None,
                        "reason": "Not printed anywhere in the scan, verified against rendered source. Demo fixture includes additional assumed information.",
                    }
                )
                line[field] = None
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
if audit:
    (root / "label-audit.json").write_text(
        json.dumps(
            {
                "label_version": "source-audit-1",
                "corrections": audit,
                "policy": "Apply these same labels to both baseline and improved results. No model output is changed.",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
print(f"Audited {len(audit)} unsupported demo label values")
