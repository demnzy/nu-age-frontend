"""
Cross-Platform Push Notification Service for NU-Front.
Integrates OneSignal (backed by Firebase Cloud Messaging on Android and APNs on iOS)
with graceful fallback and zero-crash desktop/web protection.
"""

import os
import sys
import uuid
import httpx
from typing import Optional, Callable
import flet as ft

# Check if flet_onesignal is installed
try:
    import flet_onesignal as fos
    _ONESIGNAL_AVAILABLE = True
except ImportError:
    _ONESIGNAL_AVAILABLE = False

from src.components.notifications_drawer import NotificationManager
from src.requests.auth import api_url

# Default fallback / placeholder App ID
DEFAULT_ONESIGNAL_APP_ID = os.environ.get("ONESIGNAL_APP_ID", "")
DEFAULT_ONESIGNAL_APP_ID = "36b0ae74-81fa-4bd4-bafd-09e8de69cdcc"

# Module-level reference to the active OneSignal instance
_onesignal_instance = None
_initialized_pages = set()


def is_push_supported(page: ft.Page) -> bool:
    """Returns True ONLY on mobile platforms (Android/iOS) where native Flutter

    push notification bridges are compiled and available."""
    if not page or not hasattr(page, "platform"):
        return False
    return page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS)


async def register_device_token_with_backend(
    token: str,
    auth_token: Optional[str],
    device_type: str = "android",
) -> bool:
    """Registers or upserts the device/push token with Nu-age POST /users/device-token."""
    if not token or not auth_token:
        return False

    endpoint = f"{api_url}/users/device-token"
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "token": token,
        "device_type": device_type,
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            res = await client.post(endpoint, json=payload, headers=headers)
            if res.status_code in (200, 201):
                print(f"[PushService] Device token registered with backend successfully: {token[:12]}...")
                return True
            else:
                print(f"[PushService] Backend device token registration returned status {res.status_code}")
                return False
    except Exception as ex:
        print(f"[PushService] Failed to register device token with backend: {ex!r}")
        return False


async def init_push_notifications(
    page: ft.Page,
    app_id: Optional[str] = None,
    on_navigate: Optional[Callable[[str], None]] = None,
):
    """Initializes OneSignal push notification service on Android/iOS.

    On desktop or browser (Windows, macOS, Linux, Web), cleanly no-ops without error.
    """
    global _onesignal_instance

    if not _ONESIGNAL_AVAILABLE:
        print("[PushService] flet_onesignal library not available in environment.")
        return None

    if not is_push_supported(page):
        # Gracefully handle desktop / web preview (flet run)
        platform_name = page.platform.value if hasattr(page, "platform") and page.platform else "desktop"
        print(f"[PushService] Push notifications idle (unsupported platform: {platform_name}).")
        return None

    page_id = id(page)
    if page_id in _initialized_pages and _onesignal_instance is not None:
        return _onesignal_instance

    effective_app_id = (app_id or DEFAULT_ONESIGNAL_APP_ID or "").strip()
    if not effective_app_id or effective_app_id == "YOUR_ONESIGNAL_APP_ID":
        print("[PushService] NOTICE: ONESIGNAL_APP_ID is not configured. Set ONESIGNAL_APP_ID to enable mobile push.")
        return None

    # Handle Notification Click (e.g. from System Tray when app is backgrounded or killed)
    def _handle_notification_click(e):
        try:
            notif = e.notification or {}
            # OneSignal packages additional payload in additionalData or custom dict
            custom_data = notif.get("additionalData") or notif.get("additional_data") or notif.get("data") or {}
            target_route = custom_data.get("route")
            exam_id = custom_data.get("exam_id")
            course_id = custom_data.get("course_id")

            if not target_route:
                if exam_id:
                    target_route = f"/exam/{exam_id}"
                elif course_id:
                    target_route = f"/courses/{course_id}"
                else:
                    target_route = "/notifications"

            print(f"[PushService] Notification clicked! Navigating to: {target_route}")
            if on_navigate:
                on_navigate(target_route)
            elif hasattr(page, "go"):
                page.go(target_route)
        except Exception as ex:
            print(f"[PushService] Error processing notification click: {ex!r}")

    # Handle Notification in Foreground (When app is active and open)
    async def _handle_foreground_notification(e):
        try:
            notif = e.notification or {}
            title = notif.get("title") or "New Notification"
            body = notif.get("body") or ""
            custom_data = notif.get("additionalData") or notif.get("additional_data") or notif.get("data") or {}
            category = custom_data.get("category", "announcement")
            notif_id = custom_data.get("id") or f"push_{uuid.uuid4().hex[:8]}"

            # 1. Feed into in-memory NotificationManager so badge & drawer update
            NotificationManager.upsert(
                notif_id=str(notif_id),
                title=title,
                body=body,
                category=category,
                icon=ft.Icons.NOTIFICATIONS_ACTIVE_ROUNDED,
            )

            # 2. Present non-intrusive in-app SnackBar notification
            if hasattr(page, "overlay"):
                def _open_route(ev):
                    r = custom_data.get("route", "/notifications")
                    page.go(r)

                snack = ft.SnackBar(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.NOTIFICATIONS_ACTIVE_ROUNDED, color=ft.Colors.WHITE, size=20),
                            ft.Expanded(
                                ft.Column(
                                    [
                                        ft.Text(title, weight=ft.FontWeight.BOLD, size=13, color=ft.Colors.WHITE),
                                        ft.Text(body, size=12, color=ft.Colors.WHITE70, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                    ],
                                    spacing=2,
                                    tight=True,
                                )
                            ),
                        ],
                        spacing=10,
                    ),
                    action="View",
                    on_action=_open_route,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                    duration=4000,
                )
                page.overlay.append(snack)
                snack.open = True
                page.update()
        except Exception as ex:
            print(f"[PushService] Error handling foreground push: {ex!r}")

    try:
        onesignal = fos.OneSignal(
            app_id=effective_app_id,
            log_level=fos.OSLogLevel.INFO,
            on_notification_click=_handle_notification_click,
            on_notification_foreground=_handle_foreground_notification,
        )

        # Flet 0.86.5 convention: services must be added to page.services
        if hasattr(page, "services"):
            page.services.append(onesignal)

        _onesignal_instance = onesignal
        _initialized_pages.add(page_id)
        print(f"[PushService] OneSignal successfully registered with App ID: {effective_app_id[:8]}...")

        # Request permission on Android 13+ / iOS
        try:
            granted = await onesignal.notifications.request_permission()
            print(f"[PushService] Notification permission granted: {granted}")
        except Exception as perm_ex:
            print(f"[PushService] Notification permission request error: {perm_ex!r}")

        return onesignal

    except Exception as ex:
        print(f"[PushService] Failed to initialize OneSignal: {ex!r}")
        return None


