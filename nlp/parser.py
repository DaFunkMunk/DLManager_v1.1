from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib

TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def tokenize(text: str) -> Tuple[List[str], List[Tuple[int, int]]]:
    tokens: List[str] = []
    spans: List[Tuple[int, int]] = []
    for match in TOKEN_PATTERN.finditer(text):
        tokens.append(match.group())
        spans.append((match.start(), match.end()))
    return tokens, spans


def token_features(tokens: List[str], index: int) -> Dict[str, Any]:
    token = tokens[index]
    features: Dict[str, Any] = {
        "token.lower": token.lower(),
        "token[-3:]": token[-3:],
        "token[-2:]": token[-2:],
        "token.isupper": token.isupper(),
        "token.istitle": token.istitle(),
        "token.isdigit": token.isdigit(),
    }
    if index == 0:
        features["BOS"] = True
    else:
        prev = tokens[index - 1]
        features.update(
            {
                "prev.lower": prev.lower(),
                "prev.istitle": prev.istitle(),
                "prev.isupper": prev.isupper(),
            }
        )
    if index == len(tokens) - 1:
        features["EOS"] = True
    else:
        nxt = tokens[index + 1]
        features.update(
            {
                "next.lower": nxt.lower(),
                "next.istitle": nxt.istitle(),
                "next.isupper": nxt.isupper(),
            }
        )
    return features


