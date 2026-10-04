import os
import sys
import shutil
import urllib.parse
import subprocess
import asyncio
from typing import Any, Optional, Union
import flet as ft


def show_page_snackbar(page: ft.Page, snack: Any):
    """
    Safely presents a SnackBar across different Flet runtime contexts
    without throwing AttributeError on missing show_snack_bar or string TypeError.
    """
    if not page:
        return
    # Guard against swapped arguments e.g. show_page_snackbar("text", page)
    if isinstance(page, (str, ft.SnackBar)) and isinstance(snack, ft.Page):
        page, snack = snack, page
    # Coerce raw strings into SnackBar
    if isinstance(snack, str):
        snack = ft.SnackBar(
            content=ft.Text(snack, color=ft.Colors.WHITE, weight=ft.FontWeight.W_600, size=13),
            bgcolor="#064E3B",
            behavior=ft.SnackBarBehavior.FLOATING,
            duration=2500,
        )
    try:
        if hasattr(page, "open"):
            page.open(snack)
        elif hasattr(page, "show_snack_bar"):
            page.show_snack_bar(snack)
        elif hasattr(page, "show_dialog"):
            page.show_dialog(snack)
        elif hasattr(page, "overlay") and page.overlay is not None:
            page.overlay.append(snack)
            snack.open = True
            page.update()
    except Exception as e:
        print(f"[file_opener] Could not display snackbar: {e}")


async def safe_set_clipboard(page: ft.Page, text: str):
    """
    Safely stores text into the system clipboard across Flet versions and platforms
    without throwing AttributeError on missing set_clipboard.
    """
    if not page or text is None:
        return
    text = str(text)
    try:
        if hasattr(page, "clipboard"):
            cb = getattr(page, "clipboard")
            if hasattr(cb, "set") and callable(cb.set):
                res = cb.set(text)
                if asyncio.iscoroutine(res):
                    await res
                return
            elif callable(cb):
                res = cb(text)
                if asyncio.iscoroutine(res):
                    await res
                return

        if hasattr(page, "set_clipboard") and callable(page.set_clipboard):
            res = page.set_clipboard(text)
            if asyncio.iscoroutine(res):
                await res
            return

        cb = ft.Clipboard()
        if hasattr(page, "overlay") and page.overlay is not None and cb not in page.overlay:
            page.overlay.append(cb)
            if hasattr(page, "update"):
                page.update()
        res = cb.set(text)
        if asyncio.iscoroutine(res):
            await res
    except Exception as ex:
        print(f"[file_opener] Clipboard set notice: {ex}")


