"""
Milestone Share Modal for Nu Age LMS.
Mirrors Duolingo's and Spotify Wrapped's viral celebration cards:
Presents the high-resolution generated milestone PNG card with pre-formatted snappy
social bragging caption, 1-tap native sharing to WhatsApp / Socials, copy caption, and download options.
Optimized for mobile viewports with clamped heights, dynamic image scaling, and bytes-based image loading.
100% Non-blocking: Dialog opens instantly with sleek skeleton while procedural generation runs in background thread.
"""
import os
import shutil
import asyncio
import tempfile
from typing import Optional, Dict, Any
import flet as ft
from src.services.shareable_card_engine import generate_milestone_card, MilestoneType
from src.utils.file_opener import safe_set_clipboard
from src.utils.modal_guard import safe_open_dialog, safe_close_dialog, safe_update_dialog


def open_milestone_share_modal(
    page: ft.Page,
    milestone_type: MilestoneType = MilestoneType.STREAK,
    user_name: Optional[str] = None,
    metric_value: str = "7",
    subtitle: Optional[str] = None,
    tagline: Optional[str] = None,
    on_dismiss: Optional[callable] = None,
):
    """
    Renders an executive, responsive celebration share modal with full card graphic preview,
    snappy social caption, 1-tap WhatsApp/Social share sheet integration, and image download.
    Mobile-optimized: bounded within viewport constraints, scrolls cleanly, loads image via bytes.
    Opens immediately with zero UI hang while Pillow card generation runs asynchronously in a worker thread.
    """
    # 1. Resolve Learner Name & Profile Picture
    resolved_name = user_name
    avatar_url = None
    if hasattr(page, "session") and hasattr(page.session, "store"):
        u = page.session.store.get("current_user") or {}
        if not resolved_name:
            resolved_name = u.get("name") or u.get("username")
        avatar_url = u.get("profile_picture_url") or u.get("avatar_url") or u.get("avatar")
    if not resolved_name:
        resolved_name = "Learner"

    metric_clean = str(metric_value).strip()
    if milestone_type == MilestoneType.STREAK:
        title_text = f"{metric_clean}-Day Streak"
    elif milestone_type == MilestoneType.CBT_EXAM:
        title_text = f"CBT Exam Result • {metric_clean}"
    elif milestone_type == MilestoneType.QUIZ_MASTERY:
        title_text = f"Quiz Result • {metric_clean}"
    else:
        title_text = f"Objective Complete • {metric_clean}"

    # 2. Viewport Dimensions & Clamping
    w_val = getattr(page, "width", None)
    screen_w = int(w_val) if isinstance(w_val, (int, float)) and w_val > 0 else 380
    h_val = getattr(page, "height", None)
    screen_h = int(h_val) if isinstance(h_val, (int, float)) and h_val > 0 else 720

    modal_w = min(screen_w - 24, 420)
    content_w = modal_w - 28

    # Dynamic square preview size bounded by both width and height
    preview_size = max(180, min(int(content_w), int(screen_h * 0.35), 310))
    dialog_content_h = min(screen_h - 130, 560)

    is_dark = getattr(page, "theme_mode", None) == ft.ThemeMode.DARK
    dialog_bg = ft.Colors.SURFACE if is_dark else "#FFFFFF"

    # Async state holder
    async_state = {
        "img_path": None,
        "caption": f"Achieved milestone on Nu Age LMS! https://nu-age.com.ng",
        "ready": False,
    }

    dlg_ref = [None]

    def _close_dlg(e=None):
        if dlg_ref[0]:
            safe_close_dialog(page, dlg_ref[0])
        if on_dismiss:
            try:
                on_dismiss()
            except Exception:
                pass

    # 3. Action Buttons (start disabled until background card generation completes)
    share_btn = ft.Button(
        content=ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            tight=True,
            spacing=8,
            controls=[
                ft.Icon(ft.Icons.SHARE_ROUNDED, size=16, color=ft.Colors.WHITE),
                ft.Text("Share on Socials", size=12.5, weight=ft.FontWeight.W_800, color=ft.Colors.WHITE),
            ],
        ),
        bgcolor=ft.Colors.PRIMARY,
        height=40,
        disabled=True,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=10),
            elevation=0,
        ),
    )

    copy_btn = ft.OutlinedButton(
        content=ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            tight=True,
            spacing=6,
            controls=[
                ft.Icon(ft.Icons.COPY_ROUNDED, size=13, color=ft.Colors.PRIMARY),
                ft.Text("Copy Caption", size=11.5, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY),
            ],
        ),
        height=38,
        disabled=True,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=10),
            padding=ft.Padding.symmetric(horizontal=8, vertical=0),
        ),
    )

    download_btn = ft.OutlinedButton(
        content=ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            tight=True,
            spacing=6,
            controls=[
                ft.Icon(ft.Icons.DOWNLOAD_ROUNDED, size=13, color=ft.Colors.PRIMARY),
                ft.Text("Download Card", size=11.5, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY),
            ],
        ),
        height=38,
        disabled=True,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=10),
            padding=ft.Padding.symmetric(horizontal=8, vertical=0),
        ),
    )

    async def _handle_share(e=None):
        if not async_state["ready"]:
            return
        share_btn.disabled = True
        try:
            share_btn.update()
        except Exception:
            pass

        try:
            share_svc = ft.Share()
            if getattr(share_svc, "_i", None) is None and hasattr(page, "_services") and page._services is not None:
                page._services.register_service(share_svc)

            img_p = async_state.get("img_path")
            cap = async_state.get("caption", "")
            if img_p and os.path.exists(img_p):
                share_file = ft.ShareFile(img_p)
                res = share_svc.share_files(
                    [share_file],
                    text=cap,
                    title=f"Nu Age Milestone • {title_text}",
                )
            else:
                res = share_svc.share_text(cap, title=f"Nu Age Milestone • {title_text}")

            if asyncio.iscoroutine(res):
                await asyncio.wait_for(res, timeout=12.0)
        except Exception as ex:
            print(f"[milestone_share_modal] share fallback: {ex}")
            await safe_set_clipboard(page, async_state.get("caption", ""))

        share_btn.disabled = False
        try:
            share_btn.update()
        except Exception:
            pass

    async def _handle_copy_caption(e=None):
        if not async_state["ready"]:
            return
        await safe_set_clipboard(page, async_state.get("caption", ""))
        orig_controls = list(copy_btn.content.controls)
        copy_btn.content = ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            tight=True,
            spacing=6,
            controls=[
                ft.Icon(ft.Icons.CHECK_ROUNDED, size=13, color=ft.Colors.GREEN_600),
                ft.Text("Copied!", size=11.5, weight=ft.FontWeight.W_700, color=ft.Colors.GREEN_600),
            ],
        )
        try:
            copy_btn.update()
        except Exception:
            pass
        await asyncio.sleep(2)
        copy_btn.content = ft.Row(alignment=ft.MainAxisAlignment.CENTER, tight=True, spacing=6, controls=orig_controls)
        try:
            copy_btn.update()
        except Exception:
            pass

    async def _handle_download(e=None):
        if not async_state["ready"] or not async_state.get("img_path"):
            return
        downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
        if not os.path.exists(downloads_dir):
            downloads_dir = tempfile.gettempdir()

        fname = f"Nu_Age_{milestone_type.value}_{metric_value.replace('%', '').replace('/', '_')}.png"
        target_dest = os.path.join(downloads_dir, fname)

        def _do_copy():
            shutil.copy2(async_state["img_path"], target_dest)

        await asyncio.to_thread(_do_copy)

        orig_controls = list(download_btn.content.controls)
        download_btn.content = ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            tight=True,
            spacing=6,
            controls=[
                ft.Icon(ft.Icons.CHECK_ROUNDED, size=13, color=ft.Colors.GREEN_600),
                ft.Text("Saved to Downloads!", size=11.5, weight=ft.FontWeight.W_700, color=ft.Colors.GREEN_600),
            ],
        )
        try:
            download_btn.update()
        except Exception:
            pass
        await asyncio.sleep(2.5)
        download_btn.content = ft.Row(alignment=ft.MainAxisAlignment.CENTER, tight=True, spacing=6, controls=orig_controls)
        try:
            download_btn.update()
        except Exception:
            pass

    share_btn.on_click = lambda _: page.run_task(_handle_share)
    copy_btn.on_click = lambda _: page.run_task(_handle_copy_caption)
    download_btn.on_click = lambda _: page.run_task(_handle_download)

    # 4. Preview Container
    loading_spinner = ft.ProgressRing(width=34, height=34, stroke_width=3, color=ft.Colors.PRIMARY)
    loading_label = ft.Text("Crafting celebration card...", size=12, color=ft.Colors.GREY_600, weight=ft.FontWeight.W_600)
    preview_box = ft.Container(
        width=preview_size,
        height=preview_size,
        border_radius=ft.BorderRadius.all(16),
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        alignment=ft.Alignment.CENTER,
        bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
        shadow=ft.BoxShadow(
            blur_radius=14,
            color=ft.Colors.with_opacity(0.14, ft.Colors.BLACK),
            offset=ft.Offset(0, 4),
        ),
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            controls=[loading_spinner, loading_label],
        ),
    )

    secondary_row = ft.Row(
        spacing=8,
        controls=[
            ft.Container(expand=True, content=download_btn),
            ft.Container(expand=True, content=copy_btn),
        ],
    )

    # 5. Build Modal Dialog
    modal_content_h = min(screen_h - 130, preview_size + 115)
    dlg_ref[0] = ft.AlertDialog(
        modal=True,
        bgcolor=dialog_bg,
        shape=ft.RoundedRectangleBorder(radius=18),
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(
                    spacing=8,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.STARS_ROUNDED, color=ft.Colors.AMBER_500, size=20),
                        ft.Text(title_text, size=14.5, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ],
                ),
                ft.IconButton(
                    icon=ft.Icons.CLOSE_ROUNDED,
                    icon_size=18,
                    icon_color=ft.Colors.GREY_500,
                    on_click=_close_dlg,
                ),
            ],
        ),
        content=ft.Container(
            width=content_w,
            height=modal_content_h,
            content=ft.Column(
                tight=True,
                spacing=12,
                scroll=ft.ScrollMode.AUTO,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    preview_box,
                    ft.Container(width=content_w, content=share_btn),
                    ft.Container(width=content_w, content=secondary_row),
                ],
            ),
        ),
        actions=[
            ft.TextButton(
                "Keep Learning",
                style=ft.ButtonStyle(color=ft.Colors.GREY_500),
                on_click=_close_dlg,
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.CENTER,
    )

    # 6. Immediately Open Modal (Instant Feedback, Zero Freezing)
    safe_open_dialog(page, dlg_ref[0], tag="milestone_share")

    # 7. Asynchronously Generate Card in Background Worker Thread
    async def _async_generate_card():
        try:
            # Offload heavy Pillow procedural rendering to thread
            card_data = await asyncio.to_thread(
                generate_milestone_card,
                milestone_type=milestone_type,
                user_name=resolved_name,
                avatar_source=avatar_url,
                metric_value=metric_value,
                subtitle=subtitle,
                tagline=tagline,
            )
            img_path = card_data["image_path"]
            async_state["img_path"] = img_path
            async_state["caption"] = card_data["caption"]
            async_state["ready"] = True

            # Read image into raw bytes for 100% reliable Flutter sandbox rendering
            def _read_bytes():
                if os.path.exists(img_path):
                    with open(img_path, "rb") as f:
                        return f.read()
                return None

            img_bytes = await asyncio.to_thread(_read_bytes)

            # Swap loading skeleton with generated card
            if img_bytes:
                preview_box.content = ft.Image(
                    src=img_bytes,
                    fit=ft.BoxFit.CONTAIN,
                    border_radius=ft.BorderRadius.all(14),
                )
            else:
                preview_box.content = ft.Image(
                    src=img_path,
                    fit=ft.BoxFit.CONTAIN,
                    border_radius=ft.BorderRadius.all(14),
                )

            share_btn.disabled = False
            download_btn.disabled = False
            copy_btn.disabled = False

            safe_update_dialog(page, dlg_ref[0])
        except Exception as gen_err:
            print(f"[milestone_share_modal] background generation failed: {gen_err}")
            preview_box.content = ft.Column(
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
                controls=[
                    ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, size=32, color=ft.Colors.AMBER_600),
                    ft.Text("Card preview unavailable.", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
            )
            share_btn.disabled = False
            copy_btn.disabled = False
            safe_update_dialog(page, dlg_ref[0])

    page.run_task(_async_generate_card)