async def bind_user_push_identity(
    page: ft.Page,
    user_id: int | str,
    auth_token: Optional[str] = None,
):
    """Binds the logged-in user ID as the OneSignal external user ID and registers

    the device subscription token with the Nu-age backend."""
    if not is_push_supported(page) or _onesignal_instance is None:
        return

    try:
        user_str_id = str(user_id)
        await _onesignal_instance.login(user_str_id)
        print(f"[PushService] Bound OneSignal user external_id to: {user_str_id}")

        # Fetch subscription token or ID to register with backend
        try:
            push_token = await _onesignal_instance.user.get_push_subscription_token()
            if not push_token:
                push_token = await _onesignal_instance.user.get_push_subscription_id()

            if push_token and auth_token:
                device_type = "android" if page.platform == ft.PagePlatform.ANDROID else "ios"
                await register_device_token_with_backend(push_token, auth_token, device_type=device_type)
        except Exception as token_ex:
            print(f"[PushService] Error reading push subscription token: {token_ex!r}")

    except Exception as ex:
        print(f"[PushService] Error binding user push identity: {ex!r}")


async def unbind_user_push_identity(page: ft.Page):
    """Unbinds the user upon logout, ensuring the device ceases to receive private user notifications."""
    if not is_push_supported(page) or _onesignal_instance is None:
        return

    try:
        await _onesignal_instance.logout()
        print("[PushService] OneSignal user logged out.")
    except Exception as ex:
        print(f"[PushService] Error during push logout: {ex!r}")


async def setup_user_push_notifications(page: ft.Page, auth_token: str):
    """Fetches user profile and binds user identity to OneSignal and backend."""
    if not is_push_supported(page) or not auth_token:
        return

    try:
        from src.requests.auth import get_current_user_request
        status, user_data = await get_current_user_request(auth_token)
        if status == 200 and isinstance(user_data, dict):
            user_id = user_data.get("id")
            if user_id:
                await bind_user_push_identity(page, user_id=user_id, auth_token=auth_token)
    except Exception as ex:
        print(f"[PushService] Error in setup_user_push_notifications: {ex!r}")

