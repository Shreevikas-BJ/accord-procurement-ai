"""Run Qwen on stable external-parser output; ground truth opens after inference."""

import argparse
import hashlib
import json
import statistics
import time
from pathlib import Path

from app.document_input import DocumentInput
from app.document_structure import rows_from_external
from app.evaluation.metrics import evaluate
from app.extraction_validation import validate_extraction
from app.local_ai import OllamaProvider


parser = argparse.ArgumentParser()
parser.add_argument("--subset", required=True)
parser.add_argument("--input", required=True)
parser.add_argument("--output", required=True)
args = parser.parse_args()
subset_path = Path(args.subset)
root = subset_path.parent
subset = {Path(item["path"]).name: item for item in json.loads(subset_path.read_text(encoding="utf-8"))}
records = json.loads(Path(args.input).read_text(encoding="utf-8"))["documents"]
results = []
for record in records:
    item = subset[Path(record["path"]).name]
    rows = rows_from_external(record, source_type=record["provider"])
    if record.get("text"):
        text = record["text"]
    else:
        text = "\n".join(
            [block.get("block_content", "") for page in record.get("pages", []) for block in page.get("blocks", [])]
            + [value for page in record.get("pages", []) for value in page.get("ocr_text", [])]
        )
    document = DocumentInput(text=text, pages={1: text}, structured_rows=rows, metadata={"parser": record["provider"], "parser_quality": "normal"})
    provider = OllamaProvider()
    started = time.monotonic()
    diagnostics = {}
    try:
        extracted = provider.extract(text, hashlib.sha256(text.encode()).hexdigest(), document)
        diagnostics = validate_extraction(extracted, document)
        payload = extracted.model_dump(mode="json")
        success = True
    except Exception as error:
        payload = None
        success = False
        diagnostics = {"error_type": str(error).split(":", 1)[0]}
    expected = json.loads((root / item["truth"]).read_text(encoding="utf-8"))
    metrics = evaluate(expected, payload, item["id"])
    results.append({"id": item["id"], "format": item["format"], "success": success, "seconds": round(time.monotonic()-started, 3), "metrics": metrics, "diagnostics": diagnostics})
    print(json.dumps({"id": item["id"], "errors": len(metrics["errors"])}), flush=True)
critical_correct = sum(result["metrics"]["critical_correct"] for result in results)
critical_total = sum(result["metrics"]["critical_total"] for result in results)
association_correct = sum(result["metrics"]["association_correct"] for result in results)
association_total = sum(result["metrics"]["association_total"] for result in results)
summary = {
    "provider": records[0]["provider"] if records else None,
    "documents": len(results),
    "critical_accuracy_percent": round(critical_correct/max(critical_total,1)*100, 3),
    "line_association_accuracy_percent": round(association_correct/max(association_total,1)*100, 3),
    "processing_success_percent": round(sum(result["success"] for result in results)/max(len(results),1)*100, 3),
    "median_model_validation_seconds": round(statistics.median(result["seconds"] for result in results),3),
    "results": results,
}
Path(args.output).write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
