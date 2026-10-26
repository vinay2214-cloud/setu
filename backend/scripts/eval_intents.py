import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.intent_extractor import CRITICAL, IntentExtractor

ROOT = Path(__file__).resolve().parents[2]
cases = json.loads((ROOT / "seed" / "eval_utterances.json").read_text(encoding="utf-8"))["cases"]
extractor = IntentExtractor()
stats = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "critical": 0, "critical_hit": 0})
med_expected = med_correct = 0
vital_expected = vital_correct = 0
safety_expected = safety_passed = 0
negation_expected = negation_correct = 0
errors = []

for case in cases:
    expected = case.get("expect", {})
    result = extractor.extract(case["text"], case["lang"])
    bucket = stats[case["lang"]]
    expected_symptoms = set(expected.get("symptoms", []))
    found = {item["code"] for item in result["symptoms"] if not item["negated"]}
    negated = {item["code"] for item in result["symptoms"] if item["negated"]}
    bucket["tp"] += len(expected_symptoms & found)
    bucket["fp"] += len(found - expected_symptoms)
    bucket["fn"] += len(expected_symptoms - found)
    expected_critical = expected_symptoms & CRITICAL
    bucket["critical"] += len(expected_critical)
    bucket["critical_hit"] += len(expected_critical & found)
    if expected_symptoms - found:
        errors.append(f"{case['id']}: missing symptoms {sorted(expected_symptoms - found)}")
    expected_negated = set(expected.get("negated", []))
    negation_expected += len(expected_negated)
    negation_correct += len(expected_negated & negated)
    if expected_negated - negated:
        errors.append(
            f"{case['id']}: missed expected negations {sorted(expected_negated - negated)}"
        )
    if expected.get("medication_status"):
        med_expected += 1
        got = result["medication_events"][0]["status"] if result["medication_events"] else None
        med_correct += int(got == expected["medication_status"])
    if expected.get("vitals"):
        vital_expected += len(expected["vitals"])
        for expected_vital in expected["vitals"]:
            vital_correct += int(
                any(
                    all(item.get(key) == value for key, value in expected_vital.items())
                    for item in result["vitals"]
                )
            )
    if expected.get("needs_human") or expected.get("critical"):
        safety_expected += 1
        critical_detected = any(
            item["code"] in CRITICAL and not item["negated"] for item in result["symptoms"]
        )
        safety_passed += int(result["needs_human"] or critical_detected)

critical_total = sum(item["critical"] for item in stats.values())
critical_hit = sum(item["critical_hit"] for item in stats.values())
overall_tp = sum(item["tp"] for item in stats.values())
overall_fp = sum(item["fp"] for item in stats.values())
overall_fn = sum(item["fn"] for item in stats.values())
overall_precision = overall_tp / (overall_tp + overall_fp) if overall_tp + overall_fp else 1.0
critical_recall = critical_hit / critical_total if critical_total else 1.0
med_accuracy = med_correct / med_expected if med_expected else 1.0
vital_accuracy = vital_correct / vital_expected if vital_expected else 1.0
safety_coverage = safety_passed / safety_expected if safety_expected else 1.0
negation_accuracy = negation_correct / negation_expected if negation_expected else 1.0

print("language | symptom TP | symptom FP | symptom FN | precision | recall | critical recall")
for language in sorted(stats):
    item = stats[language]
    precision = item["tp"] / (item["tp"] + item["fp"]) if item["tp"] + item["fp"] else 1.0
    recall = item["tp"] / (item["tp"] + item["fn"]) if item["tp"] + item["fn"] else 1.0
    crit = item["critical_hit"] / item["critical"] if item["critical"] else 1.0
    print(
        f"{language} | {item['tp']} | {item['fp']} | {item['fn']} | "
        f"{precision:.0%} | {recall:.0%} | {crit:.0%}"
    )
print(f"critical symptom recall: {critical_hit}/{critical_total} ({critical_recall:.0%})")
print(f"medication status accuracy: {med_correct}/{med_expected} ({med_accuracy:.0%})")
print(f"vital extraction exact match: {vital_correct}/{vital_expected} ({vital_accuracy:.0%})")
print(f"needs-human safety coverage: {safety_passed}/{safety_expected} ({safety_coverage:.0%})")
print(
    f"expected negation accuracy: {negation_correct}/{negation_expected} ({negation_accuracy:.0%})"
)
print(f"symptom confusion totals: TP={overall_tp}, FP={overall_fp}, FN={overall_fn}")
for error in errors:
    print(error)

if (
    critical_recall < 1.0
    or overall_precision < 0.90
    or med_accuracy < 0.90
    or vital_accuracy < 0.95
    or safety_coverage < 1.0
    or negation_accuracy < 1.0
):
    raise SystemExit(1)
