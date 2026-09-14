import flet as ft
import asyncio
from src.requests.playlists import (
    get_playlist,
    save_bulk_playlist_courses,
)
from src.requests.organisations import get_organisation_courses
from src.components.course_card_theme import get_course_module_meta


def _get_course_module_count(c: dict) -> int:
    if not isinstance(c, dict):
        return 0
    modules_data = (
        c.get("total_modules")
        or c.get("module_count")
        or c.get("modules")
        or (c.get("curriculum", {}).get("modules") if isinstance(c.get("curriculum"), dict) else None)
    )
    seed = c.get("id") or c.get("name") or "course"
    total_modules, _, _ = get_course_module_meta(modules_data, seed_key=seed)
    return total_modules


def _get_palette(is_dark: bool) -> dict:
    return {
        "page_bg": ft.Colors.SURFACE,
        "card_bg": "#181B24" if is_dark else "#FFFFFF",
        "card_bg_subtle": "#222736" if is_dark else "#F8FAFC",
        "border": ft.Colors.with_opacity(0.12, ft.Colors.WHITE) if is_dark else ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
        "text_primary": "#F8FAFC" if is_dark else "#0F172A",
        "text_secondary": "#94A3B8" if is_dark else "#64748B",
        "text_tertiary": "#64748B" if is_dark else "#94A3B8",
        "accent": ft.Colors.PRIMARY,
        "accent_light": ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
        "connector": ft.Colors.with_opacity(0.18, ft.Colors.PRIMARY if is_dark else ft.Colors.GREY_400),
    }


