"""Development-only replay of saved model responses through current parsing/evidence code.

This never selects a better response and is never a release benchmark. It exists
to iterate on deterministic structure/evidence without spending another model
call; final development and holdout runs must use fresh inference.
"""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from ..document_input import PIPELINE_VERSION, prepare_document
from ..extraction_validation import validate_extraction
from ..local_ai import OllamaProvider, PROMPT_VERSION
from .metrics import evaluate
from .report import report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--source-results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("Replay output already exists; choose a new development directory.")
    args.output.mkdir(parents=True)
    source_rows = [json.loads(line) for line in (args.source_results / "results.jsonl").read_text().splitlines()]
    rows = []
    for source in source_rows:
        started = time.monotonic()
        document = prepare_document(args.corpus / source["path"])
        provider = OllamaProvider()
        provider.metadata = {
            "model": source.get("metadata", {}).get("model"),
            "prompt_version": PROMPT_VERSION,
            "pipeline_version": PIPELINE_VERSION,
            "replay_source_prompt_version": source.get("metadata", {}).get("prompt_version"),
            "replay_source_pipeline_version": source.get("metadata", {}).get("pipeline_version"),
            "development_replay": True,
            **document.metadata,
        }
        extracted = None
        error_type = None
        try:
            if not source.get("model_response"):
                raise ValueError("SOURCE_RESPONSE_MISSING")
            quote = provider.parse_response(source["model_response"], document)
            provider.metadata.update(validate_extraction(quote, document))
            extracted = quote.model_dump(mode="json")
        except Exception as error:
            error_type = str(error).split(":", 1)[0] if isinstance(error, ValueError) else type(error).__name__
        provider.metadata["total_seconds"] = round(time.monotonic() - started, 4)
        expected = json.loads((args.corpus / source["truth"]).read_text())
        row = {
            **{key: value for key, value in source.items() if key not in {"timestamp", "success", "error_type", "metadata", "extracted", "metrics"}},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "success": extracted is not None,
            "error_type": error_type,
            "metadata": provider.metadata,
            "extracted": extracted,
            "metrics": evaluate(expected, extracted, source["id"]),
        }
        rows.append(row)
    (args.output / "results.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    summary = report(rows, args.output)
    (args.output / "REPLAY_ONLY.txt").write_text(
        "Development-only deterministic replay of saved model responses. Not a fresh model or release result.\n",
        encoding="utf-8",
    )
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
