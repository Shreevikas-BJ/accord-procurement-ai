from pathlib import Path

from app.document_structure import (
    DoclingStructureProvider,
    PaddleStructureProvider,
    StructureQuality,
    canonical_from_rows,
    choose_structure,
    normalize_ocr_token,
)


def strong_rows():
    return [
        {
            "page": 1,
            "table": 1,
            "row": 1,
            "cells": ["Part No", "Qty", "UOM", "Unit Price", "Extended"],
            "headers": ["Part No", "Qty", "UOM", "Unit Price", "Extended"],
            "semantic_headers": ["supplier_sku", "quantity", "uom", "unit_price", "stated_line_total"],
            "raw_text": "Part No | Qty | UOM | Unit Price | Extended",
        },
        {
            "page": 1,
            "table": 1,
            "row": 2,
            "cells": ["AX-100", "500", "EA", "4.72", "2360"],
            "semantic_headers": ["supplier_sku", "quantity", "uom", "unit_price", "stated_line_total"],
            "raw_text": "AX-100 | 500 | EA | 4.72 | 2360",
        },
    ]


def test_canonical_representation_preserves_rows_cells_and_provenance():
    document = canonical_from_rows(Path("quote.pdf"), strong_rows(), parser_name="pdfplumber", parser_version="0.11.10")
    assert document.tables[0].rows[1].cells[0].value == "AX-100"
    assert document.tables[0].rows[1].source_reference == "page:1:row:2"
    assert document.assessment.state == StructureQuality.STRONG


def test_structure_quality_has_weak_and_none_states():
    weak = canonical_from_rows(
        Path("quote.pdf"),
        [{"page": 1, "table": 1, "row": 1, "cells": ["misc", "text"], "raw_text": "misc text"}],
        parser_name="docling",
        parser_version="test",
    )
    empty = canonical_from_rows(Path("quote.pdf"), [], parser_name="docling", parser_version="test")
    assert weak.assessment.state == StructureQuality.WEAK
    assert empty.assessment.state == StructureQuality.NONE


def test_routing_selects_strong_primary_and_falls_back_from_weak():
    current = canonical_from_rows(Path("quote.pdf"), strong_rows(), parser_name="pdfplumber", parser_version="test")
    weak = canonical_from_rows(Path("quote.pdf"), [], parser_name="docling", parser_version="test")
    assert choose_structure(current, weak)[1] == "pdfplumber"
    selected, route = choose_structure(weak, current)
    assert selected is current and route == "pdfplumber_fallback"


def test_ocr_normalization_repairs_spacing_without_inventing_decimals():
    assert normalize_ocr_token("AX - 100")[0] == "AX-100"
    assert normalize_ocr_token("6 . 10")[0] == "6.10"
    assert normalize_ocr_token("1 , 000")[0] == "1,000"
    assert normalize_ocr_token("61") == ("61", ["DECIMAL_SUSPECT"])


def test_docling_successful_multi_row_table_and_repeated_sku():
    payload = {"tables": [{"page": 1, "rows": [["SKU", "Qty", "UOM", "Unit price"], ["AX-100", "10", "EA", "4.72"], ["AX-100", "20", "EA", "4.50"]]}]}
    document = DoclingStructureProvider(lambda _: payload).parse(Path("quote.pdf"))
    assert [row.cells[0].value for row in document.tables[0].rows[1:]] == ["AX-100", "AX-100"]
    assert document.assessment.state == StructureQuality.STRONG


def test_paddle_table_and_image_output_converts_to_same_schema():
    payload = {"pages": [{"tables": [{"bbox": [1, 2, 3, 4], "rows": [["Part No", "Qty", "UOM", "Net Ea"], ["NC/H01-1", "1,000", "EA", "6.10"]]}]}]}
    document = PaddleStructureProvider(lambda _: payload).parse(Path("scan.png"))
    row = document.tables[0].rows[1]
    assert row.cells[0].value == "NC/H01-1" and row.cells[3].value == "6.10"
    assert row.bbox == [1, 2, 3, 4]
