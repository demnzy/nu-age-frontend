import asyncio
import base64

import flet as ft
from src.components.bottom_appbar import get_bottom_appbar
from src.requests.Courses import create_course, get_categories, get_courses
from src.requests.organisations import get_my_organisation, get_organisation_members


# ── shared field style ────────────────────────────────────────────────────────
_INPUT = {
    "border_color": ft.Colors.GREY_300,
    "focused_border_color": ft.Colors.PRIMARY,
    "cursor_color": ft.Colors.PRIMARY,
    "border_radius": 10,
    "text_size": 13,
    "content_padding": ft.padding.symmetric(horizontal=14, vertical=12),
}

def _section_label(text: str) -> ft.Text:
    return ft.Text(text, size=11, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_500)


# ─────────────────────────────────────────────────────────────────────────────
# VIEW
# ─────────────────────────────────────────────────────────────────────────────
async def create_courses_view(page: ft.Page, org_id: str = None):
    app_bar = get_bottom_appbar(page)
    token   = await page.shared_preferences.get("auth_token")

    # ── view-level state ──────────────────────────────────────────────────────
    categories_options: list = []
    teachers_options:   list = []
    theme_color              = ft.Colors.PRIMARY
    current_courses:    list = []

    # ── content socket (spinner → real layout) ────────────────────────────────
    content_socket = ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.ProgressRing(color=ft.Colors.PRIMARY, width=36, height=36),
                ft.Text("Loading courses…", size=13, color=ft.Colors.GREY_500),
            ],
        ),
    )

    # ─────────────────────────────────────────────────────────────────────────
    # COURSE CARD
    # ─────────────────────────────────────────────────────────────────────────
    def build_course_card(course: dict) -> ft.Container:
        title       = course.get("name",        "Untitled Course")
        desc        = course.get("description", "No description available.")
        image_url   = course.get("image_url")
        course_id   = course.get("id", "")
        is_public   = course.get("public",      False)
        is_supervised = course.get("supervised", False)
        students    = len(course.get("Students", []))

        # ── badges ────────────────────────────────────────────────────────────
        def pill(label, bg, fg):
            return ft.Container(
                padding=ft.padding.symmetric(horizontal=8, vertical=3),
                bgcolor=bg, border_radius=10,
                content=ft.Text(label, size=10, color=fg, weight=ft.FontWeight.W_600),
            )

        status_badge = pill(
            "Public" if is_public else "Draft",
            ft.Colors.GREEN_50 if is_public else ft.Colors.GREY_100,
            ft.Colors.GREEN_700 if is_public else ft.Colors.GREY_600,
        )
        type_badge = pill(
            "Instructor-Led" if is_supervised else "Automated",
            ft.Colors.BLUE_50 if is_supervised else ft.Colors.PURPLE_50,
            ft.Colors.BLUE_700 if is_supervised else ft.Colors.PURPLE_700,
        )

        # ── action buttons ────────────────────────────────────────────────────
        # "Curriculum" → course builder / content editor
        curriculum_btn = ft.ElevatedButton(
            content=ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                tight=True,
                spacing=6,
                controls=[
                    ft.Icon(ft.Icons.MENU_BOOK_ROUNDED, size=14, color=ft.Colors.WHITE),
                    ft.Text("Curriculum", size=12, color=ft.Colors.WHITE, weight=ft.FontWeight.W_600),
                ],
            ),
            bgcolor=theme_color,
            expand=True,
            height=36,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                elevation=0,
                padding=ft.padding.symmetric(vertical=0, horizontal=8),
            ),
            on_click=lambda e, cid=course_id: page.go(f"/courses/{cid}/manage"),
        )

        # "Analytics" → course stats / performance
        analytics_btn = ft.OutlinedButton(
            content=ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                tight=True,
                spacing=6,
                controls=[
                    ft.Icon(ft.Icons.BAR_CHART_ROUNDED, size=14, color=theme_color),
                    ft.Text("Analytics", size=12, color=theme_color, weight=ft.FontWeight.W_600),
                ],
            ),
            expand=True,
            height=36,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
                side=ft.BorderSide(1, theme_color),
                padding=ft.padding.symmetric(vertical=0, horizontal=8),
            ),
            on_click=lambda e, cid=course_id: page.go(f"/courses/{cid}/analytics"),
        )

        # ── settings icon (top-right of card) ────────────────────────────────
        settings_btn = ft.IconButton(
            ft.Icons.SETTINGS_OUTLINED,
            icon_size=16,
            icon_color=ft.Colors.GREY_400,
            tooltip="Course Settings",
            on_click=lambda e, oid=org_id, cid=course_id: page.go(f"/organisations/{oid}/courses/{cid}/settings"),
        )

        return ft.Container(
            col={"xs": 12, "sm": 6, "md": 4, "lg": 3},
            bgcolor=ft.Colors.SURFACE,
            border_radius=14,
            border=ft.border.all(1, ft.Colors.GREY_200),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            shadow=ft.BoxShadow(
                blur_radius=8,
                color=ft.Colors.with_opacity(0.07, ft.Colors.BLACK),
                offset=ft.Offset(0, 3),
            ),
            content=ft.Column(
                spacing=0,
                controls=[
                    # ── Cover image ───────────────────────────────────────────
                    ft.Container(
                        width=float("inf"),
                        height=130,
                        bgcolor=ft.Colors.GREY_100,
                        content=ft.Image(
                            src=image_url or "https://nu-age-cdn.b-cdn.net/logos/placeholder%202.png",
                            fit=ft.BoxFit.COVER,
                        ),
                    ),

                    # ── Card body ─────────────────────────────────────────────
                    ft.Container(
                        padding=ft.padding.only(left=14, right=6, top=12, bottom=14),
                        content=ft.Column(
                            spacing=8,
                            controls=[
                                # Badges + settings icon on same row
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Row([status_badge, type_badge], spacing=6, wrap=True, expand=True),
                                        settings_btn,
                                    ],
                                ),

                                # Title
                                ft.Text(
                                    title, size=15,
                                    weight=ft.FontWeight.W_700,
                                    color=ft.Colors.ON_SURFACE,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),

                                # Description
                                ft.Text(
                                    desc, size=12,
                                    color=ft.Colors.GREY_500,
                                    max_lines=2,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),

                                # Student count
                                ft.Row(
                                    spacing=4,
                                    controls=[
                                        ft.Icon(ft.Icons.PEOPLE_ALT_ROUNDED, size=13, color=ft.Colors.GREY_400),
                                        ft.Text(f"{students} enrolled", size=11, color=ft.Colors.GREY_400),
                                    ],
                                ),

                                ft.Divider(height=1, color=ft.Colors.GREY_100),

                                # Action buttons side by side
                                ft.Row(
                                    spacing=8,
                                    controls=[curriculum_btn, analytics_btn],
                                ),
                            ],
                        ),
                    ),
                ],
            ),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # GRID
    # ─────────────────────────────────────────────────────────────────────────
    courses_grid = ft.ResponsiveRow(run_spacing=16, spacing=16)

    def refresh_grid(initial_load=False):
        courses_grid.controls.clear()
        if not current_courses:
            courses_grid.controls.append(
                ft.Container(
                    col=12,
                    padding=ft.padding.symmetric(vertical=60),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=10,
                        controls=[
                            ft.Icon(ft.Icons.LIBRARY_BOOKS_OUTLINED, size=44, color=ft.Colors.GREY_300),
                            ft.Text("No courses yet.", size=15, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_400),
                            ft.Text("Click 'New Course' to get started.", size=13, color=ft.Colors.GREY_400),
                        ],
                    ),
                )
            )
        else:
            for course in current_courses:
                courses_grid.controls.append(build_course_card(course))

        if not initial_load:
            page.update()

    # ─────────────────────────────────────────────────────────────────────────
    # CREATE MODAL
    # ─────────────────────────────────────────────────────────────────────────
    def open_create_modal(e):
        # ── fields ────────────────────────────────────────────────────────────
        name_input = ft.TextField(label="Course Title *", **_INPUT)
        desc_input = ft.TextField(
            label="Short Description",
            multiline=True, min_lines=2, max_lines=3,
            **_INPUT,
        )
        category_dropdown = ft.Dropdown(
            label="Category",
            options=categories_options,
            border_color=ft.Colors.GREY_300,
            focused_border_color=ft.Colors.PRIMARY,
            border_radius=10,
        )
        teacher_dropdown = ft.Dropdown(
            label="Assign Teacher (Optional)",
            options=teachers_options,
            border_color=ft.Colors.GREY_300,
            focused_border_color=ft.Colors.PRIMARY,
            border_radius=10,
        )

        # ── objectives ────────────────────────────────────────────────────────
        objectives_list  = []
        objectives_chips = ft.Row(wrap=True, spacing=6)

        def add_objective(e):
            val = obj_input.value.strip()
            if not val or val in objectives_list:
                return
            objectives_list.append(val)

            def remove_chip(ev):
                chip = ev.control
                objectives_list.remove(chip.data)
                objectives_chips.controls.remove(chip)
                page.update()

            objectives_chips.controls.append(
                ft.Chip(
                    label=ft.Text(val, size=12),
                    data=val,
                    delete_icon=ft.Icon(ft.Icons.CANCEL, size=14),
                    on_delete=remove_chip,
                )
            )
            obj_input.value = ""
            page.update()

        obj_input = ft.TextField(
            label="Type an objective and press Enter",
            on_submit=add_objective,
            suffix=ft.IconButton(
                ft.Icons.ADD_CIRCLE_OUTLINE_ROUNDED,
                icon_color=ft.Colors.PRIMARY,
                icon_size=18,
                on_click=add_objective,
            ),
            **_INPUT,
        )

        # ── logo picker ───────────────────────────────────────────────────────
        selected_logo_bytes = None
        selected_logo_name  = None
        logo_icon = ft.Icon(ft.Icons.CLOUD_UPLOAD_OUTLINED, color=ft.Colors.PRIMARY, size=28)
        logo_text = ft.Text("Upload Cover Image (Optional)", color=ft.Colors.GREY_500, size=13)

        async def handle_logo_pick(ev):
            nonlocal selected_logo_bytes, selected_logo_name
            try:
                files = await ft.FilePicker().pick_files(
                    allow_multiple=False,
                    file_type=ft.FilePickerFileType.IMAGE,
                    with_data=True,
                )
                if files:
                    selected              = files[0]
                    selected_logo_bytes   = selected.bytes
                    selected_logo_name    = selected.name
                    logo_icon.name        = ft.Icons.CHECK_CIRCLE_ROUNDED
                    logo_icon.color       = ft.Colors.GREEN_600
                    logo_text.value       = f"Selected: {selected_logo_name}"
                    logo_text.color       = ft.Colors.GREEN_600
                    page.update()
            except Exception:
                logo_text.value = "Could not open file picker. Try again."
                logo_text.color = ft.Colors.RED_700
                page.update()

        image_picker_container = ft.Container(
            width=float("inf"),
            padding=ft.padding.symmetric(vertical=18),
            border=ft.border.all(1, ft.Colors.GREY_300),
            border_radius=10,
            ink=True,
            on_click=handle_logo_pick,
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=6,
                controls=[logo_icon, logo_text],
            ),
        )

        # ── error text ────────────────────────────────────────────────────────
        error_text = ft.Text("", color=ft.Colors.RED_700, size=12,
                             visible=False, weight=ft.FontWeight.W_500)

        # ── modal controls ────────────────────────────────────────────────────
        def close_modal(ev=None):
            modal.open = False
            page.update()

        async def submit_course(ev):
            nonlocal selected_logo_bytes, selected_logo_name
            if not name_input.value or not name_input.value.strip():
                error_text.value   = "Course Title is required."
                error_text.visible = True
                page.update()
                return

            error_text.visible = False
            submit_btn.disabled = True
            submit_btn.content = ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    ft.ProgressRing(width=14, height=14, color=ft.Colors.WHITE, stroke_width=2),
                    ft.Text("Creating…", color=ft.Colors.WHITE, size=13, weight=ft.FontWeight.W_600),
                ],
            )
            page.update()

            try:
                logo_b64 = (
                    base64.b64encode(selected_logo_bytes).decode("utf-8")
                    if selected_logo_bytes else None
                )
                payload = {
                    "name":           name_input.value.strip(),
                    "category_id":    category_dropdown.value,
                    "description":    desc_input.value or name_input.value,
                    "public":         False,
                    "objectives":     objectives_list,
                    "image_bytes":    logo_b64,
                    "image_filename": selected_logo_name,
                    "org_id":         org_id,
                    "teacher_id":     teacher_dropdown.value or None,
                }

                new_course = await asyncio.wait_for(
                    create_course(token, payload), timeout=20
                )

                if isinstance(new_course, dict):
                    current_courses.insert(0, new_course)
                    close_modal()
                    refresh_grid()
                else:
                    raise ValueError("Unexpected server response.")

            except asyncio.TimeoutError:
                error_text.value   = "Request timed out. Check your connection and try again."
                error_text.visible = True
                submit_btn.disabled = False
                submit_btn.content = ft.Text("Create Course", color=ft.Colors.WHITE,
                                             size=13, weight=ft.FontWeight.W_600)
                page.update()

            except Exception as ex:
                error_text.value   = f"Something went wrong ({type(ex).__name__}). Please try again."
                error_text.visible = True
                submit_btn.disabled = False
                submit_btn.content = ft.Text("Create Course", color=ft.Colors.WHITE,
                                             size=13, weight=ft.FontWeight.W_600)
                page.update()

        submit_btn = ft.ElevatedButton(
            content=ft.Text("Create Course", color=ft.Colors.WHITE,
                            size=13, weight=ft.FontWeight.W_600),
            bgcolor=ft.Colors.PRIMARY,
            height=44,
            expand=True,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                elevation=0,
            ),
            on_click=submit_course,
        )

        modal = ft.AlertDialog(
            modal=True,
            bgcolor=ft.Colors.SURFACE,
            title=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Text("New Course", size=17, weight=ft.FontWeight.W_700,
                            color=ft.Colors.ON_SURFACE),
                    ft.IconButton(
                        ft.Icons.CLOSE_ROUNDED,
                        icon_size=18,
                        icon_color=ft.Colors.GREY_400,
                        on_click=close_modal,
                    ),
                ],
            ),
            content=ft.Container(
                width=520,
                height=480,
                content=ft.Column(
                    scroll=ft.ScrollMode.AUTO,
                    spacing=14,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    controls=[
                        # ── Course basics ─────────────────────────────────────
                        _section_label("COURSE DETAILS"),
                        name_input,
                        desc_input,

                        # ── Organisation ──────────────────────────────────────
                        _section_label("CLASSIFICATION"),
                        category_dropdown,
                        teacher_dropdown,

                        # ── Cover image ───────────────────────────────────────
                        _section_label("COVER IMAGE"),
                        image_picker_container,

                        # ── Objectives ────────────────────────────────────────
                        _section_label("LEARNING OBJECTIVES"),
                        obj_input,
                        objectives_chips,

                        ft.Divider(height=1, color=ft.Colors.GREY_100),
                        error_text,
                        ft.Row(controls=[submit_btn]),
                        ft.Container(height=8),
                    ],
                ),
            ),
            actions=[],          # actions moved into content for layout control
        )

        page.overlay.append(modal)
        modal.open = True
        page.update()

    # ─────────────────────────────────────────────────────────────────────────
    # MAIN LAYOUT (built after data loads)
    # ─────────────────────────────────────────────────────────────────────────
    def build_main_layout():
        return ft.Column(
            expand=True,
            controls=[
                # ── Header banner ─────────────────────────────────────────────
                ft.Container(
                    bgcolor=theme_color,
                    border_radius=ft.BorderRadius.only(bottom_left=24, bottom_right=24),
                    padding=ft.padding.only(left=20, right=20, top=14, bottom=20),
                    content=ft.Column(
                        spacing=12,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Column(
                                        spacing=2,
                                        controls=[
                                            ft.Text("Course Library", size=22,
                                                    weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                                            ft.Text(
                                                f"{len(current_courses)} course{'s' if len(current_courses) != 1 else ''}",
                                                size=13, color=ft.Colors.with_opacity(0.8, ft.Colors.WHITE),
                                            ),
                                        ],
                                    ),
                                    ft.ElevatedButton(
                                        content=ft.Row(
                                            tight=True,
                                            spacing=6,
                                            controls=[
                                                ft.Icon(ft.Icons.ADD_ROUNDED, size=16, color=theme_color),
                                                ft.Text("New Course", size=13,
                                                        color=theme_color, weight=ft.FontWeight.W_700),
                                            ],
                                        ),
                                        bgcolor=ft.Colors.WHITE,
                                        height=40,
                                        style=ft.ButtonStyle(
                                            shape=ft.RoundedRectangleBorder(radius=10),
                                            elevation=0,
                                        ),
                                        on_click=open_create_modal,
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),

                # ── Grid ──────────────────────────────────────────────────────
                ft.Container(
                    expand=True,
                    padding=ft.padding.symmetric(horizontal=16, vertical=16),
                    content=ft.Column(
                        expand=True,
                        scroll=ft.ScrollMode.AUTO,
                        controls=[courses_grid, ft.Container(height=20)],
                    ),
                ),
            ],
        )

    # ─────────────────────────────────────────────────────────────────────────
    # DATA FETCHER
    # ─────────────────────────────────────────────────────────────────────────
    async def fetch_initial_data():
        nonlocal categories_options, theme_color, current_courses, teachers_options

        try:
            categories, teachers, org_data, courses = await asyncio.gather(
                asyncio.wait_for(get_categories(token, None),                                   timeout=15),
                asyncio.wait_for(get_organisation_members(token, id=org_id, teachers=True),     timeout=15),
                asyncio.wait_for(get_my_organisation(token),                                    timeout=15),
                asyncio.wait_for(get_courses(token, params={"org": org_id}),                    timeout=15),
                return_exceptions=True,
            )

            # categories
            if isinstance(categories, list):
                categories_options = [
                    ft.dropdown.Option(key=c["id"], text=c["name"]) for c in categories
                ]

            # teachers
            if isinstance(teachers, list):
                teachers_options = [
                    ft.dropdown.Option(
                        key=t["id"],
                        text=f"{t['first_name']} {t['last_name']}".title(),
                    )
                    for t in teachers
                ]

            # theme
            if isinstance(org_data, dict):
                theme_color = org_data.get("theme_color", ft.Colors.PRIMARY)

            # courses
            if isinstance(courses, list):
                current_courses = courses

            refresh_grid(initial_load=True)
            content_socket.alignment = None
            content_socket.content   = build_main_layout()
            page.update()

        except asyncio.TimeoutError:
            _show_load_error("Connection timed out.", ft.Icons.WIFI_OFF_ROUNDED, ft.Colors.ORANGE_400)

        except Exception as ex:
            _show_load_error(
                f"Failed to load data ({type(ex).__name__}).",
                ft.Icons.ERROR_OUTLINE_ROUNDED,
                ft.Colors.RED_400,
            )

    def _show_load_error(message: str, icon, color):
        content_socket.alignment = ft.Alignment.CENTER
        content_socket.content = ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            controls=[
                ft.Icon(icon, size=48, color=color),
                ft.Text("Could not load courses", size=16, weight=ft.FontWeight.W_600,
                        color=ft.Colors.ON_SURFACE),
                ft.Text(message, size=13, color=ft.Colors.GREY_500,
                        text_align=ft.TextAlign.CENTER),
                ft.Container(height=4),
                ft.ElevatedButton(
                    "Retry",
                    bgcolor=ft.Colors.PRIMARY,
                    color=ft.Colors.WHITE,
                    height=42,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
                    on_click=lambda _: page.run_task(fetch_initial_data),
                ),
            ],
        )
        page.update()

    page.run_task(fetch_initial_data)

    # ─────────────────────────────────────────────────────────────────────────
    # VIEW
    # ─────────────────────────────────────────────────────────────────────────
    return ft.View(
        route=f"/organisations/{org_id}/courses" if org_id else "/courses",
        bottom_appbar=app_bar,
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        padding=0,
        controls=[
            ft.SafeArea(expand=True, content=content_socket)
        ],
    )