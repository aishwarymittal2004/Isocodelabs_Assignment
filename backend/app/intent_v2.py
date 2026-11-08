"""SitePilot portable TF-IDF + linear SVM intent inference (stdlib only).

This is an optional classifier fallback. It neither produces AI responses
nor executes actions. Trained on synthetic text; output margin is not a probability.
"""
from __future__ import annotations

import gzip
import json
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

V2_MODEL_PATH = Path(__file__).resolve().parent.parent / "training" / "intent_model_v2.json.gz"
_WORD = re.compile(r"(?u)\b\w+\b")
_SPACES = re.compile(r"\s\s+")


@lru_cache(maxsize=1)
def _model():
    with gzip.open(V2_MODEL_PATH, "rt", encoding="utf-8") as f:
        payload = json.load(f)
    if payload.get("format") != "sitepilot-tfidf-linear-svm-v1":
        raise ValueError("Unsupported SitePilot intent model format")
    return payload


def _terms(text: str, component: dict):
    lo, hi = component["ngram_range"]
    if component["analyzer"] == "word":
        tokens = _WORD.findall(text.lower())
        for n in range(lo, hi + 1):
            for i in range(len(tokens) - n + 1):
                yield " ".join(tokens[i:i + n])
    elif component["analyzer"] == "char":
        text = _SPACES.sub(" ", text.lower())
        for n in range(lo, min(hi, len(text)) + 1):
            for i in range(len(text) - n + 1):
                yield text[i:i + n]
    else:
        raise ValueError("Unsupported feature analyzer")


def classify_intent_v2(message: str) -> tuple[str, float]:
    """Return predicted intent and relative SVM margin (NOT confidence).

    No match returns unknown. Use deterministic routing for consequential
    actions including booking, cancellation, consent, and human handoff.
    """
    if not isinstance(message, str) or not message.strip():
        return "unknown", 0.0
    model = _model()
    classes = model["labels"]
    scores = list(model["intercepts"])
    feature_offset = 0
    found_any = False
    for component in model["components"]:
        vocab = component["vocabulary"]
        idf = component["idf"]
        counts = Counter(vocab[term] for term in _terms(message, component) if term in vocab)
        if counts:
            found_any = True
            raw = [(idx, (1.0 + math.log(n)) * idf[idx]) for idx, n in counts.items()]
            norm = math.sqrt(sum(w*w for _, w in raw))
            for idx, val in raw:
                scaled = val/norm
                for class_index in range(len(classes)):
                    scores[class_index] += model["weights"][class_index][feature_offset + idx] * scaled
        feature_offset += len(vocab)
    if not found_any:
        return "unknown", 0.0
    ordered = sorted(range(len(classes)), key=lambda i: scores[i], reverse=True)
    return classes[ordered[0]], float(scores[ordered[0]] - scores[ordered[1]])
