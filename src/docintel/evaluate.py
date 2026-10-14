"""Score extractions against CUAD's lawyer-highlighted passages.

Two views per field:
  * Span level  - did we quote the right passages?
      precision = predicted passages that match a gold passage / all predicted passages
      recall    = gold passages matched by some prediction    / all gold passages
    A predicted and a gold passage "match" when their word-set Jaccard >= threshold
    (0.5, as in the CUAD paper), so small boundary differences don't count as errors.
  * Presence    - did we correctly say whether the clause exists at all?
    This is where "correctly said absent" gets credit: most clauses are absent from
    most contracts.

Each (contract, field) pair also gets one outcome label for failure analysis.
"""

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

from docintel.cuad import GoldContract
from docintel.fields import FIELDS
from docintel.schema import ContractExtraction
from docintel.text import containment, jaccard

MATCH_THRESHOLD = 0.5
SAME_REGION = 0.5  # containment above this with no Jaccard match = right place, wrong extent

OUTCOMES = ("hit", "partial_hit", "boundary", "wrong_passage", "missed", "false_alarm", "correct_absent")


@dataclass
class FieldScore:
    contract_id: str
    field: str
    gold_present: bool
    pred_present: bool
    n_pred: int
    pred_matched: int
    n_gold: int
    gold_matched: int
    outcome: str


def score_field(contract_id: str, field: str, pred: list[str], gold: list[str],
                threshold: float = MATCH_THRESHOLD) -> FieldScore:
    pred_ok = [any(jaccard(p, g) >= threshold for g in gold) for p in pred]
    gold_ok = [any(jaccard(p, g) >= threshold for p in pred) for g in gold]

    if not gold and not pred:
        outcome = "correct_absent"
    elif not gold:
        outcome = "false_alarm"
    elif not pred:
        outcome = "missed"
    elif all(pred_ok) and all(gold_ok):
        outcome = "hit"
    elif any(gold_ok):
        outcome = "partial_hit"
    elif any(containment(p, g) >= SAME_REGION for p in pred for g in gold):
        outcome = "boundary"
    else:
        outcome = "wrong_passage"

    return FieldScore(contract_id, field, bool(gold), bool(pred), len(pred), sum(pred_ok),
                      len(gold), sum(gold_ok), outcome)


def score_contract(pred: ContractExtraction, gold: GoldContract,
                   threshold: float = MATCH_THRESHOLD) -> list[FieldScore]:
    return [
        score_field(gold.id, key, fx.evidence if fx.present else [], gold.labels[key], threshold)
        for key, fx in pred.items()
    ]


def _ratio(num: int, den: int) -> float | None:
    return num / den if den else None


def _f1(p: float | None, r: float | None) -> float | None:
    if p is None or r is None or p + r == 0:
        return None if p is None or r is None else 0.0
    return 2 * p * r / (p + r)


def summarize(scores: list[FieldScore]) -> dict:
    """Aggregate per field and overall (micro-averaged over all passages)."""
    groups: dict[str, list[FieldScore]] = defaultdict(list)
    for s in scores:
        groups[s.field].append(s)
        groups["ALL"].append(s)

    summary = {}
    for name in [f.key for f in FIELDS if f.key in groups] + ["ALL"]:
        g = groups[name]
        p = _ratio(sum(s.pred_matched for s in g), sum(s.n_pred for s in g))
        r = _ratio(sum(s.gold_matched for s in g), sum(s.n_gold for s in g))
        tp = sum(s.gold_present and s.pred_present for s in g)
        fp = sum(not s.gold_present and s.pred_present for s in g)
        fn = sum(s.gold_present and not s.pred_present for s in g)
        tn = sum(not s.gold_present and not s.pred_present for s in g)
        summary[name] = {
            "contracts": len(g),
            "span_precision": p,
            "span_recall": r,
            "span_f1": _f1(p, r),
            "presence_precision": _ratio(tp, tp + fp),
            "presence_recall": _ratio(tp, tp + fn),
            "presence_accuracy": _ratio(tp + tn, len(g)),
            "outcomes": {o: c for o, c in Counter(s.outcome for s in g).items()},
        }
    return summary


def _pct(x: float | None) -> str:
    return "  -  " if x is None else f"{100 * x:5.1f}"


def format_table(summary: dict) -> str:
    """Markdown table: renders in the terminal, in the README and on GitHub."""
    lines = [
        "| field | span P | span R | span F1 | presence acc | top errors |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for name, m in summary.items():
        errors = {o: c for o, c in m["outcomes"].items() if o not in ("hit", "correct_absent")}
        top = ", ".join(f"{o} {c}" for o, c in sorted(errors.items(), key=lambda x: -x[1])[:3])
        label = f"**{name}**" if name == "ALL" else name
        lines.append(f"| {label} | {_pct(m['span_precision'])} | {_pct(m['span_recall'])} | "
                     f"{_pct(m['span_f1'])} | {_pct(m['presence_accuracy'])} | {top} |")
    return "\n".join(lines)


def save_run(run_dir: Path, scores: list[FieldScore], meta: dict) -> dict:
    """Write everything a later chart, README table or post needs to reproduce the numbers."""
    run_dir.mkdir(parents=True, exist_ok=True)
    summary = summarize(scores)
    with open(run_dir / "scores.jsonl", "w", encoding="utf-8") as f:
        for s in scores:
            f.write(json.dumps(asdict(s)) + "\n")
    (run_dir / "summary.json").write_text(json.dumps({"meta": meta, "summary": summary}, indent=2),
                                          encoding="utf-8")
    (run_dir / "summary.md").write_text(format_table(summary) + "\n", encoding="utf-8")
    return summary
