import flet as ft

from src.components.bottom_appbar import get_bottom_appbar
from src.requests.Courses import get_categories, get_courses, update_course_settings, delete_course
from src.requests.organisations import get_organisation_members
from src.requests.enrollments import bulk_enrol_students, bulk_unenrol_students, get_enrolled_students


# =========================================================
# SECTION 1: CONSTANTS
# =========================================================
_BORDER_RADIUS = 12
_SECTION_SPACING = 20
_INPUT_STYLE = {
    "border_color": ft.Colors.OUTLINE_VARIANT,
    "focused_border_color": ft.Colors.PRIMARY,
    "border_radius": _BORDER_RADIUS,
}


# =========================================================
# SECTION 2: MAIN VIEW FUNCTION
# =========================================================
async def course_settings_view(page: ft.Page, course_id: str, org_id: str) -> ft.View:

    # ── Auth token ────────────────────────────────────────────────────────────
    try:
        token = await page.shared_preferences.get("auth_token")
        if not token:
            raise ValueError("Missing auth token")
    except Exception:
        return _error_view(course_id, "Authentication failed. Please log in again.")

    # =========================================================
    # SECTION 3: API WRAPPERS (with error handling)
    # =========================================================
    async def _get_categories() -> list:
        try:
            result = await get_categories(token, None)
            return result or []
        except Exception as ex:
            _log_error("get_categories", ex)
            return []

    async def _get_teachers() -> list:
        try:
            result = await get_organisation_members(token, id=org_id, teachers=True)
            print(result)
            return result or []
        except Exception as ex:
            _log_error("get_teachers", ex)
            return []

    async def _get_org_students() -> list:
        try:
            result = await get_organisation_members(token, id=org_id, students=True)
            return result or []
        except Exception as ex:
            _log_error("get_org_students", ex)
            return []

    async def _save_setting(key: str, value) -> bool:
        try:
            value = None if value in ["None", "none", "false", "null"] else value
            await update_course_settings(token, course_id, {key: value})
            return True  # ← if no exception, it succeeded
        except Exception as ex:
            _log_error(f"save_setting:{key}", ex)
            return False

    async def _enroll_students(student_ids: list) -> tuple[bool, str]:
        try:
            await bulk_enrol_students(
                token, course_id,
                payload={"student_ids": student_ids},
                params={}
            )
            return True, f"Enrolled {len(student_ids)}"
        except Exception as ex:
            _log_error("enroll_students", ex)
            return False, "Enrollment failed. Please try again."

    async def _unenroll_students(student_ids: list) -> tuple[bool, str]:
        try:
            await bulk_unenrol_students(
                token, course_id,
                payload={"student_ids": student_ids},
                params={}
            )
            return True, f"Removed {len(student_ids)}"
        except Exception as ex:
            _log_error("unenroll_students", ex)
            return False, "Unenrollment failed. Please try again."

    async def _delete_course() -> bool:
        try:
            await delete_course(token, course_id)
            return True  # ← same logic
        except Exception as ex:
            _log_error("delete_course", ex)
            return False

    # ── Fetch core course data ────────────────────────────────────────────────
    try:
        raw = await get_courses(token, params={"id": course_id})
        course_data = raw[0] if raw else None
    except Exception as ex:
        _log_error("get_courses", ex)
        course_data = None

    if not course_data:
        return _error_view(course_id, "Course not found or could not be loaded.")

    # =========================================================
    # SECTION 4: SHARED UI HELPERS
    # =========================================================
    bottom_bar = get_bottom_appbar(page)

    # Lazy-load socket — shown while background data loads
    content_socket = ft.Container(
        expand=True,
        alignment=ft.Alignment(0, 0),
        content=ft.ProgressRing(color=ft.Colors.PRIMARY),
    )

    def show_toast(message: str, color=ft.Colors.GREEN_700):
        snack = ft.SnackBar(
            content=ft.Text(message, color=ft.Colors.WHITE),
            bgcolor=color,
            duration=3000,
        )
        page.overlay.append(snack)
        snack.open = True
        page.update()

    def show_error_toast(message: str):
        show_toast(message, color=ft.Colors.RED_700)

    def _save_btn(on_click_fn) -> ft.ElevatedButton:
        """Factory for uniform Save buttons."""
        return ft.ElevatedButton(
            content=ft.Text("Save", color=ft.Colors.ON_PRIMARY, weight=ft.FontWeight.W_600),
            bgcolor=ft.Colors.PRIMARY,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            on_click=on_click_fn,
        )

    def _set_btn_loading(btn: ft.ElevatedButton):
        btn.disabled = True
        btn.content = ft.ProgressRing(width=16, height=16, color=ft.Colors.ON_PRIMARY)
        page.update()

    def _set_btn_done(btn: ft.ElevatedButton, label="Save"):
        btn.disabled = False
        btn.content = ft.Text(label, color=ft.Colors.ON_PRIMARY, weight=ft.FontWeight.W_600)
        page.update()

    def create_section(
        title: str,
        description: str,
        content: ft.Control,
        is_danger: bool = False,
    ) -> ft.Container:
        title_color    = ft.Colors.RED_700 if is_danger else ft.Colors.ON_SURFACE
        border_color   = ft.Colors.RED_200 if is_danger else ft.Colors.OUTLINE_VARIANT
        return ft.Container(
            bgcolor=ft.Colors.SURFACE,
            border_radius=15,
            padding=20,
            border=ft.border.all(1, border_color),
            content=ft.Column(
                spacing=15,
                controls=[
                    ft.Column(
                        spacing=4,
                        controls=[
                            ft.Text(title, size=16, weight=ft.FontWeight.W_700, color=title_color),
                            ft.Text(description, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                    ),
                    ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT),
                    content,
                ],
            ),
        )

    # =========================================================
    # SECTION 5: GENERAL SETTINGS
    # =========================================================
    name_input = ft.TextField(
        value=course_data.get("name", ""),
        label="Course Name",
        expand=True,
        **_INPUT_STYLE,
    )
    category_dropdown = ft.Dropdown(
        label="Category",
        value=course_data.get("category", {}).get("name"),
        expand=True,
        **_INPUT_STYLE,
    )

    async def save_name(e):
        btn = e.control
        name = name_input.value.strip()
        if not name:
            show_error_toast("Course name cannot be empty.")
            return
        _set_btn_loading(btn)
        ok = await _save_setting("name", name)
        _set_btn_done(btn)
        show_toast("Course name updated.") if ok else show_error_toast("Failed to update course name.")

    async def save_category(e):
        btn = e.control
        if not category_dropdown.value:
            show_error_toast("Please select a category.")
            return
        _set_btn_loading(btn)
        ok = await _save_setting("category", category_dropdown.value)
        _set_btn_done(btn)
        show_toast("Category updated.") if ok else show_error_toast("Failed to update category.")

    save_name_btn     = _save_btn(lambda e: page.run_task(save_name, e))
    save_category_btn = _save_btn(lambda e: page.run_task(save_category, e))

    general_section = create_section(
        title="General Information",
        description="Update the foundational details of this course.",
        content=ft.Column(
            spacing=15,
            controls=[
                ft.Row([name_input, save_name_btn]),
                ft.Row([category_dropdown, save_category_btn]),
            ],
        ),
    )

    # =========================================================
    # SECTION 6: ACCESS CONTROLS
    # =========================================================
    public_radio = ft.RadioGroup(
        value=course_data.get("public"),
        content=ft.Row(
            wrap=True,
            controls=[
                ft.Radio(value=False,          label="Private",      fill_color=ft.Colors.PRIMARY),
                ft.Radio(value="organization", label="Organization", fill_color=ft.Colors.PRIMARY),
                ft.Radio(value=True,           label="Public",       fill_color=ft.Colors.PRIMARY),
            ],
        ),
    )

    teacher_dropdown = ft.Dropdown(
        label="Assigned Instructor",
        value=course_data.get("teacher_id"),
        expand=True,
        **_INPUT_STYLE,
    )

    async def save_public(e):
        btn = e.control
        _set_btn_loading(btn)
        ok = await _save_setting("public", public_radio.value)
        _set_btn_done(btn)
        show_toast("Visibility updated.") if ok else show_error_toast("Failed to update visibility.")

    async def save_teacher(e):
        btn = e.control
        if not teacher_dropdown.value:
            show_error_toast("Please select an instructor.")
            return
        _set_btn_loading(btn)
        ok = await _save_setting("teacher_id", teacher_dropdown.value)
        _set_btn_done(btn)
        show_toast("Instructor reassigned.") if ok else show_error_toast("Failed to reassign instructor.")

    save_public_btn  = _save_btn(lambda e: page.run_task(save_public, e))
    save_teacher_btn = _save_btn(lambda e: page.run_task(save_teacher, e))

    access_section = create_section(
        title="Access & Instructors",
        description="Control who can view this course and who is managing it.",
        content=ft.Column(
            spacing=20,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(
                            expand=True,
                            spacing=4,
                            controls=[
                                ft.Text("Course Visibility", weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                                public_radio,
                            ],
                        ),
                        save_public_btn,
                    ],
                ),
                ft.Row([teacher_dropdown, save_teacher_btn]),
            ],
        ),
    )

    # =========================================================
    # SECTION 7: ENROLLMENT MANAGER
    # =========================================================
    def open_enrollment_manager(e):
        enrollment_list_view = ft.ListView(spacing=5, expand=True)
        student_checkboxes: dict = {}
        initial_states: dict     = {}

        # ── Select-all checkbox ───────────────────────────────────────────────
        def toggle_all(e):
            for cb in student_checkboxes.values():
                cb.value = master_checkbox.value
            page.update()

        master_checkbox = ft.Checkbox(
            label="Select / Deselect All",
            fill_color={"selected": ft.Colors.PRIMARY, "": ft.Colors.WHITE},
            check_color=ft.Colors.WHITE,
            on_change=toggle_all,
        )

        action_btn = ft.ElevatedButton(
            "Save Changes",
            bgcolor=ft.Colors.PRIMARY,
            color=ft.Colors.WHITE,
            disabled=True,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
        )
        loading_ring    = ft.Container(
            content=ft.ProgressRing(color=ft.Colors.PRIMARY),
            alignment=ft.Alignment(0, 0),
            expand=True,
            padding=20,
        )
        empty_state     = ft.Container(
            visible=False,
            alignment=ft.Alignment(0, 0),
            expand=True,
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.PEOPLE_ROUNDED, size=40, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text("No students found.", color=ft.Colors.ON_SURFACE_VARIANT, size=13),
                ],
            ),
        )
        error_state     = ft.Container(
            visible=False,
            alignment=ft.Alignment(0, 0),
            expand=True,
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, size=40, color=ft.Colors.ERROR),
                    ft.Text("Failed to load students.", color=ft.Colors.ERROR, size=13),
                ],
            ),
        )
        content_wrapper = ft.Column(
            visible=False,
            expand=True,
            controls=[
                master_checkbox,
                ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT),
                enrollment_list_view,
            ],
        )

        def close_modal(e=None):
            dlg.open = False
            page.update()

        async def execute_enrollment(e):
            btn = e.control
            btn.disabled = True
            btn.text = "Saving…"
            page.update()

            to_enroll   = []
            to_unenroll = []

            for s_id, cb in student_checkboxes.items():
                was_enrolled = initial_states.get(s_id, False)
                is_now       = cb.value
                if is_now and not was_enrolled:
                    to_enroll.append(s_id)
                elif not is_now and was_enrolled:
                    to_unenroll.append(s_id)

            if not to_enroll and not to_unenroll:
                show_toast("No changes to save.")
                close_modal()
                return

            msgs   = []
            errors = []

            if to_enroll:
                ok, msg = await _enroll_students(to_enroll)
                (msgs if ok else errors).append(msg)

            if to_unenroll:
                ok, msg = await _unenroll_students(to_unenroll)
                (msgs if ok else errors).append(msg)

            close_modal()
            if msgs:
                show_toast(" · ".join(msgs))
            if errors:
                show_error_toast(" · ".join(errors))

        dlg = ft.AlertDialog(
            modal=True,
            bgcolor=ft.Colors.SURFACE,
            title=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Text("Manage Enrollments", weight=ft.FontWeight.BOLD,
                            color=ft.Colors.ON_SURFACE, size=18, expand=True),
                    ft.IconButton(ft.Icons.CLOSE_ROUNDED, on_click=close_modal),
                ],
            ),
            content=ft.Container(
                width=340,
                height=420,
                content=ft.Column(
                    expand=True,
                    controls=[loading_ring, empty_state, error_state, content_wrapper],
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=close_modal),
                action_btn,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        page.overlay.append(dlg)
        dlg.open = True
        page.update()

        async def fetch_and_populate():
            try:
                students = await get_enrolled_students(token, course_id, params={})
            except Exception as ex:
                _log_error("get_enrolled_students", ex)
                students = None

            loading_ring.visible = False

            if students is None:
                # API error
                error_state.visible = True
                page.update()
                return

            if not students:
                # No students in org
                empty_state.visible = True
                page.update()
                return

            for student in students:
                try:
                    is_enrolled = student.get("is_enrolled", False)
                    s_id        = student["id"]
                    initial_states[s_id] = is_enrolled

                    cb = ft.Checkbox(
                        value=is_enrolled,
                        fill_color={"selected": ft.Colors.PRIMARY, "": ft.Colors.WHITE},
                        check_color=ft.Colors.WHITE,
                    )
                    student_checkboxes[s_id] = cb

                    enrollment_list_view.controls.append(
                        ft.Container(
                            padding=ft.padding.symmetric(vertical=5),
                            content=ft.Row([
                                cb,
                                ft.Column(
                                    expand=True,
                                    spacing=2,
                                    controls=[
                                        ft.Text(student.get("name", "Unknown"), size=14,
                                                weight=ft.FontWeight.W_600,
                                                color=ft.Colors.ON_SURFACE),
                                        ft.Text(student.get("email", "—"), size=12,
                                                color=ft.Colors.ON_SURFACE_VARIANT),
                                    ],
                                ),
                            ]),
                        )
                    )
                except (KeyError, TypeError) as ex:
                    _log_error(f"render_student_row:{student}", ex)
                    continue

            content_wrapper.visible = True
            action_btn.disabled     = False
            action_btn.on_click     = execute_enrollment
            page.update()

        page.run_task(fetch_and_populate)

    enrollment_section = create_section(
        title="Student Enrollments",
        description="Batch enroll or remove students from your organisation.",
        content=ft.ElevatedButton(
            "Open Enrollment Manager",
            width=float("inf"),
            icon=ft.Icons.PEOPLE_ALT_ROUNDED,
            icon_color=ft.Colors.ON_SURFACE,
            color=ft.Colors.ON_SURFACE,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            on_click=open_enrollment_manager,
        ),
    )

    # =========================================================
    # SECTION 8: DANGER ZONE
    # =========================================================
    def open_delete_modal(e):
        def close_delete_modal(e=None):
            dlg_delete.open = False
            page.update()

        async def confirm_delete(e):
            btn = e.control
            btn.disabled = True
            btn.text = "Deleting…"
            page.update()

            ok = await _delete_course()
            close_delete_modal()

            if ok:
                show_toast("Course deleted.", ft.Colors.RED_700)
                page.go("/organisations")
            else:
                show_error_toast("Failed to delete course. Please try again.")

        dlg_delete = ft.AlertDialog(
            modal=True,
            bgcolor=ft.Colors.SURFACE,
            title=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Text("Delete Course", color=ft.Colors.RED_700,
                            weight=ft.FontWeight.BOLD, expand=True),
                    ft.IconButton(ft.Icons.CLOSE_ROUNDED, on_click=close_delete_modal),
                ],
            ),
            content=ft.Container(
                width=340,
                content=ft.Column(
                    spacing=12,
                    controls=[
                        ft.Text(
                            "Are you absolutely sure? This action cannot be undone.",
                            color=ft.Colors.ON_SURFACE,
                        ),
                        ft.Container(
                            bgcolor=ft.Colors.RED_50,
                            border_radius=8,
                            padding=ft.padding.all(10),
                            content=ft.Row(
                                spacing=8,
                                controls=[
                                    ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED,
                                            color=ft.Colors.RED_700, size=18),
                                    ft.Text(
                                        "All modules, question banks and student records will be permanently wiped.",
                                        size=12,
                                        color=ft.Colors.RED_700,
                                        expand=True,
                                    ),
                                ],
                            ),
                        ),
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=close_delete_modal),
                ft.ElevatedButton(
                    "Yes, Delete Everything",
                    bgcolor=ft.Colors.RED_700,
                    color=ft.Colors.WHITE,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                    on_click=confirm_delete,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        page.overlay.append(dlg_delete)
        dlg_delete.open = True
        page.update()

    danger_section = create_section(
        title="Danger Zone",
        description="Irreversible actions regarding this course.",
        is_danger=True,
        content=ft.ElevatedButton(
            "Delete Course",
            width=float("inf"),
            icon=ft.Icons.DELETE_FOREVER_ROUNDED,
            icon_color=ft.Colors.RED_700,
            bgcolor=ft.Colors.RED_50,
            color=ft.Colors.RED_700,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
            on_click=open_delete_modal,
        ),
    )

    # =========================================================
    # SECTION 9: DATA FETCH & LAYOUT ASSEMBLY
    # =========================================================
    async def load_initial_data():
        try:
            categories, teachers = await _parallel_fetch(
                _get_categories(),
                _get_teachers(),
            )
        except Exception as ex:
            _log_error("load_initial_data", ex)
            categories, teachers = [], []

        # Populate dropdowns (gracefully handle empty lists)
        if categories:
            category_dropdown.options = [ft.dropdown.Option(c["name"]) for c in categories]
        else:
            category_dropdown.hint_text = "No categories available"
            category_dropdown.disabled  = True

        if teachers:
            teacher_dropdown.options = [
                ft.dropdown.Option(
                    key=t["id"],
                    text=f"{t.get('first_name', '')} {t.get('last_name', '')}".strip().capitalize()
                    or "Unnamed",
                )
                for t in teachers
            ]
            teacher_dropdown.options.insert(
                0, ft.dropdown.Option(key="none", text="None (Unassigned)")
            )
        else:
            teacher_dropdown.hint_text = "No instructors available"
            teacher_dropdown.disabled  = True

        # ── Header ───────────────────────────────────────────────────────────
        header = ft.Container(
            bgcolor=ft.Colors.PRIMARY,
            height=85,
            border_radius=ft.BorderRadius(
                top_left=0, top_right=0, bottom_left=30, bottom_right=30
            ),
            padding=ft.Padding(top=10, left=15, right=25, bottom=15),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.IconButton(
                        ft.Icons.ARROW_BACK_ROUNDED,
                        icon_color=ft.Colors.WHITE,
                        on_click=lambda _: page.go("/organisations"),
                    ),
                    ft.Text(
                        "Course Settings",
                        size=20,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE,
                    ),
                    ft.Container(width=40),  # balance the back button
                ],
            ),
        )

        final_layout = ft.Column(
            expand=True,
            spacing=0,
            controls=[
                header,
                ft.Container(
                    expand=True,
                    padding=ft.padding.all(20),
                    content=ft.Column(
                        scroll=ft.ScrollMode.AUTO,
                        spacing=_SECTION_SPACING,
                        controls=[
                            general_section,
                            access_section,
                            enrollment_section,
                            danger_section,
                            ft.Container(height=20),
                        ],
                    ),
                ),
            ],
        )

        # Hot-swap loading socket → real UI
        content_socket.alignment = None
        content_socket.content   = final_layout
        page.update()

    page.run_task(load_initial_data)

    return ft.View(
        route=f"/organisations/{org_id}/courses/{course_id}/settings",
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        padding=0,
        bottom_appbar=bottom_bar,
        controls=[
            ft.SafeArea(
                expand=True,
                content=content_socket,
            )
        ],
    )


# =========================================================
# SECTION 10: UTILITIES
# =========================================================
def _error_view(course_id: str, message: str) -> ft.View:
    """Full-screen error fallback view."""
    return ft.View(
        route=f"/courses/{course_id}/settings",
        bgcolor=ft.Colors.SURFACE_CONTAINER,
        controls=[
            ft.Container(
                expand=True,
                alignment=ft.Alignment(0, 0),
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    mainAxisAlignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED,
                                size=52, color=ft.Colors.ERROR),
                        ft.Text(message, color=ft.Colors.ERROR, size=16,
                                text_align=ft.TextAlign.CENTER),
                    ],
                ),
            )
        ],
    )


def _log_error(context: str, ex: Exception):
    """Centralised error logger — swap for Sentry / logging as needed."""
    print(f"[ERROR] [{context}] {type(ex).__name__}: {ex}")


async def _parallel_fetch(*coros):
    """Run multiple coroutines concurrently and return their results."""
    import asyncio
    return await asyncio.gather(*coros, return_exceptions=False)