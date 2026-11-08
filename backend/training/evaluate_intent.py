"""Small hand-written, held-out synthetic smoke set; NOT a production accuracy benchmark."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.local_intent import classify_intent
cases = [
    ('Could you arrange a tour for me?', 'booking'),
    ('Please show some appointment times', 'booking'),
    ('I need a human representative', 'human'),
    ('Can I speak with the sales team?', 'human'),
    ('What is the estimated cost?', 'project_facts'),
    ('Tell me its RERA registration', 'project_facts'),
    ('I am uncertain about my loan', 'hesitation'),
    ('The commute is a concern for us', 'hesitation'),
    ('Thank you so much', 'general'),
    ('મારે ઘર જોવા માટે સમય જોઈએ', 'booking'),
]
correct = 0
for message, expected in cases:
    got, gap = classify_intent(message)
    correct += got == expected
    print(f'{"PASS" if got == expected else "MISS"} {expected:14} -> {got:14} {message}')
print(f'Observed performance on 10 held-out synthetic examples: {correct}/10')
print('Not a representative or measured production metric; collect consented, anonymized real evaluation cases.')
