"""
Local Notification Service for Nu Age LMS (Flet 1.1.2).
Powered by `flet-notifications` (Flutter Local Notifications).
Provides 100% offline-capable scheduled streak alerts, morning study prompts,
and native Windows Action Center toasts / Android notification shade delivery.
Uses Nu Age branded app icons (not generic Flet icons).
"""
from __future__ import annotations
import os
import sys
import asyncio
from datetime import datetime, timedelta, time
from typing import Optional, Callable, Any
import flet as ft

fn = None
_LOCAL_NOTIFS_AVAILABLE: Optional[bool] = None


def _ensure_local_notifs_loaded() -> bool:
    """Lazily imports `flet_notifications` with graceful fallback."""
    global fn, _LOCAL_NOTIFS_AVAILABLE
    if _LOCAL_NOTIFS_AVAILABLE is not None:
        return _LOCAL_NOTIFS_AVAILABLE
    try:
        import flet_notifications as module
        fn = module
        _LOCAL_NOTIFS_AVAILABLE = True
    except ImportError:
        _LOCAL_NOTIFS_AVAILABLE = False
    return _LOCAL_NOTIFS_AVAILABLE


class LocalNotificationManager:
    """Singleton manager for client-side local notifications."""
    _instance: Optional[LocalNotificationManager] = None
    _service_control = None
    _page: Optional[ft.Page] = None
    _on_navigate: Optional[Callable[[str], Any]] = None

    # Notification IDs
    ID_MORNING_REMINDER = 1001
    ID_EVENING_STREAK = 1002
    ID_NIGHT_EMERGENCY = 1003
    ID_INSTANT_CELEBRATION = 1004

    @classmethod
    def get_instance(cls) -> LocalNotificationManager:
        if cls._instance is None:
            cls._instance = LocalNotificationManager()
        return cls._instance

    async def initialize(self, page: ft.Page, on_navigate: Optional[Callable[[str], Any]] = None) -> bool:
        """Mounts and registers local notifications on the page services."""
        if not _ensure_local_notifs_loaded():
            return False

        self._page = page
        self._on_navigate = on_navigate

        if self._service_control is not None:
            return True

        try:
            def handle_tap(e):
                route = getattr(e, "payload", None) or "/dashboard"
                if self._on_navigate:
                    res = self._on_navigate(route)
                    if asyncio.iscoroutine(res):
                        asyncio.create_task(res)
                elif self._page:
                    try:
                        self._page.navigate(route)
                    except Exception:
                        pass

            # In Flet 1.1, Service controls register automatically when instantiated in page context.
            # Do NOT add to page.overlay or page.controls.
            # Windows caches the icon permanently per AppUserModelID.
            # Versioning the AppUserModelID forces Windows to discard the initial Flet cache
            # and display the customized Nu Age brand iconography immediately.
            self._service_control = fn.Notifications(
                android_default_icon="icon",
                windows_app_name="Nu Age",
                windows_app_user_model_id="NuAge.LMS.App.v1",
                on_tap=handle_tap,
            )

            # In Flet 1.1, Services belong in page.services (never page.overlay or page.controls)
            if hasattr(page, "services") and self._service_control not in page.services:
                page.services.append(self._service_control)

            # Create dedicated Android Notification Channel for Streaks
            try:
                channel = fn.NotificationChannel(
                    id="nu_age_streaks",
                    name="Streak & Habit Reminders",
                    description="Daily Nu Age study streak reminders and morning motivation",
                    importance=fn.AndroidImportance.HIGH,
                )
                await self._service_control.create_channel(channel)
            except Exception as ch_err:
                # Expected on desktop/web platforms where channels are unsupported
                pass

            # Request notification permissions on Android 13+ / desktop
            try:
                await self._service_control.request_permissions()
            except Exception:
                pass

            return True
        except Exception as ex:
            print(f"[LocalNotifications] Initialization notice: {ex}")
            return False

    def _build_notification_options(self) -> Any:
        """Constructs platform-specific notification options with Nu Age branded iconography."""
        if not _ensure_local_notifs_loaded():
            return None

        android_opt = fn.AndroidOptions(
            channel="nu_age_streaks",
            icon="icon",
            priority=fn.AndroidPriority.HIGH,
            auto_cancel=True,
        )

        icon_path = os.path.abspath("assets/icon.png")
        if not os.path.exists(icon_path):
            icon_path = os.path.abspath("assets/favicon.png")
        icon_uri = f"file:///{icon_path.replace(os.sep, '/')}"

        win_opt = fn.WindowsOptions(
            header="Nu Age",
            images=[icon_uri],
        )

        return fn.NotificationOptions(android=android_opt, windows=win_opt)

    async def schedule_daily_habit_reminders(self) -> None:
        """Schedules recurring morning, evening, and night streak reminders."""
        if not self._service_control or not fn:
            return

        try:
            now = datetime.now()
            today = now.date()
            options = self._build_notification_options()

            # 1. Morning Study Sprint (8:30 AM daily)
            morning_time = datetime.combine(today, time(8, 30))
            if morning_time <= now:
                morning_time += timedelta(days=1)

            try:
                await self._service_control.schedule(
                    id=self.ID_MORNING_REMINDER,
                    when=morning_time,
                    title="☀️ Start your morning study sprint!",
                    body="2 minutes today keeps your momentum going and builds your streak.",
                    payload="/dashboard",
                    match_components=fn.DateTimeComponents.TIME,
                    options=options,
                )
            except Exception as sch_err:
                print(f"[LocalNotifications] Morning reminder schedule notice: {sch_err}")

            # 2. Evening Streak Saver (7:30 PM daily)
            evening_time = datetime.combine(today, time(19, 30))
            if evening_time <= now:
                evening_time += timedelta(days=1)

            try:
                await self._service_control.schedule(
                    id=self.ID_EVENING_STREAK,
                    when=evening_time,
                    title="🔥 Keep your Nu Age streak alive!",
                    body="Spend 2 minutes reviewing flashcards or answering a quick quiz question.",
                    payload="/self-study?tab=quizzes",
                    match_components=fn.DateTimeComponents.TIME,
                    options=options,
                )
            except Exception as sch_err:
                print(f"[LocalNotifications] Evening reminder schedule notice: {sch_err}")

            # 3. Night Emergency Reminder (9:30 PM daily)
            night_time = datetime.combine(today, time(21, 30))
            if night_time <= now:
                night_time += timedelta(days=1)

            try:
                await self._service_control.schedule(
                    id=self.ID_NIGHT_EMERGENCY,
                    when=night_time,
                    title="🌙 Don't lose your study streak!",
                    body="Your streak resets at midnight. 1 quick question protects your flame.",
                    payload="/self-study?tab=quizzes",
                    match_components=fn.DateTimeComponents.TIME,
                    options=options,
                )
            except Exception as sch_err:
                print(f"[LocalNotifications] Night reminder schedule notice: {sch_err}")

        except Exception as ex:
            print(f"[LocalNotifications] Scheduling notice: {ex}")

    async def cancel_streak_reminders(self) -> None:
        """Cancels streak reminders once today's practice session is logged."""
        if not self._service_control or not fn:
            return
        try:
            await self._service_control.cancel(self.ID_EVENING_STREAK)
            await self._service_control.cancel(self.ID_NIGHT_EMERGENCY)
        except Exception:
            pass

    async def show_instant_streak_celebration(self, streak: int) -> None:
        """Triggers an immediate celebration notification on streak progression."""
        if not self._service_control or not fn:
            return
        try:
            options = self._build_notification_options()
            await self._service_control.show(
                id=self.ID_INSTANT_CELEBRATION,
                title=f"🔥 {streak}-Day Streak Milestone!",
                body="Great job! You've protected your streak for today.",
                payload="/dashboard",
                options=options,
            )
        except Exception as ex:
            print(f"[LocalNotifications] Celebration notice: {ex}")


async def init_local_notifications(page: ft.Page, on_navigate: Optional[Callable[[str], Any]] = None) -> LocalNotificationManager:
    """Async entrypoint for bootstrapping local notifications."""
    mgr = LocalNotificationManager.get_instance()
    ok = await mgr.initialize(page, on_navigate)
    if ok:
        await mgr.schedule_daily_habit_reminders()
    return mgr
