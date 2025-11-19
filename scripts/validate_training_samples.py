"""Validate training samples against the current intent parser.

This script replays the utterances stored in training_samples.jsonl and
compares the model output with the expected intent/slots. Results are printed
to stdout and stored in a JSONL log file for future reference.

Usage examples:

    # Validate every sample with the local parser (default)
    python scripts/validate_training_samples.py

    # Only check employee_record_set utterances with active toggles
    python scripts/validate_training_samples.py --intent employee_record_set --field active

    # Use the running API instead of the local parser (requires an authenticated session)
    python scripts/validate_training_samples.py --mode api --base-url http://127.0.0.1:5000
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from urllib import request, error as urlerror
except ImportError:  # pragma: no cover
    request = None  # type: ignore
    urlerror = None  # type: ignore

SCRIPT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SAMPLES = SCRIPT_ROOT / "training_samples.jsonl"
LOG_DIR = SCRIPT_ROOT / "validation_logs"

OPTIONAL_SLOTS = {
    "rule_type",
    "rule_value",
    "group",
    "location",
    "from_value",
    "to_value",
}

CASE_INSENSITIVE_SLOTS = {
    "user",
    "group",
    "rule_value",
    "from_value",
    "to_value",
    "location",
}


@dataclass
class Sample:
    text: str
    intent: str
    slots: Dict[str, Any]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate training samples with the intent parser.")
    parser.add_argument(
        "--samples",
        type=Path,
        default=DEFAULT_SAMPLES,
        help=f"Path to the training samples JSONL file (default: {DEFAULT_SAMPLES})",
    )
    parser.add_argument(
        "--intent",
        action="append",
        default=None,
        help="Only validate samples with the specified intent (repeatable). If omitted, all samples are tested.",
    )
    parser.add_argument(
        "--field",
        action="append",
        default=None,
        help="Only validate samples whose field_updates/record_updates include the given field name (repeatable).",
    )
    parser.add_argument(
        "--skip-intent",
        action="append",
        default=None,
        help="Intent names to treat as informational only (failures become warnings when intent mismatches).",
    )
    parser.add_argument(
        "--mode",
        choices=("local", "api"),
        default="local",
        help="Use the local parser (default) or call the running API (requires authenticated session).",
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:5000",
        help="Base URL for API mode (defaults to http://127.0.0.1:5000).",
    )
    parser.add_argument(
        "--cookie",
        default=None,
        help="Optional Cookie header value when calling the API (e.g., 'session=<token>').",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="Optional path for the JSONL log file. Default is validation_logs/<timestamp>.jsonl.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-sample results even when they pass.",
    )
    return parser.parse_args()


def load_samples(path: Path) -> List[Sample]:
    if not path.exists():
        raise FileNotFoundError(f"Training samples file not found: {path}")
    samples: List[Sample] = []
    with path.open("r", encoding="utf-8") as handle:
        for idx, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {idx} of {path}: {exc}") from exc
            samples.append(
                Sample(
                    text=payload.get("text", ""),
                    intent=payload.get("intent", ""),
                    slots=payload.get("slots") or {},
                )
            )
    return samples


def filter_samples(samples: Iterable[Sample], intents: Optional[List[str]], fields: Optional[List[str]]) -> List[Sample]:
    def matches(sample: Sample) -> bool:
        if intents and sample.intent not in intents:
            return False
        if fields:
            updates = _normalize_slots(sample.slots).get("record_updates") or []
            update_fields = {entry.get("field") for entry in updates if isinstance(entry, dict)}
            if not any(field in update_fields for field in fields):
                return False
        return True

    return [sample for sample in samples if matches(sample)]


def _normalize_updates(entries: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
    if not isinstance(entries, list):
        return entries
    cleaned: List[Dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        normalized = dict(entry)
        value = normalized.get("value")
        if isinstance(value, str):
            normalized["value"] = value.strip().lower()
        cleaned.append(normalized)
    return cleaned


def _normalize_slots(slots: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    normalized = dict(slots or {})
    if "field_updates" in normalized and "record_updates" not in normalized:
        normalized["record_updates"] = normalized["field_updates"]
    if "field_updates" in normalized:
        normalized.pop("field_updates", None)
    if "fields_to_clear" in normalized and "record_clears" not in normalized:
        normalized["record_clears"] = normalized["fields_to_clear"]
    if "fields_to_clear" in normalized:
        normalized.pop("fields_to_clear", None)
    if "record_updates" in normalized:
        normalized["record_updates"] = _normalize_updates(normalized.get("record_updates"))
    if "record_clears" in normalized:
        normalized["record_clears"] = _normalize_updates(normalized.get("record_clears"))
    return normalized


def _normalize_structure(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _normalize_structure(value[k]) for k in sorted(value.keys())}
    if isinstance(value, list):
        normalized_list = [_normalize_structure(item) for item in value]
        try:
            return sorted(normalized_list, key=lambda item: json.dumps(item, sort_keys=True))
        except TypeError:
            return normalized_list
    if isinstance(value, str):
        return value.strip()
    return value


def _normalize_expression(expr: str) -> Tuple[str, ...]:
    if not isinstance(expr, str):
        return tuple()
    parts = [part.strip().lower() for part in re.split(r"\s+and\s+", expr) if part.strip()]
    return tuple(sorted(parts))


def _values_equal(expected: Any, actual: Any) -> bool:
    return _normalize_structure(expected) == _normalize_structure(actual)


def _compare_slots(expected: Dict[str, Any], actual: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        if (
            isinstance(expected_value, str)
            and isinstance(actual_value, str)
            and key in CASE_INSENSITIVE_SLOTS
        ):
            if expected_value.strip().lower() != actual_value.strip().lower():
                target = warnings if key in OPTIONAL_SLOTS else errors
                target.append(
                    f"slot '{key}' mismatch (expected={expected_value!r}, actual={actual_value!r})"
                )
            continue
        if (
            key == "expression"
            and isinstance(expected_value, str)
            and isinstance(actual_value, str)
        ):
            if _normalize_expression(expected_value) != _normalize_expression(actual_value):
                target = warnings if key in OPTIONAL_SLOTS else errors
                target.append(
                    f"slot '{key}' mismatch (expected={expected_value!r}, actual={actual_value!r})"
                )
            continue
        if not _values_equal(expected_value, actual_value):
            target = warnings if key in OPTIONAL_SLOTS else errors
            target.append(f"slot '{key}' mismatch (expected={expected_value!r}, actual={actual_value!r})")
    return errors, warnings


def _call_api(text: str, base_url: str, cookie_header: Optional[str]) -> Dict[str, Any]:
    if request is None or urlerror is None:
        raise RuntimeError("urllib not available; cannot call API mode.")
    payload = json.dumps({"text": text}).encode("utf-8")
    headers = {"Content-Type": "application/json", "X-Mode": "demo"}
    if cookie_header:
        headers["Cookie"] = cookie_header
    req = request.Request(
        url=f"{base_url.rstrip('/')}/api/nlp/parse",
        data=payload,
        headers=headers,
        method="POST",
    )
    try:
        with request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urlerror.HTTPError as exc:
        raise RuntimeError(f"API request failed ({exc.code}): {exc.read().decode('utf-8', errors='ignore')}") from exc


def _call_local_parser(text: str):
    sys.path.append(str(SCRIPT_ROOT))
    from nlp.parser import IntentSlotParser  # pylint: disable=import-outside-toplevel

    parser = getattr(_call_local_parser, "_parser", None)
    if parser is None:
        parser = IntentSlotParser(model_dir=Path("models/intent_slot"), synonyms_path=Path("nlp_synonyms.json"))
        setattr(_call_local_parser, "_parser", parser)
    return parser.parse(text).__dict__


def determine_log_path(explicit: Optional[Path]) -> Path:
    if explicit:
        return explicit
    LOG_DIR.mkdir(exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    return LOG_DIR / f"validation_{timestamp}.jsonl"


def main() -> None:
    args = parse_args()
    samples = load_samples(args.samples)
    filtered = filter_samples(samples, args.intent, args.field)
    if not filtered:
        print("No samples matched the provided filters.", file=sys.stderr)
        sys.exit(1)

    executor = (
        _call_local_parser
        if args.mode == "local"
        else lambda text: _call_api(text, args.base_url, args.cookie)
    )
    log_path = determine_log_path(args.log_file)

    successes = 0
    failures = 0
    log_entries: List[str] = []
    expression_failures: List[str] = []

    for sample in filtered:
        run_timestamp = datetime.utcnow().isoformat() + "Z"
        try:
            response = executor(sample.text)
        except Exception as exc:  # pragma: no cover - defensive
            failures += 1
            message = f"[ERROR] \"{sample.text}\" -> {exc}"
            print(message)
            log_entries.append(json.dumps({"text": sample.text, "error": str(exc), "success": False, "timestamp": run_timestamp}))
            continue

        actual_intent = response.get("intent", "")
        actual_slots = _normalize_slots(response.get("slots"))
        expected_slots = _normalize_slots(sample.slots)
        if expected_slots.get("expression") and not actual_slots.get("expression"):
            expression_failures.append(sample.text)

        intent_match = sample.intent == actual_intent
        intent_warning = False
        if not intent_match and args.skip_intent and sample.intent in args.skip_intent:
            intent_warning = True
            intent_match = True
        slot_errors, slot_warnings = _compare_slots(expected_slots, actual_slots)
        success = intent_match and not slot_errors

        if success:
            successes += 1
            if args.verbose:
                print(f"[PASS] \"{sample.text}\"")
            if slot_warnings:
                print(f"[WARN] \"{sample.text}\": {'; '.join(slot_warnings)}")
            if args.verbose and intent_warning:
                print(f"[WARN] \"{sample.text}\": intent mismatch ignored (expected={sample.intent}, actual={actual_intent})")
        else:
            failures += 1
            detail_lines = []
            if not intent_match:
                detail_lines.append(f"intent mismatch (expected={sample.intent}, actual={actual_intent})")
            detail_lines.extend(slot_errors)
            detail = "; ".join(detail_lines) or "Unknown mismatch"
            print(f"[FAIL] \"{sample.text}\": {detail}")
            if slot_warnings:
                print(f"        (warnings: {'; '.join(slot_warnings)})")

        log_entries.append(
            json.dumps(
                {
                    "text": sample.text,
                    "success": success,
                    "timestamp": run_timestamp,
                    "intent_expected": sample.intent,
                    "intent_actual": actual_intent,
                    "slot_errors": slot_errors,
                    "slot_warnings": slot_warnings,
                }
            )
        )

    with log_path.open("w", encoding="utf-8") as handle:
        handle.write("\n".join(log_entries))

    total = successes + failures
    print(f"\nValidation complete: {successes}/{total} passed. Log written to {log_path}")
    if expression_failures:
        print("Missing expressions for:")
        for text in expression_failures:
            print(f"  - {text}")
    sys.exit(0 if failures == 0 else 1)


if __name__ == "__main__":
    main()
