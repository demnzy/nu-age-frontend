import os
import sys
import shutil
import urllib.parse
import subprocess
import flet as ft


def show_page_snackbar(page: ft.Page, snack: ft.SnackBar):
    """
    Safely presents a SnackBar across different Flet runtime contexts
    without throwing AttributeError on missing show_snack_bar.
    """
    if not page:
        return
    try:
        if hasattr(page, "show_dialog"):
            page.show_dialog(snack)
        elif hasattr(page, "open"):
            page.open(snack)
        elif hasattr(page, "show_snack_bar"):
            page.show_snack_bar(snack)
        elif hasattr(page, "overlay") and page.overlay is not None:
            page.overlay.append(snack)
            snack.open = True
            page.update()
    except Exception as e:
        print(f"[file_opener] Could not display snackbar: {e}")


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
