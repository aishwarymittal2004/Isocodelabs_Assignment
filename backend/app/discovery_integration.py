"""Optional read-only discovery bridge for existing SitePilot ticket flow.

Only call from handle_ticket_message AFTER accepted-ticket protection and
AFTER requirements extraction. No booking or handoff mutations occur here.
"""
from __future__ import annotations

from sqlalchemy import select

from .ai_policy import asks_final_price_or_discount, wants_human
from .agent import (
    LocalAgentUnavailable,
    fast_route,
    is_language_switch,
    route_latest_message,
    AgentDecision,
)
from .conversation import MAX_HISTORY_TURNS, bounded_history
from .grounded_discovery import handle_discovery, ollama_discovery_plan
from .models import Message



def _must_use_existing_chat_controller(message: str) -> bool:
    """Preserve policy, language switching, hesitation and booking handling."""
    if wants_human(message) or asks_final_price_or_discount(message):
        return True

    if is_language_switch(message):
        return True

    probe = AgentDecision(
        intent="general",
        concern_type="none",
        evidence_kind="unknown",
        evidence_quote="",
        reply="",
        needs_human=False,
    )
    probe = route_latest_message(probe, message)

    if probe.intent in ("hesitation", "booking", "human"):
        return True

    routed = fast_route(message)
    return routed is not None and getattr(routed, "intent", None) in (
        "booking", "human", "hesitation"
    )


def try_grounded_discovery(db, lead, message: str):
    """Return a grounded DiscoveryResult or None (use the legacy controller)."""
    if _must_use_existing_chat_controller(message):
        return None

    prior = db.scalars(
        select(Message)
        .where(Message.lead_id == lead.id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(min(MAX_HISTORY_TURNS, 10))
    ).all()
    history = bounded_history(
        [{"speaker": row.speaker, "body": row.body} for row in reversed(prior)]
    )
    try:
        return handle_discovery(db, message, history, ollama_discovery_plan)
    except LocalAgentUnavailable:
        # The original code still owns fallback, review, and handoff policy.
        return None
