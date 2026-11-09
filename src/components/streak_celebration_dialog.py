"""
Streak Celebration Dialog for Nu Age LMS.
Fires when learners complete study sessions (quizzes, flashcards, CBT simulations)
to celebrate streak milestones without devaluing currency (strictly 0 coin bonus).
"""
import flet as ft
from src.utils.db_manager import log_daily_activity


def show_streak_celebration_dialog(page: ft.Page, streak_days: int = 2) -> None:
    """Displays a celebratory flame modal acknowledging streak progress."""
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

    def _close_dlg(e=None):
        dlg.open = False
        page.update()

    is_dark = getattr(page, "theme_mode", None) == ft.ThemeMode.DARK
    dialog_bg = ft.Colors.SURFACE if is_dark else "#FFFFFF"

    dlg = ft.AlertDialog(
        modal=True,
        bgcolor=dialog_bg,
        shape=ft.RoundedRectangleBorder(radius=20),
        content_padding=ft.Padding.symmetric(horizontal=24, vertical=28),
        content=ft.Container(
            width=360,
            content=ft.Column(
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=16,
                controls=[
                    # Animated flame container with glowing gradient
                    ft.Container(
                        width=72,
                        height=72,
                        border_radius=ft.BorderRadius.all(22),
                        gradient=ft.LinearGradient(
                            colors=[ft.Colors.AMBER_400, ft.Colors.DEEP_ORANGE_600],
                            begin=ft.Alignment.TOP_LEFT,
                            end=ft.Alignment.BOTTOM_RIGHT,
                        ),
                        alignment=ft.Alignment.CENTER,
                        shadow=ft.BoxShadow(
                            blur_radius=16,
                            color=ft.Colors.with_opacity(0.35, ft.Colors.ORANGE),
                            offset=ft.Offset(0, 4),
                        ),
                        content=ft.Icon(
                            ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED,
                            size=42,
                            color=ft.Colors.WHITE,
                        ),
                    ),
                    ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=4,
                        tight=True,
                        controls=[
                            ft.Text(
                                "Streak Active!",
                                size=20,
                                weight=ft.FontWeight.W_900,
                                color=ft.Colors.ON_SURFACE,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Text(
                                f"{streak_days}-Day Habit Streak",
                                size=13,
                                weight=ft.FontWeight.W_700,
                                color=ft.Colors.ORANGE_800 if not is_dark else ft.Colors.AMBER_400,
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ],
                    ),
                    ft.Text(
                        "You protected your daily flame! Consistent micro-practice is the fastest path to mastering concepts and passing your exams.",
                        size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(
                        padding=ft.Padding.only(top=8),
                        content=ft.Button(
                            content=ft.Text(
                                "Keep Learning",
                                size=13,
                                weight=ft.FontWeight.W_800,
                                color=ft.Colors.WHITE,
                            ),
                            bgcolor=ft.Colors.PRIMARY,
                            height=42,
                            width=float("inf"),
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=12),
                                elevation=0,
                            ),
                            on_click=_close_dlg,
                        ),
                    ),
                ],
            ),
        ),
    )

    page.overlay.append(dlg)
    dlg.open = True
    page.update()
