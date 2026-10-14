from docintel.cuad import GoldContract
from docintel.evaluate import score_contract, score_field, summarize
from docintel.fields import FIELDS
from docintel.schema import ContractExtraction

GOV = "This Agreement shall be governed by the laws of the State of New York without regard to conflicts"


def gold(**labels) -> GoldContract:
    return GoldContract("c1", "text", "Test", {f.key: labels.get(f.key, []) for f in FIELDS})


def prediction_from(g: GoldContract) -> ContractExtraction:
    return ContractExtraction.model_validate({
        f.key: {"present": bool(g.labels[f.key]), "evidence": g.labels[f.key],
                "value": [] if f.kind == "names" else None}
        for f in FIELDS
    })


def test_oracle_scores_perfectly():
    g = gold(governing_law=[GOV], parties=["Acme Corp", "Beta LLC"])
    m = summarize(score_contract(prediction_from(g), g))["ALL"]
    assert m["span_precision"] == m["span_recall"] == m["presence_accuracy"] == 1.0


def test_correct_absence_counts_for_presence_not_spans():
    s = score_field("c1", "non_compete", [], [])
    assert s.outcome == "correct_absent"
    m = summarize([s])["non_compete"]
    assert m["presence_accuracy"] == 1.0 and m["span_precision"] is None


def test_small_boundary_difference_still_matches():
    s = score_field("c1", "governing_law", [GOV + "."], [GOV + " principles."])
    assert s.outcome == "hit"


def test_sub_sentence_quote_is_a_boundary_error():
    s = score_field("c1", "governing_law", ["the laws of the State of New York"], [GOV])
    assert s.outcome == "boundary"


def test_outcome_labels():
    assert score_field("c1", "x", [], [GOV]).outcome == "missed"
    assert score_field("c1", "x", [GOV], []).outcome == "false_alarm"
    assert score_field("c1", "x", ["completely unrelated payment terms"], [GOV]).outcome == "wrong_passage"
    assert score_field("c1", "x", [GOV, "extra unrelated sentence here"], [GOV]).outcome == "partial_hit"


def test_precision_and_recall_counts():
    s = score_field("c1", "x", [GOV, "noise words only"], [GOV, "Acme may not assign this Agreement"])
    assert (s.pred_matched, s.n_pred, s.gold_matched, s.n_gold) == (1, 2, 1, 2)
