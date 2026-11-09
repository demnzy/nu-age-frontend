"""
Course Space Hub View for Nu-Age LMS.

A living, asynchronous course hub ("Classroom") featuring:
1. Multi-course syllabus navigation with two-tier Course & Module segmentation filters.
2. Asynchronous Materials Vault: tutor uploads anytime (via BunnyCDN) segmented by course and module,
   with relative timestamps, search filtering, and 1-tap open/download.
3. CBT-Style Topic Drills & Formative Assessments:
   - Super-Admin-grade AI Document & Text Ingestion (PDF, scanned PDF, DOCX, TXT, MD, Images)
     supporting both Past Question Extraction and AI Question Generation from lecture notes.
   - Dual-Pane CBT Question Curator Studio (4 or 5 options A-E, inline diagram figures, explanations).
   - Interactive Student CBT Drill Runner with live countdown timer, inline diagrams, and review breakdown.
   - Tutor Drill Results & Gradebook Analytics modal.
4. Live Classes & Office Hours: scheduled Google Meet / Zoom sessions with upcoming/past segmentation.
5. Space Management & Member Roster: link/unlink courses, edit space settings, regenerate invite codes,
   and manage co-tutors and students.
"""

import asyncio
import urllib.parse
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

import flet as ft

from src.requests.course_spaces import (
    get_space_details,
    update_course_space,
    delete_course_space,
    regenerate_space_code,
    join_course_space,
    leave_course_space,
    add_courses_to_space,
    remove_course_from_space,
    get_space_members,
    update_space_member_role,
    remove_space_member,
    invite_space_members,
    get_space_materials,
    upload_space_material,
    delete_space_material,
    get_space_quizzes,
    get_quiz_for_taking,
    submit_quiz_attempt,
    create_topic_quiz,
    update_space_quiz,
    delete_space_quiz,
    get_space_quiz_attempts,
    ai_parse_space_quiz_text,
    ai_parse_space_quiz_file,
    upload_space_quiz_image,
    get_scheduled_sessions,
    schedule_live_session,
    cancel_scheduled_session,
)
from src.requests.Courses import get_courses
from src.components.question_curator_modal import show_question_curator_dialog
from src.utils.file_opener import (
    safe_set_clipboard,
    show_page_snackbar,
    open_or_download_asset,
    safe_open_dialog,
    safe_close_dialog,
)
from src.utils.dropdown_theme import apply_dropdown_theme


