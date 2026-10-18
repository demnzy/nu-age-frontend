import asyncio
import urllib.parse
import flet as ft
from src.requests.auth import get_google_auth_start_url
from src.utils.file_opener import show_page_snackbar


def is_dark_mode(page: ft.Page) -> bool:
    if getattr(page, "theme_mode", None) == ft.ThemeMode.DARK:
        return True
    if getattr(page, "theme_mode", None) == ft.ThemeMode.LIGHT:
        return False
    return getattr(page, "platform_brightness", None) == ft.Brightness.DARK


def detect_client_platform(page: ft.Page) -> str:
    """Accurately identifies the runtime platform for backend OAuth callback dispatch."""
    if getattr(page, "web", False):
        return "web"

    plat = getattr(page, "platform", None)
    if plat in [ft.PagePlatform.ANDROID, "android"]:
        return "android"
    elif plat in [ft.PagePlatform.IOS, "ios"]:
        return "ios"

    ua = (getattr(page, "client_user_agent", None) or "").lower()
    if "android" in ua:
        return "android"
    elif "iphone" in ua or "ipad" in ua:
        return "ios"

    return "desktop"


def build_google_auth_button(
    page: ft.Page,
    text: str = "Continue with Google",
    persona: str = "student",
    height: int = 42,
    expand: bool = True,
    on_error = None,
) -> ft.Container:
    """
    Renders an official Google-branded authentication button compliant with Google
    Identity Guidelines and Nu-Age visual hierarchy.

    Zero-secret & Zero-.env design: Communicates strictly through the backend API.
    Supports local loopback listener for 100% reliable desktop OAuth sign-in.
    """
    is_dark = is_dark_mode(page)

    # Google Official Colors & Neutral Surface styling
    bg_color = ft.Colors.with_opacity(0.08, ft.Colors.WHITE) if is_dark else ft.Colors.WHITE
    border_color = ft.Colors.with_opacity(0.18, ft.Colors.WHITE) if is_dark else ft.Colors.GREY_300
    text_color = ft.Colors.WHITE if is_dark else ft.Colors.GREY_900

    btn_content_row = ft.Row(
        controls=[
            ft.Image(
                src="google_logo.svg",
                width=18,
                height=18,
                fit=ft.BoxFit.CONTAIN,
            ),
            ft.Text(
                text,
                size=13,
                weight=ft.FontWeight.W_600,
                color=text_color,
            ),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=10,
        tight=True,
    )

    loading_indicator = ft.Row(
        controls=[
            ft.ProgressRing(width=16, height=16, stroke_width=2.2, color=ft.Colors.PRIMARY),
            ft.Text("Connecting to Google...", size=12.5, color=text_color, weight=ft.FontWeight.W_500),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=8,
        tight=True,
    )

    button_container = ft.Container(
        content=btn_content_row,
        height=height,
        expand=expand,
        alignment=ft.Alignment.CENTER,
        border_radius=10,
        bgcolor=bg_color,
        border=ft.Border.all(1, border_color),
        animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
    )

    is_busy = False

    async def handle_click(e=None):
        nonlocal is_busy
        if is_busy:
            return
        is_busy = True

        button_container.content = loading_indicator
        button_container.opacity = 0.85
        button_container.update()

        loopback_server = None
        auth_done_event = asyncio.Event()
        received_tokens = {}

        try:
            platform_str = detect_client_platform(page)
            loopback_port = None
            web_origin = None

            if platform_str == "desktop":
                # Spin up local loopback server for instant desktop auth callback
                async def handle_loopback_client(reader, writer):
                    try:
                        data = await reader.read(4096)
                        req_str = data.decode("utf-8", errors="ignore")
                        first_line = req_str.split("\r\n")[0] if "\r\n" in req_str else ""
                        parts = first_line.split(" ")
                        if len(parts) >= 2:
                            parsed = urllib.parse.urlparse(parts[1])
                            params = urllib.parse.parse_qs(parsed.query)
                            if "access_token" in params:
                                received_tokens["access_token"] = params["access_token"][0]
                                received_tokens["refresh_token"] = params.get("refresh_token", [""])[0]
                            elif "error" in params:
                                received_tokens["error"] = params["error"][0]

                        html = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>Nu Age - Logged In</title>
                        <style>body{font-family:-apple-system,sans-serif;text-align:center;padding:50px 20px;background:#0F1711;color:#E8F5E9;}
                        .c{max-width:420px;margin:auto;background:#1B241C;padding:32px;border-radius:16px;border:1px solid #2B3A2C;box-shadow:0 8px 32px rgba(0,0,0,0.5);}
                        h2{color:#37BF14;margin-top:0;}p{color:#A5D6A7;font-size:15px;line-height:1.5;}</style></head>
                        <body><div class="c"><h2>Welcome to Nu Age! 🎉</h2><p>You have signed in with Google successfully.<br>You can close this tab and return to the Nu Age app.</p></div></body></html>"""
                        resp_bytes = html.encode("utf-8")
                        header = f"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nContent-Length: {len(resp_bytes)}\r\nConnection: close\r\n\r\n".encode("utf-8")
                        writer.write(header + resp_bytes)
                        await writer.drain()
                    except Exception:
                        pass
                    finally:
                        try:
                            writer.close()
                            await writer.wait_closed()
                        except Exception:
                            pass
                        auth_done_event.set()

                loopback_server = await asyncio.start_server(handle_loopback_client, "127.0.0.1", 0)
                loopback_port = loopback_server.sockets[0].getsockname()[1]

            elif platform_str == "web":
                # Forward current browser origin (e.g. http://localhost:8550) so callback returns to this app
                full_url = getattr(page, "url", "") or ""
                if full_url and "://" in full_url:
                    p = urllib.parse.urlparse(full_url)
                    web_origin = f"{p.scheme}://{p.netloc}"

            status, data = await get_google_auth_start_url(
                platform=platform_str,
                persona=persona,
                port=loopback_port,
                origin=web_origin,
            )

            if status == 200 and isinstance(data, dict) and data.get("auth_url"):
                auth_url = data["auth_url"]
                # Launch system browser / OAuth window
                await page.launch_url(auth_url)

                if platform_str == "desktop" and loopback_server:
                    try:
                        # Wait up to 150 seconds for user to complete sign in in browser
                        await asyncio.wait_for(auth_done_event.wait(), timeout=150.0)
                        if "access_token" in received_tokens:
                            from src.services.auth_session import AuthSession
                            from src.utils.session_utils import set_session_value
                            at = received_tokens["access_token"]
                            rt = received_tokens.get("refresh_token", "")
                            session = AuthSession.for_page(page)
                            await session.set_tokens(at, rt)
                            await page.shared_preferences.set("auth_token", at)
                            if rt:
                                await page.shared_preferences.set("refresh_token", rt)
                            set_session_value(page, "session_auth_token", at)
                            nav_bar = getattr(page, "persistent_nav_bar", None)
                            if nav_bar:
                                try:
                                    nav_bar.refresh()
                                except Exception:
                                    pass
                            page.go("/dashboard")
                            return
                        elif "error" in received_tokens:
                            err_msg = received_tokens["error"]
                            if on_error:
                                on_error(err_msg)
                            else:
                                show_page_snackbar(page, f"Google login cancelled: {err_msg}", icon=ft.Icons.WARNING_ROUNDED)
                    except asyncio.TimeoutError:
                        show_page_snackbar(page, "Google sign-in timed out. Please try again.", icon=ft.Icons.TIMER_OUTLINED)
            else:
                err_detail = "Failed to initialize Google authentication."
                if isinstance(data, dict):
                    err_detail = data.get("detail", err_detail)
                if on_error:
                    on_error(err_detail)
                else:
                    show_page_snackbar(page, err_detail, icon=ft.Icons.WARNING_ROUNDED)
        except Exception as ex:
            msg = f"Connection error: {ex}"
            if on_error:
                on_error(msg)
            else:
                show_page_snackbar(page, msg, icon=ft.Icons.WIFI_OFF_ROUNDED)
        finally:
            if loopback_server:
                try:
                    loopback_server.close()
                    await loopback_server.wait_closed()
                except Exception:
                    pass
            is_busy = False
            button_container.content = btn_content_row
            button_container.opacity = 1.0
            if getattr(button_container, "page", None):
                button_container.update()

    button_container.on_click = handle_click

    return button_container

