import json

import pytest
from pydantic import ValidationError

from docintel.fields import FIELDS
from docintel.schema import ContractExtraction, DateExtraction, FieldExtraction
from docintel.validation import validate_output

CONTRACT = 'This Agreement shall be governed by the laws of the State of New York.\nDated May 8, 2014.'


def absent():
    return {"present": False, "evidence": [], "value": None}


def full(**overrides):
    out = {f.key: absent() for f in FIELDS}
    out["parties"]["value"] = []
    out.update(overrides)
    return out


def test_schema_attributes_match_field_registry():
    assert list(ContractExtraction.model_fields) == [f.key for f in FIELDS]


def test_json_schema_generates():
    schema = ContractExtraction.model_json_schema()
    assert set(schema["required"]) == {f.key for f in FIELDS}


def test_present_requires_evidence():
    with pytest.raises(ValidationError, match="no evidence"):
        FieldExtraction(present=True, evidence=[], value="x")


def test_absent_forbids_evidence():
    with pytest.raises(ValidationError, match="present=false"):
        FieldExtraction(present=False, evidence=["some text"], value=None)


def test_blank_and_duplicate_quotes_are_dropped():
    fx = FieldExtraction(present=True, evidence=[" a ", "", "a"], value=None)
    assert fx.evidence == ["a"]


@pytest.mark.parametrize("bad", ["May 8, 2014", "2014-5-8", "2014-02-30"])
def test_dates_must_be_real_iso_dates(bad):
    with pytest.raises(ValidationError):
        DateExtraction(present=True, evidence=["x"], value=bad)


def test_date_may_be_null_when_clause_present():
    # e.g. "expires five years after the Effective Date" with no known anchor
    assert DateExtraction(present=True, evidence=["x"], value=None).value is None


def test_validate_output_reports_schema_errors_without_raising():
    report = validate_output('{"document_name": {}}', CONTRACT)
    assert report.extraction is None and report.schema_errors


def test_grounding_accepts_whitespace_and_case_differences():
    raw = json.dumps(full(governing_law={
        "present": True, "evidence": ["governed by the LAWS of the\n State of New York"], "value": "New York"}))
    report = validate_output(raw, CONTRACT)
    assert report.ok


def test_grounding_flags_invented_quotes():
    raw = json.dumps(full(governing_law={
        "present": True, "evidence": ["governed by the laws of Delaware"], "value": "Delaware"}))
    report = validate_output(raw, CONTRACT)
    assert not report.ok
    assert [i.field for i in report.grounding_issues] == ["governing_law"]


def test_grounding_accepts_elided_quotes():
    raw = json.dumps(full(governing_law={
        "present": True, "evidence": ["This Agreement ... State of New York"], "value": "New York"}))
    assert validate_output(raw, CONTRACT).ok
