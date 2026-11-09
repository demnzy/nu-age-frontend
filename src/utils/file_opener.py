import os
import sys
import shutil
import urllib.parse
import subprocess
import asyncio
from typing import Any, Optional, Union
import flet as ft
from src.utils.modal_guard import (
    safe_open_dialog,
    safe_close_dialog,
    safe_update_dialog,
    run_after_modal_close,
    is_modal_open,
    debounced_click,
)


_toast_registry = {}  # {page_id: {"container": c, "text": t, "icon": i, "card": k, "dismiss_id": int}}


def show_page_snackbar(
    page: ft.Page,
    snack: Any,
    icon: Optional[Any] = None,
    bgcolor: Optional[str] = None,
    **kwargs,
):
    """
    Safely presents a sleek floating toast notification in page.overlay.
    Unlike modal dialog routes, this never pops Flutter's Navigator,
    guaranteeing page scroll offset is 100% preserved when the toast appears or dismisses.
    """
    if not page:
        return
    # Guard against swapped arguments e.g. show_page_snackbar("text", page)
    if isinstance(page, (str, ft.SnackBar)) and isinstance(snack, ft.Page):
        page, snack = snack, page

    message = ""
    bg_color = bgcolor or "#064E3B"
    text_color = ft.Colors.WHITE

    def _extract_text_from_control(ctrl: Any) -> str:
        if not ctrl:
            return ""
        if isinstance(ctrl, str):
            return ctrl
        if isinstance(ctrl, ft.Text):
            return str(ctrl.value or "")
        if hasattr(ctrl, "value") and isinstance(ctrl.value, str):
            return ctrl.value
        # If it's a Row, Column, or other parent control with .controls
        if hasattr(ctrl, "controls") and isinstance(ctrl.controls, (list, tuple)):
            parts = [_extract_text_from_control(c) for c in ctrl.controls]
            return " ".join([p for p in parts if p])
        # If it's a Container or has a single .content
        if hasattr(ctrl, "content"):
            return _extract_text_from_control(ctrl.content)
        return ""

    if isinstance(snack, str):
        message = snack
    elif isinstance(snack, ft.SnackBar):
        bg_color = bgcolor or snack.bgcolor or "#064E3B"
        extracted = _extract_text_from_control(snack.content)
        message = extracted if extracted else str(getattr(snack.content, "value", ""))
    elif hasattr(snack, "value") and isinstance(snack.value, str):
        message = str(snack.value)
    else:
        extracted = _extract_text_from_control(snack)
        message = extracted if extracted else ""

    message = (message or "").strip()
    if not message:
        return

    # Choose icon & theme based on tone / message
    m_lower = message.lower()
    if any(w in m_lower for w in ("error", "fail", "could not", "invalid", "cannot")):
        icon_name = ft.Icons.ERROR_OUTLINE_ROUNDED
        icon_color = "#FCA5A5"
        if bg_color == "#064E3B":
            bg_color = "#7F1D1D"
    elif any(w in m_lower for w in ("downloading", "saving", "adding", "removing", "refreshing")):
        icon_name = ft.Icons.HOURGLASS_EMPTY_ROUNDED
        icon_color = "#93C5FD"
    elif any(w in m_lower for w in ("saved", "added", "success", "done", "completed")):
        icon_name = ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED
        icon_color = "#86EFAC"
    else:
        icon_name = ft.Icons.INFO_OUTLINE_ROUNDED
        icon_color = "#A7F3D0"

    # Allow caller override for icon and bgcolor
    if icon:
        icon_name = icon
    if bgcolor:
        bg_color = bgcolor

    page_key = id(page)
    state = _toast_registry.get(page_key)

    page_width = getattr(page, "width", None)
    if page_width is None:
        page_width = getattr(getattr(page, "window", None), "width", 400) or 400
    try:
        page_width = float(page_width)
    except Exception:
        page_width = 400.0

    max_toast_width = min(max(260.0, page_width - 32.0), 520.0)
    is_multiline = len(message) > 40 or "\n" in message or page_width < 450
    card_width = max_toast_width if is_multiline else None

    # If active toast already mounted on this page, update in-place smoothly
    if state and state.get("container") in getattr(page, "overlay", []):
        container = state["container"]
        txt_ctrl = state["text"]
        icon_ctrl = state["icon"]
        card = state["card"]

        txt_ctrl.value = message
        txt_ctrl.max_lines = 5
        txt_ctrl.no_wrap = False
        txt_ctrl.text_align = ft.TextAlign.CENTER
        icon_ctrl.name = icon_name
        icon_ctrl.color = icon_color
        card.bgcolor = bg_color
        card.width = card_width
        card.border_radius = ft.BorderRadius.all(24)
        right_spacer = ft.Container(width=18)
        card.content = ft.Row(
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            tight=not is_multiline,
            controls=[
                icon_ctrl,
                ft.Container(content=txt_ctrl, expand=True, alignment=ft.Alignment.CENTER) if is_multiline else txt_ctrl,
                right_spacer,
            ],
        )
        container.content = ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[card],
        )
        container.opacity = 1.0
        container.visible = True
        state["dismiss_id"] = state.get("dismiss_id", 0) + 1
        my_id = state["dismiss_id"]
        try:
            container.update()
        except Exception:
            try:
                page.update()
            except Exception:
                pass
    else:
        txt_ctrl = ft.Text(
            message,
            size=12.5,
            weight=ft.FontWeight.W_600,
            color=text_color,
            max_lines=5,
            no_wrap=False,
            text_align=ft.TextAlign.CENTER,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        icon_ctrl = ft.Icon(icon_name, size=18, color=icon_color)
        right_spacer = ft.Container(width=18)
        card = ft.Container(
            padding=ft.Padding.symmetric(horizontal=16, vertical=10),
            border_radius=ft.BorderRadius.all(24),
            bgcolor=bg_color,
            width=card_width,
            shadow=ft.BoxShadow(
                blur_radius=16,
                color=ft.Colors.with_opacity(0.28, ft.Colors.BLACK),
                offset=ft.Offset(0, 4),
            ),
            content=ft.Row(
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                tight=not is_multiline,
                controls=[
                    icon_ctrl,
                    ft.Container(content=txt_ctrl, expand=True, alignment=ft.Alignment.CENTER) if is_multiline else txt_ctrl,
                    right_spacer,
                ],
            ),
        )
        container = ft.Container(
            bottom=26,
            left=0,
            right=0,
            alignment=ft.Alignment.CENTER,
            animate_opacity=250,
            opacity=1.0,
            visible=True,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[card],
            ),
        )

        state = {
            "container": container,
            "text": txt_ctrl,
            "icon": icon_ctrl,
            "card": card,
            "dismiss_id": 1,
        }
        _toast_registry[page_key] = state
        my_id = 1

        try:
            if hasattr(page, "overlay") and page.overlay is not None:
                page.overlay.append(container)
                page.update()
            else:
                if hasattr(page, "show_dialog"):
                    page.show_dialog(ft.SnackBar(content=ft.Text(message)))
                return
        except Exception as e:
            print(f"[file_opener] Could not append overlay toast: {e}")
            return

    # Asynchronously auto-dismiss without popping Flutter Navigator
    async def _auto_dismiss(t_id: int):
        await asyncio.sleep(2.6)
        curr = _toast_registry.get(page_key)
        if not curr or curr.get("dismiss_id") != t_id:
            return
        try:
            c = curr["container"]
            c.opacity = 0.0
            c.update()
            await asyncio.sleep(0.3)
            if curr.get("dismiss_id") == t_id:
                c.visible = False
                c.update()
        except Exception:
            pass

    try:
        page.run_task(_auto_dismiss, my_id)
    except Exception:
        pass


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
        try:
            if getattr(cb, "_i", None) is None and hasattr(page, "_services") and page._services is not None:
                page._services.register_service(cb)
        except Exception:
            pass
        res = cb.set(text)
        if asyncio.iscoroutine(res):
            await res
    except Exception as ex:
        print(f"[file_opener] Clipboard set notice: {ex}")


