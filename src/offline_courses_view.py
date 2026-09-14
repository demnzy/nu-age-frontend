"""
src/offline_courses_view.py

The offline library entry point: reachable regardless of connectivity or auth-token
validity, listing all courses that have been downloaded locally with their offline progress.
Reads from SQLite (via local_db.py) and synchronizes progress back up to the cloud
via progress_sync.py.
"""

import asyncio
from datetime import datetime
import flet as ft
from src.local_db import get_local_db
from src.download_manager import delete_downloaded_course
from src.progress_sync import sync_offline_progress, has_unsynced_progress, SyncResult


def is_mobile(page: ft.Page) -> bool:
    w = getattr(page, "width", None)
    if w is None and hasattr(page, "window") and page.window:
        w = getattr(page.window, "width", None)
    return (w or 0) < 768


async def offline_courses_view(page: ft.Page, back_target: str = None) -> ft.View:
    db = get_local_db(page)

    def handle_back(e):
        if back_target:
            page.go(back_target)
            return
        if len(page.views) > 1:
            page.views.pop()
            top = page.views[-1]
            page.route = getattr(top, "route", "/dashboard")
            page.update()
        else:
            has_user = (page.session.store.get("current_user") is not None) if hasattr(page, "session") and hasattr(page.session, "store") else False
            page.go("/dashboard" if has_user else "/")

    search_query = [""]
    active_filter = ["all"]  # 'all' | 'in_progress' | 'completed'

    def get_downloaded_courses():
        return db.execute(
            """
            SELECT 
                c.id, c.name, c.description, c.downloaded_at, c.total_size_bytes,
                (SELECT COUNT(*) FROM downloaded_modules WHERE course_id = c.id) as module_count,
                (SELECT COUNT(*) FROM downloaded_lessons l 
                 JOIN downloaded_modules m ON l.module_id = m.id 
                 WHERE m.course_id = c.id) as lesson_count,
                (SELECT COUNT(*) FROM lesson_progress lp 
                 WHERE lp.course_id = c.id AND lp.status = 'completed') as completed_count
            FROM downloaded_courses c
            ORDER BY c.downloaded_at DESC
            """
        ).fetchall()

    def get_unsynced_count() -> int:
        try:
            row = db.execute(
                "SELECT COUNT(*) FROM lesson_progress WHERE synced_at IS NULL"
            ).fetchone()
            return row[0] if row else 0
        except Exception:
            return 0

    def format_size(size_bytes: int) -> str:
        if not size_bytes:
            return "0 KB"
        mb = size_bytes / (1024 * 1024)
        if mb >= 1000:
            return f"{mb / 1024:.2f} GB"
        return f"{mb:.1f} MB" if mb >= 1 else f"{max(1, size_bytes // 1024)} KB"

    def format_date(iso_str: str) -> str:
        if not iso_str:
            return ""
        try:
            dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            return dt.strftime("%b %d, %Y")
        except Exception:
            return iso_str[:10]

    async def handle_open_course(e, course_id: str):
        # Explicitly route to offline course view so main.py strictly loads
        # the offline SQLite-backed engine without probing or attempting network
        page.go(f"/courses/{course_id}/offline")

    async def handle_delete_course(e, course_id: str, course_name: str):
        async def confirm_delete(e):
            page.pop_dialog()
            await delete_downloaded_course(page, course_id)
            await refresh_list()

        def cancel_delete(e):
            page.pop_dialog()

        dialog = ft.AlertDialog(
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.DELETE_OUTLINE_ROUNDED, color=ft.Colors.ERROR, size=22),
                    ft.Text("Remove Download?", weight=ft.FontWeight.BOLD, size=16),
                ],
                spacing=8,
            ),
            content=ft.Column(
                [
                    ft.Text(f"Are you sure you want to remove '{course_name}' from local storage?"),
                    ft.Text(
                        "Your lesson progress and completed quiz scores are safely preserved on your device and will not be lost.",
                        size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=10,
                tight=True,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=cancel_delete),
                ft.FilledButton("Remove Course", on_click=confirm_delete, style=ft.ButtonStyle(bgcolor=ft.Colors.ERROR)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.show_dialog(dialog)

    # --- UI Components ---
    sync_status_icon = ft.Icon(ft.Icons.CLOUD_DONE_ROUNDED, size=18, color=ft.Colors.GREEN_600)
    sync_status_title = ft.Text("All progress in sync", weight=ft.FontWeight.BOLD, size=13)
    sync_status_subtitle = ft.Text("Local learning is up to date with cloud", size=11, color=ft.Colors.ON_SURFACE_VARIANT)
    sync_action_btn = ft.FilledButton(
        "Sync Now",
        icon=ft.Icons.SYNC_ROUNDED,
        height=34,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=8),
            padding=ft.Padding.symmetric(horizontal=12, vertical=0),
        ),
    )

    sync_card = ft.Container(
        col={"sm": 12, "md": 6},
        border_radius=12,
        padding=12,
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.OUTLINE)),
    )

    storage_stat_text = ft.Text("0 Courses · 0 MB cached", size=11, color=ft.Colors.ON_SURFACE_VARIANT)
    storage_card = ft.Container(
        col={"sm": 12, "md": 6},
        border_radius=12,
        padding=12,
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.OUTLINE)),
        content=ft.Row(
            [
                ft.Container(
                    width=36,
                    height=36,
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(ft.Icons.SD_STORAGE_ROUNDED, color=ft.Colors.PRIMARY, size=18),
                ),
                ft.Column(
                    [
                        ft.Text("Local Offline Storage", weight=ft.FontWeight.BOLD, size=13),
                        storage_stat_text,
                    ],
                    spacing=2,
                    tight=True,
                ),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )

    hero_section = ft.ResponsiveRow(
        [storage_card, sync_card],
        spacing=10,
        run_spacing=10,
    )

    def on_search_change(e):
        search_query[0] = e.control.value or ""
        clear_search_btn.visible = bool(search_query[0])
        render_courses()
        page.update()

    def clear_search_click(e):
        search_query[0] = ""
        search_field.value = ""
        clear_search_btn.visible = False
        render_courses()
        page.update()

    clear_search_btn = ft.IconButton(
        ft.Icons.CLEAR_ROUNDED,
        icon_size=16,
        tooltip="Clear search",
        visible=False,
        on_click=clear_search_click,
    )

    search_field = ft.TextField(
        hint_text="Search downloaded courses...",
        prefix_icon=ft.Icons.SEARCH_ROUNDED,
        suffix=clear_search_btn,
        height=40,
        text_size=13,
        content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        border_radius=10,
        on_change=on_search_change,
        expand=True,
    )

    text_all = ft.Text("All Courses", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY)
    text_in_prog = ft.Text("In Progress", size=12, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE)
    text_comp = ft.Text("Completed", size=12, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE)

    def set_filter(filter_name: str):
        active_filter[0] = filter_name
        is_all = (filter_name == "all")
        is_in = (filter_name == "in_progress")
        is_co = (filter_name == "completed")

        chip_all.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if is_all else ft.Colors.SURFACE_CONTAINER_HIGH
        text_all.color = ft.Colors.PRIMARY if is_all else ft.Colors.ON_SURFACE
        text_all.weight = ft.FontWeight.BOLD if is_all else ft.FontWeight.W_500

        chip_in_prog.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if is_in else ft.Colors.SURFACE_CONTAINER_HIGH
        text_in_prog.color = ft.Colors.PRIMARY if is_in else ft.Colors.ON_SURFACE
        text_in_prog.weight = ft.FontWeight.BOLD if is_in else ft.FontWeight.W_500

        chip_comp.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if is_co else ft.Colors.SURFACE_CONTAINER_HIGH
        text_comp.color = ft.Colors.PRIMARY if is_co else ft.Colors.ON_SURFACE
        text_comp.weight = ft.FontWeight.BOLD if is_co else ft.FontWeight.W_500

        render_courses()
        page.update()

    chip_all = ft.Container(
        content=text_all,
        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        border_radius=8,
        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
        on_click=lambda e: set_filter("all"),
    )
    chip_in_prog = ft.Container(
        content=text_in_prog,
        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        border_radius=8,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
        on_click=lambda e: set_filter("in_progress"),
    )
    chip_comp = ft.Container(
        content=text_comp,
        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        border_radius=8,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
        on_click=lambda e: set_filter("completed"),
    )

    filter_row = ft.Row(
        [chip_all, chip_in_prog, chip_comp],
        spacing=8,
        tight=True,
        wrap=True,
    )

    search_bar_container = ft.Container(
        content=ft.Column(
            [
                ft.Row([search_field], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                filter_row,
            ],
            spacing=8,
            tight=True,
        )
    )

    course_list_column = ft.Column(spacing=12, expand=True, scroll=ft.ScrollMode.AUTO)

    cached_courses = []

    def build_course_card(course_id, name, description, downloaded_at, size_bytes, module_count, lesson_count, completed_count):
        pct = int(round((completed_count / lesson_count) * 100)) if lesson_count > 0 else 0
        is_completed = (completed_count == lesson_count and lesson_count > 0)
        is_in_progress = (0 < completed_count < lesson_count)
        prog_fraction = (completed_count / lesson_count) if lesson_count > 0 else 0.0

        accent_color = ft.Colors.GREEN_600 if is_completed else ft.Colors.PRIMARY

        btn_text = "Review Course" if is_completed else ("Continue Learning" if is_in_progress else "Start Learning")
        btn_icon = ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED if is_completed else ft.Icons.PLAY_ARROW_ROUNDED

        progress_badge = ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=2),
            border_radius=6,
            bgcolor=ft.Colors.with_opacity(0.1, accent_color),
            content=ft.Text(
                "COMPLETED" if is_completed else (f"{pct}% DONE" if is_in_progress else "NOT STARTED"),
                size=10,
                weight=ft.FontWeight.BOLD,
                color=accent_color,
            ),
        )

        metadata_chips = ft.Row(
            [
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=6,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                    content=ft.Row(
                        [ft.Icon(ft.Icons.FOLDER_OUTLINED, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                         ft.Text(f"{module_count} module{'s' if module_count != 1 else ''}", size=11, color=ft.Colors.ON_SURFACE_VARIANT)],
                        spacing=4,
                        tight=True,
                    ),
                ),
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=6,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                    content=ft.Row(
                        [ft.Icon(ft.Icons.ARTICLE_OUTLINED, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                         ft.Text(f"{lesson_count} lesson{'s' if lesson_count != 1 else ''}", size=11, color=ft.Colors.ON_SURFACE_VARIANT)],
                        spacing=4,
                        tight=True,
                    ),
                ),
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=6,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                    content=ft.Row(
                        [ft.Icon(ft.Icons.STORAGE_ROUNDED, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                         ft.Text(format_size(size_bytes), size=11, color=ft.Colors.ON_SURFACE_VARIANT)],
                        spacing=4,
                        tight=True,
                    ),
                ),
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=6,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                    content=ft.Row(
                        [ft.Icon(ft.Icons.ACCESS_TIME_ROUNDED, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                         ft.Text(format_date(downloaded_at), size=11, color=ft.Colors.ON_SURFACE_VARIANT)],
                        spacing=4,
                        tight=True,
                    ),
                ),
            ],
            spacing=6,
            wrap=True,
        )

        return ft.Container(
            padding=16,
            border_radius=16,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.OUTLINE)),
            content=ft.Column(
                [
                    # Top Row: Icon, Title & Delete
                    ft.Row(
                        [
                            ft.Container(
                                width=40,
                                height=40,
                                border_radius=10,
                                bgcolor=ft.Colors.with_opacity(0.1, accent_color),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.SCHOOL_ROUNDED, color=accent_color, size=20),
                            ),
                            ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Text(name, weight=ft.FontWeight.BOLD, size=15, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                            progress_badge,
                                        ],
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                    ft.Text(
                                        description or "Downloaded for offline study",
                                        size=12,
                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                        max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                icon_size=18,
                                icon_color=ft.Colors.ON_SURFACE_VARIANT,
                                tooltip="Remove download",
                                on_click=lambda e, cid=course_id, cname=name: page.run_task(handle_delete_course, e, cid, cname),
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=12,
                    ),
                    # Metadata chips
                    metadata_chips,
                    # Progress indicator
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(f"{completed_count} of {lesson_count} completed", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ft.Text(f"{pct}%", size=11, weight=ft.FontWeight.BOLD, color=accent_color),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.ProgressBar(
                                value=prog_fraction,
                                color=accent_color,
                                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                                height=5,
                                border_radius=3,
                            ),
                        ],
                        spacing=4,
                    ),
                    # Action Button
                    ft.Row(
                        [
                            ft.FilledButton(
                                btn_text,
                                icon=btn_icon,
                                height=38,
                                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                                on_click=lambda e, cid=course_id: page.run_task(handle_open_course, e, cid),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.END,
                    ),
                ],
                spacing=12,
            ),
        )

    def render_courses():
        course_list_column.controls.clear()
        q = search_query[0].lower().strip()
        f = active_filter[0]

        filtered = []
        for row in cached_courses:
            cid, name, desc, dl_at, size_b, mod_cnt, les_cnt, comp_cnt = row
            if q and (q not in name.lower() and q not in (desc or "").lower()):
                continue
            if f == "completed" and (comp_cnt < les_cnt or les_cnt == 0):
                continue
            if f == "in_progress" and (comp_cnt == 0 or comp_cnt >= les_cnt):
                continue
            filtered.append(row)

        if not cached_courses:
            course_list_column.controls.append(
                ft.Container(
                    padding=48,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        [
                            ft.Container(
                                width=64,
                                height=64,
                                border_radius=32,
                                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.OFFLINE_PIN_OUTLINED, size=32, color=ft.Colors.PRIMARY),
                            ),
                            ft.Text("No Downloaded Courses", size=16, weight=ft.FontWeight.BOLD),
                            ft.Container(
                                width=360,
                                content=ft.Text(
                                    "Save your enrolled courses while online to continue learning offline anytime, anywhere.",
                                    size=12,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                            ),
                            ft.FilledButton(
                                "Explore Courses",
                                icon=ft.Icons.EXPLORE_ROUNDED,
                                height=38,
                                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                                on_click=lambda e: page.go("/courses"),
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=12,
                    ),
                )
            )
        elif not filtered:
            course_list_column.controls.append(
                ft.Container(
                    padding=40,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.SEARCH_OFF_ROUNDED, size=36, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(f"No courses match '{q or f}'", size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.TextButton("Reset Filter", on_click=clear_search_click),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                    ),
                )
            )
        else:
            for row in filtered:
                course_list_column.controls.append(build_course_card(*row))

    def is_mounted(ctrl: ft.Control) -> bool:
        try:
            return ctrl.page is not None
        except Exception:
            return False

    def safe_page_update():
        try:
            page.update()
        except Exception:
            pass

    async def refresh_sync_status():
        unsynced_count = get_unsynced_count()
        if unsynced_count > 0:
            sync_status_icon.name = ft.Icons.SYNC_PROBLEM_ROUNDED
            sync_status_icon.color = ft.Colors.AMBER_600
            sync_status_title.value = f"{unsynced_count} update{'s' if unsynced_count != 1 else ''} pending sync"
            sync_status_title.color = ft.Colors.AMBER_700
            sync_status_subtitle.value = "Will sync automatically when connected"
            sync_action_btn.visible = True
            sync_action_btn.disabled = False
            sync_action_btn.text = "Sync Now"
            sync_action_btn.icon = ft.Icons.SYNC_ROUNDED
        else:
            sync_status_icon.name = ft.Icons.CLOUD_DONE_ROUNDED
            sync_status_icon.color = ft.Colors.GREEN_600
            sync_status_title.value = "All progress in sync"
            sync_status_title.color = ft.Colors.ON_SURFACE
            sync_status_subtitle.value = "Local learning matches cloud records"
            sync_action_btn.visible = False

        sync_card.content = ft.Row(
            [
                ft.Container(
                    width=36,
                    height=36,
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.1, sync_status_icon.color),
                    alignment=ft.Alignment.CENTER,
                    content=sync_status_icon,
                ),
                ft.Column(
                    [
                        sync_status_title,
                        sync_status_subtitle,
                    ],
                    spacing=2,
                    expand=True,
                    tight=True,
                ),
                sync_action_btn,
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        if is_mounted(sync_card):
            safe_page_update()

    async def handle_sync_click(e):
        sync_action_btn.disabled = True
        sync_action_btn.text = "Syncing..."
        sync_status_title.value = "Syncing progress with cloud..."
        sync_status_title.color = ft.Colors.PRIMARY
        sync_status_subtitle.value = "Connecting to server..."
        sync_status_icon.name = ft.Icons.SYNC_ROUNDED
        sync_status_icon.color = ft.Colors.PRIMARY
        safe_page_update()

        result: SyncResult = await sync_offline_progress(page)

        unsynced_count = get_unsynced_count()
        if result.status == "done" and unsynced_count == 0:
            sync_status_icon.name = ft.Icons.CLOUD_DONE_ROUNDED
            sync_status_icon.color = ft.Colors.GREEN_600
            sync_status_title.value = "All progress in sync!"
            sync_status_title.color = ft.Colors.GREEN_700
            sync_status_subtitle.value = f"Synced {result.synced} offline record{'s' if result.synced != 1 else ''} to cloud"
            sync_action_btn.visible = False
        elif result.status == "done" and unsynced_count > 0:
            sync_status_icon.name = ft.Icons.SYNC_PROBLEM_ROUNDED
            sync_status_icon.color = ft.Colors.AMBER_600
            sync_status_title.value = f"{unsynced_count} update{'s' if unsynced_count != 1 else ''} still pending"
            sync_status_title.color = ft.Colors.AMBER_700
            sync_status_subtitle.value = f"Synced {result.synced} of {result.total} records. Tap to retry remaining."
            sync_action_btn.visible = True
            sync_action_btn.disabled = False
            sync_action_btn.text = "Retry Sync"
        elif result.status == "nothing_to_sync":
            sync_status_icon.name = ft.Icons.CLOUD_DONE_ROUNDED
            sync_status_icon.color = ft.Colors.GREEN_600
            sync_status_title.value = "All progress in sync"
            sync_status_title.color = ft.Colors.ON_SURFACE
            sync_status_subtitle.value = "Local records match cloud"
            sync_action_btn.visible = False
        else:
            sync_status_icon.name = ft.Icons.SYNC_PROBLEM_ROUNDED
            sync_status_icon.color = ft.Colors.RED_600
            sync_status_title.value = "Sync Failed"
            sync_status_title.color = ft.Colors.RED_700
            sync_status_subtitle.value = result.error_message or "Unable to reach server"
            sync_action_btn.visible = True
            sync_action_btn.disabled = False
            sync_action_btn.text = "Retry Sync"

        sync_card.content = ft.Row(
            [
                ft.Container(
                    width=36,
                    height=36,
                    border_radius=8,
                    bgcolor=ft.Colors.with_opacity(0.1, sync_status_icon.color),
                    alignment=ft.Alignment.CENTER,
                    content=sync_status_icon,
                ),
                ft.Column(
                    [
                        sync_status_title,
                        sync_status_subtitle,
                    ],
                    spacing=2,
                    expand=True,
                    tight=True,
                ),
                sync_action_btn,
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        nonlocal cached_courses
        cached_courses = get_downloaded_courses()
        render_courses()
        safe_page_update()

    sync_action_btn.on_click = lambda e: page.run_task(handle_sync_click, e)

    async def refresh_list():
        nonlocal cached_courses
        cached_courses = get_downloaded_courses()

        total_bytes = sum(r[4] or 0 for r in cached_courses)
        total_lessons = sum(r[6] or 0 for r in cached_courses)
        storage_stat_text.value = f"{len(cached_courses)} Course{'s' if len(cached_courses) != 1 else ''} · {total_lessons} Lessons · {format_size(total_bytes)}"

        render_courses()
        await refresh_sync_status()

        if is_mounted(course_list_column):
            safe_page_update()
        else:
            await asyncio.sleep(0.05)
            if is_mounted(course_list_column):
                safe_page_update()

    view = ft.View(
        route="/offline",
        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
        appbar=ft.AppBar(
            leading=ft.IconButton(
                ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED,
                tooltip="Return",
                icon_size=18,
                on_click=handle_back,
            ),
            title=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text("Offline Library", weight=ft.FontWeight.BOLD, size=17),
                            ft.Container(
                                content=ft.Text("OFFLINE", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                border_radius=6,
                                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                            ),
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Text("Downloaded courses & local progress", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
                spacing=1,
            ),
            actions=[
                ft.IconButton(
                    ft.Icons.REFRESH_ROUNDED,
                    tooltip="Refresh Library",
                    icon_size=20,
                    on_click=lambda e: page.run_task(refresh_list),
                )
            ],
            bgcolor=ft.Colors.SURFACE,
        ),
        controls=[
            ft.SafeArea(
                expand=True,
                content=ft.Container(
                    padding=ft.Padding.symmetric(
                        horizontal=12 if is_mobile(page) else 24,
                        vertical=12,
                    ),
                    content=ft.Column(
                        [
                            hero_section,
                            search_bar_container,
                            ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.OUTLINE)),
                            course_list_column,
                        ],
                        spacing=12,
                        expand=True,
                    ),
                ),
            )
        ],
    )

    # Return the view with loading indicator and populate via page.run_task
    # after mount (avoids "Control must be added to page first")
    course_list_column.controls.append(
        ft.Container(
            padding=40,
            alignment=ft.Alignment.CENTER,
            content=ft.ProgressRing(width=28, height=28, stroke_width=3),
        )
    )
    page.run_task(refresh_list)

    return view