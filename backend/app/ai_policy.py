"""Server-owned SitePilot AI guardrails. LLM text is never an authority for project claims.

Contains no database or HTTP operations; easy to unit-test independently.
"""
import re
from .agent import is_fact_summary_query, relevant_approved_facts

# A final quotation or discount must NEVER come from the chatbot, even if someone
# mistakenly approves such a phrase as a 'fact'. Indicative *approved* ranges may
# be disclosed with a non-binding label, but no final price, offers or bargaining.
FORBIDDEN_FACT = re.compile(
    r'\b(?:discount|rebate|negotiat(?:e|ion)|final\s+(?:price|cost|quote)|best\s+price|'
    r'firm\s+quote|guaranteed\s+price|special\s+offer|lowest\s+price)\b|'
    r'(?:अंतिम\s+कीमत|छूट|डिस्काउंट|અંતિમ\s+ભાવ|ડિસ્કાઉન્ટ|છૂટ)', re.I
)
HUMAN_REQUEST = re.compile(
    r'\b(?:speak|talk|connect|contact|reach|call|transfer|handoff|hand\s*off|need|want)\b'
    r'.{0,55}\b(?:human|person|sales(?:person|man|woman| executive| team)?|representative|agent)\b'
    r'|\b(?:human|salesperson|sales executive|real person)\b.{0,35}'
    r'\b(?:please|now|call|contact|speak|talk)\b|'
    r'(?:बिक्री प्रतिनिधि|इंसान से बात|सेल्सपर्सन|સેલ્સપર્સન|વ્યક્તિ સાથે વાત)', re.I
)
# These are only routing triggers: nothing below is used as a property fact.
FACT_TERMS = re.compile(
    r'\b(?:price|pricing|cost|amenit(?:y|ies)|parking|possession|rera|'
    r'carpet\s+area|sq\s*ft|configuration|floor\s+plan|school\s+distance|'
    r'commute\s+time|location|maintenance\s+charges?|discount|final\s+quote|'
    r'lifts?|elevators?|security|backup|water|fire\s+safety|floor|area|size|available|'
    r'nearby|school|hospital|bus|metro|maintenance|registration|stamp\s+duty|emi|'
    r'unit|resale|rent|pet\s+policy|policy|construction|noise|facing|view|'
    r'available\s+flat|facilit(?:y|ies)|project\s+(?:information|facts|details))\b|'
    r'(?:कीमत|दाम|छूट|सुविधा|पार्किंग|कब्जा|કિંમત|સુવિધા|પાર્કિંગ|કબજો)', re.I
)
SEEK = re.compile(r'\b(?:what|which|where|when|how|show|list|tell|give|share|is|are|does|do|can|any|provide)\b|[?]|(?:क्या|कितना|कब|दिखाओ|बताओ|શું|કેટલું|ક્યારે)', re.I)


def wants_human(message: str) -> bool:
    return bool(HUMAN_REQUEST.search(message))


def asks_final_price_or_discount(message: str) -> bool:
    return bool(FORBIDDEN_FACT.search(message) and (SEEK.search(message) or re.search(r'\b(?:give|want|need)\b',message,re.I)))


def looks_like_fact_request(message: str) -> bool:
    # Do not mistake 'My wife thinks the price is too high' for a missing fact
    # merely because the message contains 'price'.
    return bool(FACT_TERMS.search(message) and SEEK.search(message))


def allowed_facts(approved: dict[str,str]) -> dict[str,str]:
    """Reject unauthorized negotiable quote/discount content on ALL AI paths."""
    return {key: value for key,value in approved.items()
            if not FORBIDDEN_FACT.search(key.replace('_',' '))
            and not FORBIDDEN_FACT.search(value)
            and key not in {'listing_disclaimer', 'contact_policy'} }


def fact_result(message: str, raw_approved: dict[str,str]) -> tuple[list[tuple[str,str]], bool]:
    """(supported-fact entries, missing) for exactly this question."""
    if asks_final_price_or_discount(message):
        return [], True
    facts=allowed_facts(raw_approved)
    if is_fact_summary_query(message):
        matches=list(facts.items())[:12]
    else:
        matches=relevant_approved_facts(message, facts)
    return matches, not bool(matches)


def missing_fact_reply(lang: str, consent: bool) -> str:
    suffix={'en':'You can opt in to follow-up contact in your preferences.',
            'hi':'आगे संपर्क के लिए अपनी सहमति दीजिए।',
            'gu':'આગળ સંપર્ક માટે કૃપા કરીને તમારી સંમતિ આપો.'}
    core={'en':'I cannot confirm that from the sales-head-approved fact sheet. I have recorded a request for the sales team to verify it. A response time is not guaranteed.',
          'hi':'बिक्री प्रमुख द्वारा स्वीकृत तथ्य-सूची में इसकी पुष्टि नहीं है। मैंने बिक्री टीम से पुष्टि का अनुरोध दर्ज किया है। जवाब के समय की गारंटी नहीं है।',
          'gu':'વેચાણ વડા દ્વારા મંજૂર હકીકત પત્રકમાં આ માહિતીની પુષ્ટિ નથી. મેં વેચાણ ટીમને તેની ચકાસણી માટે વિનંતી નોંધાવી છે. જવાબના સમયની ખાતરી નથી.'}
    lang=lang if lang in core else 'en'
    return core[lang] + ('' if consent else ' '+suffix[lang])


def human_reply(lang: str, consent: bool) -> str:
    core={'en':'Your request to speak with the sales team has been recorded. A reply is not guaranteed immediately.',
          'hi':'बिक्री टीम से बात करने का आपका अनुरोध दर्ज कर लिया गया है। तुरंत जवाब की गारंटी नहीं है।',
          'gu':'વેચાણ ટીમ સાથે વાત કરવાની તમારી વિનંતી નોંધાઈ ગઈ છે. તરત જવાબની ખાતરી નથી.'}
    lang=lang if lang in core else 'en'
    return core[lang] + ('' if consent else ' '+{'en':' Please opt in before we contact you.', 'hi':' संपर्क के लिए कृपया सहमति दें।', 'gu':' સંપર્ક માટે કૃપા કરીને સંમતિ આપો.'}[lang])


def final_price_reply(lang: str, consent: bool) -> str:
    core={'en':'I cannot provide a final price or negotiate a discount. I have recorded a request for the sales team to confirm the terms.',
          'hi':'मैं अंतिम कीमत या छूट तय नहीं कर सकता। मैंने बिक्री टीम से शर्तों की पुष्टि का अनुरोध दर्ज किया है।',
          'gu':'હું અંતિમ કિંમત અથવા ડિસ્કાઉન્ટ આપી શકતો નથી. મેં વેચાણ ટીમને શરતોની પુષ્ટિ માટે વિનંતી નોંધાવી છે.'}
    lang=lang if lang in core else 'en'
    return core[lang] + ('' if consent else ' '+{'en':' Please opt in before we contact you.', 'hi':' संपर्क के लिए सहमति दें।', 'gu':' સંપર્ક માટે સંમતિ આપો.'}[lang])
