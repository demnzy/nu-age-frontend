import asyncio
import base64

import flet as ft
from src.components.bottom_appbar import get_bottom_appbar
from src.requests.organisations import (
    create_organisation,
    get_my_organisation,
    get_organisation_members,
    get_joined_organisations,  
    get_organisation_courses,
    remove_organisation_member,
)
from src.requests.Courses import create_course, get_categories
from src.requests.playlists import get_org_playlists, create_playlist
from src.utils.file_opener import show_page_snackbar

# The shared "Nu Age" account every freelance course is filed under.
# /courses now scopes TEACHER-role requests against this org_id down to
# teacher_id == the calling user server-side, so fetching "the org's courses"
# here naturally returns only this teacher's own freelance courses.
DEFAULT_ORG_ID = "584b537e-6521-4852-a7e4-18f6c095126d"


# ── shared field style ────────────────────────────────────────────────────────
_INPUT = {
    "border_color": ft.Colors.GREY_300,
    "focused_border_color": ft.Colors.PRIMARY,
    "cursor_color": ft.Colors.PRIMARY,
    "border_radius": 10,
    "width": float("inf"),
    "text_size": 13,
    "content_padding": ft.Padding.symmetric(horizontal=14, vertical=12),
}

# ── section label helper ──────────────────────────────────────────────────────
def _section_label(text: str) -> ft.Text:
    return ft.Text(text, size=11, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_600)


