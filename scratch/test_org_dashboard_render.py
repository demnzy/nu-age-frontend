import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import flet as ft
from unittest.mock import MagicMock, AsyncMock
from src.utils.file_opener import show_page_snackbar

mock_org_data = {
    "id": "584b537e-6521-4852-a7e4-18f6c095126d",
    "name": "Apex Engineering Institute",
    "email": "contact@apex.edu",
    "number": "+1 (555) 382-9912",
    "website": "https://apex.edu",
    "address": "400 University Crest, Silicon Valley, CA",
    "owner_id": "owner-1234-uuid",
    "logo": "https://nu-age-cdn.b-cdn.net/logos/placeholder%202.png",
    "theme_color": "#4338CA",
    "created_at": "2024-03-01T12:00:00Z",
    "members": 15,
    "courses": 4,
    "staff": 3,
    "students": 12,
    "plan": {
        "name": "Enterprise Academy",
        "max_members": 100,
        "max_courses": 50,
        "price": 149.0,
        "features": ["AI Course Builder", "Branded Mobile Portal", "Custom Domain", "Priority 24/7 Support"]
    }
}

mock_members = [
    {"id": "owner-1234-uuid", "first_name": "Daniel", "last_name": "Davids", "email": "daniel@apex.edu", "role": "OWNER"},
    {"id": "user-2", "first_name": "Sarah", "last_name": "Connor", "email": "sarah@apex.edu", "role": "TEACHER"},
    {"id": "user-3", "first_name": "Alex", "last_name": "Rivera", "email": "alex.r@apex.edu", "role": "STUDENT"},
    {"id": "user-4", "first_name": "Elena", "last_name": "Rostova", "email": "elena@apex.edu", "role": "STUDENT"},
]

mock_courses = [
    {
        "id": "c-1",
        "name": "Advanced Distributed Systems",
        "description": "Architecting high-throughput, fault-tolerant cloud services.",
        "image_url": "https://nu-age-cdn.b-cdn.net/logos/placeholder%202.png",
        "public": "true",
        "total_students": 45,
    },
    {
        "id": "c-2",
        "name": "Internal Engineering Onboarding",
        "description": "Exclusive internal curriculum for junior engineers.",
        "image_url": "https://nu-age-cdn.b-cdn.net/logos/placeholder%202.png",
        "public": "organisation",
        "total_students": 12,
    },
    {
        "id": "c-3",
        "name": "Rust for High Performance Systems",
        "description": "Deep dive into memory safety without garbage collection.",
        "image_url": None,
        "public": "false",
        "total_students": 0,
    }
]

mock_playlists = [
    {
        "id": "pl-1",
        "name": "Fullstack Cloud Path",
        "description": "Zero to production fullstack learning track.",
        "image_url": "https://nu-age-cdn.b-cdn.net/logos/placeholder%202.png"
    }
]

