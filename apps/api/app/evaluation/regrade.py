"""Re-score saved responses against audited source labels without any inference."""

import argparse
import json
from pathlib import Path
from .metrics import evaluate
from .report import report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    path = args.output / "results.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    manifest = {entry["id"]: entry for entry in json.loads((args.corpus / "manifest.json").read_text())}
    original = args.output / "results.original-labels.jsonl"
    if not original.exists():
        original.write_bytes(path.read_bytes())
    for row in rows:
        expected = json.loads((args.corpus / row["truth"]).read_text())
        row["metrics"] = evaluate(expected, row["extracted"], row["id"])
        row["label_version"] = "source-audit-1"
        row["format"] = manifest[row["id"]]["format"]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    print(json.dumps(report(rows, args.output)))


if __name__ == "__main__":
    main()
