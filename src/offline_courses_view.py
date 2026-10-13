"""
src/offline_courses_view.py

The offline library entry point: reachable regardless of connectivity or auth-token
validity, sectionally listing both downloaded courses and offline study materials
(flashcard decks, quick quizzes, exam simulations, notes, and study packs).
Reads from SQLite (via local_db.py) and synchronizes progress back up to the cloud
via progress_sync.py.
"""

import asyncio
from datetime import datetime
import re
import flet as ft
from src.local_db import (
    get_local_db,
    get_offline_study_materials,
    delete_offline_study_material,
    is_study_material_downloaded,
)
from src.download_manager import (
    delete_downloaded_course,
    delete_downloaded_study_material,
    get_plain_language_sync_status,
)
from src.progress_sync import sync_offline_progress, has_unsynced_progress, SyncResult
from src.utils.file_opener import show_page_snackbar


def is_mobile(page: ft.Page) -> bool:
    w = getattr(page, "width", None)
    if w is None and hasattr(page, "window") and page.window:
        w = getattr(page.window, "width", None)
    return (w or 0) < 768


def clean_pack_import_tag(title: str) -> str:
    """Strip [pack import] or (pack import) prefixes, suffixes, or bracketed labels from material titles."""
    if not title or not isinstance(title, str):
        return ""
    t = re.sub(r"(?i)\s*[\[\(]\s*pack\s*import\s*[\]\)]\s*[:\-–—]?\s*", " ", title)
    t = re.sub(r"(?i)^pack\s*import\s*[:\-–—]?\s*", "", t)
    return t.strip()


