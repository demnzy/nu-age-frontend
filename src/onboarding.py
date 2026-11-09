"""
Full-Page Onboarding View for Nu Age LMS (Flet 1.1.2).
Integrates the complete 6-screen interactive presentation deck from onboarding_overlay.py:
1. Self-Study Hub & Practice Tools
2. Courses & Spaces
3. Nu Chat & Nu Owl AI Companion
4. Study Network & Duo Streaks
5. What's New in Nu Age
6. Interactive Goal Customizer (15m/30m/60m Daily Target & Focus Topics)

Features:
- Dedicated distraction-free full-page view at /onboarding.
- Works on first app launch after install, fully independent of auth status.
- Top-left Nu Age logo rendered from assets/icon.png.
- Heavily optimized for mobile viewports with snug vertical scaling and smooth touch swipe gestures.
"""

from __future__ import annotations
import os
import json
import asyncio
from typing import Optional, Dict, Any
import flet as ft

from src.components.onboarding_overlay import (
    build_onboarding_view,
    build_onboarding_overlay,
    ONBOARDING_SCREENS,
)
from src.utils.theme_bridge import get_theme_palette, THEME_PALETTES

# DEV TOGGLE:
# True  -> ALWAYS show on startup (allows instant review/testing)
# False -> NEVER show
# None  -> Normal behavior (only shows on compiled first launch, then never again)
FORCE_SHOW_ONBOARDING = None


# ─────────────────────────────────────────────────────────────────────────────
# 1. PERSISTENCE HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def _get_app_disk_state() -> dict:
    try:
        app_dir = os.path.join(
            os.environ.get("APPDATA") or os.environ.get("HOME") or os.path.expanduser("~"),
            ".nu_age"
        )
        state_file = os.path.join(app_dir, "client_state.json")
        if os.path.exists(state_file):
            with open(state_file, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _set_app_disk_state(key: str, val: Any) -> None:
    try:
        app_dir = os.path.join(
            os.environ.get("APPDATA") or os.environ.get("HOME") or os.path.expanduser("~"),
            ".nu_age"
        )
        os.makedirs(app_dir, exist_ok=True)
        state_file = os.path.join(app_dir, "client_state.json")
        data = _get_app_disk_state()
        data[key] = val
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as ex:
        print(f"[Onboarding] Disk save warning: {ex}")


async def check_should_show_onboarding(page: ft.Page) -> bool:
    """Returns True if the onboarding carousel should be displayed on app startup."""
    if FORCE_SHOW_ONBOARDING is not None:
        return FORCE_SHOW_ONBOARDING

    disk_data = _get_app_disk_state()
    disk_shown = disk_data.get("app_onboarding_shown")

    pref_shown = False
    try:
        if hasattr(page, "shared_preferences"):
            pref_shown = await page.shared_preferences.get("app_onboarding_shown_v1")
    except Exception:
        pass

    has_client_shown = disk_shown or pref_shown
    return not has_client_shown


async def mark_onboarding_seen(page: ft.Page, data: Optional[dict] = None) -> None:
    """Saves onboarding completion and user preferences across all storage tiers."""
    _set_app_disk_state("app_onboarding_shown", True)
    try:
        if hasattr(page, "shared_preferences"):
            await page.shared_preferences.set("app_onboarding_shown_v1", True)
            await page.shared_preferences.set("has_seen_onboarding", True)
            if data:
                if "goal_minutes" in data:
                    await page.shared_preferences.set("study_goal_minutes", data["goal_minutes"])
                if "study_focus" in data:
                    await page.shared_preferences.set("study_focus", data["study_focus"])
    except Exception as ex:
        print(f"[Onboarding] Preferences save warning: {ex}")

    try:
        from src.utils.session_utils import get_session_user
        u = get_session_user(page)
        if u:
            u["has_seen_onboarding"] = True
            if data:
                if "goal_minutes" in data:
                    u["study_goal_minutes"] = data["goal_minutes"]
                if "study_focus" in data:
                    u["study_focus"] = data["study_focus"]
    except Exception:
        pass


def onboarding_view(page: ft.Page, on_dismiss=None) -> ft.View:
    """Entrypoint for the full-page onboarding view."""
    return build_onboarding_view(page, on_dismiss=on_dismiss)
