"""Emit stable JSON from Docling without exposing its objects downstream."""

import json
import argparse
import time
from importlib.metadata import version

from docling.document_converter import DocumentConverter


parser = argparse.ArgumentParser()
parser.add_argument("paths", nargs="+")
parser.add_argument("--output")
args = parser.parse_args()
converter = DocumentConverter()
documents = []
for path in args.paths:
    started = time.monotonic()
    document = converter.convert(path).document
    tables = []
    for table_index, table in enumerate(document.tables, 1):
        exported = table.export_to_dataframe()
        rows = [[str(value) for value in exported.columns]]
        rows.extend([[None if value is None else str(value) for value in row] for row in exported.itertuples(index=False, name=None)])
        prov = table.prov[0] if table.prov else None
        tables.append({"table": table_index, "page": prov.page_no if prov else None, "bbox": list(prov.bbox.as_tuple()) if prov and prov.bbox else None, "rows": rows})
    documents.append(
        {
            "path": path,
            "provider": "docling",
            "version": version("docling"),
            "seconds": round(time.monotonic() - started, 4),
            "text": document.export_to_text(),
            "tables": tables,
        }
    )
payload = json.dumps({"documents": documents}, ensure_ascii=False)
if args.output:
    with open(args.output, "w", encoding="utf-8") as stream:
        stream.write(payload)
else:
    print(payload)
