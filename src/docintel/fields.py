"""The fields we extract, and how each maps onto a CUAD label category.

This registry is the single source of truth: the schema, the prompt and the
evaluator all read from it, so adding a field means adding one entry here
(plus its attribute on ContractExtraction).
"""

from dataclasses import dataclass
from typing import Literal

# text   -> a short normalized string (e.g. "Delaware")
# date   -> an ISO date (YYYY-MM-DD) when one can be determined
# names  -> a list of names
# clause -> a clause whose value is a short plain-English summary
Kind = Literal["text", "date", "names", "clause"]


@dataclass(frozen=True)
class FieldSpec:
    key: str  # attribute name on ContractExtraction
    cuad_category: str  # exact category name in CUAD_v1.json
    kind: Kind
    definition: str  # CUAD's official definition, used verbatim in the baseline prompt
    difficulty: Literal["factual", "interpretive"]


FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("document_name", "Document Name", "text",
              "The name of the contract", "factual"),
    FieldSpec("parties", "Parties", "names",
              "The two or more parties who signed the contract", "factual"),
    FieldSpec("agreement_date", "Agreement Date", "date",
              "The date of the contract", "factual"),
    FieldSpec("effective_date", "Effective Date", "date",
              "The date when the contract is effective", "factual"),
    FieldSpec("expiration_date", "Expiration Date", "date",
              "On what date will the contract's initial term expire?", "factual"),
    FieldSpec("governing_law", "Governing Law", "text",
              "Which state/country's law governs the interpretation of the contract?", "factual"),
    FieldSpec("renewal_term", "Renewal Term", "clause",
              "What is the renewal term after the initial term expires? This includes automatic "
              "extensions and unilateral extensions with prior notice.", "interpretive"),
    FieldSpec("notice_period_to_terminate_renewal", "Notice Period To Terminate Renewal", "clause",
              "What is the notice period required to terminate renewal?", "interpretive"),
    FieldSpec("termination_for_convenience", "Termination For Convenience", "clause",
              "Can a party terminate this contract without cause (solely by giving a notice and "
              "allowing a waiting period to expire)?", "interpretive"),
    FieldSpec("anti_assignment", "Anti-Assignment", "clause",
              "Is consent or notice required of a party if the contract is assigned to a third party?",
              "interpretive"),
    FieldSpec("cap_on_liability", "Cap On Liability", "clause",
              "Does the contract include a cap on liability upon the breach of a party's obligation? "
              "This includes time limitation for the counterparty to bring claims or maximum amount "
              "for recovery.", "interpretive"),
    FieldSpec("non_compete", "Non-Compete", "clause",
              "Is there a restriction on the ability of a party to compete with the counterparty or "
              "operate in a certain geography or business or technology sector?", "interpretive"),
)

FIELDS_BY_KEY = {f.key: f for f in FIELDS}
