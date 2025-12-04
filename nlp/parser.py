from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import joblib

TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)
NAME_PATTERN = r"[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)+"
TENURE_EXPRESSION_MAP = {
    "less_than_30": "tenureDays < 30",
    "greater_than_365": "tenureDays >= 365",
}


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
        synonyms: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.intent_clf = joblib.load(model_dir / "intent_classifier.joblib")
        self.intent_encoder = joblib.load(model_dir / "label_encoder.joblib")
        self.slot_vectorizer = joblib.load(model_dir / "slot_vectorizer.joblib")
        self.slot_label_encoder = joblib.load(model_dir / "slot_label_encoder.joblib")
        self.slot_classifier = joblib.load(model_dir / "slot_classifier.joblib")
        if synonyms is not None:
            self.synonyms = synonyms
        else:
            self.synonyms = load_json(synonyms_path)
        self.inverse_synonyms = build_inverse_synonyms(self.synonyms)
        self.employee_names = {
            name.lower(): name for name in self.synonyms.get("employee_names", [])
        }
        self.boolean_values = self.synonyms.get("boolean_values", {})
        self.tenure_phrases = self.synonyms.get("tenure_phrases", {})

    def parse(self, text: str) -> ParseResult:
        tokens, spans = tokenize(text)
        intent_idx = self.intent_clf.predict([text])[0]
        intent = self.intent_encoder.inverse_transform([intent_idx])[0]
        confidence = self._intent_confidence(text, intent_idx)

        slot_labels = self._predict_slot_labels(tokens)
        spans_by_label = self._decode_spans(tokens, spans, slot_labels)
        normalized_slots = self._normalize_slots(spans_by_label, intent)
        intent, normalized_slots = self._apply_rule_inference(text, intent, normalized_slots)
        user_name = normalized_slots.get("user")
        if not user_name:
            inferred_user = self._infer_employee_name(text)
            if inferred_user:
                normalized_slots["user"] = inferred_user
        else:
            canonical = self._canonicalize_employee_name(user_name)
            if canonical:
                normalized_slots["user"] = canonical

        lowered_text = text.lower()
        should_infer_expression = intent == "expression_rule" or (
            not normalized_slots.get("rule_type") and "tenure" in lowered_text
        )
        if should_infer_expression:
            inferred_expression = self._infer_expression(text, normalized_slots)
            if inferred_expression:
                normalized_slots["expression"] = inferred_expression
                expression_action = self._infer_expression_action(lowered_text)
                if expression_action:
                    normalized_slots["expression_action"] = expression_action
                if intent != "expression_rule" and not normalized_slots.get("rule_type"):
                    intent = "expression_rule"

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

        clauses: List[str] = []

        def add_clause(clause: Optional[str]) -> None:
            if clause and clause not in clauses:
                clauses.append(clause)

        active_clause = self._infer_active_clause(lowered)
        add_clause(active_clause)

        employment_value = None
        if slots.get("rule_type") == "employment-type" and slots.get("rule_value"):
            employment_value = slots["rule_value"]
        else:
            employment_match = self._find_synonym_value("employment-type", lowered)
            if employment_match:
                employment_value = employment_match[0]
        if employment_value:
            employment_display = self._format_expression_value("employment-type", employment_value)
            add_clause(f'employmentType == "{employment_display}"')

        location_value = slots.get("location")
        if not location_value:
            location_match = self._find_synonym_value("location", lowered)
            if location_match:
                location_value = location_match[0]
        if location_value:
            location_display = self._format_expression_value("location", location_value)
            add_clause(f'location == "{location_display}"')

        manager_match = self._find_synonym_value("manager", lowered)
        if manager_match and self._has_manager_context(lowered, manager_match[1]):
            manager_display = self._format_expression_value("manager", manager_match[0])
            add_clause(f'manager == "{manager_display}"')

        tag_match = self._find_synonym_value("tags", lowered)
        if tag_match:
            tag_display = self._format_expression_value("tags", tag_match[0])
            add_clause(f'contains(tags, "{tag_display}")')

        tenure_clause = self._extract_tenure_clause(text)
        add_clause(tenure_clause)

        if clauses:
            return " and ".join(clauses)
        return None

    def _infer_employee_name(self, text: str) -> Optional[str]:
        if not self.employee_names:
            return None
        lowered_text = text.lower()
        for key, canonical in self.employee_names.items():
            if key in lowered_text:
                return canonical

        matches = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", text)
        for candidate in matches:
            normalized = candidate.strip()
            canonical = self.employee_names.get(normalized.lower())
            if canonical:
                return canonical
            canonical = self._canonicalize_employee_name(normalized)
            if canonical:
                return canonical
        return None

    def _canonicalize_employee_name(self, name: str) -> Optional[str]:
        if not name:
            return None
        lower = name.strip().lower()
        if lower in self.employee_names:
            return self.employee_names[lower]
        startswith_matches = [
            canonical for key, canonical in self.employee_names.items() if canonical.lower().startswith(lower)
        ]
        if len(startswith_matches) == 1:
            return startswith_matches[0]
        first_name_matches = [
            canonical
            for canonical in self.employee_names.values()
            if canonical.lower().split()[0] == lower.split()[0]
        ]
        if len(first_name_matches) == 1:
            return first_name_matches[0]
        last_name_matches = [
            canonical
            for canonical in self.employee_names.values()
            if canonical.lower().split()[-1] == lower.split()[-1]
        ]
        if len(last_name_matches) == 1:
            return last_name_matches[0]
        return None

    def _find_synonym_value(self, category: str, lowered_text: str) -> Optional[Tuple[str, str]]:
        lookup = self.inverse_synonyms.get(category, {})
        for synonym, canonical in lookup.items():
            if not synonym:
                continue
            pattern = rf"\b{re.escape(synonym)}\b"
            if re.search(pattern, lowered_text):
                return canonical, synonym
            if synonym in lowered_text:
                return canonical, synonym
        return None

    def _contains_phrase(self, lowered_text: str, phrases: Optional[Iterable[str]]) -> bool:
        if not phrases:
            return False
        for phrase in phrases:
            if not phrase:
                continue
            pattern = rf"\b{re.escape(phrase.lower())}\b"
            if re.search(pattern, lowered_text):
                return True
        return False

    def _infer_active_clause(self, lowered_text: str) -> Optional[str]:
        inactive_phrases = self.boolean_values.get("inactive", [])
        active_phrases = self.boolean_values.get("active", [])
        if self._contains_phrase(lowered_text, inactive_phrases):
            return "active == 0"
        if self._contains_phrase(lowered_text, active_phrases):
            return "active == 1"
        return None

    def _extract_tenure_clause(self, text: str) -> Optional[str]:
        lowered = text.lower()
        between = re.search(
            r"(?:between|from)\s+(\d+(?:\.\d+)?)\s+(?:and|to|-)\s+(\d+(?:\.\d+)?)\s+(day|days|month|months|year|years)",
            lowered,
        )
        if between:
            low = self._convert_duration_to_days(
                float(between.group(1)),
                between.group(3),
                direction="ceil",
            )
            high = self._convert_duration_to_days(
                float(between.group(2)),
                between.group(3),
                direction="floor",
            )
            if low and high:
                low, high = sorted((low, high))
                return f"tenureDays >= {low} and tenureDays <= {high}"

        more_pattern = re.search(
            r"(?:over|more than|greater than|at least)\s+(\d+(?:\.\d+)?)\s+(day|days|month|months|year|years)",
            lowered,
        )
        if more_pattern:
            value = self._convert_duration_to_days(
                float(more_pattern.group(1)),
                more_pattern.group(2),
                direction="ceil",
            )
            if value:
                return f"tenureDays >= {value}"

        less_pattern = re.search(
            r"(?:under|less than|fewer than|at most|no more than)\s+(\d+(?:\.\d+)?)\s+(day|days|month|months|year|years)",
            lowered,
        )
        if less_pattern:
            value = self._convert_duration_to_days(
                float(less_pattern.group(1)),
                less_pattern.group(2),
                direction="floor",
            )
            if value:
                return f"tenureDays <= {value}"

        single = re.search(r"(\d+(?:\.\d+)?)\s+(day|days|month|months|year|years)\s+tenure", lowered)
        if single:
            value = self._convert_duration_to_days(
                float(single.group(1)),
                single.group(2),
                direction="ceil",
            )
            if value:
                return f"tenureDays >= {value}"

        for key, phrases in (self.tenure_phrases or {}).items():
            if not phrases:
                continue
            for phrase in phrases:
                if phrase and phrase.lower() in lowered:
                    return TENURE_EXPRESSION_MAP.get(key)
        return None

    def _format_expression_value(self, category: str, value: str) -> str:
        if not value:
            return value
        if category in {"employment-type", "tags", "manager"}:
            return value.title()
        return value

    def _apply_rule_inference(self, text: str, intent: str, slots: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        updates: Dict[str, Any] = {}
        resolved_intent = intent
        lowered_text = text.lower()
        manager_rule_type = (slots.get("rule_type") or "").lower()
        report_match = re.search(
            rf"(?:reporting to|reports to|who report to|under|managed by)\s+(?P<name>{NAME_PATTERN})",
            text,
            re.IGNORECASE,
        )
        if manager_rule_type != "manager" and report_match:
            candidate = self._match_employee_name_fragment(report_match.group("name"))
            if candidate:
                updates["rule_type"] = "manager"
                updates["rule_value"] = candidate
                inferred_intent = self._infer_manager_action(lowered_text)
                if inferred_intent:
                    resolved_intent = inferred_intent

        edit_match = re.search(
            rf"(?:retarget|switch|swap|change)\s+(?:the\s+)?manager rule\s+(?:from\s+)?(?P<from>{NAME_PATTERN})\s+(?:to)\s+(?P<to>{NAME_PATTERN})",
            text,
            re.IGNORECASE,
        )
        if edit_match:
            from_name = self._match_employee_name_fragment(edit_match.group("from"))
            to_name = self._match_employee_name_fragment(edit_match.group("to"))
            if from_name and to_name:
                updates["rule_type"] = "manager"
                updates["from_value"] = from_name
                updates["to_value"] = to_name
                resolved_intent = "edit_rule"

        if updates:
            merged = dict(slots)
            merged.update(updates)
            return self._apply_additional_rule_inference(text, resolved_intent, merged)
        return self._apply_additional_rule_inference(text, resolved_intent, slots)

    def _match_employee_name_fragment(self, fragment: str) -> Optional[str]:
        if not fragment:
            return None
        cleaned = fragment.strip()
        if not cleaned:
            return None
        lower = cleaned.lower()
        if lower in self.employee_names:
            return self.employee_names[lower]
        return self._canonicalize_employee_name(cleaned)

    def _infer_manager_action(self, lowered_text: str) -> Optional[str]:
        remove_keywords = ["remove", "delete", "exclude", "drop"]
        add_keywords = ["add", "include", "ensure", "pull"]
        if any(keyword in lowered_text for keyword in remove_keywords):
            return "remove_rule"
        if any(keyword in lowered_text for keyword in add_keywords):
            return "add_rule"
        return None

    def _infer_expression_action(self, lowered_text: str) -> Optional[str]:
        remove_keywords = ["remove", "exclude", "drop", "less than"]
        add_keywords = ["add", "include", "greater than", "over", "at least"]
        if any(keyword in lowered_text for keyword in remove_keywords):
            return "remove"
        if any(keyword in lowered_text for keyword in add_keywords):
            return "add"
        return None

    def _has_manager_context(self, lowered_text: str, matched_phrase: str) -> bool:
        if not matched_phrase:
            return False
        tokens = [
            r"under\s+" + re.escape(matched_phrase),
            r"reporting\s+to\s+" + re.escape(matched_phrase),
            r"reports\s+to\s+" + re.escape(matched_phrase),
            r"managed\s+by\s+" + re.escape(matched_phrase),
        ]
        return any(re.search(pattern, lowered_text) for pattern in tokens)

    def _convert_duration_to_days(
        self,
        value: float,
        unit: Optional[str],
        *,
        direction: str = "round",
    ) -> Optional[int]:
        if value is None or not unit:
            return None
        normalized = unit.lower()
        mapping = {
            "day": 1,
            "days": 1,
            "month": 30,
            "months": 30,
            "year": 365,
            "years": 365,
        }
        multiplier = mapping.get(normalized)
        if not multiplier:
            return None
        days = value * multiplier
        if direction == "ceil":
            return int(math.ceil(days))
        if direction == "floor":
            return int(math.floor(days))
        return int(round(days))

    def _apply_additional_rule_inference(self, text: str, intent: str, slots: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        lowered = text.lower()
        merged = dict(slots)
        resolved_intent = intent

        # Pre-calc matches for reuse
        employment_matches = self._find_all_synonym_values("employment-type", lowered)

        # Tag-based rules
        if (merged.get("rule_type") or "").lower() != "tag":
            tag_match = re.search(r"(?:tagged|tag)\s+(?P<tag>[A-Za-z0-9_]+)", text, re.IGNORECASE)
            if tag_match:
                canonical_tag = self._match_synonym_value("tags", tag_match.group("tag"))
                if canonical_tag:
                    merged["rule_type"] = "tag"
                    merged["rule_value"] = canonical_tag
                    inferred = self._infer_manager_action(lowered)
                    if inferred:
                        resolved_intent = inferred

        # Location rule edits
        if (merged.get("rule_type") or "").lower() != "location":
            locations = self._find_all_synonym_values("location", lowered)
            if locations and any(word in lowered for word in ["remove", "drop"]):
                merged["rule_type"] = "location"
                merged["rule_value"] = locations[0]
                resolved_intent = "remove_rule"
            elif "location rule" in lowered and len(locations) >= 2:
                merged["rule_type"] = "location"
                merged["from_value"] = locations[0]
                merged["to_value"] = locations[1]
                merged["rule_value"] = locations[1]
                resolved_intent = "edit_rule"

        # Employment-type rule heuristics (remove/edit/add)
        removal_keywords = ["remove", "drop", "delete", "eliminate", "retire"]
        employment_context = any(
            phrase in lowered for phrase in ["employment type", "employment status", "contract type", "employment rule"]
        ) or any(word in lowered for word in removal_keywords)
        if (
            (merged.get("rule_type") or "").lower() != "employment-type"
            and (employment_context or "rule" in lowered)
            and employment_matches
        ):
            if employment_matches:
                if any(word in lowered for word in removal_keywords):
                    merged["rule_type"] = "employment-type"
                    merged["rule_value"] = employment_matches[0]
                    resolved_intent = "remove_rule"
                elif "rule" in lowered and len(employment_matches) >= 2:
                    merged["rule_type"] = "employment-type"
                    merged["from_value"] = employment_matches[0]
                    merged["to_value"] = employment_matches[1]
                    merged["rule_value"] = employment_matches[1]
                    resolved_intent = "edit_rule"
                else:
                    merged["rule_type"] = "employment-type"
                    merged["rule_value"] = employment_matches[-1]
                    inferred = self._infer_manager_action(lowered)
                    resolved_intent = inferred or "add_rule"

        # Directory group edits
        if (merged.get("rule_type") or "").lower() != "directory-group":
            directory_groups = self._find_all_synonym_values("directory-group", lowered)
            if directory_groups:
                removal_keywords = ["remove", "drop", "delete", "eliminate", "retire"]
                if any(word in lowered for word in removal_keywords):
                    merged["rule_type"] = "directory-group"
                    merged["rule_value"] = directory_groups[0]
                    resolved_intent = "remove_rule"
                elif len(directory_groups) >= 2 and re.search(r"(?:replace|switch|swap|change)\s+dl", lowered):
                    merged["rule_type"] = "directory-group"
                    merged["from_value"] = directory_groups[0]
                    merged["to_value"] = directory_groups[1]
                    merged["rule_value"] = directory_groups[1]
                    resolved_intent = "edit_rule"

        return resolved_intent, merged

    def _match_synonym_value(self, category: str, raw: str) -> Optional[str]:
        if not raw:
            return None
        lookup = self.inverse_synonyms.get(category, {})
        return lookup.get(raw.lower(), raw.lower())

    def _find_all_synonym_values(self, category: str, lowered_text: str) -> List[str]:
        lookup = self.inverse_synonyms.get(category, {})
        matches: List[Tuple[int, str]] = []
        for synonym, canonical in lookup.items():
            if not synonym:
                continue
            pattern = rf"\b{re.escape(synonym)}\b"
            for match in re.finditer(pattern, lowered_text):
                matches.append((match.start(), canonical))
        matches.sort(key=lambda item: item[0])
        ordered: List[str] = []
        for _, canonical in matches:
            if canonical not in ordered:
                ordered.append(canonical)
        return ordered

    def _infer_employee_record_changes(self, text: str, intent: str) -> Tuple[List[Dict[str, Any]], List[str]]:
        updates: List[Dict[str, Any]] = []
        clears: List[str] = []
        lowered = text.lower()

        def _matches_toggle(keyword: str) -> bool:
            pattern = rf"(?:make|set|turn|keep|switch|bring|enable)\s+(?:[\w']+\s+){{0,5}}\b{keyword}\b"
            return re.search(pattern, lowered) is not None

        if intent == "employee_record_set":
            if "tenure" in lowered:
                match = re.search(r"(\d+)\s*(?:day|days)", lowered)
                if match:
                    updates.append({"field": "tenureDays", "value": int(match.group(1))})

            inactive_keywords = [
                "deactivate",
                "set inactive",
                "make inactive",
                "turn off",
                "mark inactive",
                "inactive again",
                "disable",
                "switch off",
                "shut off",
                "turn off active status",
                "make inactive again",
            ]
            active_keywords = [
                "activate",
                "reactivate",
                "make active",
                "set active",
                "active again",
                "re-enable",
                "enable",
                "turn on",
                "switch on",
                "back on",
                "back online",
                "bring back online",
            ]

            if any(word in lowered for word in inactive_keywords) or _matches_toggle("inactive"):
                updates.append({"field": "active", "value": False})
            elif any(word in lowered for word in active_keywords) or _matches_toggle("active"):
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