async def open_or_download_asset(page: ft.Page, target_url_or_path: str, file_name: str = "Course Document"):
    """
    Safely opens or downloads a lesson asset (PDF document, audio file, etc.)
    supporting both online web URLs and offline local filesystem paths without
    triggering ShellExecute / url_launcher errors on Windows or mobile.
    """
    if not target_url_or_path or not str(target_url_or_path).strip():
        if page:
            show_page_snackbar(
                page,
                ft.SnackBar(
                    content=ft.Text("No document path or URL provided."),
                    bgcolor=ft.Colors.RED_700,
                    duration=3000,
                ),
            )
        return

    raw_target = str(target_url_or_path).strip()

    # ── 1. Remote HTTP/HTTPS URL ──────────────────────────────────────────────
    if raw_target.startswith(("http://", "https://")):
        try:
            if page:
                await page.launch_url(raw_target)
        except Exception as ex:
            print(f"[file_opener] launch_url failed for remote URL: {ex}")
            if page:
                show_page_snackbar(
                    page,
                    ft.SnackBar(
                        content=ft.Text(f"Could not open document link: {ex}"),
                        bgcolor=ft.Colors.RED_700,
                        duration=3000,
                    ),
                )
        return

    # ── 2. Local Filesystem Path (Offline Course Asset) ────────────────────────
    clean_path = raw_target
    if clean_path.startswith("file:///"):
        clean_path = clean_path[8:]
    elif clean_path.startswith("file://"):
        clean_path = clean_path[7:]

    clean_path = urllib.parse.unquote(clean_path)
    norm_path = os.path.normpath(clean_path)

    if not os.path.exists(norm_path):
        print(f"[file_opener] Local file not found: {norm_path}")
        if page:
            show_page_snackbar(
                page,
                ft.SnackBar(
                    content=ft.Row([
                        ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, color=ft.Colors.WHITE, size=18),
                        ft.Text("File not found in local offline storage.", size=13, color=ft.Colors.WHITE),
                    ], spacing=8),
                    bgcolor=ft.Colors.RED_700,
                    duration=3500,
                ),
            )
        return

    # ── A. Copy to User's Personal Downloads Folder ───────────────────────────
    downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
    exported_path = None
    if os.path.exists(downloads_dir):
        try:
            _, ext = os.path.splitext(norm_path)
            if not ext:
                ext = ".pdf" if "pdf" in file_name.lower() else ""

            # Sanitize file name for filesystem
            safe_base = "".join(c for c in file_name if c.isalnum() or c in (" ", "_", "-", "(", ")", ".")).strip()
            if not safe_base:
                safe_base = "Course_Document"
            if ext and not safe_base.lower().endswith(ext.lower()):
                safe_base = f"{safe_base}{ext}"

            target_file = os.path.join(downloads_dir, safe_base)
            base_stem, ext_part = os.path.splitext(safe_base)
            counter = 1
            while os.path.exists(target_file):
                if os.path.getsize(target_file) == os.path.getsize(norm_path):
                    break
                target_file = os.path.join(downloads_dir, f"{base_stem} ({counter}){ext_part}")
                counter += 1

            shutil.copy2(norm_path, target_file)
            exported_path = target_file
        except Exception as copy_err:
            print(f"[file_opener] Notice: Could not copy to user Downloads: {copy_err}")

    # File to open with system viewer (prefer exported version in Downloads, else cache)
    open_target = exported_path if exported_path and os.path.exists(exported_path) else norm_path

    # ── B. Launch in System's Default Application ─────────────────────────────
    opened = False
    if sys.platform == "win32":
        if hasattr(os, "startfile"):
            try:
                os.startfile(open_target)
                opened = True
            except Exception as e:
                print(f"[file_opener] os.startfile failed: {e}")

        if not opened:
            try:
                subprocess.Popen(f'explorer.exe "{open_target}"', shell=True)
                opened = True
            except Exception as e:
                print(f"[file_opener] explorer fallback failed: {e}")

    elif sys.platform == "darwin":
        try:
            subprocess.Popen(["open", open_target])
            opened = True
        except Exception as e:
            print(f"[file_opener] macOS open failed: {e}")

    elif sys.platform.startswith("linux"):
        try:
            subprocess.Popen(["xdg-open", open_target])
            opened = True
        except Exception as e:
            print(f"[file_opener] linux xdg-open failed: {e}")

    # ── C. Fallback via local_media_server ─────────────────────────────────────
    if not opened and page:
        try:
            from src.local_media_server import asset_url
            http_url = asset_url(norm_path)
            if http_url.startswith("http://"):
                await page.launch_url(http_url)
                opened = True
        except Exception as e:
            print(f"[file_opener] asset_url fallback failed: {e}")

    # ── D. Feedback Notification ──────────────────────────────────────────────
    if page:
        if exported_path:
            msg = f"Saved to Downloads & opened: {os.path.basename(exported_path)}"
        elif opened:
            msg = f"Opening {file_name}..."
        else:
            msg = f"Document ready at: {norm_path}"

        show_page_snackbar(
            page,
            ft.SnackBar(
                content=ft.Row([
                    ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.WHITE, size=18),
                    ft.Text(msg, size=13, color=ft.Colors.WHITE, expand=True),
                ], spacing=8),
                bgcolor=ft.Colors.GREEN_700,
                duration=3500,
            ),
        )


