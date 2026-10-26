"""Reference rule engine for Setu (prototype).

Purpose: a small, dependency-light implementation that defines the exact semantics in
docs/03-BACKEND-SPEC.md section 5. Port it into backend/app/rules/engine.py (add typing,
Pydantic models, logging) and keep the golden tests passing.

Run the golden tests:
    python3 seed/rules/reference_engine.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml

SEVERITY_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}

KNOWN_FACTS = {
    "conditions", "days_since_discharge", "max_missed_streak_critical", "symptoms",
    "symptom_severity_unknown_critical", "glucose_latest", "glucose_context",
    "bp_sys_latest", "bp_dia_latest", "consecutive_no_response",
    "intent_confidence_min", "needs_human", "medical_question",
}
OPS = {"==", "!=", ">", ">=", "<", "<=", "in", "not_in", "contains_any", "contains_all", "is_true", "is_false"}


def _validate_node(node: Any, rule_id: str) -> None:
    if "all" in node or "any" in node:
        for child in node.get("all", node.get("any")):
            _validate_node(child, rule_id)
    elif "not" in node:
        _validate_node(node["not"], rule_id)
    else:
        if node["fact"] not in KNOWN_FACTS:
            raise ValueError(f"{rule_id}: unknown fact {node['fact']!r}")
        if node["op"] not in OPS:
            raise ValueError(f"{rule_id}: unknown operator {node['op']!r}")


def load_pack(path: str | Path) -> dict:
    pack = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    ids = [r["id"] for r in pack["rules"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate rule ids")
    for rule in pack["rules"]:
        for key in ("id", "family", "title", "severity", "when", "patient_template"):
            if key not in rule:
                raise ValueError(f"{rule.get('id')}: missing {key}")
        if rule["severity"] not in SEVERITY_ORDER:
            raise ValueError(f"{rule['id']}: bad severity")
        _validate_node(rule["when"], rule["id"])
    return pack


def _leaf(node: dict, facts: dict) -> bool:
    value = facts.get(node["fact"])
    op, ref = node["op"], node.get("value")
    if op == "is_true":
        return value is True
    if op == "is_false":
        return value is False
    if value is None:
        return False  # missing fact: comparisons are false, never an error
    if op == "==":
        return value == ref
    if op == "!=":
        return value != ref
    if op == ">":
        return value > ref
    if op == ">=":
        return value >= ref
    if op == "<":
        return value < ref
    if op == "<=":
        return value <= ref
    if op == "in":
        return value in ref
    if op == "not_in":
        return value not in ref
    if op == "contains_any":
        return bool(set(value) & set(ref))
    if op == "contains_all":
        return set(ref) <= set(value)
    raise ValueError(op)


def _eval(node: dict, facts: dict) -> bool:
    if "all" in node:
        return all(_eval(n, facts) for n in node["all"])
    if "any" in node:
        return any(_eval(n, facts) for n in node["any"])
    if "not" in node:
        return not _eval(node["not"], facts)
    return _leaf(node, facts)


def evaluate(pack: dict, facts: dict) -> list[dict]:
    """Return fired rules after family reduction (highest severity per family), most severe first."""
    fired = [r for r in pack["rules"] if _eval(r["when"], facts)]
    best: dict[str, dict] = {}
    for rule in fired:
        cur = best.get(rule["family"])
        if cur is None or SEVERITY_ORDER[rule["severity"]] > SEVERITY_ORDER[cur["severity"]]:
            best[rule["family"]] = rule
    return sorted(best.values(), key=lambda r: -SEVERITY_ORDER[r["severity"]])


def run_golden(pack_path: Path, tests_path: Path) -> int:
    pack = load_pack(pack_path)
    spec = json.loads(tests_path.read_text(encoding="utf-8"))
    failures = 0
    for case in spec["cases"]:
        facts = {**spec["defaults"], **case["facts"]}
        got = sorted(r["id"] for r in evaluate(pack, facts))
        want = sorted(case["expect"])
        ok = got == want
        failures += 0 if ok else 1
        print(("PASS " if ok else "FAIL ") + case["name"] + ("" if ok else f"  got={got} want={want}"))
    print(f"\n{len(spec['cases']) - failures}/{len(spec['cases'])} passed; {len(pack['rules'])} rules loaded")
    return failures


if __name__ == "__main__":
    here = Path(__file__).parent
    sys.exit(1 if run_golden(here / "diabetes_htn_v1.yaml", here / "diabetes_htn_v1.tests.json") else 0)
