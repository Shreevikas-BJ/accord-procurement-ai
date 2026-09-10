"""python -m app.evaluation.benchmark --corpus /app/benchmark-data --output ... --limit 10"""

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from ..document_input import prepare_document, PIPELINE_VERSION
from ..local_ai import OllamaProvider, PROMPT_VERSION
from ..extraction_validation import validate_extraction
from .metrics import evaluate
from .report import report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    destination = args.output / "results.jsonl"
    if destination.exists() and not args.resume:
        raise SystemExit("Results already exist. Use --resume or choose a new output directory.")
    rows = [json.loads(line) for line in destination.read_text().splitlines()] if destination.exists() else []
    if any(
        r["metadata"].get("prompt_version") != PROMPT_VERSION
        or r["metadata"].get("pipeline_version") != PIPELINE_VERSION
        for r in rows
    ):
        raise SystemExit("Cannot mix prompt/pipeline versions in a resumed run.")
    done = {r["id"] for r in rows}
    entries = json.loads((args.corpus / "manifest.json").read_text())
    if args.limit:
        entries = entries[: args.limit]
    for entry in entries:
        if entry["id"] in done:
            continue
        path = (args.corpus / entry["path"]).resolve()
        if (
            not path.is_relative_to(args.corpus.resolve())
            or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]
        ):
            raise SystemExit("Corpus document hash/path mismatch")
        started = time.monotonic()
        provider = OllamaProvider()
        metadata = {"prompt_version": PROMPT_VERSION, "pipeline_version": PIPELINE_VERSION}
        extracted = None
        error_type = None
        try:
            document = prepare_document(path)
            metadata.update(document.metadata)
            extracted = provider.extract(document.text, document_input=document)
            metadata.update(provider.metadata)
            metadata.update(validate_extraction(extracted, document))
            extracted = extracted.model_dump(mode="json")
        except Exception as error:
            metadata.update(provider.metadata)
            error_type = str(error).split(":", 1)[0] if isinstance(error, ValueError) else type(error).__name__
        metadata["total_seconds"] = round(time.monotonic() - started, 4)
        # Ground truth is opened only AFTER inference; never sent to the provider.
        expected = json.loads((args.corpus / entry["truth"]).read_text())
        row = {
            **entry,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "success": extracted is not None,
            "error_type": error_type,
            "metadata": metadata,
            "extracted": extracted,
            "model_response": provider.raw_response,
            "metrics": evaluate(expected, extracted, entry["id"]),
        }
        with destination.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row) + "\n")
        rows.append(row)
        report(rows, args.output)
        print(
            json.dumps(
                {
                    "completed": len(rows),
                    "id": entry["id"],
                    "success": row["success"],
                    "errors": len(row["metrics"]["errors"]),
                    "seconds": metadata["total_seconds"],
                }
            ),
            flush=True,
        )
    print(json.dumps(report(rows, args.output)), flush=True)


if __name__ == "__main__":
    main()
