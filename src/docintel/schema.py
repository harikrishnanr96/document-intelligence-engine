"""Pydantic schema for one contract's extraction.

Validation happens in two places:
  1. Structure: the JSON schema generated from these models is sent to the API
     (structured outputs), so the model cannot return the wrong shape.
  2. Meaning: the validators below enforce rules a JSON schema can't express,
     e.g. "present=true requires evidence" and "dates must be real ISO dates".
Grounding (is each quote really in the contract?) needs the contract text, so it
lives in validation.py.
"""

import re
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from docintel.fields import FIELDS


class FieldExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    present: bool = Field(description="True if the contract contains this clause/information.")
    evidence: list[str] = Field(
        description="Verbatim passages copied exactly from the contract that support the answer. "
        "Empty when present is false."
    )
    value: str | None = Field(description="Short normalized answer, or null if not determinable.")

    @field_validator("evidence")
    @classmethod
    def clean_evidence(cls, quotes: list[str]) -> list[str]:
        cleaned = []
        for q in (q.strip() for q in quotes):
            if q and q not in cleaned:
                cleaned.append(q)
        return cleaned

    @model_validator(mode="after")
    def present_matches_evidence(self):
        if self.present and not self.evidence:
            raise ValueError("present=true but no evidence was quoted")
        if not self.present and (self.evidence or self.value):
            raise ValueError("present=false but evidence or value was given")
        return self


ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


class DateExtraction(FieldExtraction):
    value: str | None = Field(
        description="The date as YYYY-MM-DD if it can be determined (resolve relative terms such as "
        "'five years after the Effective Date' when the anchor date is known), else null."
    )

    @field_validator("value")
    @classmethod
    def iso_date(cls, v: str | None) -> str | None:
        if v is not None:
            if not ISO_DATE.fullmatch(v):
                raise ValueError(f"date must be YYYY-MM-DD, got {v!r}")
            date.fromisoformat(v)  # rejects impossible dates such as 2020-02-30
        return v


class NamesExtraction(FieldExtraction):
    value: list[str] = Field(description="Each party's legal name, one entry per party.")


class ContractExtraction(BaseModel):
    """One attribute per entry in fields.FIELDS (enforced by a test)."""

    model_config = ConfigDict(extra="forbid")

    document_name: FieldExtraction
    parties: NamesExtraction
    agreement_date: DateExtraction
    effective_date: DateExtraction
    expiration_date: DateExtraction
    governing_law: FieldExtraction
    renewal_term: FieldExtraction
    notice_period_to_terminate_renewal: FieldExtraction
    termination_for_convenience: FieldExtraction
    anti_assignment: FieldExtraction
    cap_on_liability: FieldExtraction
    non_compete: FieldExtraction

    def items(self) -> list[tuple[str, FieldExtraction]]:
        return [(f.key, getattr(self, f.key)) for f in FIELDS]