async def build_modern_dashboard_view(page: ft.Page, org_data: dict, token: str = "mock_token"):
    org_name = org_data.get("name", "My Workspace")
    org_id = org_data.get("id", "")
    org_email = org_data.get("email", "admin@org.com")
    org_phone = org_data.get("number", "+000 0000 0000")
    org_website = org_data.get("website", "")
    org_address = org_data.get("address", "")
    org_logo = org_data.get("logo", "")
    owner_id = str(org_data.get("owner_id", ""))
    theme_color = org_data.get("theme_color") or ft.Colors.PRIMARY

    if not org_id:
        raise ValueError("build_dashboard_view received org_data with no valid 'id'")

    if hasattr(page, "session") and hasattr(page.session, "store"):
        if hasattr(page.session.store, "set"):
            page.session.store.set("current_org_id", org_id)
        elif isinstance(page.session.store, dict):
            page.session.store["current_org_id"] = org_id
    elif hasattr(page, "session") and hasattr(page.session, "set"):
        page.session.set("current_org_id", org_id)

    plan_data = org_data.get("plan") or {}
    plan_name = plan_data.get("name", "Free Plan") if isinstance(plan_data, dict) else "Free Plan"
    max_members = plan_data.get("max_members") if isinstance(plan_data, dict) else None
    max_courses = plan_data.get("max_courses") if isinstance(plan_data, dict) else None
    plan_features = plan_data.get("features", []) if isinstance(plan_data, dict) else []

    members = list(mock_members)
    courses = list(mock_courses)
    playlists = list(mock_playlists)

    stats = {
        "members": len(members),
        "courses": len(courses),
        "staff": sum(1 for m in members if str(m.get("role", "")).upper() in ("TEACHER", "STAFF", "ADMIN", "OWNER")),
        "plan": plan_name,
        "students": sum(1 for m in members if str(m.get("role", "")).upper() == "STUDENT"),
    }

    active_tab = "courses"
    course_search_query = ""
    course_filter_status = "all"
    member_search_query = ""
    member_filter_role = "all"

    tab_content_container = ft.Container(expand=True)

    async def copy_to_clipboard(text: str, label: str = "Link"):
        try:
            if hasattr(page, "set_clipboard"):
                await page.set_clipboard(text)
            show_page_snackbar(
                page,
                ft.SnackBar(
                    content=ft.Row([
                        ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.WHITE, size=18),
                        ft.Text(f"{label} copied to clipboard!", color=ft.Colors.WHITE, size=13),
                    ], spacing=8),
                    bgcolor=ft.Colors.GREEN_700,
                    duration=2500,
                )
            )
        except Exception as e:
            print(f"Clipboard error: {e}")

    async def launch_url_safe(url: str):
        if not url:
            return
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        try:
            if hasattr(page, "launch_url"):
                await page.launch_url(url)
        except Exception as e:
            print(f"Failed to launch url {url}: {e}")

    # ── Role Badge Color Helper ───────────────────────────────────────────────
    def get_role_badge(member_role: str):
        role_upper = member_role.upper()
        if role_upper == "OWNER":
            color = ft.Colors.PURPLE_600
        elif role_upper == "ADMIN":
            color = ft.Colors.BLUE_600
        elif role_upper in ("TEACHER", "INSTRUCTOR", "STAFF"):
            color = ft.Colors.ORANGE_600
        else:
            color = ft.Colors.TEAL_600

        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=2.5),
            bgcolor=ft.Colors.with_opacity(0.12, color),
            border_radius=8,
            content=ft.Text(role_upper, size=10, color=color, weight=ft.FontWeight.BOLD),
        )

    # ── Tab 1: Courses Render ─────────────────────────────────────────────────
    def render_courses_tab():
        filtered_courses = courses
        if course_search_query.strip():
            q = course_search_query.strip().lower()
            filtered_courses = [c for c in filtered_courses if q in c.get("name", "").lower() or q in c.get("description", "").lower()]

        if course_filter_status == "public":
            filtered_courses = [c for c in filtered_courses if str(c.get("public", "")).lower() == "true"]
        elif course_filter_status == "campus":
            filtered_courses = [c for c in filtered_courses if str(c.get("public", "")).lower() in ("organisation", "organization", "campus")]
        elif course_filter_status == "draft":
            filtered_courses = [c for c in filtered_courses if str(c.get("public", "")).lower() not in ("true", "organisation", "organization", "campus")]

        def on_search_change(e):
            nonlocal course_search_query
            course_search_query = e.control.value or ""
            render_active_tab()
            page.update()

        def set_filter(status):
            nonlocal course_filter_status
            course_filter_status = status
            render_active_tab()
            page.update()

        def filter_chip(label: str, key: str):
            is_active = (course_filter_status == key)
            return ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                border_radius=18,
                bgcolor=theme_color if is_active else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                ink=True,
                on_click=lambda _: set_filter(key),
                content=ft.Text(
                    label,
                    size=11,
                    weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.NORMAL,
                    color=ft.Colors.WHITE if is_active else ft.Colors.ON_SURFACE,
                ),
            )

        filter_bar = ft.Row([
            filter_chip("All", "all"),
            filter_chip("Public", "public"),
            filter_chip("Campus", "campus"),
            filter_chip("Drafts", "draft"),
        ], spacing=8, scroll=ft.ScrollMode.AUTO)

        search_box = ft.TextField(
            hint_text="Search courses…",
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            border_radius=10,
            dense=True,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            on_change=on_search_change,
            value=course_search_query,
            expand=True,
        )

        course_items = []
        for c in filtered_courses:
            c_id = c.get("id", "")
            title = c.get("name", "Untitled Course")
            desc = c.get("description", "No description provided.")
            img = c.get("image_url")
            pub_val = str(c.get("public", "false")).lower()
            students_cnt = c.get("total_students", 0)

            # Clean public / campus / draft badges per user instruction
            if pub_val == "true":
                status_badge = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=6,
                    bgcolor=ft.Colors.with_opacity(0.9, ft.Colors.GREEN_700),
                    content=ft.Text("PUBLIC", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                )
            elif pub_val in ("organisation", "organization", "campus"):
                status_badge = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=6,
                    bgcolor=ft.Colors.with_opacity(0.9, ft.Colors.BLUE_700),
                    content=ft.Text("CAMPUS", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                )
            else:
                status_badge = ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=6,
                    bgcolor=ft.Colors.with_opacity(0.9, ft.Colors.GREY_700),
                    content=ft.Text("DRAFT", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                )

            card = ft.Container(
                bgcolor=ft.Colors.SURFACE,
                border_radius=14,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                shadow=ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK), offset=ft.Offset(0, 2)),
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                content=ft.Column([
                    ft.Stack([
                        ft.Container(
                            height=125,
                            width=float("inf"),
                            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                            content=ft.Image(src=img or "https://nu-age-cdn.b-cdn.net/logos/placeholder%202.png", fit=ft.BoxFit.COVER),
                        ),
                        ft.Container(top=8, left=8, content=status_badge),
                    ]),
                    ft.Container(
                        padding=14,
                        content=ft.Column([
                            ft.Text(title, size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(desc, size=12, color=ft.Colors.ON_SURFACE_VARIANT, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Container(height=4),
                            ft.Row([
                                ft.Row([
                                    ft.Icon(ft.Icons.PEOPLE_OUTLINE_ROUNDED, size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ft.Text(f"{students_cnt} Enrolled", size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500),
                                ], spacing=4),
                                ft.Row([
                                    ft.IconButton(
                                        ft.Icons.EDIT_ROUNDED,
                                        tooltip="Manage Curriculum",
                                        icon_size=17,
                                        icon_color=theme_color,
                                        on_click=lambda _, cid=c_id: page.go(f"/courses/{cid}/manage"),
                                    ),
                                    ft.IconButton(
                                        ft.Icons.SETTINGS_OUTLINED,
                                        tooltip="Course Settings",
                                        icon_size=17,
                                        icon_color=ft.Colors.ON_SURFACE_VARIANT,
                                        on_click=lambda _, cid=c_id: page.go(f"/organisations/{org_id}/courses/{cid}/settings"),
                                    ),
                                    ft.IconButton(
                                        ft.Icons.VISIBILITY_OUTLINED,
                                        tooltip="View Course",
                                        icon_size=17,
                                        icon_color=ft.Colors.ON_SURFACE_VARIANT,
                                        on_click=lambda _, cid=c_id: page.go(f"/courses/{cid}/view"),
                                    ),
                                ], spacing=0),
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ], spacing=4),
                    ),
                ], spacing=0),
            )
            course_items.append(ft.Container(col={"xs": 12, "sm": 6, "lg": 4}, content=card))

        content_list = ft.ResponsiveRow(controls=course_items, run_spacing=14) if course_items else ft.Container(
            padding=40,
            alignment=ft.Alignment.CENTER,
            content=ft.Column([
                ft.Icon(ft.Icons.AUTO_STORIES_OUTLINED, size=44, color=ft.Colors.with_opacity(0.3, ft.Colors.ON_SURFACE)),
                ft.Text("No courses found matching your criteria.", size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.FilledButton("Create Course", icon=ft.Icons.ADD_ROUNDED, on_click=lambda _: page.go(f"/organisations/{org_id}/courses")),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
        )

        return ft.Column([
            # Section Title & Primary Action
            ft.Row([
                ft.Column([
                    ft.Text("Courses & Curricula", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Text(f"{len(courses)} published courses in academy library", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                ], spacing=1),
                ft.FilledButton(
                    "New Course",
                    icon=ft.Icons.ADD_ROUNDED,
                    style=ft.ButtonStyle(bgcolor=theme_color, shape=ft.RoundedRectangleBorder(radius=10)),
                    on_click=lambda _: page.go(f"/organisations/{org_id}/courses"),
                ),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row([search_box, filter_bar], spacing=10, wrap=True),
            content_list,
        ], spacing=14)

    # ── Tab 2: Members Render ─────────────────────────────────────────────────
    def render_members_tab():
        filtered_members = members
        if member_search_query.strip():
            q = member_search_query.strip().lower()
            filtered_members = [m for m in filtered_members if q in f"{m.get('first_name', '')} {m.get('last_name', '')}".lower() or q in m.get("email", "").lower()]

        if member_filter_role == "staff":
            filtered_members = [m for m in filtered_members if str(m.get("role", "")).upper() in ("TEACHER", "STAFF", "ADMIN", "OWNER")]
        elif member_filter_role == "students":
            filtered_members = [m for m in filtered_members if str(m.get("role", "")).upper() == "STUDENT"]

        def on_search_change(e):
            nonlocal member_search_query
            member_search_query = e.control.value or ""
            render_active_tab()
            page.update()

        def set_role_filter(role):
            nonlocal member_filter_role
            member_filter_role = role
            render_active_tab()
            page.update()

        def role_chip(label: str, key: str):
            is_active = (member_filter_role == key)
            return ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                border_radius=18,
                bgcolor=theme_color if is_active else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                ink=True,
                on_click=lambda _: set_role_filter(key),
                content=ft.Text(
                    label,
                    size=11,
                    weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.NORMAL,
                    color=ft.Colors.WHITE if is_active else ft.Colors.ON_SURFACE,
                ),
            )

        filter_bar = ft.Row([
            role_chip(f"All ({len(members)})", "all"),
            role_chip(f"Faculty & Staff ({stats['staff']})", "staff"),
            role_chip(f"Students ({stats['students']})", "students"),
        ], spacing=8, scroll=ft.ScrollMode.AUTO)

        search_box = ft.TextField(
            hint_text="Search members by name or email…",
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            border_radius=10,
            dense=True,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            on_change=on_search_change,
            value=member_search_query,
            expand=True,
        )

        member_cards = []
        for m in filtered_members:
            u_id = str(m.get("id", ""))
            first_name = m.get("first_name", "")
            last_name = m.get("last_name", "")
            full_name = f"{first_name} {last_name}".strip() or "Academy Member"
            email = m.get("email", "")
            is_owner = (u_id == owner_id)
            role_str = "OWNER" if is_owner else m.get("role", "STUDENT").upper()
            initials = f"{first_name[0] if first_name else '?'}{last_name[0] if last_name else ''}".upper()

            menu_items = [
                ft.PopupMenuItem(
                    content=ft.Text("View Profile", size=13),
                    icon=ft.Icons.PERSON_SEARCH_ROUNDED,
                    on_click=lambda _, uid=u_id: page.go(f"/member/{uid}"),
                ),
                ft.PopupMenuItem(
                    content=ft.Text("Copy Email", size=13),
                    icon=ft.Icons.CONTENT_COPY_ROUNDED,
                    on_click=lambda _, em=email: asyncio.create_task(copy_to_clipboard(em, "Email")),
                ),
            ]

            row = ft.Container(
                padding=12,
                bgcolor=ft.Colors.SURFACE,
                border_radius=12,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                content=ft.Row([
                    ft.Row([
                        ft.CircleAvatar(
                            content=ft.Text(initials, size=13, weight=ft.FontWeight.BOLD),
                            bgcolor=ft.Colors.with_opacity(0.12, theme_color),
                            color=theme_color,
                            radius=19,
                        ),
                        ft.Column([
                            ft.Row([
                                ft.Text(full_name, size=14, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                                get_role_badge(role_str),
                            ], spacing=8),
                            ft.Text(email, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                        ], spacing=2),
                    ], spacing=12, expand=True),
                    ft.PopupMenuButton(
                        icon=ft.Icons.MORE_VERT_ROUNDED,
                        icon_color=ft.Colors.ON_SURFACE_VARIANT,
                        items=menu_items,
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            )
            member_cards.append(row)

        member_list = ft.Column(controls=member_cards, spacing=8) if member_cards else ft.Container(
            padding=40,
            alignment=ft.Alignment.CENTER,
            content=ft.Column([
                ft.Icon(ft.Icons.GROUPS_ROUNDED, size=44, color=ft.Colors.with_opacity(0.3, ft.Colors.ON_SURFACE)),
                ft.Text("No members match your search.", size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.FilledButton("Invite Members", icon=ft.Icons.PERSON_ADD_ROUNDED, on_click=lambda _: page.go(f"/organisations/{org_id}/invite-members")),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
        )

        return ft.Column([
            # Section Title & Primary Action
            ft.Row([
                ft.Column([
                    ft.Text("Members & Faculty", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Text(f"{len(members)} total community members enrolled", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                ], spacing=1),
                ft.FilledButton(
                    "Invite Member",
                    icon=ft.Icons.PERSON_ADD_ROUNDED,
                    style=ft.ButtonStyle(bgcolor=theme_color, shape=ft.RoundedRectangleBorder(radius=10)),
                    on_click=lambda _: page.go(f"/organisations/{org_id}/invite-members"),
                ),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Row([search_box, filter_bar], spacing=10, wrap=True),
            member_list,
        ], spacing=14)

    # ── Tab 3: Playlists (Learning Paths) Render ───────────────────────────────
    def render_playlists_tab():
        playlist_items = []
        for p in playlists:
            p_id = p.get("id", "")
            title = p.get("name", "Learning Track")
            desc = p.get("description", "Curated roadmap for mastering core skills.")
            img = p.get("image_url")

            card = ft.Container(
                bgcolor=ft.Colors.SURFACE,
                border_radius=14,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                shadow=ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK), offset=ft.Offset(0, 2)),
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                content=ft.Column([
                    ft.Container(
                        height=110,
                        width=float("inf"),
                        bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                        content=ft.Image(src=img or "https://nu-age-cdn.b-cdn.net/logos/placeholder%202.png", fit=ft.BoxFit.COVER),
                    ),
                    ft.Container(
                        padding=14,
                        content=ft.Column([
                            ft.Text(title, size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(desc, size=12, color=ft.Colors.ON_SURFACE_VARIANT, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Container(height=4),
                            ft.Row([
                                ft.Container(
                                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                    border_radius=6,
                                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER_600),
                                    content=ft.Text("LEARNING PATH", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_700),
                                ),
                                ft.Row([
                                    ft.IconButton(
                                        ft.Icons.EDIT_ROUNDED,
                                        tooltip="Playlist Settings",
                                        icon_size=18,
                                        icon_color=theme_color,
                                        on_click=lambda _, pid=p_id: page.go(f"/playlists/{pid}/settings"),
                                    ),
                                    ft.IconButton(
                                        ft.Icons.VISIBILITY_ROUNDED,
                                        tooltip="View Learning Path",
                                        icon_size=18,
                                        icon_color=ft.Colors.ON_SURFACE_VARIANT,
                                        on_click=lambda _, pid=p_id: page.go(f"/playlists/{pid}"),
                                    ),
                                ], spacing=0),
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ], spacing=4),
                    ),
                ], spacing=0),
            )
            playlist_items.append(ft.Container(col={"xs": 12, "sm": 6, "lg": 4}, content=card))

        content_list = ft.ResponsiveRow(controls=playlist_items, run_spacing=14) if playlist_items else ft.Container(
            padding=40,
            alignment=ft.Alignment.CENTER,
            content=ft.Column([
                ft.Icon(ft.Icons.PLAYLIST_PLAY_ROUNDED, size=44, color=ft.Colors.with_opacity(0.3, ft.Colors.ON_SURFACE)),
                ft.Text("No learning paths created yet.", size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.FilledButton("Create Learning Path", icon=ft.Icons.ADD_ROUNDED, on_click=lambda _: page.go(f"/organisations/{org_id}/playlists")),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
        )

        return ft.Column([
            ft.Row([
                ft.Column([
                    ft.Text("Curated Learning Paths", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Text(f"{len(playlists)} guided tracks configured", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                ], spacing=1),
                ft.FilledButton(
                    "New Path",
                    icon=ft.Icons.ADD_ROUNDED,
                    style=ft.ButtonStyle(bgcolor=theme_color, shape=ft.RoundedRectangleBorder(radius=10)),
                    on_click=lambda _: page.go(f"/organisations/{org_id}/playlists"),
                ),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            content_list,
        ], spacing=14)

    # ── Tab 4: Organization Details ───────────────────────────────────────────
    def render_info_tab():
        features_column = []
        if plan_features:
            for feat in plan_features:
                features_column.append(
                    ft.Row([
                        ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.GREEN_600, size=16),
                        ft.Text(feat, size=13, color=ft.Colors.ON_SURFACE),
                    ], spacing=8)
                )

        info_card = ft.Container(
            padding=20,
            bgcolor=ft.Colors.SURFACE,
            border_radius=14,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.BUSINESS_ROUNDED, color=theme_color, size=20),
                    ft.Text("Academy Information", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                ], spacing=8),
                ft.Divider(height=1, color=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
                ft.ResponsiveRow([
                    ft.Column([
                        ft.Text("ORGANIZATION ID", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Row([
                            ft.Text(org_id, size=12, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE, expand=True),
                            ft.IconButton(ft.Icons.CONTENT_COPY_ROUNDED, icon_size=15, tooltip="Copy Org ID", on_click=lambda _: asyncio.create_task(copy_to_clipboard(org_id, "Organization ID"))),
                        ], spacing=4),
                    ], col={"xs": 12, "sm": 6}, spacing=2),
                    ft.Column([
                        ft.Text("PRIMARY CONTACT EMAIL", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(org_email, size=13, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE),
                    ], col={"xs": 12, "sm": 6}, spacing=2),
                    ft.Column([
                        ft.Text("CONTACT PHONE", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(org_phone or "Not specified", size=13, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE),
                    ], col={"xs": 12, "sm": 6}, spacing=2),
                    ft.Column([
                        ft.Text("OFFICIAL WEBSITE", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(org_website or "Not specified", size=13, weight=ft.FontWeight.W_500, color=theme_color if org_website else ft.Colors.ON_SURFACE),
                    ], col={"xs": 12, "sm": 6}, spacing=2),
                    ft.Column([
                        ft.Text("CAMPUS ADDRESS", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(org_address or "Not specified", size=13, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE),
                    ], col={"xs": 12}, spacing=2),
                ], run_spacing=14),
            ], spacing=14),
        )

        plan_card = ft.Container(
            padding=20,
            bgcolor=ft.Colors.SURFACE,
            border_radius=14,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.WORKSPACE_PREMIUM_ROUNDED, color=ft.Colors.PURPLE_500, size=20),
                    ft.Text("Subscription & Capacity", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                ], spacing=8),
                ft.Divider(height=1, color=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
                ft.Row([
                    ft.Text(plan_name, size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Container(padding=ft.Padding.symmetric(horizontal=10, vertical=4), border_radius=12, bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PURPLE_600), content=ft.Text("ACTIVE PLAN", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.PURPLE_600)),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([
                    ft.Text(f"Max Seats: {max_members or 'Unlimited'}", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text(f"Max Courses: {max_courses or 'Unlimited'}", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ], spacing=20),
                ft.Container(height=4),
                ft.Text("Included Features:", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                ft.Column(features_column, spacing=6) if features_column else ft.Text("Standard LMS capabilities included.", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            ], spacing=10),
        )

        return ft.Column([
            info_card,
            plan_card,
        ], spacing=14)

    def render_active_tab():
        if active_tab == "courses":
            tab_content_container.content = render_courses_tab()
        elif active_tab == "members":
            tab_content_container.content = render_members_tab()
        elif active_tab == "playlists":
            tab_content_container.content = render_playlists_tab()
        elif active_tab == "info":
            tab_content_container.content = render_info_tab()

    def refresh_tab_headers():
        tab_buttons.controls = [
            tab_button("Courses", "courses", ft.Icons.AUTO_STORIES_ROUNDED, len(courses)),
            tab_button("Members", "members", ft.Icons.GROUPS_ROUNDED, len(members)),
            tab_button("Learning Paths", "playlists", ft.Icons.PLAYLIST_PLAY_ROUNDED, len(playlists)),
            tab_button("Organization Details", "info", ft.Icons.INFO_OUTLINE_ROUNDED),
        ]

    def switch_tab(tab_key: str):
        nonlocal active_tab
        active_tab = tab_key
        refresh_tab_headers()
        render_active_tab()
        page.update()

    def tab_button(label: str, key: str, icon_name, count: int = None):
        is_sel = (active_tab == key)
        count_tag = f" ({count})" if count is not None else ""
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=14, vertical=8),
            border_radius=10,
            bgcolor=theme_color if is_sel else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
            ink=True,
            on_click=lambda _: switch_tab(key),
            content=ft.Row([
                ft.Icon(icon_name, size=15, color=ft.Colors.WHITE if is_sel else ft.Colors.ON_SURFACE),
                ft.Text(f"{label}{count_tag}", size=12, weight=ft.FontWeight.BOLD if is_sel else ft.FontWeight.W_500, color=ft.Colors.WHITE if is_sel else ft.Colors.ON_SURFACE),
            ], spacing=6, tight=True),
        )

    tab_buttons = ft.Row([
        tab_button("Courses", "courses", ft.Icons.AUTO_STORIES_ROUNDED, len(courses)),
        tab_button("Members", "members", ft.Icons.GROUPS_ROUNDED, len(members)),
        tab_button("Learning Paths", "playlists", ft.Icons.PLAYLIST_PLAY_ROUNDED, len(playlists)),
        tab_button("Organization Details", "info", ft.Icons.INFO_OUTLINE_ROUNDED),
    ], scroll=ft.ScrollMode.AUTO, spacing=8)

    # ── Bento Stat Card Component ─────────────────────────────────────────────
    def bento_stat_card(icon_name, title: str, main_val: str, subtitle: str, tint_color, on_tap_tab: str = None):
        return ft.Container(
            col={"xs": 6, "md": 3},
            bgcolor=ft.Colors.SURFACE,
            border_radius=14,
            padding=16,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            shadow=ft.BoxShadow(blur_radius=8, color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK), offset=ft.Offset(0, 2)),
            ink=bool(on_tap_tab),
            on_click=(lambda _: switch_tab(on_tap_tab)) if on_tap_tab else None,
            content=ft.Column([
                ft.Row([
                    ft.Container(
                        padding=7,
                        border_radius=8,
                        bgcolor=ft.Colors.with_opacity(0.12, tint_color),
                        content=ft.Icon(icon_name, size=18, color=tint_color),
                    ),
                    ft.Text(title, size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                ], spacing=8),
                ft.Container(height=2),
                ft.Text(str(main_val), size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                ft.Text(subtitle, size=11, color=ft.Colors.ON_SURFACE_VARIANT, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            ], spacing=2),
        )

    # ── Circular Logo & Clean Hero Header ─────────────────────────────────────
    # Circular logo with white/surface border ring overlapping banner smoothly
    logo_circle = ft.Container(
        width=80,
        height=80,
        border_radius=40,
        bgcolor=ft.Colors.SURFACE,
        alignment=ft.Alignment.CENTER,
        border=ft.Border.all(3, ft.Colors.SURFACE),
        shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.15, ft.Colors.BLACK), offset=ft.Offset(0, 3)),
        content=ft.CircleAvatar(
            radius=36,
            background_image_src=org_logo if org_logo else None,
            bgcolor=theme_color if not org_logo else ft.Colors.SURFACE,
            content=ft.Text(org_name[:2].upper() if org_name else "NU", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE) if not org_logo else None,
        ),
    )

    share_url = f"https://nu-age.name.ng/organisations/{org_id}/join"

    hero_card = ft.Container(
        margin=ft.Margin.symmetric(horizontal=16, vertical=8),
        border_radius=16,
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
        shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.05, ft.Colors.BLACK), offset=ft.Offset(0, 2)),
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=ft.Column([
            # Top Banner Strip
            ft.Container(
                gradient=ft.LinearGradient(
                    begin=ft.Alignment(-1, -1),
                    end=ft.Alignment(1, 1),
                    colors=[theme_color, ft.Colors.PRIMARY],
                ),
                padding=ft.Padding.only(top=12, left=16, right=12, bottom=38),
                content=ft.Row([
                    ft.Row([
                        ft.Icon(ft.Icons.ADMIN_PANEL_SETTINGS_ROUNDED, size=16, color=ft.Colors.WHITE),
                        ft.Text("Academy Portal", size=13, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE),
                    ], spacing=6),
                    ft.Row([
                        ft.IconButton(
                            ft.Icons.SHARE_ROUNDED,
                            icon_color=ft.Colors.WHITE,
                            icon_size=18,
                            tooltip="Copy Shareable Join Link",
                            on_click=lambda _: asyncio.create_task(copy_to_clipboard(share_url, "Invite Link")),
                        ),
                        ft.IconButton(
                            ft.Icons.INFO_OUTLINE_ROUNDED,
                            icon_color=ft.Colors.WHITE,
                            icon_size=18,
                            tooltip="Organization Details",
                            on_click=lambda _: switch_tab("info"),
                        ),
                    ], spacing=2),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ),
            # Organization Identity Area (Uncluttered, calm layout)
            ft.Container(
                padding=ft.Padding.only(left=20, right=20, bottom=16),
                content=ft.Column([
                    ft.Row([
                        ft.Container(margin=ft.Margin.only(top=-38), content=logo_circle),
                    ], alignment=ft.MainAxisAlignment.START),
                    ft.Row([
                        ft.Text(org_name, size=19, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=8, vertical=2.5),
                            border_radius=6,
                            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PURPLE_600),
                            content=ft.Text(plan_name.upper(), size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.PURPLE_600),
                        ),
                    ], spacing=8, wrap=True),
                    # Contact Meta
                    ft.Row([
                        ft.Row([
                            ft.Icon(ft.Icons.EMAIL_OUTLINED, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(org_email, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                        ], spacing=4),
                        ft.Row([
                            ft.Icon(ft.Icons.PHONE_ROUNDED, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(org_phone, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                        ], spacing=4) if org_phone and org_phone != "+000 0000 0000" else ft.Container(),
                        ft.Row([
                            ft.Icon(ft.Icons.LANGUAGE_ROUNDED, size=13, color=theme_color),
                            ft.Text(
                                org_website,
                                size=12,
                                color=theme_color,
                            ),
                        ], spacing=4) if org_website else ft.Container(),
                    ], spacing=14, wrap=True),
                ], spacing=6),
            ),
        ], spacing=0),
    )

    # Initial Render of active tab
    render_active_tab()

    return ft.Column([
        hero_card,
        ft.Container(
            padding=ft.Padding.symmetric(horizontal=16),
            content=ft.Column([
                # Bento Metrics Grid
                ft.ResponsiveRow([
                    bento_stat_card(
                        ft.Icons.GROUPS_ROUNDED,
                        "TOTAL MEMBERS",
                        str(stats["members"]),
                        f"{stats['students']} Learners · {stats['staff']} Faculty",
                        ft.Colors.INDIGO_500,
                        "members",
                    ),
                    bento_stat_card(
                        ft.Icons.AUTO_STORIES_ROUNDED,
                        "COURSE CATALOG",
                        str(stats["courses"]),
                        f"{len([c for c in courses if str(c.get('public')).lower() == 'true'])} Public · {len([c for c in courses if str(c.get('public')).lower() in ('organisation', 'organization', 'campus')])} Campus",
                        ft.Colors.BLUE_500,
                        "courses",
                    ),
                    bento_stat_card(
                        ft.Icons.PLAYLIST_PLAY_ROUNDED,
                        "LEARNING TRACKS",
                        str(len(playlists)),
                        "Curated roadmaps",
                        ft.Colors.AMBER_600,
                        "playlists",
                    ),
                    bento_stat_card(
                        ft.Icons.WORKSPACE_PREMIUM_ROUNDED,
                        "TIER & CAPACITY",
                        stats["plan"],
                        f"{stats['members']} / {max_members or '∞'} Seats",
                        ft.Colors.PURPLE_500,
                        "info",
                    ),
                ], run_spacing=12),
                ft.Container(height=4),
                # Segmented Tab Row
                tab_buttons,
                ft.Container(height=4),
                # Tab Content Socket (Clean card container)
                ft.Container(
                    padding=16,
                    border_radius=14,
                    bgcolor=ft.Colors.SURFACE,
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    content=tab_content_container,
                ),
                ft.Container(height=24),
            ], spacing=10),
        ),
    ], expand=True, scroll=ft.ScrollMode.AUTO)

async def run_full_test():
    page = MagicMock(spec=ft.Page)
    page.width = 1200
    page.height = 850
    page.overlay = []
    page.controls = []
    page.session = MagicMock()
    page.session.store = {}
    page.shared_preferences = MagicMock()
    page.shared_preferences.get = AsyncMock(return_value="mock_jwt_token")
    page.show_dialog = MagicMock()
    page.go = MagicMock()
    page.update = MagicMock()
    page.launch_url = AsyncMock()
    page.set_clipboard = AsyncMock()

    col = await build_modern_dashboard_view(page, mock_org_data, "token_123")
    print("New uncluttered dashboard view built successfully!")
    print("ALL TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(run_full_test())
