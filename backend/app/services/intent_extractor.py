import re
from typing import Any

SYMPTOMS: dict[str, tuple[str, ...]] = {
    "chest_pain": (
        "ఛాతీ నొప్పి",
        "ఛాతిలో నొప్పి",
        "ఛాతీలో నొప్పి",
        "सीने में दर्द",
        "chest pain",
        "pain in chest",
        "chaati noppi",
        "chaati noppiga",
    ),
    "breathlessness": (
        "ఊపిరి ఆడటం లేదు",
        "ఆయాసం",
        "साँस फूल",
        "सांस फूल",
        "साँस लेने में तकलीफ़",
        "सांस लेने में तकलीफ",
        "saans phool",
        "ayasam",
        "short of breath",
        "can't breathe",
        "breathless",
    ),
    "fainting": ("స్పృహ తప్పింది", "మూర్ఛ", "बेहोश", "बेहोशी", "fainted", "passed out", "moorcha"),
    "confusion": ("గందరగోళం", "తికమక", "भ्रम", "उलझन", "confused", "disoriented"),
    "one_sided_weakness": (
        "ఒక వైపు బలహీనం",
        "చేయి కాలు పనిచేయడం లేదు",
        "एक तरफ़ कमज़ोरी",
        "हाथ पैर नहीं चल",
        "हाथ-पैर नहीं चल",
        "weakness on one side",
        "arm weak",
        "left arm feels weak",
    ),
    "slurred_speech": (
        "మాట తడబడుతోంది",
        "మాట రావడం లేదు",
        "बोलने में दिक्कत",
        "slurred speech",
        "can't speak properly",
        "speech is slurred",
        "ज़ुबान लड़खड़",
        "जुबान लड़खड़",
    ),
    "leg_swelling": (
        "కాళ్ళు వాచాయి",
        "కాళ్ళ వాపు",
        "పాదాలు వాచాయి",
        "వాచాయి",
        "पैरों में सूजन",
        "swollen legs",
        "swollen feet",
    ),
    "dizziness": ("కళ్ళు తిరుగుతున్నాయి", "తల తిరుగుతోంది", "चक्कर", "chakkar", "dizzy", "giddy"),
    "sweating_shaking": ("చెమటలు", "వణుకు", "पसीना", "काँप", "sweating", "shaking", "shaky"),
    "severe_headache": ("తీవ్రమైన తలనొప్పి", "तेज़ सिरदर्द", "severe headache", "bad headache"),
    "vision_change": ("చూపు మసక", "धुंधला दिख", "blurred vision", "vision change"),
    "excessive_thirst": ("దాహం ఎక్కువ", "बहुत प्यास", "very thirsty", "excessive thirst"),
    "frequent_urination": ("తరచుగా మూత్రం", "बार बार पेशाब", "frequent urination"),
    "palpitations": ("గుండె వేగంగా", "दिल तेज़", "palpitations", "heart racing"),
    "nausea_vomiting": ("వాంతులు", "उल्टी", "vomiting", "nausea"),
    "fever": ("జ్వరం", "बुखार", "fever"),
    "foot_wound": ("పాదానికి గాయం", "पैर में घाव", "foot wound", "foot ulcer"),
    "reduced_urine": ("మూత్రం తగ్గింది", "पेशाब कम", "less urine", "reduced urine"),
    "fatigue": ("అలసట", "थकान", "fatigue", "tired"),
}
CRITICAL = {
    "chest_pain",
    "breathlessness",
    "fainting",
    "confusion",
    "one_sided_weakness",
    "slurred_speech",
}
NEGATIONS = ("లేదు", "లేవు", "కాదు", "नहीं", "नही", "no", "not", "without")
MED_TAKEN = (
    "మాత్ర వేసుకున్నాను",
    "వేసుకున్నాను",
    "दवा ली",
    "दवा ले ली",
    "दवाई ली",
    "took",
    "taken",
)
MED_MISSED = (
    "మాత్ర వేసుకోలేదు",
    "వేసుకోలేదు",
    "दवा नहीं ली",
    "दवाई नहीं ली",
    "dawa nahi li",
    "not taken",
    "haven't taken",
    "have not taken",
    "didn't take",
    "did not take",
    "forgot",
    "skipped",
)


def _number(text: str, pattern: str) -> float | None:
    match = re.search(pattern, text, re.I)
    return float(match.group(1)) if match else None


