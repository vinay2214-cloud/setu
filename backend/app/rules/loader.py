from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

KNOWN_FACTS = {
    "conditions",
    "days_since_discharge",
    "max_missed_streak_critical",
    "symptoms",
    "symptom_severity_unknown_critical",
    "glucose_latest",
    "glucose_context",
    "bp_sys_latest",
    "bp_dia_latest",
    "consecutive_no_response",
    "intent_confidence_min",
    "needs_human",
    "medical_question",
}
OPS = {
    "==",
    "!=",
    ">",
    ">=",
    "<",
    "<=",
    "in",
    "not_in",
    "contains_any",
    "contains_all",
    "is_true",
    "is_false",
}
SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


class Rule(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    family: str
    title: str
    severity: str
    when: dict[str, Any]
    patient_template: str
    suggested_action: str = ""
    rationale: str = ""
    clinician_review: str = "required"


class RulePack(BaseModel):
    model_config = ConfigDict(extra="allow")
    pack: dict[str, Any]
    defaults: dict[str, Any]
    rules: list[Rule] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_rules(self) -> "RulePack":
        ids = [rule.id for rule in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate rule ids")
        for rule in self.rules:
            if rule.severity not in SEVERITIES:
                raise ValueError(f"{rule.id}: bad severity")
            validate_node(rule.when, rule.id)
        return self


def validate_node(node: Any, rule_id: str) -> None:
    if not isinstance(node, dict):
        raise ValueError(f"{rule_id}: condition must be an object")
    if "all" in node or "any" in node:
        children = node.get("all", node.get("any"))
        if not isinstance(children, list) or not children:
            raise ValueError(f"{rule_id}: all/any must contain conditions")
        for child in children:
            validate_node(child, rule_id)
    elif "not" in node:
        validate_node(node["not"], rule_id)
    else:
        fact = node.get("fact")
        op = node.get("op")
        if fact not in KNOWN_FACTS:
            raise ValueError(f"{rule_id}: unknown fact {fact!r}")
        if op not in OPS:
            raise ValueError(f"{rule_id}: unknown operator {op!r}")


def load_pack(path: str | Path) -> RulePack:
    parsed = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("rule pack must be a YAML object")
    return RulePack.model_validate(parsed)
