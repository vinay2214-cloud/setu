from typing import Any

from app.rules.loader import Rule, RulePack

SEVERITY_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


def _leaf(node: dict[str, Any], facts: dict[str, Any]) -> bool:
    value = facts.get(node["fact"])
    op, ref = node["op"], node.get("value")
    if op == "is_true":
        return value is True
    if op == "is_false":
        return value is False
    if value is None:
        return False
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
    raise ValueError(f"Unsupported operator: {op}")


def evaluate_node(node: dict[str, Any], facts: dict[str, Any]) -> bool:
    if "all" in node:
        return all(evaluate_node(item, facts) for item in node["all"])
    if "any" in node:
        return any(evaluate_node(item, facts) for item in node["any"])
    if "not" in node:
        return not evaluate_node(node["not"], facts)
    return _leaf(node, facts)


def evaluate(pack: RulePack, facts: dict[str, Any]) -> list[Rule]:
    """Evaluate all rules, then keep the highest-severity rule in each family."""
    best: dict[str, Rule] = {}
    for rule in pack.rules:
        if not evaluate_node(rule.when, facts):
            continue
        current = best.get(rule.family)
        if current is None or SEVERITY_ORDER[rule.severity] > SEVERITY_ORDER[current.severity]:
            best[rule.family] = rule
    return sorted(best.values(), key=lambda rule: -SEVERITY_ORDER[rule.severity])