async def organisations_view(page: ft.Page):
    app_bar = get_bottom_appbar(page)
    token = None

    user_data = page.session.store.get("current_user") or {}
    role = user_data.get("role", "STUDENT").upper()

    # ── content socket ────────────────────────────────────────────────────────
    content_socket = ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.ProgressRing(color=ft.Colors.PRIMARY, width=36, height=36),
                ft.Text("Loading…", size=13, color=ft.Colors.GREY_500),
            ],
        ),
    )

    # ─────────────────────────────────────────────────────────────────────────
    # 1. ADMIN DASHBOARD
    # ─────────────────────────────────────────────────────────────────────────
    async def build_dashboard_view(org_data: dict):
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
            raise ValueError(
                "build_dashboard_view received org_data with no valid 'id'. "
                f"Keys present: {list(org_data.keys())}"
            )

        # Set current_org_id so that playlists and other views can use it
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

        try:
            members = await asyncio.wait_for(
                get_organisation_members(token, org_id), timeout=15
            )
            if not isinstance(members, list):
                members = []
        except asyncio.TimeoutError:
            members = []
        except Exception as ex:
            print(f"Warning: could not load members: {type(ex).__name__}: {ex}")
            members = []

        try:
            courses = await asyncio.wait_for(
                get_organisation_courses(token, org_id), timeout=15
            )
            if not isinstance(courses, list):
                courses = []
        except asyncio.TimeoutError:
            courses = []
        except Exception as ex:
            print(f"Warning: could not load courses: {type(ex).__name__}: {ex}")
            courses = []

        try:
            playlists = await asyncio.wait_for(
                get_org_playlists(token, org_id), timeout=15
            )
            if not isinstance(playlists, list):
                playlists = []
        except asyncio.TimeoutError:
            playlists = []
        except Exception as ex:
            print(f"Warning: could not load playlists: {type(ex).__name__}: {ex}")
            playlists = []

        # Local mutable copy of lists for reactive UI updates
        members = list(members)
        courses = list(courses)
        playlists = list(playlists)

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
        course_filter_category = "all"
        course_filter_instructor = "all"
        member_search_query = ""
        member_filter_role = "all"

        tab_content_container = ft.Container()

        # ── Clipboard Helper ──────────────────────────────────────────────────
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

        # ── Member Remove Action & Confirmation Dialog ────────────────────────
        def confirm_remove_member(e, uid: str, name: str, email: str):
            def close_dialog(ev=None):
                dialog.open = False
                page.update()

            def on_dialog_dismiss(ev=None):
                pass

            async def do_remove(ev=None):
                confirm_btn.disabled = True
                confirm_btn.text = "Removing…"
                page.update()

                try:
                    auth_tok = token or await page.shared_preferences.get("auth_token")
                    res = await remove_organisation_member(auth_tok, org_id, uid)
                except Exception as ex:
                    res = {"error": str(ex)}
                finally:
                    close_dialog()

                if isinstance(res, dict) and "error" in res:
                    err_msg = res["error"]
                    show_page_snackbar(
                        page,
                        ft.SnackBar(
                            content=ft.Text(f"Could not remove member: {err_msg}", color=ft.Colors.WHITE),
                            bgcolor=ft.Colors.RED_700,
                            duration=4000,
                        )
                    )
                else:
                    nonlocal members
                    members = [m for m in members if str(m.get("id", "")) != uid]
                    stats["members"] = len(members)
                    stats["staff"] = sum(1 for m in members if str(m.get("role", "")).upper() in ("TEACHER", "STAFF", "ADMIN", "OWNER"))
                    stats["students"] = sum(1 for m in members if str(m.get("role", "")).upper() == "STUDENT")
                    render_active_tab()
                    refresh_tab_headers()
                    page.update()

                    show_page_snackbar(
                        page,
                        ft.SnackBar(
                            content=ft.Row([
                                ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, color=ft.Colors.WHITE, size=18),
                                ft.Text(f"{name} was removed from {org_name}.", color=ft.Colors.WHITE, size=13),
                            ], spacing=8),
                            bgcolor=ft.Colors.GREEN_700,
                            duration=3000,
                        )
                    )

            confirm_btn = ft.TextButton("Remove", style=ft.ButtonStyle(color=ft.Colors.RED_600), on_click=do_remove)
            cancel_btn = ft.TextButton("Cancel", on_click=close_dialog)

            dialog = ft.AlertDialog(
                modal=True,
                on_dismiss=on_dialog_dismiss,
                bgcolor=ft.Colors.SURFACE,
                shape=ft.RoundedRectangleBorder(radius=16),
                title=ft.Row([
                    ft.Icon(ft.Icons.WARNING_ROUNDED, color=ft.Colors.RED_500, size=22),
                    ft.Text("Remove Member", weight=ft.FontWeight.W_700, size=16),
                ], spacing=8),
                content=ft.Container(
                    width=360,
                    content=ft.Column([
                        ft.Text(f"Are you sure you want to remove {name} from {org_name}?", size=13, color=ft.Colors.ON_SURFACE),
                        ft.Text(f"Email: {email}", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Container(height=4),
                        ft.Text("They will immediately lose access to all courses and private resources in this organization.", size=12, color=ft.Colors.RED_700),
                    ], tight=True, spacing=6),
                ),
                actions=[cancel_btn, confirm_btn],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.show_dialog(dialog)

        # ── Role Badge Color Helper ───────────────────────────────────────────
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

        # ── CREATE COURSE MODAL ───────────────────────────────────────────────
        categories_cache: list = []

        def open_create_course_modal(e=None):
            name_input = ft.TextField(
                label="Course Title *",
                hint_text="e.g. Modern Cloud Architectures",
                **_INPUT,
            )
            desc_input = ft.TextField(
                label="Short Description",
                hint_text="Overview of what students will master...",
                multiline=True,
                min_lines=2,
                max_lines=3,
                **_INPUT,
            )

            category_dropdown = ft.Dropdown(
                label="Category *",
                border_color=ft.Colors.with_opacity(0.20, ft.Colors.ON_SURFACE),
                focused_border_color=theme_color,
                border_radius=8,
                dense=True,
                text_size=13,
                menu_height=260,
                menu_style=ft.MenuStyle(
                    bgcolor=ft.Colors.SURFACE,
                    elevation=8,
                    shape=ft.RoundedRectangleBorder(radius=10),
                    side=ft.BorderSide(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                ),
                content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                width=float("inf"),
                options=[ft.dropdown.Option(c["id"], c["name"]) for c in categories_cache if isinstance(c, dict) and "id" in c and "name" in c],
                hint_text="Select a category",
            )

            # Eligible teachers from org members
            staff_options = [
                ft.dropdown.Option(
                    str(m.get("id", "")),
                    f"{m.get('first_name', '')} {m.get('last_name', '')}".strip() or m.get("email", "")
                )
                for m in members
                if str(m.get("role", "")).upper() in ("TEACHER", "STAFF", "ADMIN", "OWNER", "INSTRUCTOR")
            ]

            teacher_dropdown = ft.Dropdown(
                label="Assign Instructor (Optional)",
                border_color=ft.Colors.with_opacity(0.20, ft.Colors.ON_SURFACE),
                focused_border_color=theme_color,
                border_radius=8,
                dense=True,
                text_size=13,
                menu_height=260,
                menu_style=ft.MenuStyle(
                    bgcolor=ft.Colors.SURFACE,
                    elevation=8,
                    shape=ft.RoundedRectangleBorder(radius=10),
                    side=ft.BorderSide(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                ),
                content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                width=float("inf"),
                options=staff_options,
                hint_text="Assign a faculty member",
            )

            # Visibility: Draft (false) vs Campus (organisation) vs Public (true)
            visibility_dropdown = ft.Dropdown(
                label="Access & Visibility *",
                value="false",  # Default to Draft (Private / Unpublished) until curriculum is configured
                border_color=ft.Colors.with_opacity(0.20, ft.Colors.ON_SURFACE),
                focused_border_color=theme_color,
                border_radius=8,
                dense=True,
                text_size=13,
                menu_height=260,
                menu_style=ft.MenuStyle(
                    bgcolor=ft.Colors.SURFACE,
                    elevation=8,
                    shape=ft.RoundedRectangleBorder(radius=10),
                    side=ft.BorderSide(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                ),
                content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                width=float("inf"),
                options=[
                    ft.dropdown.Option("false", "Draft (Private / Unpublished)"),
                    ft.dropdown.Option("organisation", "Campus (Academy Members Only)"),
                    ft.dropdown.Option("true", "Public (Global Student Network)"),
                ],
            )

            auto_certificate_switch = ft.Switch(
                label="Issue Certificates Automatically",
                value=True,
                active_color=ft.Colors.GREEN_600,
            )

            # Objectives tag builder
            objectives_list = []
            objectives_chips = ft.Row(wrap=True, spacing=6)

            def add_objective(ev=None):
                val = obj_input.value.strip() if obj_input.value else ""
                if not val or val in objectives_list:
                    return
                objectives_list.append(val)

                def remove_chip(ce):
                    chip = ce.control
                    if chip.data in objectives_list:
                        objectives_list.remove(chip.data)
                    objectives_chips.controls.remove(chip)
                    page.update()

                objectives_chips.controls.append(
                    ft.Chip(
                        label=ft.Text(val, size=11),
                        data=val,
                        delete_icon=ft.Icon(ft.Icons.CANCEL, size=13),
                        on_delete=remove_chip,
                    )
                )
                obj_input.value = ""
                page.update()

            obj_input = ft.TextField(
                label="Course Objectives",
                hint_text="Type learning objective & press Enter",
                on_submit=add_objective,
                suffix=ft.IconButton(
                    ft.Icons.ADD_CIRCLE_OUTLINE_ROUNDED,
                    icon_color=theme_color,
                    icon_size=18,
                    on_click=add_objective,
                ),
                **_INPUT,
            )

            # Cover Image Picker
            selected_logo_bytes = None
            selected_logo_name = None
            logo_icon = ft.Icon(ft.Icons.CLOUD_UPLOAD_OUTLINED, color=theme_color, size=24)
            logo_text = ft.Text("Upload Course Cover (Optional)", color=ft.Colors.GREY_500, size=12)

            async def handle_cover_pick(ev=None):
                nonlocal selected_logo_bytes, selected_logo_name
                try:
                    files = await ft.FilePicker().pick_files(
                        allow_multiple=False,
                        file_type=ft.FilePickerFileType.IMAGE,
                        with_data=True,
                    )
                    if files:
                        selected = files[0]
                        selected_logo_bytes = selected.bytes
                        selected_logo_name = selected.name
                        logo_icon.name = ft.Icons.CHECK_CIRCLE_ROUNDED
                        logo_icon.color = ft.Colors.GREEN_600
                        logo_text.value = f"Selected: {selected_logo_name}"
                        logo_text.color = ft.Colors.GREEN_600
                        page.update()
                except Exception as pex:
                    print(f"Picker error: {pex}")

            cover_picker_container = ft.Container(
                width=float("inf"),
                padding=ft.Padding.symmetric(vertical=14, horizontal=16),
                border=ft.Border.all(1, ft.Colors.GREY_300),
                border_radius=10,
                ink=True,
                on_click=lambda _: page.run_task(handle_cover_pick),
                content=ft.Row([logo_icon, logo_text], spacing=10, alignment=ft.MainAxisAlignment.CENTER),
            )

            error_text = ft.Text("", color=ft.Colors.RED_700, size=12, visible=False, weight=ft.FontWeight.W_500)

            def close_course_modal(ev=None):
                course_dialog.open = False
                page.update()

            async def submit_new_course(ev=None):
                nonlocal selected_logo_bytes, selected_logo_name
                t_val = name_input.value.strip() if name_input.value else ""
                if not t_val:
                    error_text.value = "Course Title is required."
                    error_text.visible = True
                    page.update()
                    return

                if not category_dropdown.value:
                    error_text.value = "Category is required."
                    error_text.visible = True
                    page.update()
                    return

                error_text.visible = False
                submit_btn.disabled = True
                submit_btn.content = ft.Row([
                    ft.ProgressRing(width=14, height=14, color=ft.Colors.WHITE, stroke_width=2),
                    ft.Text("Creating Course…", color=ft.Colors.WHITE, size=12, weight=ft.FontWeight.W_600),
                ], tight=True, spacing=8)
                page.update()

                try:
                    logo_b64 = (
                        base64.b64encode(selected_logo_bytes).decode("utf-8")
                        if selected_logo_bytes else None
                    )
                    payload = {
                        "name": t_val,
                        "category_id": category_dropdown.value,
                        "description": desc_input.value.strip() if desc_input.value else t_val,
                        "public": visibility_dropdown.value if visibility_dropdown.value else "false",
                        "objectives": objectives_list,
                        "image_bytes": logo_b64,
                        "image_filename": selected_logo_name,
                        "org_id": org_id,
                        "is_freelance": False,
                        "teacher_id": teacher_dropdown.value or None,
                        "auto_certificate": auto_certificate_switch.value,
                    }

                    auth_tok = token or await page.shared_preferences.get("auth_token")
                    new_course = await asyncio.wait_for(
                        create_course(auth_tok, payload), timeout=25
                    )

                    if isinstance(new_course, dict) and "id" in new_course:
                        courses.insert(0, new_course)
                        stats["courses"] = len(courses)
                        render_active_tab()
                        refresh_tab_headers()
                        close_course_modal()
                        page.update()

                        cid = new_course.get("id")
                        show_page_snackbar(
                            page,
                            ft.SnackBar(
                                content=ft.Row([
                                    ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.WHITE, size=18),
                                    ft.Text(f"Course '{t_val}' created!", color=ft.Colors.WHITE, size=13),
                                ], spacing=8),
                                action="Build Curriculum",
                                on_action=lambda _: page.go(f"/courses/{cid}/manage"),
                                bgcolor=ft.Colors.GREEN_700,
                                duration=5000,
                            )
                        )
                    else:
                        err = new_course.get("error", "Failed to create course") if isinstance(new_course, dict) else "Unknown server error"
                        error_text.value = f"Could not create course: {err}"
                        error_text.visible = True
                        submit_btn.disabled = False
                        submit_btn.content = ft.Text("Create Course", color=ft.Colors.WHITE, size=13, weight=ft.FontWeight.BOLD)
                        page.update()
                except Exception as ex:
                    error_text.value = f"Error: {ex}"
                    error_text.visible = True
                    submit_btn.disabled = False
                    submit_btn.content = ft.Text("Create Course", color=ft.Colors.WHITE, size=13, weight=ft.FontWeight.BOLD)
                    page.update()

            submit_btn = ft.FilledButton(
                "Create Course",
                style=ft.ButtonStyle(bgcolor=theme_color, shape=ft.RoundedRectangleBorder(radius=10)),
                on_click=lambda _: page.run_task(submit_new_course),
            )
            cancel_btn = ft.TextButton("Cancel", on_click=close_course_modal)

            course_dialog = ft.AlertDialog(
                modal=True,
                bgcolor=ft.Colors.SURFACE,
                shape=ft.RoundedRectangleBorder(radius=16),
                title=ft.Row([
                    ft.Icon(ft.Icons.AUTO_STORIES_ROUNDED, color=theme_color, size=22),
                    ft.Text("Create New Course", weight=ft.FontWeight.BOLD, size=16),
                ], spacing=8),
                content=ft.Container(
                    width=min(getattr(page, "width", 540) - 32, 540) if hasattr(page, "width") and page.width else 500,
                    content=ft.Column([
                        name_input,
                        category_dropdown,
                        visibility_dropdown,
                        teacher_dropdown,
                        desc_input,
                        auto_certificate_switch,
                        obj_input,
                        objectives_chips,
                        cover_picker_container,
                        error_text,
                    ], tight=True, spacing=10, scroll=ft.ScrollMode.AUTO),
                ),
                actions=[cancel_btn, submit_btn],
                actions_alignment=ft.MainAxisAlignment.END,
            )

            # Lazy load categories if empty
            async def load_categories_and_show():
                nonlocal categories_cache
                if not categories_cache:
                    try:
                        auth_tok = token or await page.shared_preferences.get("auth_token")
                        cats = await get_categories(auth_tok)
                        if isinstance(cats, list):
                            categories_cache = cats
                            category_dropdown.options = [
                                ft.dropdown.Option(c["id"], c["name"])
                                for c in categories_cache if isinstance(c, dict) and "id" in c and "name" in c
                            ]
                    except Exception as cex:
                        print(f"Failed to fetch categories: {cex}")
                page.show_dialog(course_dialog)
                page.update()

            page.run_task(load_categories_and_show)

        # ── CREATE PLAYLIST MODAL ─────────────────────────────────────────────
        def open_create_playlist_modal(e=None):
            name_input = ft.TextField(
                label="Learning Path Title *",
                hint_text="e.g. Fullstack Cloud Track",
                **_INPUT,
            )
            desc_input = ft.TextField(
                label="Short Description",
                hint_text="Curated roadmap to master this track...",
                multiline=True,
                min_lines=2,
                max_lines=3,
                **_INPUT,
            )
            public_switch = ft.Switch(
                label="Public Track (Catalog Visibility)",
                value=True,
                active_color=theme_color,
            )

            selected_logo_bytes = None
            selected_logo_name = None
            logo_icon = ft.Icon(ft.Icons.CLOUD_UPLOAD_OUTLINED, color=theme_color, size=24)
            logo_text = ft.Text("Upload Track Cover (Optional)", color=ft.Colors.GREY_500, size=12)

            async def handle_cover_pick(ev=None):
                nonlocal selected_logo_bytes, selected_logo_name
                try:
                    files = await ft.FilePicker().pick_files(
                        allow_multiple=False,
                        file_type=ft.FilePickerFileType.IMAGE,
                        with_data=True,
                    )
                    if files:
                        selected = files[0]
                        selected_logo_bytes = selected.bytes
                        selected_logo_name = selected.name
                        logo_icon.name = ft.Icons.CHECK_CIRCLE_ROUNDED
                        logo_icon.color = ft.Colors.GREEN_600
                        logo_text.value = f"Selected: {selected_logo_name}"
                        logo_text.color = ft.Colors.GREEN_600
                        page.update()
                except Exception as pex:
                    print(f"Picker error: {pex}")

            cover_picker_container = ft.Container(
                width=float("inf"),
                padding=ft.Padding.symmetric(vertical=14, horizontal=16),
                border=ft.Border.all(1, ft.Colors.GREY_300),
                border_radius=10,
                ink=True,
                on_click=lambda _: page.run_task(handle_cover_pick),
                content=ft.Row([logo_icon, logo_text], spacing=10, alignment=ft.MainAxisAlignment.CENTER),
            )

            error_text = ft.Text("", color=ft.Colors.RED_700, size=12, visible=False, weight=ft.FontWeight.W_500)

            def close_pl_modal(ev=None):
                playlist_dialog.open = False
                page.update()

            async def submit_new_playlist(ev=None):
                nonlocal selected_logo_bytes, selected_logo_name
                t_val = name_input.value.strip() if name_input.value else ""
                if not t_val:
                    error_text.value = "Learning Track Title is required."
                    error_text.visible = True
                    page.update()
                    return

                error_text.visible = False
                submit_btn.disabled = True
                submit_btn.content = ft.Row([
                    ft.ProgressRing(width=14, height=14, color=ft.Colors.WHITE, stroke_width=2),
                    ft.Text("Creating Track…", color=ft.Colors.WHITE, size=12, weight=ft.FontWeight.W_600),
                ], tight=True, spacing=8)
                page.update()

                try:
                    logo_b64 = (
                        base64.b64encode(selected_logo_bytes).decode("utf-8")
                        if selected_logo_bytes else None
                    )
                    payload = {
                        "name": t_val,
                        "description": desc_input.value.strip() if desc_input.value else t_val,
                        "is_public": public_switch.value,
                        "image_bytes": logo_b64,
                        "image_filename": selected_logo_name,
                        "org_id": org_id,
                    }

                    auth_tok = token or await page.shared_preferences.get("auth_token")
                    new_pl = await asyncio.wait_for(
                        create_playlist(auth_tok, payload), timeout=25
                    )

                    if isinstance(new_pl, dict) and "id" in new_pl:
                        playlists.insert(0, new_pl)
                        stats["playlists"] = len(playlists)
                        render_active_tab()
                        refresh_tab_headers()
                        close_pl_modal()
                        page.update()

                        pid = new_pl.get("id")
                        show_page_snackbar(
                            page,
                            ft.SnackBar(
                                content=ft.Row([
                                    ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.WHITE, size=18),
                                    ft.Text(f"Learning Track '{t_val}' created!", color=ft.Colors.WHITE, size=13),
                                ], spacing=8),
                                action="Build Track",
                                on_action=lambda _: page.go(f"/playlists/{pid}/build"),
                                bgcolor=ft.Colors.GREEN_700,
                                duration=5000,
                            )
                        )
                    else:
                        err = new_pl.get("error", "Failed to create track") if isinstance(new_pl, dict) else "Unknown error"
                        error_text.value = f"Could not create track: {err}"
                        error_text.visible = True
                        submit_btn.disabled = False
                        submit_btn.content = ft.Text("Create Path", color=ft.Colors.WHITE, size=13, weight=ft.FontWeight.BOLD)
                        page.update()
                except Exception as ex:
                    error_text.value = f"Error: {ex}"
                    error_text.visible = True
                    submit_btn.disabled = False
                    submit_btn.content = ft.Text("Create Path", color=ft.Colors.WHITE, size=13, weight=ft.FontWeight.BOLD)
                    page.update()

            submit_btn = ft.FilledButton(
                "Create Path",
                style=ft.ButtonStyle(bgcolor=theme_color, shape=ft.RoundedRectangleBorder(radius=10)),
                on_click=lambda _: page.run_task(submit_new_playlist),
            )
            cancel_btn = ft.TextButton("Cancel", on_click=close_pl_modal)

            playlist_dialog = ft.AlertDialog(
                modal=True,
                bgcolor=ft.Colors.SURFACE,
                shape=ft.RoundedRectangleBorder(radius=16),
                title=ft.Row([
                    ft.Icon(ft.Icons.PLAYLIST_PLAY_ROUNDED, color=theme_color, size=22),
                    ft.Text("Create Learning Path", weight=ft.FontWeight.BOLD, size=16),
                ], spacing=8),
                content=ft.Container(
                    width=min(getattr(page, "width", 500) - 32, 480) if hasattr(page, "width") and page.width else 440,
                    content=ft.Column([
                        name_input,
                        desc_input,
                        public_switch,
                        cover_picker_container,
                        error_text,
                    ], tight=True, spacing=10),
                ),
                actions=[cancel_btn, submit_btn],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.show_dialog(playlist_dialog)
            page.update()

        # ── Filter Bottom Sheet (Drawer) ──────────────────────────────────────
        def build_filter_sheet(title, options, active_val, on_select):
            sheet = None

            def handle_select(e):
                on_select(e.control.value)
                if sheet:
                    sheet.open = False
                page.update()

            def handle_reset(e):
                on_select(None)
                if sheet:
                    sheet.open = False
                page.update()

            def close_sheet(e=None):
                if sheet:
                    sheet.open = False
                    page.update()

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
                        ft.Row([
                            ft.Text(title, size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                            ft.IconButton(
                                ft.Icons.CLOSE_ROUNDED,
                                icon_size=20,
                                on_click=close_sheet,
                            ),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Divider(),
                        ft.Container(content=rg, expand=True),
                        ft.Divider(),
                        ft.TextButton("Reset Filter", icon=ft.Icons.REFRESH, on_click=handle_reset),
                    ]),
                )
            )
            return sheet

        # ── TAB 1: Courses & Curricula ─────────────────────────────────────────
        def render_courses_tab():
            def get_filtered_courses():
                res = courses
                if course_search_query.strip():
                    q = course_search_query.strip().lower()
                    res = [c for c in res if q in c.get("name", "").lower() or q in c.get("description", "").lower()]

                if course_filter_status == "public":
                    res = [c for c in res if str(c.get("public", "")).lower() == "true"]
                elif course_filter_status == "campus":
                    res = [c for c in res if str(c.get("public", "")).lower() in ("organisation", "organization", "campus")]
                elif course_filter_status == "draft":
                    res = [c for c in res if str(c.get("public", "")).lower() not in ("true", "organisation", "organization", "campus")]

                if course_filter_category != "all":
                    res = [
                        c for c in res
                        if (isinstance(c.get("category"), dict) and c.get("category", {}).get("name") == course_filter_category)
                        or (isinstance(c.get("category"), str) and c.get("category") == course_filter_category)
                        or (str(c.get("category_id")) == course_filter_category)
                    ]

                if course_filter_instructor != "all":
                    def match_teacher(c):
                        t_id = str(c.get("teacher_id", ""))
                        for m in members:
                            m_id = str(m.get("id", ""))
                            m_name = f"{m.get('first_name', '')} {m.get('last_name', '')}".strip() or m.get("email", "")
                            if (m_id == t_id or m_id == str(c.get("admin_id", ""))) and m_name == course_filter_instructor:
                                return True
                        t_info = c.get("teacher")
                        if isinstance(t_info, dict):
                            t_name = f"{t_info.get('first_name', '')} {t_info.get('last_name', '')}".strip() or t_info.get("email", "")
                            if t_name == course_filter_instructor:
                                return True
                        return False

                    res = [c for c in res if match_teacher(c)]
                return res

            def on_search_change(e):
                nonlocal course_search_query
                course_search_query = e.control.value or ""
                content_list.controls = build_course_items(get_filtered_courses())
                content_list.update()

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

            def create_drawer_chip(label_text, on_click, is_active=False):
                return ft.Container(
                    content=ft.Row([
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
                    ], spacing=2, tight=True),
                    padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                    border_radius=18,
                    bgcolor=theme_color if is_active else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                    on_click=on_click,
                    ink=True,
                )

            def open_category_filter(e=None):
                cats = []
                seen_cat_names = set()
                for cat in categories_cache:
                    if isinstance(cat, dict) and cat.get("name") and cat["name"] not in seen_cat_names:
                        seen_cat_names.add(cat["name"])
                        cats.append(cat["name"])
                for c in courses:
                    cat_info = c.get("category")
                    c_name = cat_info.get("name") if isinstance(cat_info, dict) else (cat_info if isinstance(cat_info, str) else None)
                    if c_name and c_name not in seen_cat_names:
                        seen_cat_names.add(c_name)
                        cats.append(c_name)
                cats.sort()
                sheet = build_filter_sheet("Filter by Category", cats, course_filter_category if course_filter_category != "all" else None, set_category_filter)
                page.show_dialog(sheet)

            def set_category_filter(val):
                nonlocal course_filter_category
                course_filter_category = val if val else "all"
                render_active_tab()
                page.update()

            def open_instructor_filter(e=None):
                insts = []
                seen_insts = set()
                for m in members:
                    role = str(m.get("role", "")).upper()
                    if role in ("TEACHER", "STAFF", "ADMIN", "OWNER", "INSTRUCTOR"):
                        name = f"{m.get('first_name', '')} {m.get('last_name', '')}".strip() or m.get("email", "")
                        if name and name not in seen_insts:
                            seen_insts.add(name)
                            insts.append(name)
                for c in courses:
                    t_info = c.get("teacher")
                    if isinstance(t_info, dict):
                        t_name = f"{t_info.get('first_name', '')} {t_info.get('last_name', '')}".strip() or t_info.get("email", "")
                        if t_name and t_name not in seen_insts:
                            seen_insts.add(t_name)
                            insts.append(t_name)
                insts.sort()
                sheet = build_filter_sheet("Filter by Instructor", insts, course_filter_instructor if course_filter_instructor != "all" else None, set_instructor_filter)
                page.show_dialog(sheet)

            def set_instructor_filter(val):
                nonlocal course_filter_instructor
                course_filter_instructor = val if val else "all"
                render_active_tab()
                page.update()

            cat_chip = create_drawer_chip(
                f"Category: {course_filter_category}" if course_filter_category != "all" else "Category",
                open_category_filter,
                is_active=(course_filter_category != "all"),
            )

            inst_chip = create_drawer_chip(
                f"Instructor: {course_filter_instructor}" if course_filter_instructor != "all" else "Instructor",
                open_instructor_filter,
                is_active=(course_filter_instructor != "all"),
            )

            filter_bar = ft.Row([
                filter_chip("All", "all"),
                filter_chip("Public", "public"),
                filter_chip("Campus", "campus"),
                filter_chip("Drafts", "draft"),
                cat_chip,
                inst_chip,
            ], spacing=8, scroll=ft.ScrollMode.AUTO)

            search_box = ft.TextField(
                hint_text="Search courses by title or description…",
                prefix_icon=ft.Icons.SEARCH_ROUNDED,
                border_radius=10,
                dense=True,
                content_padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                on_change=on_search_change,
                value=course_search_query,
                width=float("inf"),
            )

            def build_course_items(c_list):
                items = []
                for c in c_list:
                    c_id = c.get("id", "")
                    title = c.get("name", "Untitled Course")
                    desc = c.get("description", "No description provided.")
                    img = c.get("image_url")
                    pub_val = str(c.get("public", "false")).lower()
                    students_cnt = c.get("total_students", 0)

                    # Badges: Public / Campus / Draft
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
                                                ft.Icons.BAR_CHART_ROUNDED,
                                                tooltip="Course Analytics",
                                                icon_size=17,
                                                icon_color=ft.Colors.ON_SURFACE_VARIANT,
                                                on_click=lambda _, cid=c_id: page.go(f"/organisations/{org_id}/courses/{cid}/analytics"),
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
                    items.append(ft.Container(col={"xs": 12, "sm": 6, "lg": 4}, content=card))

                if items:
                    return items
                return [
                    ft.Container(
                        col={"xs": 12},
                        padding=40,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Column([
                            ft.Icon(ft.Icons.AUTO_STORIES_OUTLINED, size=44, color=ft.Colors.with_opacity(0.3, ft.Colors.ON_SURFACE)),
                            ft.Text("No courses found matching your criteria.", size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.FilledButton(
                                "Create Course",
                                icon=ft.Icons.ADD_ROUNDED,
                                style=ft.ButtonStyle(
                                    bgcolor=theme_color,
                                    shape=ft.RoundedRectangleBorder(radius=10),
                                    padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                                ),
                                on_click=lambda _: open_create_course_modal(),
                            ),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                    )
                ]

            content_list = ft.ResponsiveRow(controls=build_course_items(get_filtered_courses()), run_spacing=14)

            return ft.Column([
                # Section Title & Primary Action (Responsive: expand=True prevents button bleeding off screen on mobile)
                ft.Row([
                    ft.Column([
                        ft.Text("Courses & Curricula", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(f"{len(courses)} published courses in academy library", size=11, color=ft.Colors.ON_SURFACE_VARIANT, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=1, expand=True),
                    ft.FilledButton(
                        "New Course",
                        icon=ft.Icons.ADD_ROUNDED,
                        style=ft.ButtonStyle(
                            bgcolor=theme_color,
                            shape=ft.RoundedRectangleBorder(radius=10),
                            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                        ),
                        on_click=lambda _: open_create_course_modal(),
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                search_box,
                filter_bar,
                content_list,
            ], spacing=14)

        # ── TAB 2: Members & Staff ─────────────────────────────────────────────
        def render_members_tab():
            def get_filtered_members():
                res = members
                if member_search_query.strip():
                    q = member_search_query.strip().lower()
                    res = [m for m in res if q in f"{m.get('first_name', '')} {m.get('last_name', '')}".lower() or q in m.get("email", "").lower()]

                if member_filter_role == "staff":
                    res = [m for m in res if str(m.get("role", "")).upper() in ("TEACHER", "STAFF", "ADMIN", "OWNER")]
                elif member_filter_role == "students":
                    res = [m for m in res if str(m.get("role", "")).upper() == "STUDENT"]
                return res

            def on_search_change(e):
                nonlocal member_search_query
                member_search_query = e.control.value or ""
                member_list.controls = build_member_cards(get_filtered_members())
                member_list.update()

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
                width=float("inf"),
            )

            def build_member_cards(m_list):
                cards = []
                for m in m_list:
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
                    if not is_owner:
                        menu_items.append(
                            ft.PopupMenuItem(
                                content=ft.Text("Remove Member", size=13, color=ft.Colors.RED_600),
                                icon=ft.Icons.PERSON_REMOVE_OUTLINED,
                                on_click=lambda _, uid=u_id, n=full_name, em=email: confirm_remove_member(_, uid, n, em),
                            )
                        )

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
                    cards.append(row)

                if cards:
                    return cards
                return [
                    ft.Container(
                        padding=40,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Column([
                            ft.Icon(ft.Icons.GROUPS_ROUNDED, size=44, color=ft.Colors.with_opacity(0.3, ft.Colors.ON_SURFACE)),
                            ft.Text("No members match your search.", size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.FilledButton(
                                "Invite Members",
                                icon=ft.Icons.PERSON_ADD_ROUNDED,
                                style=ft.ButtonStyle(
                                    bgcolor=theme_color,
                                    shape=ft.RoundedRectangleBorder(radius=10),
                                    padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                                ),
                                on_click=lambda _: page.go(f"/organisations/{org_id}/invite-members"),
                            ),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                    )
                ]

            member_list = ft.Column(controls=build_member_cards(get_filtered_members()), spacing=8)

            return ft.Column([
                # Section Title & Primary Action (Responsive: expand=True prevents button bleeding off screen on mobile)
                ft.Row([
                    ft.Column([
                        ft.Text("Members & Faculty", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(f"{len(members)} total community members enrolled", size=11, color=ft.Colors.ON_SURFACE_VARIANT, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=1, expand=True),
                    ft.FilledButton(
                        "Invite Member",
                        icon=ft.Icons.PERSON_ADD_ROUNDED,
                        style=ft.ButtonStyle(
                            bgcolor=theme_color,
                            shape=ft.RoundedRectangleBorder(radius=10),
                            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                        ),
                        on_click=lambda _: page.go(f"/organisations/{org_id}/invite-members"),
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                search_box,
                filter_bar,
                member_list,
            ], spacing=14)

        # ── TAB 3: Learning Paths (Playlists) ─────────────────────────────────
        def render_playlists_tab():
            playlist_items = []
            for p in playlists:
                p_id = p.get("id", "")
                title = p.get("name", "Learning Track")
                desc = p.get("description", "Curated roadmap for mastering core competencies.")
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
                                            ft.Icons.EDIT_ROAD_ROUNDED,
                                            tooltip="Manage Roadmap",
                                            icon_size=17,
                                            icon_color=theme_color,
                                            on_click=lambda _, pid=p_id: page.go(f"/playlists/{pid}/build"),
                                        ),
                                        ft.IconButton(
                                            ft.Icons.BAR_CHART_ROUNDED,
                                            tooltip="Pathway Analytics",
                                            icon_size=17,
                                            icon_color=ft.Colors.ON_SURFACE_VARIANT,
                                            on_click=lambda _, pid=p_id: page.go(f"/organisations/{org_id}/playlists/{pid}/analytics"),
                                        ),
                                        ft.IconButton(
                                            ft.Icons.SETTINGS_OUTLINED,
                                            tooltip="Playlist Settings",
                                            icon_size=17,
                                            icon_color=ft.Colors.ON_SURFACE_VARIANT,
                                            on_click=lambda _, pid=p_id: page.go(f"/playlists/{pid}/settings"),
                                        ),
                                        ft.IconButton(
                                            ft.Icons.VISIBILITY_OUTLINED,
                                            tooltip="View Learning Path",
                                            icon_size=17,
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
                    ft.FilledButton(
                        "Create Learning Path",
                        icon=ft.Icons.ADD_ROUNDED,
                        style=ft.ButtonStyle(
                            bgcolor=theme_color,
                            shape=ft.RoundedRectangleBorder(radius=10),
                            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                        ),
                        on_click=lambda _: open_create_playlist_modal(),
                    ),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
            )

            return ft.Column([
                # Section Title & Primary Action (Responsive: expand=True prevents button bleeding off screen on mobile)
                ft.Row([
                    ft.Column([
                        ft.Text("Curated Learning Paths", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(f"{len(playlists)} guided tracks configured", size=11, color=ft.Colors.ON_SURFACE_VARIANT, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                    ], spacing=1, expand=True),
                    ft.FilledButton(
                        "New Path",
                        icon=ft.Icons.ADD_ROUNDED,
                        style=ft.ButtonStyle(
                            bgcolor=theme_color,
                            shape=ft.RoundedRectangleBorder(radius=10),
                            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                        ),
                        on_click=lambda _: open_create_playlist_modal(),
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                content_list,
            ], spacing=14)

        # ── TAB 4: Organization Details ───────────────────────────────────────
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

        # ── Active Tab Dispatcher ─────────────────────────────────────────────
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

        # ── Bento Stat Card Component ─────────────────────────────────────────
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

        # ── Circular Logo & Clean Hero Header ─────────────────────────────────
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

        # Preload categories in background
        async def preload_categories():
            nonlocal categories_cache
            try:
                auth_tok = token or await page.shared_preferences.get("auth_token")
                cats = await get_categories(auth_tok)
                if isinstance(cats, list) and cats:
                    categories_cache = cats
                    render_active_tab()
                    page.update()
            except Exception as e:
                print(f"Preload categories error: {e}")

        page.run_task(preload_categories)

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

    # ─────────────────────────────────────────────────────────────────────────
    # 2. CREATE FORM
    # ─────────────────────────────────────────────────────────────────────────
    def build_create_form_view():
        name_input    = ft.TextField(label="Organisation Name *",  **_INPUT)
        email_input   = ft.TextField(label="Contact Email *",      keyboard_type=ft.KeyboardType.EMAIL,  **_INPUT)
        number_input  = ft.TextField(label="Phone Number *",       keyboard_type=ft.KeyboardType.PHONE,  **_INPUT)
        website_input = ft.TextField(label="Website (Optional)",   keyboard_type=ft.KeyboardType.URL,    **_INPUT)
        address_input = ft.TextField(label="Physical Address *",   multiline=True, min_lines=2, max_lines=4, **_INPUT)
        error_text    = ft.Text("", color=ft.Colors.RED_700, size=12, visible=False, weight=ft.FontWeight.W_500)

        selected_logo_bytes = None
        selected_logo_name  = None

        logo_icon = ft.Icon(ft.Icons.CLOUD_UPLOAD_OUTLINED, color=ft.Colors.PRIMARY, size=28)
        logo_text = ft.Text("Upload Logo (Optional)", color=ft.Colors.GREY_500, size=13)

        curated_themes = [
            ft.Colors.PRIMARY, ft.Colors.BLUE_500, ft.Colors.TEAL_500,
            ft.Colors.GREEN_500, ft.Colors.ORANGE_500, ft.Colors.RED_500, ft.Colors.PURPLE_500,
        ]
        selected_theme_color = curated_themes[0]

        def handle_color_select(e):
            nonlocal selected_theme_color
            selected_theme_color = e.control.data
            for swatch in color_swatches_row.controls:
                swatch.border = (
                    ft.Border.all(3, ft.Colors.ON_SURFACE)
                    if swatch.data == selected_theme_color
                    else None
                )
            page.update()

        color_swatches_row = ft.Row(
            spacing=10,
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=32, height=32, border_radius=16,
                    bgcolor=color, data=color, ink=True,
                    on_click=handle_color_select,
                    border=ft.Border.all(3, ft.Colors.ON_SURFACE) if color == selected_theme_color else None,
                )
                for color in curated_themes
            ],
        )

        # ==========================================
# 1. THE SETUP (Put this in your main page setup, NOT inside the button click)
# ==========================================

# This function automatically wakes up when the user finishes picking an image
# Do NOT append anything to page.overlay

        async def handle_logo_pick(e):
            nonlocal selected_logo_bytes, selected_logo_name
            try:
                # 1. Instantiate the Service natively inside the function
                file_picker = ft.FilePicker()
                
                # 2. Await it directly! This pauses execution until the user selects an image.
                # In 0.84.0, this returns a list of FilePickerFile objects directly.
                files = await file_picker.pick_files(
                    allow_multiple=False,
                    file_type=ft.FilePickerFileType.IMAGE,
                    with_data=True, 
                )
                
                # 3. Process the files 
                if files and len(files) > 0:
                    selected = files[0] # Notice it is just files[0], not files.files
                    
                    # Because you used with_data=True, the raw bytes are already here!
                    selected_logo_bytes = selected.bytes 
                    selected_logo_name  = selected.name
                    
                    # Update UI
                    logo_icon.name  = ft.Icons.CHECK_CIRCLE_ROUNDED
                    logo_icon.color = ft.Colors.GREEN_600
                    logo_text.value = f"Selected: {selected_logo_name}"
                    logo_text.color = ft.Colors.GREEN_600
                    page.update()
                    
            except Exception as ex:
                print(f"FilePicker error: {type(ex).__name__}: {ex}")
                logo_text.value = "Could not open file picker. Try again."
                logo_text.color = ft.Colors.RED_700
                page.update()
        async def handle_submit(e):
            nonlocal selected_logo_bytes, selected_logo_name
            if not all([name_input.value, email_input.value, number_input.value, address_input.value]):
                error_text.value   = "Please fill in all required fields (*)."
                error_text.visible = True
                page.update()
                return

            error_text.visible = False
            submit_btn.disabled = True
            submit_btn.content = ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    ft.ProgressRing(width=16, height=16, color=ft.Colors.WHITE, stroke_width=2),
                    ft.Text("Creating…", color=ft.Colors.WHITE, weight=ft.FontWeight.W_600, size=14),
                ],
            )
            page.update()

            try:
                logo_b64 = (
                    base64.b64encode(selected_logo_bytes).decode("utf-8")
                    if selected_logo_bytes else None
                )
                payload = {
                    "name":          name_input.value.strip(),
                    "email":         email_input.value.strip(),
                    "number":        number_input.value.strip(),
                    "website":       f"https://{website_input.value.strip()}" if website_input.value else None,
                    "address":       address_input.value.strip(),
                    "logo_bytes":    logo_b64,
                    "logo_filename": selected_logo_name,
                    "theme_color":   selected_theme_color,
                }

                tok = await page.shared_preferences.get("auth_token")

                # Step 1: Create the org
                new_org = await asyncio.wait_for(
                    create_organisation(tok, payload), timeout=20
                )

                if not isinstance(new_org, dict) or not new_org.get("id"):
                    raise ValueError(f"Unexpected response from server: {new_org}")

                # Step 2: Fetch full org data from /me (includes stats, plan, members, courses)
                full_org_data = await asyncio.wait_for(
                    get_my_organisation(tok), timeout=15
                )

                if not full_org_data:
                    raise ValueError("Organisation created but could not load dashboard data.")

                await show_dashboard(full_org_data)

            except asyncio.TimeoutError:
                error_text.value   = "Request timed out. Please check your connection and try again."
                error_text.visible = True
                submit_btn.disabled = False
                submit_btn.content = ft.Text("Create Organisation", color=ft.Colors.WHITE, weight=ft.FontWeight.W_600, size=14)
                page.update()

            except Exception as ex:
                error_text.value   = f"Something went wrong: {type(ex).__name__}: {str(ex)}"
                error_text.visible = True
                submit_btn.disabled = False
                submit_btn.content = ft.Text("Create Organisation", color=ft.Colors.WHITE, weight=ft.FontWeight.W_600, size=14)
                page.update()

        submit_btn = ft.ElevatedButton(
            content=ft.Text("Create Organisation", color=ft.Colors.WHITE, weight=ft.FontWeight.W_600, size=14),
            bgcolor=ft.Colors.PRIMARY,
            height=48,
            expand=True,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                elevation=0,
            ),
            on_click=handle_submit,
        )

        return ft.Container(
            expand=True,
            bgcolor=ft.Colors.SURFACE,
            content=ft.Column(
                scroll=ft.ScrollMode.AUTO,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=[
                    # ── Top bar ───────────────────────────────────────────────
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.IconButton(
                                    ft.Icons.ARROW_BACK_ROUNDED,
                                    icon_color=ft.Colors.ON_SURFACE,
                                    on_click=lambda _: show_promo_view(),
                                ),
                                ft.Text("New Organisation", size=18, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                                ft.Container(width=40),
                            ],
                        ),
                    ),
                    ft.Divider(height=1, color=ft.Colors.GREY_100),

                    # ── Form fields ───────────────────────────────────────────
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=20, vertical=16),
                        content=ft.Column(
                            spacing=14,
                            controls=[
                                _section_label("BASIC INFORMATION"),
                                name_input, email_input, number_input,
                                website_input,

                                _section_label("ADDRESS"),
                                address_input,

                                _section_label("LOGO"),
                                ft.Container(
                                    width=float("inf"),
                                    padding=ft.Padding.symmetric(vertical=18, horizontal=12),
                                    border=ft.Border.all(1, ft.Colors.GREY_300),
                                    border_radius=10,
                                    ink=True,
                                    on_click=handle_logo_pick,
                                    content=ft.Column(
                                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                        spacing=6,
                                        controls=[logo_icon, logo_text],
                                    ),
                                ),

                                _section_label("BRAND COLOUR"),
                                ft.Container(
                                    width=float("inf"),
                                    padding=ft.Padding.symmetric(vertical=14, horizontal=12),
                                    border=ft.Border.all(1, ft.Colors.GREY_300),
                                    border_radius=10,
                                    content=ft.Column(
                                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                        spacing=10,
                                        controls=[
                                            ft.Text("Select a colour for your workspace", size=12, color=ft.Colors.GREY_500),
                                            color_swatches_row,
                                        ],
                                    ),
                                ),

                                error_text,
                                ft.Row(controls=[submit_btn]),
                                ft.Container(height=24),
                            ],
                        ),
                    ),
                ],
            ),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 3. PROMO / ZERO STATE
    # ─────────────────────────────────────────────────────────────────────────
    def build_promo_view():
        return ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            padding=30,
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=0,
                controls=[
                    ft.Container(
                        width=110, height=110,
                        bgcolor=ft.Colors.PRIMARY,
                        border_radius=55,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(ft.Icons.BUSINESS_ROUNDED, size=52, color=ft.Colors.WHITE),
                    ),
                    ft.Container(height=24),
                    ft.Text(
                        "Scale Your Teaching",
                        size=26, weight=ft.FontWeight.W_700,
                        color=ft.Colors.ON_SURFACE,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=10),
                    ft.Text(
                        "Create a centralised hub to manage your instructors,\npublish courses, and monitor student progress.",
                        size=14, color=ft.Colors.GREY_500,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=32),
                    ft.ElevatedButton(
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.CENTER,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.ADD_ROUNDED, color=ft.Colors.WHITE, size=20),
                                ft.Text("Create Organisation", color=ft.Colors.WHITE, weight=ft.FontWeight.W_600, size=15),
                            ],
                        ),
                        bgcolor=ft.Colors.PRIMARY,
                        height=50,
                        width=float("inf"),
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=12),
                            elevation=0,
                        ),
                        on_click=lambda _: show_create_form(),
                    ),
                ],
            ),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 4. TEACHER / INSTRUCTOR VIEW
    # ─────────────────────────────────────────────────────────────────────────
    # ═══════════════════════════════════════════════════════════════════════════════
# SURGICAL DROP-IN REPLACEMENT
# Replace the entire `build_teacher_view` function (lines 749–865) in org_view.py.
# Also update `fetch_org_status` to pass org memberships into it (see bottom).
#
# ── WHAT IS REAL vs MOCK ───────────────────────────────────────────────────────
#
#  ✅ REAL (live data, real navigation):
#    - Teacher's org list                → fetched via get_my_organisation() + member list
#    - Per-org course list               → fetched via get_organisation_courses()
#    - Org card click → org course view  → real navigation to per-org course detail
#    - Freelance tab "Create Free Course"→ navigates to real /create-course route
#
#  🟡 MOCK (wired UI, no backend yet):
#    - "Create Course for Org" button inside org course view  → page.go() stub
#    - Freelance course library list     → empty state (no freelance courses API yet)
#    - Course card click inside org view → page.go() stub (settings route exists)
#
# ── REQUIRED: add this import at the top of org_view.py if not already present ─
#   from src.requests.organisations import get_my_organisation, get_organisation_courses
#
# ── REQUIRED: update fetch_org_status (lines 889–955) ─────────────────────────
#   Change the TEACHER branch from:
#       show_teacher_view()
#   To:
#       memberships = await asyncio.wait_for(get_my_organisation(token), timeout=15)
#       show_teacher_view(memberships or [])
#
#   If get_my_organisation returns a single dict (admin view), wrap it in a list:
#       raw = await asyncio.wait_for(get_my_organisation(token), timeout=15)
#       memberships = raw if isinstance(raw, list) else ([raw] if raw else [])
#       show_teacher_view(memberships)
#
#   Then update show_teacher_view (lines 882–884) to:
#       def show_teacher_view(memberships=None):
#           content_socket.content = build_teacher_view(memberships or [])
#           page.update()
# ═══════════════════════════════════════════════════════════════════════════════


    # ─────────────────────────────────────────────────────────────────────────
    # 4. TEACHER / INSTRUCTOR VIEW
    # ─────────────────────────────────────────────────────────────────────────
    async def build_teacher_view(memberships: list):
        """
        memberships: list of org dicts the teacher belongs to.
        Each dict expected shape (from your existing API):
          { "id", "name", "role", "logo", "theme_color",
            "students", "courses", "members" }
        """

        # ── Per-org course cache ──────────────────────────────────────────────
        # Keyed by org_id, populated lazily when the teacher taps an org card.
        org_courses_cache: dict[str, list] = {}

        # ── State: which org is currently expanded (None = list view) ─────────
        selected_org: dict | None = None

        # ─────────────────────────────────────────────────────────────────────
        # Helpers
        # ─────────────────────────────────────────────────────────────────────
        def role_badge(role_label: str):
            colour_map = {
                "ADMIN":             (ft.Colors.BLUE_50,    ft.Colors.BLUE_800),
                "TEACHER":           (ft.Colors.ORANGE_50,  ft.Colors.ORANGE_800),
                "LEAD TUTOR":        (ft.Colors.PURPLE_50,  ft.Colors.PURPLE_800),
                "GUEST INSTRUCTOR":  (ft.Colors.TEAL_50,    ft.Colors.TEAL_800),
                "INSTRUCTOR":        (ft.Colors.AMBER_50,   ft.Colors.AMBER_900),
            }
            bg, fg = colour_map.get(role_label.upper(), (ft.Colors.GREY_100, ft.Colors.GREY_700))
            return ft.Container(
                padding=ft.Padding.symmetric(horizontal=9, vertical=3),
                bgcolor=bg,
                border_radius=20,
                content=ft.Text(role_label, size=10, color=fg, weight=ft.FontWeight.W_600),
            )

        def mini_stat(icon, value, label, color):
            return ft.Row(
                spacing=5,
                controls=[
                    ft.Container(
                        bgcolor=ft.Colors.with_opacity(0.12, color),
                        border_radius=6,
                        padding=5,
                        content=ft.Icon(icon, size=14, color=color),
                    ),
                    ft.Column(
                        spacing=0,
                        controls=[
                            ft.Text(str(value), size=13, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                            ft.Text(label,       size=10, color=ft.Colors.GREY_500),
                        ],
                    ),
                ],
            )

        # ─────────────────────────────────────────────────────────────────────
        # Tab 1 — My Orgs
        # ─────────────────────────────────────────────────────────────────────

        # Mutable socket so we can swap between list ↔ org-detail in-place
        orgs_socket = ft.Column(expand=True)

        async def load_org_detail(org: dict):
            nonlocal selected_org
            selected_org = org
            org_id        = org.get("id", "")
            org_name      = org.get("name", "Organisation")
            theme_color   = org.get("theme_color") or ft.Colors.PRIMARY
            teacher_role  = org.get("role", "Instructor")

            # Fetch courses if not cached  ── REAL ──
            if org_id not in org_courses_cache:
                try:
                    # is_freelance=False: this is the teacher's genuine "My Orgs"
                    # view — even when org_id happens to be DEFAULT_ORG_ID (a
                    # teacher who's a real Nu Age staff member, not a freelancer),
                    # this must NOT pull in the freelance pool's courses.
                    courses = await asyncio.wait_for(
                        get_organisation_courses(token, org_id, is_freelance=False), timeout=15
                    )
                    org_courses_cache[org_id] = courses or []
                except Exception as ex:
                    print(f"[teacher_view] courses fetch failed: {ex}")
                    org_courses_cache[org_id] = []

            courses = org_courses_cache[org_id]
            
            # ── Course card inside org detail ────────────────────────────────
            def org_course_card(course: dict):
                title    = course.get("name", "Untitled Course")
                desc     = course.get("description", "")
                enrolled = course.get("total_students", 0)
                public_val = str(course.get("public", "false")).lower()
                cid      = course.get("id", "")

                status_bg  = ft.Colors.GREEN_50 if public_val == "true" else (ft.Colors.BLUE_50 if public_val == "organisation" else ft.Colors.GREY_100)
                status_fg  = ft.Colors.GREEN_700 if public_val == "true" else (ft.Colors.BLUE_700 if public_val == "organisation" else ft.Colors.GREY_600)
                status_lbl = "Published" if public_val == "true" else ("Organization" if public_val == "organisation" else "Draft")

                return ft.Container(
                    bgcolor=ft.Colors.SURFACE,
                    border_radius=12,
                    border=ft.Border.all(1, ft.Colors.GREY_200),
                    shadow=ft.BoxShadow(
                        blur_radius=6,
                        color=ft.Colors.with_opacity(0.07, ft.Colors.BLACK),
                        offset=ft.Offset(0, 2),
                    ),
                    margin=ft.Margin.only(bottom=2),
                    ink=True,
                    on_click=lambda e, cid=cid: page.go(
                        f"/courses/{cid}/manage"
                    ),
                    content=ft.Row(
                        spacing=0,
                        controls=[
                            # Left accent stripe using org theme colour
                            ft.Container(
                                width=4,
                                bgcolor=theme_color,
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
                                                    title, size=14,
                                                    weight=ft.FontWeight.W_600,
                                                    color=ft.Colors.ON_SURFACE,
                                                    expand=True,
                                                    max_lines=1,
                                                    overflow=ft.TextOverflow.ELLIPSIS,
                                                ),
                                                ft.Container(
                                                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                                    bgcolor=status_bg,
                                                    border_radius=10,
                                                    content=ft.Text(
                                                        status_lbl, size=9,
                                                        color=status_fg,
                                                        weight=ft.FontWeight.W_600,
                                                    ),
                                                ),
                                            ],
                                        ),
                                        ft.Text(
                                            desc, size=12, color=ft.Colors.GREY_500,
                                            max_lines=2, overflow=ft.TextOverflow.ELLIPSIS,
                                        ),
                                        ft.Row(
                                            spacing=12,
                                            controls=[
                                                ft.Row(
                                                    spacing=4,
                                                    controls=[
                                                        ft.Icon(ft.Icons.PEOPLE_ALT_ROUNDED, size=13, color=ft.Colors.GREY_400),
                                                        ft.Text(f"{enrolled} enrolled", size=11, color=ft.Colors.GREY_500),
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

            # ── Org detail screen ────────────────────────────────────────────
            course_list = (
                ft.Column(
                    spacing=10,
                    scroll=ft.ScrollMode.AUTO,
                    expand=False,
                    controls=[org_course_card(c) for c in courses],
                )
                if courses
                else ft.Column(
                    expand=True,
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(height=24),
                        ft.Icon(ft.Icons.LIBRARY_BOOKS_OUTLINED, size=44, color=ft.Colors.GREY_300),
                        ft.Container(height=10),
                        ft.Text("No courses yet", size=15, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_500),
                        ft.Text(
                            "Create your first course for this organisation.",
                            size=12, color=ft.Colors.GREY_400,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                )
            )

            orgs_socket.controls = [
                ft.Column(
                    expand=True,
                    controls=[
                        # ── Org detail header banner ─────────────────────────
                        ft.Container(
                            bgcolor=theme_color,
                            border_radius=ft.BorderRadius.only(bottom_left=20, bottom_right=20),
                            padding=ft.Padding.only(top=8, left=8, right=16, bottom=20),
                            content=ft.Column(
                                spacing=6,
                                controls=[
                                    ft.Row(
                                        controls=[
                                            ft.IconButton(
                                                ft.Icons.ARROW_BACK_ROUNDED,
                                                icon_color=ft.Colors.WHITE,
                                                icon_size=22,
                                                on_click=lambda _: page.run_task(show_org_list),
                                            ),ft.Container(
                                        padding=ft.Padding.only(left=16),
                                        content=ft.Column(
                                            spacing=4,
                                            controls=[
                                                ft.Text(
                                                    org_name, size=20,
                                                    weight=ft.FontWeight.W_700,
                                                    color=ft.Colors.WHITE,
                                                ),
                                                role_badge(teacher_role),
                                            ],
                                        ),
                                    ),
                                        ],
                                    ),
                                ],
                            ),
                        ),
                        # ── Courses section ──────────────────────────────────
                        ft.Container(
                            expand=True,
                            padding=ft.Padding.symmetric(horizontal=16, vertical=14),
                            content=ft.Column(
                                expand=True,
                                scroll=ft.ScrollMode.AUTO,
                                spacing=12,
                                controls=[
                                    ft.Row(
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        controls=[
                                            ft.Text("Courses", size=16, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                                            ft.ElevatedButton(
                                                content=ft.Row(
                                                    tight=True,
                                                    spacing=4,
                                                    controls=[
                                                        ft.Icon(ft.Icons.ADD_ROUNDED, color=ft.Colors.WHITE, size=16),
                                                        ft.Text("Create Course", color=ft.Colors.WHITE, size=12, weight=ft.FontWeight.W_600),
                                                    ],
                                                ),
                                                bgcolor=theme_color,
                                                height=34,
                                                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), elevation=0),
                                                on_click=lambda _: page.go("/create-course"),
                                            ),
                                        ],
                                    ),
                                    ft.Divider(height=1, color=ft.Colors.GREY_100),
                                    course_list,
                                ],
                            ),
                        ),
                    ],
                )
            ]
            page.update()

        async def show_org_list():
            nonlocal selected_org
            selected_org = None
            orgs_socket.controls = [build_org_list()]
            page.update()

        # ── Org card (list view) ─────────────────────────────────────────────
        def org_card(org: dict):
            theme_color  = org.get("theme_color") or ft.Colors.PRIMARY
            teacher_role = org.get("role", "Instructor")
            students     = org.get("students", 0)
            courses      = org.get("courses", 0)
            logo_url     = org.get("logo")

            avatar = (
                ft.CircleAvatar(
                    radius=21,
                    bgcolor=ft.Colors.GREY_100,
                    background_image_src=logo_url,
                )
                if logo_url
                else ft.Container(
                    width=42, height=42,
                    bgcolor=ft.Colors.with_opacity(0.15, theme_color),
                    border_radius=12,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text(
                        org.get("name", "?")[0].upper(),
                        size=18, weight=ft.FontWeight.W_700, color=theme_color,
                    ),
                )
            )

            return ft.Container(
                bgcolor=ft.Colors.SURFACE,
                border_radius=14,
                border=ft.Border.all(1, ft.Colors.GREY_200),
                shadow=ft.BoxShadow(
                    blur_radius=8,
                    color=ft.Colors.with_opacity(0.07, ft.Colors.BLACK),
                    offset=ft.Offset(0, 3),
                ),
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                ink=True,
                on_click=lambda e, o=org: page.run_task(load_org_detail, o),
                content=ft.Column(
                    spacing=0,
                    controls=[
                        # Coloured top stripe
                        ft.Container(
                            height=4,
                            bgcolor=theme_color,
                        ),
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=16, vertical=14),
                            content=ft.Column(
                                spacing=12,
                                controls=[
                                    ft.Row(
                                        spacing=12,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                        controls=[
                                            avatar,
                                            ft.Column(
                                                spacing=4,
                                                expand=True,
                                                controls=[
                                                    ft.Text(
                                                        org.get("name", "Organisation"),
                                                        size=15,
                                                        weight=ft.FontWeight.W_700,
                                                        color=ft.Colors.ON_SURFACE,
                                                        max_lines=1,
                                                        overflow=ft.TextOverflow.ELLIPSIS,
                                                    ),
                                                    role_badge(teacher_role),
                                                ],
                                            ),
                                            ft.Icon(
                                                ft.Icons.CHEVRON_RIGHT_ROUNDED,
                                                color=ft.Colors.GREY_400,
                                                size=20,
                                            ),
                                        ],
                                    ),
                                    ft.Divider(height=1, color=ft.Colors.GREY_100),
                                    ft.Row(
                                        spacing=20,
                                        controls=[
                                            mini_stat(ft.Icons.LIBRARY_BOOKS_ROUNDED, courses, "Courses", theme_color),
                                            mini_stat(ft.Icons.PEOPLE_ALT_ROUNDED,   students, "Students", ft.Colors.BLUE_400),
                                        ],
                                    ),
                                ],
                            ),
                        ),
                    ],
                ),
            )

        def build_org_list():
            if not memberships:
                # Empty state — real, shows when teacher has no orgs
                return ft.Container(
                    expand=True,
                    alignment=ft.Alignment.CENTER,
                    padding=40,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=10,
                        controls=[
                            ft.Icon(ft.Icons.BUSINESS_OUTLINED, size=52, color=ft.Colors.GREY_300),
                            ft.Container(height=6),
                            ft.Text("No organisations yet", size=16, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_500),
                            ft.Text(
                                "You haven't been added to any organisation.",
                                size=13, color=ft.Colors.GREY_400,
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ],
                    ),
                )

            return ft.ListView(
                expand=True,
                spacing=12,
                padding=ft.Padding.symmetric(horizontal=16, vertical=16),
                controls=[org_card(org) for org in memberships],
            )

        # Seed the socket with the org list
        orgs_socket.controls = [build_org_list()]

        # ─────────────────────────────────────────────────────────────────────
        # Tab 2 — Freelance Course Library
        # ─────────────────────────────────────────────────────────────────────
        # ✅ REAL: fetches this teacher's freelance courses. The backend scopes
        #    TEACHER-role requests against DEFAULT_ORG_ID to teacher_id == the
        #    calling user, so this list is automatically "just theirs" — no
        #    client-side filtering needed, and there's no way to see other
        #    freelancers' courses even by tampering with the request.
        try:
            freelance_courses = await asyncio.wait_for(
                get_organisation_courses(token, DEFAULT_ORG_ID, is_freelance=True), timeout=15
            )
            freelance_courses = freelance_courses or []
        except Exception as ex:
            print(f"[teacher_view] freelance courses fetch failed: {ex}")
            freelance_courses = []

        def freelance_course_card(course: dict):
            title    = course.get("name", "Untitled Course")
            enrolled = course.get("total_students", 0)
            public_val = str(course.get("public", "false")).lower()
            cid      = course.get("id", "")
            status_bg  = ft.Colors.GREEN_50 if public_val == "true" else (ft.Colors.BLUE_50 if public_val == "organisation" else ft.Colors.GREY_100)
            status_fg  = ft.Colors.GREEN_700 if public_val == "true" else (ft.Colors.BLUE_700 if public_val == "organisation" else ft.Colors.GREY_600)
            status_lbl = "Published" if public_val == "true" else ("Organization" if public_val == "organisation" else "Draft")

            return ft.Container(
                bgcolor=ft.Colors.SURFACE,
                border_radius=12,
                border=ft.Border.all(1, ft.Colors.GREY_200),
                padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                margin=ft.Margin.only(bottom=8),
                ink=True,
                on_click=lambda e, cid=cid: page.go(f"/courses/{cid}/manage"),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(
                            spacing=2, expand=True,
                            controls=[
                                ft.Text(title, size=13, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                                ft.Text(f"{enrolled} student{'s' if enrolled != 1 else ''}", size=11, color=ft.Colors.GREY_500),
                            ],
                        ),
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.Container(
                                    padding=ft.Padding.symmetric(horizontal=9, vertical=3),
                                    bgcolor=status_bg, border_radius=10,
                                    content=ft.Text(status_lbl, size=10, color=status_fg, weight=ft.FontWeight.W_600),
                                ),
                                ft.IconButton(
                                    ft.Icons.BAR_CHART_ROUNDED, icon_size=16, icon_color=ft.Colors.GREY_400,
                                    tooltip="Analytics",
                                    on_click=lambda e, cid=cid: page.go(
                                        f"/organisations/{DEFAULT_ORG_ID}/courses/{cid}/analytics"
                                    ),
                                ),
                            ],
                        ),
                    ],
                ),
            )

        freelance_list_content = (
            ft.Column(
                spacing=0,
                controls=[freelance_course_card(c) for c in freelance_courses],
            )
            if freelance_courses else
            # Empty state — shown only when this teacher genuinely has no
            # freelance courses yet.
            ft.Column(
                    expand=True,
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            width=80, height=80,
                            bgcolor=ft.Colors.PRIMARY_CONTAINER,
                            border_radius=40,
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(
                                ft.Icons.MIC_EXTERNAL_ON_ROUNDED,
                                size=38, color=ft.Colors.PRIMARY,
                            ),
                        ),
                        ft.Container(height=16),
                        ft.Text(
                            "No freelance courses yet",
                            size=16, weight=ft.FontWeight.W_600,
                            color=ft.Colors.ON_SURFACE,
                        ),
                        ft.Container(height=6),
                        ft.Text(
                            "Publish a course independently — no organisation needed.",
                            size=12, color=ft.Colors.GREY_500,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Container(height=24),
                        ft.OutlinedButton(
                            content=ft.Row(
                                tight=True,
                                spacing=6,
                                controls=[
                                    ft.Icon(ft.Icons.ADD_ROUNDED, size=16, color=ft.Colors.PRIMARY),
                                    ft.Text("Create Your First Course", size=13, color=ft.Colors.PRIMARY, weight=ft.FontWeight.W_600),
                                ],
                            ),
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=10),
                                side=ft.BorderSide(1.5, ft.Colors.PRIMARY),
                            ),
                            height=44,
                            on_click=lambda _: page.go("/create-course"),
                        ),
                    ],
                )
        )

        freelance_content = ft.Container(
            expand=True,
            padding=ft.Padding.symmetric(horizontal=16, vertical=16),
            content=ft.Column(
                expand=True,
                spacing=0,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Column(
                                spacing=2,
                                controls=[
                                    ft.Text(
                                        "Freelance Courses",
                                        size=16, weight=ft.FontWeight.W_700,
                                        color=ft.Colors.ON_SURFACE,
                                    ),
                                    ft.Text(
                                        "Courses you own outside any organisation.",
                                        size=11, color=ft.Colors.GREY_500,
                                    ),
                                ],
                            ),
                            # ✅ REAL navigation to create-course
                            ft.ElevatedButton(
                                content=ft.Row(
                                    tight=True,
                                    spacing=4,
                                    controls=[
                                        ft.Icon(ft.Icons.ADD_ROUNDED, color=ft.Colors.WHITE, size=16),
                                        ft.Text("Create Free", color=ft.Colors.WHITE, size=12, weight=ft.FontWeight.W_600),
                                    ],
                                ),
                                bgcolor=ft.Colors.PRIMARY,
                                height=34,
                                style=ft.ButtonStyle(
                                    shape=ft.RoundedRectangleBorder(radius=8),
                                    elevation=0,
                                ),
                                on_click=lambda _: page.go("/create-course"),
                            ),
                        ],
                    ),
                    ft.Divider(height=20, color=ft.Colors.GREY_100),
                    freelance_list_content,
                ],
            ),
        )

        # ─────────────────────────────────────────────────────────────────────
        # Outer shell
        # ─────────────────────────────────────────────────────────────────────
        # ── REPLACE lines 826–865 (the return ft.Column at the bottom of build_teacher_view) ──

        # ── REPLACE the final return ft.Column(...) block inside build_teacher_view ──
# (the one that starts at line 826 in the original, containing the header banner + ft.Tabs)

        # ── Identity card: instructor profile strip ───────────────────────────
        first_name  = user_data.get("first_name", "Instructor")
        last_name   = user_data.get("last_name", "")
        initials    = f"{first_name[0]}{last_name[0]}".upper() if last_name else first_name[:2].upper()
        org_count   = len(memberships)

        identity_card = ft.Container(
            # Subtle gradient: PRIMARY at top-left fading to a deeper tint bottom-right
            gradient=ft.LinearGradient(
                begin=ft.Alignment(-1, -1),
                end=ft.Alignment(1, 1),
                colors=[ft.Colors.PRIMARY, ft.Colors.with_opacity(0.78, ft.Colors.PRIMARY)],
            ),
            padding=ft.Padding.only(left=20, right=20, top=18, bottom=16),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        spacing=14,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            # Avatar with white ring
                            ft.Container(
                                width=46, height=46,
                                border_radius=23,
                                bgcolor=ft.Colors.with_opacity(0.22, ft.Colors.WHITE),
                                border=ft.Border.all(2, ft.Colors.with_opacity(0.5, ft.Colors.WHITE)),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Text(
                                    initials,
                                    size=16,
                                    weight=ft.FontWeight.W_700,
                                    color=ft.Colors.WHITE,
                                ),
                            ),
                            ft.Column(
                                spacing=2,
                                controls=[
                                    ft.Text(
                                        f"Hey, {first_name}, Ready to teach?",
                                        size=16,
                                        weight=ft.FontWeight.W_700,
                                        color=ft.Colors.WHITE,
                                    ),
                                    ft.Text(
                                        "Instructor",
                                        size=11,
                                        color=ft.Colors.with_opacity(0.75, ft.Colors.WHITE),
                                        weight=ft.FontWeight.W_500,
                                    ),
                                ],
                            ),
                        ],
                    ),
                    # Org count chip
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                        bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.WHITE),
                        border_radius=20,
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.WHITE)),
                        content=ft.Row(
                            tight=True,
                            spacing=5,
                            controls=[
                                ft.Icon(ft.Icons.BUSINESS_ROUNDED, size=12, color=ft.Colors.WHITE),
                                ft.Text(
                                    f"{org_count} Org{'s' if org_count != 1 else ''}",
                                    size=11,
                                    weight=ft.FontWeight.W_600,
                                    color=ft.Colors.WHITE,
                                ),
                            ],
                        ),
                    ),
                ],
            ),
        )

        return ft.Column(
            expand=True,
            spacing=0,
            controls=[
                identity_card,
                # ── Tab bar ───────────────────────────────────────────────────
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
                                unselected_label_color=ft.Colors.GREY_400,
                                unselected_label_text_style=ft.TextStyle(size=12),
                                divider_color=ft.Colors.GREY_100,
                                tabs=[
                                    ft.Tab(label="My Orgs",   icon=ft.Icons.BUSINESS_ROUNDED),
                                    ft.Tab(label="Freelance", icon=ft.Icons.MIC_EXTERNAL_ON_ROUNDED),
                                ],
                            ),
                            ft.TabBarView(
                                expand=True,
                                controls=[
                                    orgs_socket,
                                    freelance_content,
                                ],
                            ),
                        ],
                    ),
                ),
            ],
        )
    # ─────────────────────────────────────────────────────────────────────────
    # 5. NAVIGATION HANDLERS
    # ─────────────────────────────────────────────────────────────────────────
    async def _load_teacher_view(memberships):
        content_socket.content = await build_teacher_view(memberships)
        page.update()
    async def show_dashboard(org_data):
        content_socket.content = await build_dashboard_view(org_data)
        page.update()

    def show_create_form():
        content_socket.content = build_create_form_view()
        page.update()

    def show_promo_view():
        content_socket.content = build_promo_view()
        page.update()

    def show_teacher_view(memberships=None):
        page.run_task(_load_teacher_view, memberships or [])




    # ─────────────────────────────────────────────────────────────────────────
    # 6. INITIAL LOAD  (with full error safety)
    # ─────────────────────────────────────────────────────────────────────────
    async def fetch_org_status():
        nonlocal token
        token = await page.shared_preferences.get("auth_token")
        if role in ("TEACHER", "INSTRUCTOR"):
            try:
                memberships = await asyncio.wait_for(
                    get_joined_organisations(token), timeout=15
                )
            except Exception:
                memberships = []
            show_teacher_view(memberships)
            return

        try:
            org_data = await asyncio.wait_for(
                get_my_organisation(token), timeout=15
            )
            if org_data:
                await show_dashboard(org_data)
            else:
                show_promo_view()

        except asyncio.TimeoutError:
            content_socket.content = ft.Container(
                expand=True,
                alignment=ft.Alignment.CENTER,
                padding=30,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=10,
                    controls=[
                        ft.Icon(ft.Icons.WIFI_OFF_ROUNDED, size=48, color=ft.Colors.ORANGE_400),
                        ft.Text("Connection timed out", size=17, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                        ft.Text("Please check your internet connection\nand try again.", size=13, color=ft.Colors.GREY_500, text_align=ft.TextAlign.CENTER),
                        ft.Container(height=8),
                        ft.ElevatedButton(
                            "Retry",
                            bgcolor=ft.Colors.PRIMARY,
                            color=ft.Colors.WHITE,
                            height=42,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
                            on_click=lambda _: page.run_task(fetch_org_status),
                        ),
                    ],
                ),
            )
            page.update()

        except Exception as ex:
            content_socket.content = ft.Container(
                expand=True,
                alignment=ft.Alignment.CENTER,
                padding=30,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=10,
                    controls=[
                        ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, size=48, color=ft.Colors.RED_400),
                        ft.Text("Something went wrong", size=17, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                        ft.Text(f"{type(ex).__name__}: unable to load your organisation.", size=13, color=ft.Colors.GREY_500, text_align=ft.TextAlign.CENTER),
                        ft.Container(height=8),
                        ft.ElevatedButton(
                            "Retry",
                            bgcolor=ft.Colors.PRIMARY,
                            color=ft.Colors.WHITE,
                            height=42,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
                            on_click=lambda _: page.run_task(fetch_org_status),
                        ),
                    ],
                ),
            )
            page.update()

    page.run_task(fetch_org_status)

    # ─────────────────────────────────────────────────────────────────────────
    # 7. VIEW
    # ─────────────────────────────────────────────────────────────────────────
    return ft.View(
        route="/organisations",
        bottom_appbar=app_bar,
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        padding=0,
        controls=[
            ft.SafeArea(expand=True, content=content_socket)
        ],
    )