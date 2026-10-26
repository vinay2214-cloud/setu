import copy
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.providers.llm.base import LLMProvider

SEED = Path(__file__).resolve().parents[3] / "seed"


class CandidatePlan(BaseModel):
    model_config = ConfigDict(extra="allow")
    diagnoses: list[dict] = Field(default_factory=list)
    medications: list[dict] = Field(default_factory=list)
    monitoring: list[dict] = Field(default_factory=list)
    red_flags: list[dict] = Field(default_factory=list)
    follow_ups: list[dict] = Field(default_factory=list)
    diet: dict = Field(default_factory=dict)
    activity: dict = Field(default_factory=dict)


def verify_plan(candidate: dict, source: str) -> tuple[dict, list[str]]:
    """Keep only source-backed facts. Never calculate or expand a dose."""
    plan = copy.deepcopy(CandidatePlan.model_validate(candidate).model_dump())
    warnings: list[str] = []
    for key in ("diagnoses", "medications", "monitoring", "red_flags", "follow_ups"):
        kept = []
        for item in plan.get(key, []):
            if not isinstance(item, dict):
                warnings.append(f"Dropped invalid {key} item.")
                continue
            span = item.get("source_span", {})
            quoted = span.get("text", "") if isinstance(span, dict) else ""
            if not quoted or quoted not in source:
                warnings.append(f"Dropped {key} item: source span not found.")
                continue
            if key == "medications" and (
                not item.get("name")
                or item["name"].lower() not in quoted.lower()
                or not item.get("dose_text")
                or item["dose_text"] not in quoted
            ):
                warnings.append("Dropped medication: name/dose is not verbatim in its source span.")
                continue
            if key == "medications":
                name_end = quoted.lower().find(item["name"].lower()) + len(item["name"])
                if item["dose_text"].strip() != quoted[name_end:].strip():
                    warnings.append("Dropped medication: incomplete source dose instruction.")
                    continue
            start = source.index(quoted)
            item["source_span"] = {"start": start, "end": start + len(quoted), "text": quoted}
            item["needs_review"] = float(item.get("confidence", 0)) < 0.75
            if key == "medications":
                item["criticality"] = item.get("criticality", "standard")
                if item["criticality"] not in {"critical", "standard"}:
                    item["criticality"] = "standard"
                    item["needs_review"] = True
            kept.append(item)
        plan[key] = kept
    for key in ("diet", "activity"):
        item = plan.get(key, {})
        quoted = item.get("source_span", {}).get("text", "") if isinstance(item, dict) else ""
        if not quoted or quoted not in source:
            plan[key] = {}
            if item:
                warnings.append(f"Dropped {key}: source span not found.")
    plan["warnings"] = warnings
    return plan, warnings


def canned_plan(source: str, language: str) -> dict:
    sample = (SEED / "discharge_summary_ramesh.txt").read_text()
    if " ".join(source.split()) != " ".join(sample.split()):
        return {"language": language, "medications": [], "diagnoses": [], "needs_review": True}
    candidate = json.loads((SEED / "discharge_summary_ramesh.expected_plan.json").read_text())
    candidate["language"] = language
    for medication in candidate["medications"]:
        quote = medication["source_span"]["text"]
        medication["dose_text"] = quote.split(medication["name"], 1)[1].strip()
    for item in candidate["red_flags"]:
        index = source.lower().find(item["label"].lower())
        if index >= 0:
            quote = source[index : index + len(item["label"])]
            item["source_span"] = {"start": index, "end": index + len(quote), "text": quote}
            item["confidence"] = 1.0
    return candidate


def compile_plan(
    source: str, language: str, provider: LLMProvider
) -> tuple[dict[str, Any], list[str]]:
    try:
        candidate = provider.generate_json(task="plan", text=source, language=language)
        plan, warnings = verify_plan(candidate, source)
        if not plan.get("medications"):
            warnings.append("No source-verified medicines extracted; clinician review required.")
        return plan, warnings
    except Exception:
        return {"language": language, "medications": [], "needs_review": True}, [
            "Provider failed; empty draft requires clinician review."
        ]