def _format_datetime(dt_str: Optional[str]) -> str:
    if not dt_str:
        return "TBD"
    try:
        dt = datetime.fromisoformat(str(dt_str).replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y • %I:%M %p")
    except Exception:
        return str(dt_str)[:16]


def _format_relative_time(dt_str: Optional[str]) -> str:
    if not dt_str:
        return "Recently"
    try:
        dt = datetime.fromisoformat(str(dt_str).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        diff = datetime.now(timezone.utc) - dt
        secs = int(diff.total_seconds())
        if secs < 60:
            return "Just now"
        if secs < 3600:
            return f"{secs // 60}m ago"
        if secs < 86400:
            return f"{secs // 3600}h ago"
        days = secs // 86400
        if days == 1:
            return "Yesterday"
        if days < 30:
            return f"{days}d ago"
        return dt.strftime("%b %d, %Y")
    except Exception:
        return _format_datetime(dt_str)


def _format_filesize(bytes_val: int) -> str:
    if not bytes_val or bytes_val <= 0:
        return "0 KB"
    if bytes_val < 1024 * 1024:
        return f"{max(1, bytes_val // 1024)} KB"
    return f"{bytes_val / (1024 * 1024):.1f} MB"


def _get_file_icon(filename: str) -> tuple[str, str]:
    ext = (filename.split(".")[-1] if "." in filename else "").lower()
    if ext in ("pdf",):
        return ft.Icons.PICTURE_AS_PDF_ROUNDED, ft.Colors.RED_400
    if ext in ("doc", "docx", "txt", "rtf", "md"):
        return ft.Icons.DESCRIPTION_ROUNDED, ft.Colors.BLUE_400
    if ext in ("zip", "rar", "7z", "tar", "gz"):
        return ft.Icons.FOLDER_ZIP_ROUNDED, ft.Colors.AMBER_400
    if ext in ("py", "js", "ts", "html", "css", "java", "cpp", "c", "sql", "json"):
        return ft.Icons.CODE_ROUNDED, ft.Colors.PRIMARY
    if ext in ("ppt", "pptx", "key"):
        return ft.Icons.CO_PRESENT_ROUNDED, ft.Colors.ORANGE_400
    if ext in ("png", "jpg", "jpeg", "webp", "gif", "svg"):
        return ft.Icons.IMAGE_ROUNDED, ft.Colors.PURPLE_400
    return ft.Icons.INSERT_DRIVE_FILE_ROUNDED, ft.Colors.SECONDARY


async def course_space_hub_view(
    page: ft.Page,
    space_id: str,
    target_back: str = "/courses?tab=spaces",
    manage_mode: bool = False,
) -> ft.View:
    # 1. Clean space_id and extract optional deep-link query params
    raw_route = str(getattr(page, "route", "") or "")
    raw_space_str = str(space_id or "")
    clean_space_id = raw_space_str.split("?")[0].replace("/manage", "").strip()

    query_str = ""
    if "?" in raw_route:
        query_str = raw_route.split("?", 1)[1]
    elif "?" in raw_space_str:
        query_str = raw_space_str.split("?", 1)[1]

    q_params = urllib.parse.parse_qs(query_str)
    is_manage_mode = bool(
        manage_mode
        or "/manage" in raw_route
        or (q_params.get("mode", [""])[0] or "").lower().strip() == "manage"
    )
    init_tab = (q_params.get("tab", ["courses"])[0] or "courses").lower().strip()
    if init_tab == "quizzes":
        init_tab = "drills"
    if init_tab not in ("courses", "materials", "drills", "sessions", "members"):
        init_tab = "courses"
    if not is_manage_mode and init_tab == "members":
        init_tab = "courses"

    init_course_filter = q_params.get("course", [None])[0]
    init_module_filter = q_params.get("module", [None])[0]
    init_quiz_id = q_params.get("quiz_id", [None])[0]

    user_data = (
        page.session.store.get("current_user") or {}
        if hasattr(page, "session") and hasattr(page.session, "store")
        else {}
    )
    current_user_id = str(user_data.get("id", ""))

    token = None
    try:
        if hasattr(page, "shared_preferences"):
            token = await page.shared_preferences.get("auth_token")
    except Exception:
        pass
    if not token and hasattr(page, "session") and hasattr(page.session, "store"):
        token = page.session.store.get("session_auth_token")
    if not token:
        token = user_data.get("token", "")

    state: Dict[str, Any] = {
        "loading": True,
        "space": {},
        "courses": [],
        "materials": [],
        "quizzes": [],
        "sessions": [],
        "members": [],
        "active_tab": init_tab,
        "selected_course_filter": init_course_filter,
        "selected_module_filter": init_module_filter,
        "material_search": "",
        "drill_search": "",
        "member_search": "",
        "pending_deep_quiz_id": init_quiz_id,
    }

    content_area = ft.Column(spacing=16, expand=True)

    def _screen_w() -> int:
        try:
            w = page.width or getattr(page.window, "width", None) or 1024
            return int(w)
        except Exception:
            return 1024

    def _screen_h() -> int:
        try:
            h = page.height or getattr(page.window, "height", None) or 800
            return int(h)
        except Exception:
            return 800

    def _close_modal(dlg: Optional[ft.AlertDialog] = None):
        safe_close_dialog(page, dlg)

    def _get_course_modules(cid: Optional[str]) -> List[Dict[str, Any]]:
        if not cid:
            return []
        for c in state["courses"]:
            if str(c.get("id")) == str(cid):
                return c.get("modules") or []
        return []

    # ── Fetch Hub Data ─────────────────────────────────────────────────────
    async def _load_hub_data(show_spinner: bool = True):
        if show_spinner:
            state["loading"] = True
            _render_view()
            page.update()

        try:
            res = await get_space_details(token=token, space_id=clean_space_id)
            if res.get("status") == "success":
                state["space"] = res.get("space", {})
                state["courses"] = state["space"].get("courses", [])

                c_filter = state["selected_course_filter"]
                m_filter = state["selected_module_filter"]

                mat_task = get_space_materials(token=token, space_id=clean_space_id, course_id=c_filter, module_id=m_filter)
                quiz_task = get_space_quizzes(token=token, space_id=clean_space_id, course_id=c_filter, module_id=m_filter)
                sess_task = get_scheduled_sessions(token=token, space_id=clean_space_id, course_id=c_filter)
                mem_task = get_space_members(token=token, space_id=clean_space_id)

                mat_res, quiz_res, sess_res, mem_res = await asyncio.gather(
                    mat_task, quiz_task, sess_task, mem_task
                )
                state["materials"] = mat_res.get("materials", []) if isinstance(mat_res, dict) else []
                state["quizzes"] = quiz_res.get("quizzes", []) if isinstance(quiz_res, dict) else []
                state["sessions"] = sess_res.get("sessions", []) if isinstance(sess_res, dict) else []
                state["members"] = mem_res.get("members", []) if isinstance(mem_res, dict) else []
            else:
                show_page_snackbar(page, res.get("message", "Failed to load Course Space."))
        except Exception as ex:
            print(f"[CourseSpaceHub] Error reloading hub data: {ex}")
            show_page_snackbar(page, f"Error loading space: {ex}")
        finally:
            state["loading"] = False
            _render_view()
            page.update()

    # ── Course & Module Filter Handlers ────────────────────────────────────
    async def _on_course_filter_changed(course_id_filter: Optional[str]):
        state["selected_course_filter"] = course_id_filter
        state["selected_module_filter"] = None
        await _reload_filtered_collections()

    async def _on_module_filter_changed(module_id_filter: Optional[str]):
        state["selected_module_filter"] = module_id_filter
        await _reload_filtered_collections()

    async def _reload_filtered_collections():
        c_filter = state["selected_course_filter"]
        m_filter = state["selected_module_filter"]
        mat_res, quiz_res, sess_res = await asyncio.gather(
            get_space_materials(token=token, space_id=clean_space_id, course_id=c_filter, module_id=m_filter),
            get_space_quizzes(token=token, space_id=clean_space_id, course_id=c_filter, module_id=m_filter),
            get_scheduled_sessions(token=token, space_id=clean_space_id, course_id=c_filter),
        )
        state["materials"] = mat_res.get("materials", []) if isinstance(mat_res, dict) else []
        state["quizzes"] = quiz_res.get("quizzes", []) if isinstance(quiz_res, dict) else []
        state["sessions"] = sess_res.get("sessions", []) if isinstance(sess_res, dict) else []
        _render_view()
        page.update()

    # ── Invite Learners Modal (Direct Enrollment & Code Sharing) ───────────
    def _open_invite_modal(e=None):
        sp = state["space"]
        sw = _screen_w()
        modal_w = min(480, max(280, int(sw * 0.92)))
        code_str = sp.get("code", "")

        ident_tf = ft.TextField(
            label="Learner Email or Username *",
            hint_text="e.g. learner@example.com or @username",
            dense=True,
            border_radius=10,
            border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
            focused_border_color=ft.Colors.PRIMARY,
            text_size=13,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=11),
        )

        role_dropdown = apply_dropdown_theme(
            ft.Dropdown(
                label="Role",
                dense=True,
                options=[
                    ft.dropdown.Option("student", "Student / Learner"),
                    ft.dropdown.Option("tutor", "Co-Tutor / Assistant"),
                ],
                value="student",
                width=160,
            )
        )

        btn_send = ft.Button(
            "Enroll & Send Invite",
            icon=ft.Icons.SEND_ROUNDED,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.PRIMARY,
                color=ft.Colors.ON_PRIMARY,
                shape=ft.RoundedRectangleBorder(radius=10),
            ),
        )

        async def _do_send_invite(ev):
            val = (ident_tf.value or "").strip()
            if not val:
                show_page_snackbar(page, "Please enter an email or username.")
                return

            btn_send.disabled = True
            btn_send.content = ft.ProgressRing(width=16, height=16, stroke_width=2, color=ft.Colors.ON_PRIMARY)
            page.update()

            res = await invite_space_members(
                token=token,
                space_id=clean_space_id,
                user_identifiers=[val],
                role=role_dropdown.value or "student"
            )

            if res.get("status") == "success" and res.get("added_count", 0) > 0:
                show_page_snackbar(page, f"Enrolled {val} and delivered in-app notification!")
                _close_modal(dlg)
                await _load_hub_data(show_spinner=False)
            elif res.get("already_members"):
                show_page_snackbar(page, f"{val} is already a member of this space.")
                btn_send.disabled = False
                btn_send.content = None
                btn_send.text = "Enroll & Send Invite"
                page.update()
            elif res.get("not_found"):
                show_page_snackbar(page, f"User '{val}' not found. Verify email or username.")
                btn_send.disabled = False
                btn_send.content = None
                btn_send.text = "Enroll & Send Invite"
                page.update()
            else:
                show_page_snackbar(page, res.get("message", "Could not send invitation."))
                btn_send.disabled = False
                btn_send.content = None
                btn_send.text = "Enroll & Send Invite"
                page.update()

        btn_send.on_click = lambda ev: page.run_task(_do_send_invite, ev)
        ident_tf.on_submit = lambda ev: page.run_task(_do_send_invite, ev)

        code_card = ft.Container(
            padding=ft.Padding.all(12),
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.PRIMARY),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.18, ft.Colors.PRIMARY)),
            content=ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text("Space Invite Code", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(code_str, size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                        ],
                        spacing=1,
                    ),
                    ft.Button(
                        "Copy Code",
                        icon=ft.Icons.COPY_ALL_ROUNDED,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                        on_click=lambda ev: page.run_task(safe_set_clipboard, page, code_str),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

        dlg = ft.AlertDialog(
            shape=ft.RoundedRectangleBorder(radius=16),
            title_padding=ft.Padding.only(left=20, right=20, top=18, bottom=6),
            content_padding=ft.Padding.symmetric(horizontal=20, vertical=8),
            actions_padding=ft.Padding.only(left=20, right=20, top=6, bottom=16),
            title=ft.Row(
                [
                    ft.Row(
                        [
                            ft.Container(
                                width=36,
                                height=36,
                                border_radius=10,
                                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.PERSON_ADD_ROUNDED, color=ft.Colors.PRIMARY, size=18),
                            ),
                            ft.Column(
                                [
                                    ft.Text("Invite Learners", weight=ft.FontWeight.BOLD, size=16),
                                    ft.Text(sp.get("name", "Course Space"), size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                                spacing=1,
                            ),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.IconButton(
                        ft.Icons.CLOSE_ROUNDED,
                        icon_size=18,
                        tooltip="Close",
                        on_click=lambda _: _close_modal(dlg),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            content=ft.Container(
                width=modal_w,
                content=ft.Column(
                    [
                        code_card,
                        ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                        ft.Text("Or Enroll Directly by Account", weight=ft.FontWeight.BOLD, size=12.5),
                        ident_tf,
                        role_dropdown,
                    ],
                    spacing=12,
                    tight=True,
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: _close_modal(dlg)),
                btn_send,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        safe_open_dialog(page, dlg, tag="space_invite_modal")

    # ── Space Settings & Edit Modal (Decluttered Studio) ───────────────────
    def _open_space_settings_modal(e=None):
        sp = state["space"]
        sw = _screen_w()
        modal_w = min(500, max(280, int(sw * 0.92)))

        name_tf = ft.TextField(
            label="Space Name *",
            value=sp.get("name", ""),
            dense=True,
            border_radius=10,
            border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
            focused_border_color=ft.Colors.PRIMARY,
            text_size=13,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=11),
        )
        desc_tf = ft.TextField(
            label="Description & Learning Goals",
            value=sp.get("description", "") or "",
            multiline=True,
            min_lines=2,
            max_lines=3,
            dense=True,
            border_radius=10,
            border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
            focused_border_color=ft.Colors.PRIMARY,
            text_size=12.5,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        )

        is_open_val = bool(sp.get("is_open", False))
        access_state = {"is_open": is_open_val}

        def _update_settings_access_ui():
            is_op = access_state["is_open"]
            access_card.border = ft.Border.all(
                1.5,
                ft.Colors.PRIMARY if is_op else ft.Colors.with_opacity(0.3, ft.Colors.SECONDARY),
            )
            access_icon.name = ft.Icons.PUBLIC_ROUNDED if is_op else ft.Icons.LOCK_ROUNDED
            access_icon.color = ft.Colors.PRIMARY if is_op else ft.Colors.SECONDARY
            access_title.value = "Open Access (Discoverable)" if is_op else "Invite Only (Code Required)"
            access_sub.value = (
                "Anyone can discover and join this space."
                if is_op
                else "Learners must enter the secret invite code to unlock and join."
            )
            access_switch.value = is_op
            page.update()

        access_icon = ft.Icon(
            ft.Icons.PUBLIC_ROUNDED if is_open_val else ft.Icons.LOCK_ROUNDED,
            color=ft.Colors.PRIMARY if is_open_val else ft.Colors.SECONDARY,
            size=20,
        )
        access_title = ft.Text(
            "Open Access (Discoverable)" if is_open_val else "Invite Only (Code Required)",
            weight=ft.FontWeight.BOLD,
            size=12.5,
        )
        access_sub = ft.Text(
            "Anyone can discover and join this space."
            if is_open_val
            else "Learners must enter the secret invite code to unlock and join.",
            size=11,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        access_switch = ft.Switch(
            value=is_open_val,
            active_color=ft.Colors.PRIMARY,
            scale=0.85,
        )

        def _toggle_settings_access(ev):
            access_state["is_open"] = bool(access_switch.value)
            _update_settings_access_ui()

        access_switch.on_change = _toggle_settings_access

        access_card = ft.Container(
            padding=ft.Padding.all(12),
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
            content=ft.Row(
                [
                    ft.Row(
                        [
                            ft.Container(
                                width=34,
                                height=34,
                                border_radius=8,
                                bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY if is_open_val else ft.Colors.SECONDARY),
                                alignment=ft.Alignment.CENTER,
                                content=access_icon,
                            ),
                            ft.Column([access_title, access_sub], spacing=2, expand=True),
                        ],
                        spacing=10,
                        expand=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    access_switch,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

        code_val = sp.get("code", "")
        code_txt = ft.Text(f"Code: {code_val}", weight=ft.FontWeight.BOLD, size=13, color=ft.Colors.PRIMARY)
        regen_btn = ft.OutlinedButton(
            "Regenerate",
            icon=ft.Icons.REFRESH_ROUNDED,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
        )
        copy_btn = ft.IconButton(
            ft.Icons.COPY_ALL_ROUNDED,
            icon_size=18,
            tooltip="Copy Invite Code",
            on_click=lambda ev: page.run_task(safe_set_clipboard, page, state["space"].get("code", "")),
        )

        code_card = ft.Container(
            padding=ft.Padding.all(12),
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.PRIMARY),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.18, ft.Colors.PRIMARY)),
            content=ft.Row(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.VPN_KEY_ROUNDED, color=ft.Colors.PRIMARY, size=18),
                            code_txt,
                            copy_btn,
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    regen_btn,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

        delete_btn = ft.TextButton(
            "Delete Space Permanently",
            icon=ft.Icons.DELETE_FOREVER_ROUNDED,
            style=ft.ButtonStyle(color=ft.Colors.RED_400),
        )
        save_btn = ft.Button(
            "Save Settings",
            icon=ft.Icons.CHECK_ROUNDED,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.PRIMARY,
                color=ft.Colors.ON_PRIMARY,
                shape=ft.RoundedRectangleBorder(radius=10),
            ),
        )

        async def _do_regen(ev):
            regen_btn.disabled = True
            page.update()
            res = await regenerate_space_code(token=token, space_id=clean_space_id)
            regen_btn.disabled = False
            if res.get("status") == "success":
                new_code = res.get("code", "")
                state["space"]["code"] = new_code
                code_txt.value = f"Code: {new_code}"
                show_page_snackbar(page, f"Invite code updated to {new_code}!")
                _render_view()
            else:
                show_page_snackbar(page, res.get("message", "Failed to regenerate code."))
            page.update()

        async def _do_delete(ev):
            delete_btn.disabled = True
            page.update()
            res = await delete_course_space(token=token, space_id=clean_space_id)
            if res.get("status") == "success":
                show_page_snackbar(page, "Course Space deleted.")
                _close_modal(dlg)
                page.navigate(target_back)
            else:
                delete_btn.disabled = False
                show_page_snackbar(page, res.get("message", "Could not delete space."))
                page.update()

        async def _do_save(ev):
            if not (name_tf.value or "").strip():
                show_page_snackbar(page, "Space name cannot be empty.")
                return
            save_btn.disabled = True
            save_btn.content = ft.ProgressRing(width=16, height=16, stroke_width=2, color=ft.Colors.ON_PRIMARY)
            page.update()

            res = await update_course_space(
                token=token,
                space_id=clean_space_id,
                payload={
                    "name": name_tf.value.strip(),
                    "description": (desc_tf.value or "").strip(),
                    "is_open": access_state["is_open"],
                },
            )
            if res.get("status") == "success":
                show_page_snackbar(page, "Space settings updated!")
                _close_modal(dlg)
                await _load_hub_data(show_spinner=False)
            else:
                show_page_snackbar(page, res.get("message", "Failed to update settings."))
                save_btn.disabled = False
                save_btn.content = None
                save_btn.text = "Save Settings"
                page.update()

        regen_btn.on_click = lambda ev: page.run_task(_do_regen, ev)
        delete_btn.on_click = lambda ev: page.run_task(_do_delete, ev)
        save_btn.on_click = lambda ev: page.run_task(_do_save, ev)

        dlg = ft.AlertDialog(
            shape=ft.RoundedRectangleBorder(radius=16),
            title_padding=ft.Padding.only(left=20, right=20, top=18, bottom=6),
            content_padding=ft.Padding.symmetric(horizontal=20, vertical=8),
            actions_padding=ft.Padding.only(left=20, right=20, top=6, bottom=16),
            title=ft.Row(
                [
                    ft.Row(
                        [
                            ft.Container(
                                width=36,
                                height=36,
                                border_radius=10,
                                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.SETTINGS_ROUNDED, color=ft.Colors.PRIMARY, size=18),
                            ),
                            ft.Column(
                                [
                                    ft.Text("Course Space Settings", weight=ft.FontWeight.BOLD, size=16),
                                    ft.Text("Configure access, invite codes & info", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                                spacing=1,
                            ),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.IconButton(
                        ft.Icons.CLOSE_ROUNDED,
                        icon_size=18,
                        tooltip="Close",
                        on_click=lambda _: _close_modal(dlg),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            content=ft.Container(
                width=modal_w,
                content=ft.Column(
                    [
                        name_tf,
                        desc_tf,
                        access_card,
                        code_card,
                        ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                        delete_btn,
                    ],
                    spacing=12,
                    tight=True,
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: _close_modal(dlg)),
                save_btn,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        safe_open_dialog(page, dlg, tag="space_invite_modal")

    # ── Manage Linked Courses Modal (Decluttered Studio) ───────────────────
    def _open_manage_courses_modal(e=None):
        sw = _screen_w()
        modal_w = min(500, max(280, int(sw * 0.92)))
        existing_ids = {str(c.get("id")) for c in state["courses"]}
        selected_to_add = set()
        available_courses = []

        counter_pill = ft.Text(
            "0 selected",
            size=11,
            weight=ft.FontWeight.W_600,
            color=ft.Colors.PRIMARY,
        )

        def _update_link_counter():
            counter_pill.value = f"{len(selected_to_add)} selected"
            page.update()

        search_tf = ft.TextField(
            hint_text="Search available courses to link...",
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            dense=True,
            border_radius=10,
            border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
            focused_border_color=ft.Colors.PRIMARY,
            text_size=12.5,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        )
        checks_col = ft.Column(spacing=4, scroll=ft.ScrollMode.AUTO, height=210)
        btn_link = ft.Button(
            "Link Selected Courses",
            icon=ft.Icons.ADD_LINK_ROUNDED,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.PRIMARY,
                color=ft.Colors.ON_PRIMARY,
                shape=ft.RoundedRectangleBorder(radius=10),
            ),
        )

        def _render_checks(q_str: str = ""):
            checks_col.controls.clear()
            ql = (q_str or "").strip().lower()
            count = 0
            for c in available_courses:
                cid = str(c.get("id"))
                if cid in existing_ids:
                    continue
                ctitle = c.get("name") or c.get("title", "Course")
                if ql and ql not in ctitle.lower():
                    continue
                count += 1

                def _toggle(ev, target_id=cid):
                    if ev.control.value:
                        selected_to_add.add(target_id)
                    else:
                        selected_to_add.discard(target_id)
                    _update_link_counter()

                checks_col.controls.append(
                    ft.Checkbox(
                        label=ctitle,
                        value=(cid in selected_to_add),
                        on_change=_toggle,
                        active_color=ft.Colors.PRIMARY,
                    )
                )
            if count == 0:
                checks_col.controls.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(vertical=16),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Text(
                            "No additional courses found to link.",
                            size=12,
                            italic=True,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    )
                )

        search_tf.on_change = lambda ev: (_render_checks(ev.control.value), page.update())

        async def _fetch_available():
            available_courses.clear()
            seen_cids = set()
            org_id = state["space"].get("organisation_id")
            if org_id:
                try:
                    from src.requests.organisations import get_organisation_courses
                    org_c_res = await get_organisation_courses(token=token, id=str(org_id))
                    if isinstance(org_c_res, list):
                        for oc in org_c_res:
                            cid_str = str(oc.get("id") or oc.get("course_id") or "")
                            if cid_str and cid_str not in seen_cids:
                                seen_cids.add(cid_str)
                                available_courses.append(oc)
                except Exception as ex:
                    print(f"[CourseSpaceHub] Error fetching org courses: {ex}")

            if not available_courses:
                c_res = await get_courses(token=token)
                if isinstance(c_res, list):
                    for c in c_res:
                        cid_str = str(c.get("id") or "")
                        if cid_str and cid_str not in seen_cids:
                            seen_cids.add(cid_str)
                            available_courses.append(c)

            _render_checks("")
            page.update()

        async def _do_link(ev):
            if not selected_to_add:
                show_page_snackbar(page, "Select at least one course to link.")
                return
            btn_link.disabled = True
            btn_link.content = ft.ProgressRing(width=16, height=16, stroke_width=2, color=ft.Colors.ON_PRIMARY)
            page.update()

            res = await add_courses_to_space(token=token, space_id=clean_space_id, course_ids=list(selected_to_add))
            if res.get("status") == "success":
                show_page_snackbar(page, res.get("message", "Courses linked and members enrolled!"))
                _close_modal(dlg)
                await _load_hub_data(show_spinner=False)
            else:
                show_page_snackbar(page, res.get("message", "Failed to link courses."))
                btn_link.disabled = False
                btn_link.content = None
                btn_link.text = "Link Selected Courses"
                page.update()

        btn_link.on_click = lambda ev: page.run_task(_do_link, ev)

        dlg = ft.AlertDialog(
            shape=ft.RoundedRectangleBorder(radius=16),
            title_padding=ft.Padding.only(left=20, right=20, top=18, bottom=6),
            content_padding=ft.Padding.symmetric(horizontal=20, vertical=8),
            actions_padding=ft.Padding.only(left=20, right=20, top=6, bottom=16),
            title=ft.Row(
                [
                    ft.Row(
                        [
                            ft.Container(
                                width=36,
                                height=36,
                                border_radius=10,
                                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.LINK_ROUNDED, color=ft.Colors.PRIMARY, size=18),
                            ),
                            ft.Column(
                                [
                                    ft.Text("Link Courses to Space", weight=ft.FontWeight.BOLD, size=16),
                                    ft.Text("Auto-enrolls all current and future members", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                                spacing=1,
                            ),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.IconButton(
                        ft.Icons.CLOSE_ROUNDED,
                        icon_size=18,
                        tooltip="Close",
                        on_click=lambda _: _close_modal(dlg),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            content=ft.Container(
                width=modal_w,
                content=ft.Column(
                    [
                        search_tf,
                        ft.Row(
                            [
                                ft.Text("Available Courses", weight=ft.FontWeight.BOLD, size=12),
                                counter_pill,
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        ft.Container(
                            content=checks_col,
                            padding=8,
                            border_radius=10,
                            border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                        ),
                    ],
                    spacing=10,
                    tight=True,
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: _close_modal(dlg)),
                btn_link,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        safe_open_dialog(page, dlg, tag="space_link_courses_modal")
        page.run_task(_fetch_available)

    # ── Upload Material Modal (Decluttered Studio) ─────────────────────────
    def _open_upload_modal(e=None):
        if not state["courses"]:
            show_page_snackbar(page, "Please link at least one course to this Space before uploading materials.")
            _open_manage_courses_modal()
            return

        sw = _screen_w()
        modal_w = min(500, max(280, int(sw * 0.92)))
        picked_file = {"bytes": None, "name": None}

        title_tf = ft.TextField(
            label="Resource Title *",
            hint_text="e.g. Lecture 4 Notes & Dynamic Programming Cheat Sheet",
            dense=True,
            border_radius=10,
            border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
            focused_border_color=ft.Colors.PRIMARY,
            text_size=13,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=11),
        )
        desc_tf = ft.TextField(
            label="Description / Study Notes (Optional)",
            multiline=True,
            min_lines=2,
            max_lines=3,
            dense=True,
            border_radius=10,
            border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
            focused_border_color=ft.Colors.PRIMARY,
            text_size=12.5,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        )

        initial_cid = state["selected_course_filter"] or str(state["courses"][0]["id"])
        course_dropdown = apply_dropdown_theme(
            ft.Dropdown(
                label="Belongs to Course *",
                dense=True,
                options=[ft.dropdown.Option(str(c["id"]), c["title"]) for c in state["courses"]],
                value=initial_cid,
            )
        )

        module_dropdown = apply_dropdown_theme(
            ft.Dropdown(
                label="Course Module / Topic (Optional)",
                dense=True,
                options=[],
                value="",
            )
        )

        def _sync_module_options(cid: Optional[str]):
            mods = _get_course_modules(cid)
            opts = [ft.dropdown.Option("", "General (All Modules)")]
            for m in mods:
                opts.append(ft.dropdown.Option(str(m.get("id")), m.get("title", "Module")))
            module_dropdown.options = opts
            module_dropdown.value = state["selected_module_filter"] if (state["selected_module_filter"] and any(str(m.get("id")) == state["selected_module_filter"] for m in mods)) else ""

        _sync_module_options(initial_cid)

        def _on_course_change(ev):
            _sync_module_options(course_dropdown.value)
            page.update()

        course_dropdown.on_change = _on_course_change

        file_status_txt = ft.Text("No document selected yet (PDF, DOCX, TXT, Slides)", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
        clear_file_btn = ft.IconButton(
            ft.Icons.CLOSE_ROUNDED,
            icon_size=16,
            tooltip="Clear selected file",
            visible=False,
        )

        def _clear_picked_file(ev=None):
            picked_file["bytes"] = None
            picked_file["name"] = None
            file_status_txt.value = "No document selected yet (PDF, DOCX, TXT, Slides)"
            file_status_txt.color = ft.Colors.ON_SURFACE_VARIANT
            clear_file_btn.visible = False
            page.update()

        clear_file_btn.on_click = _clear_picked_file

        btn_upload = ft.Button(
            "Upload Resource",
            icon=ft.Icons.CLOUD_UPLOAD_ROUNDED,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.PRIMARY,
                color=ft.Colors.ON_PRIMARY,
                shape=ft.RoundedRectangleBorder(radius=10),
            ),
        )

        async def _pick_file_click(ev):
            try:
                files = await ft.FilePicker().pick_files(
                    allow_multiple=False,
                    with_data=True,
                    dialog_title="Select Course Resource",
                )
                if files and len(files) > 0:
                    f = files[0]
                    raw_bytes = getattr(f, "bytes", None)
                    if not raw_bytes and getattr(f, "path", None):
                        with open(f.path, "rb") as opened_f:
                            raw_bytes = opened_f.read()
                    if not raw_bytes:
                        show_page_snackbar(page, "Could not read file bytes. Please try another file.")
                        return
                    picked_file["bytes"] = raw_bytes
                    picked_file["name"] = f.name
                    file_status_txt.value = f"Selected: {f.name} ({_format_filesize(len(raw_bytes))})"
                    file_status_txt.color = ft.Colors.PRIMARY
                    clear_file_btn.visible = True
                    if not title_tf.value:
                        title_tf.value = f.name.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()
                    page.update()
            except Exception as ex:
                show_page_snackbar(page, f"Could not pick file: {ex}")

        async def _do_upload(ev):
            if not picked_file["bytes"]:
                show_page_snackbar(page, "Please pick a document to upload.")
                return
            if not (title_tf.value or "").strip() or not course_dropdown.value:
                show_page_snackbar(page, "Please enter a title and select a course.")
                return

            btn_upload.disabled = True
            btn_upload.content = ft.ProgressRing(width=16, height=16, stroke_width=2, color=ft.Colors.ON_PRIMARY)
            page.update()

            upload_res = await upload_space_material(
                token=token,
                space_id=clean_space_id,
                file_bytes=picked_file["bytes"],
                filename=picked_file["name"],
                course_id=course_dropdown.value,
                module_id=module_dropdown.value if module_dropdown.value else None,
                title=title_tf.value.strip(),
                description=desc_tf.value.strip() if desc_tf.value else None,
            )

            if upload_res.get("status") == "success":
                show_page_snackbar(page, "Resource uploaded! Enrolled students notified.")
                _close_modal(dlg)
                await _load_hub_data(show_spinner=False)
            else:
                show_page_snackbar(page, upload_res.get("message", "Upload failed."))
                btn_upload.disabled = False
                btn_upload.text = "Upload Resource"
                btn_upload.content = None
                page.update()

        btn_upload.on_click = lambda ev: page.run_task(_do_upload, ev)

        file_dropzone = ft.Container(
            padding=ft.Padding.all(12),
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.PRIMARY),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.PRIMARY)),
            content=ft.Row(
                [
                    ft.Button(
                        "Choose File",
                        icon=ft.Icons.ATTACH_FILE_ROUNDED,
                        on_click=lambda ev: page.run_task(_pick_file_click, ev),
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                    ),
                    ft.Container(content=file_status_txt, expand=True),
                    clear_file_btn,
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

        dlg = ft.AlertDialog(
            shape=ft.RoundedRectangleBorder(radius=16),
            title_padding=ft.Padding.only(left=20, right=20, top=18, bottom=6),
            content_padding=ft.Padding.symmetric(horizontal=20, vertical=8),
            actions_padding=ft.Padding.only(left=20, right=20, top=6, bottom=16),
            title=ft.Row(
                [
                    ft.Row(
                        [
                            ft.Container(
                                width=36,
                                height=36,
                                border_radius=10,
                                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.CLOUD_UPLOAD_ROUNDED, color=ft.Colors.PRIMARY, size=18),
                            ),
                            ft.Column(
                                [
                                    ft.Text("Upload Course Resource", weight=ft.FontWeight.BOLD, size=16),
                                    ft.Text("Add slides, notes, or code to Materials Vault", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                                spacing=1,
                            ),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.IconButton(
                        ft.Icons.CLOSE_ROUNDED,
                        icon_size=18,
                        tooltip="Close",
                        on_click=lambda _: _close_modal(dlg),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            content=ft.Container(
                width=modal_w,
                content=ft.Column(
                    [
                        file_dropzone,
                        course_dropdown,
                        module_dropdown,
                        title_tf,
                        desc_tf,
                    ],
                    spacing=12,
                    tight=True,
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda ev: _close_modal(dlg)),
                btn_upload,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        safe_open_dialog(page, dlg, tag="space_invite_modal")

    # ── Schedule Live Class Modal (Decluttered Studio) ─────────────────────
    def _open_schedule_session_modal(e=None):
        sw = _screen_w()
        is_mob = sw < 768
        modal_w = min(500, max(280, int(sw * 0.92)))

        title_tf = ft.TextField(
            label="Session Title *",
            hint_text="e.g. Live Q&A & Graph Algorithms Walkthrough",
            dense=True,
            border_radius=10,
            border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
            focused_border_color=ft.Colors.PRIMARY,
            text_size=13,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=11),
        )
        meet_tf = ft.TextField(
            label="Meeting URL (Google Meet / Zoom) *",
            hint_text="https://meet.google.com/xyz-qwer-tyu",
            dense=True,
            border_radius=10,
            border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
            focused_border_color=ft.Colors.PRIMARY,
            prefix_icon=ft.Icons.LINK_ROUNDED,
            text_size=12.5,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=11),
        )
        desc_tf = ft.TextField(
            label="Agenda / Preparation Notes (Optional)",
            multiline=True,
            min_lines=2,
            max_lines=3,
            dense=True,
            border_radius=10,
            border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
            focused_border_color=ft.Colors.PRIMARY,
            text_size=12.5,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        )

        now = datetime.now()
        date_str_tf = ft.TextField(
            label="Date (YYYY-MM-DD) *",
            value=now.strftime("%Y-%m-%d"),
            dense=True,
            border_radius=10,
            border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
            focused_border_color=ft.Colors.PRIMARY,
            text_size=12.5,
            expand=not is_mob,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        )
        time_str_tf = ft.TextField(
            label="Time (HH:MM 24h) *",
            value="16:00",
            dense=True,
            border_radius=10,
            border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
            focused_border_color=ft.Colors.PRIMARY,
            text_size=12.5,
            expand=not is_mob,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        )
        duration_tf = ft.TextField(
            label="Duration (Mins)",
            value="60",
            dense=True,
            border_radius=10,
            border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
            focused_border_color=ft.Colors.PRIMARY,
            text_size=12.5,
            expand=not is_mob,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        )

        course_dropdown = apply_dropdown_theme(
            ft.Dropdown(
                label="Course Focus (Optional)",
                dense=True,
                options=[ft.dropdown.Option("", "Space-wide (All Courses)")]
                + [ft.dropdown.Option(str(c["id"]), c["title"]) for c in state["courses"]],
                value=state["selected_course_filter"] or "",
            )
        )

        btn_save = ft.Button(
            "Schedule Class",
            icon=ft.Icons.EVENT_AVAILABLE_ROUNDED,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.PRIMARY,
                color=ft.Colors.ON_PRIMARY,
                shape=ft.RoundedRectangleBorder(radius=10),
            ),
        )

        async def _do_schedule(ev):
            if not (title_tf.value or "").strip() or not (meet_tf.value or "").strip() or not (date_str_tf.value or "").strip() or not (time_str_tf.value or "").strip():
                show_page_snackbar(page, "Please fill in title, meeting URL, date, and time.")
                return

            try:
                t_val = time_str_tf.value.strip()
                if len(t_val.split(":")) == 2:
                    t_val = f"{t_val}:00"
                dt_combined = datetime.fromisoformat(f"{date_str_tf.value.strip()}T{t_val}")
                dt_utc = dt_combined.replace(tzinfo=timezone.utc)
            except Exception:
                show_page_snackbar(page, "Invalid date/time format. Use YYYY-MM-DD and HH:MM (e.g. 16:00).")
                return

            btn_save.disabled = True
            btn_save.content = ft.ProgressRing(width=16, height=16, stroke_width=2, color=ft.Colors.ON_PRIMARY)
            page.update()

            dur_val = int(duration_tf.value) if (duration_tf.value and str(duration_tf.value).strip().isdigit()) else 60
            payload = {
                "title": title_tf.value.strip(),
                "description": desc_tf.value.strip() if desc_tf.value else None,
                "meeting_link": meet_tf.value.strip(),
                "start_time": dt_utc.isoformat(),
                "duration_minutes": max(10, dur_val),
                "course_id": course_dropdown.value if course_dropdown.value else None,
            }

            res = await schedule_live_session(token=token, space_id=clean_space_id, payload=payload)
            if res.get("status") == "success":
                show_page_snackbar(page, "Live class scheduled! Notifications sent to learners.")
                _close_modal(dlg)
                await _load_hub_data(show_spinner=False)
            else:
                show_page_snackbar(page, res.get("message", "Failed to schedule session."))
                btn_save.disabled = False
                btn_save.text = "Schedule Class"
                btn_save.content = None
                page.update()

        btn_save.on_click = lambda ev: page.run_task(_do_schedule, ev)

        dt_controls = (
            [date_str_tf, time_str_tf, duration_tf]
            if is_mob
            else [ft.Row([date_str_tf, time_str_tf, duration_tf], spacing=8)]
        )

        dlg = ft.AlertDialog(
            shape=ft.RoundedRectangleBorder(radius=16),
            title_padding=ft.Padding.only(left=20, right=20, top=18, bottom=6),
            content_padding=ft.Padding.symmetric(horizontal=20, vertical=8),
            actions_padding=ft.Padding.only(left=20, right=20, top=6, bottom=16),
            title=ft.Row(
                [
                    ft.Row(
                        [
                            ft.Container(
                                width=36,
                                height=36,
                                border_radius=10,
                                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.VIDEO_CALL_ROUNDED, color=ft.Colors.PRIMARY, size=18),
                            ),
                            ft.Column(
                                [
                                    ft.Text("Schedule Live Class", weight=ft.FontWeight.BOLD, size=16),
                                    ft.Text("Set meeting link, schedule and agenda", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                                spacing=1,
                            ),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.IconButton(
                        ft.Icons.CLOSE_ROUNDED,
                        icon_size=18,
                        tooltip="Close",
                        on_click=lambda _: _close_modal(dlg),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            content=ft.Container(
                width=modal_w,
                content=ft.Column(
                    [
                        title_tf,
                        meet_tf,
                        *dt_controls,
                        course_dropdown,
                        desc_tf,
                    ],
                    spacing=12,
                    tight=True,
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda ev: _close_modal(dlg)),
                btn_save,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        safe_open_dialog(page, dlg, tag="space_invite_modal")

    # ── CBT AI Question Ingestion & Curator Studio Flow (Super Admin Style) ──
    def _launch_cbt_curator_for_space(
        initial_questions: List[Dict[str, Any]],
        drill_title: str,
        course_id: str,
        module_id: Optional[str],
        subject_name: str,
        duration_minutes: int = 20,
        passing_score: float = 70.0,
        description: str = "",
        editing_quiz_id: Optional[str] = None,
    ):
        """Opens the Dual-Pane CBT Question Curator Studio wired directly to this Course Space."""

        async def _upload_diagram_cb(file_bytes: bytes, file_name: str) -> dict:
            return await upload_space_quiz_image(
                token=token,
                space_id=clean_space_id,
                file_bytes=file_bytes,
                filename=file_name,
            )

        async def _save_or_publish_drill(curated_data: Dict[str, Any]):
            raw_qs = curated_data.get("questions") or []
            formatted_qs = []
            for idx, q in enumerate(raw_qs):
                ans_i = int(q.get("answer_index", q.get("correct_index", 0)))
                formatted_qs.append({
                    "id": q.get("id") or f"q_{idx + 1}",
                    "question_text": (q.get("question_text") or "").strip(),
                    "scenario_text": q.get("scenario_text"),
                    "options": q.get("options") or [],
                    "correct_index": ans_i,
                    "answer_index": ans_i,
                    "explanation": (q.get("explanation") or "").strip() or None,
                    "topic": (q.get("topic") or subject_name).strip(),
                    "difficulty": q.get("difficulty") or "standard",
                    "image_url": (q.get("image_url") or "").strip() or None,
                    "has_diagram": bool(q.get("has_diagram") or q.get("image_url")),
                    "points": 1.0,
                })

            payload = {
                "course_id": course_id,
                "module_id": module_id if module_id else None,
                "title": curated_data.get("title") or drill_title,
                "description": curated_data.get("description") or description or None,
                "time_limit_minutes": int(curated_data.get("duration_minutes", duration_minutes) or 0),
                "passing_score_percentage": float(curated_data.get("passing_score_percentage", passing_score) or 70.0),
                "questions": formatted_qs,
            }

            if editing_quiz_id:
                res = await update_space_quiz(token=token, space_id=clean_space_id, quiz_id=editing_quiz_id, payload=payload)
                if res.get("status") == "success":
                    show_page_snackbar(page, f"Drill '{payload['title']}' updated ({len(formatted_qs)} questions)!")
                    await _load_hub_data(show_spinner=False)
                else:
                    show_page_snackbar(page, res.get("message", "Failed to update drill."))
            else:
                res = await create_topic_quiz(token=token, space_id=clean_space_id, payload=payload)
                if res.get("status") == "success":
                    show_page_snackbar(page, f"CBT Drill '{payload['title']}' published ({len(formatted_qs)} questions)!")
                    await _load_hub_data(show_spinner=False)
                else:
                    show_page_snackbar(page, res.get("message", "Failed to publish drill."))

        show_question_curator_dialog(
            page=page,
            initial_questions=initial_questions,
            pack_title=drill_title,
            subject=subject_name,
            exam_type="Course Space CBT",
            initial_description=description or f"Topic-aligned CBT practice drill for {subject_name}.",
            initial_duration_minutes=duration_minutes,
            initial_passing_score=passing_score,
            is_course_space_drill=True,
            on_upload_image=_upload_diagram_cb,
            on_publish=lambda data: page.run_task(_save_or_publish_drill, data),
            token=token,
            save_button_label="Save Drill Changes" if editing_quiz_id else "Publish CBT Drill to Space",
        )

    def _open_create_drill_modal(e=None):
        """
        Opens the CBT AI Document Ingestion & Question Creation Modal (matching Super Admin flow),
        allowing tutors to:
        1. Generate new CBT questions from uploaded lecture notes / PDFs / DOCX / pasted syllabus text.
        2. Extract past exam questions from uploaded PDF / scanned exam paper / DOCX / image / text.
        3. Launch the blank Dual-Pane CBT Question Curator Studio directly.
        """
        if not state["courses"]:
            show_page_snackbar(page, "Please link at least one course to this Space before creating a drill.")
            _open_manage_courses_modal()
            return

        sw = _screen_w()
        is_mob = sw < 768
        modal_w = min(600, max(290, int(sw * 0.94)))

        initial_cid = state["selected_course_filter"] or str(state["courses"][0]["id"])

        course_dropdown = apply_dropdown_theme(
            ft.Dropdown(
                label="Target Course *",
                dense=True,
                expand=not is_mob,
                options=[ft.dropdown.Option(str(c["id"]), c["title"]) for c in state["courses"]],
                value=initial_cid,
            )
        )
        module_dropdown = apply_dropdown_theme(
            ft.Dropdown(
                label="Course Module / Topic (Optional)",
                dense=True,
                expand=not is_mob,
                options=[],
                value="",
            )
        )

        def _get_selected_course_title() -> str:
            for c in state["courses"]:
                if str(c.get("id")) == str(course_dropdown.value):
                    return c.get("title", "General")
            return "General"

        def _get_selected_module_title() -> str:
            mods = _get_course_modules(course_dropdown.value)
            for m in mods:
                if str(m.get("id")) == str(module_dropdown.value):
                    return m.get("title", "")
            return ""

        def _sync_drill_modules(cid: Optional[str]):
            mods = _get_course_modules(cid)
            opts = [ft.dropdown.Option("", "All Modules / General")]
            for m in mods:
                opts.append(ft.dropdown.Option(str(m.get("id")), m.get("title", "Module")))
            module_dropdown.options = opts
            module_dropdown.value = (
                state["selected_module_filter"]
                if (state["selected_module_filter"] and any(str(m.get("id")) == state["selected_module_filter"] for m in mods))
                else ""
            )

        _sync_drill_modules(initial_cid)

        def _on_course_change(ev):
            _sync_drill_modules(course_dropdown.value)
            page.update()

        course_dropdown.on_change = _on_course_change

        title_tf = ft.TextField(
            label="Drill Title (Optional)",
            hint_text="e.g. Week 3: Trees & Graph Traversal CBT Drill",
            dense=True,
            border_radius=10,
            border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
            focused_border_color=ft.Colors.PRIMARY,
            text_size=12.5,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        )

        mode_dropdown = apply_dropdown_theme(
            ft.Dropdown(
                label="AI Ingestion Mode",
                dense=True,
                expand=not is_mob,
                options=[
                    ft.dropdown.Option("generate", "✨ AI Generate New Questions from Notes"),
                    ft.dropdown.Option("extract", "📄 AI Extract Existing Past Questions"),
                    ft.dropdown.Option("auto", "🤖 Auto-Detect (Extract or Generate)"),
                ],
                value="generate",
            )
        )
        q_count_tf = ft.TextField(
            label="Questions",
            value="10",
            dense=True,
            width=110 if not is_mob else None,
            border_radius=10,
            border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
            focused_border_color=ft.Colors.PRIMARY,
            text_size=12.5,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        )
        difficulty_dropdown = apply_dropdown_theme(
            ft.Dropdown(
                label="Difficulty",
                dense=True,
                width=130 if not is_mob else None,
                options=[
                    ft.dropdown.Option("easy", "Easy"),
                    ft.dropdown.Option("standard", "Standard"),
                    ft.dropdown.Option("hard", "Hard / Exam"),
                ],
                value="standard",
            )
        )
        duration_tf = ft.TextField(
            label="Time (Mins, 0=Untimed)",
            value="20",
            dense=True,
            expand=not is_mob,
            border_radius=10,
            border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
            focused_border_color=ft.Colors.PRIMARY,
            text_size=12.5,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        )
        pass_mark_tf = ft.TextField(
            label="Pass Mark (%)",
            value="70",
            dense=True,
            expand=not is_mob,
            border_radius=10,
            border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
            focused_border_color=ft.Colors.PRIMARY,
            text_size=12.5,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        )

        picked_doc = {"bytes": None, "name": ""}
        file_badge_text = ft.Text(
            "Select PDF, Word (.docx), TXT, or Exam Image (.png/.jpg)",
            size=11.5,
            color=ft.Colors.ON_SURFACE_VARIANT,
        )
        clear_file_btn = ft.IconButton(
            ft.Icons.CLOSE_ROUNDED,
            icon_size=16,
            tooltip="Clear uploaded file",
            visible=False,
        )

        raw_text_tf = ft.TextField(
            hint_text=(
                "Paste lecture notes or topic text for AI to generate CBT questions, OR paste numbered questions:\n"
                "1. What is the time complexity of binary search?\nA. O(n)\nB. O(log n)\nC. O(n log n)\nD. O(1)\nAnswer: B"
            ),
            multiline=True,
            min_lines=4,
            max_lines=7,
            border_radius=10,
            border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
            focused_border_color=ft.Colors.PRIMARY,
            text_size=12,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        )

        status_text = ft.Text("", size=12, color=ft.Colors.PRIMARY, visible=False)

        async def _pick_ingest_file(ev=None):
            try:
                files = await ft.FilePicker().pick_files(
                    allow_multiple=False,
                    file_type=ft.FilePickerFileType.CUSTOM,
                    allowed_extensions=["pdf", "txt", "docx", "md", "png", "jpg", "jpeg", "webp"],
                    with_data=True,
                    dialog_title="Select Lecture Document or Past Question Paper",
                )
                if not files:
                    return
                f = files[0]
                raw_bytes = getattr(f, "bytes", None)
                if not raw_bytes and getattr(f, "path", None):
                    with open(f.path, "rb") as fp:
                        raw_bytes = fp.read()
                if not raw_bytes:
                    show_page_snackbar(page, "Could not read file bytes.")
                    return

                picked_doc["bytes"] = raw_bytes
                picked_doc["name"] = f.name
                file_badge_text.value = f"📄 {f.name} ({_format_filesize(len(raw_bytes))})"
                file_badge_text.color = ft.Colors.PRIMARY
                clear_file_btn.visible = True
                if not title_tf.value:
                    title_tf.value = f.name.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()
                page.update()
            except Exception as ex:
                show_page_snackbar(page, f"File selection error: {ex}")

        def _clear_doc(ev=None):
            picked_doc["bytes"] = None
            picked_doc["name"] = ""
            file_badge_text.value = "Select PDF, Word (.docx), TXT, or Exam Image (.png/.jpg)"
            file_badge_text.color = ft.Colors.ON_SURFACE_VARIANT
            clear_file_btn.visible = False
            page.update()

        clear_file_btn.on_click = _clear_doc

        # ── 3-Tab Segmented Source Switcher ──
        current_source = {"mode": "upload"}  # "upload" | "paste" | "studio"

        upload_zone = ft.Container(
            padding=12,
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.PRIMARY),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.2, ft.Colors.PRIMARY)),
            content=ft.Row(
                [
                    ft.Button(
                        "Choose File",
                        icon=ft.Icons.UPLOAD_FILE_ROUNDED,
                        on_click=lambda ev: page.run_task(_pick_ingest_file, ev),
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
                    ),
                    ft.Container(content=file_badge_text, expand=True),
                    clear_file_btn,
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

        manual_card = ft.Container(
            padding=14,
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.EDIT_NOTE_ROUNDED, size=24, color=ft.Colors.PRIMARY),
                    ft.Column(
                        [
                            ft.Text("Direct Manual Question Studio", weight=ft.FontWeight.BOLD, size=13),
                            ft.Text(
                                "Skip AI generation and start composing questions manually inside the dual-pane Curator Studio.",
                                size=11.5,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

        source_container = ft.Container(content=upload_zone)

        btn_action = ft.Button(
            "Run AI Ingestion & Open Curator",
            icon=ft.Icons.AUTO_AWESOME_ROUNDED,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.PRIMARY,
                color=ft.Colors.ON_PRIMARY,
                shape=ft.RoundedRectangleBorder(radius=10),
            ),
        )

        def _update_source_tab(mode: str):
            current_source["mode"] = mode
            for pill_mode, pill_ctrl in tab_pills_map.items():
                is_active = (pill_mode == mode)
                pill_ctrl.bgcolor = ft.Colors.PRIMARY if is_active else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)
                pill_ctrl.content.controls[0].color = ft.Colors.ON_PRIMARY if is_active else ft.Colors.ON_SURFACE_VARIANT
                pill_ctrl.content.controls[1].color = ft.Colors.ON_PRIMARY if is_active else ft.Colors.ON_SURFACE
                pill_ctrl.content.controls[1].weight = ft.FontWeight.BOLD if is_active else ft.FontWeight.NORMAL

            if mode == "upload":
                source_container.content = upload_zone
                ai_cfg_container.visible = True
                btn_action.text = "Run AI Ingestion & Open Curator"
                btn_action.icon = ft.Icons.AUTO_AWESOME_ROUNDED
            elif mode == "paste":
                source_container.content = raw_text_tf
                ai_cfg_container.visible = True
                btn_action.text = "Run AI Ingestion & Open Curator"
                btn_action.icon = ft.Icons.AUTO_AWESOME_ROUNDED
            else:
                source_container.content = manual_card
                ai_cfg_container.visible = False
                btn_action.text = "Open Blank Curator Studio"
                btn_action.icon = ft.Icons.EDIT_NOTE_ROUNDED
            page.update()

        tab_defs = [
            ("upload", "📄 Upload Document / Paper", ft.Icons.UPLOAD_FILE_ROUNDED),
            ("paste", "✍️ Paste Notes / Questions", ft.Icons.TEXT_SNIPPET_ROUNDED),
            ("studio", "🛠️ Blank Studio", ft.Icons.EDIT_NOTE_ROUNDED),
        ]
        tab_pills_map = {}
        tab_buttons = []
        for t_mode, t_label, t_ico in tab_defs:
            is_def_active = (t_mode == "upload")
            p_container = ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=7),
                border_radius=8,
                bgcolor=ft.Colors.PRIMARY if is_def_active else ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                ink=True,
                on_click=lambda ev, m=t_mode: _update_source_tab(m),
                content=ft.Row(
                    [
                        ft.Icon(t_ico, size=14, color=ft.Colors.ON_PRIMARY if is_def_active else ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(
                            t_label,
                            size=11.5,
                            weight=ft.FontWeight.BOLD if is_def_active else ft.FontWeight.NORMAL,
                            color=ft.Colors.ON_PRIMARY if is_def_active else ft.Colors.ON_SURFACE,
                        ),
                    ],
                    spacing=5,
                    tight=True,
                ),
            )
            tab_pills_map[t_mode] = p_container
            tab_buttons.append(p_container)

        source_tab_bar = ft.Row(tab_buttons, spacing=6, wrap=True)

        def _get_timing_and_pass() -> tuple[int, float]:
            d_str = (duration_tf.value or "").strip()
            d_mins = int(d_str) if d_str.isdigit() else 20
            p_str = (pass_mark_tf.value or "").strip()
            try:
                p_pct = float(p_str) if p_str else 70.0
            except ValueError:
                p_pct = 70.0
            return d_mins, p_pct

        def _open_blank_studio():
            if not course_dropdown.value:
                show_page_snackbar(page, "Please select a target course.")
                return
            c_title = _get_selected_course_title()
            m_title = _get_selected_module_title()
            subj = f"{c_title} - {m_title}" if m_title else c_title
            d_mins, p_pct = _get_timing_and_pass()
            d_title = (title_tf.value or "").strip() or f"{subj} Practice Drill"
            _close_modal(ingest_dlg)
            _launch_cbt_curator_for_space(
                initial_questions=[],
                drill_title=d_title,
                course_id=course_dropdown.value,
                module_id=module_dropdown.value or None,
                subject_name=subj,
                duration_minutes=d_mins,
                passing_score=p_pct,
            )

        async def _do_ai_ingest():
            if not course_dropdown.value:
                show_page_snackbar(page, "Please select a target course.")
                return
            has_file = bool(picked_doc["bytes"])
            raw_txt = (raw_text_tf.value or "").strip()
            if current_source["mode"] == "upload" and not has_file:
                show_page_snackbar(page, "Please choose a document or image to ingest.")
                return
            if current_source["mode"] == "paste" and len(raw_txt) < 15:
                show_page_snackbar(page, "Please paste at least a paragraph of notes or numbered questions.")
                return

            c_title = _get_selected_course_title()
            m_title = _get_selected_module_title()
            subj = f"{c_title} ({m_title})" if m_title else c_title
            q_cnt_str = (q_count_tf.value or "10").strip()
            q_cnt = int(q_cnt_str) if q_cnt_str.isdigit() else 10
            mode_val = mode_dropdown.value or "auto"
            diff_val = difficulty_dropdown.value or "standard"
            d_mins, p_pct = _get_timing_and_pass()

            btn_action.disabled = True
            btn_action.content = ft.ProgressRing(width=16, height=16, stroke_width=2, color=ft.Colors.ON_PRIMARY)
            status_text.value = (
                f"⏳ AI is analyzing '{picked_doc['name']}' and structuring CBT questions..."
                if has_file and current_source["mode"] == "upload"
                else "⏳ AI is generating structured CBT questions & explanations..."
            )
            status_text.visible = True
            page.update()

            try:
                if current_source["mode"] == "upload" and has_file:
                    res = await ai_parse_space_quiz_file(
                        token=token,
                        space_id=clean_space_id,
                        file_bytes=picked_doc["bytes"],
                        filename=picked_doc["name"],
                        subject=subj,
                        exam_type="Course Space CBT",
                        mode=mode_val,
                        question_count=q_cnt,
                        difficulty=diff_val,
                    )
                else:
                    res = await ai_parse_space_quiz_text(
                        token=token,
                        space_id=clean_space_id,
                        raw_text=raw_txt,
                        subject=subj,
                        exam_type="Course Space CBT",
                        mode=mode_val,
                        question_count=q_cnt,
                        difficulty=diff_val,
                    )

                extracted_qs = res.get("questions") or []
                if res.get("status") == "error" or not extracted_qs:
                    err_msg = res.get("message") or "No questions could be generated from the input. Try adding more detail."
                    show_page_snackbar(page, err_msg)
                    btn_action.disabled = False
                    btn_action.content = None
                    btn_action.text = "Run AI Ingestion & Open Curator"
                    status_text.visible = False
                    page.update()
                    return

                final_title = (title_tf.value or "").strip() or res.get("suggested_title") or f"{subj} CBT Drill"
                show_page_snackbar(page, f"AI prepared {len(extracted_qs)} CBT questions! Opening Curator Studio...")
                _close_modal(ingest_dlg)
                _launch_cbt_curator_for_space(
                    initial_questions=extracted_qs,
                    drill_title=final_title,
                    course_id=course_dropdown.value,
                    module_id=module_dropdown.value or None,
                    subject_name=subj,
                    duration_minutes=d_mins,
                    passing_score=p_pct,
                )
            except Exception as ex:
                show_page_snackbar(page, f"AI ingestion error: {ex}")
                btn_action.disabled = False
                btn_action.content = None
                btn_action.text = "Run AI Ingestion & Open Curator"
                status_text.visible = False
                page.update()

        async def _on_action_click(ev):
            if current_source["mode"] == "studio":
                _open_blank_studio()
            else:
                await _do_ai_ingest()

        btn_action.on_click = lambda ev: page.run_task(_on_action_click, ev)

        course_mod_controls = (
            [course_dropdown, module_dropdown]
            if is_mob
            else [ft.Row([course_dropdown, module_dropdown], spacing=10)]
        )
        ai_cfg_controls = (
            [mode_dropdown, q_count_tf, difficulty_dropdown]
            if is_mob
            else [ft.Row([mode_dropdown, q_count_tf, difficulty_dropdown], spacing=10)]
        )
        timing_controls = (
            [duration_tf, pass_mark_tf]
            if is_mob
            else [ft.Row([duration_tf, pass_mark_tf], spacing=10)]
        )
        ai_cfg_container = ft.Column(
            [
                *ai_cfg_controls,
                *timing_controls,
            ],
            spacing=10,
        )

        ingest_dlg = ft.AlertDialog(
            shape=ft.RoundedRectangleBorder(radius=16),
            title_padding=ft.Padding.only(left=20, right=20, top=18, bottom=6),
            content_padding=ft.Padding.symmetric(horizontal=20, vertical=8),
            actions_padding=ft.Padding.only(left=20, right=20, top=6, bottom=16),
            title=ft.Row(
                [
                    ft.Row(
                        [
                            ft.Container(
                                width=36,
                                height=36,
                                border_radius=10,
                                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=ft.Colors.PRIMARY, size=18),
                            ),
                            ft.Column(
                                [
                                    ft.Text("Create CBT Topic Drill", weight=ft.FontWeight.BOLD, size=16),
                                    ft.Text("AI Question Ingestion & Curator Studio", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                                spacing=1,
                            ),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.IconButton(
                        ft.Icons.CLOSE_ROUNDED,
                        icon_size=18,
                        tooltip="Close",
                        on_click=lambda _: _close_modal(ingest_dlg),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            content=ft.Container(
                width=modal_w,
                content=ft.Column(
                    [
                        *course_mod_controls,
                        title_tf,
                        source_tab_bar,
                        source_container,
                        ai_cfg_container,
                        status_text,
                    ],
                    spacing=12,
                    tight=True,
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: _close_modal(ingest_dlg)),
                btn_action,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        safe_open_dialog(page, ingest_dlg, tag="space_cbt_ingest_modal")

    # ── Tutor: Edit Existing Drill in CBT Curator Studio ───────────────────
    async def _edit_drill_in_studio(quiz_summary: dict):
        qid = str(quiz_summary.get("id"))
        res = await get_quiz_for_taking(token=token, space_id=clean_space_id, quiz_id=qid, include_answers=True)
        if res.get("status") != "success":
            show_page_snackbar(page, res.get("message", "Could not load drill for editing."))
            return
        q_data = res.get("quiz", {})
        c_title = q_data.get("course_title") or "General"
        m_title = q_data.get("module_title") or ""
        subj = f"{c_title} ({m_title})" if m_title else c_title
        _launch_cbt_curator_for_space(
            initial_questions=q_data.get("questions", []),
            drill_title=q_data.get("title", "Topic Drill"),
            course_id=str(q_data.get("course_id")),
            module_id=str(q_data.get("module_id")) if q_data.get("module_id") else None,
            subject_name=subj,
            duration_minutes=int(q_data.get("time_limit_minutes") or 0),
            passing_score=float(q_data.get("passing_score_percentage") or 70.0),
            description=q_data.get("description") or "",
            editing_quiz_id=qid,
        )

    # ── Tutor: View Drill Results & Gradebook Modal ────────────────────────
    async def _open_drill_attempts_modal(quiz_summary: dict):
        qid = str(quiz_summary.get("id"))
        qtitle = quiz_summary.get("title", "Topic Drill")
        res = await get_space_quiz_attempts(token=token, space_id=clean_space_id, quiz_id=qid)
        if res.get("status") != "success":
            show_page_snackbar(page, "Could not load drill attempts.")
            return

        summary = res.get("summary") or {}
        attempts = res.get("attempts") or []
        sw = _screen_w()
        modal_w = min(620, max(280, int(sw * 0.92)))

        metrics_row = ft.ResponsiveRow(
            spacing=10,
            run_spacing=10,
            controls=[
                ft.Container(
                    col={"xs": 6, "sm": 3},
                    padding=12,
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                    content=ft.Column(
                        [
                            ft.Text(str(summary.get("total_attempts", 0)), size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                            ft.Text("Total Attempts", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                        spacing=2,
                    ),
                ),
                ft.Container(
                    col={"xs": 6, "sm": 3},
                    padding=12,
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.SECONDARY),
                    content=ft.Column(
                        [
                            ft.Text(str(summary.get("unique_learners", 0)), size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.SECONDARY),
                            ft.Text("Unique Learners", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                        spacing=2,
                    ),
                ),
                ft.Container(
                    col={"xs": 6, "sm": 3},
                    padding=12,
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                    content=ft.Column(
                        [
                            ft.Text(f"{summary.get('average_percentage', 0)}%", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                            ft.Text("Average Score", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                        spacing=2,
                    ),
                ),
                ft.Container(
                    col={"xs": 6, "sm": 3},
                    padding=12,
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                    content=ft.Column(
                        [
                            ft.Text(f"{summary.get('pass_rate', 0)}%", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                            ft.Text("Pass Rate", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                        spacing=2,
                    ),
                ),
            ],
        )

        attempts_col = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, height=320)
        if not attempts:
            attempts_col.controls.append(
                ft.Container(
                    padding=30,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Text("No attempts recorded for this drill yet.", size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                )
            )
        else:
            for a in attempts:
                passed = a.get("passed", False)
                pct = a.get("percentage", 0)
                dur_s = int(a.get("duration_seconds") or 0)
                dur_label = f"{dur_s // 60}m {dur_s % 60}s" if dur_s > 0 else "—"
                attempts_col.controls.append(
                    ft.Container(
                        padding=12,
                        border_radius=10,
                        bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                        content=ft.Row(
                            [
                                ft.CircleAvatar(
                                    radius=16,
                                    bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.PRIMARY),
                                    content=ft.Text((a.get("learner_name") or "L")[0].upper(), size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                                ),
                                ft.Column(
                                    [
                                        ft.Text(a.get("learner_name", "Learner"), weight=ft.FontWeight.BOLD, size=13),
                                        ft.Text(
                                            f"{_format_relative_time(a.get('completed_at'))} • Time spent: {dur_label}",
                                            size=11,
                                            color=ft.Colors.ON_SURFACE_VARIANT,
                                        ),
                                    ],
                                    spacing=2,
                                    expand=True,
                                ),
                                ft.Container(
                                    padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                                    border_radius=8,
                                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY if passed else ft.Colors.AMBER_600),
                                    content=ft.Text(
                                        f"{pct}% ({'PASS' if passed else 'RETRY'})",
                                        size=11.5,
                                        weight=ft.FontWeight.BOLD,
                                        color=ft.Colors.PRIMARY if passed else ft.Colors.AMBER_400,
                                    ),
                                ),
                            ],
                            spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    )
                )

        dlg = ft.AlertDialog(
            shape=ft.RoundedRectangleBorder(radius=16),
            title=ft.Row([ft.Icon(ft.Icons.LEADERBOARD_ROUNDED, color=ft.Colors.PRIMARY), ft.Text(f"Results: {qtitle}", weight=ft.FontWeight.BOLD, size=16)]),
            content=ft.Container(
                width=modal_w,
                content=ft.Column([metrics_row, ft.Divider(height=1), attempts_col], spacing=12, tight=True),
            ),
            actions=[ft.TextButton("Close", on_click=lambda _: _close_modal(dlg))],
        )
        safe_open_dialog(page, dlg, tag="space_quiz_results_modal")

    # ── Interactive Student CBT Drill Runner Navigation ────────────────────
    async def _launch_quiz_runner(quiz_id: str, quiz_title: str = ""):
        page.navigate(f"/spaces/{clean_space_id}/drills/{quiz_id}")

    # ── UI Renderer ────────────────────────────────────────────────────────
    mat_search_tf = ft.TextField(
        hint_text="Filter materials by title, filename, or module...",
        prefix_icon=ft.Icons.SEARCH_ROUNDED,
        dense=True,
        border_radius=10,
        text_size=13,
        expand=True,
    )
    mat_search_tf.on_change = lambda ev: (
        state.update({"material_search": (ev.control.value or "").strip()}),
        _render_view(),
        page.update(),
    )

    drill_search_tf = ft.TextField(
        hint_text="Filter topic drills by title or module...",
        prefix_icon=ft.Icons.SEARCH_ROUNDED,
        dense=True,
        border_radius=10,
        text_size=13,
        expand=True,
    )
    drill_search_tf.on_change = lambda ev: (
        state.update({"drill_search": (ev.control.value or "").strip()}),
        _render_view(),
        page.update(),
    )

    member_search_tf = ft.TextField(
        hint_text="Search members by name, username, or role...",
        prefix_icon=ft.Icons.SEARCH_ROUNDED,
        dense=True,
        border_radius=10,
        text_size=13,
        expand=True,
    )
    member_search_tf.on_change = lambda ev: (
        state.update({"member_search": (ev.control.value or "").strip()}),
        _render_view(),
        page.update(),
    )

    def _render_view():
        content_area.controls.clear()
        sw = _screen_w()
        is_mob = sw < 768

        if state["loading"]:
            from src.components.shimmer_skeletons import build_course_space_hub_skeleton
            content_area.controls.append(build_course_space_hub_skeleton(page))
            return

        sp = state["space"]
        has_manage_rights = bool(sp.get("can_manage", False))
        can_manage = bool(is_manage_mode and has_manage_rights)
        is_creator = bool(sp.get("is_creator", False))
        is_member = bool(sp.get("is_member", False))
        is_student = bool(sp.get("is_student", False))
        is_open = bool(sp.get("is_open", False))
        code = sp.get("code", "")

        is_already_joined = bool(is_student or is_member or is_creator or has_manage_rights or sp.get("is_enrolled", False))

        # ── 0. Invite-Only Gating Screen for Non-Members ─────────────────────
        if not is_open and not is_already_joined:
            code_input = ft.TextField(
                label="Space Invite Code",
                hint_text="e.g. SPACE-8X9L2K",
                capitalization=ft.TextCapitalization.CHARACTERS,
                dense=True,
                autofocus=True,
                border_radius=10,
                border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
                focused_border_color=ft.Colors.PRIMARY,
                prefix_icon=ft.Icons.VPN_KEY_ROUNDED,
                text_size=13,
                width=320,
            )
            unlock_btn = ft.Button(
                "Unlock & Join Space",
                icon=ft.Icons.LOCK_OPEN_ROUNDED,
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.PRIMARY,
                    color=ft.Colors.ON_PRIMARY,
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=ft.Padding.symmetric(horizontal=20, vertical=12),
                ),
            )

            async def _do_unlock(ev):
                c_val = (code_input.value or "").strip().upper()
                if not c_val:
                    show_page_snackbar(page, "Please enter an invite code.")
                    return
                unlock_btn.disabled = True
                unlock_btn.content = ft.ProgressRing(width=16, height=16, stroke_width=2, color=ft.Colors.ON_PRIMARY)
                page.update()

                res = await join_course_space(token=token, code=c_val)
                if res.get("status") == "success":
                    show_page_snackbar(page, f"Welcome to {sp.get('name', 'Course Space')}!")
                    await _load_hub_data(show_spinner=True)
                else:
                    show_page_snackbar(page, res.get("message", "Invalid invite code. Please check with your instructor."))
                    unlock_btn.disabled = False
                    unlock_btn.content = None
                    unlock_btn.text = "Unlock & Join Space"
                    page.update()

            unlock_btn.on_click = lambda ev: page.run_task(_do_unlock, ev)
            code_input.on_submit = lambda ev: page.run_task(_do_unlock, ev)

            switch_to_manage_btn = None
            if has_manage_rights:
                switch_to_manage_btn = ft.OutlinedButton(
                    "Switch to Management Studio",
                    icon=ft.Icons.TUNE_ROUNDED,
                    on_click=lambda ev: page.navigate(f"/spaces/{clean_space_id}/manage"),
                )

            gate_card = ft.Container(
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding.all(32 if is_mob else 48),
                content=ft.Column(
                    [
                        ft.Container(
                            width=64,
                            height=64,
                            border_radius=20,
                            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.SECONDARY),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(ft.Icons.LOCK_ROUNDED, size=32, color=ft.Colors.SECONDARY),
                        ),
                        ft.Text("Private Course Space", size=22, weight=ft.FontWeight.BOLD),
                        ft.Text(
                            sp.get("name", "Course Space"),
                            size=16,
                            weight=ft.FontWeight.W_600,
                            color=ft.Colors.PRIMARY,
                        ),
                        ft.Container(
                            width=min(480, int(sw * 0.88)),
                            content=ft.Text(
                                "This space is invite-only. Enter the invite code to join your cohort and unlock access.",
                                size=13,
                                text_align=ft.TextAlign.CENTER,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ),
                        ft.Container(height=8),
                        code_input,
                        unlock_btn,
                        *([switch_to_manage_btn] if switch_to_manage_btn else []),
                        ft.TextButton(
                            "Back to Explore Spaces",
                            icon=ft.Icons.ARROW_BACK_ROUNDED,
                            on_click=lambda ev: page.navigate(target_back),
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=14,
                ),
            )
            content_area.controls.append(gate_card)
            return

        # ── 1. Hub Header ──────────────────────────────────────────────────
        async def _copy_code(ev):
            if code:
                await safe_set_clipboard(page, code)
                show_page_snackbar(page, f"Space Code '{code}' copied to clipboard!")

        async def _join_this_space(ev):
            res = await join_course_space(token=token, space_id=clean_space_id)
            if res.get("status") == "success":
                show_page_snackbar(page, f"Joined {sp.get('name', 'Space')}!")
                await _load_hub_data(show_spinner=False)
            else:
                show_page_snackbar(page, res.get("message", "Could not join space."))

        async def _leave_this_space(ev):
            res = await leave_course_space(token=token, space_id=clean_space_id)
            if res.get("status") == "success":
                show_page_snackbar(page, res.get("message", "Left Course Space."))
                page.navigate(target_back)
            else:
                show_page_snackbar(page, res.get("message", "Could not leave space."))

        code_pill = ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            border_radius=20,
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.PRIMARY)),
            on_click=lambda ev: page.run_task(_copy_code, ev),
            tooltip="Click to copy invite code",
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.COPY_ALL_ROUNDED, size=14, color=ft.Colors.PRIMARY),
                    ft.Text(f"Code: {code}", weight=ft.FontWeight.BOLD, size=12, color=ft.Colors.PRIMARY),
                ],
                spacing=6,
                tight=True,
            ),
        )

        access_badge = ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            border_radius=8,
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY if is_open else ft.Colors.SECONDARY),
            content=ft.Text(
                "OPEN HUB" if is_open else "INVITE ONLY",
                size=10,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.PRIMARY if is_open else ft.Colors.SECONDARY,
            ),
        )

        mode_badge = None
        if can_manage:
            mode_badge = ft.Container(
                padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.14, ft.Colors.PRIMARY),
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.TUNE_ROUNDED, size=12, color=ft.Colors.PRIMARY),
                        ft.Text("MANAGEMENT STUDIO", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                    ],
                    spacing=4,
                    tight=True,
                ),
            )

        header_actions = []
        if can_manage:
            header_actions.append(
                ft.Button(
                    "Invite Learners",
                    icon=ft.Icons.PERSON_ADD_ROUNDED,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.PRIMARY,
                        color=ft.Colors.ON_PRIMARY,
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                    on_click=_open_invite_modal,
                )
            )
            if code:
                header_actions.append(code_pill)
            header_actions.append(
                ft.OutlinedButton(
                    "Student Preview",
                    icon=ft.Icons.VISIBILITY_OUTLINED,
                    on_click=lambda ev: page.navigate(f"/spaces/{clean_space_id}"),
                )
            )
            header_actions.append(
                ft.OutlinedButton(
                    "Settings",
                    icon=ft.Icons.SETTINGS_ROUNDED,
                    on_click=_open_space_settings_modal,
                )
            )
        elif not is_member and is_open:
            header_actions.append(
                ft.Button(
                    "Join Space",
                    icon=ft.Icons.LOGIN_ROUNDED,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.PRIMARY, color=ft.Colors.ON_PRIMARY),
                    on_click=lambda ev: page.run_task(_join_this_space, ev),
                )
            )
        elif is_member and not is_creator:
            header_actions.append(
                ft.OutlinedButton(
                    "Leave Space",
                    icon=ft.Icons.EXIT_TO_APP_ROUNDED,
                    on_click=lambda ev: page.run_task(_leave_this_space, ev),
                )
            )

        title_row = ft.Row(
            [
                ft.IconButton(
                    ft.Icons.ARROW_BACK_ROUNDED,
                    tooltip="Back to Courses",
                    on_click=lambda ev: page.navigate(target_back or "/courses?tab=spaces"),
                ),
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(
                                    sp.get("name", "Course Space"),
                                    weight=ft.FontWeight.BOLD,
                                    size=20 if is_mob else 22,
                                    color=ft.Colors.ON_SURFACE,
                                ),
                                access_badge,
                                *([mode_badge] if mode_badge else []),
                            ],
                            spacing=8,
                            wrap=True,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Text(
                            sp.get("description") or "Cohort study space",
                            size=13,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ],
                    spacing=2,
                    expand=True,
                ),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        header_top = (
            ft.Column([title_row, *([ft.Row(header_actions, spacing=8, wrap=True)] if header_actions else [])], spacing=10)
            if is_mob
            else ft.Row(
                [title_row, *([ft.Row(header_actions, spacing=8)] if header_actions else [])],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )

        header_card = ft.Container(
            padding=16 if is_mob else 20,
            border_radius=16,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.09, ft.Colors.ON_SURFACE)),
            content=ft.Column(
                [
                    header_top,
                    ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    ft.Row(
                        [
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.PERSON_PIN_ROUNDED, size=16, color=ft.Colors.PRIMARY),
                                    ft.Text(f"Lead: {sp.get('creator_name', 'Instructor')}", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                                spacing=4,
                                tight=True,
                            ),
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.PEOPLE_ALT_ROUNDED, size=16, color=ft.Colors.PRIMARY),
                                    ft.Text(f"{len(state['members']) or sp.get('member_count', 0)} Members", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                                spacing=4,
                                tight=True,
                            ),
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.MENU_BOOK_ROUNDED, size=16, color=ft.Colors.PRIMARY),
                                    ft.Text(f"{len(state['courses'])} Linked Courses", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                                spacing=4,
                                tight=True,
                            ),
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.PSYCHOLOGY_ROUNDED, size=16, color=ft.Colors.PRIMARY),
                                    ft.Text(f"{len(state['quizzes'])} CBT Drills", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                                spacing=4,
                                tight=True,
                            ),
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.VIDEO_CAMERA_FRONT_ROUNDED, size=16, color=ft.Colors.PRIMARY),
                                    ft.Text(f"{len(state['sessions'])} Live Classes", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                                spacing=4,
                                tight=True,
                            ),
                        ],
                        spacing=16,
                        wrap=True,
                    ),
                ],
                spacing=12,
            ),
        )
        content_area.controls.append(header_card)

        # ── 2. Hub Tab Switcher ────────────────────────────────────────────
        def _set_active_tab(tab_name: str):
            state["active_tab"] = tab_name
            _render_view()
            page.update()

        tab_defs = [
            ("courses", f"Courses ({len(state['courses'])})", ft.Icons.AUTO_STORIES_ROUNDED),
            ("materials", f"Materials Vault ({len(state['materials'])})", ft.Icons.INVENTORY_2_ROUNDED),
            ("drills", f"Topic Drills & CBT ({len(state['quizzes'])})", ft.Icons.PSYCHOLOGY_ROUNDED),
            ("sessions", f"Live Classes ({len(state['sessions'])})", ft.Icons.VIDEO_CAMERA_FRONT_ROUNDED),
        ]
        if can_manage:
            tab_defs.append(
                ("members", f"Members ({len(state['members']) or sp.get('member_count', 0)})", ft.Icons.PEOPLE_ALT_ROUNDED)
            )

        tab_pills = []
        for t_key, t_label, t_icon in tab_defs:
            is_sel = state["active_tab"] == t_key
            tab_pills.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=14, vertical=8),
                    border_radius=10,
                    bgcolor=ft.Colors.PRIMARY if is_sel else ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
                    ink=True,
                    on_click=lambda ev, tk=t_key: _set_active_tab(tk),
                    content=ft.Row(
                        [
                            ft.Icon(t_icon, size=16, color=ft.Colors.ON_PRIMARY if is_sel else ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(
                                t_label,
                                size=12.5,
                                weight=ft.FontWeight.BOLD if is_sel else ft.FontWeight.W_500,
                                color=ft.Colors.ON_PRIMARY if is_sel else ft.Colors.ON_SURFACE,
                            ),
                        ],
                        spacing=6,
                        tight=True,
                    ),
                )
            )

        content_area.controls.append(ft.Row(tab_pills, scroll=ft.ScrollMode.AUTO, spacing=8))

        # ── 3. Course & Module Two-Tier Segmentation Filter Bar (Materials / Drills / Live Only) ──
        if state["active_tab"] in ("materials", "drills", "sessions") and len(state["courses"]) > 0:
            course_chips = [
                ft.Chip(
                    label=ft.Text(f"All Courses ({len(state['courses'])})", size=12),
                    selected=state["selected_course_filter"] is None,
                    on_select=lambda ev: page.run_task(_on_course_filter_changed, None),
                )
            ]
            for c in state["courses"]:
                c_id = str(c["id"])
                course_chips.append(
                    ft.Chip(
                        label=ft.Text(c["title"], size=12),
                        selected=state["selected_course_filter"] == c_id,
                        on_select=lambda ev, cid=c_id: page.run_task(_on_course_filter_changed, cid),
                    )
                )

            content_area.controls.append(
                ft.Container(
                    content=ft.Row(course_chips, scroll=ft.ScrollMode.AUTO, spacing=8),
                    padding=ft.Padding.only(bottom=2),
                )
            )

            # Secondary Module Filter Row if a course is selected and has modules (Materials & Drills)
            if state["active_tab"] in ("materials", "drills"):
                active_mods = _get_course_modules(state["selected_course_filter"])
                if active_mods:
                    mod_chips = [
                        ft.Chip(
                            label=ft.Text("All Modules", size=11),
                            selected=state["selected_module_filter"] is None,
                            on_select=lambda ev: page.run_task(_on_module_filter_changed, None),
                        )
                    ]
                    for mod in active_mods:
                        mid = str(mod.get("id"))
                        mod_chips.append(
                            ft.Chip(
                                label=ft.Text(mod.get("title", "Module"), size=11),
                                selected=state["selected_module_filter"] == mid,
                                on_select=lambda ev, m_id=mid: page.run_task(_on_module_filter_changed, m_id),
                            )
                        )
                    content_area.controls.append(
                        ft.Container(
                            content=ft.Row(mod_chips, scroll=ft.ScrollMode.AUTO, spacing=6),
                            padding=ft.Padding.only(bottom=2),
                        )
                    )

        # ── 4. Tab Content Panels ──────────────────────────────────────────

        # PANEL A: LINKED COURSES
        if state["active_tab"] == "courses":
            panel_col = ft.Column(spacing=12)
            if can_manage:
                panel_col.controls.append(
                    ft.Row(
                        [
                            ft.Text("Linked Organisation Courses", weight=ft.FontWeight.BOLD, size=15),
                            ft.Button(
                                "+ Link Courses",
                                icon=ft.Icons.ADD_LINK_ROUNDED,
                                style=ft.ButtonStyle(
                                    bgcolor=ft.Colors.PRIMARY,
                                    color=ft.Colors.ON_PRIMARY,
                                    shape=ft.RoundedRectangleBorder(radius=10),
                                ),
                                on_click=_open_manage_courses_modal,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        wrap=True,
                    )
                )

            if not state["courses"]:
                panel_col.controls.append(
                    ft.Container(
                        padding=44,
                        alignment=ft.Alignment.CENTER,
                        border_radius=14,
                        bgcolor=ft.Colors.SURFACE,
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                        content=ft.Column(
                            [
                                ft.Icon(ft.Icons.MENU_BOOK_ROUNDED, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text("No Courses Linked Yet", weight=ft.FontWeight.BOLD, size=16),
                                ft.Text(
                                    "Link one or more courses to organize materials, module drills, and automatic student enrollment."
                                    if can_manage
                                    else "The instructor has not linked any courses to this Space yet.",
                                    size=13,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                                *(
                                    [
                                        ft.Button(
                                            "+ Link Existing Courses",
                                            icon=ft.Icons.ADD_LINK_ROUNDED,
                                            style=ft.ButtonStyle(bgcolor=ft.Colors.PRIMARY, color=ft.Colors.ON_PRIMARY),
                                            on_click=_open_manage_courses_modal,
                                        )
                                    ]
                                    if can_manage
                                    else []
                                ),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=10,
                        ),
                    )
                )
            else:
                for c in state["courses"]:
                    c_id = str(c["id"])
                    raw_prog = float(c.get("progress", 0.0) or 0.0)
                    if 0.0 < raw_prog <= 1.0:
                        prog_pct = int(round(raw_prog * 100))
                    else:
                        prog_pct = int(round(raw_prog))
                    prog_pct = min(100, max(0, prog_pct))
                    prog_ratio = prog_pct / 100.0
                    mods = c.get("modules") or []

                    async def _unlink_course(ev, cid=c_id, ctitle=c.get("title", "Course")):
                        res = await remove_course_from_space(token=token, space_id=clean_space_id, course_id=cid)
                        if res.get("status") == "success":
                            show_page_snackbar(page, f"Unlinked '{ctitle}' from space.")
                            await _load_hub_data(show_spinner=False)
                        else:
                            show_page_snackbar(page, res.get("message", "Could not unlink course."))

                    mod_pills = [
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                            border_radius=6,
                            bgcolor=ft.Colors.with_opacity(0.07, ft.Colors.PRIMARY),
                            content=ft.Text(m.get("title", "Module"), size=10.5, color=ft.Colors.PRIMARY, weight=ft.FontWeight.W_600),
                        )
                        for m in mods[:4]
                    ]
                    if len(mods) > 4:
                        mod_pills.append(
                            ft.Text(f"+{len(mods) - 4} more modules", size=11, color=ft.Colors.ON_SURFACE_VARIANT)
                        )

                    if can_manage:
                        action_controls = [
                            ft.OutlinedButton(
                                "Preview Course",
                                icon=ft.Icons.OPEN_IN_NEW_ROUNDED,
                                on_click=lambda ev, cid=c_id: page.navigate(f"/courses/{cid}/view"),
                            ),
                            ft.OutlinedButton(
                                "Unlink",
                                icon=ft.Icons.LINK_OFF_ROUNDED,
                                style=ft.ButtonStyle(color=ft.Colors.RED_400),
                                on_click=lambda ev, cid=c_id, ct=c.get("title", "Course"): page.run_task(_unlink_course, ev, cid, ct),
                            ),
                        ]
                    else:
                        action_controls = [
                            ft.Button(
                                "Review Course" if prog_pct >= 100 else ("Resume Course" if prog_pct > 0 else "Start Course"),
                                icon=ft.Icons.PLAY_ARROW_ROUNDED,
                                style=ft.ButtonStyle(
                                    bgcolor=ft.Colors.PRIMARY,
                                    color=ft.Colors.ON_PRIMARY,
                                    shape=ft.RoundedRectangleBorder(radius=10),
                                ),
                                on_click=lambda ev, cid=c_id: page.navigate(f"/courses/{cid}/view"),
                            ),
                        ]

                    info_rows = [
                        ft.Text(c.get("title", "Course"), weight=ft.FontWeight.BOLD, size=15.5),
                        ft.Text(
                            c.get("description") or f"{c.get('module_count', len(mods))} syllabus modules included.",
                            size=12,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        *([ft.Row(mod_pills, spacing=6, wrap=True)] if mod_pills else []),
                    ]
                    if not can_manage:
                        info_rows.append(
                            ft.Row(
                                [
                                    ft.ProgressBar(
                                        value=prog_ratio,
                                        color=ft.Colors.PRIMARY,
                                        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE),
                                        width=180 if is_mob else 240,
                                    ),
                                    ft.Text(f"{prog_pct}% completed", size=11.5, weight=ft.FontWeight.W_600, color=ft.Colors.PRIMARY),
                                ],
                                spacing=10,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            )
                        )

                    info_col = ft.Column(
                        info_rows,
                        spacing=6,
                        expand=not is_mob,
                    )

                    card_body = (
                        ft.Column([info_col, ft.Row(action_controls, spacing=8)], spacing=10)
                        if is_mob
                        else ft.Row(
                            [
                                ft.Container(
                                    width=54,
                                    height=54,
                                    border_radius=12,
                                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                                    alignment=ft.Alignment.CENTER,
                                    content=ft.Icon(ft.Icons.BOOK_ROUNDED, color=ft.Colors.PRIMARY, size=26),
                                ),
                                info_col,
                                ft.Row(action_controls, spacing=6),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=16,
                        )
                    )

                    panel_col.controls.append(
                        ft.Container(
                            padding=16,
                            border_radius=14,
                            bgcolor=ft.Colors.SURFACE,
                            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                            content=card_body,
                        )
                    )
            content_area.controls.append(panel_col)

        # PANEL B: MATERIALS VAULT
        elif state["active_tab"] == "materials":
            panel_col = ft.Column(spacing=12)

            top_mat_row = [mat_search_tf]
            if can_manage:
                top_mat_row.append(
                    ft.Button(
                        "+ Upload Resource",
                        icon=ft.Icons.CLOUD_UPLOAD_ROUNDED,
                        style=ft.ButtonStyle(bgcolor=ft.Colors.PRIMARY, color=ft.Colors.ON_PRIMARY),
                        on_click=_open_upload_modal,
                    )
                )
            panel_col.controls.append(
                ft.Column(top_mat_row, spacing=8) if is_mob else ft.Row(top_mat_row, spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER)
            )

            q_mat = (state["material_search"] or "").strip().lower()
            filtered_mats = [
                m for m in state["materials"]
                if not q_mat or q_mat in " ".join([
                    str(m.get("title") or ""),
                    str(m.get("file_name") or ""),
                    str(m.get("description") or ""),
                    str(m.get("course_title") or ""),
                    str(m.get("module_title") or ""),
                ]).lower()
            ]

            if not filtered_mats:
                panel_col.controls.append(
                    ft.Container(
                        padding=44,
                        alignment=ft.Alignment.CENTER,
                        border_radius=14,
                        bgcolor=ft.Colors.SURFACE,
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                        content=ft.Column(
                            [
                                ft.Icon(ft.Icons.INVENTORY_2_ROUNDED, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(
                                    "No Matching Materials" if q_mat else "Materials Vault is Empty",
                                    weight=ft.FontWeight.BOLD,
                                    size=16,
                                ),
                                ft.Text(
                                    "Try clearing your search filter."
                                    if q_mat
                                    else (
                                        "Upload lecture notes, reference PDFs, slides, and study guides for your learners."
                                        if can_manage
                                        else "No materials have been uploaded to this vault yet. Check back soon for lecture notes and study guides."
                                    ),
                                    size=13,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                                *(
                                    [
                                        ft.Button(
                                            "+ Upload First Resource",
                                            icon=ft.Icons.CLOUD_UPLOAD_ROUNDED,
                                            style=ft.ButtonStyle(bgcolor=ft.Colors.PRIMARY, color=ft.Colors.ON_PRIMARY),
                                            on_click=_open_upload_modal,
                                        )
                                    ]
                                    if (can_manage and not q_mat)
                                    else []
                                ),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=10,
                        ),
                    )
                )
            else:
                for m in filtered_mats:
                    m_id = str(m["id"])
                    f_name = m.get("file_name", "document")
                    icon_code, icon_color = _get_file_icon(f_name)

                    async def _download_mat(ev, url=m.get("file_url"), fname=f_name):
                        await open_or_download_asset(page, url, fname)

                    async def _delete_mat(ev, mid=m_id):
                        del_res = await delete_space_material(token=token, space_id=clean_space_id, material_id=mid)
                        if del_res.get("status") == "success":
                            show_page_snackbar(page, "Resource deleted.")
                            await _load_hub_data(show_spinner=False)
                        else:
                            show_page_snackbar(page, del_res.get("message", "Could not delete resource."))

                    meta_badges = [
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=7, vertical=2),
                            border_radius=6,
                            bgcolor=ft.Colors.with_opacity(0.09, ft.Colors.PRIMARY),
                            content=ft.Text(m.get("course_title", "Course"), size=10.5, color=ft.Colors.PRIMARY, weight=ft.FontWeight.BOLD),
                        ),
                    ]
                    if m.get("module_title"):
                        meta_badges.append(
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=7, vertical=2),
                                border_radius=6,
                                bgcolor=ft.Colors.with_opacity(0.09, ft.Colors.SECONDARY),
                                content=ft.Text(m.get("module_title"), size=10.5, color=ft.Colors.SECONDARY, weight=ft.FontWeight.W_600),
                            )
                        )
                    meta_badges.extend([
                        ft.Text(f"• {_format_filesize(m.get('file_size_bytes', 0))}", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(f"• {_format_relative_time(m.get('created_at'))}", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(f"• By {m.get('uploaded_by_name', 'Tutor')}", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                    ])

                    mat_actions = [
                        ft.OutlinedButton(
                            "Open / Download",
                            icon=ft.Icons.DOWNLOAD_ROUNDED,
                            on_click=lambda ev, u=m.get("file_url"), fn=f_name: page.run_task(_download_mat, ev, u, fn),
                        ),
                    ]
                    if can_manage:
                        mat_actions.append(
                            ft.IconButton(
                                ft.Icons.DELETE_OUTLINE_ROUNDED,
                                tooltip="Delete Resource",
                                icon_color=ft.Colors.RED_400,
                                on_click=lambda ev, mid=m_id: page.run_task(_delete_mat, ev, mid),
                            )
                        )

                    mat_info = ft.Column(
                        [
                            ft.Text(m.get("title", f_name), weight=ft.FontWeight.BOLD, size=14.5),
                            ft.Text(
                                m.get("description", ""),
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                visible=bool(m.get("description")),
                            ),
                            ft.Row(meta_badges, spacing=6, wrap=True),
                        ],
                        spacing=4,
                        expand=not is_mob,
                    )

                    card_content = (
                        ft.Column([mat_info, ft.Row(mat_actions, spacing=8)], spacing=10)
                        if is_mob
                        else ft.Row(
                            [
                                ft.Container(
                                    width=48,
                                    height=48,
                                    border_radius=10,
                                    bgcolor=ft.Colors.with_opacity(0.12, icon_color),
                                    alignment=ft.Alignment.CENTER,
                                    content=ft.Icon(icon_code, color=icon_color, size=24),
                                ),
                                mat_info,
                                ft.Row(mat_actions, spacing=4),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=12,
                        )
                    )

                    panel_col.controls.append(
                        ft.Container(
                            padding=16,
                            border_radius=12,
                            bgcolor=ft.Colors.SURFACE,
                            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                            content=card_content,
                        )
                    )
            content_area.controls.append(panel_col)

        # PANEL C: TOPIC DRILLS & CBT
        elif state["active_tab"] == "drills":
            panel_col = ft.Column(spacing=12)

            top_drill_row = [drill_search_tf]
            if can_manage:
                top_drill_row.append(
                    ft.Button(
                        "+ Create CBT Drill (AI / Studio)",
                        icon=ft.Icons.AUTO_AWESOME_ROUNDED,
                        style=ft.ButtonStyle(bgcolor=ft.Colors.PRIMARY, color=ft.Colors.ON_PRIMARY),
                        on_click=_open_create_drill_modal,
                    )
                )
            panel_col.controls.append(
                ft.Column(top_drill_row, spacing=8) if is_mob else ft.Row(top_drill_row, spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER)
            )

            q_dr = (state["drill_search"] or "").strip().lower()
            filtered_quizzes = [
                q for q in state["quizzes"]
                if not q_dr or q_dr in " ".join([
                    str(q.get("title") or ""),
                    str(q.get("description") or ""),
                    str(q.get("course_title") or ""),
                    str(q.get("module_title") or ""),
                ]).lower()
            ]

            if not filtered_quizzes:
                panel_col.controls.append(
                    ft.Container(
                        padding=44,
                        alignment=ft.Alignment.CENTER,
                        border_radius=14,
                        bgcolor=ft.Colors.SURFACE,
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                        content=ft.Column(
                            [
                                ft.Icon(ft.Icons.PSYCHOLOGY_ROUNDED, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(
                                    "No Matching CBT Drills" if q_dr else "No Topic Drills Published Yet",
                                    weight=ft.FontWeight.BOLD,
                                    size=16,
                                ),
                                ft.Text(
                                    "Try clearing your search filter."
                                    if q_dr
                                    else (
                                        "Create interactive topic quizzes and practice drills from your course materials."
                                        if can_manage
                                        else "No topic drills or practice questions have been published yet. Check back soon!"
                                    ),
                                    size=13,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                                *(
                                    [
                                        ft.Button(
                                            "+ Create First CBT Drill with AI",
                                            icon=ft.Icons.AUTO_AWESOME_ROUNDED,
                                            style=ft.ButtonStyle(bgcolor=ft.Colors.PRIMARY, color=ft.Colors.ON_PRIMARY),
                                            on_click=_open_create_drill_modal,
                                        )
                                    ]
                                    if (can_manage and not q_dr)
                                    else []
                                ),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=10,
                        ),
                    )
                )
            else:
                for q in filtered_quizzes:
                    q_id = str(q["id"])
                    q_title = q.get("title", "Topic Drill")
                    my_score = q.get("my_best_score")
                    attempts_cnt = q.get("my_attempt_count", 0)
                    has_passed = q.get("my_has_passed", False)
                    class_attempts = q.get("total_class_attempts", 0)

                    async def _del_drill(ev, qid=q_id, qt=q_title):
                        res = await delete_space_quiz(token=token, space_id=clean_space_id, quiz_id=qid)
                        if res.get("status") == "success":
                            show_page_snackbar(page, f"Drill '{qt}' deleted.")
                            await _load_hub_data(show_spinner=False)
                        else:
                            show_page_snackbar(page, res.get("message", "Could not delete drill."))

                    score_pill = None
                    if my_score is not None:
                        score_pill = ft.Container(
                            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                            border_radius=8,
                            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY if has_passed else ft.Colors.AMBER_600),
                            content=ft.Text(
                                f"Best: {my_score}% ({'Passed' if has_passed else 'Retry'})",
                                size=11,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.PRIMARY if has_passed else ft.Colors.AMBER_400,
                            ),
                        )

                    drill_badges = [
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=7, vertical=2),
                            border_radius=6,
                            bgcolor=ft.Colors.with_opacity(0.09, ft.Colors.PRIMARY),
                            content=ft.Text(q.get("course_title", "Course"), size=10.5, color=ft.Colors.PRIMARY, weight=ft.FontWeight.BOLD),
                        ),
                    ]
                    if q.get("module_title"):
                        drill_badges.append(
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=7, vertical=2),
                                border_radius=6,
                                bgcolor=ft.Colors.with_opacity(0.09, ft.Colors.SECONDARY),
                                content=ft.Text(q.get("module_title"), size=10.5, color=ft.Colors.SECONDARY, weight=ft.FontWeight.W_600),
                            )
                        )
                    drill_badges.extend([
                        ft.Text(f"• {q.get('question_count', 0)} Questions", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(
                            f"• ⏱ {q.get('time_limit_minutes', 0)} mins" if q.get("time_limit_minutes") else "• Self-paced",
                            size=11,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Text(f"• Pass: {int(q.get('passing_score_percentage', 70))}%", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                    ])
                    if can_manage:
                        drill_badges.append(
                            ft.Text(f"• 👥 {class_attempts} class attempts", size=11, weight=ft.FontWeight.W_600, color=ft.Colors.PRIMARY)
                        )

                    drill_actions = [
                        ft.Button(
                            "Retake Drill" if attempts_cnt > 0 else "Start CBT Drill",
                            icon=ft.Icons.PLAY_ARROW_ROUNDED,
                            style=ft.ButtonStyle(bgcolor=ft.Colors.PRIMARY, color=ft.Colors.ON_PRIMARY),
                            on_click=lambda ev, qid=q_id, qt=q_title: page.run_task(_launch_quiz_runner, qid, qt),
                        ),
                    ]
                    if can_manage:
                        drill_actions.append(
                            ft.PopupMenuButton(
                                icon=ft.Icons.MORE_VERT_ROUNDED,
                                tooltip="Manage CBT Drill",
                                items=[
                                    ft.PopupMenuItem(
                                        icon=ft.Icons.EDIT_NOTE_ROUNDED,
                                        content="Edit in CBT Curator Studio",
                                        on_click=lambda ev, qobj=q: page.run_task(_edit_drill_in_studio, qobj),
                                    ),
                                    ft.PopupMenuItem(
                                        icon=ft.Icons.LEADERBOARD_ROUNDED,
                                        content="View Class Results & Attempts",
                                        on_click=lambda ev, qobj=q: page.run_task(_open_drill_attempts_modal, qobj),
                                    ),
                                    ft.PopupMenuItem(
                                        icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                        content="Delete Drill",
                                        on_click=lambda ev, qid=q_id, qt=q_title: page.run_task(_del_drill, ev, qid, qt),
                                    ),
                                ],
                            )
                        )

                    drill_info = ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(q_title, weight=ft.FontWeight.BOLD, size=15),
                                    *([score_pill] if score_pill else []),
                                ],
                                spacing=8,
                                wrap=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            ft.Text(
                                q.get("description", ""),
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                visible=bool(q.get("description")),
                            ),
                            ft.Row(drill_badges, spacing=6, wrap=True),
                        ],
                        spacing=4,
                        expand=not is_mob,
                    )

                    card_content = (
                        ft.Column([drill_info, ft.Row(drill_actions, spacing=8)], spacing=10)
                        if is_mob
                        else ft.Row(
                            [
                                ft.Container(
                                    width=48,
                                    height=48,
                                    border_radius=10,
                                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                                    alignment=ft.Alignment.CENTER,
                                    content=ft.Icon(ft.Icons.QUIZ_ROUNDED, color=ft.Colors.PRIMARY, size=24),
                                ),
                                drill_info,
                                ft.Row(drill_actions, spacing=4),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=12,
                        )
                    )

                    panel_col.controls.append(
                        ft.Container(
                            padding=16,
                            border_radius=12,
                            bgcolor=ft.Colors.SURFACE,
                            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                            content=card_content,
                        )
                    )
            content_area.controls.append(panel_col)

        # PANEL D: LIVE CLASSES & SESSIONS
        elif state["active_tab"] == "sessions":
            panel_col = ft.Column(spacing=12)

            if can_manage:
                panel_col.controls.append(
                    ft.Row(
                        [
                            ft.Text("Scheduled Classes & Live Meeting Links", weight=ft.FontWeight.BOLD, size=15, color=ft.Colors.ON_SURFACE),
                            ft.Button(
                                "+ Schedule Live Class",
                                icon=ft.Icons.VIDEO_CALL_ROUNDED,
                                style=ft.ButtonStyle(bgcolor=ft.Colors.PRIMARY, color=ft.Colors.ON_PRIMARY),
                                on_click=_open_schedule_session_modal,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        wrap=True,
                    )
                )

            if not state["sessions"]:
                panel_col.controls.append(
                    ft.Container(
                        padding=44,
                        alignment=ft.Alignment.CENTER,
                        border_radius=14,
                        bgcolor=ft.Colors.SURFACE,
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                        content=ft.Column(
                            [
                                ft.Icon(ft.Icons.VIDEO_CAMERA_FRONT_ROUNDED, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text("No Live Classes Scheduled Yet", weight=ft.FontWeight.BOLD, size=16),
                                ft.Text(
                                    (
                                        "Schedule upcoming live classes and share meeting links with your learners."
                                        if can_manage
                                        else "No upcoming live classes right now. When a class is scheduled, you'll see the time and meeting link here."
                                    ),
                                    size=13,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                                *(
                                    [
                                        ft.Button(
                                            "+ Schedule First Class",
                                            icon=ft.Icons.VIDEO_CALL_ROUNDED,
                                            style=ft.ButtonStyle(bgcolor=ft.Colors.PRIMARY, color=ft.Colors.ON_PRIMARY),
                                            on_click=_open_schedule_session_modal,
                                        )
                                    ]
                                    if can_manage
                                    else []
                                ),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=10,
                        ),
                    )
                )
            else:
                for s in state["sessions"]:
                    s_id = str(s["id"])
                    meet_link = s.get("meeting_link", "")
                    is_upcoming = bool(s.get("is_upcoming", False))

                    async def _join_meeting(ev, url=meet_link):
                        if url:
                            await page.launch_url(url)

                    async def _copy_meet_link(ev, url=meet_link):
                        if url:
                            await safe_set_clipboard(page, url)
                            show_page_snackbar(page, "Meeting link copied to clipboard!")

                    async def _cancel_sess(ev, sid=s_id):
                        del_res = await cancel_scheduled_session(token=token, space_id=clean_space_id, session_id=sid)
                        if del_res.get("status") == "success":
                            show_page_snackbar(page, "Session removed.")
                            await _load_hub_data(show_spinner=False)
                        else:
                            show_page_snackbar(page, del_res.get("message", "Failed to cancel."))

                    sess_info = ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(s.get("title", "Live Class"), weight=ft.FontWeight.BOLD, size=15),
                                    ft.Container(
                                        padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                                        border_radius=6,
                                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY if is_upcoming else ft.Colors.ON_SURFACE),
                                        content=ft.Text(
                                            "UPCOMING" if is_upcoming else "PAST",
                                            size=10,
                                            weight=ft.FontWeight.BOLD,
                                            color=ft.Colors.PRIMARY if is_upcoming else ft.Colors.ON_SURFACE_VARIANT,
                                        ),
                                    ),
                                    *(
                                        [
                                            ft.Container(
                                                padding=ft.Padding.symmetric(horizontal=7, vertical=2),
                                                border_radius=6,
                                                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                                                content=ft.Text(s.get("course_title"), size=10, color=ft.Colors.PRIMARY, weight=ft.FontWeight.W_600),
                                            )
                                        ]
                                        if s.get("course_title")
                                        else []
                                    ),
                                ],
                                spacing=8,
                                wrap=True,
                            ),
                            ft.Text(
                                s.get("description", ""),
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                visible=bool(s.get("description")),
                            ),
                            ft.Row(
                                [
                                    ft.Text(f"📅 {_format_datetime(s.get('start_time'))}", size=12, weight=ft.FontWeight.W_600),
                                    ft.Text(f"• {s.get('duration_minutes', 60)} mins", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ft.Text(f"• Host: {s.get('creator_name', 'Tutor')}", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                                spacing=6,
                                wrap=True,
                            ),
                        ],
                        spacing=4,
                        expand=not is_mob,
                    )

                    sess_actions = [
                        ft.IconButton(
                            ft.Icons.COPY_ROUNDED,
                            tooltip="Copy Meeting Link",
                            on_click=lambda ev, u=meet_link: page.run_task(_copy_meet_link, ev, u),
                        ),
                        ft.Button(
                            "Join Class",
                            icon=ft.Icons.OPEN_IN_NEW_ROUNDED,
                            style=ft.ButtonStyle(bgcolor=ft.Colors.PRIMARY, color=ft.Colors.ON_PRIMARY),
                            on_click=lambda ev, u=meet_link: page.run_task(_join_meeting, ev, u),
                        ),
                    ]
                    if can_manage:
                        sess_actions.append(
                            ft.IconButton(
                                ft.Icons.DELETE_OUTLINE_ROUNDED,
                                tooltip="Cancel / Remove Session",
                                icon_color=ft.Colors.RED_400,
                                on_click=lambda ev, sid=s_id: page.run_task(_cancel_sess, ev, sid),
                            )
                        )

                    card_content = (
                        ft.Column([sess_info, ft.Row(sess_actions, spacing=8)], spacing=10)
                        if is_mob
                        else ft.Row(
                            [
                                ft.Container(
                                    width=48,
                                    height=48,
                                    border_radius=10,
                                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY if is_upcoming else ft.Colors.ON_SURFACE),
                                    alignment=ft.Alignment.CENTER,
                                    content=ft.Icon(
                                        ft.Icons.VIDEO_CALL_ROUNDED,
                                        color=ft.Colors.PRIMARY if is_upcoming else ft.Colors.ON_SURFACE_VARIANT,
                                        size=24,
                                    ),
                                ),
                                sess_info,
                                ft.Row(sess_actions, spacing=4),
                            ],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=12,
                        )
                    )

                    panel_col.controls.append(
                        ft.Container(
                            padding=16,
                            border_radius=12,
                            bgcolor=ft.Colors.SURFACE,
                            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                            content=card_content,
                        )
                    )
            content_area.controls.append(panel_col)

        # PANEL E: MEMBERS & CO-TUTORS ROSTER
        elif state["active_tab"] == "members":
            panel_col = ft.Column(spacing=12)
            invite_top_btn = ft.Button(
                "Invite Learners",
                icon=ft.Icons.PERSON_ADD_ROUNDED,
                style=ft.ButtonStyle(
                    bgcolor=ft.Colors.PRIMARY,
                    color=ft.Colors.ON_PRIMARY,
                    shape=ft.RoundedRectangleBorder(radius=8),
                ),
                on_click=_open_invite_modal,
            )
            top_member_row = (
                ft.Column([member_search_tf, invite_top_btn], spacing=8)
                if is_mob
                else ft.Row(
                    [member_search_tf, *([invite_top_btn] if can_manage else [])],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
            panel_col.controls.append(top_member_row)

            q_mem = (state["member_search"] or "").strip().lower()
            filtered_members = [
                m for m in state["members"]
                if not q_mem or q_mem in " ".join([
                    str(m.get("name") or ""),
                    str(m.get("username") or ""),
                    str(m.get("email") or ""),
                    str(m.get("role") or ""),
                ]).lower()
            ]

            if not filtered_members:
                panel_col.controls.append(
                    ft.Container(
                        padding=40,
                        alignment=ft.Alignment.CENTER,
                        content=ft.Text("No matching members found.", size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                    )
                )
            else:
                for m in filtered_members:
                    m_uid = str(m.get("user_id"))
                    m_name = m.get("name", "Member")
                    m_role = str(m.get("role") or "student").lower()
                    m_is_creator = bool(m.get("is_creator", False))

                    async def _toggle_role(ev, uid=m_uid, cur_r=m_role, uname=m_name):
                        new_r = "student" if cur_r in ("tutor", "manager") else "tutor"
                        res = await update_space_member_role(token=token, space_id=clean_space_id, member_user_id=uid, role=new_r)
                        if res.get("status") == "success":
                            show_page_snackbar(page, f"{uname} is now a {new_r.upper()}!")
                            await _load_hub_data(show_spinner=False)
                        else:
                            show_page_snackbar(page, res.get("message", "Could not update role."))

                    async def _kick_member(ev, uid=m_uid, uname=m_name):
                        res = await remove_space_member(token=token, space_id=clean_space_id, member_user_id=uid)
                        if res.get("status") == "success":
                            show_page_snackbar(page, f"Removed {uname} from space.")
                            await _load_hub_data(show_spinner=False)
                        else:
                            show_page_snackbar(page, res.get("message", "Could not remove member."))

                    role_badge = ft.Container(
                        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                        border_radius=6,
                        bgcolor=ft.Colors.with_opacity(
                            0.12,
                            ft.Colors.PRIMARY if (m_is_creator or m_role in ("tutor", "manager")) else ft.Colors.ON_SURFACE,
                        ),
                        content=ft.Text(
                            "CREATOR" if m_is_creator else m_role.upper(),
                            size=10,
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.PRIMARY if (m_is_creator or m_role in ("tutor", "manager")) else ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    )

                    mem_menu = None
                    if can_manage and not m_is_creator and m_uid != current_user_id:
                        mem_menu = ft.PopupMenuButton(
                            icon=ft.Icons.MORE_VERT_ROUNDED,
                            items=[
                                ft.PopupMenuItem(
                                    icon=ft.Icons.SCHOOL_ROUNDED,
                                    content="Demote to Student" if m_role in ("tutor", "manager") else "Promote to Co-Tutor",
                                    on_click=lambda ev, uid=m_uid, cr=m_role, un=m_name: page.run_task(_toggle_role, ev, uid, cr, un),
                                ),
                                ft.PopupMenuItem(
                                    icon=ft.Icons.PERSON_REMOVE_ROUNDED,
                                    content="Remove from Space",
                                    on_click=lambda ev, uid=m_uid, un=m_name: page.run_task(_kick_member, ev, uid, un),
                                ),
                            ],
                        )

                    panel_col.controls.append(
                        ft.Container(
                            padding=12,
                            border_radius=12,
                            bgcolor=ft.Colors.SURFACE,
                            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                            content=ft.Row(
                                [
                                    ft.CircleAvatar(
                                        radius=18,
                                        bgcolor=ft.Colors.with_opacity(0.14, ft.Colors.PRIMARY),
                                        content=ft.Text((m_name or "U")[0].upper(), weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                                    ),
                                    ft.Column(
                                        [
                                            ft.Text(m_name, weight=ft.FontWeight.BOLD, size=14),
                                            ft.Text(
                                                f"{m.get('email') or ('@' + str(m.get('username')) if m.get('username') else 'Member')} • Joined {_format_relative_time(m.get('joined_at'))}",
                                                size=11.5,
                                                color=ft.Colors.ON_SURFACE_VARIANT,
                                            ),
                                        ],
                                        spacing=2,
                                        expand=True,
                                    ),
                                    role_badge,
                                    *([mem_menu] if mem_menu else []),
                                ],
                                spacing=10,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        )
                    )
            content_area.controls.append(panel_col)

    # Initial pre-fetch so load_view handles skeleton transition smoothly
    try:
        res = await get_space_details(token=token, space_id=clean_space_id)
        if res.get("status") == "success":
            state["space"] = res.get("space", {})
            state["courses"] = state["space"].get("courses", [])

            c_filter = state["selected_course_filter"]
            m_filter = state["selected_module_filter"]

            mat_res, quiz_res, sess_res, mem_res = await asyncio.gather(
                get_space_materials(token=token, space_id=clean_space_id, course_id=c_filter, module_id=m_filter),
                get_space_quizzes(token=token, space_id=clean_space_id, course_id=c_filter, module_id=m_filter),
                get_scheduled_sessions(token=token, space_id=clean_space_id, course_id=c_filter),
                get_space_members(token=token, space_id=clean_space_id),
            )
            state["materials"] = mat_res.get("materials", []) if isinstance(mat_res, dict) else []
            state["quizzes"] = quiz_res.get("quizzes", []) if isinstance(quiz_res, dict) else []
            state["sessions"] = sess_res.get("sessions", []) if isinstance(sess_res, dict) else []
            state["members"] = mem_res.get("members", []) if isinstance(mem_res, dict) else []
        else:
            show_page_snackbar(page, res.get("message", "Failed to load Course Space."))
    except Exception as ex:
        print(f"[CourseSpaceHub] Initial fetch error: {ex}")
    finally:
        state["loading"] = False

    _render_view()

    # If deep-linked to a specific quiz_id, auto-launch the drill runner
    if state.get("pending_deep_quiz_id"):
        target_qid = state["pending_deep_quiz_id"]
        state["pending_deep_quiz_id"] = None
        matched_q = next((q for q in state["quizzes"] if str(q.get("id")) == str(target_qid)), None)
        q_title = matched_q.get("title", "Practice Drill") if matched_q else "Practice Drill"
        page.run_task(_launch_quiz_runner, str(target_qid), q_title)

    return ft.View(
        route=f"/spaces/{clean_space_id}/manage" if is_manage_mode else f"/spaces/{clean_space_id}",
        bgcolor=ft.Colors.SURFACE,
        controls=[
            ft.SafeArea(
                expand=True,
                content=ft.Container(
                    content=ft.Column(
                        [content_area],
                        scroll=ft.ScrollMode.AUTO,
                        expand=True,
                        spacing=16,
                    ),
                    padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                    expand=True,
                ),
            )
        ],
    )
