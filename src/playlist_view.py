"""
Modern Sleek Playlist / Learning Path View for Nu-Age LMS.
Provides a comprehensive roadmap view with sequential curriculum timeline,
single-tap full path enrollment, real-time course progress tracking,
and responsive multi-column layout aligned with the modern LMS design system.
"""

import asyncio
import urllib.parse
from typing import Any, Dict, List, Optional
import flet as ft

from src.requests.playlists import get_playlist, enroll_in_playlist
from src.requests.enrollments import enrol_user, get_enrollments
from src.requests.Courses import get_courses

UI_ACCENT = ft.Colors.PRIMARY


# ─────────────────────────────────────────────────────────────────────────────
# VIEW: Modern Sleek Playlist / Learning Path View
# ─────────────────────────────────────────────────────────────────────────────
async def playlist_view(page: ft.Page, playlist_id: str, back_target: str = "/courses"):
    """
    Renders the modern, comprehensive Learning Path / Playlist view.
    """
    token: Optional[str] = None
    playlist_data: Dict[str, Any] = {}
    playlist_courses: List[Dict[str, Any]] = []
    user_enrollments: List[Dict[str, Any]] = []
    completed_course_ids: set = set()

    # Content Socket Ref
    content_socket = ft.Ref[ft.Container]()

    # ── WhatsApp Share Handler ────────────────────────────────────────────────
    async def open_whatsapp_share(e):
        title = playlist_data.get("name") or "Learning Path"
        num_courses = len(playlist_courses)
        message = (
            f'Hey! Check out the curated learning path "{title}" ({num_courses} courses) on Nu-Age! 🚀\n\n'
            f"It features step-by-step interactive modules, flashcards, quizzes, and smart AI tutoring!\n\n"
            f"Check it out 👉 : nu-age.com.ng"
        )
        encoded_message = urllib.parse.quote(message)
        await page.launch_url(f"https://wa.me/?text={encoded_message}")

    # ── Top AppBar ────────────────────────────────────────────────────────────
    app_bar = ft.AppBar(
        bgcolor=ft.Colors.SURFACE,
        title=ft.Text(
            "Learning Path",
            color=ft.Colors.ON_SURFACE,
            weight=ft.FontWeight.W_700,
            size=16,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        ),
        leading=ft.IconButton(
            icon=ft.Icons.ARROW_BACK_ROUNDED,
            icon_color=ft.Colors.ON_SURFACE,
            tooltip="Back to Catalog",
            on_click=lambda _: page.go(back_target),
        ),
        actions=[
            ft.IconButton(
                icon=ft.Icons.SHARE_OUTLINED,
                icon_color=ft.Colors.ON_SURFACE,
                tooltip="Share Learning Path via WhatsApp",
                on_click=open_whatsapp_share,
            ),
            ft.IconButton(
                icon=ft.Icons.REFRESH_ROUNDED,
                icon_color=ft.Colors.ON_SURFACE,
                tooltip="Refresh",
                on_click=lambda _: asyncio.create_task(refresh_view()),
            ),
            ft.Container(width=8),
        ],
        elevation=0,
    )

    # ── Data Loader ───────────────────────────────────────────────────────────
    async def load_data():
        nonlocal token, playlist_data, playlist_courses, user_enrollments, completed_course_ids
        try:
            token = await page.shared_preferences.get("auth_token")
        except Exception:
            token = None

        # 1. Fetch Playlist Details
        try:
            res = await get_playlist(token, playlist_id)
            if isinstance(res, dict) and "error" not in res:
                playlist_data = res
                raw_courses = res.get("playlist_courses", [])
                if isinstance(raw_courses, list):
                    # Sort courses by order_index to preserve pedagogical sequence
                    sorted_items = sorted(
                        raw_courses,
                        key=lambda x: (x.get("order_index", 0) if isinstance(x, dict) else 0)
                    )
                    playlist_courses = [
                        item.get("course", {})
                        for item in sorted_items
                        if isinstance(item, dict) and "course" in item and item.get("course")
                    ]
                else:
                    playlist_courses = []
            else:
                playlist_data = {"error": res.get("error", "Playlist not found") if isinstance(res, dict) else "Failed"}
                playlist_courses = []
        except Exception as ex:
            playlist_data = {"error": str(ex)}
            playlist_courses = []

        # 2. Fetch User Enrollments & Completed Courses
        try:
            enr_res = await asyncio.wait_for(get_enrollments(token, None), timeout=12)
            user_enrollments = enr_res if isinstance(enr_res, list) else []
        except Exception:
            user_enrollments = []

        try:
            comp_res = await asyncio.wait_for(get_courses(token, {"progress": 100}), timeout=12)
            if isinstance(comp_res, list):
                completed_course_ids = {str(c.get("id")) for c in comp_res if isinstance(c, dict) and c.get("id")}
            else:
                completed_course_ids = set()
        except Exception:
            completed_course_ids = set()

    # ── Refresh Trigger ───────────────────────────────────────────────────────
    async def refresh_view():
        if content_socket.current:
            content_socket.current.alignment = ft.Alignment.CENTER
            content_socket.current.content = ft.Column(
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
                controls=[
                    ft.ProgressRing(color=UI_ACCENT, width=36, height=36, stroke_width=3),
                    ft.Text("Refreshing learning path…", size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
            )
            page.update()

        await load_data()
        if content_socket.current:
            content_socket.current.alignment = None
            content_socket.current.content = build_main_content()
            page.update()

    # ── Bulk / Path Enrollment Handler ────────────────────────────────────────
    async def handle_path_enroll(e):
        if e.control.disabled:
            return

        e.control.disabled = True
        orig_content = e.control.content
        e.control.content = ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            tight=True,
            spacing=8,
            controls=[
                ft.ProgressRing(width=16, height=16, color=ft.Colors.ON_PRIMARY, stroke_width=2),
                ft.Text("Enrolling in Path…", color=ft.Colors.ON_PRIMARY, size=13, weight=ft.FontWeight.W_600),
            ],
        )
        page.update()

        try:
            # 1. Attempt single-tap playlist enrollment endpoint
            res = await asyncio.wait_for(enroll_in_playlist(token, playlist_id), timeout=15)
            has_error = isinstance(res, dict) and "error" in res

            # 2. Fallback / ensure individual courses enrolled if bulk was partial
            enrolled_ids = {str(c.get("id")) for c in user_enrollments if isinstance(c, dict)}
            for c in playlist_courses:
                c_id = str(c.get("id"))
                if c_id and c_id not in enrolled_ids:
                    try:
                        await enrol_user(token, c_id, None)
                    except Exception:
                        pass

            page.show_dialog(
                ft.SnackBar(
                    content=ft.Row(
                        spacing=8,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.WHITE, size=18),
                            ft.Text("Enrolled in learning path successfully! 🎉", color=ft.Colors.WHITE),
                        ],
                    ),
                    bgcolor=ft.Colors.GREEN_700,
                    duration=ft.Duration(milliseconds=2500),
                )
            )
        except Exception as ex:
            page.show_dialog(
                ft.SnackBar(
                    content=ft.Text(f"Enrollment note: {ex}"),
                    bgcolor=ft.Colors.PRIMARY,
                    duration=ft.Duration(milliseconds=2500),
                )
            )

        await refresh_view()

    # ── Single Course Quick Enroll Handler ────────────────────────────────────
    def make_course_enroll_handler(course_id: str, btn_ref):
        async def handler(e):
            if btn_ref.current:
                btn_ref.current.disabled = True
                btn_ref.current.content = "Enrolling…"
                page.update()

            try:
                await enrol_user(token, course_id, None)
                page.show_dialog(
                    ft.SnackBar(
                        content=ft.Text("Course enrolled!"),
                        bgcolor=ft.Colors.PRIMARY,
                        duration=ft.Duration(milliseconds=2000),
                    )
                )
            except Exception as ex:
                page.show_dialog(
                    ft.SnackBar(content=ft.Text(f"Could not enroll: {ex}"), duration=ft.Duration(milliseconds=2000))
                )

            await refresh_view()
        return handler

    # ── Resume Learning Handler ───────────────────────────────────────────────
    def handle_resume_learning(_):
        """Routes learner directly to the first uncompleted or current course in the path."""
        enrolled_ids = {str(c.get("id")) for c in user_enrollments if isinstance(c, dict)}
        for c in playlist_courses:
            cid = str(c.get("id"))
            if cid in enrolled_ids and cid not in completed_course_ids:
                page.go(f"/courses/{cid}/view")
                return

        # If all courses completed or none marked, open the first course
        if playlist_courses:
            first_id = playlist_courses[0].get("id")
            page.go(f"/courses/{first_id}/view")
        else:
            page.go("/courses")

    # ── View Construction ─────────────────────────────────────────────────────
    def build_main_content() -> ft.Control:
        if not playlist_data or "error" in playlist_data:
            err_msg = playlist_data.get("error", "Playlist not found") if isinstance(playlist_data, dict) else "Could not load playlist"
            return ft.Container(
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding.all(40),
                content=ft.Column(
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=16,
                    controls=[
                        ft.Icon(ft.Icons.PLAYLIST_REMOVE_ROUNDED, size=56, color=ft.Colors.RED_400),
                        ft.Text(err_msg, size=16, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                        ft.ElevatedButton(
                            "Return to Catalog",
                            icon=ft.Icons.ARROW_BACK_ROUNDED,
                            on_click=lambda _: page.go("/courses"),
                        ),
                    ],
                ),
            )

        name = playlist_data.get("name") or "Untitled Learning Path"
        description = playlist_data.get("description") or "Curated sequential curriculum designed for comprehensive skill mastery."
        image_url = playlist_data.get("image_url")
        org_name = playlist_data.get("Organisation") or "Nu-Age Learning Hub"
        rating = round(float(playlist_data.get("rating") or 4.9), 1)
        is_public = playlist_data.get("is_public", True)

        # Update AppBar Title
        app_bar.title = ft.Text(
            name,
            color=ft.Colors.ON_SURFACE,
            weight=ft.FontWeight.W_700,
            size=16,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        # Build Enrolled Lookup Map
        enrolled_map: Dict[str, Dict[str, Any]] = {}
        for item in user_enrollments:
            if isinstance(item, dict) and item.get("id"):
                enrolled_map[str(item.get("id"))] = item

        total_courses = len(playlist_courses)
        enrolled_count = sum(1 for c in playlist_courses if str(c.get("id")) in enrolled_map)
        completed_count = sum(1 for c in playlist_courses if str(c.get("id")) in completed_course_ids)

        all_enrolled = (total_courses > 0) and (enrolled_count == total_courses)
        all_completed = (total_courses > 0) and (completed_count == total_courses)

        # Compute average progression across path
        total_progress_sum = 0.0
        for c in playlist_courses:
            cid = str(c.get("id"))
            if cid in completed_course_ids:
                total_progress_sum += 100.0
            elif cid in enrolled_map:
                raw_prog = enrolled_map[cid].get("progress", 0.0)
                total_progress_sum += (raw_prog * 100.0 if raw_prog <= 1.0 else raw_prog)
        avg_path_progress = round(total_progress_sum / total_courses, 1) if total_courses > 0 else 0.0
        path_progress_fraction = min(1.0, max(0.0, avg_path_progress / 100.0))

        # Approximate curriculum total hours (~2.5h per course average)
        est_hours = round(total_courses * 2.5, 1)

        # Screen width responsive check
        page_w = getattr(page, "width", None) or 1080
        is_mobile = page_w < 650
        is_desktop = page_w >= 960

        # ── UI Helpers ────────────────────────────────────────────────────────
        def pill_badge(text: str, icon=None, bg=None, fg=None):
            controls = []
            if icon:
                controls.append(ft.Icon(icon, size=10, color=fg or UI_ACCENT))
            controls.append(ft.Text(text, size=9, color=fg or UI_ACCENT, weight=ft.FontWeight.W_600))
            return ft.Container(
                padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                border_radius=ft.BorderRadius.all(8),
                bgcolor=bg or ft.Colors.with_opacity(0.08, UI_ACCENT),
                content=ft.Row(controls, tight=True, spacing=5),
            )

        # ── 1. Hero Banner ────────────────────────────────────────────────────
        badges_row = ft.Row(
            wrap=True,
            spacing=8,
            controls=[
                pill_badge("LEARNING PATH", icon=ft.Icons.FORMAT_LIST_BULLETED_ROUNDED,
                           bg=ft.Colors.with_opacity(0.12, UI_ACCENT), fg=UI_ACCENT),
                pill_badge(f"~{est_hours} Hours", icon=ft.Icons.TIMELAPSE_ROUNDED,
                           bg=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE), fg=ft.Colors.ON_SURFACE),
            ],
        )

        hero_left = ft.Column(
            spacing=16,
            controls=[
                badges_row,
                ft.Text(
                    name,
                    size=26 if is_mobile else 30,
                    weight=ft.FontWeight.W_800,
                    color=ft.Colors.ON_SURFACE,
                    max_lines=2,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                ft.Text(
                    description,
                    size=14,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                    selectable=True,
                    style=ft.TextStyle(height=1.4),
                ),
            ],
        )

        # High-Fidelity Cover Frame with Stacked Depth
        cover_image_content = ft.Container(
            border_radius=ft.BorderRadius.all(18),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
            shadow=ft.BoxShadow(
                blur_radius=18,
                color=ft.Colors.with_opacity(0.1, ft.Colors.BLACK),
                offset=ft.Offset(0, 6),
            ),
            content=ft.Stack(
                controls=[
                    ft.Image(
                        src=image_url if image_url else "assets/placeholder.png",
                        fit=ft.BoxFit.COVER,
                        width=float("inf"),
                        height=210,
                    ),
                    # Subtle dark gradient overlay
                    ft.Container(
                        gradient=ft.LinearGradient(
                            begin=ft.Alignment.TOP_CENTER,
                            end=ft.Alignment.BOTTOM_CENTER,
                            colors=[ft.Colors.TRANSPARENT, ft.Colors.with_opacity(0.65, ft.Colors.BLACK)],
                        ),
                        expand=True,
                    ),
                    # Bottom Path Pill
                    ft.Container(
                        bottom=12,
                        left=12,
                        padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                        border_radius=ft.BorderRadius.all(8),
                        bgcolor=ft.Colors.with_opacity(0.85, ft.Colors.BLACK),
                        content=ft.Row(
                            tight=True,
                            spacing=5,
                            controls=[
                                ft.Icon(ft.Icons.PLAYLIST_PLAY_ROUNDED, color=ft.Colors.WHITE, size=16),
                                ft.Text(f"{total_courses} Courses", size=11, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                            ],
                        ),
                    ),
                    # Enrolled Banner Tag
                    ft.Container(
                        top=12,
                        right=12,
                        visible=all_enrolled or (enrolled_count > 0),
                        padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                        border_radius=ft.BorderRadius.all(20),
                        bgcolor=ft.Colors.GREEN_700 if all_completed else UI_ACCENT,
                        content=ft.Row(
                            tight=True,
                            spacing=4,
                            controls=[
                                ft.Icon(
                                    ft.Icons.CHECK_CIRCLE_ROUNDED if all_completed else ft.Icons.BOOKMARK_ADDED_ROUNDED,
                                    color=ft.Colors.ON_PRIMARY,
                                    size=13,
                                ),
                                ft.Text(
                                    "Completed" if all_completed else (f"Enrolled ({enrolled_count}/{total_courses})"),
                                    color=ft.Colors.ON_PRIMARY,
                                    size=11,
                                    weight=ft.FontWeight.BOLD,
                                ),
                            ],
                        ),
                    ),
                ]
            ),
        )

        hero_card = ft.Container(
            bgcolor=ft.Colors.SURFACE,
            border_radius=ft.BorderRadius.all(20),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            padding=ft.Padding.all(20 if is_mobile else 24),
            margin=ft.Margin.only(bottom=24),
            content=ft.ResponsiveRow(
                columns=12,
                spacing=20,
                run_spacing=20,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(content=hero_left, col={"xs": 12, "md": 7}),
                    ft.Container(content=cover_image_content, col={"xs": 12, "md": 5}),
                ],
            ),
        )

        # ── 2. Course Sequence Timeline Cards ─────────────────────────────────
        def render_course_sequence_card(idx: int, course: Dict[str, Any], is_last: bool) -> ft.Control:
            cid = str(course.get("id") or "")
            c_name = course.get("name") or "Untitled Course"
            c_desc = course.get("description") or "Core component of this learning journey."
            c_img = course.get("image_url") or ""
            c_cat = (course.get("category") or {}).get("name") if isinstance(course.get("category"), dict) else "Curriculum"
            c_rating = round(float(course.get("rating") or 4.8), 1)

            admin = course.get("admin") or {}
            author_name = f"{admin.get('first_name', '')} {admin.get('last_name', '')}".strip() or "Course Instructor"

            is_enrolled = cid in enrolled_map
            is_completed = cid in completed_course_ids
            raw_prog = enrolled_map.get(cid, {}).get("progress", 0.0) if is_enrolled else 0.0
            prog_val = 100.0 if is_completed else (raw_prog * 100.0 if raw_prog <= 1.0 else raw_prog)
            prog_fraction = min(1.0, max(0.0, prog_val / 100.0))

            step_num = f"{idx + 1:02d}"

            # Step Indicator Node
            if is_completed:
                node_bg = ft.Colors.GREEN_600
                node_content = ft.Icon(ft.Icons.CHECK_ROUNDED, size=16, color=ft.Colors.WHITE)
            elif is_enrolled:
                node_bg = UI_ACCENT
                node_content = ft.Text(step_num, size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_PRIMARY)
            else:
                node_bg = ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)
                node_content = ft.Text(step_num, size=12, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE_VARIANT)

            step_node = ft.Container(
                width=34,
                height=34,
                border_radius=ft.BorderRadius.all(17),
                bgcolor=node_bg,
                alignment=ft.Alignment.CENTER,
                content=node_content,
            )

            # Vertical Connector Guide
            connector_line = ft.Container(
                width=2,
                expand=True,
                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE) if not is_last else ft.Colors.TRANSPARENT,
                margin=ft.Margin.only(top=4, bottom=4),
            )

            stepper_column = ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=0,
                controls=[
                    step_node,
                    connector_line,
                ],
            )

            # Course Status Tag
            if is_completed:
                status_tag = pill_badge("Completed", icon=ft.Icons.CHECK_CIRCLE_ROUNDED,
                                        bg=ft.Colors.with_opacity(0.12, ft.Colors.GREEN_600), fg=ft.Colors.GREEN_700)
            elif is_enrolled and prog_val > 0:
                status_tag = pill_badge(f"In Progress ({int(prog_val)}%)", icon=ft.Icons.PLAY_ARROW_ROUNDED,
                                        bg=ft.Colors.with_opacity(0.1, UI_ACCENT), fg=UI_ACCENT)
            elif is_enrolled:
                status_tag = pill_badge("Enrolled • Ready to Start", icon=ft.Icons.FLAG_OUTLINED,
                                        bg=ft.Colors.with_opacity(0.08, ft.Colors.TEAL_600), fg=ft.Colors.TEAL_700)
            else:
                status_tag = pill_badge("Step in Pathway", icon=ft.Icons.AUTO_STORIES_ROUNDED,
                                        bg=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE), fg=ft.Colors.ON_SURFACE_VARIANT)

            # Quick Action Button
            btn_ref = ft.Ref[ft.ElevatedButton]()
            if is_enrolled:
                action_btn = ft.ElevatedButton(
                    content=ft.Row(
                        spacing=6,
                        tight=True,
                        controls=[
                            ft.Text("Continue Course", size=12, weight=ft.FontWeight.BOLD),
                            ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=15),
                        ],
                    ),
                    bgcolor=UI_ACCENT,
                    color=ft.Colors.ON_PRIMARY,
                    height=36,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8),
                        elevation=0,
                    ),
                    on_click=lambda _, c_id=cid: page.go(f"/courses/{c_id}/view"),
                )
            else:
                action_btn = ft.OutlinedButton(
                    content=ft.Row(
                        spacing=6,
                        tight=True,
                        controls=[
                            ft.Text("Course Details", size=12, weight=ft.FontWeight.W_600),
                            ft.Icon(ft.Icons.OPEN_IN_NEW_ROUNDED, size=14),
                        ],
                    ),
                    height=36,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8),
                        side=ft.BorderSide(1, ft.Colors.with_opacity(0.2, ft.Colors.ON_SURFACE)),
                    ),
                    on_click=lambda _, c_id=cid: page.go(f"/courses/{c_id}"),
                )

            # Optional Quick Enroll button if not enrolled
            quick_enroll_btn = None
            if not is_enrolled:
                quick_enroll_btn = ft.TextButton(
                    "Enroll Only This",
                    ref=btn_ref,
                    icon=ft.Icons.ADD_ROUNDED,
                    style=ft.ButtonStyle(color=UI_ACCENT),
                    on_click=make_course_enroll_handler(cid, btn_ref),
                )

            # Course thumbnail
            thumb_widget = ft.Container(
                width=64 if is_mobile else 80,
                height=64 if is_mobile else 80,
                border_radius=ft.BorderRadius.all(10),
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
                content=ft.Image(
                    src=c_img if c_img else "assets/placeholder.png",
                    fit=ft.BoxFit.COVER,
                ),
            )

            # Progress Bar line
            # Assign col props only to non-None buttons for ResponsiveRow
            if quick_enroll_btn:
                quick_enroll_btn.col = {"xs": 6, "md": 6}
                action_btn.col = {"xs": 6, "md": 6}
            else:
                action_btn.col = {"xs": 12}

            progress_strip = None
            if is_enrolled:
                progress_strip = ft.Column(
                    spacing=4,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text(f"Progress", size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(f"{int(prog_val)}%", size=11, weight=ft.FontWeight.BOLD, color=UI_ACCENT),
                            ],
                        ),
                        ft.ProgressBar(
                            value=prog_fraction,
                            color=ft.Colors.GREEN_600 if is_completed else UI_ACCENT,
                            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                            height=4,
                            border_radius=ft.BorderRadius.all(2),
                        ),
                    ],
                )

            # Build the action buttons row as a ResponsiveRow so it wraps on mobile
            action_buttons_row = ft.ResponsiveRow(
                columns=12,
                spacing=8,
                run_spacing=8,
                controls=[
                    *([quick_enroll_btn] if quick_enroll_btn else []),
                    action_btn,
                ],
            )

            # Bottom footer: step label + buttons — use Column to stack on mobile
            step_label = ft.Row(
                spacing=6,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.LAYERS_OUTLINED, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text(f"Step {idx + 1} of {total_courses}", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
            )

            card_footer = ft.Column(
                spacing=10,
                controls=[
                    step_label,
                    action_buttons_row,
                ],
            ) if is_mobile else ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    step_label,
                    action_buttons_row,
                ],
            )

            # Card Container
            card_container = ft.Container(
                bgcolor=ft.Colors.SURFACE,
                border_radius=ft.BorderRadius.all(14),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                padding=ft.Padding.all(14 if is_mobile else 16),
                expand=True,
                shadow=ft.BoxShadow(
                    blur_radius=8,
                    color=ft.Colors.with_opacity(0.04, ft.Colors.BLACK),
                    offset=ft.Offset(0, 2),
                ),
                content=ft.Column(
                    spacing=12,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.START,
                            wrap=True,
                            run_spacing=6,
                            controls=[
                                ft.Row(
                                    spacing=8,
                                    wrap=True,
                                    controls=[
                                        pill_badge(c_cat, icon=ft.Icons.FOLDER_OPEN_ROUNDED),
                                        ft.Row(
                                            spacing=3,
                                            tight=True,
                                            controls=[
                                                ft.Icon(ft.Icons.STAR_ROUNDED, size=13, color=ft.Colors.AMBER_400),
                                                ft.Text(f"{c_rating}", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                                            ],
                                        ),
                                    ],
                                ),
                                status_tag,
                            ],
                        ),
                        ft.Row(
                            spacing=14,
                            vertical_alignment=ft.CrossAxisAlignment.START,
                            controls=[
                                thumb_widget,
                                ft.Column(
                                    expand=True,
                                    spacing=4,
                                    controls=[
                                        ft.Text(
                                            c_name,
                                            size=15 if is_mobile else 16,
                                            weight=ft.FontWeight.W_700,
                                            color=ft.Colors.ON_SURFACE,
                                            max_lines=2,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                        ),
                                        ft.Text(
                                            c_desc,
                                            size=12,
                                            color=ft.Colors.ON_SURFACE_VARIANT,
                                            max_lines=2,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                        ),
                                        ft.Row(
                                            spacing=4,
                                            tight=True,
                                            controls=[
                                                ft.Icon(ft.Icons.PERSON_OUTLINED, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                                ft.Text(author_name, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                            ],
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        *( [progress_strip] if progress_strip else [] ),
                        ft.Divider(height=1, color=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
                        card_footer,
                    ],
                ),
            )

            return ft.Container(
                margin=ft.Margin.only(bottom=16),
                content=ft.Row(
                    vertical_alignment=ft.CrossAxisAlignment.START,
                    spacing=14,
                    controls=[
                        stepper_column,
                        card_container,
                    ],
                ),
            )

        course_roadmap_cards = [
            render_course_sequence_card(idx, c, idx == total_courses - 1)
            for idx, c in enumerate(playlist_courses)
        ]

        if not course_roadmap_cards:
            course_roadmap_cards = [
                ft.Container(
                    padding=ft.Padding.all(40),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=12,
                        controls=[
                            ft.Icon(ft.Icons.FOLDER_OPEN_ROUNDED, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text("This learning path has no courses yet.", size=15, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.ElevatedButton("Explore Catalog", on_click=lambda _: page.go("/courses")),
                        ],
                    ),
                )
            ]

        roadmap_section = ft.Column(
            spacing=16,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Row(
                            spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Icon(ft.Icons.MAP_ROUNDED, color=UI_ACCENT, size=22),
                                ft.Text("Curriculum Pathway", size=18, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                            ],
                        ),
                        ft.Text(f"{total_courses} Sequential Steps", size=12, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500),
                    ],
                ),
                ft.Text(
                    "Follow this curated roadmap from foundational principles to advanced practical mastery.",
                    size=13,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
                ft.Column(controls=course_roadmap_cards, spacing=0),
            ],
        )

        # ── 3. Right Sidebar: Sticky Action & Pathway Cards ───────────────────
        # Primary Action CTA Card
        if all_completed:
            cta_badge = pill_badge("Path Complete! 🎓", icon=ft.Icons.VERIFIED_ROUNDED,
                                   bg=ft.Colors.with_opacity(0.12, ft.Colors.GREEN_600), fg=ft.Colors.GREEN_700)
            cta_title = "Congratulations! You Finished This Path"
            cta_sub = "You've successfully completed every course in this curriculum."
            cta_btn = ft.ElevatedButton(
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    tight=True,
                    spacing=8,
                    controls=[
                        ft.Icon(ft.Icons.REPLAY_ROUNDED, size=18, color=ft.Colors.ON_PRIMARY),
                        ft.Text("Review First Course", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_PRIMARY),
                    ],
                ),
                bgcolor=ft.Colors.GREEN_700,
                height=46,
                expand=True,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=2),
                on_click=handle_resume_learning,
            )
        elif all_enrolled:
            cta_badge = pill_badge("Active Pathway", icon=ft.Icons.CHECK_CIRCLE_ROUNDED,
                                   bg=ft.Colors.with_opacity(0.12, UI_ACCENT), fg=UI_ACCENT)
            cta_title = "Continue Your Learning Journey"
            cta_sub = f"You are enrolled in all {total_courses} courses. Jump back into your curriculum."
            cta_btn = ft.ElevatedButton(
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    tight=True,
                    spacing=8,
                    controls=[
                        ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, size=18, color=ft.Colors.ON_PRIMARY),
                        ft.Text("Resume Learning Path", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_PRIMARY),
                    ],
                ),
                bgcolor=UI_ACCENT,
                height=46,
                expand=True,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=2),
                on_click=handle_resume_learning,
            )
        else:
            cta_badge = pill_badge("Accelerated Curriculum", icon=ft.Icons.AUTO_AWESOME_ROUNDED,
                                   bg=ft.Colors.with_opacity(0.1, UI_ACCENT), fg=UI_ACCENT)
            cta_title = "Enroll in Full Learning Path"
            cta_sub = f"Unlock and track all {total_courses} courses in one click with continuous progress synchronization."
            cta_btn = ft.ElevatedButton(
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    tight=True,
                    spacing=8,
                    controls=[
                        ft.Icon(ft.Icons.BOLT_ROUNDED, size=18, color=ft.Colors.ON_PRIMARY),
                        ft.Text("Enroll in Full Learning Path", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_PRIMARY),
                    ],
                ),
                bgcolor=UI_ACCENT,
                height=48,
                expand=True,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=3),
                on_click=handle_path_enroll,
            )

        progress_summary_box = ft.Container(
            padding=ft.Padding.all(14),
            border_radius=ft.BorderRadius.all(12),
            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
            content=ft.Column(
                spacing=8,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text("Overall Path Completion", size=12, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                            ft.Text(f"{int(avg_path_progress)}%", size=13, weight=ft.FontWeight.BOLD, color=UI_ACCENT),
                        ],
                    ),
                    ft.ProgressBar(
                        value=path_progress_fraction,
                        color=ft.Colors.GREEN_600 if all_completed else UI_ACCENT,
                        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE),
                        height=6,
                        border_radius=ft.BorderRadius.all(3),
                    ),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text(f"{enrolled_count} of {total_courses} Enrolled", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(f"{completed_count} Completed", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                        ],
                    ),
                ],
            ),
        )

        enrollment_sidebar_card = ft.Container(
            bgcolor=ft.Colors.SURFACE,
            border_radius=ft.BorderRadius.all(18),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
            padding=ft.Padding.all(20),
            shadow=ft.BoxShadow(
                blur_radius=12,
                color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK),
                offset=ft.Offset(0, 3),
            ),
            content=ft.Column(
                spacing=16,
                controls=[
                    cta_badge,
                    ft.Text(cta_title, size=18, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                    ft.Text(cta_sub, size=13, color=ft.Colors.ON_SURFACE_VARIANT),
                    progress_summary_box,
                    ft.Row([cta_btn]),
                ],
            ),
        )

        right_sidebar = ft.Column(
            spacing=18,
            controls=[
                enrollment_sidebar_card,
            ],
        )

        # ── Two-Column Layout Assembly ────────────────────────────────────────
        body_grid = ft.ResponsiveRow(
            columns=12,
            spacing=24,
            run_spacing=24,
            controls=[
                ft.Container(content=roadmap_section, col={"xs": 12, "lg": 8}),
                ft.Container(content=right_sidebar, col={"xs": 12, "lg": 4}),
            ],
        )

        return ft.Column(
            scroll=ft.ScrollMode.AUTO,
            spacing=0,
            expand=True,
            controls=[
                hero_card,
                body_grid,
                ft.Container(height=40),  # Bottom padding
            ],
        )

    # Content Socket
    content = ft.Container(
        ref=content_socket,
        expand=True,
        padding=ft.Padding.symmetric(
            horizontal=16 if (getattr(page, "width", None) or 1080) < 650 else 24,
            vertical=16,
        ),
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
            controls=[
                ft.ProgressRing(color=UI_ACCENT, width=36, height=36, stroke_width=3),
                ft.Text("Loading Learning Path…", size=13, color=ft.Colors.ON_SURFACE_VARIANT),
            ],
        ),
    )

    # Initial async load task
    asyncio.create_task(refresh_view())

    return ft.View(
        route=f"/playlists/{playlist_id}",
        appbar=app_bar,
        padding=0,
        controls=[ft.SafeArea(expand=True, content=content)],
    )