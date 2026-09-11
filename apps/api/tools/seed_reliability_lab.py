"""Isolated fictional catalog for fresh Phase 2.5 UI verification; no quote fixtures."""

from tools.seed_evaluation_lab import main, CASES

if __name__ == "__main__":
    main(
        [*CASES, "reliability-013-missing_quantity", "reliability-006-injection"],
        namespace="reliability",
        name="Accord Reliability Lab",
        email="buyer@reliability.example",
    )
