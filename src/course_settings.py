import asyncio
import flet as ft
from src.components.bottom_appbar import get_bottom_appbar
from src.requests.Courses import get_categories, get_courses, update_course_settings, delete_course
from src.requests.organisations import get_organisation_members, get_enrolled_org_students, get_my_organisation
from src.requests.enrollments import bulk_enrol_students, bulk_unenrol_students


# ═══════════════════════════════════════════════════════════════════════════════
# MODERN COURSE SETTINGS (SLEEK, UNCLUTTERED & INTUITIVE)
# ═══════════════════════════════════════════════════════════════════════════════

def _pill(label: str, bg, fg, icon=None) -> ft.Container:
    controls = []
    if icon:
        controls.append(ft.Icon(icon, size=11, color=fg))
    controls.append(ft.Text(label, size=10, color=fg, weight=ft.FontWeight.BOLD))
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
        bgcolor=bg,
        border_radius=8,
        content=ft.Row(controls, spacing=4, tight=True),
    )


def _card_header(title: str, subtitle: str = None, action: ft.Control = None) -> ft.Row:
    text_col = ft.Column([
        ft.Text(title, size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
    ], spacing=2, expand=True)
    if subtitle:
        text_col.controls.append(
            ft.Text(subtitle, size=11, color=ft.Colors.ON_SURFACE_VARIANT)
        )
    controls = [text_col]
    if action:
        controls.append(action)
    return ft.Row(controls, alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER)


async def course_settings_view(page: ft.Page, course_id: str, org_id: str = None) -> ft.View:
    app_bar = get_bottom_appbar(page)
    token = await page.shared_preferences.get("auth_token")
    if not token:
        return _error_view(course_id, "Authentication failed. Please log in again.")

    effective_org_id = org_id or (page.session.store.get("current_org_id") if page.session and page.session.store else None) or ""

    def _go_back(e=None):
        if len(page.views) > 1:
            page.views.pop()
        else:
            page.go(f"/organisations/{effective_org_id}" if effective_org_id else "/organisations")
        page.update()

    theme_color = ft.Colors.INDIGO_600

    # ── Toast Helpers ─────────────────────────────────────────────────────────
    def show_toast(message: str, color=ft.Colors.GREEN_700):
        snack = ft.SnackBar(
            content=ft.Text(message, color=ft.Colors.WHITE, size=12, weight=ft.FontWeight.W_500),
            bgcolor=color,
            duration=2800,
        )
        page.overlay.append(snack)
        snack.open = True
        page.update()

    def show_error_toast(message: str):
        show_toast(message, color=ft.Colors.RED_700)

    # ── Centered Loading Socket ───────────────────────────────────────────────
    content_socket = ft.Container(
        expand=True,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.ProgressRing(color=ft.Colors.PRIMARY, width=44, height=44, stroke_width=3.5),
                ft.Container(height=16),
                ft.Text("Loading Course Configuration…", size=13, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE_VARIANT),
            ],
        ),
    )

    # ── Fetch Initial Data ───────────────────────────────────────────────────
    async def load_all_data():
        nonlocal theme_color
        try:
            # Parallel fetch course data, categories, teachers, and org profile
            raw_courses_task = get_courses(token, params={"id": course_id})
            categories_task = get_categories(token, None)
            teachers_task = get_organisation_members(token, id=effective_org_id, teachers=True) if effective_org_id else asyncio.sleep(0, result=[])
            org_task = get_my_organisation(token) if effective_org_id else asyncio.sleep(0, result={})

            raw_courses, categories, teachers, org_data = await asyncio.gather(
                raw_courses_task, categories_task, teachers_task, org_task, return_exceptions=True
            )

            course_data = None
            if isinstance(raw_courses, list) and raw_courses:
                course_data = raw_courses[0]
            elif isinstance(raw_courses, dict) and "id" in raw_courses:
                course_data = raw_courses

            if not course_data or (isinstance(course_data, dict) and "error" in course_data):
                content_socket.content = _build_error_widget("Course not found or could not be loaded.")
                page.update()
                return

            if isinstance(org_data, dict) and org_data.get("theme_color"):
                theme_color = org_data.get("theme_color")

            cat_list = categories if isinstance(categories, list) else []
            teacher_list = teachers if isinstance(teachers, list) else []

            content_socket.alignment = None
            content_socket.content = build_settings_ui(course_data, cat_list, teacher_list)
            page.update()

        except Exception as ex:
            content_socket.content = _build_error_widget(f"Failed to load course settings: {ex}")
            page.update()

    def _build_error_widget(msg: str):
        return ft.Container(
            padding=32,
            alignment=ft.Alignment.CENTER,
            content=ft.Column(
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, size=48, color=ft.Colors.RED_400),
                    ft.Text("Configuration Unavailable", size=17, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Text(msg, size=12, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER),
                    ft.Container(height=8),
                    ft.FilledButton(
                        "Return to Dashboard",
                        icon=ft.Icons.ARROW_BACK_ROUNDED,
                        on_click=lambda _: page.go("/organisations"),
                    ),
                ],
            ),
        )

    # ── UI Builder ───────────────────────────────────────────────────────────
    def build_settings_ui(course_data: dict, categories: list, teachers: list):
        course_name = course_data.get("name") or "Untitled Course"
        course_desc = course_data.get("description") or ""
        current_cat = course_data.get("category", {}).get("name") if isinstance(course_data.get("category"), dict) else (course_data.get("category") or "")
        current_teacher_id = course_data.get("teacher_id")

        # Normalize public visibility value
        raw_pub = str(course_data.get("public", "false")).lower()
        if raw_pub in ["true", "public"]:
            current_visibility = "public"
        elif raw_pub in ["organisation", "campus", "organization"]:
            current_visibility = "organisation"
        else:
            current_visibility = "false"

        # ── HERO HEADER CARD ─────────────────────────────────────────────────
        pub_badge = (
            _pill("PUBLIC", ft.Colors.GREEN_700, ft.Colors.WHITE, ft.Icons.PUBLIC_ROUNDED)
            if current_visibility == "public"
            else (
                _pill("CAMPUS", ft.Colors.BLUE_700, ft.Colors.WHITE, ft.Icons.LOCK_ROUNDED)
                if current_visibility == "organisation"
                else _pill("DRAFT", ft.Colors.GREY_700, ft.Colors.WHITE, ft.Icons.EDIT_NOTE_ROUNDED)
            )
        )

        hero_card = ft.Container(
            margin=ft.Margin.symmetric(horizontal=16, vertical=8),
            border_radius=16,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.with_opacity(0.05, ft.Colors.BLACK), offset=ft.Offset(0, 2)),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            content=ft.Column([
                # Gradient Bar
                ft.Container(
                    gradient=ft.LinearGradient(
                        begin=ft.Alignment(-1, -1),
                        end=ft.Alignment(1, 1),
                        colors=[theme_color, ft.Colors.PRIMARY],
                    ),
                    padding=ft.Padding.only(top=10, left=12, right=12, bottom=12),
                    content=ft.Row([
                        ft.Row([
                            ft.IconButton(
                                ft.Icons.ARROW_BACK_ROUNDED,
                                icon_color=ft.Colors.WHITE,
                                icon_size=18,
                                tooltip="Back",
                                on_click=_go_back,
                            ),
                            ft.Text("Course Configuration & Settings", size=13, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE),
                        ], spacing=4),
                        ft.Row([
                            ft.IconButton(
                                ft.Icons.BAR_CHART_ROUNDED,
                                icon_color=ft.Colors.WHITE,
                                icon_size=17,
                                tooltip="Analytics Telemetry",
                                on_click=lambda _: page.go(f"/organisations/{effective_org_id}/courses/{course_id}/analytics" if effective_org_id else f"/courses/{course_id}/analytics"),
                            ),
                            ft.IconButton(
                                ft.Icons.SCHOOL_ROUNDED,
                                icon_color=ft.Colors.WHITE,
                                icon_size=17,
                                tooltip="Curriculum Builder",
                                on_click=lambda _: page.go(f"/courses/{course_id}/manage"),
                            ),
                            ft.IconButton(
                                ft.Icons.VISIBILITY_OUTLINED,
                                icon_color=ft.Colors.WHITE,
                                icon_size=17,
                                tooltip="Preview Course",
                                on_click=lambda _: page.go(f"/courses/{course_id}/view"),
                            ),
                        ], spacing=2),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ),
                # Breadcrumb & Info Body
                ft.Container(
                    padding=ft.Padding.all(16),
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(ft.Icons.HOME_ROUNDED, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text("Academy", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text("Courses", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(course_name, size=11, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                        ], spacing=4, wrap=True),
                        ft.Text(course_name, size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                        ft.Row([
                            pub_badge,
                            ft.Row([
                                ft.Icon(ft.Icons.CATEGORY_ROUNDED, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(current_cat or "Uncategorized", size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500),
                            ], spacing=4),
                        ], spacing=8),
                    ], spacing=6),
                ),
            ], spacing=0),
        )

        # ── CARD 1: GENERAL INFORMATION ───────────────────────────────────────
        name_input = ft.TextField(
            value=course_name,
            label="Course Title",
            hint_text="e.g. Distributed Systems Architecture",
            prefix_icon=ft.Icons.TITLE_ROUNDED,
            border_radius=10,
            border_color=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE),
            focused_border_color=theme_color,
            dense=True,
            expand=True,
        )

        desc_input = ft.TextField(
            value=course_desc,
            label="Course Summary & Description",
            hint_text="Provide a clear, pedagogical overview of the syllabus and learning objectives…",
            prefix_icon=ft.Icons.DESCRIPTION_OUTLINED,
            multiline=True,
            min_lines=2,
            max_lines=4,
            border_radius=10,
            border_color=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE),
            focused_border_color=theme_color,
            dense=True,
            expand=True,
        )

        cat_options = [ft.dropdown.Option(c["name"]) for c in categories if isinstance(c, dict) and "name" in c]
        category_dropdown = ft.Dropdown(
            label="Curriculum Category",
            value=current_cat if any(opt.key == current_cat for opt in cat_options) else (cat_options[0].key if cat_options else None),
            options=cat_options,
            leading_icon=ft.Icons.LABEL_OUTLINE_ROUNDED,
            border_radius=10,
            border_color=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE),
            focused_border_color=theme_color,
            dense=True,
            expand=True,
        )

        save_general_btn = ft.FilledButton(
            "Save Changes",
            icon=ft.Icons.CHECK_ROUNDED,
            style=ft.ButtonStyle(
                bgcolor=theme_color,
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding.symmetric(horizontal=14, vertical=8),
            ),
        )

        async def on_save_general(e):
            save_general_btn.disabled = True
            save_general_btn.text = "Saving…"
            page.update()

            title_val = name_input.value.strip()
            if not title_val:
                show_error_toast("Course title cannot be empty.")
                save_general_btn.disabled = False
                save_general_btn.text = "Save Changes"
                page.update()
                return

            try:
                p1 = update_course_settings(token, course_id, {"name": title_val})
                p2 = update_course_settings(token, course_id, {"description": desc_input.value.strip()})
                p3 = update_course_settings(token, course_id, {"category": category_dropdown.value}) if category_dropdown.value else asyncio.sleep(0)
                await asyncio.gather(p1, p2, p3)
                show_toast("Course details successfully updated.")
            except Exception as ex:
                show_error_toast(f"Failed to update course: {ex}")
            finally:
                save_general_btn.disabled = False
                save_general_btn.text = "Save Changes"
                page.update()

        save_general_btn.on_click = lambda e: page.run_task(on_save_general, e)

        general_card = ft.Container(
            margin=ft.Margin.symmetric(horizontal=16, vertical=6),
            bgcolor=ft.Colors.SURFACE,
            border_radius=14,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            padding=ft.Padding.all(16),
            content=ft.Column([
                _card_header(
                    "General Information",
                    "Foundational details and syllabus metadata",
                    save_general_btn,
                ),
                ft.Container(height=10),
                name_input,
                ft.Container(height=4),
                desc_input,
                ft.Container(height=4),
                category_dropdown,
            ], spacing=6),
        )

        # ── CARD 2: ACCESS & GOVERNANCE ───────────────────────────────────────
        selected_visibility = current_visibility

        def build_visibility_option(key: str, title: str, subtitle: str, icon):
            is_active = (selected_visibility == key)
            border_col = theme_color if is_active else ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)
            bg_col = ft.Colors.with_opacity(0.08, theme_color) if is_active else ft.Colors.with_opacity(0.02, ft.Colors.ON_SURFACE)

            def select_opt(e):
                nonlocal selected_visibility
                selected_visibility = key
                access_card.content.controls[2] = render_visibility_row()
                page.update()

            return ft.Container(
                expand=True,
                bgcolor=bg_col,
                border_radius=10,
                border=ft.Border.all(1.5 if is_active else 1, border_col),
                padding=ft.Padding.all(12),
                ink=True,
                on_click=select_opt,
                content=ft.Row([
                    ft.Container(
                        width=32, height=32, border_radius=16,
                        bgcolor=ft.Colors.with_opacity(0.12, theme_color if is_active else ft.Colors.ON_SURFACE),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(icon, size=16, color=theme_color if is_active else ft.Colors.ON_SURFACE_VARIANT),
                    ),
                    ft.Column([
                        ft.Row([
                            ft.Text(title, size=12, weight=ft.FontWeight.BOLD, color=theme_color if is_active else ft.Colors.ON_SURFACE),
                            ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=14, color=theme_color) if is_active else ft.Container(),
                        ], spacing=4),
                        ft.Text(subtitle, size=10, color=ft.Colors.ON_SURFACE_VARIANT, max_lines=2),
                    ], spacing=2, expand=True),
                ], spacing=10),
            )

        def render_visibility_row():
            return ft.ResponsiveRow([
                ft.Container(content=build_visibility_option("false", "Draft / Private", "Visible only to course authors & admins", ft.Icons.EDIT_NOTE_ROUNDED), col={"xs": 12, "md": 4}),
                ft.Container(content=build_visibility_option("organisation", "Campus Track", "Restricted to verified organisation members", ft.Icons.LOCK_ROUNDED), col={"xs": 12, "md": 4}),
                ft.Container(content=build_visibility_option("public", "Public Track", "Discoverable and open across Nu-Age", ft.Icons.PUBLIC_ROUNDED), col={"xs": 12, "md": 4}),
            ], spacing=8, run_spacing=8)

        # Teacher dropdown
        teacher_options = [
            ft.dropdown.Option(
                key=t["id"],
                text=f"{t.get('first_name', '')} {t.get('last_name', '')}".strip() or t.get("email", "Faculty"),
            )
            for t in teachers if isinstance(t, dict) and "id" in t
        ]
        teacher_options.insert(0, ft.dropdown.Option(key="none", text="None (Unassigned)"))

        teacher_dropdown = ft.Dropdown(
            label="Assigned Lead Instructor",
            value=current_teacher_id if any(opt.key == current_teacher_id for opt in teacher_options) else "none",
            options=teacher_options,
            leading_icon=ft.Icons.PERSON_ROUNDED,
            border_radius=10,
            border_color=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE),
            focused_border_color=theme_color,
            dense=True,
            expand=True,
        )

        save_access_btn = ft.FilledButton(
            "Save Access",
            icon=ft.Icons.CHECK_ROUNDED,
            style=ft.ButtonStyle(
                bgcolor=theme_color,
                shape=ft.RoundedRectangleBorder(radius=8),
                padding=ft.Padding.symmetric(horizontal=14, vertical=8),
            ),
        )

        async def on_save_access(e):
            save_access_btn.disabled = True
            save_access_btn.text = "Saving…"
            page.update()

            try:
                t_val = teacher_dropdown.value if teacher_dropdown.value != "none" else None
                p1 = update_course_settings(token, course_id, {"public": selected_visibility})
                p2 = update_course_settings(token, course_id, {"teacher_id": t_val})
                await asyncio.gather(p1, p2)
                show_toast("Access & Instructor governance saved.")
            except Exception as ex:
                show_error_toast(f"Failed to update access: {ex}")
            finally:
                save_access_btn.disabled = False
                save_access_btn.text = "Save Access"
                page.update()

        save_access_btn.on_click = lambda e: page.run_task(on_save_access, e)

        access_card = ft.Container(
            margin=ft.Margin.symmetric(horizontal=16, vertical=6),
            bgcolor=ft.Colors.SURFACE,
            border_radius=14,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            padding=ft.Padding.all(16),
            content=ft.Column([
                _card_header(
                    "Access & Governance",
                    "Configure course discoverability and faculty leadership",
                    save_access_btn,
                ),
                ft.Container(height=6),
                render_visibility_row(),
                ft.Container(height=10),
                teacher_dropdown,
            ], spacing=6),
        )

        # ── CARD 3: STUDENT ENROLLMENT MANAGER ────────────────────────────────
        def open_enrollment_dialog(e):
            search_field = ft.TextField(
                hint_text="Search students by name or email…",
                prefix_icon=ft.Icons.SEARCH_ROUNDED,
                dense=True,
                border_radius=10,
                border_color=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE),
                focused_border_color=theme_color,
                expand=True,
            )

            student_rows_container = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO)
            student_checkboxes: dict = {}
            initial_states: dict = {}
            all_students_cache: list = []

            modal_loader = ft.Container(
                alignment=ft.Alignment.CENTER,
                padding=24,
                content=ft.ProgressRing(color=theme_color, width=32, height=32),
            )

            def close_dialog(ev=None):
                enroll_dlg.open = False
                page.update()

            def update_rendered_students():
                q = search_field.value.strip().lower()
                student_rows_container.controls.clear()

                filtered = [
                    s for s in all_students_cache
                    if not q or (q in (s.get("name") or "").lower() or q in (s.get("email") or "").lower())
                ]

                if not filtered:
                    student_rows_container.controls.append(
                        ft.Container(
                            padding=24,
                            alignment=ft.Alignment.CENTER,
                            content=ft.Column([
                                ft.Icon(ft.Icons.PEOPLE_OUTLINE_ROUNDED, size=32, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text("No students match your search.", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
                        )
                    )
                else:
                    for s in filtered:
                        s_id = s.get("id")
                        cb = student_checkboxes.get(s_id)
                        name_str = s.get("name") or "Unnamed Student"
                        email_str = s.get("email") or ""
                        initials = "".join([part[0].upper() for part in name_str.split()[:2]]) or "S"

                        student_rows_container.controls.append(
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                                border_radius=8,
                                bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
                                content=ft.Row([
                                    cb,
                                    ft.CircleAvatar(
                                        radius=14,
                                        bgcolor=ft.Colors.with_opacity(0.12, theme_color),
                                        content=ft.Text(initials, size=10, weight=ft.FontWeight.BOLD, color=theme_color),
                                    ),
                                    ft.Column([
                                        ft.Text(name_str, size=12, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                                        ft.Text(email_str, size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ], spacing=1, expand=True),
                                ], spacing=10),
                            )
                        )
                page.update()

            search_field.on_change = lambda _: update_rendered_students()

            # Select / Deselect All
            def toggle_all(ev):
                all_checked = all(cb.value for cb in student_checkboxes.values())
                target_state = not all_checked
                for cb in student_checkboxes.values():
                    cb.value = target_state
                page.update()

            toggle_all_btn = ft.TextButton(
                "Toggle All",
                icon=ft.Icons.SELECT_ALL_ROUNDED,
                on_click=toggle_all,
            )

            confirm_btn = ft.FilledButton(
                "Apply Changes",
                style=ft.ButtonStyle(bgcolor=theme_color, shape=ft.RoundedRectangleBorder(radius=8)),
            )

            async def save_enrollments(ev):
                confirm_btn.disabled = True
                confirm_btn.text = "Saving…"
                page.update()

                to_enroll = []
                to_unenroll = []
                for s_id, cb in student_checkboxes.items():
                    was_enrolled = initial_states.get(s_id, False)
                    is_now = cb.value
                    if is_now and not was_enrolled:
                        to_enroll.append(s_id)
                    elif not is_now and was_enrolled:
                        to_unenroll.append(s_id)

                if not to_enroll and not to_unenroll:
                    show_toast("No enrollment modifications were made.")
                    close_dialog()
                    return

                msgs = []
                if to_enroll:
                    try:
                        await bulk_enrol_students(token, course_id, payload={"student_ids": to_enroll}, params={})
                        msgs.append(f"Enrolled {len(to_enroll)} students")
                    except Exception as ex:
                        show_error_toast(f"Enroll error: {ex}")

                if to_unenroll:
                    try:
                        await bulk_unenrol_students(token, course_id, payload={"student_ids": to_unenroll}, params={})
                        msgs.append(f"Unenrolled {len(to_unenroll)} students")
                    except Exception as ex:
                        show_error_toast(f"Unenroll error: {ex}")

                close_dialog()
                if msgs:
                    show_toast(" · ".join(msgs))

            confirm_btn.on_click = lambda ev: page.run_task(save_enrollments, ev)

            enroll_dlg = ft.AlertDialog(
                modal=True,
                bgcolor=ft.Colors.SURFACE,
                shape=ft.RoundedRectangleBorder(radius=16),
                title=ft.Row([
                    ft.Row([
                        ft.Icon(ft.Icons.PEOPLE_ROUNDED, size=20, color=theme_color),
                        ft.Text("Manage Course Cohort", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ], spacing=8),
                    ft.IconButton(ft.Icons.CLOSE_ROUNDED, icon_size=18, on_click=close_dialog),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                content=ft.Container(
                    width=460,
                    height=440,
                    content=ft.Column([
                        ft.Row([search_field, toggle_all_btn], spacing=8),
                        ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                        ft.Container(expand=True, content=modal_loader),
                    ], spacing=8),
                ),
                actions=[
                    ft.TextButton("Cancel", on_click=close_dialog),
                    confirm_btn,
                ],
            )

            page.overlay.append(enroll_dlg)
            enroll_dlg.open = True
            page.update()

            async def fetch_dialog_students():
                try:
                    res = await get_enrolled_org_students(token, course_id, params={})
                    st_list = res.get("students", []) if isinstance(res, dict) else (res if isinstance(res, list) else [])
                    all_students_cache.extend(st_list)

                    for s in st_list:
                        s_id = s.get("id")
                        is_en = bool(s.get("is_enrolled", False))
                        initial_states[s_id] = is_en
                        student_checkboxes[s_id] = ft.Checkbox(
                            value=is_en,
                            fill_color={"selected": theme_color, "": ft.Colors.TRANSPARENT},
                            check_color=ft.Colors.WHITE,
                        )

                    enroll_dlg.content.content.controls[2] = ft.Container(expand=True, content=student_rows_container)
                    update_rendered_students()
                except Exception as ex:
                    enroll_dlg.content.content.controls[2] = ft.Container(
                        alignment=ft.Alignment.CENTER,
                        content=ft.Text(f"Failed to fetch students: {ex}", size=12, color=ft.Colors.RED_400),
                    )
                    page.update()

            page.run_task(fetch_dialog_students)

        enroll_card = ft.Container(
            margin=ft.Margin.symmetric(horizontal=16, vertical=6),
            bgcolor=ft.Colors.SURFACE,
            border_radius=14,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            padding=ft.Padding.all(16),
            content=ft.Column([
                _card_header(
                    "Student Cohort & Enrollments",
                    "Batch enroll or remove academy students from this course",
                ),
                ft.Container(height=6),
                ft.Container(
                    padding=ft.Padding.all(12),
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                    content=ft.Row([
                        ft.Icon(ft.Icons.PEOPLE_ALT_ROUNDED, size=24, color=theme_color),
                        ft.Column([
                            ft.Text("Enrolled Student Registry", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                            ft.Text("Search and toggle member access across your academy directory.", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ], spacing=2, expand=True),
                        ft.FilledButton(
                            "Manage Roster",
                            icon=ft.Icons.EDIT_ROUNDED,
                            style=ft.ButtonStyle(
                                bgcolor=theme_color,
                                shape=ft.RoundedRectangleBorder(radius=8),
                                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                            ),
                            on_click=open_enrollment_dialog,
                        ),
                    ], spacing=12),
                ),
            ], spacing=6),
        )

        # ── CARD 4: DANGER ZONE ───────────────────────────────────────────────
        def open_delete_modal(e):
            def close_del(ev=None):
                del_dlg.open = False
                page.update()

            async def confirm_delete_action(ev):
                del_btn.disabled = True
                del_btn.text = "Deleting…"
                page.update()
                try:
                    await delete_course(token, course_id)
                    close_del()
                    show_toast("Course permanently deleted.", ft.Colors.RED_700)
                    page.go(f"/organisations/{effective_org_id}" if effective_org_id else "/organisations")
                except Exception as ex:
                    show_error_toast(f"Failed to delete course: {ex}")
                    del_btn.disabled = False
                    del_btn.text = "Yes, Permanently Delete"
                    page.update()

            del_btn = ft.ElevatedButton(
                "Yes, Permanently Delete",
                bgcolor=ft.Colors.RED_700,
                color=ft.Colors.WHITE,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                on_click=lambda ev: page.run_task(confirm_delete_action, ev),
            )

            del_dlg = ft.AlertDialog(
                modal=True,
                bgcolor=ft.Colors.SURFACE,
                shape=ft.RoundedRectangleBorder(radius=16),
                title=ft.Row([
                    ft.Row([
                        ft.Icon(ft.Icons.WARNING_ROUNDED, size=20, color=ft.Colors.RED_600),
                        ft.Text("Delete Course", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_600),
                    ], spacing=8),
                    ft.IconButton(ft.Icons.CLOSE_ROUNDED, icon_size=18, on_click=close_del),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                content=ft.Container(
                    width=380,
                    content=ft.Column([
                        ft.Text("Are you sure you want to delete this course? This action is irreversible.", size=13, color=ft.Colors.ON_SURFACE),
                        ft.Container(
                            padding=ft.Padding.all(10),
                            border_radius=8,
                            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.RED_400),
                            content=ft.Text(
                                "All curriculum modules, lessons, questions, and learner progress records will be completely removed.",
                                size=11, color=ft.Colors.RED_700, weight=ft.FontWeight.W_500,
                            ),
                        ),
                    ], spacing=10),
                ),
                actions=[
                    ft.TextButton("Cancel", on_click=close_del),
                    del_btn,
                ],
            )

            page.overlay.append(del_dlg)
            del_dlg.open = True
            page.update()

        danger_card = ft.Container(
            margin=ft.Margin.symmetric(horizontal=16, vertical=6),
            bgcolor=ft.Colors.SURFACE,
            border_radius=14,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.RED_400)),
            padding=ft.Padding.all(16),
            content=ft.Column([
                _card_header(
                    "Danger Zone",
                    "Irreversible destruction of curriculum content and student records",
                ),
                ft.Container(height=6),
                ft.Row([
                    ft.Column([
                        ft.Text("Permanently Remove Course", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_700),
                        ft.Text("Once deleted, this curriculum and all student grade history cannot be recovered.", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                    ], spacing=2, expand=True),
                    ft.OutlinedButton(
                        "Delete Course",
                        icon=ft.Icons.DELETE_FOREVER_ROUNDED,
                        style=ft.ButtonStyle(
                            color=ft.Colors.RED_700,
                            side=ft.BorderSide(1, ft.Colors.RED_400),
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                        ),
                        on_click=open_delete_modal,
                    ),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ], spacing=6),
        )

        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                hero_card,
                ft.Container(
                    alignment=ft.Alignment.CENTER,
                    content=ft.Container(
                        width=860,
                        content=ft.Column([
                            general_card,
                            access_card,
                            enroll_card,
                            danger_card,
                            ft.Container(height=32),
                        ], spacing=4),
                    ),
                ),
            ],
            spacing=0,
        )

    page.run_task(load_all_data)

    target_route = f"/organisations/{effective_org_id}/courses/{course_id}/settings" if effective_org_id else f"/courses/{course_id}/settings"

    return ft.View(
        route=target_route,
        padding=0,
        bottom_appbar=app_bar,
        controls=[
            ft.SafeArea(
                expand=True,
                content=content_socket,
            )
        ],
    )


def _error_view(course_id: str, message: str) -> ft.View:
    return ft.View(
        route=f"/courses/{course_id}/settings",
        padding=0,
        controls=[
            ft.SafeArea(
                expand=True,
                content=ft.Container(
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=12,
                        controls=[
                            ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, size=52, color=ft.Colors.RED_400),
                            ft.Text(message, size=15, weight=ft.FontWeight.W_500, color=ft.Colors.ON_SURFACE),
                        ],
                    ),
                ),
            )
        ],
    )