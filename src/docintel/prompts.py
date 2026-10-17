"""Prompt versions. Each run records which version it used, so scores can be compared.

v1 is deliberately plain: CUAD's one-line definitions and basic rules, nothing else.
It is the "before" measurement that context engineering (v2+) has to beat.
"""

from dataclasses import dataclass

from docintel.fields import FIELDS


@dataclass(frozen=True)
class Prompt:
    version: str
    system: str
    task: str  # appears after the contract text


V1 = Prompt(
    version="v1",
    system="""You are a contract analyst. You will read one commercial contract and extract specific information from it.

Rules:
1. Read the entire contract before answering. Information can appear anywhere, including definitions, schedules and signature blocks.
2. For each field, set "present" to true only if the contract contains it.
3. "evidence" must be copied word for word from the contract. Never paraphrase, summarize or fix typos in a quote.
4. If a field is not in the contract: present = false, evidence = [], value = null (an empty list for parties).
5. "value" is a short, clean answer (e.g. "California", "30 days"). Dates as YYYY-MM-DD; if a date can't be determined, use null.""",
    task="Extract these fields from the contract above:\n"
    + "\n".join(f"- {f.key}: {f.definition}" for f in FIELDS),
)

# v2a = v1 + quoting rules. CUAD reviewers highlight only the name/date for
# parties and dates, but whole sentences for clauses (checked on dev labels).
QUOTING_RULES = """How much to quote (match how legal reviewers highlight):
- document_name: only the title as written (e.g. "STRATEGIC ALLIANCE AGREEMENT").
- parties: each party's name as a separate quote, AND each short name it is defined as (e.g. "Lightbridge Corporation" and "Lightbridge"). Names only, not the sentence around them.
- agreement_date, effective_date: only the date phrase itself (e.g. "16 day of August. 2012"), not the sentence.
- all other fields: the complete sentence(s) containing the clause. If the clause appears in several places, quote each passage separately. Include every relevant passage, not just the first one you find."""

V2A = Prompt(version="v2a", system=V1.system + "\n\n" + QUOTING_RULES, task=V1.task)

PROMPTS = {p.version: p for p in (V1, V2A)}


def build_messages(prompt: Prompt, contract_text: str) -> list[dict]:
    # Long document first, question last: models answer long-context questions
    # better when the instructions come after the document.
    return [{
        "role": "user",
        "content": f"<contract>\n{contract_text}\n</contract>\n\n{prompt.task}",
    }]
