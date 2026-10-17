"""Extract fields from one contract with Claude: call -> validate -> (retry once) -> result.

The API enforces the JSON shape (structured outputs). Our validation then checks
meaning and grounding; if that fails, the errors go back to the model once.
"""

import time
from dataclasses import dataclass, field

import anthropic
from anthropic import transform_schema
from dotenv import load_dotenv

from docintel.prompts import Prompt, build_messages
from docintel.schema import ContractExtraction
from docintel.validation import ValidationReport, drop_ungrounded, validate_output

load_dotenv()  # reads ANTHROPIC_API_KEY from .env

# USD per million tokens (input, output). Update if pricing changes.
PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}
DEFAULT_MODEL = "claude-haiku-5-5"  # cheapest; used for prompt iteration
OUTPUT_FORMAT = {"type": "json_schema", "schema": transform_schema(ContractExtraction)}
# Server-side fallback re-runs a declined request on another model. Haiku has none.
FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5"}
FALLBACK_BETA = "server-side-fallback-2026-07-01"


@dataclass
class ExtractionResult:
    extraction: ContractExtraction | None  # None only if no valid output after the retry
    attempts: int = 0
    first_attempt_schema_errors: list[str] = field(default_factory=list)
    first_attempt_ungrounded: int = 0
    final_ungrounded_dropped: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    seconds: float = 0.0
    served_by: str = ""
    error: str | None = None


def _feedback(report: ValidationReport) -> str:
    problems = report.schema_errors + [
        f'{i.field}: this quote does not appear in the contract: "{i.quote[:200]}"'
        for i in report.grounding_issues
    ]
    return ("Your output failed validation:\n- " + "\n- ".join(problems) +
            "\n\nReturn the complete corrected JSON. Evidence must be copied word for word from the contract.")


def extract(client: anthropic.Anthropic, contract_text: str, prompt: Prompt,
            model: str = DEFAULT_MODEL, effort: str = "medium") -> ExtractionResult:
    result = ExtractionResult(extraction=None)
    messages = build_messages(prompt, contract_text)
    fallback = {"betas": [FALLBACK_BETA], "fallbacks": "default"} if model in FALLBACK_MODELS else {}
    start = time.perf_counter()

    for attempt in (1, 2):
        result.attempts = attempt
        response = client.beta.messages.create(
            model=model,
            max_tokens=16000,
            system=prompt.system,
            messages=messages,
            output_config={"effort": effort, "format": OUTPUT_FORMAT},
            **fallback,
        )
        result.input_tokens += response.usage.input_tokens
        result.output_tokens += response.usage.output_tokens
        result.served_by = response.model

        if response.stop_reason in ("refusal", "max_tokens"):
            result.error = response.stop_reason
            break
        text = next(b.text for b in response.content if b.type == "text")
        report = validate_output(text, contract_text)

        if attempt == 1:
            result.first_attempt_schema_errors = report.schema_errors
            result.first_attempt_ungrounded = len(report.grounding_issues)
        if report.extraction is not None:
            result.extraction = drop_ungrounded(report.extraction, report.grounding_issues)
            result.final_ungrounded_dropped = len(report.grounding_issues)
        if report.ok or attempt == 2:
            break
        # Append the full response (not just its text) so the conversation stays append-only.
        messages = messages + [
            {"role": "assistant", "content": response.content},
            {"role": "user", "content": _feedback(report)},
        ]

    in_price, out_price = PRICES[model]
    result.cost_usd = (result.input_tokens * in_price + result.output_tokens * out_price) / 1e6
    result.seconds = time.perf_counter() - start
    return result
