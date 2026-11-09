import asyncio
from typing import Any, Callable, Dict, List, Optional
import flet as ft

from src.requests.organisations import get_organisation_courses
from src.requests.course_spaces import get_my_spaces, get_organisation_spaces
from src.components.standard_create_modal import open_standard_create_modal
from src.utils.file_opener import show_page_snackbar, safe_set_clipboard


def build_teacher_portal(
    page: ft.Page,
    user_data: dict,
    memberships: list,
    token: str,
    on_back_to_admin: Optional[Callable] = None,
    initial_spaces: Optional[list] = None,
) -> ft.Column:
    """
    Renders the modernized Faculty Command Center for educators & instructors.
    Provides:
    - Executive Faculty Identity Header with role badging & Admin Hub switcher.
    - 4-Card Instructor Command Bento Grid (Students Reached, Curriculum Health, Spaces, AI Studio CTA).
    - Fluid Segmented Tabs:
      1. My Academies: Drill down into assigned organizations, search courses, view stats,
         manage curriculum, and launch Course Creation Studio directly (no dead routes).
      2. My Course Spaces: Monitor active cohort spaces, view members, jump into Space Hub.
      3. Freelance Studio: Manage independent courses, create new content, and review analytics.
    """
    first_name = user_data.get("first_name", "Instructor")
    last_name = user_data.get("last_name", "")
    full_name = f"{first_name} {last_name}".strip() or "Faculty Instructor"
    initials = f"{first_name[0]}{last_name[0]}".upper() if (first_name and last_name) else (first_name[:2].upper() if first_name else "ED")
    user_role = str(user_data.get("role", "TEACHER")).upper()

    # Dynamic In-Memory Caches & State
    state = {
        "active_tab": "academies",  # "academies", "spaces", "freelance"
        "selected_org": None,       # When viewing a specific academy
        "org_courses": {},          # {org_id: [course_dict, ...]}
        "org_spaces": {},           # {org_id: [space_dict, ...]}
        "freelance_courses": [],
        "freelance_loaded": False,
        "my_spaces": list(initial_spaces or []),
        "my_spaces_loaded": bool(initial_spaces),
        "search_query": "",
        "filter_status": "all",     # "all", "published", "campus", "draft"
        "is_refreshing": False,
    }

    # ── Master Content Sockets ───────────────────────────────────────────────
    tab_content_switcher = ft.AnimatedSwitcher(
        content=ft.Container(expand=True),
        transition=ft.AnimatedSwitcherTransition.FADE,
        duration=180,
        reverse_duration=140,
        switch_in_curve=ft.AnimationCurve.EASE_OUT,
        switch_out_curve=ft.AnimationCurve.EASE_IN,
        expand=True,
    )
    bento_holder = ft.Container()
    tab_bar_holder = ft.Container()

    # ── Role & Status Badges ─────────────────────────────────────────────────
    def _role_badge(role_label: str) -> ft.Container:
        r = str(role_label or "Instructor").upper()
        if r in ("ADMIN", "OWNER"):
            fg = ft.Colors.PRIMARY
        elif r in ("TEACHER", "INSTRUCTOR", "LEAD TUTOR", "FACULTY"):
            fg = ft.Colors.GREEN_700
        else:
            fg = ft.Colors.ON_SURFACE_VARIANT

        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
            border_radius=ft.BorderRadius.all(6),
            bgcolor=ft.Colors.with_opacity(0.12, fg),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.25, fg)),
            content=ft.Text(role_label, size=9.5, weight=ft.FontWeight.W_800, color=fg),
        )

    def _status_badge(public_val: Any) -> ft.Container:
        pv = str(public_val or "").lower()
        if pv == "true":
            fg = ft.Colors.GREEN_700
            lbl = "Public"
        elif pv in ("organisation", "organization", "campus"):
            fg = ft.Colors.PRIMARY
            lbl = "Campus"
        else:
            fg = ft.Colors.ON_SURFACE_VARIANT
            lbl = "Draft"

        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=7, vertical=2.5),
            border_radius=ft.BorderRadius.all(6),
            bgcolor=ft.Colors.with_opacity(0.10, fg),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.20, fg)),
            content=ft.Text(lbl, size=9, weight=ft.FontWeight.W_800, color=fg),
        )

    # ── 1. KPI Calculation & Bento Grid ──────────────────────────────────────
    def _render_bento():
        # Compute aggregate metrics
        all_courses = []
        for c_list in state["org_courses"].values():
            all_courses.extend(c_list)
        all_courses.extend(state["freelance_courses"])

        # De-duplicate by id
        seen_c = set()
        dedup_courses = []
        for c in all_courses:
            cid = str(c.get("id", ""))
            if cid and cid not in seen_c:
                seen_c.add(cid)
                dedup_courses.append(c)

        total_students = sum(int(c.get("total_students") or 0) for c in dedup_courses)
        for s in state["my_spaces"]:
            total_students += int(s.get("members_count") or s.get("student_count") or 0)

        pub_courses = sum(1 for c in dedup_courses if str(c.get("public", "")).lower() == "true")
        campus_courses = sum(1 for c in dedup_courses if str(c.get("public", "")).lower() in ("organisation", "organization", "campus"))
        draft_courses = len(dedup_courses) - pub_courses - campus_courses

        total_spaces = len(state["my_spaces"])

        def _bento_card(
            icon: str,
            title: str,
            main_val: str,
            sub_val: str,
            accent_color: str,
            on_click_fn: Optional[Callable] = None,
        ) -> ft.Container:
            return ft.Container(
                col={"xs": 6, "sm": 6, "md": 3},
                bgcolor=ft.Colors.SURFACE,
                border_radius=ft.BorderRadius.all(12),
                padding=ft.Padding.all(12),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                ink=bool(on_click_fn),
                on_click=on_click_fn,
                content=ft.Column(
                    spacing=3,
                    tight=True,
                    controls=[
                        ft.Row(
                            spacing=6,
                            tight=True,
                            controls=[
                                ft.Container(
                                    padding=ft.Padding.all(5),
                                    border_radius=ft.BorderRadius.all(6),
                                    bgcolor=ft.Colors.with_opacity(0.12, accent_color),
                                    content=ft.Icon(icon, size=14, color=accent_color),
                                ),
                                ft.Text(
                                    title,
                                    size=9,
                                    weight=ft.FontWeight.W_800,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                            ],
                        ),
                        ft.Container(height=1),
                        ft.Text(
                            main_val,
                            size=18,
                            weight=ft.FontWeight.W_900,
                            color=ft.Colors.ON_SURFACE,
                        ),
                        ft.Text(
                            sub_val,
                            size=10,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                ),
            )

        bento_holder.content = ft.ResponsiveRow(
            spacing=8,
            run_spacing=8,
            controls=[
                _bento_card(
                    ft.Icons.PEOPLE_ALT_ROUNDED,
                    "LEARNERS TAUGHT",
                    f"{total_students:,}",
                    "Enrolled across courses & spaces",
                    ft.Colors.PRIMARY,
                ),
                _bento_card(
                    ft.Icons.AUTO_STORIES_ROUNDED,
                    "CURRICULUM CATALOG",
                    str(len(dedup_courses)),
                    f"{pub_courses} Public • {campus_courses} Campus • {draft_courses} Draft",
                    ft.Colors.GREEN_700,
                    on_click_fn=lambda _: _switch_tab("academies"),
                ),
                _bento_card(
                    ft.Icons.GROUPS_ROUNDED,
                    "COURSE SPACES",
                    str(total_spaces),
                    "Active cohort & discussion spaces",
                    ft.Colors.INDIGO_500,
                    on_click_fn=lambda _: _switch_tab("spaces"),
                ),
                _bento_card(
                    ft.Icons.AUTO_AWESOME_ROUNDED,
                    "COURSE BUILDER",
                    "New Course",
                    "Create course & open curriculum",
                    ft.Colors.PRIMARY,
                    on_click_fn=lambda _: open_standard_create_modal(page, org_id=None, on_course_created=_on_any_course_created),
                ),
            ],
        )

    # ── 2. Tab Navigation Switcher ───────────────────────────────────────────
    def _switch_tab(tab_key: str):
        state["active_tab"] = tab_key
        state["search_query"] = ""
        state["filter_status"] = "all"
        _render_tabs_bar()
        _render_active_tab_view()
        page.update()

    def _render_tabs_bar():
        academies_cnt = len(memberships)
        spaces_cnt = len(state["my_spaces"])
        freelance_cnt = len(state["freelance_courses"])

        def _tab_btn(label: str, key: str, icon_name: str, count: int):
            is_sel = (state["active_tab"] == key)
            return ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=7),
                border_radius=ft.BorderRadius.all(8),
                bgcolor=ft.Colors.PRIMARY if is_sel else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                ink=True,
                on_click=lambda _: _switch_tab(key),
                content=ft.Row(
                    spacing=5,
                    tight=True,
                    controls=[
                        ft.Icon(icon_name, size=13, color=ft.Colors.ON_PRIMARY if is_sel else ft.Colors.ON_SURFACE),
                        ft.Text(
                            f"{label} ({count})",
                            size=11,
                            weight=ft.FontWeight.W_800 if is_sel else ft.FontWeight.W_600,
                            color=ft.Colors.ON_PRIMARY if is_sel else ft.Colors.ON_SURFACE,
                        ),
                    ],
                ),
            )

        tab_bar_holder.content = ft.Row(
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                _tab_btn("My Academies", "academies", ft.Icons.BUSINESS_ROUNDED, academies_cnt),
                _tab_btn("Course Spaces", "spaces", ft.Icons.GROUPS_ROUNDED, spaces_cnt),
                _tab_btn("Freelance Studio", "freelance", ft.Icons.MIC_EXTERNAL_ON_ROUNDED, freelance_cnt),
            ],
        )

    # ── 3. Tab Views ─────────────────────────────────────────────────────────

    # ── Tab 1: Academies & Drill-Down Cockpit ─────────────────────────────────
    def _render_academies_tab():
        if state["selected_org"]:
            return _build_academy_cockpit(state["selected_org"])

        if not memberships:
            return ft.Container(
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding.all(36),
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=10,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.BUSINESS_OUTLINED, size=42, color=ft.Colors.with_opacity(0.25, ft.Colors.ON_SURFACE)),
                        ft.Text("No Faculty Memberships Yet", size=15, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                        ft.Text(
                            "When an academy adds you as an instructor or mentor, it will appear here.",
                            size=12,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                ),
            )

        cards = []
        for org in memberships:
            org_id = str(org.get("id", ""))
            name = org.get("name", "Organisation")
            theme = org.get("theme_color") or ft.Colors.PRIMARY
            teacher_role = org.get("role", "Instructor")
            logo_url = org.get("logo")
            st_cnt = org.get("students", 0)
            c_cnt = org.get("courses", 0)

            avatar = (
                ft.CircleAvatar(radius=20, background_image_src=logo_url)
                if logo_url
                else ft.Container(
                    width=40,
                    height=40,
                    border_radius=ft.BorderRadius.all(10),
                    bgcolor=ft.Colors.with_opacity(0.12, theme),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text(name[:2].upper(), size=14, weight=ft.FontWeight.W_800, color=theme),
                )
            )

            cards.append(
                ft.Container(
                    bgcolor=ft.Colors.SURFACE,
                    border_radius=ft.BorderRadius.all(14),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    padding=ft.Padding.all(14),
                    margin=ft.Margin.only(bottom=8),
                    ink=True,
                    on_click=(lambda o=org: lambda _: _drill_into_org(o))(),
                    content=ft.Column(
                        spacing=10,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Row(
                                        spacing=12,
                                        expand=True,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                        controls=[
                                            avatar,
                                            ft.Column(
                                                spacing=2,
                                                expand=True,
                                                controls=[
                                                    ft.Text(
                                                        name,
                                                        size=14,
                                                        weight=ft.FontWeight.W_800,
                                                        color=ft.Colors.ON_SURFACE,
                                                        max_lines=1,
                                                        overflow=ft.TextOverflow.ELLIPSIS,
                                                    ),
                                                    ft.Row(
                                                        spacing=6,
                                                        tight=True,
                                                        controls=[
                                                            _role_badge(teacher_role),
                                                            ft.Text(f"ID: {org_id[:8]}…", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                                                        ],
                                                    ),
                                                ],
                                            ),
                                        ],
                                    ),
                                    ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, size=20, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                            ),
                            ft.Divider(height=1, color=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
                            ft.Row(
                                spacing=18,
                                controls=[
                                    ft.Row(
                                        spacing=5,
                                        tight=True,
                                        controls=[
                                            ft.Icon(ft.Icons.AUTO_STORIES_ROUNDED, size=13, color=ft.Colors.PRIMARY),
                                            ft.Text(f"{c_cnt} Courses", size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_600),
                                        ],
                                    ),
                                    ft.Row(
                                        spacing=5,
                                        tight=True,
                                        controls=[
                                            ft.Icon(ft.Icons.PEOPLE_ALT_ROUNDED, size=13, color=ft.Colors.GREEN_700),
                                            ft.Text(f"{st_cnt} Learners", size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_600),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                )
            )

        return ft.Column(
            spacing=4,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            controls=cards,
        )

    def _drill_into_org(org: dict):
        state["selected_org"] = org
        state["search_query"] = ""
        state["filter_status"] = "all"
        _render_active_tab_view()
        page.update()
        page.run_task(_fetch_org_curricula, org)

    def _build_academy_cockpit(org: dict) -> ft.Column:
        org_id = str(org.get("id", ""))
        org_name = org.get("name", "Organisation")
        org_theme = org.get("theme_color") or ft.Colors.PRIMARY
        teacher_role = org.get("role", "Instructor")

        courses = state["org_courses"].get(org_id, [])

        # Filter courses
        filtered = list(courses)
        if state["search_query"].strip():
            sq = state["search_query"].strip().lower()
            filtered = [c for c in filtered if sq in str(c.get("name", "")).lower() or sq in str(c.get("description", "")).lower()]

        if state["filter_status"] == "published":
            filtered = [c for c in filtered if str(c.get("public", "")).lower() == "true"]
        elif state["filter_status"] == "campus":
            filtered = [c for c in filtered if str(c.get("public", "")).lower() in ("organisation", "organization", "campus")]
        elif state["filter_status"] == "draft":
            filtered = [c for c in filtered if str(c.get("public", "")).lower() not in ("true", "organisation", "organization", "campus")]

        # Header bar
        header_bar = ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
            border_radius=ft.BorderRadius.all(12),
            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        spacing=6,
                        tight=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.IconButton(
                                icon=ft.Icons.ARROW_BACK_ROUNDED,
                                icon_size=18,
                                tooltip="Back to Academies",
                                on_click=lambda _: _exit_org_cockpit(),
                            ),
                            ft.Column(
                                spacing=1,
                                tight=True,
                                controls=[
                                    ft.Text(org_name, size=14, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                    ft.Row(
                                        spacing=6,
                                        tight=True,
                                        controls=[
                                            _role_badge(teacher_role),
                                            ft.Text(f"{len(courses)} Curricula", size=10.5, color=ft.Colors.ON_SURFACE_VARIANT),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                    ft.Button(
                        "Create Course",
                        icon=ft.Icons.ADD_ROUNDED,
                        bgcolor=ft.Colors.PRIMARY,
                        color=ft.Colors.ON_PRIMARY,
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                        ),
                        on_click=lambda _: open_standard_create_modal(
                            page,
                            org_id=org_id,
                            on_course_created=lambda new_c: _on_org_course_created(org_id, new_c),
                        ),
                    ),
                ],
            ),
        )

        # Search & Filter bar
        search_field = ft.TextField(
            hint_text="Search courses & descriptions…",
            value=state["search_query"],
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            dense=True,
            expand=True,
            text_size=12,
            border_radius=ft.BorderRadius.all(8),
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            on_change=lambda e: _on_search_change(e.control.value),
        )

        filter_chips = ft.Row(
            spacing=6,
            tight=True,
            controls=[
                _status_filter_chip("All", "all"),
                _status_filter_chip("Published", "published"),
                _status_filter_chip("Campus", "campus"),
                _status_filter_chip("Draft", "draft"),
            ],
        )

        # Course items
        if filtered:
            course_items = [_course_card(c, org_id) for c in filtered]
            course_container = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True, controls=course_items)
        else:
            course_container = ft.Container(
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding.all(32),
                expand=True,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.SEARCH_OFF_ROUNDED if state["search_query"] else ft.Icons.AUTO_STORIES_OUTLINED, size=36, color=ft.Colors.with_opacity(0.25, ft.Colors.ON_SURFACE)),
                        ft.Text(
                            "No courses match your filter" if state["search_query"] else "No courses in this academy yet",
                            size=13,
                            weight=ft.FontWeight.W_700,
                            color=ft.Colors.ON_SURFACE,
                        ),
                        ft.Button(
                            "Author First Course",
                            icon=ft.Icons.ADD_ROUNDED,
                            bgcolor=ft.Colors.PRIMARY,
                            color=ft.Colors.ON_PRIMARY,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                            on_click=lambda _: open_standard_create_modal(
                                page,
                                org_id=org_id,
                                on_course_created=lambda new_c: _on_org_course_created(org_id, new_c),
                            ),
                        ),
                    ],
                ),
            )

        return ft.Column(
            spacing=8,
            expand=True,
            controls=[
                header_bar,
                ft.Row(spacing=8, controls=[search_field]),
                filter_chips,
                course_container,
            ],
        )

    def _exit_org_cockpit():
        state["selected_org"] = None
        state["search_query"] = ""
        state["filter_status"] = "all"
        _render_active_tab_view()
        page.update()

    # ── Tab 2: My Course Spaces (The Teaching Cohorts) ───────────────────────
    def _render_spaces_tab() -> ft.Column:
        spaces = state["my_spaces"]

        if not spaces:
            return ft.Container(
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding.all(36),
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=10,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.GROUPS_ROUNDED, size=42, color=ft.Colors.with_opacity(0.25, ft.Colors.ON_SURFACE)),
                        ft.Text("No Assigned Course Spaces", size=15, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                        ft.Text(
                            "Course Spaces allow you to interact with cohorts, host live lectures, and manage study discussions.",
                            size=12,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                ),
            )

        cards = []
        for sp in spaces:
            sp_id = str(sp.get("id", ""))
            sp_name = sp.get("name") or sp.get("title") or "Course Space"
            sp_code = sp.get("code", "")
            members_cnt = sp.get("members_count") or sp.get("student_count") or 0
            courses_linked = len(sp.get("course_ids") or [])

            cards.append(
                ft.Container(
                    bgcolor=ft.Colors.SURFACE,
                    border_radius=ft.BorderRadius.all(12),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    padding=ft.Padding.all(12),
                    margin=ft.Margin.only(bottom=6),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(
                                spacing=10,
                                expand=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Container(
                                        width=36,
                                        height=36,
                                        border_radius=ft.BorderRadius.all(8),
                                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.INDIGO_500),
                                        alignment=ft.Alignment.CENTER,
                                        content=ft.Icon(ft.Icons.GROUPS_ROUNDED, size=18, color=ft.Colors.INDIGO_500),
                                    ),
                                    ft.Column(
                                        spacing=2,
                                        expand=True,
                                        controls=[
                                            ft.Text(
                                                sp_name,
                                                size=13.5,
                                                weight=ft.FontWeight.W_800,
                                                color=ft.Colors.ON_SURFACE,
                                                max_lines=1,
                                                overflow=ft.TextOverflow.ELLIPSIS,
                                            ),
                                            ft.Row(
                                                spacing=8,
                                                tight=True,
                                                controls=[
                                                    ft.Text(f"{members_cnt} learners", size=10.5, color=ft.Colors.ON_SURFACE_VARIANT),
                                                    ft.Text("•", size=10.5, color=ft.Colors.ON_SURFACE_VARIANT),
                                                    ft.Text(f"{courses_linked} linked courses", size=10.5, color=ft.Colors.ON_SURFACE_VARIANT),
                                                    (
                                                        ft.Container(
                                                            padding=ft.Padding.symmetric(horizontal=6, vertical=1),
                                                            border_radius=ft.BorderRadius.all(4),
                                                            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                                                            content=ft.Text(f"#{sp_code}", size=9, weight=ft.FontWeight.W_700),
                                                        )
                                                        if sp_code
                                                        else ft.Container()
                                                    ),
                                                ],
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            ft.Row(
                                spacing=6,
                                tight=True,
                                controls=[
                                    ft.OutlinedButton(
                                        "Manage",
                                        icon=ft.Icons.SETTINGS_ROUNDED,
                                        style=ft.ButtonStyle(
                                            shape=ft.RoundedRectangleBorder(radius=8),
                                            padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                                        ),
                                        on_click=(lambda sid=sp_id: lambda _: page.navigate(f"/spaces/{sid}/manage"))(),
                                    ),
                                    ft.Button(
                                        "Open Space",
                                        icon=ft.Icons.CHAT_ROUNDED,
                                        bgcolor=ft.Colors.PRIMARY,
                                        color=ft.Colors.ON_PRIMARY,
                                        style=ft.ButtonStyle(
                                            shape=ft.RoundedRectangleBorder(radius=8),
                                            padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                                        ),
                                        on_click=(lambda sid=sp_id: lambda _: page.navigate(f"/spaces/{sid}/hub"))(),
                                    ),
                                ],
                            ),
                        ],
                    ),
                )
            )

        return ft.Column(
            spacing=6,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            controls=cards,
        )

    # ── Tab 3: Freelance Studio ──────────────────────────────────────────────
    def _render_freelance_tab() -> ft.Column:
        courses = state["freelance_courses"]

        filtered = list(courses)
        if state["search_query"].strip():
            sq = state["search_query"].strip().lower()
            filtered = [c for c in filtered if sq in str(c.get("name", "")).lower() or sq in str(c.get("description", "")).lower()]

        if state["filter_status"] == "published":
            filtered = [c for c in filtered if str(c.get("public", "")).lower() == "true"]
        elif state["filter_status"] == "campus":
            filtered = [c for c in filtered if str(c.get("public", "")).lower() in ("organisation", "organization", "campus")]
        elif state["filter_status"] == "draft":
            filtered = [c for c in filtered if str(c.get("public", "")).lower() not in ("true", "organisation", "organization", "campus")]

        top_actions = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Column(
                    spacing=1,
                    tight=True,
                    controls=[
                        ft.Text("Independent Authoring Studio", size=13.5, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                        ft.Text("Courses you own and distribute independently outside an academy", size=10.5, color=ft.Colors.ON_SURFACE_VARIANT),
                    ],
                ),
                ft.Button(
                    "New Course",
                    icon=ft.Icons.ADD_ROUNDED,
                    bgcolor=ft.Colors.PRIMARY,
                    color=ft.Colors.ON_PRIMARY,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8),
                        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                    ),
                    on_click=lambda _: open_standard_create_modal(
                        page,
                        org_id=None,
                        on_course_created=_on_freelance_created,
                    ),
                ),
            ],
        )

        search_field = ft.TextField(
            hint_text="Search freelance courses…",
            value=state["search_query"],
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            dense=True,
            expand=True,
            text_size=12,
            border_radius=ft.BorderRadius.all(8),
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            on_change=lambda e: _on_search_change(e.control.value),
        )

        filter_chips = ft.Row(
            spacing=6,
            tight=True,
            controls=[
                _status_filter_chip("All", "all"),
                _status_filter_chip("Published", "published"),
                _status_filter_chip("Draft", "draft"),
            ],
        )

        if filtered:
            course_items = [_course_card(c, is_freelance=True) for c in filtered]
            course_container = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True, controls=course_items)
        else:
            course_container = ft.Container(
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding.all(32),
                expand=True,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.MIC_EXTERNAL_ON_ROUNDED, size=40, color=ft.Colors.PRIMARY),
                        ft.Text("No Freelance Courses Yet", size=14, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                        ft.Text(
                            "Publish and sell your courses directly to learners worldwide without organizational requirements.",
                            size=12,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Button(
                            "Author Freelance Course",
                            icon=ft.Icons.ADD_ROUNDED,
                            bgcolor=ft.Colors.PRIMARY,
                            color=ft.Colors.ON_PRIMARY,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                            on_click=lambda _: open_standard_create_modal(
                                page,
                                org_id=None,
                                on_course_created=_on_freelance_created,
                            ),
                        ),
                    ],
                ),
            )

        return ft.Column(
            spacing=8,
            expand=True,
            controls=[
                top_actions,
                ft.Row(spacing=8, controls=[search_field]),
                filter_chips,
                course_container,
            ],
        )

    # ── Course Card Reusable Component ───────────────────────────────────────
    def _course_card(course: dict, org_id: Optional[str] = None, is_freelance: bool = False) -> ft.Container:
        cid = str(course.get("id", ""))
        name = course.get("name", "Untitled Course")
        desc = course.get("description", "Curriculum details configured inside studio.")
        enrolled = int(course.get("total_students") or 0)
        pub_val = course.get("public", "false")

        return ft.Container(
            bgcolor=ft.Colors.SURFACE,
            border_radius=ft.BorderRadius.all(12),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            padding=ft.Padding.all(12),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Column(
                        spacing=3,
                        expand=True,
                        controls=[
                            ft.Row(
                                spacing=8,
                                tight=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Text(
                                        name,
                                        size=13.5,
                                        weight=ft.FontWeight.W_800,
                                        color=ft.Colors.ON_SURFACE,
                                        max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                    _status_badge(pub_val),
                                ],
                            ),
                            ft.Text(
                                desc,
                                size=11,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            ft.Row(
                                spacing=12,
                                tight=True,
                                controls=[
                                    ft.Row(
                                        spacing=4,
                                        tight=True,
                                        controls=[
                                            ft.Icon(ft.Icons.PEOPLE_ALT_ROUNDED, size=11.5, color=ft.Colors.ON_SURFACE_VARIANT),
                                            ft.Text(f"{enrolled} student{'s' if enrolled != 1 else ''}", size=10.5, color=ft.Colors.ON_SURFACE_VARIANT),
                                        ],
                                    ),
                                    ft.Row(
                                        spacing=4,
                                        tight=True,
                                        controls=[
                                            ft.Icon(ft.Icons.FINGERPRINT_ROUNDED, size=11.5, color=ft.Colors.ON_SURFACE_VARIANT),
                                            ft.Text(f"ID: {cid[:8]}…", size=10.5, color=ft.Colors.ON_SURFACE_VARIANT),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                    ft.Row(
                        spacing=4,
                        tight=True,
                        controls=[
                            ft.IconButton(
                                icon=ft.Icons.BAR_CHART_ROUNDED,
                                icon_size=18,
                                tooltip="Performance & Analytics",
                                on_click=(lambda c_id=cid: lambda _: page.navigate(f"/courses/{c_id}/stats"))(),
                            ),
                            ft.OutlinedButton(
                                "Manage",
                                icon=ft.Icons.EDIT_NOTE_ROUNDED,
                                style=ft.ButtonStyle(
                                    shape=ft.RoundedRectangleBorder(radius=8),
                                    padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                                ),
                                on_click=(lambda c_id=cid: lambda _: page.navigate(f"/courses/{c_id}/manage"))(),
                            ),
                        ],
                    ),
                ],
            ),
        )

    # ── Filter Chip Helper ───────────────────────────────────────────────────
    def _status_filter_chip(label: str, key: str) -> ft.Container:
        is_sel = (state["filter_status"] == key)
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=4),
            border_radius=ft.BorderRadius.all(6),
            bgcolor=ft.Colors.PRIMARY if is_sel else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
            ink=True,
            on_click=(lambda k=key: lambda _: _set_filter_status(k))(),
            content=ft.Text(
                label,
                size=10.5,
                weight=ft.FontWeight.W_800 if is_sel else ft.FontWeight.W_600,
                color=ft.Colors.ON_PRIMARY if is_sel else ft.Colors.ON_SURFACE,
            ),
        )

    def _set_filter_status(status_key: str):
        state["filter_status"] = status_key
        _render_active_tab_view()
        page.update()

    def _on_search_change(val: str):
        state["search_query"] = val
        _render_active_tab_view()
        page.update()

    def _render_active_tab_view():
        if state["active_tab"] == "academies":
            tab_content_switcher.content = _render_academies_tab()
        elif state["active_tab"] == "spaces":
            tab_content_switcher.content = _render_spaces_tab()
        elif state["active_tab"] == "freelance":
            tab_content_switcher.content = _render_freelance_tab()

    # ── Background Data Fetchers ─────────────────────────────────────────────
    async def _fetch_org_curricula(org: dict):
        org_id = str(org.get("id", ""))
        if not org_id:
            return
        try:
            courses_res = await asyncio.wait_for(
                get_organisation_courses(token, org_id), timeout=15
            )
            if isinstance(courses_res, list):
                state["org_courses"][org_id] = [c for c in courses_res if isinstance(c, dict)]
            else:
                state["org_courses"][org_id] = []
            _render_bento()
            if state["selected_org"] and str(state["selected_org"].get("id")) == org_id:
                _render_active_tab_view()
            page.update()
        except Exception as ex:
            print(f"[teacher_portal] fetch org courses error: {ex}")

    async def _fetch_freelance_and_spaces():
        # 1. Fetch Freelance Courses
        try:
            fl_res = await asyncio.wait_for(
                get_organisation_courses(token, "default", is_freelance=True),
                timeout=12,
            )
            if isinstance(fl_res, list):
                state["freelance_courses"] = [c for c in fl_res if isinstance(c, dict)]
            else:
                state["freelance_courses"] = []
            state["freelance_loaded"] = True
        except Exception as ex:
            print(f"[teacher_portal] fetch freelance error: {ex}")

        # 2. Fetch Assigned Spaces
        try:
            sp_res = await asyncio.wait_for(
                get_my_spaces(token, scope="instructor"),
                timeout=12,
            )
            if isinstance(sp_res, dict):
                state["my_spaces"] = sp_res.get("spaces") or sp_res.get("items") or []
            elif isinstance(sp_res, list):
                state["my_spaces"] = sp_res
            state["my_spaces_loaded"] = True
        except Exception as ex:
            print(f"[teacher_portal] fetch instructor spaces error: {ex}")

        _render_bento()
        _render_tabs_bar()
        _render_active_tab_view()
        page.update()

    def _on_org_course_created(org_id: str, new_course: dict):
        if org_id not in state["org_courses"]:
            state["org_courses"][org_id] = []
        state["org_courses"][org_id].insert(0, new_course)
        _render_bento()
        _render_active_tab_view()
        page.update()
        show_page_snackbar(page, f"Course '{new_course.get('name', 'Course')}' created successfully!", ft.Colors.GREEN_700)

    def _on_freelance_created(new_course: dict):
        state["freelance_courses"].insert(0, new_course)
        _render_bento()
        _render_tabs_bar()
        _render_active_tab_view()
        page.update()
        show_page_snackbar(page, f"Freelance course '{new_course.get('name', 'Course')}' created!", ft.Colors.GREEN_700)

    def _on_any_course_created(new_course: dict):
        # Fallback callback for top bento CTA
        state["freelance_courses"].insert(0, new_course)
        _render_bento()
        _render_tabs_bar()
        _render_active_tab_view()
        page.update()

    async def _on_refresh_all(e=None):
        if state["is_refreshing"]:
            return
        state["is_refreshing"] = True
        show_page_snackbar(page, "Refreshing faculty command center…")
        await _fetch_freelance_and_spaces()
        for org in memberships:
            await _fetch_org_curricula(org)
        state["is_refreshing"] = False
        show_page_snackbar(page, "Faculty center updated!", ft.Colors.GREEN_700)

    # ── Executive Faculty Header ─────────────────────────────────────────────
    header_right = []
    if on_back_to_admin:
        header_right.append(
            ft.OutlinedButton(
                "Admin Hub",
                icon=ft.Icons.ADMIN_PANEL_SETTINGS_ROUNDED,
                style=ft.ButtonStyle(
                    side=ft.BorderSide(1, ft.Colors.with_opacity(0.3, ft.Colors.PRIMARY)),
                    shape=ft.RoundedRectangleBorder(radius=8),
                    padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                ),
                on_click=lambda _: on_back_to_admin(),
            )
        )

    header_right.append(
        ft.IconButton(
            icon=ft.Icons.REFRESH_ROUNDED,
            icon_size=18,
            tooltip="Refresh Faculty Center",
            on_click=lambda _: page.run_task(_on_refresh_all),
        )
    )

    faculty_header = ft.Container(
        bgcolor=ft.Colors.SURFACE,
        border_radius=ft.BorderRadius.all(14),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
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
                            border_radius=ft.BorderRadius.all(12),
                            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                            border=ft.Border.all(1.5, ft.Colors.with_opacity(0.25, ft.Colors.PRIMARY)),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Text(initials, size=15, weight=ft.FontWeight.W_900, color=ft.Colors.PRIMARY),
                        ),
                        ft.Column(
                            spacing=2,
                            tight=True,
                            controls=[
                                ft.Row(
                                    spacing=6,
                                    tight=True,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.Text(f"Welcome, {first_name}!", size=15, weight=ft.FontWeight.W_900, color=ft.Colors.ON_SURFACE),
                                        _role_badge(user_role),
                                    ],
                                ),
                                ft.Text(
                                    "Faculty Command Center & Course Studio",
                                    size=11,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                            ],
                        ),
                    ],
                ),
                ft.Row(spacing=6, tight=True, controls=header_right),
            ],
        ),
    )

    # ── Initial Render & Execution ───────────────────────────────────────────
    _render_bento()
    _render_tabs_bar()
    _render_active_tab_view()
    page.run_task(_fetch_freelance_and_spaces)
    for org in memberships:
        page.run_task(_fetch_org_curricula, org)

    return ft.Column(
        expand=True,
        spacing=10,
        controls=[
            faculty_header,
            bento_holder,
            tab_bar_holder,
            ft.Divider(height=1, color=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
            tab_content_switcher,
        ],
    )