def softmax(scores):
    e = math.e ** (scores - scores.max())
    return e / e.sum()


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_inverse_synonyms(data: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    inverse: Dict[str, Dict[str, str]] = {}
    for category, values in data.get("value_synonyms", {}).items():
        inverse.setdefault(category, {})
        for canonical, synonyms in values.items():
            inverse[category][canonical.lower()] = canonical
            for alt in synonyms:
                inverse[category][alt.lower()] = canonical
    return inverse


@dataclass
class ParseResult:
    intent: str
    confidence: float
    slots: Dict[str, Any]
    tokens: List[str]


class IntentSlotParser:
    def __init__(
        self,
        model_dir: Path = Path("models/intent_slot"),
        synonyms_path: Path = Path("nlp_synonyms.json"),
    ) -> None:
        self.intent_clf = joblib.load(model_dir / "intent_classifier.joblib")
        self.intent_encoder = joblib.load(model_dir / "label_encoder.joblib")
        self.slot_vectorizer = joblib.load(model_dir / "slot_vectorizer.joblib")
        self.slot_label_encoder = joblib.load(model_dir / "slot_label_encoder.joblib")
        self.slot_classifier = joblib.load(model_dir / "slot_classifier.joblib")
        self.synonyms = load_json(synonyms_path)
        self.inverse_synonyms = build_inverse_synonyms(self.synonyms)

    def parse(self, text: str) -> ParseResult:
        tokens, spans = tokenize(text)
        intent_idx = self.intent_clf.predict([text])[0]
        intent = self.intent_encoder.inverse_transform([intent_idx])[0]
        confidence = self._intent_confidence(text, intent_idx)

        slot_labels = self._predict_slot_labels(tokens)
        spans_by_label = self._decode_spans(tokens, spans, slot_labels)
        normalized_slots = self._normalize_slots(spans_by_label, intent)

        if intent == "expression_rule" and "expression" not in normalized_slots:
            inferred = self._infer_expression(text, normalized_slots)
            if inferred:
                normalized_slots["expression"] = inferred

        if intent in {"employee_record_set", "employee_record_clear"}:
            updates, clears = self._infer_employee_record_changes(text, intent)
            if updates:
                normalized_slots["record_updates"] = updates
            if clears:
                normalized_slots["record_clears"] = clears

        return ParseResult(
            intent=intent,
            confidence=confidence,
            slots=normalized_slots,
            tokens=tokens,
        )

    def _intent_confidence(self, text: str, intent_idx: int) -> float:
        if hasattr(self.intent_clf, "predict_proba"):
            probs = self.intent_clf.predict_proba([text])[0]
            return float(probs[intent_idx])
        if hasattr(self.intent_clf, "decision_function"):
            scores = self.intent_clf.decision_function([text])[0]
            try:
                probs = softmax(scores)
                return float(probs[intent_idx])
            except Exception:
                pass
        return 0.0

    def _predict_slot_labels(self, tokens: List[str]) -> List[str]:
        feats = [token_features(tokens, idx) for idx in range(len(tokens))]
        X = self.slot_vectorizer.transform(feats)
        y = self.slot_classifier.predict(X)
        return self.slot_label_encoder.inverse_transform(y)

    def _decode_spans(
        self,
        tokens: List[str],
        spans: List[Tuple[int, int]],
        labels: List[str],
    ) -> Dict[str, str]:
        collected: Dict[str, str] = {}
        current_label: Optional[str] = None
        current_tokens: List[str] = []

        for token, label in zip(tokens, labels):
            if label == "O":
                if current_label:
                    collected[current_label] = " ".join(current_tokens)
                    current_label = None
                    current_tokens = []
                continue
            prefix, tag = label.split("-", 1)
            if prefix == "B" or tag != current_label:
                if current_label and current_tokens:
                    collected[current_label] = " ".join(current_tokens)
                current_label = tag
                current_tokens = [token]
            else:
                current_tokens.append(token)

        if current_label and current_tokens:
            collected[current_label] = " ".join(current_tokens)
        return collected

    def _normalize_slots(self, spans: Dict[str, str], intent: str) -> Dict[str, Any]:
        slots: Dict[str, Any] = {}
        if "USER" in spans:
            slots["user"] = spans["USER"].strip()
        if "GROUP" in spans:
            slots["group"] = spans["GROUP"].strip().replace(" - ", "-")
        if "LOCATION" in spans:
            slots["location"] = self._canonical_value("location", spans["LOCATION"])
        if "RULE_VALUE" in spans:
            value, category = self._canonical_rule_value(spans["RULE_VALUE"])
            slots["rule_value"] = value
            if category:
                slots["rule_type"] = category
        slots["intent_hint"] = intent
        return {k: v for k, v in slots.items() if v}

    def _canonical_value(self, category: str, raw: str) -> str:
        lookup = self.inverse_synonyms.get(category, {})
        return lookup.get(raw.lower(), raw)

    def _canonical_rule_value(self, raw: str) -> Tuple[str, Optional[str]]:
        raw_lower = raw.lower()
        for category, lookup in self.inverse_synonyms.items():
            if raw_lower in lookup:
                return lookup[raw_lower], category
        return raw, None

    def _infer_expression(self, text: str, slots: Dict[str, Any]) -> Optional[str]:
        lowered = text.lower()

        # Catch-all cases: "all users", "everyone", etc -> active == true
        keywords = ["all user", "everyone", "entire company", "whole company", "every user", "all employees"]
        if any(phrase in lowered for phrase in keywords):
            return "active == 1"

        # Heuristic: if we already have employment-type/location slots, build expression
        parts: List[str] = []
        rule_type = slots.get("rule_type")
        if rule_type == "employment-type" and slots.get("rule_value"):
            parts.append(f'employmentType == "{slots["rule_value"]}"')
        if slots.get("location"):
            parts.append(f'location == "{slots["location"]}"')
        if parts:
            return " and ".join(parts)
        return None

    def _infer_employee_record_changes(self, text: str, intent: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        updates: List[Dict[str, Any]] = []
        clears: List[str] = []
        lowered = text.lower()

        if intent == "employee_record_set":
            if "tenure" in lowered:
                match = re.search(r"(\d+)\s*(?:day|days)", lowered)
                if match:
                    updates.append({"field": "tenureDays", "value": int(match.group(1))})

            if any(word in lowered for word in ["deactivate", "set inactive", "make inactive", "turn off"]):
                updates.append({"field": "active", "value": False})
            elif any(word in lowered for word in ["activate", "reactivate", "make active", "set active"]):
                updates.append({"field": "active", "value": True})

            manager = self._match_canonical_value("manager", lowered)
            if manager and "manager" in lowered:
                updates.append({"field": "manager", "value": manager})

            location = self._match_canonical_value("location", lowered)
            if location and any(word in lowered for word in ["location", "office", "move to", "assign to"]):
                updates.append({"field": "location", "value": location})

        if intent == "employee_record_clear":
            field_map = {
                "tenure": "tenureDays",
                "location": "location",
                "manager": "manager",
                "role": "role",
                "employment": "employmentType",
                "status": "active",
            }
            if any(word in lowered for word in ["clear", "remove", "wipe"]):
                for keyword, field_name in field_map.items():
                    if keyword in lowered:
                        clears.append(field_name)

        return updates, clears

    def _match_canonical_value(self, category: str, lowered_text: str) -> Optional[str]:
        lookup = self.inverse_synonyms.get(category, {})
        for key, canonical in lookup.items():
            if key in lowered_text:
                return canonical
        return None
