"""Run LLM extraction on a sample of CUAD contracts and score it.

    python scripts/run_extraction.py --n 20                 # 20 dev contracts, Haiku 5.5, prompt v1
    python scripts/run_extraction.py --n 1                  # smoke test on one contract
    python scripts/run_extraction.py --n 20 --model claude-opus-5-5
    python scripts/run_extraction.py --n 100 --exclude-sample 20  # 80 dev contracts not used for tuning
"""

import argparse
import json
import random
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import anthropic

from docintel.cuad import load_cuad
from docintel.evaluate import format_table, save_run, score_contract
from docintel.extract import DEFAULT_MODEL, PRICES, extract
from docintel.fields import FIELDS
from docintel.prompts import PROMPTS
from docintel.schema import ContractExtraction

ROOT = Path(__file__).resolve().parents[1]
EMPTY = ContractExtraction.model_validate({
    f.key: {"present": False, "evidence": [], "value": [] if f.kind == "names" else None} for f in FIELDS
})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test"], default="dev")
    ap.add_argument("--n", type=int, default=20, help="number of contracts (sampled with a fixed seed)")
    ap.add_argument("--model", choices=sorted(PRICES), default=DEFAULT_MODEL)
    ap.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"], default="medium")
    ap.add_argument("--prompt", choices=sorted(PROMPTS), default="v1")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--exclude-sample", type=int, default=0, metavar="K",
                    help="leave out the contracts a --n K run uses, e.g. the 20 used for prompt tuning")
    args = ap.parse_args()

    pool = sorted(load_cuad(split=args.split), key=lambda c: c.id)
    # Same seed -> same contracts every run, so prompt/model versions are compared on identical inputs.
    contracts = random.Random(0).sample(pool, min(args.n, len(pool)))
    if args.exclude_sample:
        tuning = {c.id for c in random.Random(0).sample(pool, args.exclude_sample)}
        contracts = [c for c in contracts if c.id not in tuning]
    prompt = PROMPTS[args.prompt]
    client = anthropic.Anthropic()

    name = f"{datetime.now():%Y%m%d-%H%M%S}-{args.model}-{args.effort}-{args.prompt}-{args.split}{len(contracts)}"
    run_dir = ROOT / "runs" / name
    (run_dir / "outputs").mkdir(parents=True)

    def run_one(contract):
        try:
            res = extract(client, contract.text, prompt, args.model, args.effort)
        except anthropic.APIStatusError as e:
            print(f"  ✗ {contract.id[:60]}: API error {e.status_code}")
            return contract, None
        except anthropic.APIConnectionError:
            print(f"  ✗ {contract.id[:60]}: connection error")
            return contract, None
        status = "ok" if res.extraction and not res.error else (res.error or "invalid")
        print(f"  {'✓' if status == 'ok' else '✗'} {contract.id[:60]:60} {res.seconds:5.1f}s "
              f"${res.cost_usd:.3f} attempts={res.attempts} {status}")
        record = {k: v for k, v in vars(res).items() if k != "extraction"}
        record["extraction"] = res.extraction.model_dump() if res.extraction else None
        (run_dir / "outputs" / f"{contract.id[:120]}.json").write_text(json.dumps(record, indent=2),
                                                                     encoding="utf-8")
        return contract, res

    print(f"{len(contracts)} contracts · {args.model} · effort={args.effort} · prompt={args.prompt}")
    with ThreadPoolExecutor(args.workers) as pool:
        results = list(pool.map(run_one, contracts))

    scores, done = [], [r for _, r in results if r is not None]
    for contract, res in results:
        # A contract with no valid output is scored as "found nothing", so failures cost recall.
        scores += score_contract(res.extraction if res and res.extraction else EMPTY, contract)

    n = len(contracts)
    meta = {
        "system": "llm", "model": args.model, "effort": args.effort, "prompt": args.prompt,
        "split": args.split, "contracts": n,
        "api_failures": n - len(done),
        "cost_usd_total": round(sum(r.cost_usd for r in done), 4),
        "cost_usd_per_contract": round(sum(r.cost_usd for r in done) / max(len(done), 1), 4),
        "seconds_per_contract": round(sum(r.seconds for r in done) / max(len(done), 1), 1),
        "validation": {
            "first_attempt_schema_failures": sum(bool(r.first_attempt_schema_errors) for r in done),
            "first_attempt_with_ungrounded_quotes": sum(r.first_attempt_ungrounded > 0 for r in done),
            "retried": sum(r.attempts > 1 for r in done),
            "ungrounded_quotes_dropped_after_retry": sum(r.final_ungrounded_dropped for r in done),
            "no_valid_output": sum(r.extraction is None for r in done),
        },
        "served_by": sorted({r.served_by for r in done}),
    }
    summary = save_run(run_dir, scores, meta)
    print("\n" + format_table(summary))
    print(f"\ncost ${meta['cost_usd_total']:.2f} total, ${meta['cost_usd_per_contract']:.3f}/contract, "
          f"{meta['seconds_per_contract']}s/contract")
    print("validation:", json.dumps(meta["validation"]))
    print(f"saved to {run_dir.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
