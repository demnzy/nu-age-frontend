import asyncio
import flet as ft
from src.requests.organisations import get_organisation_courses

DEFAULT_ORG_ID = "00000000-0000-0000-0000-000000000000"


def build_teacher_portal(
    page: ft.Page,
    user_data: dict,
    memberships: list,
    token: str,
    on_back_to_admin=None,
) -> ft.Column:
    """
    Renders the dedicated Faculty Portal for instructors.
    Allows teachers to navigate their assigned organizations, inspect org curricula,
    manage freelance courses, and switch to their admin dashboard if applicable.
    """
    first_name = user_data.get("first_name", "Instructor")
    last_name = user_data.get("last_name", "")
    initials = f"{first_name[0]}{last_name[0]}".upper() if last_name else first_name[:2].upper()
    org_count = len(memberships)

    org_courses_cache: dict[str, list] = {}
    freelance_courses: list[dict] = []
    freelance_loaded = False

    orgs_socket = ft.Column(expand=True, spacing=0)
    freelance_socket = ft.Column(expand=True, spacing=12)

    def _role_badge(role_label: str) -> ft.Container:
        r = role_label.upper()
        if r in ("ADMIN", "OWNER"):
            bg = ft.Colors.with_opacity(0.12, ft.Colors.BLUE_600)
            fg = ft.Colors.BLUE_600
        elif r in ("TEACHER", "INSTRUCTOR"):
            bg = ft.Colors.with_opacity(0.12, ft.Colors.AMBER_600)
            fg = ft.Colors.AMBER_700
        elif r == "LEAD TUTOR":
            bg = ft.Colors.with_opacity(0.12, ft.Colors.PURPLE_600)
            fg = ft.Colors.PURPLE_600
        elif r == "GUEST INSTRUCTOR":
            bg = ft.Colors.with_opacity(0.12, ft.Colors.TEAL_600)
            fg = ft.Colors.TEAL_600
        else:
            bg = ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE_VARIANT)
            fg = ft.Colors.ON_SURFACE_VARIANT

        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=2.5),
            border_radius=8,
            bgcolor=bg,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.2, fg)),
            content=ft.Text(role_label, size=9.5, weight=ft.FontWeight.BOLD, color=fg),
        )

    def _status_badge(public_val: str) -> ft.Container:
        pv = str(public_val).lower()
        if pv == "true":
            bg = ft.Colors.with_opacity(0.12, ft.Colors.GREEN_600)
            fg = ft.Colors.GREEN_600
            lbl = "Published"
        elif pv in ("organisation", "organization", "campus"):
            bg = ft.Colors.with_opacity(0.12, ft.Colors.BLUE_600)
            fg = ft.Colors.BLUE_600
            lbl = "Campus"
        else:
            bg = ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE_VARIANT)
            fg = ft.Colors.ON_SURFACE_VARIANT
            lbl = "Draft"

        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=2.5),
            border_radius=8,
            bgcolor=bg,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.2, fg)),
            content=ft.Text(lbl, size=9.5, weight=ft.FontWeight.BOLD, color=fg),
        )

    # ── Teacher Org Course Card ──────────────────────────────────────────────
    def _org_course_card(course: dict, org_theme: str) -> ft.Container:
        cid = str(course.get("id", ""))
        title = course.get("name", "Untitled Course")
        desc = course.get("description", "Curriculum details configured inside studio.")
        enrolled = course.get("total_students", 0)
        pub_val = course.get("public", "false")

        return ft.Container(
            bgcolor=ft.Colors.SURFACE,
            border_radius=12,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            shadow=ft.BoxShadow(
                blur_radius=6,
                color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                offset=ft.Offset(0, 2),
            ),
            margin=ft.Margin.only(bottom=8),
            ink=True,
            on_click=lambda _: page.go(f"/courses/{cid}/manage"),
            content=ft.Row(
                spacing=0,
                controls=[
                    ft.Container(
                        width=4,
                        bgcolor=org_theme,
                        border_radius=ft.BorderRadius.only(top_left=12, bottom_left=12),
                    ),
                    ft.Container(
                        expand=True,
                        padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                        content=ft.Column(
                            spacing=6,
                            controls=[
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Text(
                                            title,
                                            size=14,
                                            weight=ft.FontWeight.W_600,
                                            color=ft.Colors.ON_SURFACE,
                                            expand=True,
                                            max_lines=1,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                        ),
                                        _status_badge(pub_val),
                                    ],
                                ),
                                ft.Text(
                                    desc,
                                    size=11.5,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                    max_lines=2,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Row(
                                    spacing=4,
                                    tight=True,
                                    controls=[
                                        ft.Icon(ft.Icons.PEOPLE_ALT_ROUNDED, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                                        ft.Text(f"{enrolled} student{'s' if enrolled != 1 else ''} enrolled", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ],
                                ),
                            ],
                        ),
                    ),
                ],
            ),
        )

    # ── Org Detail Subview ───────────────────────────────────────────────────
    async def _show_org_detail(org: dict):
        org_id = str(org.get("id", ""))
        org_name = org.get("name", "Organisation")
        org_theme = org.get("theme_color") or ft.Colors.PRIMARY
        teacher_role = org.get("role", "Instructor")

        if org_id not in org_courses_cache:
            try:
                c_list = await asyncio.wait_for(
                    get_organisation_courses(token, org_id), timeout=15
                )
                if isinstance(c_list, list):
                    org_courses_cache[org_id] = [c for c in c_list if isinstance(c, dict)]
                else:
                    org_courses_cache[org_id] = []
            except Exception as ex:
                print(f"[teacher_portal] fetch courses error: {ex}")
                org_courses_cache[org_id] = []

        courses = org_courses_cache[org_id]

        course_list_control = (
            ft.Column(
                spacing=8,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
                controls=[_org_course_card(c, org_theme) for c in courses],
            )
            if courses
            else ft.Container(
                alignment=ft.Alignment.CENTER,
                padding=30,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.AUTO_STORIES_OUTLINED, size=40, color=ft.Colors.with_opacity(0.3, ft.Colors.ON_SURFACE)),
                        ft.Text("No courses yet in this organisation.", size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.FilledButton(
                            "Create First Course",
                            icon=ft.Icons.ADD_ROUNDED,
                            style=ft.ButtonStyle(bgcolor=org_theme, shape=ft.RoundedRectangleBorder(radius=8)),
                            on_click=lambda _: page.go(f"/organisations/{org_id}/courses"),
                        ),
                    ],
                ),
            )
        )

        orgs_socket.controls = [
            ft.Column(
                expand=True,
                spacing=0,
                controls=[
                    # Header bar for selected org
                    ft.Container(
                        bgcolor=org_theme,
                        padding=ft.Padding.only(left=8, right=16, top=10, bottom=16),
                        border_radius=ft.BorderRadius.only(bottom_left=16, bottom_right=16),
                        content=ft.Row(
                            spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.IconButton(
                                    ft.Icons.ARROW_BACK_ROUNDED,
                                    icon_color=ft.Colors.WHITE,
                                    icon_size=22,
                                    on_click=lambda _: _restore_org_list(),
                                ),
                                ft.Column(
                                    spacing=2,
                                    expand=True,
                                    controls=[
                                        ft.Text(
                                            org_name,
                                            size=17,
                                            weight=ft.FontWeight.BOLD,
                                            color=ft.Colors.WHITE,
                                            no_wrap=True,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                        ),
                                        _role_badge(teacher_role),
                                    ],
                                ),
                            ],
                        ),
                    ),
                    # Section content
                    ft.Container(
                        expand=True,
                        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                        content=ft.Column(
                            expand=True,
                            spacing=12,
                            controls=[
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Text("Courses & Modules", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                                        ft.FilledButton(
                                            "Create Course",
                                            icon=ft.Icons.ADD_ROUNDED,
                                            style=ft.ButtonStyle(
                                                bgcolor=org_theme,
                                                shape=ft.RoundedRectangleBorder(radius=8),
                                                padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                                            ),
                                            on_click=lambda _: page.go(f"/organisations/{org_id}/courses"),
                                        ),
                                    ],
                                ),
                                ft.Divider(height=1, color=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
                                course_list_control,
                            ],
                        ),
                    ),
                ],
            )
        ]
        page.update()

    def _restore_org_list():
        orgs_socket.controls = [_build_org_list_view()]
        page.update()

    def _org_card(org: dict) -> ft.Container:
        theme = org.get("theme_color") or ft.Colors.PRIMARY
        teacher_role = org.get("role", "Instructor")
        students = org.get("students", 0)
        courses = org.get("courses", 0)
        logo_url = org.get("logo")
        name = org.get("name", "Organisation")

        avatar = (
            ft.CircleAvatar(
                radius=21,
                bgcolor=ft.Colors.with_opacity(0.10, theme),
                background_image_src=logo_url,
            )
            if logo_url
            else ft.Container(
                width=42,
                height=42,
                bgcolor=ft.Colors.with_opacity(0.12, theme),
                border_radius=12,
                alignment=ft.Alignment.CENTER,
                content=ft.Text(name[:2].upper(), size=15, weight=ft.FontWeight.BOLD, color=theme),
            )
        )

        return ft.Container(
            bgcolor=ft.Colors.SURFACE,
            border_radius=14,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            shadow=ft.BoxShadow(
                blur_radius=8,
                color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                offset=ft.Offset(0, 2),
            ),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            ink=True,
            on_click=lambda _, o=org: page.run_task(_show_org_detail, o),
            content=ft.Column(
                spacing=0,
                controls=[
                    ft.Container(height=4, bgcolor=theme),
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=16, vertical=14),
                        content=ft.Column(
                            spacing=10,
                            controls=[
                                ft.Row(
                                    spacing=12,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        avatar,
                                        ft.Column(
                                            spacing=2,
                                            expand=True,
                                            controls=[
                                                ft.Text(
                                                    name,
                                                    size=14.5,
                                                    weight=ft.FontWeight.BOLD,
                                                    color=ft.Colors.ON_SURFACE,
                                                    max_lines=1,
                                                    overflow=ft.TextOverflow.ELLIPSIS,
                                                ),
                                                _role_badge(teacher_role),
                                            ],
                                        ),
                                        ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, color=ft.Colors.ON_SURFACE_VARIANT, size=20),
                                    ],
                                ),
                                ft.Divider(height=1, color=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
                                ft.Row(
                                    spacing=20,
                                    controls=[
                                        ft.Row(
                                            spacing=4,
                                            tight=True,
                                            controls=[
                                                ft.Icon(ft.Icons.AUTO_STORIES_ROUNDED, size=14, color=theme),
                                                ft.Text(f"{courses} Courses", size=11.5, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500),
                                            ],
                                        ),
                                        ft.Row(
                                            spacing=4,
                                            tight=True,
                                            controls=[
                                                ft.Icon(ft.Icons.PEOPLE_ALT_ROUNDED, size=14, color=ft.Colors.BLUE_500),
                                                ft.Text(f"{students} Students", size=11.5, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500),
                                            ],
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ),
                ],
            ),
        )

    def _build_org_list_view():
        if not memberships:
            return ft.Container(
                alignment=ft.Alignment.CENTER,
                padding=40,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=10,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.BUSINESS_OUTLINED, size=46, color=ft.Colors.with_opacity(0.3, ft.Colors.ON_SURFACE)),
                        ft.Text("No faculty memberships yet", size=15, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                        ft.Text(
                            "When an academy adds you as an instructor, it will appear here.",
                            size=12,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                ),
            )

        return ft.ListView(
            expand=True,
            spacing=10,
            padding=ft.Padding.symmetric(horizontal=16, vertical=16),
            controls=[_org_card(org) for org in memberships],
        )

    # ── Freelance Tab ────────────────────────────────────────────────────────
    def _freelance_card(c: dict) -> ft.Container:
        cid = str(c.get("id", ""))
        title = c.get("name", "Untitled Course")
        enrolled = c.get("total_students", 0)
        pub_val = c.get("public", "false")

        return ft.Container(
            bgcolor=ft.Colors.SURFACE,
            border_radius=12,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            padding=ft.Padding.symmetric(horizontal=14, vertical=12),
            margin=ft.Margin.only(bottom=8),
            ink=True,
            on_click=lambda _: page.go(f"/courses/{cid}/manage"),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Column(
                        spacing=2,
                        expand=True,
                        controls=[
                            ft.Text(title, size=13.5, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                            ft.Text(f"{enrolled} student{'s' if enrolled != 1 else ''}", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                    ),
                    ft.Row(
                        spacing=8,
                        tight=True,
                        controls=[
                            _status_badge(pub_val),
                            ft.IconButton(
                                ft.Icons.BAR_CHART_ROUNDED,
                                icon_size=16,
                                icon_color=ft.Colors.ON_SURFACE_VARIANT,
                                tooltip="Analytics",
                                on_click=lambda _, cid=cid: page.go(f"/organisations/{DEFAULT_ORG_ID}/courses/{cid}/analytics"),
                            ),
                        ],
                    ),
                ],
            ),
        )

    def _render_freelance_content():
        if freelance_courses:
            cards = [_freelance_card(c) for c in freelance_courses]
            content = ft.Column(spacing=0, controls=cards)
        else:
            content = ft.Container(
                alignment=ft.Alignment.CENTER,
                padding=36,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.MIC_EXTERNAL_ON_ROUNDED, size=44, color=ft.Colors.PRIMARY),
                        ft.Text("No freelance courses yet", size=15, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                        ft.Text(
                            "Publish courses independently without an organization requirement.",
                            size=12,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Container(height=6),
                        ft.FilledButton(
                            "Create Free Course",
                            icon=ft.Icons.ADD_ROUNDED,
                            style=ft.ButtonStyle(
                                bgcolor=ft.Colors.PRIMARY,
                                shape=ft.RoundedRectangleBorder(radius=10),
                            ),
                            on_click=lambda _: page.go("/create-course"),
                        ),
                    ],
                ),
            )

        freelance_socket.controls = [
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Column(
                        spacing=2,
                        controls=[
                            ft.Text("Freelance Courses", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                            ft.Text("Courses you own outside of any academy", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                    ),
                    ft.FilledButton(
                        "New Course",
                        icon=ft.Icons.ADD_ROUNDED,
                        style=ft.ButtonStyle(
                            bgcolor=ft.Colors.PRIMARY,
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                        ),
                        on_click=lambda _: page.go("/create-course"),
                    ),
                ],
            ),
            ft.Divider(height=1, color=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
            content,
        ]

    async def _fetch_freelance_courses():
        nonlocal freelance_courses, freelance_loaded
        if not freelance_loaded:
            try:
                fl = await asyncio.wait_for(
                    get_organisation_courses(token, DEFAULT_ORG_ID, is_freelance=True),
                    timeout=15,
                )
                if isinstance(fl, list):
                    freelance_courses = [c for c in fl if isinstance(c, dict)]
                else:
                    freelance_courses = []
                freelance_loaded = True
                _render_freelance_content()
                page.update()
            except Exception as ex:
                print(f"[teacher_portal] fetch freelance courses error: {ex}")

    # Seed orgs
    orgs_socket.controls = [_build_org_list_view()]
    _render_freelance_content()
    page.run_task(_fetch_freelance_courses)

    # ── Top Identity Card ────────────────────────────────────────────────────
    right_controls = []
    if on_back_to_admin:
        right_controls.append(
            ft.OutlinedButton(
                "Admin Hub",
                icon=ft.Icons.ADMIN_PANEL_SETTINGS_ROUNDED,
                style=ft.ButtonStyle(
                    color=ft.Colors.WHITE,
                    side=ft.BorderSide(1, ft.Colors.with_opacity(0.4, ft.Colors.WHITE)),
                    shape=ft.RoundedRectangleBorder(radius=18),
                    padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                ),
                on_click=lambda _: on_back_to_admin(),
            )
        )

    right_controls.append(
        ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=4),
            bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.WHITE),
            border_radius=16,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.WHITE)),
            content=ft.Row(
                tight=True,
                spacing=4,
                controls=[
                    ft.Icon(ft.Icons.BUSINESS_ROUNDED, size=12, color=ft.Colors.WHITE),
                    ft.Text(f"{org_count} Org{'s' if org_count != 1 else ''}", size=11, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE),
                ],
            ),
        )
    )

    identity_card = ft.Container(
        gradient=ft.LinearGradient(
            begin=ft.Alignment(-1, -1),
            end=ft.Alignment(1, 1),
            colors=[ft.Colors.PRIMARY, ft.Colors.with_opacity(0.78, ft.Colors.PRIMARY)],
        ),
        padding=ft.Padding.symmetric(horizontal=16, vertical=16),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            width=44,
                            height=44,
                            border_radius=22,
                            bgcolor=ft.Colors.with_opacity(0.2, ft.Colors.WHITE),
                            border=ft.Border.all(2, ft.Colors.with_opacity(0.5, ft.Colors.WHITE)),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Text(initials, size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ),
                        ft.Column(
                            spacing=1,
                            controls=[
                                ft.Text(f"Hey, {first_name}!", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                ft.Text("Faculty Workspace", size=11, color=ft.Colors.with_opacity(0.8, ft.Colors.WHITE)),
                            ],
                        ),
                    ],
                ),
                ft.Row(spacing=6, tight=True, controls=right_controls),
            ],
        ),
    )

    # ── Tabs View ────────────────────────────────────────────────────────────
    return ft.Column(
        expand=True,
        spacing=0,
        controls=[
            identity_card,
            ft.Tabs(
                length=2,
                expand=True,
                selected_index=0,
                content=ft.Column(
                    expand=True,
                    controls=[
                        ft.TabBar(
                            tab_alignment=ft.TabAlignment.START,
                            indicator_color=ft.Colors.PRIMARY,
                            indicator_size=2,
                            label_color=ft.Colors.PRIMARY,
                            label_text_style=ft.TextStyle(size=12, weight=ft.FontWeight.W_600),
                            unselected_label_color=ft.Colors.ON_SURFACE_VARIANT,
                            unselected_label_text_style=ft.TextStyle(size=12),
                            divider_color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                            tabs=[
                                ft.Tab(label="My Academies", icon=ft.Icons.BUSINESS_ROUNDED),
                                ft.Tab(label="Freelance Studio", icon=ft.Icons.MIC_EXTERNAL_ON_ROUNDED),
                            ],
                        ),
                        ft.TabBarView(
                            expand=True,
                            controls=[
                                orgs_socket,
                                ft.Container(
                                    expand=True,
                                    padding=ft.Padding.symmetric(horizontal=16, vertical=14),
                                    content=freelance_socket,
                                ),
                            ],
                        ),
                    ],
                ),
            ),
        ],
    )