async def playlist_builder_view(page: ft.Page, playlist_id: str):
    token = None
    org_id = page.session.store.get("current_org_id")
    is_dark = page.theme_mode == ft.ThemeMode.DARK
    p = _get_palette(is_dark)

    # State
    playlist_data = {}
    playlist_courses = []
    local_courses = []  # Local staging list
    org_courses = []
    has_unsaved_changes = [False]

    # Loading Socket
    content_socket = ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        content=ft.ProgressRing(color=ft.Colors.PRIMARY, stroke_width=3, width=36, height=36),
    )

    async def load_data():
        nonlocal playlist_data, playlist_courses, local_courses, org_courses, token
        token = await page.shared_preferences.get("auth_token")

        # Load playlist info
        res = await get_playlist(token, playlist_id)
        if "error" not in res:
            playlist_data = res
            raw_courses = res.get("playlist_courses", [])
            playlist_courses = [item.get("course", {}) for item in raw_courses if "course" in item]
            local_courses = list(playlist_courses)

        # Load org courses for adding
        if org_id:
            fetched_org_courses = await get_organisation_courses(token, org_id)
            if isinstance(fetched_org_courses, list):
                org_courses = fetched_org_courses

    # ── Add Course Modal ──────────────────────────────────────────────────────
    def show_add_course_modal(e):
        current_dark = page.theme_mode == ft.ThemeMode.DARK
        dlg_palette = _get_palette(current_dark)

        # Exclude courses already in the local staging list
        existing_ids = {c.get("id") for c in local_courses if c.get("id")}
        available_courses = [c for c in org_courses if c.get("id") not in existing_ids]

        courses_list_view = ft.Column(
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        def close_dialog(ev=None):
            page.pop_dialog()

        def add_course_to_path(c_obj):
            local_courses.append(c_obj)
            has_unsaved_changes[0] = True
            close_dialog()
            render_curriculum()
            page.update()

        if available_courses:
            for c in available_courses:
                c_name = c.get("name", "Untitled Course")
                c_desc = c.get("description", "") or "No description provided."
                c_modules = _get_course_module_count(c)
                mod_label = f"{c_modules} {'module' if c_modules == 1 else 'modules'}"

                item_card = ft.Container(
                    bgcolor=dlg_palette["card_bg_subtle"],
                    border_radius=12,
                    border=ft.Border.all(1, dlg_palette["border"]),
                    padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                    ink=True,
                    on_click=lambda ev, obj=c: add_course_to_path(obj),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(
                                spacing=12,
                                expand=True,
                                controls=[
                                    ft.Container(
                                        width=38,
                                        height=38,
                                        border_radius=10,
                                        bgcolor=dlg_palette["accent_light"],
                                        alignment=ft.Alignment.CENTER,
                                        content=ft.Icon(
                                            ft.Icons.AUTO_STORIES_ROUNDED,
                                            size=18,
                                            color=dlg_palette["accent"],
                                        ),
                                    ),
                                    ft.Column(
                                        spacing=2,
                                        expand=True,
                                        controls=[
                                            ft.Text(
                                                c_name,
                                                size=13,
                                                weight=ft.FontWeight.BOLD,
                                                color=dlg_palette["text_primary"],
                                                max_lines=1,
                                                overflow=ft.TextOverflow.ELLIPSIS,
                                            ),
                                            ft.Text(
                                                f"{mod_label} • {c_desc}",
                                                size=11,
                                                color=dlg_palette["text_secondary"],
                                                max_lines=1,
                                                overflow=ft.TextOverflow.ELLIPSIS,
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            ft.IconButton(
                                icon=ft.Icons.ADD_ROUNDED,
                                icon_color=dlg_palette["accent"],
                                icon_size=20,
                                tooltip="Add to path",
                                on_click=lambda ev, obj=c: add_course_to_path(obj),
                            ),
                        ],
                    ),
                )
                courses_list_view.controls.append(item_card)
        else:
            courses_list_view.controls.append(
                ft.Container(
                    padding=ft.Padding.symmetric(vertical=24),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                        controls=[
                            ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, size=32, color=dlg_palette["accent"]),
                            ft.Text("All Courses Added", size=13, weight=ft.FontWeight.BOLD, color=dlg_palette["text_primary"]),
                            ft.Text(
                                "Every course in your organisation is already included in this path.",
                                size=11,
                                color=dlg_palette["text_secondary"],
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ],
                    ),
                )
            )

        modal_content = ft.Container(
            width=min(page.width or 600, 480),
            height=360,
            content=courses_list_view,
        )

        dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=18),
            bgcolor=dlg_palette["card_bg"],
            title=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row([
                        ft.Icon(ft.Icons.PLAYLIST_ADD_ROUNDED, color=dlg_palette["accent"], size=20),
                        ft.Text("Add Course to Path", size=16, weight=ft.FontWeight.BOLD, color=dlg_palette["text_primary"]),
                    ], spacing=8),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE_ROUNDED,
                        icon_size=18,
                        icon_color=dlg_palette["text_secondary"],
                        on_click=close_dialog,
                    ),
                ],
            ),
            content=modal_content,
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.show_dialog(dlg)
        page.update()

    # ── Save Curriculum Handler ───────────────────────────────────────────────
    async def on_save_curriculum(e):
        save_btn.disabled = True
        save_btn.text = "Saving…"
        page.update()

        course_ids = [c.get("id") for c in local_courses if c.get("id")]
        res = await save_bulk_playlist_courses(token, playlist_id, {"course_ids": course_ids})

        if "error" in res:
            save_btn.disabled = False
            save_btn.text = "Save Changes"
            page.update()

            dlg = ft.AlertDialog(
                shape=ft.RoundedRectangleBorder(radius=14),
                title=ft.Text("Save Error", size=15, weight=ft.FontWeight.BOLD),
                content=ft.Text(res["error"], size=13),
                actions=[ft.TextButton("Dismiss", on_click=lambda _: page.pop_dialog())],
            )
            page.show_dialog(dlg)
            page.update()
            return

        has_unsaved_changes[0] = False
        save_btn.disabled = False
        save_btn.text = "Saved"
        save_btn.icon = ft.Icons.CHECK_ROUNDED

        snack = ft.SnackBar(
            content=ft.Row(
                spacing=10,
                controls=[
                    ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.WHITE, size=18),
                    ft.Text("Learning path sequence saved successfully!", color=ft.Colors.WHITE, size=13),
                ],
            ),
            bgcolor=ft.Colors.GREEN_600,
            behavior=ft.SnackBarBehavior.FLOATING,
            shape=ft.RoundedRectangleBorder(radius=10),
            margin=ft.Margin.all(16),
        )
        page.show_dialog(snack)

        # Refresh baseline state
        await load_data()
        render_curriculum()
        page.update()

        await asyncio.sleep(2)
        save_btn.text = "Save Changes"
        save_btn.icon = ft.Icons.SAVE_ROUNDED
        page.update()

    # ── Header Action Controls ────────────────────────────────────────────────
    save_btn = ft.FilledButton(
        "Save Changes",
        icon=ft.Icons.SAVE_ROUNDED,
        height=40,
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.PRIMARY,
            color=ft.Colors.WHITE,
            shape=ft.RoundedRectangleBorder(radius=10),
            padding=ft.Padding.symmetric(horizontal=16, vertical=8),
        ),
        on_click=on_save_curriculum,
    )

    count_chip_text = ft.Text("0 Courses", size=11, weight=ft.FontWeight.W_600, color=ft.Colors.PRIMARY)
    count_chip = ft.Container(
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
        border_radius=20,
        bgcolor=p["accent_light"],
        content=count_chip_text,
    )

    # ── Curriculum List Container ─────────────────────────────────────────────
    curriculum_container = ft.Column(spacing=0)

    def render_curriculum():
        curriculum_container.controls.clear()
        total = len(local_courses)
        count_chip_text.value = f"{total} Course{'s' if total != 1 else ''} Sequenced"

        if not local_courses:
            empty_state = ft.Container(
                padding=ft.Padding.symmetric(vertical=48, horizontal=20),
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                    controls=[
                        ft.Container(
                            width=60,
                            height=60,
                            border_radius=30,
                            bgcolor=p["card_bg_subtle"],
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(
                                ft.Icons.ACCOUNT_TREE_ROUNDED,
                                size=28,
                                color=p["text_tertiary"],
                            ),
                        ),
                        ft.Text(
                            "Curriculum is Empty",
                            size=16,
                            weight=ft.FontWeight.BOLD,
                            color=p["text_primary"],
                        ),
                        ft.Text(
                            "Sequence courses to build an end-to-end guided learning journey.",
                            size=12,
                            color=p["text_secondary"],
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Container(height=6),
                        ft.FilledButton(
                            "Add First Course",
                            icon=ft.Icons.ADD_ROUNDED,
                            height=40,
                            style=ft.ButtonStyle(
                                bgcolor=p["accent"],
                                color=ft.Colors.WHITE,
                                shape=ft.RoundedRectangleBorder(radius=10),
                            ),
                            on_click=show_add_course_modal,
                        ),
                    ],
                ),
            )
            curriculum_container.controls.append(empty_state)
            return

        for index, c in enumerate(local_courses):
            c_name = c.get("name", "Untitled Course")
            c_desc = c.get("description", "") or "Curriculum module"
            c_modules = _get_course_module_count(c)
            mod_label = f"{c_modules} {'module' if c_modules == 1 else 'modules'}"
            step_num = f"{index + 1:02d}"

            def make_move_up(idx=index):
                def _fn(e):
                    if idx > 0:
                        local_courses[idx], local_courses[idx - 1] = local_courses[idx - 1], local_courses[idx]
                        has_unsaved_changes[0] = True
                        render_curriculum()
                        page.update()
                return _fn

            def make_move_down(idx=index):
                def _fn(e):
                    if idx < total - 1:
                        local_courses[idx], local_courses[idx + 1] = local_courses[idx + 1], local_courses[idx]
                        has_unsaved_changes[0] = True
                        render_curriculum()
                        page.update()
                return _fn

            def make_remove(idx=index):
                def _fn(e):
                    local_courses.pop(idx)
                    has_unsaved_changes[0] = True
                    render_curriculum()
                    page.update()
                return _fn

            # Step Course Card
            course_tile = ft.Container(
                bgcolor=p["card_bg"],
                border_radius=16,
                border=ft.Border.all(1, p["border"]),
                padding=ft.Padding.symmetric(horizontal=16, vertical=14),
                shadow=ft.BoxShadow(
                    blur_radius=8,
                    color=ft.Colors.with_opacity(0.03, ft.Colors.BLACK),
                    offset=ft.Offset(0, 2),
                ),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        # Step number + course info
                        ft.Row(
                            spacing=12,
                            expand=True,
                            controls=[
                                ft.Container(
                                    width=38,
                                    height=38,
                                    border_radius=10,
                                    bgcolor=p["accent_light"],
                                    alignment=ft.Alignment.CENTER,
                                    content=ft.Text(
                                        step_num,
                                        size=13,
                                        weight=ft.FontWeight.BOLD,
                                        color=p["accent"],
                                    ),
                                ),
                                ft.Column(
                                    spacing=2,
                                    expand=True,
                                    controls=[
                                        ft.Text(
                                            c_name,
                                            size=14,
                                            weight=ft.FontWeight.BOLD,
                                            color=p["text_primary"],
                                            max_lines=1,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                        ),
                                        ft.Row(
                                            spacing=6,
                                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                            controls=[
                                                ft.Icon(ft.Icons.PLAY_LESSON_ROUNDED, size=12, color=p["text_secondary"]),
                                                ft.Text(
                                                    mod_label,
                                                    size=11,
                                                    color=p["text_secondary"],
                                                    weight=ft.FontWeight.W_500,
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        # Reorder + Delete action buttons
                        ft.Row(
                            spacing=4,
                            tight=True,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.IconButton(
                                    icon=ft.Icons.KEYBOARD_ARROW_UP_ROUNDED,
                                    icon_size=20,
                                    icon_color=p["text_secondary"] if index > 0 else ft.Colors.with_opacity(0.2, p["text_secondary"]),
                                    disabled=(index == 0),
                                    tooltip="Move up in sequence",
                                    on_click=make_move_up(index),
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED,
                                    icon_size=20,
                                    icon_color=p["text_secondary"] if index < total - 1 else ft.Colors.with_opacity(0.2, p["text_secondary"]),
                                    disabled=(index == total - 1),
                                    tooltip="Move down in sequence",
                                    on_click=make_move_down(index),
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                    icon_size=19,
                                    icon_color=ft.Colors.RED_400,
                                    tooltip="Remove from path",
                                    style=ft.ButtonStyle(
                                        bgcolor={"": ft.Colors.with_opacity(0.08, ft.Colors.RED_400)},
                                        shape=ft.CircleBorder(),
                                    ),
                                    on_click=make_remove(index),
                                ),
                            ],
                        ),
                    ],
                ),
            )

            # Sequenced connector dot
            if index < total - 1:
                connector = ft.Container(
                    width=2,
                    height=18,
                    bgcolor=p["connector"],
                    margin=ft.Margin.only(left=34),
                )
                curriculum_container.controls.extend([course_tile, connector])
            else:
                curriculum_container.controls.append(course_tile)

        # Dashed / Outline Add Course Button at bottom of sequence
        add_more_card = ft.Container(
            margin=ft.Margin.only(top=14),
            padding=ft.Padding.symmetric(vertical=14),
            border_radius=14,
            border=ft.Border.all(1.5, ft.Colors.with_opacity(0.3, p["accent"])),
            bgcolor=ft.Colors.with_opacity(0.04, p["accent"]),
            ink=True,
            on_click=show_add_course_modal,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
                controls=[
                    ft.Icon(ft.Icons.ADD_ROUNDED, color=p["accent"], size=18),
                    ft.Text(
                        "Add Another Course to Path",
                        size=13,
                        weight=ft.FontWeight.BOLD,
                        color=p["accent"],
                    ),
                ],
            ),
        )
        curriculum_container.controls.append(add_more_card)

    # ── Main Assembly ─────────────────────────────────────────────────────────
    async def render_full_view():
        await load_data()
        playlist_title = playlist_data.get("title") or playlist_data.get("name") or "Learning Path"

        # Modern Minimalist Header
        header_banner = ft.Container(
            gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
                colors=[
                    p["accent"],
                    ft.Colors.with_opacity(0.85, p["accent"]),
                ],
            ),
            border_radius=ft.BorderRadius.only(bottom_left=28, bottom_right=28),
            padding=ft.Padding(left=16, right=20, top=20, bottom=24),
            shadow=ft.BoxShadow(
                blur_radius=20,
                color=ft.Colors.with_opacity(0.18, p["accent"]),
                offset=ft.Offset(0, 6),
            ),
            content=ft.Row(
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED,
                        icon_color=ft.Colors.WHITE,
                        icon_size=18,
                        tooltip="Back to Organizations",
                        style=ft.ButtonStyle(
                            bgcolor={"": ft.Colors.with_opacity(0.18, ft.Colors.WHITE)},
                            shape=ft.CircleBorder(),
                        ),
                        on_click=lambda _: page.go("/organisations"),
                    ),
                    ft.Column(
                        spacing=2,
                        expand=True,
                        controls=[
                            ft.Text(
                                "Curriculum Builder",
                                size=18,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.WHITE,
                            ),
                            ft.Text(
                                playlist_title,
                                size=12,
                                weight=ft.FontWeight.W_500,
                                color=ft.Colors.with_opacity(0.9, ft.Colors.WHITE),
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                    ),
                    save_btn,
                ],
            ),
        )

        # Toolbar row
        toolbar = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row([
                    ft.Icon(ft.Icons.TIMELINE_ROUNDED, size=18, color=p["accent"]),
                    ft.Text("Sequence Flow", size=14, weight=ft.FontWeight.BOLD, color=p["text_primary"]),
                ], spacing=8),
                count_chip,
            ],
        )

        render_curriculum()

        # Responsive centered column
        body_content = ft.Container(
            alignment=ft.Alignment.TOP_CENTER,
            content=ft.Container(
                width=min(page.width or 800, 680),
                padding=ft.Padding.symmetric(horizontal=16, vertical=20),
                content=ft.Column(
                    spacing=16,
                    controls=[
                        toolbar,
                        curriculum_container,
                        ft.Container(height=32),
                    ],
                ),
            ),
        )

        content_socket.content = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=0,
            controls=[
                header_banner,
                body_content,
            ],
        )
        content_socket.alignment = None
        page.update()

    page.run_task(render_full_view)

    return ft.View(
        route=f"/playlists/{playlist_id}/build",
        bgcolor=ft.Colors.SURFACE,
        padding=0,
        controls=[
            ft.SafeArea(
                expand=True,
                content=content_socket,
            ),
        ],
    )