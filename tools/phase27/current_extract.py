"""Collect canonical output from Accord's current parsers for the parser matrix."""

import argparse
import json
import time
from pathlib import Path

from app.document_input import prepare_document


parser = argparse.ArgumentParser()
parser.add_argument("paths", nargs="+")
parser.add_argument("--output", required=True)
args = parser.parse_args()
documents = []
for raw_path in args.paths:
    started = time.monotonic()
    document = prepare_document(Path(raw_path))
    canonical = document.canonical_document.to_dict() if document.canonical_document else None
    documents.append(
        {
            "path": raw_path,
            "provider": document.metadata.get("parser"),
            "version": document.metadata.get("parser_version"),
            "seconds": round(time.monotonic() - started, 4),
            "text": document.text,
            "canonical": canonical,
        }
    )
Path(args.output).write_text(json.dumps({"documents": documents}, ensure_ascii=False, default=str), encoding="utf-8")
