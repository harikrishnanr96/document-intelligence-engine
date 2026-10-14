"""Validate raw model output: schema + semantic rules, then grounding against the contract.

Every failure is recorded rather than raised, so the eval can report how often
each safeguard fired (a number worth quoting: "validation caught N% of outputs").
"""

import re
from dataclasses import dataclass, field

from pydantic import ValidationError

from docintel.schema import ContractExtraction
from docintel.text import normalize

_ELLIPSIS = re.compile(r"\.\.\.|…")


@dataclass
class GroundingIssue:
    field: str
    quote: str


@dataclass
class ValidationReport:
    extraction: ContractExtraction | None
    schema_errors: list[str] = field(default_factory=list)
    grounding_issues: list[GroundingIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.extraction is not None and not self.grounding_issues


def is_grounded(quote: str, normalized_contract: str) -> bool:
    """True if the quote appears in the contract, ignoring case/spacing/punctuation.

    A quote elided with '...' counts as grounded if every piece appears.
    """
    pieces = [normalize(p) for p in _ELLIPSIS.split(quote)]
    pieces = [p for p in pieces if p]
    return bool(pieces) and all(f" {p} " in normalized_contract for p in pieces)


def check_grounding(extraction: ContractExtraction, contract_text: str) -> list[GroundingIssue]:
    normalized_contract = f" {normalize(contract_text)} "
    return [
        GroundingIssue(key, quote)
        for key, fx in extraction.items()
        for quote in fx.evidence
        if not is_grounded(quote, normalized_contract)
    ]


def validate_output(raw_json: str, contract_text: str) -> ValidationReport:
    try:
        extraction = ContractExtraction.model_validate_json(raw_json)
    except ValidationError as e:
        errors = [f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors()]
        return ValidationReport(extraction=None, schema_errors=errors)
    return ValidationReport(extraction, grounding_issues=check_grounding(extraction, contract_text))
