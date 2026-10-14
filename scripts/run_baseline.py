"""Score the keyword baseline on a CUAD split.

    python scripts/run_baseline.py --split dev
"""

import argparse
import time
from datetime import datetime
from pathlib import Path

from docintel import baseline
from docintel.cuad import load_cuad
from docintel.evaluate import format_table, save_run, score_contract

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test"], default="dev")
    args = ap.parse_args()

    contracts = load_cuad(split=args.split)
    start = time.perf_counter()
    scores = [s for c in contracts for s in score_contract(baseline.extract(c.text), c)]
    elapsed = time.perf_counter() - start

    run_dir = ROOT / "runs" / f"{datetime.now():%Y%m%d-%H%M%S}-baseline-{args.split}"
    summary = save_run(run_dir, scores, {
        "system": "keyword-baseline", "split": args.split, "contracts": len(contracts),
        "seconds_total": round(elapsed, 2), "cost_usd": 0.0,
    })
    print(f"{len(contracts)} contracts ({args.split}), {elapsed:.1f}s\n")
    print(format_table(summary))
    print(f"\nsaved to {run_dir.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
