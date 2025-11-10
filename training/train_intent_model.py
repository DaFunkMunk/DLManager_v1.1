"""
Prototype spaCy/sklearn pipeline for intent + slot parsing.

Usage:
    python training/train_intent_model.py \
        --data training_samples.jsonl \
        --model-out models/intent_slot
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder

TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def tokenize(text: str) -> Tuple[List[str], List[Tuple[int, int]]]:
    tokens: List[str] = []
    spans: List[Tuple[int, int]] = []
    for match in TOKEN_PATTERN.finditer(text):
        tokens.append(match.group())
        spans.append((match.start(), match.end()))
    return tokens, spans


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_dataset(path: Path) -> Tuple[List[str], List[str], List[Dict]]:
    texts: List[str] = []
    intents: List[str] = []
    records: List[Dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            texts.append(record["text"])
            intents.append(record["intent"])
            records.append(record)
    return texts, intents, records


def train_intent_classifier(texts: List[str], intents: List[str]) -> Tuple[Pipeline, LabelEncoder]:
    label_encoder = LabelEncoder()
    y = label_encoder.fit_transform(intents)
    clf = Pipeline(
        steps=[
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
            ("logreg", LogisticRegression(max_iter=1000, multi_class="auto"))
        ]
    )
    clf.fit(texts, y)
    return clf, label_encoder


def candidate_phrases(category: str, canonical: str, synonyms: Dict[str, Any]) -> List[str]:
    canonical = canonical or ""
    values = synonyms.get("value_synonyms", {}).get(category, {})
    variations = values.get(canonical.lower(), [])
    return list(dict.fromkeys([canonical] + variations))


def match_span(text: str, phrases: List[str]) -> Tuple[int, int]:
    lowered = text.lower()
    for phrase in phrases:
        if not phrase:
            continue
        idx = lowered.find(phrase.lower())
        if idx != -1:
            return idx, idx + len(phrase)
    return (-1, -1)


def label_span(
    labels: List[str],
    token_spans: List[Tuple[int, int]],
    span: Tuple[int, int],
    label_prefix: str,
) -> None:
    start, end = span
    if start < 0:
        return
    begun = False
    for idx, (tok_start, tok_end) in enumerate(token_spans):
        if tok_end <= start or tok_start >= end:
            continue
        labels[idx] = f"B-{label_prefix}" if not begun else f"I-{label_prefix}"
        begun = True


def build_slot_sequences(
    records: List[Dict],
    synonyms: Dict[str, Any],
) -> Tuple[List[List[str]], List[List[str]]]:
    tokens_all: List[List[str]] = []
    labels_all: List[List[str]] = []
    for record in records:
        text = record["text"]
        slots = record.get("slots", {})
        tokens, spans = tokenize(text)
        labels = ["O"] * len(tokens)

        if "user" in slots:
            span = match_span(text, [slots["user"]])
            label_span(labels, spans, span, "USER")

        if "group" in slots:
            span = match_span(text, [slots["group"]])
            label_span(labels, spans, span, "GROUP")

        if "location" in slots:
            span = match_span(text, candidate_phrases("location", slots["location"], synonyms))
            label_span(labels, spans, span, "LOCATION")

        if "rule_value" in slots:
            category = slots.get("rule_type") or "rule_value"
            span = match_span(text, candidate_phrases(category, slots["rule_value"], synonyms))
            label_span(labels, spans, span, "RULE_VALUE")

        tokens_all.append(tokens)
        labels_all.append(labels)
    return tokens_all, labels_all


def token_features(tokens: List[str], index: int) -> Dict[str, Any]:
    token = tokens[index]
    feats: Dict[str, Any] = {
        "token.lower": token.lower(),
        "token[-3:]": token[-3:],
        "token[-2:]": token[-2:],
        "token.isupper": token.isupper(),
        "token.istitle": token.istitle(),
        "token.isdigit": token.isdigit(),
    }
    if index == 0:
        feats["BOS"] = True
    else:
        prev = tokens[index - 1]
        feats.update(
            {
                "prev.lower": prev.lower(),
                "prev.istitle": prev.istitle(),
                "prev.isupper": prev.isupper(),
            }
        )
    if index == len(tokens) - 1:
        feats["EOS"] = True
    else:
        nxt = tokens[index + 1]
        feats.update(
            {
                "next.lower": nxt.lower(),
                "next.istitle": nxt.istitle(),
                "next.isupper": nxt.isupper(),
            }
        )
    return feats


def train_slot_classifier(
    token_sequences: List[List[str]],
    label_sequences: List[List[str]],
) -> Tuple[DictVectorizer, LabelEncoder, LogisticRegression]:
    feature_dicts: List[Dict[str, Any]] = []
    label_list: List[str] = []

    for tokens, labels in zip(token_sequences, label_sequences):
        for idx, label in enumerate(labels):
            feature_dicts.append(token_features(tokens, idx))
            label_list.append(label)

    vectorizer = DictVectorizer(sparse=True)
    X = vectorizer.fit_transform(feature_dicts)

    label_encoder = LabelEncoder()
    y = label_encoder.fit_transform(label_list)

    clf = LogisticRegression(max_iter=1000, multi_class="auto")
    clf.fit(X, y)
    return vectorizer, label_encoder, clf


def main() -> None:
    parser = argparse.ArgumentParser(description="Train intent + slot models.")
    parser.add_argument("--data", type=Path, default=Path("training_samples.jsonl"))
    parser.add_argument("--model-out", type=Path, default=Path("models/intent_slot"))
    parser.add_argument("--synonyms", type=Path, default=Path("nlp_synonyms.json"))
    args = parser.parse_args()

    texts, intents, records = load_dataset(args.data)
    intent_clf, intent_encoder = train_intent_classifier(texts, intents)

    synonyms = load_json(args.synonyms)
    token_sequences, label_sequences = build_slot_sequences(records, synonyms)
    slot_vectorizer, slot_label_encoder, slot_clf = train_slot_classifier(token_sequences, label_sequences)

    args.model_out.mkdir(parents=True, exist_ok=True)
    joblib.dump(intent_clf, args.model_out / "intent_classifier.joblib")
    joblib.dump(intent_encoder, args.model_out / "label_encoder.joblib")
    joblib.dump(slot_vectorizer, args.model_out / "slot_vectorizer.joblib")
    joblib.dump(slot_label_encoder, args.model_out / "slot_label_encoder.joblib")
    joblib.dump(slot_clf, args.model_out / "slot_classifier.joblib")

    total_tokens = sum(len(seq) for seq in token_sequences)
    print(f"Trained intent classifier on {len(texts)} samples.")
    print(f"Trained slot classifier on {total_tokens} tokens.")


if __name__ == "__main__":
    main()