async def safe_share_text(
    page: ft.Page,
    text: str,
    title: Optional[str] = None,
    subject: Optional[str] = None,
    fallback_toast: str = "Copied to clipboard for sharing!",
) -> bool:
    """
    Uses Flet 1.1.2's native `ft.Share` service (`share_text`) to invoke the native
    Android/iOS/macOS/Windows share sheet (WhatsApp, Telegram, Messages, Email).
    Falls back to copying `text` to clipboard if native sharing is unavailable.
    """
    if not page or not text:
        return False
    text = str(text)
    try:
        share_svc = ft.Share()
        if getattr(share_svc, "_i", None) is None and hasattr(page, "_services") and page._services is not None:
            page._services.register_service(share_svc)
        res = share_svc.share_text(text, title=title, subject=subject)
        if asyncio.iscoroutine(res):
            result = await asyncio.wait_for(res, timeout=12.0)
        else:
            result = res
        status = getattr(result, "status", None)
        status_val = getattr(status, "value", str(status or "")).lower()
        if status_val == "unavailable":
            await safe_set_clipboard(page, text)
            if fallback_toast:
                show_page_snackbar(page, ft.SnackBar(content=ft.Text(fallback_toast), bgcolor=ft.Colors.GREEN_700))
            return False
        return True
    except Exception:
        await safe_set_clipboard(page, text)
        if fallback_toast:
            show_page_snackbar(page, ft.SnackBar(content=ft.Text(fallback_toast), bgcolor=ft.Colors.GREEN_700))
        return False


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
    already_in_downloads = os.path.dirname(os.path.abspath(norm_path)).lower() == os.path.abspath(downloads_dir).lower()
    if os.path.exists(downloads_dir) and not already_in_downloads:
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


