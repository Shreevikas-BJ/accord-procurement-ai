from app.document_input import prepare_document
from app.structured_input import compact_candidates, word_rows


def test_alternate_csv_headers_map_to_exact_cells(tmp_path):
    path = tmp_path / "offer.csv"
    path.write_text(
        "Vendor part no.,Description,Order quantity,UOM,Price per unit,Line total,Minimum order quantity\n"
        "AX-100,Relay,500,EA,4.72,2360,100\n",
        encoding="utf-8",
    )
    document = prepare_document(path)
    row = document.structured_rows[1]
    assert row["field_cells"]["supplier_sku"] == {"value": "AX-100", "cell": "CSV!A2"}
    assert row["field_cells"]["quantity"]["cell"] == "CSV!C2"
    assert row["field_cells"]["unit_price"]["value"] == "4.72"


def test_geometric_rows_preserve_blank_leading_sku():
    words = []
    for index, (text, x) in enumerate(
        [("SKU", 10), ("Description", 80), ("Qty", 240), ("UOM", 300), ("Unit", 360), ("price", 395)]
    ):
        words.append({"text": text, "x0": x, "x1": x + 25, "top": 10, "bottom": 20, "line_key": (1, 1, 1)})
    for text, x in [("Packing sleeve", 80), ("513", 240), ("PCS", 300), ("12.56", 370)]:
        words.append({"text": text, "x0": x, "x1": x + 35, "top": 30, "bottom": 40, "line_key": (1, 1, 2)})
    rows = word_rows(words, source_type="ocr_layout", page=1)
    data = rows[1]["field_cells"]
    assert data["supplier_sku"]["value"] is None
    assert data["quantity"]["value"] == "513"
    assert data["unit_price"]["value"] == "12.56"


def test_model_ocr_candidates_omit_duplicate_unmapped_lines_and_raw_cells():
    rows = [
        {"source_type": "ocr_layout", "row": 1, "raw_text": "Supplier: Example", "layout_confidence": "unmapped"},
        {
            "source_type": "ocr_layout",
            "row": 2,
            "raw_text": "SKU Qty Unit price",
            "cells": ["SKU", "Qty", "Unit", "price"],
            "layout_confidence": "header",
        },
        {
            "source_type": "ocr_layout",
            "row": 3,
            "raw_text": "AX-1 100 4.72",
            "cells": ["AX-1", "100", "4.72"],
            "field_cells": {"supplier_sku": {"value": "AX-1"}, "quantity": {"value": "100"}},
            "layout_confidence": "strong",
        },
    ]
    compact = compact_candidates(rows)
    assert [row["row"] for row in compact] == [2, 3]
    assert compact[0]["cells"] == ["SKU", "Qty", "Unit", "price"]
    assert "cells" not in compact[1]
