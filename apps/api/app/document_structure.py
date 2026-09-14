"""Canonical, provider-neutral document structure for local extraction.

Heavy optional parsers are imported only by their adapters. Procurement and
evidence code consume canonical rows, never Docling or Paddle objects.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Callable, Protocol

from .structured_input import semantic_header


class StructureQuality(StrEnum):
    STRONG = "STRONG_STRUCTURE"
    WEAK = "WEAK_STRUCTURE"
    NONE = "NO_STRUCTURE"


@dataclass
class CanonicalCell:
    row: int
    column: int
    value: object = None
    normalized_value: object = None
    bbox: list[float] | None = None
    header: str | None = None
    confidence: float | None = None
    source_reference: str | None = None
    flags: list[str] = field(default_factory=list)


@dataclass
class CanonicalRow:
    row_id: str
    page: int | None
    table_id: str | None
    cells: list[CanonicalCell]
    raw_text: str
    bbox: list[float] | None = None
    confidence: float | None = None
    source_reference: str | None = None


@dataclass
class CanonicalTable:
    table_id: str
    page: int | None
    bbox: list[float] | None
    headers: list[str]
    rows: list[CanonicalRow]
    confidence: float | None = None


@dataclass
class CanonicalBlock:
    block_id: str
    page: int
    text: str
    bbox: list[float] | None = None
    kind: str = "text"
    confidence: float | None = None


@dataclass
class CanonicalPage:
    page_number: int
    width: float | None = None
    height: float | None = None
    blocks: list[CanonicalBlock] = field(default_factory=list)
    tables: list[CanonicalTable] = field(default_factory=list)


@dataclass
class StructureAssessment:
    state: StructureQuality
    score: float
    signals: dict[str, float | int | bool]
    reasons: list[str]


@dataclass
class CanonicalDocument:
    document_id: str
    pages: list[CanonicalPage]
    text_blocks: list[CanonicalBlock]
    tables: list[CanonicalTable]
    metadata: dict
    source_format: str
    parser_name: str
    parser_version: str
    assessment: StructureAssessment | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class DocumentStructureProvider(Protocol):
    name: str
    version: str

    def parse(self, path: Path, *, pages: list[int] | None = None) -> CanonicalDocument: ...


def normalize_ocr_token(value: object) -> tuple[object, list[str]]:
    """Repair spacing only; retain ambiguous digits and flag decimal suspects."""
    if not isinstance(value, str):
        return value, []
    normalized = re.sub(r"(?<=\w)\s*[-/]\s*(?=\w)", lambda m: m.group().strip(), value)
    normalized = re.sub(r"(?<=\d)\s*([.,])\s*(?=\d)", r"\1", normalized)
    flags: list[str] = []
    if re.fullmatch(r"\d{2,3}", normalized.strip()):
        flags.append("DECIMAL_SUSPECT")
    return normalized, flags


def canonical_from_rows(
    path: Path,
    rows: list[dict],
    *,
    parser_name: str,
    parser_version: str,
    source_format: str | None = None,
    page_text: dict[int, str] | None = None,
) -> CanonicalDocument:
    source_format = source_format or path.suffix.casefold().lstrip(".")
    tables: dict[tuple[int | None, object], CanonicalTable] = {}
    pages: dict[int, CanonicalPage] = {}
    blocks: list[CanonicalBlock] = []
    for page_number, text in sorted((page_text or {}).items()):
        block = CanonicalBlock(f"p{page_number}-text", page_number, text)
        blocks.append(block)
        pages.setdefault(page_number, CanonicalPage(page_number)).blocks.append(block)
    for ordinal, row in enumerate(rows, 1):
        page_number = row.get("page")
        table_number = row.get("table")
        table_id = f"p{page_number or 0}-t{table_number}" if table_number is not None else None
        headers = row.get("headers") or []
        semantic_headers = row.get("semantic_headers") or []
        raw_cells = row.get("cells") or []
        field_cells = row.get("field_cells") or {}
        cells: list[CanonicalCell] = []
        if raw_cells:
            for column, value in enumerate(raw_cells):
                normalized, flags = normalize_ocr_token(value) if "ocr" in parser_name else (value, [])
                header = semantic_headers[column] if column < len(semantic_headers) else None
                source_refs = row.get("cell_refs") or []
                cells.append(
                    CanonicalCell(
                        row=int(row.get("row") or ordinal),
                        column=column,
                        value=value,
                        normalized_value=normalized,
                        bbox=None,
                        header=header,
                        source_reference=source_refs[column] if column < len(source_refs) else None,
                        flags=flags,
                    )
                )
        elif field_cells:
            for column, (header, payload) in enumerate(field_cells.items()):
                value = payload.get("value")
                normalized, flags = normalize_ocr_token(value) if "ocr" in parser_name else (value, [])
                cells.append(
                    CanonicalCell(
                        row=int(row.get("row") or ordinal),
                        column=column,
                        value=value,
                        normalized_value=normalized,
                        bbox=payload.get("bbox"),
                        header=header,
                        source_reference=payload.get("cell"),
                        flags=flags,
                    )
                )
        canonical_row = CanonicalRow(
            row_id=f"{table_id or 'block'}-r{row.get('row') or ordinal}",
            page=page_number,
            table_id=table_id,
            cells=cells,
            raw_text=row.get("raw_text", ""),
            bbox=row.get("bbox"),
            confidence={"strong": 0.9, "weak": 0.55, "header": 0.7}.get(row.get("layout_confidence")),
            source_reference=(
                f"{row.get('sheet')}!row:{row.get('row')}" if row.get("sheet") else f"page:{page_number}:row:{row.get('row')}"
            ),
        )
        if table_id:
            key = (page_number, table_number)
            table = tables.setdefault(key, CanonicalTable(table_id, page_number, row.get("bbox"), list(headers), []))
            table.rows.append(canonical_row)
            if not table.headers and headers:
                table.headers = list(headers)
        elif page_number:
            block = CanonicalBlock(f"p{page_number}-row{ordinal}", page_number, canonical_row.raw_text, row.get("bbox"), "row")
            blocks.append(block)
            pages.setdefault(page_number, CanonicalPage(page_number)).blocks.append(block)
    for table in tables.values():
        if table.page:
            pages.setdefault(table.page, CanonicalPage(table.page)).tables.append(table)
    document = CanonicalDocument(
        document_id=path.stem,
        pages=list(sorted(pages.values(), key=lambda page: page.page_number)),
        text_blocks=blocks,
        tables=list(tables.values()),
        metadata={"row_count": len(rows)},
        source_format=source_format,
        parser_name=parser_name,
        parser_version=parser_version,
    )
    document.assessment = assess_structure(document)
    return document


def assess_structure(document: CanonicalDocument) -> StructureAssessment:
    rows = [row for table in document.tables for row in table.rows]
    data_rows = [row for row in rows if sum(cell.value not in (None, "") for cell in row.cells) >= 2]
    headers = {cell.header for row in rows for cell in row.cells if cell.header}
    consistent = 0.0
    if data_rows:
        counts = [sum(cell.value not in (None, "") for cell in row.cells) for row in data_rows]
        consistent = max(counts.count(value) for value in set(counts)) / len(counts)
    sku_tokens = sum(bool(re.search(r"[A-Z0-9]+[-/][A-Z0-9-]+", row.raw_text, re.I)) for row in data_rows)
    numeric_rows = sum(len(re.findall(r"(?<!\w)\d[\d,.]*", row.raw_text)) >= 2 for row in data_rows)
    signals: dict[str, float | int | bool] = {
        "table_count": len(document.tables),
        "data_row_count": len(data_rows),
        "procurement_header_count": len(headers & {"supplier_sku", "description", "quantity", "uom", "unit_price", "stated_line_total"}),
        "consistent_column_ratio": round(consistent, 3),
        "sku_row_count": sku_tokens,
        "numeric_row_count": numeric_rows,
    }
    score = min(1.0, 0.15 * min(len(document.tables), 1) + 0.1 * min(len(data_rows), 3) + 0.08 * min(signals["procurement_header_count"], 5) + 0.15 * consistent + 0.05 * min(sku_tokens, 2))
    reasons = []
    if not document.tables:
        reasons.append("no tables detected")
    if signals["procurement_header_count"] < 3:
        reasons.append("fewer than three procurement headers")
    if not data_rows:
        reasons.append("no multi-cell data rows")
    state = StructureQuality.STRONG if score >= 0.68 and len(data_rows) >= 1 else StructureQuality.WEAK if score >= 0.25 else StructureQuality.NONE
    return StructureAssessment(state, round(score, 3), signals, reasons)


class RowProvider:
    """Adapter for built-in parsers that already emit provenance-rich rows."""

    def __init__(self, name: str, version: str, loader: Callable):
        self.name, self.version, self.loader = name, version, loader

    def parse(self, path: Path, *, pages: list[int] | None = None) -> CanonicalDocument:
        rows = self.loader(path, pages) if pages is not None else self.loader(path)
        if isinstance(rows, tuple):
            rows = rows[0]
        return canonical_from_rows(path, rows, parser_name=self.name, parser_version=self.version)


def rows_from_external(payload: dict, *, source_type: str) -> list[dict]:
    """Convert the stable evaluator/service JSON contract into Accord rows."""
    rows: list[dict] = []
    tables = payload.get("tables", [])
    if payload.get("pages"):
        tables = [table for page in payload["pages"] for table in page.get("tables", [])]
    for table_index, table in enumerate(tables, 1):
        headers: list[str] = []
        semantic: list[str | None] = []
        for row_index, cells in enumerate(table.get("rows", []), 1):
            if row_index == 1:
                headers = [str(cell or "") for cell in cells]
                semantic = [semantic_header(cell) for cell in cells]
            field_cells = {
                key: {"value": cells[column] if column < len(cells) else None, "bbox": table.get("bbox")}
                for column, key in enumerate(semantic)
                if key and row_index > 1
            }
            rows.append(
                {
                    "source_type": source_type,
                    "page": table.get("page", 1),
                    "table": table_index,
                    "row": row_index,
                    "cells": cells,
                    "headers": headers,
                    "semantic_headers": semantic,
                    "field_cells": field_cells,
                    "raw_text": " | ".join(str(cell or "") for cell in cells),
                    "bbox": table.get("bbox"),
                    "layout_confidence": "strong" if field_cells else "header" if row_index == 1 else "weak",
                }
            )
    return rows


class ExternalStructureProvider:
    """Adapter around an isolated local worker client returning stable JSON."""

    def __init__(self, name: str, version: str, client: Callable[[Path], dict]):
        self.name, self.version, self.client = name, version, client

    def parse(self, path: Path, *, pages: list[int] | None = None) -> CanonicalDocument:
        payload = self.client(path)
        rows = rows_from_external(payload, source_type=self.name)
        document = canonical_from_rows(path, rows, parser_name=self.name, parser_version=self.version)
        document.metadata["selected_pages"] = pages
        return document


class DoclingStructureProvider(ExternalStructureProvider):
    def __init__(self, client: Callable[[Path], dict], version: str = "2.126.0"):
        super().__init__("docling", version, client)


class PaddleStructureProvider(ExternalStructureProvider):
    def __init__(self, client: Callable[[Path], dict], version: str = "3.7.0"):
        super().__init__("paddle_ppstructure_v3", version, client)


def choose_structure(primary: CanonicalDocument | None, fallback: CanonicalDocument) -> tuple[CanonicalDocument, str]:
    if primary and primary.assessment and primary.assessment.state == StructureQuality.STRONG:
        return primary, primary.parser_name
    suffix = "_fallback" if primary is not None else ""
    return fallback, f"{fallback.parser_name}{suffix}"


def parse_with_fallback(
    path: Path,
    fallback: DocumentStructureProvider,
    primary: DocumentStructureProvider | None = None,
    *,
    pages: list[int] | None = None,
) -> tuple[CanonicalDocument, str]:
    """Contain optional parser failures and always preserve a local fallback."""
    primary_document = None
    if primary:
        try:
            primary_document = primary.parse(path, pages=pages)
        except (ImportError, OSError, RuntimeError, TimeoutError, ValueError):
            primary_document = None
    fallback_document = fallback.parse(path, pages=pages)
    return choose_structure(primary_document, fallback_document)