async def export_text_or_markdown_as_pdf(
    page: ft.Page,
    title: str,
    text: str,
    subtitle: Optional[str] = "Nu Age LMS • Study Hub",
) -> bool:
    """
    Converts study notes or markdown into a PDF document directly in the user's
    Downloads folder and opens it with the default system PDF application.
    Uses headless Chromium/Edge/Chrome print-to-pdf for authentic PDF rendering.
    """
    import os
    import sys
    import html
    import shutil
    import tempfile
    import subprocess

    raw_text = str(text or "").strip()
    if not raw_text:
        if page:
            show_page_snackbar(page, "No text content available to export as PDF.", ft.Colors.RED_700)
        return False

    display_title = str(title or "Study Notes").strip()
    safe_base = "".join(c for c in display_title if c.isalnum() or c in (" ", "_", "-", "(", ")", ".")).strip()
    if not safe_base:
        safe_base = "Nu_Age_Study_Notes"
    if not safe_base.lower().endswith(".pdf"):
        safe_base = f"{safe_base}.pdf"

    downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
    if not os.path.exists(downloads_dir):
        downloads_dir = tempfile.gettempdir()

    target_pdf = os.path.join(downloads_dir, safe_base)
    base_stem, ext_part = os.path.splitext(safe_base)
    counter = 1
    while os.path.exists(target_pdf):
        target_pdf = os.path.join(downloads_dir, f"{base_stem} ({counter}){ext_part}")
        counter += 1

    def _md_to_html(raw_md: str) -> str:
        import re
        import html
        lines = raw_md.splitlines()
        out = []
        in_list = False
        for line in lines:
            s = line.strip()
            if not s:
                if in_list:
                    out.append("</ul>")
                    in_list = False
                out.append('<div style="height:6px;"></div>')
                continue
            if s.startswith("### "):
                if in_list:
                    out.append("</ul>")
                    in_list = False
                text = html.escape(s[4:])
                text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
                out.append(f'<h3 style="color:#0f172a; margin:14px 0 4px 0; font-size:15px; font-weight:700;">{text}</h3>')
            elif s.startswith("## "):
                if in_list:
                    out.append("</ul>")
                    in_list = False
                out.append(f'<h2 style="color:#059669; margin:22px 0 6px 0; font-size:18px; font-weight:800; border-bottom:1.5px solid #d1fae5; padding-bottom:4px;">{html.escape(s[3:])}</h2>')
            elif s.startswith("# "):
                if in_list:
                    out.append("</ul>")
                    in_list = False
                out.append(f'<h1 style="color:#0f172a; margin:16px 0 6px 0; font-size:22px; font-weight:900;">{html.escape(s[2:])}</h1>')
            elif s.startswith("---"):
                if in_list:
                    out.append("</ul>")
                    in_list = False
                out.append('<hr style="border:0; border-top:1px solid #e2e8f0; margin:14px 0;"/>')
            elif s.startswith("> "):
                if in_list:
                    out.append("</ul>")
                    in_list = False
                quote_text = html.escape(s[2:])
                quote_text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", quote_text)
                quote_text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", quote_text)
                out.append(f'<div style="border-left:3.5px solid #059669; background:#f0fdf4; padding:6px 12px; margin:6px 0; font-size:12.5px; color:#166534; border-radius:0 6px 6px 0; line-height:1.5;">{quote_text}</div>')
            elif s.startswith("- "):
                if not in_list:
                    out.append('<ul style="margin:4px 0 8px 0; padding-left:22px;">')
                    in_list = True
                content = html.escape(s[2:])
                content = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", content)
                content = re.sub(r"\*(.+?)\*", r"<em>\1</em>", content)
                out.append(f'<li style="margin-bottom:4px; font-size:13.5px;">{content}</li>')
            else:
                if in_list:
                    out.append("</ul>")
                    in_list = False
                content = html.escape(s)
                content = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", content)
                content = re.sub(r"\*(.+?)\*", r"<em>\1</em>", content)
                out.append(f'<p style="margin:4px 0; font-size:13.5px; line-height:1.65; color:#334155;">{content}</p>')
        if in_list:
            out.append("</ul>")
        return "\n".join(out)

    formatted_body = _md_to_html(raw_text)

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{html.escape(display_title)}</title>
  <style>
    @page {{ size: A4; margin: 18mm 16mm; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
      color: #0f172a;
      line-height: 1.65;
      margin: 0;
      padding: 24px;
      background: #ffffff;
    }}
    .header {{
      border-bottom: 2.5px solid #059669;
      padding-bottom: 14px;
      margin-bottom: 24px;
    }}
    .brand {{
      font-size: 11px;
      font-weight: 800;
      color: #059669;
      text-transform: uppercase;
      letter-spacing: 1.2px;
    }}
    h1 {{
      font-size: 24px;
      font-weight: 900;
      color: #0f172a;
      margin: 8px 0 4px 0;
    }}
    .meta {{
      font-size: 12px;
      color: #64748b;
    }}
    .content {{
      font-size: 13.5px;
      color: #334155;
      white-space: pre-wrap;
      word-break: break-word;
      line-height: 1.7;
    }}
  </style>
