"""
Utility to sanitize AI chat errors into warm, user-friendly messages.
Prevents internal stack traces, API keys, HTTP status codes, or raw python
exceptions from ever leaking into learner-facing chat bubbles or conversation memory.
"""
from typing import Any, Optional


def get_user_friendly_ai_error(raw_error: Any = None, is_quota: bool = False) -> str:
    """
    Transforms any raw exception, HTTP status error, or network timeout into
    a friendly, reassuring educational message.
    """
    if is_quota:
        return (
            "⚡ **Daily AI Query Cap Reached**\n\n"
            "You have used all 15 free AI queries for today. Your free daily quota resets automatically "
            "every midnight at 00:00 UTC, or you can upgrade to **Pro Scholar** for unlimited questions."
        )

    if not raw_error:
        return "I encountered a brief hiccup while processing that query. Please try asking again in a moment."

    err_str = str(raw_error).strip()
    err_lower = err_str.lower()

    # Quota or paywall
    if "limit reached" in err_lower or "403" in err_lower or "quota" in err_lower:
        return (
            "⚡ **Daily AI Query Cap Reached**\n\n"
            "You have used all 15 free AI queries for today. Your free daily quota resets automatically "
            "every midnight at 00:00 UTC, or you can upgrade to **Pro Scholar** for unlimited questions."
        )

    # Timeouts
    if "timeout" in err_lower or "timed out" in err_lower:
        return "⏳ Synthesizing that answer took a little longer than expected. Please try asking again."

    # Network / Connectivity
    if any(k in err_lower for k in ("connection", "getaddrinfo", "network", "offline", "econnrefused", "nodename")):
        return "📡 I'm having trouble connecting to the study server. Please verify your internet connection and try again."

    # Content Safety / Academic Filter
    if any(k in err_lower for k in ("safety", "moderation", "policy", "harmful")):
        return "🛡️ I wasn't able to process that question under our academic safety standards. Could you please rephrase your question?"

    # If already a friendly message returned from backend
    if "temporary hiccup" in err_lower or "experiencing a temporary" in err_lower:
        return err_str

    # General catch-all: NEVER leak python class names, stack traces, or server codes
    return "🧠 I ran into a brief hiccup synthesizing your study notes right now. Please try asking again in a few moments."

