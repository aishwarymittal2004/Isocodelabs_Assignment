"""Run a few live, synthetic V5 prompts against your own Ollama installation.

Usage (from backend/sitepilot_backend): python -m app.v5_smoke
Does not use PostgreSQL, create bookings, or send user data to third parties.
"""
from .agent import (classify_with_sitepilot, ground_obvious_concern, safe_response,
                    preferred_language, LocalAgentUnavailable)
from .conversation import (eligible_for_contextual_reply, draft_contextual_reply,
                           validate_draft, DialogueDraft)
from types import SimpleNamespace

PROJECT=SimpleNamespace(name='Aranya Residences',city='Ahmedabad',
                        price_min_inr=0,price_max_inr=0,rera_registration=None)
EXAMPLES=[
    ('I like the apartment, but my wife is worried about school travel.', 'en', []),
    ('What if our child has to travel a long time each day?', 'en', [
        {'speaker':'buyer','body':'I like the apartment, but my wife is worried about school travel.'},
        {'speaker':'ai','body':'What journey would feel manageable to your family?'}]),
    ('स्कूल दूर होने की बात से हम चिंतित हैं।', 'hi', []),
    ('શાળાની મુસાફરી અંગે મારા પરિવારને ચિંતા છે.', 'gu', []),
]


def main():
    print('SitePilot V5 | live local Ollama smoke test | synthetic prompts only')
    success=0
    for index,(message,language,history) in enumerate(EXAMPLES,1):
        print(f'\nScenario {index} | language={language} | buyer={message}')
        try:
            decision=ground_obvious_concern(classify_with_sitepilot(message,language,PROJECT.name),message)
            if eligible_for_contextual_reply(decision,message):
                reply=draft_contextual_reply(message,language,decision,history)
                mode='contextual_local_model'
            else:
                reply,_=safe_response(decision,message,PROJECT,language=language)
                mode='backend_policy'
            print(f'intent={decision.intent} concern={decision.concern_type} mode={mode}')
            print('assistant:',reply)
            success+=1
        except LocalAgentUnavailable as exc:
            print('FAILED:',str(exc))
    print(f'\nAccepted {success}/{len(EXAMPLES)} synthetic replies. Inspect the language, specificity and safety manually.')
    if success != len(EXAMPLES):
        raise SystemExit(1)


if __name__=='__main__':
    main()
