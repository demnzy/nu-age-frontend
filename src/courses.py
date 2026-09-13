import flet as ft
from src.components.completed_card import get_completed_card
from src.components.course_card import get_course_card
from src.components.playlist_card import get_playlist_card
from src.components.enrolled_card import get_enrolled_card
from src.components.org_course_card import get_org_course_card
from src.components.bottom_appbar import get_bottom_appbar
from src.requests.Courses import get_courses
from src.requests.enrollments import get_enrollments, enrol_user
from src.requests.playlists import get_all_playlists
from datetime import datetime

# Section keys/order for navigation
SECTION_ENROLLED = 0
SECTION_AVAILABLE = 1
SECTION_PLAYLISTS = 2
SECTION_COMPLETED = 3
SECTION_ORG = 4


def _is_mounted(control: ft.Control) -> bool:
    try:
        return control.page is not None
    except RuntimeError:
        return False


async def courses_view(page: ft.Page):
    course_cards = []
    enroll_cards = []
    completed_cards = []
    playlist_cards = []
    org_cards = []

    # ── Filter States ──────────────────────────────────────────────────────────
    all_available_courses = []
    current_search_query = ""
    current_category_filter = None
    current_instructor_filter = None
    current_org_filter = None

    async def handle_enrol_click(e, course_id: str):
        token = await page.shared_preferences.get("auth_token")
        if e.control.disabled:
            return

        e.control.disabled = True
        e.control.content = ft.ProgressRing(width=16, height=16, color=ft.Colors.ON_PRIMARY)
        is_enrolling = True
        page.update()

        try:
            if is_enrolling:
                status, data = await enrol_user(token, course_id, None)
            else:
                pass

            if status == 200:
                e.control.content = ft.Text("Fetching Course Contents...", color=ft.Colors.WHITE)
                page.update()
                page.go(f"/courses/{course_id}/view")
            else:
                e.control.disabled = False
                e.control.content = ft.Text("Enroll")
                page.update()
        except Exception:
            e.control.disabled = False
            e.control.content = ft.Text("Enroll")
            page.update()

    def build_course_card(course):
        course_name = course.get("name", "Untitled Course")
        image_url = course.get("image_url", None)
        course_id = course.get("id")
        first_name = course.get("admin", {}).get("first_name", "Unknown")
        last_name = course.get("admin", {}).get("last_name", "Instructor")
        full_name = f"{first_name} {last_name}".strip()
        category = course.get("category", {}).get("name")
        created_at = course.get("created_at", "")
        if created_at:
            try:
                created_at = datetime.fromisoformat(created_at).strftime("%d/%m/%Y")
            except Exception:
                pass
        card = get_course_card(
            course_title=course_name,
            course_category=category,
            course_author=full_name,
            image_url=image_url,
            created_at=created_at,
            on_view_click=lambda e, c_id=course_id: page.go(f"/courses/{c_id}"),
            course_dict=course,
            page=page,
        )
        card.col = {"xs": 12, "sm": 6}
        return card

    def filter_courses(e=None):
        nonlocal current_search_query
        if e and getattr(e.control, "value", None) is not None:
            current_search_query = e.control.value.lower()
        else:
            try:
                current_search_query = search_tf_input.value.lower() if search_tf_input.value else ""
            except NameError:
                current_search_query = ""

        course_cards.clear()
        for course in all_available_courses:
            # 1. Search Query
            c_name = course.get("name", "").lower()
            if current_search_query and current_search_query not in c_name:
                continue

            # 2. Category
            c_cat = course.get("category", {}).get("name")
            if current_category_filter and c_cat != current_category_filter:
                continue

            # 3. Instructor
            c_first = course.get("admin", {}).get("first_name", "")
            c_last = course.get("admin", {}).get("last_name", "")
            c_instructor = f"{c_first} {c_last}".strip()
            if current_instructor_filter and c_instructor != current_instructor_filter:
                continue

            # 4. Org
            c_org = course.get("organisation", {}).get("name")
            if current_org_filter and c_org != current_org_filter:
                continue

            course_cards.append(build_course_card(course))

        if course_cards:
            course_container.content.controls = course_cards
        else:
            course_container.content.controls = [
                ft.Container(
                    padding=40,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=12,
                        controls=[
                            ft.Icon(ft.Icons.SEARCH_OFF_ROUNDED, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(
                                "No courses found matching your filter.",
                                size=15,
                                color=ft.Colors.ON_SURFACE,
                                weight=ft.FontWeight.W_600,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Text(
                                "Try adjusting your search terms or clearing active filters.",
                                size=13,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.TextButton(
                                "Reset Filters",
                                icon=ft.Icons.REFRESH_ROUNDED,
                                on_click=lambda _: reset_all_filters(),
                            ),
                        ],
                    ),
                )
            ]
        page.update()

        async def animate_cards():
            import asyncio
            await asyncio.sleep(0.02)
            if course_cards:
                for card in course_cards:
                    card.opacity = 1
                    card.offset = ft.Offset(0, 0)
                page.update()

        page.run_task(animate_cards)

    def reset_all_filters():
        nonlocal current_category_filter, current_instructor_filter, current_org_filter, current_search_query
        current_category_filter = None
        current_instructor_filter = None
        current_org_filter = None
        current_search_query = ""
        search_tf_input.value = ""
        cat_chip.content.controls[0].value = "Category"
        cat_chip.bgcolor = ft.Colors.TRANSPARENT
        cat_chip.border = ft.Border.all(1, ft.Colors.with_opacity(0.14, ft.Colors.ON_SURFACE))
        inst_chip.content.controls[0].value = "Instructor"
        inst_chip.bgcolor = ft.Colors.TRANSPARENT
        inst_chip.border = ft.Border.all(1, ft.Colors.with_opacity(0.14, ft.Colors.ON_SURFACE))
        org_chip.content.controls[0].value = "Organisation"
        org_chip.bgcolor = ft.Colors.TRANSPARENT
        org_chip.border = ft.Border.all(1, ft.Colors.with_opacity(0.14, ft.Colors.ON_SURFACE))
        filter_courses()

    search_tf_input = ft.TextField(
        hint_text="Search courses, instructors, topics...",
        hint_style=ft.TextStyle(size=13, color=ft.Colors.ON_SURFACE_VARIANT),
        text_style=ft.TextStyle(size=13, color=ft.Colors.ON_SURFACE),
        border=ft.InputBorder.NONE,
        on_change=filter_courses,
        on_submit=filter_courses,
        expand=True,
        content_padding=ft.Padding.symmetric(vertical=6),
    )

    def on_clear_search(e):
        search_tf_input.value = ""
        filter_courses()

    search_tf = ft.Container(
        bgcolor=ft.Colors.TRANSPARENT,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.14, ft.Colors.ON_SURFACE)),
        border_radius=10,
        padding=ft.Padding(12, 2, 8, 2),
        expand=True,
        content=ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(ft.Icons.SEARCH_ROUNDED, color=ft.Colors.ON_SURFACE_VARIANT, size=18),
                search_tf_input,
                ft.IconButton(
                    icon=ft.Icons.CLEAR_ROUNDED,
                    on_click=on_clear_search,
                    icon_color=ft.Colors.ON_SURFACE_VARIANT,
                    icon_size=18,
                    tooltip="Clear search",
                ),
            ],
        ),
    )

    # Filter Bottom Sheets
    def build_filter_sheet(title, options, active_val, on_select):
        sheet = None

        def handle_select(e):
            on_select(e.control.value)
            if sheet:
                sheet.open = False
            page.update()
            filter_courses()

        def handle_reset(e):
            on_select(None)
            if sheet:
                sheet.open = False
            page.update()
            filter_courses()

        rg = ft.RadioGroup(
            value=active_val,
            on_change=handle_select,
            content=ft.Column(
                [ft.Radio(value=opt, label=opt) for opt in options],
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            ),
        )

        sheet = ft.BottomSheet(
            ft.Container(
                padding=20,
                bgcolor=ft.Colors.SURFACE,
                border_radius=ft.BorderRadius.only(top_left=16, top_right=16),
                height=400,
                content=ft.Column([
                    ft.Text(title, size=18, weight=ft.FontWeight.BOLD),
                    ft.Divider(),
                    ft.Container(content=rg, expand=True),
                    ft.Divider(),
                    ft.TextButton("Reset Filter", icon=ft.Icons.REFRESH, on_click=handle_reset),
                ]),
            )
        )
        return sheet

    def create_filter_chip(label_text, on_click):
        return ft.Container(
            content=ft.Row([
                ft.Text(label_text, size=11, weight=ft.FontWeight.W_600),
                ft.Icon(ft.Icons.ARROW_DROP_DOWN_ROUNDED, size=16),
            ], spacing=3),
            padding=ft.Padding(10, 5, 8, 5),
            border_radius=8,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.14, ft.Colors.ON_SURFACE)),
            bgcolor=ft.Colors.TRANSPARENT,
            on_click=on_click,
            ink=True,
        )

    def open_category_filter():
        cats = sorted(list(set(c.get("category", {}).get("name") for c in all_available_courses if c.get("category", {}).get("name"))))
        sheet = build_filter_sheet("Filter by Category", cats, current_category_filter, set_category_filter)
        page.show_dialog(sheet)

    def set_category_filter(val):
        nonlocal current_category_filter
        current_category_filter = val
        cat_chip.content.controls[0].value = f"Category: {val}" if val else "Category"
        cat_chip.bgcolor = ft.Colors.PRIMARY_CONTAINER if val else ft.Colors.TRANSPARENT
        cat_chip.border = ft.Border.all(1, ft.Colors.PRIMARY if val else ft.Colors.with_opacity(0.14, ft.Colors.ON_SURFACE))
        page.update()

    def open_instructor_filter():
        insts = sorted(list(set(f"{c.get('admin', {}).get('first_name', '')} {c.get('admin', {}).get('last_name', '')}".strip() for c in all_available_courses)))
        insts = [i for i in insts if i]
        sheet = build_filter_sheet("Filter by Instructor", insts, current_instructor_filter, set_instructor_filter)
        page.show_dialog(sheet)

    def set_instructor_filter(val):
        nonlocal current_instructor_filter
        current_instructor_filter = val
        inst_chip.content.controls[0].value = f"Instructor: {val}" if val else "Instructor"
        inst_chip.bgcolor = ft.Colors.PRIMARY_CONTAINER if val else ft.Colors.TRANSPARENT
        inst_chip.border = ft.Border.all(1, ft.Colors.PRIMARY if val else ft.Colors.with_opacity(0.14, ft.Colors.ON_SURFACE))
        page.update()

    def open_org_filter():
        orgs = sorted(list(set(c.get("organisation", {}).get("name") for c in all_available_courses if c.get("organisation", {}).get("name"))))
        sheet = build_filter_sheet("Filter by Organisation", orgs, current_org_filter, set_org_filter)
        page.show_dialog(sheet)

    def set_org_filter(val):
        nonlocal current_org_filter
        current_org_filter = val
        org_chip.content.controls[0].value = f"Org: {val}" if val else "Organisation"
        org_chip.bgcolor = ft.Colors.PRIMARY_CONTAINER if val else ft.Colors.TRANSPARENT
        org_chip.border = ft.Border.all(1, ft.Colors.PRIMARY if val else ft.Colors.with_opacity(0.14, ft.Colors.ON_SURFACE))
        page.update()

    cat_chip = create_filter_chip("Category", lambda e: open_category_filter())
    inst_chip = create_filter_chip("Instructor", lambda e: open_instructor_filter())
    org_chip = create_filter_chip("Organisation", lambda e: open_org_filter())

    filter_row = ft.Row([cat_chip, inst_chip, org_chip], scroll=ft.ScrollMode.AUTO, spacing=8)
    App_bar = get_bottom_appbar(page)

    # ── Section Subtitles ──────────────────────────────────────────────────────
    SECTION_SUBTITLES = {
        SECTION_ENROLLED: "Continue your ongoing courses & offline library",
        SECTION_AVAILABLE: "Explore our rich collection of courses",
        SECTION_PLAYLISTS: "Curated learning tracks & playlists",
        SECTION_COMPLETED: "Track your completed courses and achievements",
        SECTION_ORG: "Courses exclusive to your organisation",
    }

    section_subtitle_text = ft.Text(
        value=SECTION_SUBTITLES[SECTION_ENROLLED],
        size=12,
        color=ft.Colors.ON_SURFACE_VARIANT,
    )

    course_container = ft.Container(
        content=ft.ResponsiveRow(
            spacing=16,
            run_spacing=16,
            controls=course_cards,
        ),
        padding=16,
    )
    enroll_container = ft.Container(
        content=ft.ResponsiveRow(
            spacing=16,
            run_spacing=16,
            controls=enroll_cards,
        ),
        padding=16,
    )
    completed_container = ft.Container(
        content=ft.ResponsiveRow(
            spacing=16,
            run_spacing=16,
            controls=completed_cards,
        ),
        padding=16,
    )
    playlist_container = ft.Container(
        content=ft.ResponsiveRow(
            spacing=16,
            run_spacing=16,
            controls=playlist_cards,
        ),
        padding=16,
    )

    # ── Loading Placeholder Helper ─────────────────────────────────────────────
    def _loading_view(message: str):
        return ft.Container(
            height=260,
            alignment=ft.Alignment.CENTER,
            content=ft.Column(
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
                controls=[
                    ft.ProgressRing(width=28, height=28, stroke_width=3, color=ft.Colors.PRIMARY),
                    ft.Text(message, size=13, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500),
                ],
            ),
        )

    # ── Section Content Panes ──────────────────────────────────────────────────
    available_section = ft.Container(
        expand=True,
        padding=ft.Padding.only(left=16, right=16, top=12, bottom=8),
        content=ft.Column(
            expand=True,
            controls=[
                # STATIC SEARCH & FILTER SECTION
                ft.Container(
                    content=ft.Column([
                        ft.Row([search_tf]),
                        filter_row,
                    ], spacing=10),
                    padding=ft.Padding.only(bottom=6),
                ),
                # SCROLLABLE COURSES
                ft.ListView(
                    expand=True,
                    scroll=ft.ScrollMode.AUTO,
                    controls=[_loading_view("Getting available courses...")],
                ),
            ],
        ),
    )

    enrolled_section = ft.Container(
        expand=True,
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ft.ListView(
                    expand=True,
                    scroll=ft.ScrollMode.AUTO,
                    controls=[_loading_view("Fetching your courses...")],
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        ),
        padding=0,
    )

    completed_section = ft.Container(
        expand=True,
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ft.ListView(
                    expand=True,
                    scroll=ft.ScrollMode.AUTO,
                    controls=[_loading_view("Getting completed courses...")],
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        ),
        padding=0,
    )

    playlists_section = ft.Container(
        expand=True,
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ft.ListView(
                    expand=True,
                    scroll=ft.ScrollMode.AUTO,
                    controls=[_loading_view("Fetching playlists...")],
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        ),
        padding=0,
    )

    org_section = ft.Container(
        expand=True,
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ft.ListView(
                    expand=True,
                    scroll=ft.ScrollMode.AUTO,
                    controls=[_loading_view("Fetching organisation courses...")],
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        ),
        padding=0,
    )

    section_body = ft.Container(
        expand=True,
        content=enrolled_section,
    )

    SECTION_CONTENT = {
        SECTION_ENROLLED: enrolled_section,
        SECTION_AVAILABLE: available_section,
        SECTION_PLAYLISTS: playlists_section,
        SECTION_COMPLETED: completed_section,
        SECTION_ORG: org_section,
    }

    # ── Sleek Sectional Quick Tab Bar (Squircle Modern Standard) ─────────────
    TABS_DATA = [
        {"index": SECTION_ENROLLED, "label": "My Courses", "icon": ft.Icons.AUTO_STORIES_ROUNDED},
        {"index": SECTION_AVAILABLE, "label": "Explore", "icon": ft.Icons.EXPLORE_ROUNDED},
        {"index": SECTION_PLAYLISTS, "label": "Playlists", "icon": ft.Icons.PLAYLIST_PLAY_ROUNDED},
        {"index": SECTION_COMPLETED, "label": "Completed", "icon": ft.Icons.CHECK_CIRCLE_ROUNDED},
        {"index": SECTION_ORG, "label": "Organisation", "icon": ft.Icons.BUSINESS_ROUNDED},
    ]

    current_active_tab = SECTION_ENROLLED
    tab_pills = []

    def update_tab_pills(selected_index: int):
        nonlocal current_active_tab
        current_active_tab = selected_index
        for pill in tab_pills:
            idx = pill.data
            is_active = (idx == selected_index)
            pill.bgcolor = ft.Colors.PRIMARY if is_active else ft.Colors.TRANSPARENT
            pill.border = ft.Border.all(
                1,
                ft.Colors.PRIMARY if is_active else ft.Colors.with_opacity(0.14, ft.Colors.ON_SURFACE),
            )
            pill.shadow = ft.BoxShadow(
                blur_radius=6,
                spread_radius=0,
                color=ft.Colors.with_opacity(0.2, ft.Colors.PRIMARY),
                offset=ft.Offset(0, 2),
            ) if is_active else None
            row = pill.content
            row.controls[0].color = ft.Colors.ON_PRIMARY if is_active else ft.Colors.ON_SURFACE_VARIANT
            row.controls[1].color = ft.Colors.ON_PRIMARY if is_active else ft.Colors.ON_SURFACE_VARIANT
            row.controls[1].weight = ft.FontWeight.W_700 if is_active else ft.FontWeight.W_500
        if _is_mounted(tab_bar_scroll_row):
            tab_bar_scroll_row.update()

    def show_section(index: int):
        section_body.content = SECTION_CONTENT[index]
        section_subtitle_text.value = SECTION_SUBTITLES.get(index, "")
        update_tab_pills(index)
        page.update()

    # Build initial tab pill widgets (sleek squircle, transparent unselected state)
    for item in TABS_DATA:
        idx = item["index"]
        is_active = (idx == current_active_tab)
        pill = ft.Container(
            data=idx,
            padding=ft.Padding.symmetric(horizontal=6, vertical=4),
            border_radius=4,
            bgcolor=ft.Colors.PRIMARY if is_active else ft.Colors.TRANSPARENT,
            border=ft.Border.all(
                1,
                ft.Colors.PRIMARY if is_active else ft.Colors.with_opacity(0.14, ft.Colors.ON_SURFACE),
            ),
            shadow=ft.BoxShadow(
                blur_radius=6,
                spread_radius=0,
                color=ft.Colors.with_opacity(0.2, ft.Colors.PRIMARY),
                offset=ft.Offset(0, 2),
            ) if is_active else None,
            ink=True,
            animate=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
            on_click=lambda e, target_idx=idx: show_section(target_idx),
            visible=(idx != SECTION_ORG),  # Hidden by default until org courses exist
            content=ft.Row(
                spacing=5,
                tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(
                        item["icon"],
                        size=14,
                        color=ft.Colors.ON_PRIMARY if is_active else ft.Colors.ON_SURFACE_VARIANT,
                    ),
                    ft.Text(
                        item["label"],
                        size=12,
                        weight=ft.FontWeight.W_700 if is_active else ft.FontWeight.W_500,
                        color=ft.Colors.ON_PRIMARY if is_active else ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
            ),
        )
        tab_pills.append(pill)

    tab_bar_scroll_row = ft.Row(
        spacing=8,
        scroll=ft.ScrollMode.AUTO,
        controls=tab_pills,
    )

    # ── Sleek Modern Header Container (No Hamburger, No Profile Avatar, Clean Title & Tabs) ───────
    header_container = ft.Container(
        padding=ft.Padding.only(left=16, right=16, top=14, bottom=12),
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border(bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE))),
        content=ft.Column(
            spacing=14,
            controls=[
                ft.Column(
                    spacing=2,
                    controls=[ft.Row(controls=[
                         ft.Icon(ft.Icons.SCHOOL_SHARP, color= ft.Colors.PRIMARY),
                        ft.Text(
                            "Learn",
                            size=26,
                            weight=ft.FontWeight.W_800,
                            color=ft.Colors.ON_SURFACE,
                        ),]),
                        section_subtitle_text,
                    ],
                ),
                tab_bar_scroll_row,
            ],
        ),
    )

    async def populate_tabs():
        token = await page.shared_preferences.get("auth_token")
        course_list = await get_courses(token, {"is_public": True})
        enrolled_list = await get_enrollments(token, None)
        completed_list = await get_courses(token, {"progress": 100})
        enrolled_ids = {course.get("id") for course in enrolled_list} if isinstance(enrolled_list, list) else set()
        completed_ids = {course.get("id") for course in completed_list} if isinstance(completed_list, list) else set()
        playlists = await get_all_playlists(token)

        all_available_courses.clear()
        if isinstance(course_list, list):
            for course in course_list:
                course_id = course.get("id")
                if course_id not in enrolled_ids and course_id not in completed_ids:
                    all_available_courses.append(course)

        # Run the filter to initially populate course_cards
        filter_courses()

        # Enrolled courses
        enroll_cards.clear()
        if isinstance(enrolled_list, list):
            for course in enrolled_list:
                course_name = course.get("name", "Untitled Course")
                image_url = course.get("image_url", "")
                course_id = course.get("id")
                if course_id not in completed_ids:
                    progress = course.get("progress", 0.0)
                    first_name = course.get("admin", {}).get("first_name", "Unknown")
                    last_name = course.get("admin", {}).get("last_name", "Instructor")
                    full_name = f"{first_name} {last_name}".strip()
                    category = course.get("category", {}).get("name")
                    rating = course.get("rating", 0.0)
                    card = get_enrolled_card(
                        page=page,
                        course_id=course_id,
                        course_title=course_name,
                        course_category=category,
                        course_author=full_name,
                        image_url=image_url,
                        progress=progress,
                        rating=rating,
                        course_dict=course,
                    )
                    card.on_click = lambda e, c_id=course_id, c_name=course_name: page.go(f"/courses/{c_id}/view")
                    card.col = {"xs": 12, "sm": 6}
                    enroll_cards.append(card)

        # Completed courses
        completed_cards.clear()
        if isinstance(completed_list, list):
            for course in completed_list:
                course_name = course.get("name", "Untitled Course")
                image_url = course.get("image_url", "")
                course_id = course.get("id")
                admin = course.get("admin") or {}
                first_name = admin.get("first_name", "Unknown") if isinstance(admin, dict) else "Unknown"
                last_name = admin.get("last_name", "Instructor") if isinstance(admin, dict) else "Instructor"
                full_name = f"{first_name} {last_name}".strip()
                category = (course.get("category") or {}).get("name") if isinstance(course.get("category"), dict) else None
                rating = course.get("rating", 0.0)
                card = get_completed_card(
                    course_name=course_name,
                    course_id=course_id,
                    on_review_click=lambda cid: page.go(f"/courses/{cid}/view"),
                    on_stats_click=lambda cid: page.go(f"/courses/{cid}/stats"),
                    page=page,
                    image_url=image_url,
                    category=category,
                    author=full_name,
                    rating=rating,
                    course_dict=course,
                )
                card.col = {"xs": 12, "sm": 6}
                completed_cards.append(card)

        # Playlists
        playlist_cards.clear()
        if isinstance(playlists, list):
            for playlist in playlists:
                p_name = playlist.get("name", "Untitled")
                p_img = playlist.get("image_url", "")
                p_id = playlist.get("id")
                org = playlist.get("Organisation", "Organisation")
                created_at = playlist.get("created_at", "")
                if created_at:
                    created_at = datetime.fromisoformat(created_at).strftime("%d/%m/%Y")
                card = get_playlist_card(
                    p_name,
                    org,
                    p_img,
                    created_at,
                    on_enroll_click=lambda e, cid=p_id: page.go(f"/playlists/{cid}"),
                )
                card.on_click = lambda e, pid=p_id: page.go(f"/playlists/{pid}")
                card.col = {"xs": 12, "sm": 6}
                playlist_cards.append(card)

        # Rebuild Available Section
        available_section.content = ft.Column(
            expand=True,
            controls=[
                ft.Container(
                    content=ft.Column([
                        ft.Row([search_tf]),
                        filter_row,
                    ], spacing=10),
                    padding=ft.Padding.only(bottom=6),
                ),
                ft.ListView(
                    expand=True,
                    scroll=ft.ScrollMode.AUTO,
                    controls=[
                        course_container if course_cards else ft.Container(
                            padding=40,
                            alignment=ft.Alignment.CENTER,
                            content=ft.Column(
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=12,
                                controls=[
                                    ft.Icon(ft.Icons.SEARCH_OFF_ROUNDED, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ft.Text(
                                        "No available courses found",
                                        size=16,
                                        color=ft.Colors.ON_SURFACE,
                                        weight=ft.FontWeight.W_600,
                                        text_align=ft.TextAlign.CENTER,
                                    ),
                                    ft.Text(
                                        "Try adjusting your filters or check back later for new courses.",
                                        size=13,
                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                        text_align=ft.TextAlign.CENTER,
                                    ),
                                ],
                            ),
                        ),
                    ],
                ),
            ],
        )

        # Rebuild Enrolled Section
        if enroll_cards:
            enrolled_content = enroll_container
        else:
            enrolled_content = ft.Container(
                padding=ft.Padding.all(36),
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=14,
                    controls=[
                        ft.Container(
                            padding=ft.Padding.all(18),
                            border_radius=40,
                            bgcolor=ft.Colors.PRIMARY_CONTAINER,
                            content=ft.Icon(ft.Icons.AUTO_STORIES_ROUNDED, size=44, color=ft.Colors.PRIMARY),
                        ),
                        ft.Text(
                            "No Enrolled Courses Yet",
                            size=18,
                            weight=ft.FontWeight.W_700,
                            color=ft.Colors.ON_SURFACE,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Text(
                            "You haven't enrolled in any courses yet. Browse our course catalog to kickstart your learning!",
                            size=13,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                            text_align=ft.TextAlign.CENTER,
                            max_lines=2,
                        ),
                        ft.Container(height=4),
                        ft.ElevatedButton(
                            content=ft.Row(
                                [
                                    ft.Icon(ft.Icons.EXPLORE_ROUNDED, size=16, color=ft.Colors.ON_PRIMARY),
                                    ft.Text("Explore Available Courses", size=13, weight=ft.FontWeight.W_600, color=ft.Colors.ON_PRIMARY),
                                ],
                                tight=True,
                                spacing=6,
                            ),
                            bgcolor=ft.Colors.PRIMARY,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=20),
                                padding=ft.Padding.symmetric(horizontal=18, vertical=10),
                            ),
                            on_click=lambda _: show_section(SECTION_AVAILABLE),
                        ),
                    ],
                ),
            )

        enrolled_section.content = ft.Column(
            controls=[
                ft.ListView(
                    expand=True,
                    controls=[enrolled_content],
                    scroll=ft.ScrollMode.AUTO,
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        # Rebuild Completed Section
        if completed_cards:
            completed_content = completed_container
        else:
            completed_content = ft.Container(
                padding=ft.Padding.all(36),
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=14,
                    controls=[
                        ft.Container(
                            padding=ft.Padding.all(18),
                            border_radius=40,
                            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER_600),
                            content=ft.Icon(ft.Icons.EMOJI_EVENTS_ROUNDED, size=44, color=ft.Colors.AMBER_600),
                        ),
                        ft.Text(
                            "No Completed Courses Yet",
                            size=18,
                            weight=ft.FontWeight.W_700,
                            color=ft.Colors.ON_SURFACE,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Text(
                            "Complete all modules and assignments in an enrolled course to view your achievement records here.",
                            size=13,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                            text_align=ft.TextAlign.CENTER,
                            max_lines=2,
                        ),
                        ft.Container(height=4),
                        ft.OutlinedButton(
                            content=ft.Row(
                                [
                                    ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, size=16, color=ft.Colors.PRIMARY),
                                    ft.Text("Resume Enrolled Courses", size=13, weight=ft.FontWeight.W_600, color=ft.Colors.PRIMARY),
                                ],
                                tight=True,
                                spacing=6,
                            ),
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=20),
                                side=ft.BorderSide(1.5, ft.Colors.PRIMARY),
                                padding=ft.Padding.symmetric(horizontal=18, vertical=10),
                            ),
                            on_click=lambda _: show_section(SECTION_ENROLLED),
                        ),
                    ],
                ),
            )

        completed_section.content = ft.Column(
            controls=[
                ft.ListView(
                    expand=True,
                    controls=[completed_content],
                    scroll=ft.ScrollMode.AUTO,
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        # Rebuild Playlists Section
        if playlist_cards:
            playlists_content = playlist_container
        else:
            playlists_content = ft.Container(
                padding=ft.Padding.all(36),
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=12,
                    controls=[
                        ft.Icon(ft.Icons.PLAYLIST_PLAY_ROUNDED, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text("No Playlists Available", size=16, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                        ft.Text("Curated playlist tracks will be displayed here.", size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                    ],
                ),
            )

        playlists_section.content = ft.Column(
            controls=[
                ft.ListView(
                    expand=True,
                    controls=[playlists_content],
                    scroll=ft.ScrollMode.AUTO,
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        # Organisation courses
        org_list = await get_courses(token, {"is_public": "organisation"})
        if isinstance(org_list, list) and len(org_list) > 0:
            tab_pills[SECTION_ORG].visible = True
            for course in org_list:
                course_name = course.get("name", "Untitled Course")
                image_url = course.get("image_url", "")
                course_id = course.get("id")
                if course_id not in enrolled_ids and course_id not in completed_ids:
                    category = course.get("category", {}).get("name")
                    org_name = course.get("organisation", {}).get("name", "Organisation")
                    created_at = course.get("created_at", "")
                    if created_at and "T" in created_at:
                        created_at = datetime.fromisoformat(created_at).strftime("%d/%m/%Y")

                    card = get_org_course_card(
                        course_name=course_name,
                        category=category,
                        org_name=org_name,
                        image_url=image_url,
                        created_at=created_at,
                        on_view_click=lambda e, cid=course_id: page.go(f"/courses/{cid}"),
                        course_dict=course,
                        page=page,
                    )
                    card.col = {"xs": 12, "sm": 6, "md": 6, "lg": 4}
                    org_cards.append(card)
        else:
            tab_pills[SECTION_ORG].visible = False

        org_container = ft.ResponsiveRow(spacing=16, run_spacing=16)
        org_container.controls = org_cards

        org_section.content = ft.Column(
            controls=[
                ft.ListView(
                    expand=True,
                    controls=[
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=16),
                            content=org_container,
                        ) if org_cards else ft.Container(
                            padding=ft.Padding.all(36),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Column(
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=12,
                                controls=[
                                    ft.Icon(ft.Icons.BUSINESS_ROUNDED, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ft.Text("No Organisation Courses", size=16, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                                    ft.Text("Courses tailored for your organisation will appear here.", size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                            ),
                        ),
                    ],
                    scroll=ft.ScrollMode.AUTO,
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        page.update()

        async def animate_all_cards():
            import asyncio
            await asyncio.sleep(0.02)
            for card_list in [enroll_cards, completed_cards, playlist_cards, org_cards]:
                if card_list:
                    for card in card_list:
                        card.opacity = 1
                        card.offset = ft.Offset(0, 0)
            page.update()

        page.run_task(animate_all_cards)

    page.run_task(populate_tabs)

    return ft.View(
        route="/courses",
        bottom_appbar=App_bar,
        padding=0,
        bgcolor=ft.Colors.SURFACE,
        controls=[
            ft.SafeArea(
                expand=True,
                content=ft.Column(
                    expand=True,
                    spacing=0,
                    controls=[
                        header_container,
                        section_body,
                    ],
                ),
            ),
        ],
    )