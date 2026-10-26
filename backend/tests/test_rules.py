import json
from pathlib import Path

import pytest

from app.rules.engine import evaluate, evaluate_node
from app.rules.loader import RulePack, load_pack

ROOT = Path(__file__).resolve().parents[2]
PACK_PATH = ROOT / "seed" / "rules" / "diabetes_htn_v1.yaml"
CASES_PATH = ROOT / "seed" / "rules" / "diabetes_htn_v1.tests.json"


def test_golden_rule_cases_match_reference_pack():
    pack = load_pack(PACK_PATH)
    spec = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    for case in spec["cases"]:
        facts = {**spec["defaults"], **case["facts"]}
        assert sorted(rule.id for rule in evaluate(pack, facts)) == sorted(case["expect"]), case[
            "name"
        ]


def test_unknown_fact_fails_pack_validation():
    with pytest.raises(ValueError, match="unknown fact"):
        RulePack.model_validate(
            {
                "pack": {"version": "1"},
                "defaults": {},
                "rules": [
                    {
                        "id": "R-X",
                        "family": "x",
                        "title": "x",
                        "severity": "LOW",
                        "patient_template": "x",
                        "when": {"fact": "invented_fact", "op": "is_true"},
                    }
                ],
            }
        )


def test_missing_fact_comparison_is_false():
    assert evaluate_node({"fact": "glucose_latest", "op": ">=", "value": 250}, {}) is False
