"""Tiny intent classifier trained on synthetic examples; no remote API.
This is a fallback, not a conversational foundation model. It does not
make booking decisions, approve facts, or infer psychological traits.
"""
import json
import os
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

MODEL_PATH = Path(__file__).resolve().parent.parent / 'training' / 'intent_model.json'

def tokenize(text):
    return re.findall(r"[^\W_]+", text.casefold(), flags=re.UNICODE)

def train(rows):
    counts=Counter(); tokens=defaultdict(Counter); vocabulary=set()
    for row in rows:
        label=row['intent']; counts[label]+=1
        words=set(tokenize(row['message']))
        tokens[label].update(words); vocabulary.update(words)
    return {'counts':dict(counts), 'tokens':{k:dict(v) for k,v in tokens.items()}, 'vocabulary':sorted(vocabulary)}

def classify_intent(message):
    if os.getenv('SITEPILOT_INTENT_BACKEND', 'legacy').lower() == 'v2':
        from .intent_v2 import classify_intent_v2
        return classify_intent_v2(message)
    if not MODEL_PATH.exists():
        return 'unknown', 0.0
    model=json.loads(MODEL_PATH.read_text(encoding='utf8'))
    counts=model['counts']; vocab=set(model['vocabulary']); total=sum(counts.values())
    if not total: return 'unknown', 0.0
    words=set(tokenize(message)) & vocab
    if not words: return 'unknown', 0.0
    scores={}
    for category, count in counts.items():
        tokens=model['tokens'].get(category,{})
        score=math.log(count/total)
        for word in words:
            # Bernoulli positive-feature likelihood with add-one smoothing.
            score+=math.log((tokens.get(word,0)+1)/(count+2))
        scores[category]=score
    ranked=sorted(scores.items(),key=lambda x:x[1],reverse=True)
    # Relative scores are NOT calibrated confidence probabilities.
    return ranked[0][0], ranked[0][1]-ranked[1][1] if len(ranked)>1 else 0.0
