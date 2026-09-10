"""python -m app.evaluation.benchmark --corpus /app/benchmark-data --output ... --limit 10"""

import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from ..document_input import prepare_document, PIPELINE_VERSION
from ..local_ai import OllamaProvider, PROMPT_VERSION, connection_status
from ..extraction_validation import validate_extraction
from .metrics import evaluate
from .report import report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--retry-unavailable",
        action="store_true",
        help="Archive infrastructure-only failures and retry them after connection recovery",
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    destination = args.output / "results.jsonl"
    if destination.exists() and not args.resume:
        raise SystemExit("Results already exist. Use --resume or choose a new output directory.")
    rows = [json.loads(line) for line in destination.read_text().splitlines()] if destination.exists() else []
    if connection_status()["ai_connection"] != "Available":
        raise SystemExit(
            "Ollama preflight failed: start the configured local model service before benchmarking. No documents attempted."
        )
    if any(
        r["metadata"].get("prompt_version") != PROMPT_VERSION
        or r["metadata"].get("pipeline_version") != PIPELINE_VERSION
        or r["metadata"].get("model", os.getenv("AI_MODEL")) != os.getenv("AI_MODEL")
        for r in rows
    ):
        raise SystemExit("Cannot mix model/prompt/pipeline versions in a resumed run.")
    if args.retry_unavailable:
        interrupted = [r for r in rows if r.get("error_type") == "MODEL_UNAVAILABLE"]
        if interrupted:
            with (args.output / "infrastructure-interruption.jsonl").open("a", encoding="utf-8") as stream:
                stream.writelines(json.dumps(r) + "\n" for r in interrupted)
            rows = [r for r in rows if r.get("error_type") != "MODEL_UNAVAILABLE"]
            destination.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
            print(f"Archived {len(interrupted)} unavailable-service attempts for explicit retry", flush=True)
    done = {r["id"] for r in rows}
    entries = json.loads((args.corpus / "manifest.json").read_text())
    current_hashes = {entry["id"]: entry["sha256"] for entry in entries}
    if any(current_hashes.get(row["id"]) != row["sha256"] for row in rows):
        raise SystemExit("Cannot resume with changed or removed corpus documents.")
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
        if error_type == "MODEL_UNAVAILABLE":
            raise SystemExit(
                "Ollama became unavailable. Stopped batch; resume with --resume --retry-unavailable after recovery."
            )
    print(json.dumps(report(rows, args.output)), flush=True)


if __name__ == "__main__":
    main()
