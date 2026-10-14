"""Keyword baseline: no LLM, just sentences containing tell-tale phrases.

It exists for two reasons: it exercises the eval harness end to end without an
API key, and it gives the LLM pipeline a floor to beat. If the LLM can't clearly
beat this, the extra cost isn't justified.
"""

import re

from docintel.schema import ContractExtraction

_SENTENCE_END = re.compile(r"(?<=[.;:])\s+(?=[A-Z(\"“])|\n\s*\n")
_MONTH_DATE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{1,2}(st|nd|rd|th)?,?\s+\d{4}", re.I)

# field -> (all of these must appear, at least one of these must appear)
_RULES: dict[str, tuple[list[str], list[str]]] = {
    "effective_date": ([], ["effective date", "effective as of"]),
    "expiration_date": ([], ["initial term", "term of this agreement", "shall expire", "shall continue in"]),
    "governing_law": ([], ["governed by", "governing law", "construed in accordance with the laws"]),
    "renewal_term": ([], ["renew", "automatically extend"]),
    "notice_period_to_terminate_renewal": (["renew"], ["prior to", "before the expiration", "notice of non"]),
    "termination_for_convenience": (["terminat"], ["for any reason", "without cause", "for convenience",
                                                     "at any time upon"]),
    "anti_assignment": (["assign"], ["consent", "may not", "shall not"]),
    "cap_on_liability": (["liab"], ["exceed", "limited to", "in no event"]),
    "non_compete": ([], ["compete", "competitive product", "competing"]),
}
MAX_QUOTES = 3


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_END.split(text) if s and s.strip()]


def _absent() -> dict:
    return {"present": False, "evidence": [], "value": None}


def _found(quotes: list[str], value=None) -> dict:
    return {"present": True, "evidence": quotes, "value": value} if quotes else _absent()


def extract(text: str) -> ContractExtraction:
    sents = sentences(text)
    lowered = [s.lower() for s in sents]
    out: dict[str, dict] = {}

    for key, (required, any_of) in _RULES.items():
        hits = [s for s, low in zip(sents, lowered)
                if all(k in low for k in required) and any(k in low for k in any_of)]
        out[key] = _found(hits[:MAX_QUOTES])

    first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    out["document_name"] = _found([first_line] if first_line else [], first_line or None)

    head = text[:3000]
    date = _MONTH_DATE.search(head)
    out["agreement_date"] = _found([date.group(0)] if date else [])

    intro = next((s for s in sentences(head) if "between" in s.lower()), None)
    out["parties"] = {"present": bool(intro), "evidence": [intro] if intro else [], "value": []}

    return ContractExtraction.model_validate(out)