</head>
<body>
  <div class="header">
    <div class="brand">{html.escape(subtitle or "Nu Age LMS")}</div>
    <h1>{html.escape(display_title)}</h1>
    <div class="meta">Study Material & Notes • Exported from Nu Age</div>
  </div>
  <div class="content">{formatted_body}</div>
</body>
</html>"""

    tmp_html = os.path.join(tempfile.gettempdir(), f"nu_export_{os.getpid()}.html")
    try:
        with open(tmp_html, "w", encoding="utf-8") as f:
            f.write(html_content)
    except Exception as err:
        print(f"[file_opener] Failed writing temp HTML: {err}")
        return False

    browser_candidates = []
    if sys.platform == "win32":
        prog_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        prog_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        browser_candidates.extend([
            os.path.join(prog_files_x86, "Microsoft", "Edge", "Application", "msedge.exe"),
            os.path.join(prog_files, "Microsoft", "Edge", "Application", "msedge.exe"),
            os.path.join(prog_files, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(prog_files_x86, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(local_appdata, "Google", "Chrome", "Application", "chrome.exe"),
        ])
    elif sys.platform == "darwin":
        browser_candidates.extend([
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ])

    for cmd in ("msedge", "chrome", "google-chrome", "google-chrome-stable", "chromium"):
        found = shutil.which(cmd)
        if found and found not in browser_candidates:
            browser_candidates.append(found)

    pdf_created = False
    for browser_exe in browser_candidates:
        if browser_exe and os.path.exists(browser_exe):
            try:
                cmd = [
                    browser_exe,
                    "--headless",
                    "--disable-gpu",
                    f"--print-to-pdf={target_pdf}",
                    tmp_html,
                ]
                proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    proc.kill()
                if os.path.exists(target_pdf) and os.path.getsize(target_pdf) > 0:
                    pdf_created = True
                    break
            except Exception as e:
                print(f"[file_opener] Browser PDF print error with {browser_exe}: {e}")

    if pdf_created and os.path.exists(target_pdf):
        await open_or_download_asset(page, target_pdf, os.path.basename(target_pdf))
        return True

    return launch_html_in_desktop_browser(html_content, page, file_stem=safe_base.replace(".pdf", ""))


def synthesize_material_question_bank(
    material_id: Any,
    title: str = "Question Bank",
    raw_content: Optional[str] = None,
    scoped_cards: Optional[list] = None,
    page: Optional[ft.Page] = None,
) -> dict:
    """
    Synthesizes a structured Question Bank markdown document from all available
    local questions, flashcard drills, and extracted notes for a given material.
    """
    import json
    mid = str(material_id or "").strip()
    raw_body = str(raw_content or "").strip()

    questions = []
    cards = list(scoped_cards or [])

    try:
        from src.local_db import get_local_db
        db = get_local_db(page)
        cur = db.cursor()

        # 1. Fetch raw content if missing
        if not raw_body and mid:
            row = cur.execute(
                "SELECT content FROM downloaded_study_materials WHERE id = ? LIMIT 1",
                (mid,),
            ).fetchone()
            if row and row[0]:
                raw_body = str(row[0]).strip()

        # 2. Fetch study questions
        if mid:
            q_rows = cur.execute(
                """SELECT question_text, options, answer_index, explanation, difficulty, topic, exam_year 
                   FROM downloaded_study_questions 
                   WHERE material_id = ? 
                   ORDER BY rowid ASC""",
                (mid,),
            ).fetchall()
            for r in q_rows:
                q_text = r[0] or ""
                opts = []
                try:
                    opts = json.loads(r[1]) if isinstance(r[1], str) else (r[1] or [])
                except Exception:
                    opts = []
                ans_idx = r[2] if r[2] is not None else 0
                exp = r[3] or ""
                diff = r[4] or ""
                topic = r[5] or ""
                year = r[6]
                questions.append({
                    "question_text": q_text,
                    "options": opts,
                    "answer_index": ans_idx,
                    "explanation": exp,
                    "difficulty": diff,
                    "topic": topic,
                    "exam_year": year,
                })

        # 3. Fetch flashcards if not already provided
        if not cards and mid:
            fc_rows = cur.execute(
                "SELECT front, back FROM downloaded_flashcards WHERE material_id = ? ORDER BY rowid ASC",
                (mid,),
            ).fetchall()
            for r in fc_rows:
                cards.append({"front": r[0] or "", "back": r[1] or ""})
    except Exception as ex:
        print(f"[synthesize_material_question_bank error]: {ex}")

    # Build markdown
    md_lines = []
    md_lines.append(f"# {title}")
    md_lines.append("*Nu Age LMS • Official Synthesized Question Bank*\n")
    md_lines.append("---\n")

    if questions:
        md_lines.append(f"## Practice Questions & Rationales ({len(questions)} items)\n")
        letters = ["A", "B", "C", "D", "E", "F"]
        for i, q in enumerate(questions, 1):
            q_title = f"### Question {i}: {q['question_text']}"
            if q.get("exam_year"):
                q_title += f" *({q['exam_year']})*"
            md_lines.append(q_title)
            opts = q.get("options") or []
            ans_idx = q.get("answer_index", 0)
            for j, opt in enumerate(opts):
                letter = letters[j] if j < len(letters) else str(j + 1)
                md_lines.append(f"- **{letter})** {opt}")
            ans_letter = letters[ans_idx] if 0 <= ans_idx < len(letters) else str(ans_idx + 1)
            ans_text = opts[ans_idx] if 0 <= ans_idx < len(opts) else ""
            ans_display = f"Option {ans_letter}" + (f" ({ans_text})" if ans_text else "")
            md_lines.append(f"\n**Correct Answer:** {ans_display}")
            if q.get("explanation"):
                md_lines.append(f"> **Explanation:** {q['explanation']}")
            md_lines.append("\n---\n")

    if cards:
        md_lines.append(f"## Active-Recall Drill Deck ({len(cards)} cards)\n")
        for j, c in enumerate(cards, 1):
            front = c.get("front") or c.get("question") or ""
            back = c.get("back") or c.get("answer") or ""
            exp = c.get("explanation") or ""
            md_lines.append(f"### Drill {j}: {front}")
            md_lines.append(f"**Answer / Concept:** {back}")
            if exp:
                md_lines.append(f"> **Key Note:** {exp}")
            md_lines.append("\n---\n")

    if raw_body and raw_body not in ("_No text content available for this material._",):
        md_lines.append("## Extracted Notes & Source Material\n")
        md_lines.append(raw_body)
        md_lines.append("\n---\n")

    if not questions and not cards and not raw_body:
        md_lines.append("_No question bank items or extracted notes found yet for this material._\n")
        md_lines.append("> *Tip: Tap 'Generate' to create flashcards, practice quizzes, or mock exams with Nu Age AI.*")

    final_markdown = "\n".join(md_lines)
    has_content = bool(questions or cards or raw_body)

    if questions and cards:
        summary_label = f"Question Bank • {len(questions)} questions • {len(cards)} cards"
    elif questions:
        summary_label = f"Question Bank • {len(questions)} questions"
    elif cards:
        summary_label = f"Question Bank • {len(cards)} flashcards"
    elif raw_body:
        words = len(raw_body.split())
        summary_label = f"Question Bank • {words:,} words"
    else:
        summary_label = "Question Bank • 0 items"

    return {
        "markdown": final_markdown,
        "questions": questions,
        "cards": cards,
        "raw_body": raw_body,
        "questions_count": len(questions),
        "cards_count": len(cards),
        "has_content": has_content,
        "summary_label": summary_label,
    }


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


