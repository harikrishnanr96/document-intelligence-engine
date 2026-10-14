"""Load CUAD ground truth and split it into dev/test sets."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from docintel.fields import FIELDS

DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "data" / "raw" / "CUAD_v1"


@dataclass
class GoldContract:
    id: str  # CUAD title, which is also the PDF/TXT file stem
    text: str
    contract_type: str  # e.g. "License_Agreements", from the PDF folder it sits in
    labels: dict[str, list[str]]  # field key -> lawyer-highlighted passages ([] = clause absent)

    @property
    def split(self) -> str:
        """Deterministic ~80/20 dev/test split from a hash of the id.

        Stable across runs and machines, and independent of file order, so a
        contract never moves between sets.
        """
        h = int(hashlib.sha256(self.id.encode()).hexdigest(), 16)
        return "test" if h % 5 == 0 else "dev"


def _contract_types(root: Path) -> dict[str, str]:
    return {
        p.stem.lower(): p.parent.name
        for p in (root / "full_contract_pdf").rglob("*")
        if p.suffix.lower() == ".pdf"
    }


def load_cuad(root: Path = DEFAULT_ROOT, split: str | None = None) -> list[GoldContract]:
    data = json.loads((root / "CUAD_v1.json").read_text(encoding="utf-8"))["data"]
    types = _contract_types(root)
    by_category = {f.cuad_category: f.key for f in FIELDS}

    contracts = []
    for doc in data:
        para = doc["paragraphs"][0]  # CUAD v1 stores each contract as a single paragraph
        labels: dict[str, list[str]] = {f.key: [] for f in FIELDS}
        for qa in para["qas"]:
            # qa ids look like "<title>__<Category>"
            key = by_category.get(qa["id"].rsplit("__", 1)[-1])
            if key is None:
                continue
            for answer in qa["answers"]:
                if answer["text"] not in labels[key]:
                    labels[key].append(answer["text"])
        contracts.append(GoldContract(
            id=doc["title"],
            text=para["context"],
            contract_type=types.get(doc["title"].lower(), "Unknown"),
            labels=labels,
        ))
    if split:
        contracts = [c for c in contracts if c.split == split]
    return contracts
