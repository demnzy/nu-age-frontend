import asyncio
import base64
import flet as ft
from src.requests.Courses import create_course, get_categories
from src.components.course_creation_studio import open_course_creation_studio
from src.components.standard_create_modal import open_standard_create_modal
from src.utils.file_opener import show_page_snackbar


def build_org_courses_tab(
    page: ft.Page,
    org_id: str,
    courses: list,
    members: list,
    categories_cache: list,
    theme_color: str,
    token: str,
    on_course_created=None,
) -> ft.Column:
    """
    Renders the Course Catalog tab for organization administrators.
    Provides responsive filtering, live search, curriculum navigation,
    and a robust modal for authoring new courses.
    """
    search_query = ""
    filter_status = "all"  # all, public, campus, draft
    filter_category = "all"
    filter_instructor = "all"

    content_holder = ft.AnimatedSwitcher(
        content=ft.Column(spacing=12),
        transition=ft.AnimatedSwitcherTransition.FADE,
        duration=180,
        reverse_duration=140,
        switch_in_curve=ft.AnimationCurve.EASE_OUT,
        switch_out_curve=ft.AnimationCurve.EASE_IN,
    )

    def _get_filtered():
        res = list(courses)
        if search_query.strip():
            q = search_query.strip().lower()
            res = [c for c in res if q in str(c.get("name", "")).lower() or q in str(c.get("description", "")).lower()]

        if filter_status == "public":
            res = [c for c in res if str(c.get("public", "")).lower() == "true"]
        elif filter_status == "campus":
            res = [c for c in res if str(c.get("public", "")).lower() in ("organisation", "organization", "campus")]
        elif filter_status == "draft":
            res = [c for c in res if str(c.get("public", "")).lower() not in ("true", "organisation", "organization", "campus")]

        if filter_category != "all":
            res = [
                c for c in res
                if (isinstance(c.get("category"), dict) and c.get("category", {}).get("name") == filter_category)
                or (isinstance(c.get("category"), str) and c.get("category") == filter_category)
                or (str(c.get("category_id")) == filter_category)
            ]

        if filter_instructor != "all":
            def _match_inst(c):
                t_id = str(c.get("teacher_id", ""))
                for m in members:
                    m_id = str(m.get("id", ""))
                    m_name = f"{m.get('first_name', '')} {m.get('last_name', '')}".strip() or m.get("email", "")
                    if (m_id == t_id or m_id == str(c.get("admin_id", ""))) and m_name == filter_instructor:
                        return True
                t_info = c.get("teacher")
                if isinstance(t_info, dict):
                    t_name = f"{t_info.get('first_name', '')} {t_info.get('last_name', '')}".strip() or t_info.get("email", "")
                    if t_name == filter_instructor:
                        return True
                return False

            res = [c for c in res if _match_inst(c)]
        return res

    def _reset_filters(e=None):
        nonlocal search_query, filter_status, filter_category, filter_instructor
        search_query = ""
        filter_status = "all"
        filter_category = "all"
        filter_instructor = "all"
        search_box.value = ""
        _rebuild_cards()
        page.update()

    def _build_course_card(c: dict) -> ft.Container:
        cid = str(c.get("id", ""))
        title = c.get("name", "Untitled Course")
        desc = c.get("description", "No description provided.")
        img = c.get("image_url")
        pub_val = str(c.get("public", "false")).lower()
        students_cnt = c.get("total_students", 0)

        if pub_val == "true":
            badge_bg = ft.Colors.with_opacity(0.12, ft.Colors.GREEN_600)
            badge_color = ft.Colors.GREEN_600
            badge_text = "PUBLIC"
        elif pub_val in ("organisation", "organization", "campus"):
            badge_bg = ft.Colors.with_opacity(0.12, ft.Colors.BLUE_600)
            badge_color = ft.Colors.BLUE_600
            badge_text = "CAMPUS"
        else:
            badge_bg = ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE_VARIANT)
            badge_color = ft.Colors.ON_SURFACE_VARIANT
            badge_text = "DRAFT"

        status_badge = ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=3.5),
            border_radius=8,
            bgcolor=badge_bg,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.2, badge_color)),
            content=ft.Text(badge_text, size=9.5, weight=ft.FontWeight.BOLD, color=badge_color),
        )

        card = ft.Container(
            col={"xs": 12, "sm": 6, "lg": 4},
            bgcolor=ft.Colors.SURFACE,
            border_radius=16,
            animate=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
            animate_scale=ft.Animation(180, ft.AnimationCurve.EASE_OUT_BACK),
            scale=1.0,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            shadow=ft.BoxShadow(
                blur_radius=10,
                color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                offset=ft.Offset(0, 3),
            ),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=ft.Column(
                spacing=0,
                controls=[
                    ft.Stack(
                        controls=[
                            ft.Container(
                                height=130,
                                width=float("inf"),
                                bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                                content=ft.Image(
                                    src=img or "https://nu-age-cdn.b-cdn.net/logos/placeholder%202.png",
                                    fit=ft.BoxFit.COVER,
                                ),
                            ),
                            ft.Container(top=10, left=10, content=status_badge),
                        ]
                    ),
                    ft.Container(
                        padding=14,
                        content=ft.Column(
                            spacing=6,
                            controls=[
                                ft.Text(
                                    title,
                                    size=14.5,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.ON_SURFACE,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(
                                    desc,
                                    size=11.5,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                    max_lines=2,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Container(height=4),
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.Row(
                                            spacing=4,
                                            tight=True,
                                            controls=[
                                                ft.Icon(ft.Icons.PEOPLE_OUTLINE_ROUNDED, size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                                                ft.Text(f"{students_cnt} Enrolled", size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500),
                                            ],
                                        ),
                                        ft.Row(
                                            spacing=0,
                                            tight=True,
                                            controls=[
                                                ft.IconButton(
                                                    ft.Icons.EDIT_ROUNDED,
                                                    tooltip="Manage Curriculum",
                                                    icon_size=17,
                                                    icon_color=theme_color,
                                                    on_click=lambda _, cid=cid: page.go(f"/courses/{cid}/manage"),
                                                ),
                                                ft.IconButton(
                                                    ft.Icons.BAR_CHART_ROUNDED,
                                                    tooltip="Course Analytics",
                                                    icon_size=17,
                                                    icon_color=ft.Colors.ON_SURFACE_VARIANT,
                                                    on_click=lambda _, cid=cid: page.go(f"/organisations/{org_id}/courses/{cid}/analytics"),
                                                ),
                                                ft.IconButton(
                                                    ft.Icons.SETTINGS_OUTLINED,
                                                    tooltip="Course Settings",
                                                    icon_size=17,
                                                    icon_color=ft.Colors.ON_SURFACE_VARIANT,
                                                    on_click=lambda _, cid=cid: page.go(f"/organisations/{org_id}/courses/{cid}/settings"),
                                                ),
                                                ft.IconButton(
                                                    ft.Icons.VISIBILITY_OUTLINED,
                                                    tooltip="View Course",
                                                    icon_size=17,
                                                    icon_color=ft.Colors.ON_SURFACE_VARIANT,
                                                    on_click=lambda _, cid=cid: page.go(f"/courses/{cid}/view"),
                                                ),
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

        def _on_hover(e):
            card.scale = 1.015 if e.data == "true" else 1.0
            try:
                card.update()
            except Exception:
                pass

        card.on_hover = _on_hover
        return card

    def _rebuild_cards():
        filtered = _get_filtered()
        if filtered:
            cards = [_build_course_card(c) for c in filtered]
            content_holder.content = ft.ResponsiveRow(controls=cards, run_spacing=14, spacing=14)
        else:
            has_active_filter = (
                bool(search_query.strip())
                or filter_status != "all"
                or filter_category != "all"
                or filter_instructor != "all"
            )
            if has_active_filter:
                content_holder.content = ft.Container(
                    padding=ft.Padding.symmetric(vertical=48, horizontal=24),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=10,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.SEARCH_OFF_ROUNDED, size=46, color=ft.Colors.with_opacity(0.3, ft.Colors.ON_SURFACE)),
                            ft.Text(
                                "No courses match your filter criteria.",
                                size=14,
                                weight=ft.FontWeight.W_600,
                                color=ft.Colors.ON_SURFACE,
                            ),
                            ft.Text(
                                "Try adjusting your search query, status, or category.",
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Container(height=6),
                            ft.OutlinedButton(
                                "Reset Filters",
                                icon=ft.Icons.REFRESH_ROUNDED,
                                on_click=_reset_filters,
                                style=ft.ButtonStyle(
                                    shape=ft.RoundedRectangleBorder(radius=10),
                                    side=ft.BorderSide(1, ft.Colors.with_opacity(0.2, ft.Colors.ON_SURFACE)),
                                ),
                            ),
                        ],
                    ),
                )
            else:
                content_holder.content = ft.Container(
                    padding=ft.Padding.symmetric(vertical=48, horizontal=24),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=10,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.AUTO_STORIES_OUTLINED, size=46, color=ft.Colors.with_opacity(0.3, ft.Colors.ON_SURFACE)),
                            ft.Text(
                                "No courses in academy library yet.",
                                size=14,
                                weight=ft.FontWeight.W_600,
                                color=ft.Colors.ON_SURFACE,
                            ),
                            ft.Text(
                                "Create your first course to share knowledge with your students.",
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Container(height=6),
                            ft.FilledButton(
                                "Create Course",
                                icon=ft.Icons.ADD_ROUNDED,
                                style=ft.ButtonStyle(
                                    bgcolor=theme_color,
                                    shape=ft.RoundedRectangleBorder(radius=10),
                                ),
                                on_click=lambda _: open_studio_modal(),
                            ),
                        ],
                    ),
                )

    def _on_search(e):
        nonlocal search_query
        search_query = e.control.value or ""
        _rebuild_cards()
        page.update()

    search_box = ft.TextField(
        hint_text="Search courses by title or description…",
        prefix_icon=ft.Icons.SEARCH_ROUNDED,
        border_radius=10,
        dense=True,
        content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        on_change=_on_search,
        border_color=ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE),
        focused_border_color=theme_color,
        expand=True,
    )

    def _set_status(status_key: str):
        nonlocal filter_status
        filter_status = status_key
        _update_filter_bar()
        _rebuild_cards()
        page.update()

    def _filter_chip(label: str, key: str) -> ft.Container:
        is_active = (filter_status == key)
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            border_radius=18,
            bgcolor=theme_color if is_active else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
            ink=True,
            on_click=lambda _: _set_status(key),
            content=ft.Text(
                label,
                size=11,
                weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.NORMAL,
                color=ft.Colors.WHITE if is_active else ft.Colors.ON_SURFACE,
            ),
        )

    def _open_filter_bottom_sheet(title: str, options: list, active_val: str, on_select):
        sheet_container = ft.Column(tight=True, spacing=6)

        def _select(val):
            sheet.open = False
            page.update()
            on_select(val)

        sheet_container.controls.append(
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Text(title, size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.IconButton(
                        ft.Icons.CLOSE_ROUNDED,
                        icon_size=20,
                        on_click=lambda _: _select(active_val),
                    ),
                ],
            )
        )
        sheet_container.controls.append(ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)))

        all_item = ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
            border_radius=8,
            bgcolor=ft.Colors.with_opacity(0.08, theme_color) if active_val == "all" else ft.Colors.TRANSPARENT,
            ink=True,
            on_click=lambda _: _select("all"),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Text("All", size=13, weight=ft.FontWeight.W_600 if active_val == "all" else ft.FontWeight.NORMAL),
                    ft.Icon(ft.Icons.CHECK_ROUNDED, size=16, color=theme_color, visible=(active_val == "all")),
                ],
            ),
        )
        sheet_container.controls.append(all_item)

        for opt in options:
            is_sel = (opt == active_val)
            opt_container = ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.08, theme_color) if is_sel else ft.Colors.TRANSPARENT,
                ink=True,
                on_click=lambda _, v=opt: _select(v),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text(opt, size=13, weight=ft.FontWeight.W_600 if is_sel else ft.FontWeight.NORMAL),
                        ft.Icon(ft.Icons.CHECK_ROUNDED, size=16, color=theme_color, visible=is_sel),
                    ],
                ),
            )
            sheet_container.controls.append(opt_container)

        sheet = ft.BottomSheet(
            bgcolor=ft.Colors.SURFACE,
            content=ft.Container(
                padding=16,
                border_radius=ft.BorderRadius.only(top_left=16, top_right=16),
                content=ft.Column(
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                    controls=[sheet_container],
                ),
            ),
        )
        page.overlay.append(sheet)
        sheet.open = True
        page.update()

    def _open_category_filter(e=None):
        cats = []
        seen = set()
        for cat in categories_cache:
            if isinstance(cat, dict) and cat.get("name") and cat["name"] not in seen:
                seen.add(cat["name"])
                cats.append(cat["name"])
        for c in courses:
            cat_info = c.get("category")
            c_name = cat_info.get("name") if isinstance(cat_info, dict) else (cat_info if isinstance(cat_info, str) else None)
            if c_name and c_name not in seen:
                seen.add(c_name)
                cats.append(c_name)
        cats.sort()

        def _on_cat_sel(v):
            nonlocal filter_category
            filter_category = v
            _update_filter_bar()
            _rebuild_cards()
            page.update()

        _open_filter_bottom_sheet("Filter by Category", cats, filter_category, _on_cat_sel)

    def _open_instructor_filter(e=None):
        insts = []
        seen = set()
        for m in members:
            role = str(m.get("role", "")).upper()
            if role in ("TEACHER", "STAFF", "ADMIN", "OWNER", "INSTRUCTOR"):
                name = f"{m.get('first_name', '')} {m.get('last_name', '')}".strip() or m.get("email", "")
                if name and name not in seen:
                    seen.add(name)
                    insts.append(name)
        for c in courses:
            t_info = c.get("teacher")
            if isinstance(t_info, dict):
                t_name = f"{t_info.get('first_name', '')} {t_info.get('last_name', '')}".strip() or t_info.get("email", "")
                if t_name and t_name not in seen:
                    seen.add(t_name)
                    insts.append(t_name)
        insts.sort()

        def _on_inst_sel(v):
            nonlocal filter_instructor
            filter_instructor = v
            _update_filter_bar()
            _rebuild_cards()
            page.update()

        _open_filter_bottom_sheet("Filter by Instructor", insts, filter_instructor, _on_inst_sel)

    def _drawer_chip(label_text: str, on_click, is_active: bool) -> ft.Container:
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            border_radius=18,
            bgcolor=theme_color if is_active else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
            ink=True,
            on_click=on_click,
            content=ft.Row(
                spacing=2,
                tight=True,
                controls=[
                    ft.Text(
                        label_text,
                        size=11,
                        weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.NORMAL,
                        color=ft.Colors.WHITE if is_active else ft.Colors.ON_SURFACE,
                    ),
                    ft.Icon(
                        ft.Icons.ARROW_DROP_DOWN_ROUNDED,
                        size=16,
                        color=ft.Colors.WHITE if is_active else ft.Colors.ON_SURFACE,
                    ),
                ],
            ),
        )

    filter_row = ft.Row(spacing=8, scroll=ft.ScrollMode.AUTO)

    def _update_filter_bar():
        cat_label = f"Category: {filter_category}" if filter_category != "all" else "Category"
        inst_label = f"Instructor: {filter_instructor}" if filter_instructor != "all" else "Instructor"
        filter_row.controls = [
            _filter_chip("All", "all"),
            _filter_chip("Public", "public"),
            _filter_chip("Campus", "campus"),
            _filter_chip("Drafts", "draft"),
            _drawer_chip(cat_label, _open_category_filter, is_active=(filter_category != "all")),
            _drawer_chip(inst_label, _open_instructor_filter, is_active=(filter_instructor != "all")),
        ]

    # DUAL PATH COURSE CREATION MODALS
    def _on_created_sync(new_c):
        courses_list.insert(0, new_c)
        _rebuild_cards()
        if on_course_created:
            on_course_created(new_c)

    def open_standard_modal(e=None):
        open_standard_create_modal(
            page,
            org_id=org_id,
            on_course_created=_on_created_sync,
        )

    def open_studio_modal(e=None):
        open_course_creation_studio(
            page,
            org_id=org_id,
            on_course_created=_on_created_sync,
        )

    # Initial setup
    _update_filter_bar()
    _rebuild_cards()

    # Header Row with section title & "New Course" CTA
    header_row = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Column(
                spacing=1,
                expand=True,
                controls=[
                    ft.Text(
                        "Courses & Curricula",
                        size=16,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.ON_SURFACE,
                        no_wrap=True,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Text(
                        f"{len(courses)} published courses in academy library",
                        size=11,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        no_wrap=True,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                ],
            ),
            ft.Row([
                ft.OutlinedButton(
                    "Standard Create",
                    icon=ft.Icons.ADD_ROUNDED,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=10),
                        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                    ),
                    on_click=lambda _: open_standard_modal(),
                ),
                ft.FilledButton(
                    content=ft.Row([
                        ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=15, color=ft.Colors.WHITE),
                        ft.Text("AI Parallel Studio", size=12.5, color=ft.Colors.WHITE, weight=ft.FontWeight.W_700),
                    ], tight=True, spacing=5),
                    style=ft.ButtonStyle(
                        bgcolor=theme_color,
                        shape=ft.RoundedRectangleBorder(radius=10),
                        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                    ),
                    on_click=lambda _: open_studio_modal(),
                ),
            ], spacing=6, tight=True),
        ],
    )

    return ft.Column(
        spacing=14,
        controls=[
            header_row,
            search_box,
            filter_row,
            content_holder,
        ],
    )

