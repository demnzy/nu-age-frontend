import asyncio

import flet as ft
from src.requests.Courses import get_courses
from src.requests.enrollments import get_enrollments, enrol_user


# ─────────────────────────────────────────────────────────────────────────────
# VIEW
# ─────────────────────────────────────────────────────────────────────────────
async def course_details_view(page: ft.Page, course_id: str, course_name: str):

    # ── content socket ────────────────────────────────────────────────────────
    content_socket = ft.Container(
        expand=True,
        padding=ft.padding.only(top=24),
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            controls=[
                ft.ProgressRing(color=ft.Colors.PRIMARY, width=36, height=36),
                ft.Text("Loading course details…", size=13, color=ft.Colors.GREY_500),
            ],
        ),
    )

    # ── app bar ───────────────────────────────────────────────────────────────
    app_bar = ft.AppBar(
        bgcolor=ft.Colors.PRIMARY,
        title=ft.Text(
            course_name,
            color=ft.Colors.WHITE,
            weight=ft.FontWeight.W_700,
            size=17,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        ),
        leading=ft.IconButton(
            icon=ft.Icons.ARROW_BACK_ROUNDED,
            icon_color=ft.Colors.WHITE,
            on_click=lambda _: page.go("/courses"),
        ),
        elevation=0,
    )

    # ── dialogs ───────────────────────────────────────────────────────────────
    enroll_success_dialog = ft.AlertDialog(
        title=ft.Row(
            spacing=8,
            controls=[
                ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED,
                        color=ft.Colors.PRIMARY, size=22),
                ft.Text("Enrolled!", size=18, weight=ft.FontWeight.W_600),
            ],
        ),
        content=ft.Text("You have successfully joined this course.", size=13),
        actions=[
            ft.TextButton(
                "Go to My Courses",
                on_click=lambda e: page.go("/courses"),
                style=ft.ButtonStyle(color=ft.Colors.PRIMARY),
            )
        ],
    )

    # ── enrol handler (defined early so load_course_info can close over it) ──
    async def handle_enrol_click(e, is_enrolling: bool):
        if e.control.disabled:
            return

        token = await page.shared_preferences.get("auth_token")
        e.control.disabled = True
        e.control.content = ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            tight=True,
            spacing=6,
            controls=[
                ft.ProgressRing(width=14, height=14,
                                color=ft.Colors.WHITE, stroke_width=2),
                ft.Text("Please wait…", color=ft.Colors.WHITE,
                        size=13, weight=ft.FontWeight.W_600),
            ],
        )
        page.update()

        try:
            status, data = await asyncio.wait_for(
                enrol_user(token, course_id, None), timeout=15
            )
            if status == 200:
                page.show_dialog(enroll_success_dialog)
            else:
                e.control.disabled = False
                e.control.content = ft.Text(
                    "Unenroll" if is_enrolling else "Enroll Now",
                    color=ft.Colors.WHITE,
                    size=14,
                    weight=ft.FontWeight.W_600,
                )
                page.update()

        except asyncio.TimeoutError:
            e.control.disabled = False
            e.control.content = ft.Text(
                "Timed out — tap to retry",
                color=ft.Colors.WHITE, size=13,
            )
            page.update()

        except Exception:
            e.control.disabled = False
            e.control.content = ft.Text(
                "Error — tap to retry",
                color=ft.Colors.WHITE, size=13,
            )
            page.update()

    # ─────────────────────────────────────────────────────────────────────────
    # DATA LOADER
    # ─────────────────────────────────────────────────────────────────────────
    async def load_course_info(cid: str):
        token = await page.shared_preferences.get("auth_token")

        try:
            course_list, enrolled_list = await asyncio.gather(
                asyncio.wait_for(get_courses(token, params={"id": cid}), timeout=15),
                asyncio.wait_for(get_enrollments(token, None),           timeout=15),
                return_exceptions=True,
            )

            # ── handle individual failures ─────────────────────────────────
            if isinstance(course_list, Exception) or not course_list:
                _show_error("Course not found or failed to load.")
                return

            if isinstance(enrolled_list, Exception):
                enrolled_list = []  # non-fatal — degrade gracefully

            # ── parse data ────────────────────────────────────────────────
            course_data = course_list[0]
            name        = course_data.get("name", "Untitled Course")
            image_url   = course_data.get("image_url")
            description = course_data.get("description", "No description provided.")
            objectives  = course_data.get("objectives", [])
            category    = (course_data.get("category") or {}).get("name", "Uncategorised")
            admin       = course_data.get("admin") or {}
            author      = f'{admin.get("first_name","Unknown")} {admin.get("last_name","Instructor")}'.strip()
            enrolled_count = len(course_data.get("Students", []))
            is_public   = course_data.get("public", False)
            is_supervised = course_data.get("supervised", False)

            enrolled_ids       = [c.get("id") for c in (enrolled_list or [])]
            is_already_enrolled = cid in enrolled_ids

            # ── update appbar title ───────────────────────────────────────
            view.appbar.title = ft.Text(
                name, color=ft.Colors.WHITE,
                weight=ft.FontWeight.W_700, size=17,
                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
            )

            # ── helpers ───────────────────────────────────────────────────
            def pill(label, bg, fg):
                return ft.Container(
                    padding=ft.padding.symmetric(horizontal=9, vertical=3),
                    bgcolor=bg, border_radius=10,
                    content=ft.Text(label, size=10, color=fg,
                                    weight=ft.FontWeight.W_600),
                )

            def section_label(text: str) -> ft.Text:
                return ft.Text(text, size=11, weight=ft.FontWeight.W_600,
                               color=ft.Colors.GREY_500)

            def info_row(icon, label, value):
                return ft.Row(
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            width=34, height=34,
                            border_radius=8,
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(icon, size=16,
                                            color=ft.Colors.PRIMARY),
                        ),
                        ft.Column(
                            spacing=1,
                            controls=[
                                ft.Text(label, size=10, color=ft.Colors.GREY_400,
                                        weight=ft.FontWeight.W_500),
                                ft.Text(value, size=13, color=ft.Colors.ON_SURFACE,
                                        weight=ft.FontWeight.W_600),
                            ],
                        ),
                    ],
                )

            def bullet_item(text: str):
                return ft.Row(
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                    controls=[
                        ft.Container(
                            width=6, height=6,
                            margin=ft.margin.only(top=6),
                            bgcolor=ft.Colors.PRIMARY,
                            border_radius=3,
                        ),
                        ft.Text(text, size=13, color=ft.Colors.ON_SURFACE,
                                expand=True),
                    ],
                )

            # ── cover image / placeholder ─────────────────────────────────
            cover = ft.Container(
                width=float("inf"),
                height=210,
                border_radius=ft.BorderRadius.only(
                    bottom_left=20, bottom_right=20
                ),
                bgcolor=ft.Colors.INDIGO_300,
            gradient=ft.LinearGradient(
                        begin=ft.Alignment.TOP_LEFT,
                        end=ft.Alignment.BOTTOM_RIGHT,
                        colors=[ft.Colors.PURPLE_200, ft.Colors.INDIGO_200]
                    ),

                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                content=(
                    ft.Image(
                        src=image_url,
                        fit=ft.BoxFit.COVER,
                        width=float("inf"),
                        fade_in_animation=ft.Animation(600, ft.AnimationCurve.EASE_IN_OUT),
                    )
                    if image_url
                    else ft.Container(
            bgcolor=ft.Colors.INDIGO_300,
            gradient=ft.LinearGradient(
                        begin=ft.Alignment.TOP_LEFT,
                        end=ft.Alignment.BOTTOM_RIGHT,
                        colors=[ft.Colors.PURPLE_200, ft.Colors.INDIGO_200]
                    ),
            border_radius=ft.BorderRadius.only(top_left=12, top_right=12),
            alignment=ft.Alignment.CENTER,
            content=ft.Icon(ft.Icons.MENU_BOOK_ROUNDED, size=44,
                            color=ft.Colors.WHITE),
        )
                ),
            )

            # ── status badges ─────────────────────────────────────────────
            badges = ft.Row(
                spacing=8,
                controls=[
                    pill(
                        "Public" if is_public else "Draft",
                        ft.Colors.GREEN_50 if is_public else ft.Colors.GREY_100,
                        ft.Colors.GREEN_700 if is_public else ft.Colors.GREY_600,
                    ),
                    pill(
                        "Instructor-Led" if is_supervised else "Self-Paced",
                        ft.Colors.BLUE_50 if is_supervised else ft.Colors.PURPLE_50,
                        ft.Colors.BLUE_700 if is_supervised else ft.Colors.PURPLE_700,
                    ),
                ],
            )

            # ── meta info row ─────────────────────────────────────────────
            meta_row = ft.Row(
                spacing=16,
                wrap=True,
                controls=[
                    info_row(ft.Icons.PERSON_OUTLINE_ROUNDED,  "Instructor", author),
                    info_row(ft.Icons.CATEGORY_OUTLINED,       "Category",   category),
                    info_row(ft.Icons.GROUPS_ROUNDED,           "Enrolled",   str(enrolled_count)),
                ],
            )

            # ── objectives ────────────────────────────────────────────────
            obj_controls = (
                [bullet_item(o) for o in objectives]
                if objectives
                else [bullet_item(f"Gain knowledge in {name}")]
            )

            # ── enrol button ──────────────────────────────────────────────
            enrol_btn = ft.ElevatedButton(
                content=ft.Text(
                    "Unenroll" if is_already_enrolled else "Enroll Now",
                    color=ft.Colors.WHITE,
                    size=14,
                    weight=ft.FontWeight.W_600,
                ),
                bgcolor=(
                    ft.Colors.RED_600
                    if is_already_enrolled
                    else ft.Colors.PRIMARY
                ),
                expand=True,
                height=48,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=12),
                    elevation=0,
                ),
                on_click=lambda e: page.run_task(
                    handle_enrol_click, e, is_already_enrolled
                ),
            )

            # ── card wrapper ──────────────────────────────────────────────
            def card(content):
                return ft.Container(
                    bgcolor=ft.Colors.SURFACE,
                    border_radius=14,
                    border=ft.border.all(1, ft.Colors.GREY_200),
                    padding=ft.padding.symmetric(horizontal=18, vertical=16),
                    shadow=ft.BoxShadow(
                        blur_radius=6,
                        color=ft.Colors.with_opacity(0.05, ft.Colors.BLACK),
                        offset=ft.Offset(0, 2),
                    ),
                    content=content,
                )

            # ── full layout ───────────────────────────────────────────────
            real_content = ft.Column(
                spacing=0,
                controls=[
                    # Cover
                    cover,

                    ft.Container(
                        padding=ft.padding.symmetric(horizontal=16, vertical=16),
                        content=ft.Column(
                            spacing=16,
                            controls=[
                                # Title + badges
                                ft.Column(
                                    spacing=8,
                                    controls=[
                                        ft.Text(
                                            name,
                                            size=20,
                                            weight=ft.FontWeight.W_700,
                                            color=ft.Colors.ON_SURFACE,
                                        ),
                                        badges,
                                    ],
                                ),

                                # Meta info card
                                card(
                                    ft.Column(
                                        spacing=12,
                                        controls=[
                                            section_label("COURSE INFO"),
                                            meta_row,
                                        ],
                                    )
                                ),

                                # Description card
                                card(
                                    ft.Column(
                                        spacing=10,
                                        controls=[
                                            section_label("ABOUT THIS COURSE"),
                                            ft.Text(
                                                description,
                                                size=13,
                                                color=ft.Colors.GREY_700,
                                                selectable=True,
                                            ),
                                        ],
                                    )
                                ),

                                # Objectives card
                                card(
                                    ft.Column(
                                        spacing=10,
                                        controls=[
                                            section_label("WHAT YOU WILL LEARN"),
                                            ft.Column(
                                                spacing=8,
                                                controls=obj_controls,
                                            ),
                                        ],
                                    )
                                ),

                                # Enrol row
                                ft.Container(
                                    padding=ft.padding.only(top=4, bottom=24),
                                    content=ft.Column(
                                        spacing=8,
                                        controls=[
                                            ft.Row(controls=[enrol_btn]),
                                             ft.Container(),
                                        ],
                                    ),
                                ),
                            ],
                        ),
                    ),
                ],
            )

            content_socket.alignment = None
            content_socket.padding   = 0
            content_socket.content   = real_content
            page.update()

        except asyncio.TimeoutError:
            _show_error(
                "Connection timed out.",
                icon=ft.Icons.WIFI_OFF_ROUNDED,
                color=ft.Colors.ORANGE_400,
            )

        except Exception as ex:
            _show_error(
                f"Something went wrong ({type(ex).__name__}).",
                icon=ft.Icons.ERROR_OUTLINE_ROUNDED,
                color=ft.Colors.RED_400,
            )

    # ── error helper ──────────────────────────────────────────────────────────
    def _show_error(message: str,
                    icon=ft.Icons.ERROR_OUTLINE_ROUNDED,
                    color=ft.Colors.RED_400):
        content_socket.alignment = ft.Alignment.CENTER
        content_socket.content = ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            controls=[
                ft.Icon(icon, size=48, color=color),
                ft.Text("Couldn't load course", size=16,
                        weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                ft.Text(message, size=13, color=ft.Colors.GREY_500,
                        text_align=ft.TextAlign.CENTER),
                ft.Container(height=4),
                ft.ElevatedButton(
                    "Retry",
                    bgcolor=ft.Colors.PRIMARY,
                    color=ft.Colors.WHITE,
                    height=42,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=10),
                        elevation=0,
                    ),
                    on_click=lambda _: page.run_task(load_course_info, course_id),
                ),
            ],
        )
        page.update()

    # ── trigger ───────────────────────────────────────────────────────────────
    page.run_task(load_course_info, course_id)

    # ── view ──────────────────────────────────────────────────────────────────
    view = ft.View(
        route=f"/courses/{course_id}",
        padding=0,
        bgcolor=ft.Colors.GREY_50,
        appbar=app_bar,
        scroll=ft.ScrollMode.AUTO,
        controls=[content_socket],
    )
    return view