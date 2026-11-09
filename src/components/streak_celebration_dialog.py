"""
Streak Celebration Dialog for Nu Age LMS.
Mirrors Duolingo and Spotify Wrapped viral celebration cards:
When learners achieve or protect their streak milestones, displays the procedural
high-resolution branded milestone card graphic with pre-formatted social captions,
1-tap native WhatsApp/Social sharing, and download options.
"""
import flet as ft
from src.utils.db_manager import log_daily_activity
from src.components.milestone_share_modal import open_milestone_share_modal
from src.services.shareable_card_engine import MilestoneType


def show_streak_celebration_dialog(page: ft.Page, streak_days: int = 2) -> None:
    """Displays a celebratory shareable card modal mirroring Duolingo & Spotify Wrapped."""
    try:
        log_daily_activity()
    except Exception:
        pass

    # Cancel today's pending reminder notifications since user just studied
    try:
        from src.services.local_notification_service import LocalNotificationManager
        mgr = LocalNotificationManager.get_instance()
        page.run_task(mgr.cancel_streak_reminders)
        page.run_task(mgr.show_instant_streak_celebration, streak_days)
    except Exception:
        pass

    open_milestone_share_modal(
        page=page,
        milestone_type=MilestoneType.STREAK,
        metric_value=str(streak_days),
        subtitle=f"{streak_days}-day streak!",
    )
