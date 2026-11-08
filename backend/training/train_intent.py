"""Train a small, explainable intent classifier from synthetic, labeled cases.
Run from backend root: python training/train_intent.py
This does NOT fine-tune LLM weights and is not a substitute for live evaluation.
"""
import json
from pathlib import Path
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.local_intent import train,MODEL_PATH
p=Path(__file__).parent/'examples.jsonl'
rows=[json.loads(line) for line in p.read_text(encoding='utf8').splitlines() if line.strip()]
model=train(rows)
MODEL_PATH.write_text(json.dumps(model,ensure_ascii=False,indent=2),encoding='utf8')
print(f'Trained local intent classifier on {len(rows)} synthetic examples -> {MODEL_PATH}')