class IntentExtractor:
    @staticmethod
    def _near_negation(normalized: str, phrase: str) -> bool:
        start = normalized.find(phrase.lower())
        end = start + len(phrase)
        before_text = normalized[max(0, start - 100) : start]
        after_text = normalized[end : end + 100]
        clauses = (
            " but ",
            " however ",
            " although ",
            " though ",
            " لیکن ",
            " लेकिन ",
            " కానీ ",
            ".",
            "!",
            "?",
            ";",
            "\n",
            ",",
            " just ",
        )
        last_clause = max((before_text.rfind(clause) for clause in clauses), default=-1)
        if last_clause >= 0:
            before_text = before_text[last_clause + 1 :]
        first_clause = min(
            (after_text.find(clause) for clause in clauses if clause in after_text), default=-1
        )
        if first_clause >= 0:
            after_text = after_text[:first_clause]
        # Unicode combining marks in Indic scripts split under Python's \w token class.
        # Use a bounded character window instead so Telugu/Hindi negations remain intact.
        neighborhood = f"{before_text[-60:]} {after_text[:60]}"
        for word in NEGATIONS:
            if word in {"no", "not", "without"}:
                if re.search(rf"\b{re.escape(word)}\b", neighborhood):
                    return True
            elif word in neighborhood:
                return True
        return False

    def extract(
        self, text: str | None, language: str = "en", quick_reply: str | None = None
    ) -> dict[str, Any]:
        raw = (text or "")[:1000]
        normalized = raw.lower()
        symptoms = []
        needs_human = not bool(raw)
        for code, phrases in SYMPTOMS.items():
            matched = next((phrase for phrase in phrases if phrase.lower() in normalized), None)
            if matched:
                negated = self._near_negation(normalized, matched)
                if code in CRITICAL and normalized.count(matched.lower()) > 1:
                    negated = False
                symptoms.append(
                    {
                        "code": code,
                        "raw": matched,
                        "severity_hint": "unknown" if code in CRITICAL else "mild",
                        "negated": negated,
                    }
                )
                if code in CRITICAL and negated:
                    needs_human = True

        # Independent safety net: critical phrases are rechecked regardless of provider output.
        for code in CRITICAL:
            if code not in {item["code"] for item in symptoms}:
                phrase = next((p for p in SYMPTOMS[code] if p.lower() in normalized), None)
                if phrase:
                    symptoms.append(
                        {"code": code, "raw": phrase, "severity_hint": "unknown", "negated": False}
                    )

        med_status = None
        says_missed = any(term in normalized for term in MED_MISSED)
        says_taken = any(term in normalized for term in MED_TAKEN)
        if quick_reply in {"yes_taken", "not_taken"}:
            med_status = "missed" if quick_reply == "not_taken" or says_missed else "taken"
            if (quick_reply == "yes_taken" and says_missed) or (
                quick_reply == "not_taken" and says_taken and not says_missed
            ):
                needs_human = True
        elif says_missed:
            med_status = "missed"
            if says_taken:
                needs_human = True
        elif says_taken:
            med_status = "taken"

        vitals = []
        bp_match = re.search(r"\b(\d{2,3})\s*/\s*(\d{2,3})\b", raw)
        if bp_match:
            systolic, diastolic = int(bp_match.group(1)), int(bp_match.group(2))
            if 50 <= systolic <= 260 and 30 <= diastolic <= 160:
                vitals.append(
                    {"type": "bp", "systolic": systolic, "diastolic": diastolic, "unit": "mmHg"}
                )
            else:
                needs_human = True
        glucose = (
            _number(raw, r"\b(\d{2,3}(?:\.\d+)?)\s*(?:mg/dl|mg|sugar|glucose)?\b")
            if any(w in normalized for w in ("sugar", "glucose", "షుగర్", "शुगर"))
            else None
        )
        if glucose is not None:
            if 20 <= glucose <= 800:
                vitals.append(
                    {"type": "glucose", "value": glucose, "unit": "mg/dL", "context": "unknown"}
                )
            else:
                needs_human = True

        injection_or_dose = any(
            w in normalized
            for w in (
                "you are now a doctor",
                "ignore previous instructions",
                "double my dose",
                "increase my dose",
                "tell me to",
                "set severity",
                "dose",
            )
        )
        medical_question = (
            injection_or_dose
            or "?" in raw
            or any(
                w in normalized
                for w in ("can i", "should i", "stop my", "దవా", "మాత్ర ఆప", "क्या मैं", "दवा बंद")
            )
        )
        if injection_or_dose:
            needs_human = True
        intents = []
        if med_status:
            intents.append("medication_report")
        if symptoms:
            intents.append("symptom_report")
        if vitals:
            intents.append("vital_report")
        if medical_question:
            intents.append("question")
        if not intents:
            intents.append("other")
            needs_human = True
        confidence = 0.9 if not needs_human else 0.0 if not raw else 0.55
        return {
            "language": language if language in {"te", "hi", "en"} else "en",
            "intents": intents,
            "medication_events": (
                [{"med_id": None, "status": med_status, "slot": "morning"}] if med_status else []
            ),
            "symptoms": symptoms,
            "vitals": vitals,
            "meal": None,
            "question": {"text": raw, "category": "medical"} if medical_question else None,
            "confidence": confidence,
            "needs_human": needs_human,
        }