def launch_html_in_desktop_browser(html_code: str, page: ft.Page = None, file_stem: str = "nu_web_preview") -> bool:
    """
    Writes raw HTML to a local temp file and immediately launches it in Google Chrome if installed,
    or falls back to the system's default browser (via os.startfile on Windows, open on macOS, xdg-open on Linux).
    Displays a confirmation SnackBar on the page.
    """
    import os
    import sys
    import tempfile
    import shutil
    import subprocess
    import webbrowser

    raw_html = str(html_code or "").strip()
    if not raw_html:
        raw_html = "<!DOCTYPE html><html><head><meta charset='utf-8'><title>Preview</title></head><body><h1>Empty HTML Document</h1><p>No HTML markup to preview.</p></body></html>"

    try:
        tmp_dir = tempfile.gettempdir()
        tmp_path = os.path.join(tmp_dir, f"{file_stem}.html")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(raw_html)
    except Exception as err:
        print(f"[file_opener] Failed writing HTML preview file: {err}")
        if page:
            show_page_snackbar(
                page,
                ft.SnackBar(
                    content=ft.Row([
                        ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, color=ft.Colors.WHITE, size=18),
                        ft.Text(f"Could not prepare preview file: {err}", size=13, color=ft.Colors.WHITE),
                    ], spacing=8),
                    bgcolor=ft.Colors.RED_700,
                    duration=3500,
                ),
            )
        return False

    browser_used = None

    # 1. Search for Google Chrome specifically
    chrome_candidates = []
    if sys.platform == "win32":
        prog_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        prog_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        chrome_candidates.extend([
            os.path.join(prog_files, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(prog_files_x86, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(local_appdata, "Google", "Chrome", "Application", "chrome.exe"),
        ])
    elif sys.platform == "darwin":
        chrome_candidates.extend([
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        ])

    for cmd in ("chrome", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        found = shutil.which(cmd)
        if found and found not in chrome_candidates:
            chrome_candidates.append(found)

    for candidate in chrome_candidates:
        if candidate and os.path.exists(candidate):
            try:
                subprocess.Popen([candidate, tmp_path])
                browser_used = "Google Chrome"
                break
            except Exception as ex:
                print(f"[file_opener] Could not launch Chrome via {candidate}: {ex}")

    # 2. Fallback to system default handler
    if not browser_used:
        try:
            if sys.platform == "win32" and hasattr(os, "startfile"):
                os.startfile(tmp_path)
                browser_used = "Default Browser"
            elif sys.platform == "darwin":
                subprocess.Popen(["open", tmp_path])
                browser_used = "Default Browser"
            elif sys.platform.startswith("linux"):
                subprocess.Popen(["xdg-open", tmp_path])
                browser_used = "Default Browser"
        except Exception as ex:
            print(f"[file_opener] System default open failed: {ex}")

    # 3. Python webbrowser module fallback
    if not browser_used:
        try:
            file_url = f"file:///{os.path.abspath(tmp_path).replace(os.sep, '/')}"
            webbrowser.open(file_url)
            browser_used = "Browser"
        except Exception as ex:
            print(f"[file_opener] webbrowser.open failed: {ex}")

    if page:
        if browser_used:
            show_page_snackbar(
                page,
                ft.SnackBar(
                    content=ft.Row([
                        ft.Icon(ft.Icons.LANGUAGE_ROUNDED, color=ft.Colors.WHITE, size=18),
                        ft.Text(f"Live HTML preview opened in {browser_used}!", size=13, color=ft.Colors.WHITE),
                    ], spacing=8),
                    bgcolor=ft.Colors.GREEN_700,
                    duration=3500,
                ),
            )
        else:
            show_page_snackbar(
                page,
                ft.SnackBar(
                    content=ft.Row([
                        ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, color=ft.Colors.WHITE, size=18),
                        ft.Text("Failed to launch browser for preview.", size=13, color=ft.Colors.WHITE),
                    ], spacing=8),
                    bgcolor=ft.Colors.RED_700,
                    duration=3500,
                ),
            )

    return bool(browser_used)


def open_web_preview_modal(page: ft.Page, html_code: str, title: str = "Web Preview"):
    """
    Opens an HTML preview:
    - On Desktop (Windows, macOS, Linux): Bypasses modal completely and directly launches the live
      preview in Google Chrome / default system browser with full DevTools, CSS3, and JS engine.
    - On Mobile (Android / iOS): Opens an authentic in-app WebView modal using data URLs,
      preventing Android FileUriExposedException and providing a sandboxed mobile view.
    """
    if not page:
        return

    import re
    import tempfile
    import base64

    # Detect platform: Mobile (Android/iOS) gets in-app WebView modal, Desktop gets live browser
    platform = getattr(page, "platform", None) if page else None
    platform_str = str(platform or "").lower()
    is_mobile = (
        platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS, getattr(ft.PagePlatform, "ANDROID_TV", None))
        or any(m in platform_str for m in ("android", "ios"))
    ) if platform else False

    # On desktop, bypass the modal completely and launch live preview in Chrome / default browser
    if not is_mobile:
        launch_html_in_desktop_browser(html_code, page=page)
        return

    # ── Mobile In-App WebView Modal Dialog ───────────────────────────────────────
    raw_html = str(html_code or "").strip()
    if not raw_html:
        raw_html = "<h1>Empty HTML Document</h1><p>No HTML markup to preview.</p>"

    # Inspect badges
    has_css = bool(re.search(r"<style[\s>]", raw_html, re.IGNORECASE))
    has_js = bool(re.search(r"<script[\s>]", raw_html, re.IGNORECASE))

    badges = [
        ft.Container(
            content=ft.Text("HTML5", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.DEEP_ORANGE_600),
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.DEEP_ORANGE_500),
            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
            border_radius=4,
        )
    ]
    if has_css:
        badges.append(
            ft.Container(
                content=ft.Text("CSS", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_600),
                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.BLUE_500),
                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                border_radius=4,
            )
        )
    if has_js:
        badges.append(
            ft.Container(
                content=ft.Text("JS", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_700),
                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER_500),
                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                border_radius=4,
            )
        )

    # Viewport address bar (stretches full width)
    address_bar = ft.Container(
        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        bgcolor="#F1F5F9",
        border_radius=8,
        border=ft.Border.all(1, "#E2E8F0"),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(
                    spacing=6,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.LOCK_ROUNDED, size=13, color=ft.Colors.GREEN_600),
                        ft.Text("sandbox://preview.local", size=11, color="#64748B"),
                    ],
                ),
                ft.Row(spacing=4, tight=True, controls=badges),
            ],
        ),
    )

    preview_widget = None
    try:
        from flet_webview import WebView, JavaScriptMode
        b64_html = base64.b64encode(raw_html.encode("utf-8")).decode("ascii")
        data_url = f"data:text/html;charset=utf-8;base64,{b64_html}"
        preview_widget = WebView(
            url=data_url,
            expand=True,
            bgcolor="#FFFFFF",
        )
    except Exception as ex:
        print(f"[file_opener] Mobile WebView init error: {ex}")
        preview_widget = ft.Container(
            padding=16,
            content=ft.Text(f"Could not load in-app webview: {ex}"),
        )

    # Full-width canvas container
    canvas = ft.Container(
        bgcolor=ft.Colors.WHITE,
        border_radius=8,
        border=ft.Border.all(1, "#E2E8F0"),
        expand=True,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=preview_widget,
    )

    pw = getattr(page, "width", None)
    if pw is None and hasattr(page, "window") and page.window:
        pw = getattr(page.window, "width", None)
    pw = pw or 400

    ph = getattr(page, "height", None)
    if ph is None and hasattr(page, "window") and page.window:
        ph = getattr(page.window, "height", None)
    ph = ph or 700

    # Ensure wide dialog on mobile without cutting off
    dlg_width = min(720, max(300, pw - 24))
    dlg_height = min(600, max(380, ph - 100))

    dialog_content = ft.Container(
        width=dlg_width,
        height=dlg_height,
        content=ft.Column(
            spacing=8,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[
                address_bar,
                canvas,
            ],
        ),
    )

    def _close_dlg(e):
        try:
            if hasattr(page, "close"):
                page.close(preview_dlg)
            else:
                preview_dlg.open = False
                page.update()
        except Exception:
            pass

    preview_dlg = ft.AlertDialog(
        modal=True,
        shape=ft.RoundedRectangleBorder(radius=16),
        inset_padding=ft.Padding.symmetric(horizontal=12, vertical=16),
        content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        title_padding=ft.Padding.symmetric(horizontal=16, vertical=12),
        actions_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(
                    spacing=8,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.LANGUAGE_ROUNDED, color=ft.Colors.DEEP_ORANGE_500, size=22),
                        ft.Text(title, size=15, weight=ft.FontWeight.BOLD),
                    ],
                ),
                ft.IconButton(
                    icon=ft.Icons.CLOSE_ROUNDED,
                    icon_size=20,
                    tooltip="Close",
                    on_click=_close_dlg,
                ),
            ],
        ),
        content=dialog_content,
        actions=[
            ft.FilledButton(
                "Close",
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.PRIMARY,
                    shape=ft.RoundedRectangleBorder(radius=6),
                ),
                on_click=_close_dlg,
            )
        ],
    )

    # Open dialog
    try:
        if hasattr(page, "open"):
            page.open(preview_dlg)
        elif hasattr(page, "show_dialog"):
            page.show_dialog(preview_dlg)
        else:
            page.dialog = preview_dlg
            preview_dlg.open = True
            page.update()
    except Exception as e:
        print(f"[file_opener] Error presenting preview dialog: {e}")

    # For mobile WebView, ensure unrestricted JS and reinforced HTML load
    if preview_widget and hasattr(page, "run_task"):
        async def _reinforce_mobile_webview():
            try:
                from flet_webview import JavaScriptMode
                if hasattr(preview_widget, "set_javascript_mode"):
                    await preview_widget.set_javascript_mode(JavaScriptMode.UNRESTRICTED)
            except Exception:
                pass
            try:
                if hasattr(preview_widget, "load_html"):
                    await preview_widget.load_html(raw_html)
            except Exception:
                pass
        page.run_task(_reinforce_mobile_webview)