async def offline_courses_view(page: ft.Page, back_target: str = None) -> ft.View:
    db = get_local_db(page)

    def handle_back(e):
        page.go("/")

    # State
    active_tab = ["courses"]  # 'courses' | 'study'
    search_query = [""]
    courses_filter = ["all"]    # 'all' | 'in_progress' | 'completed'
    study_filter = ["all"]      # 'all' | 'packs' | 'notes' | 'due'

    cached_courses = []
    cached_study_materials = []

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

    def get_downloaded_materials():
        return get_offline_study_materials(page)

    def get_unsynced_count() -> int:
        lesson_count = 0
        study_count = 0
        try:
            row = db.execute(
                "SELECT COUNT(*) FROM lesson_progress WHERE synced_at IS NULL"
            ).fetchone()
            lesson_count = row[0] if row else 0
        except Exception:
            pass

        try:
            row2 = db.execute(
                "SELECT COUNT(*) FROM study_review_queue WHERE synced_at IS NULL"
            ).fetchone()
            study_count = row2[0] if row2 else 0
        except Exception:
            pass

        return lesson_count + study_count

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

    def safe_dialog_close(dlg: ft.AlertDialog):
        dlg.open = False
        page.update()

    async def handle_open_course(e, course_id: str):
        page.go(f"/courses/{course_id}/offline")

    async def handle_delete_course(e, course_id: str, course_name: str):
        async def confirm_delete(e):
            safe_dialog_close(dialog)
            await delete_downloaded_course(page, course_id)
            await refresh_list()
            show_page_snackbar(page, f"Removed '{course_name}' from local storage.")

        dialog = ft.AlertDialog(
            shape=ft.RoundedRectangleBorder(radius=16),
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
                        "Your lesson progress and completed quiz scores are safely preserved on your device and will sync when reconnected.",
                        size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=10,
                tight=True,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: safe_dialog_close(dialog)),
                ft.FilledButton("Remove Course", on_click=confirm_delete, style=ft.ButtonStyle(bgcolor=ft.Colors.ERROR)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(dialog)
        dialog.open = True
        page.update()

    async def handle_delete_study_mat(e, material_id: str, title: str):
        async def confirm_delete(e):
            safe_dialog_close(dialog)
            await delete_downloaded_study_material(page, material_id)
            await refresh_list()
            show_page_snackbar(page, f"Removed '{title}' from offline storage.")

        dialog = ft.AlertDialog(
            shape=ft.RoundedRectangleBorder(radius=16),
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.DELETE_OUTLINE_ROUNDED, color=ft.Colors.ERROR, size=22),
                    ft.Text("Remove Offline Material?", weight=ft.FontWeight.BOLD, size=16),
                ],
                spacing=8,
            ),
            content=ft.Column(
                [
                    ft.Text(f"Are you sure you want to remove '{title}' from offline storage?"),
                    ft.Text(
                        "Your local flashcards, quiz questions, and exam items for this material will be cleared from offline cache.",
                        size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=10,
                tight=True,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: safe_dialog_close(dialog)),
                ft.FilledButton("Remove Material", on_click=confirm_delete, style=ft.ButtonStyle(bgcolor=ft.Colors.ERROR)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(dialog)
        dialog.open = True
        page.update()

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

    storage_stat_text = ft.Text("0 Courses · 0 Study Packs · 0 MB cached", size=11, color=ft.Colors.ON_SURFACE_VARIANT)
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

    # ─────────────────────────────────────────────────────────────────────────
    # SECTION SWITCHER (COURSES vs STUDY HUB)
    # ─────────────────────────────────────────────────────────────────────────
    tab_courses_text = ft.Text("Courses (0)", size=12.5, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY)
    tab_study_text = ft.Text("Study Vault (0)", size=12.5, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE)

    tab_courses_btn = ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.SCHOOL_ROUNDED, size=15, color=ft.Colors.PRIMARY),
                tab_courses_text,
            ],
            spacing=6,
            tight=True,
        ),
        padding=ft.Padding.symmetric(horizontal=14, vertical=8),
        border_radius=8,
        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
        ink=True,
        on_click=lambda _: switch_section("courses"),
    )

    tab_study_btn = ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.STYLE_ROUNDED, size=15, color=ft.Colors.ON_SURFACE_VARIANT),
                tab_study_text,
            ],
            spacing=6,
            tight=True,
        ),
        padding=ft.Padding.symmetric(horizontal=14, vertical=8),
        border_radius=8,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
        ink=True,
        on_click=lambda _: switch_section("study"),
    )

    section_switcher = ft.Container(
        padding=ft.Padding.all(4),
        border_radius=10,
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.OUTLINE)),
        content=ft.Row(
            [tab_courses_btn, tab_study_btn],
            spacing=4,
            tight=True,
        ),
    )

    def switch_section(section_name: str):
        active_tab[0] = section_name
        is_c = (section_name == "courses")

        tab_courses_btn.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if is_c else ft.Colors.SURFACE_CONTAINER_HIGH
        tab_courses_text.color = ft.Colors.PRIMARY if is_c else ft.Colors.ON_SURFACE
        tab_courses_text.weight = ft.FontWeight.BOLD if is_c else ft.FontWeight.W_600
        tab_courses_btn.content.controls[0].color = ft.Colors.PRIMARY if is_c else ft.Colors.ON_SURFACE_VARIANT

        tab_study_btn.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if not is_c else ft.Colors.SURFACE_CONTAINER_HIGH
        tab_study_text.color = ft.Colors.PRIMARY if not is_c else ft.Colors.ON_SURFACE
        tab_study_text.weight = ft.FontWeight.BOLD if not is_c else ft.FontWeight.W_600
        tab_study_btn.content.controls[0].color = ft.Colors.PRIMARY if not is_c else ft.Colors.ON_SURFACE_VARIANT

        search_field.hint_text = "Search downloaded courses..." if is_c else "Search offline study materials..."
        filter_row_courses.visible = is_c
        filter_row_study.visible = not is_c

        render_content()
        safe_page_update()

    # ─────────────────────────────────────────────────────────────────────────
    # SEARCH & FILTERS
    # ─────────────────────────────────────────────────────────────────────────
    def on_search_change(e):
        search_query[0] = e.control.value or ""
        clear_search_btn.visible = bool(search_query[0])
        render_content()
        page.update()

    def clear_search_click(e):
        search_query[0] = ""
        search_field.value = ""
        clear_search_btn.visible = False
        render_content()
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

    # Courses filters
    text_c_all = ft.Text("All Courses", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY)
    text_c_in_prog = ft.Text("In Progress", size=12, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE)
    text_c_comp = ft.Text("Completed", size=12, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE)

    def set_course_filter(f_name: str):
        courses_filter[0] = f_name
        is_all = (f_name == "all")
        is_in = (f_name == "in_progress")
        is_co = (f_name == "completed")

        chip_c_all.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if is_all else ft.Colors.SURFACE_CONTAINER_HIGH
        text_c_all.color = ft.Colors.PRIMARY if is_all else ft.Colors.ON_SURFACE
        text_c_all.weight = ft.FontWeight.BOLD if is_all else ft.FontWeight.W_500

        chip_c_in_prog.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if is_in else ft.Colors.SURFACE_CONTAINER_HIGH
        text_c_in_prog.color = ft.Colors.PRIMARY if is_in else ft.Colors.ON_SURFACE
        text_c_in_prog.weight = ft.FontWeight.BOLD if is_in else ft.FontWeight.W_500

        chip_c_comp.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if is_co else ft.Colors.SURFACE_CONTAINER_HIGH
        text_c_comp.color = ft.Colors.PRIMARY if is_co else ft.Colors.ON_SURFACE
        text_c_comp.weight = ft.FontWeight.BOLD if is_co else ft.FontWeight.W_500

        render_content()
        page.update()

    chip_c_all = ft.Container(
        content=text_c_all,
        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        border_radius=8,
        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
        on_click=lambda e: set_course_filter("all"),
    )
    chip_c_in_prog = ft.Container(
        content=text_c_in_prog,
        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        border_radius=8,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
        on_click=lambda e: set_course_filter("in_progress"),
    )
    chip_c_comp = ft.Container(
        content=text_c_comp,
        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        border_radius=8,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
        on_click=lambda e: set_course_filter("completed"),
    )

    filter_row_courses = ft.Row(
        [chip_c_all, chip_c_in_prog, chip_c_comp],
        spacing=8,
        tight=True,
        wrap=True,
    )

    # Study filters
    text_s_all = ft.Text("All Materials", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY)
    text_s_packs = ft.Text("Study Packs", size=12, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE)
    text_s_notes = ft.Text("Notes / PDFs", size=12, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE)
    text_s_due = ft.Text("Cards Due", size=12, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE)

    def set_study_filter(f_name: str):
        study_filter[0] = f_name
        is_all = (f_name == "all")
        is_pk = (f_name == "packs")
        is_nt = (f_name == "notes")
        is_du = (f_name == "due")

        chip_s_all.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if is_all else ft.Colors.SURFACE_CONTAINER_HIGH
        text_s_all.color = ft.Colors.PRIMARY if is_all else ft.Colors.ON_SURFACE
        text_s_all.weight = ft.FontWeight.BOLD if is_all else ft.FontWeight.W_500

        chip_s_packs.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if is_pk else ft.Colors.SURFACE_CONTAINER_HIGH
        text_s_packs.color = ft.Colors.PRIMARY if is_pk else ft.Colors.ON_SURFACE
        text_s_packs.weight = ft.FontWeight.BOLD if is_pk else ft.FontWeight.W_500

        chip_s_notes.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if is_nt else ft.Colors.SURFACE_CONTAINER_HIGH
        text_s_notes.color = ft.Colors.PRIMARY if is_nt else ft.Colors.ON_SURFACE
        text_s_notes.weight = ft.FontWeight.BOLD if is_nt else ft.FontWeight.W_500

        chip_s_due.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY) if is_du else ft.Colors.SURFACE_CONTAINER_HIGH
        text_s_due.color = ft.Colors.PRIMARY if is_du else ft.Colors.ON_SURFACE
        text_s_due.weight = ft.FontWeight.BOLD if is_du else ft.FontWeight.W_500

        render_content()
        page.update()

    chip_s_all = ft.Container(
        content=text_s_all,
        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        border_radius=8,
        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
        on_click=lambda e: set_study_filter("all"),
    )
    chip_s_packs = ft.Container(
        content=text_s_packs,
        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        border_radius=8,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
        on_click=lambda e: set_study_filter("packs"),
    )
    chip_s_notes = ft.Container(
        content=text_s_notes,
        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        border_radius=8,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
        on_click=lambda e: set_study_filter("notes"),
    )
    chip_s_due = ft.Container(
        content=text_s_due,
        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
        border_radius=8,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
        on_click=lambda e: set_study_filter("due"),
    )

    filter_row_study = ft.Row(
        [chip_s_all, chip_s_packs, chip_s_notes, chip_s_due],
        spacing=8,
        tight=True,
        wrap=True,
        visible=False,
    )

    search_bar_container = ft.Container(
        content=ft.Column(
            [
                ft.Row([section_switcher], alignment=ft.MainAxisAlignment.START),
                ft.Row([search_field], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                filter_row_courses,
                filter_row_study,
            ],
            spacing=10,
            tight=True,
        )
    )

    content_list_column = ft.Column(
        key="offline_library_scroll_column",
        spacing=12,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # COURSE CARD BUILDER
    # ─────────────────────────────────────────────────────────────────────────
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
                        [ft.Icon(ft.Icons.SYNC_ROUNDED, size=12, color=ft.Colors.GREEN_500),
                         ft.Text(get_plain_language_sync_status(downloaded_at), size=11, color=ft.Colors.ON_SURFACE_VARIANT)],
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

    # ─────────────────────────────────────────────────────────────────────────
    # STUDY MATERIAL CARD BUILDER
    # ─────────────────────────────────────────────────────────────────────────
    def build_study_material_card(mat: dict):
        mid = str(mat.get("id"))
        raw_title = mat.get("title") or "Untitled Document"
        clean_title = clean_pack_import_tag(raw_title) or "Study Pack"
        stype = (mat.get("source_type") or "text").lower()
        is_pack = (stype == "pack_import")
        dl_at = mat.get("downloaded_at") or ""

        # Fetch local cards & questions stats for this material
        cards_count = 0
        due_count = 0
        questions_count = 0
        try:
            r_c = db.execute("SELECT COUNT(*) FROM downloaded_flashcards WHERE material_id = ?", (mid,)).fetchone()
            cards_count = r_c[0] if r_c else 0
            r_due = db.execute(
                "SELECT COUNT(*) FROM downloaded_flashcards WHERE material_id = ? AND (next_review_date IS NULL OR next_review_date <= date('now'))",
                (mid,)
            ).fetchone()
            due_count = r_due[0] if r_due else 0
            r_q = db.execute("SELECT COUNT(*) FROM downloaded_study_questions WHERE material_id = ?", (mid,)).fetchone()
            questions_count = r_q[0] if r_q else 0
        except Exception:
            pass

        if is_pack:
            tag_label = "📦 Study Pack"
            tag_color = ft.Colors.GREEN_600
            tag_icon = ft.Icons.STOREFRONT_ROUNDED
        elif "pdf" in stype or raw_title.lower().endswith(".pdf"):
            tag_label = "PDF Notes"
            tag_color = ft.Colors.RED_500
            tag_icon = ft.Icons.PICTURE_AS_PDF_ROUNDED
        elif "url" in stype:
            tag_label = "Web / Video"
            tag_color = ft.Colors.TEAL_600
            tag_icon = ft.Icons.LINK_ROUNDED
        else:
            tag_label = "Quiz & Cards"
            tag_color = ft.Colors.PURPLE_500
            tag_icon = ft.Icons.STYLE_ROUNDED

        type_badge = ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=2),
            border_radius=6,
            bgcolor=ft.Colors.with_opacity(0.1, tag_color),
            content=ft.Text(tag_label, size=10, weight=ft.FontWeight.BOLD, color=tag_color),
        )

        metadata_chips = ft.Row(
            [
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=6,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.STYLE_ROUNDED, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(f"{cards_count} card{'s' if cards_count != 1 else ''}", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Container(
                                visible=due_count > 0,
                                padding=ft.Padding.symmetric(horizontal=4, vertical=1),
                                border_radius=4,
                                bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.AMBER),
                                content=ft.Text(f"{due_count} due", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_800),
                            ),
                        ],
                        spacing=4,
                        tight=True,
                    ),
                ),
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=6,
                    bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.BOLT_ROUNDED, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(f"{questions_count} drill questions", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                        spacing=4,
                        tight=True,
                    ),
                ),
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=6,
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.GREEN),
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=12, color=ft.Colors.GREEN_600),
                            ft.Text("Offline Ready", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_700),
                        ],
                        spacing=4,
                        tight=True,
                    ),
                ),
            ],
            spacing=6,
            wrap=True,
        )

        # Action Buttons (Cards, Quiz, Exam, Open)
        study_actions = ft.Row(
            spacing=8,
            wrap=True,
            controls=[
                ft.FilledButton(
                    "Cards",
                    icon=ft.Icons.STYLE_ROUNDED,
                    height=36,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.PRIMARY,
                        shape=ft.RoundedRectangleBorder(radius=8),
                        padding=ft.Padding.symmetric(horizontal=12, vertical=0),
                    ),
                    tooltip="Review spaced repetition flashcards offline",
                    on_click=lambda _: page.go(f"/self-study?offline=true&mat_id={mid}&action=flashcards"),
                ),
                ft.FilledButton(
                    "Quiz",
                    icon=ft.Icons.BOLT_ROUNDED,
                    height=36,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.TEAL_700,
                        shape=ft.RoundedRectangleBorder(radius=8),
                        padding=ft.Padding.symmetric(horizontal=12, vertical=0),
                    ),
                    tooltip="Take quick comprehension quiz offline",
                    on_click=lambda _: page.go(f"/self-study?offline=true&mat_id={mid}&action=quiz"),
                ),
                ft.FilledButton(
                    "Exam Sim",
                    icon=ft.Icons.TIMER_OUTLINED,
                    height=36,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.ORANGE_800,
                        shape=ft.RoundedRectangleBorder(radius=8),
                        padding=ft.Padding.symmetric(horizontal=12, vertical=0),
                    ),
                    tooltip="Run timed mock exam offline",
                    on_click=lambda _: page.go(f"/self-study?offline=true&mat_id={mid}&action=exam"),
                ),
                ft.OutlinedButton(
                    "Open Vault",
                    icon=ft.Icons.AUTO_STORIES_ROUNDED,
                    height=36,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8),
                        padding=ft.Padding.symmetric(horizontal=12, vertical=0),
                    ),
                    on_click=lambda _: page.go(f"/self-study?offline=true&mat_id={mid}"),
                ),
            ],
        )

        return ft.Container(
            padding=16,
            border_radius=16,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.OUTLINE)),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Container(
                                width=40,
                                height=40,
                                border_radius=10,
                                bgcolor=ft.Colors.with_opacity(0.1, tag_color),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(tag_icon, color=tag_color, size=20),
                            ),
                            ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Text(clean_title, weight=ft.FontWeight.BOLD, size=15, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                            type_badge,
                                        ],
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    ),
                                    ft.Text(
                                        f"Downloaded {format_date(dl_at)} · Ready for offline drills",
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
                                tooltip="Remove offline download",
                                on_click=lambda e, m=mid, t=clean_title: page.run_task(handle_delete_study_mat, e, m, t),
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=12,
                    ),
                    metadata_chips,
                    study_actions,
                ],
                spacing=12,
            ),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # CONTENT RENDERING
    # ─────────────────────────────────────────────────────────────────────────
    def render_content():
        content_list_column.controls.clear()
        q = search_query[0].lower().strip()

        if active_tab[0] == "courses":
            f = courses_filter[0]
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
                content_list_column.controls.append(
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
                                        "Save enrolled courses while online to continue learning lessons and quizzes offline anytime.",
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
                content_list_column.controls.append(
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
                    content_list_column.controls.append(build_course_card(*row))

        else:
            # Study Vault tab
            f = study_filter[0]
            filtered_mats = []
            for mat in cached_study_materials:
                t = (mat.get("title") or "").lower()
                st = (mat.get("source_type") or "").lower()
                if q and (q not in t and q not in st):
                    continue
                if f == "packs" and st != "pack_import":
                    continue
                if f == "notes" and st == "pack_import":
                    continue
                if f == "due":
                    # Check if any cards due
                    mid = str(mat.get("id"))
                    r_due = db.execute(
                        "SELECT COUNT(*) FROM downloaded_flashcards WHERE material_id = ? AND (next_review_date IS NULL OR next_review_date <= date('now'))",
                        (mid,)
                    ).fetchone()
                    if not r_due or r_due[0] == 0:
                        continue
                filtered_mats.append(mat)

            if not cached_study_materials:
                content_list_column.controls.append(
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
                                    content=ft.Icon(ft.Icons.AUTO_STORIES_ROUNDED, size=32, color=ft.Colors.PRIMARY),
                                ),
                                ft.Text("No Study Materials Downloaded", size=16, weight=ft.FontWeight.BOLD),
                                ft.Container(
                                    width=380,
                                    content=ft.Text(
                                        "Save flashcards, lecture notes, or peer study packs for offline spaced repetition reviews and quizzes.",
                                        size=12,
                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                        text_align=ft.TextAlign.CENTER,
                                    ),
                                ),
                                ft.FilledButton(
                                    "Open Self Study Hub",
                                    icon=ft.Icons.FOLDER_SPECIAL_ROUNDED,
                                    height=38,
                                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                                    on_click=lambda e: page.go("/self-study?offline=true"),
                                ),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=12,
                        ),
                    )
                )
            elif not filtered_mats:
                content_list_column.controls.append(
                    ft.Container(
                        padding=40,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Column(
                            [
                                ft.Icon(ft.Icons.SEARCH_OFF_ROUNDED, size=36, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(f"No study materials match '{q or f}'", size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.TextButton("Reset Filter", on_click=clear_search_click),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=8,
                        ),
                    )
                )
            else:
                for mat in filtered_mats:
                    content_list_column.controls.append(build_study_material_card(mat))

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
            sync_status_subtitle.value = "Will sync automatically when internet is available"
            sync_action_btn.visible = True
            sync_action_btn.disabled = False
            sync_action_btn.text = "Sync Now"
            sync_action_btn.icon = ft.Icons.SYNC_ROUNDED
        else:
            sync_status_icon.name = ft.Icons.CLOUD_DONE_ROUNDED
            sync_status_icon.color = ft.Colors.GREEN_600
            sync_status_title.value = "All progress in sync"
            sync_status_title.color = ft.Colors.ON_SURFACE
            sync_status_subtitle.value = "Local records match cloud database"
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
        sync_status_title.value = "Syncing progress & reviews..."
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

        nonlocal cached_courses, cached_study_materials
        cached_courses = get_downloaded_courses()
        cached_study_materials = get_downloaded_materials()
        render_content()
        safe_page_update()

    sync_action_btn.on_click = lambda e: page.run_task(handle_sync_click, e)

    async def refresh_list():
        nonlocal cached_courses, cached_study_materials
        cached_courses = get_downloaded_courses()
        cached_study_materials = get_downloaded_materials()

        tab_courses_text.value = f"Courses ({len(cached_courses)})"
        tab_study_text.value = f"Study Vault ({len(cached_study_materials)})"

        total_bytes = sum(r[4] or 0 for r in cached_courses)
        total_lessons = sum(r[6] or 0 for r in cached_courses)
        storage_stat_text.value = f"{len(cached_courses)} Course{'s' if len(cached_courses) != 1 else ''} ({total_lessons} lessons) · {len(cached_study_materials)} Study Item{'s' if len(cached_study_materials) != 1 else ''} · {format_size(total_bytes)}"

        render_content()
        await refresh_sync_status()

        if is_mounted(content_list_column):
            safe_page_update()
        else:
            await asyncio.sleep(0.05)
            if is_mounted(content_list_column):
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
                            ft.Text("Offline Learning Library", weight=ft.FontWeight.BOLD, size=16),
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
                    ft.Text("Downloaded courses, study materials, flashcards & exams", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
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
            elevation=0,
            center_title=False,
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
                            content_list_column,
                        ],
                        spacing=12,
                        expand=True,
                    ),
                ),
            )
        ],
    )

    content_list_column.controls.append(
        ft.Container(
            padding=40,
            alignment=ft.Alignment.CENTER,
            content=ft.ProgressRing(width=28, height=28, stroke_width=3),
        )
    )
    page.run_task(refresh_list)

    return view