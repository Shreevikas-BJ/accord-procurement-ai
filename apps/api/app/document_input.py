"""Bounded, page-aware input preparation. Never consults benchmark labels."""

import base64
import io
import json
import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image
from pypdf import PdfReader

PIPELINE_VERSION = "local-2.7.0"


def layout_ocr(path):
    """Keep table rows/columns together; the original OCR words remain evidence."""
    import pytesseract

    with Image.open(path) as image:
        if image.width * image.height > 40_000_000:
            raise ValueError("Image exceeds 40 megapixels.")
        return pytesseract.image_to_string(image, config="--psm 6 -c preserve_interword_spaces=1", timeout=45)


@dataclass
class DocumentInput:
    text: str
    images: list[str] = field(default_factory=list)
    image_pages: list[int] = field(default_factory=list)
    pages: dict[int, str] = field(default_factory=dict)
    structured_rows: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    canonical_document: object | None = None


def image_data(path):
    with Image.open(path) as source:
        if source.width * source.height > 40_000_000:
            raise ValueError("Image exceeds 40 megapixels.")
        source = source.convert("RGB")
        source.thumbnail((1600, 1600))
        stream = io.BytesIO()
        source.save(stream, format="PNG")
        return base64.b64encode(stream.getvalue()).decode()


def prepare_document(path: Path) -> DocumentInput:
    from .providers import parser_for, TesseractOCRProvider

    started = time.monotonic()
    result = DocumentInput("")
    ocr_seconds = 0.0
    limit = max(1, min(4, int(os.getenv("AI_MAX_PAGES", "3"))))
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        from .structured_input import ocr_candidates, pdf_candidates

        reader = PdfReader(path)
        if reader.is_encrypted or len(reader.pages) > 50:
            raise ValueError("Use an unlocked PDF with at most 50 pages.")
        pages = {i + 1: p.extract_text(extraction_mode="layout") or "" for i, p in enumerate(reader.pages)}
        selection_text = dict(pages)
        if len(pages) > limit and sum(len(p.strip()) < 80 for p in pages.values()) > limit:
            selection_started = time.monotonic()
            with tempfile.TemporaryDirectory() as temporary:
                prefix = Path(temporary) / "thumb"
                subprocess.run(
                    ["pdftoppm", "-png", "-scale-to", "700", str(path), str(prefix)],
                    check=True,
                    capture_output=True,
                    timeout=90,
                )
                for thumbnail in sorted(Path(temporary).glob("thumb-*.png")):
                    number = int(thumbnail.stem.rsplit("-", 1)[1])
                    if time.monotonic() - selection_started > 60:
                        result.metadata["page_selection_incomplete"] = True
                        break
                    if len(pages[number].strip()) < 80:
                        selection_text[number] = TesseractOCRProvider().extract(thumbnail)
            selection_seconds = time.monotonic() - selection_started
            ocr_seconds += selection_seconds
            result.metadata["page_selection_ocr_seconds"] = round(selection_seconds, 4)

        # Always retain identity on page one; rank remaining pages by commercial signals.
        def score(number):
            return len(
                re.findall(
                    r"quote|quotation|unit price|quantity|sku|moq|delivery|subtotal|total|pricing",
                    selection_text[number],
                    re.I,
                )
            )

        selected = (
            sorted({1, *sorted(range(2, len(pages) + 1), key=lambda n: (-score(n), n))[: limit - 1]}) if pages else []
        )
        result.metadata.update(
            page_count=len(pages), selected_pages=selected, omitted_pages=sorted(set(pages) - set(selected))
        )
        # Digital PDF words/tables are retained even when table detection is weak.
        result.structured_rows.extend(pdf_candidates(path, selected))
        for number in selected:
            content = pages[number]
            if len(content.strip()) < 80:
                with tempfile.TemporaryDirectory() as temporary:
                    prefix = Path(temporary) / "page"
                    subprocess.run(
                        [
                            "pdftoppm",
                            "-f",
                            str(number),
                            "-l",
                            str(number),
                            "-singlefile",
                            "-png",
                            "-scale-to",
                            "1600",
                            str(path),
                            str(prefix),
                        ],
                        check=True,
                        capture_output=True,
                        timeout=45,
                    )
                    image_path = prefix.with_suffix(".png")
                    t = time.monotonic()
                    content = layout_ocr(image_path)
                    ocr_seconds += time.monotonic() - t
                    result.structured_rows.extend(ocr_candidates(image_path, number))
                    result.images.append(image_data(image_path))
                    result.image_pages.append(number)
            result.pages[number] = content
        result.text = "\n".join(f"[Page {n}]\n{p}" for n, p in result.pages.items())
        from .document_structure import canonical_from_rows

        result.canonical_document = canonical_from_rows(
            path,
            result.structured_rows,
            parser_name="pdfplumber",
            parser_version="0.11.10",
            source_format="scan.pdf" if any(len(p.strip()) < 80 for p in pages.values()) else "pdf",
            page_text=result.pages,
        )
    elif suffix in (".png", ".jpg", ".jpeg"):
        from .structured_input import ocr_candidates

        result.images = [image_data(path)]
        result.image_pages = [1]
        t = time.monotonic()
        try:
            content = layout_ocr(path)
            result.structured_rows = ocr_candidates(path)
        except (RuntimeError, subprocess.TimeoutExpired):
            content = ""
        ocr_seconds = time.monotonic() - t
        result.pages = {1: content}
        result.text = "[Page 1]\n" + content
        from .document_structure import canonical_from_rows

        result.canonical_document = canonical_from_rows(
            path, result.structured_rows, parser_name="tesseract_ocr", parser_version="5.x", page_text=result.pages
        )
    elif suffix in (".xlsx", ".csv"):
        from .structured_input import spreadsheet_candidates

        # Existing parsers enforce ZIP expansion and row limits first.
        parser_for(path.name).parse(path)
        result.structured_rows, spreadsheet_metadata = spreadsheet_candidates(path)
        result.metadata.update(spreadsheet_metadata)
        chunks = [json.dumps(row, ensure_ascii=False, default=str) for row in result.structured_rows]
        result.text = "Structured spreadsheet rows; empty cells are missing values.\n" + "\n".join(chunks)
        from .document_structure import canonical_from_rows

        result.canonical_document = canonical_from_rows(
            path,
            result.structured_rows,
            parser_name="openpyxl" if suffix == ".xlsx" else "python_csv",
            parser_version="3.1.5" if suffix == ".xlsx" else "3.12",
        )
    else:
        result.text = parser_for(path.name).parse(path)
    # Reject oversize input rather than silently extract a truncated quotation.
    if len(result.text) > 18000:
        raise ValueError(
            "Selected quotation text exceeds the local context budget. Split the quote into smaller documents."
        )
    result.metadata.update(
        pipeline_version=PIPELINE_VERSION,
        parsing_seconds=round(time.monotonic() - started - ocr_seconds, 4),
        ocr_seconds=round(ocr_seconds, 4),
        input_characters=len(result.text),
        image_count=len(result.images),
        image_pages=result.image_pages,
        structured_candidate_count=len(result.structured_rows),
        structured_source_types=sorted({row.get("source_type") for row in result.structured_rows if row.get("source_type")}),
        parser_quality="low" if len(result.text.strip()) < 80 else "normal",
    )
    if result.canonical_document:
        assessment = result.canonical_document.assessment
        result.metadata.update(
            parser=result.canonical_document.parser_name,
            parser_version=result.canonical_document.parser_version,
            structure_quality=assessment.state.value,
            structure_quality_score=assessment.score,
            structure_quality_signals=assessment.signals,
        )
    return result
