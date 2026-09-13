import asyncio
import urllib.parse
import flet as ft
from src.requests.Courses import get_courses, get_course_curriculum
from src.requests.enrollments import get_enrollments, enrol_user


# ─────────────────────────────────────────────────────────────────────────────
# VIEW: Modern Sleek Course Details View
# ─────────────────────────────────────────────────────────────────────────────
async def course_details_view(page: ft.Page, course_id: str, back_target: str = "/courses"):
    # ── content socket ────────────────────────────────────────────────────────
    content_socket = ft.Container(
        expand=True,
        padding=ft.Padding.only(top=32),
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
            controls=[
                ft.ProgressRing(color=ft.Colors.PRIMARY, width=36, height=36, stroke_width=3),
                ft.Text("Loading course details…", size=13, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500),
            ],
        ),
    )

    # ── share handler ─────────────────────────────────────────────────────────
    course_title_holder = {"name": "Course"}

    async def open_whatsapp_share(e):
        c_title = course_title_holder.get("name") or "this course"
        message = f"""Hey! Check out the course "{c_title}" on Nu-Age! 🚀

It comes with interactive modules, flashcards, quizzes, and an AI tutor!

Check it out 👉 : nu-age.com.ng"""
        encoded_message = urllib.parse.quote(message)
        await page.launch_url(f"https://wa.me/?text={encoded_message}")

    # ── app bar ───────────────────────────────────────────────────────────────
    app_bar = ft.AppBar(
        bgcolor=ft.Colors.SURFACE,
        title=ft.Text(
            "Course Overview",
            color=ft.Colors.ON_SURFACE,
            weight=ft.FontWeight.W_700,
            size=16,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        ),
        leading=ft.IconButton(
            icon=ft.Icons.ARROW_BACK_ROUNDED,
            icon_color=ft.Colors.ON_SURFACE,
            tooltip="Back",
            on_click=lambda _: page.go(back_target),
        ),
        actions=[
            ft.IconButton(
                icon=ft.Icons.SHARE_OUTLINED,
                icon_color=ft.Colors.ON_SURFACE,
                tooltip="Share Course via WhatsApp",
                on_click=open_whatsapp_share,
            ),
            ft.Container(width=8),
        ],
        elevation=0,
    )

    # ── enrol handler ─────────────────────────────────────────────────────────
    async def handle_enrol_click(e):
        if e.control.disabled:
            return

        token = await page.shared_preferences.get("auth_token")
        e.control.disabled = True
        orig_content = e.control.content
        e.control.content = ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            tight=True,
            spacing=8,
            controls=[
                ft.ProgressRing(width=16, height=16, color=ft.Colors.ON_PRIMARY, stroke_width=2),
                ft.Text("Enrolling…", color=ft.Colors.ON_PRIMARY, size=13, weight=ft.FontWeight.W_600),
            ],
        )
        page.update()

        try:
            status, data = await asyncio.wait_for(
                enrol_user(token, course_id, None), timeout=15
            )
            if status == 200:
                page.go(f"/courses/{course_id}/view")
            else:
                e.control.disabled = False
                e.control.content = orig_content
                page.update()
                page.show_dialog(
                    ft.SnackBar(
                        content=ft.Text("Failed to enroll. Please try again.", color=ft.Colors.WHITE),
                        bgcolor=ft.Colors.ERROR,
                    )
                )

        except asyncio.TimeoutError:
            e.control.disabled = False
            e.control.content = ft.Text("Timed out — tap to retry", color=ft.Colors.ON_PRIMARY, size=13)
            page.update()

        except Exception as ex:
            e.control.disabled = False
            e.control.content = ft.Text("Error — tap to retry", color=ft.Colors.ON_PRIMARY, size=13)
            page.update()

    # ─────────────────────────────────────────────────────────────────────────
    # DATA LOADER
    # ─────────────────────────────────────────────────────────────────────────
    async def load_course_info(cid: str):
        token = await page.shared_preferences.get("auth_token")

        try:
            course_list, enrolled_list, curriculum_res = await asyncio.gather(
                asyncio.wait_for(get_courses(token, params={"id": cid}), timeout=15),
                asyncio.wait_for(get_enrollments(token, None), timeout=15),
                asyncio.wait_for(get_course_curriculum(token, cid), timeout=15),
                return_exceptions=True,
            )

            if isinstance(course_list, Exception) or not course_list:
                _show_error("Course not found or failed to load.")
                return

            if isinstance(enrolled_list, Exception):
                enrolled_list = []

            course_data = course_list[0]
            name = course_data.get("name", "Untitled Course")
            course_title_holder["name"] = name
            image_url = course_data.get("image_url")
            description = course_data.get("description", "No description provided.")
            objectives = course_data.get("objectives", [])
            category = (course_data.get("category") or {}).get("name", "General")
            admin = course_data.get("admin") or {}
            first_name = admin.get("first_name", "")
            last_name = admin.get("last_name", "")
            author = f"{first_name} {last_name}".strip() or "Course Instructor"
            students_list = course_data.get("Students", [])
            enrolled_count = len(students_list) if isinstance(students_list, list) else 0
            is_public_val = str(course_data.get("public", "false")).lower()
            is_supervised = course_data.get("supervised", False)
            rating = round(float(course_data.get("rating") or 4.8), 1)
            org_name = (course_data.get("organisation") or {}).get("name", "Independent")

            enrolled_ids = [str(c.get("id")) for c in (enrolled_list or [])]
            is_already_enrolled = str(cid) in enrolled_ids

            # Eagerly load curriculum modules with their nested lessons
            modules = []
            if isinstance(curriculum_res, dict) and "modules" in curriculum_res and isinstance(curriculum_res["modules"], list):
                modules = curriculum_res["modules"]
            elif isinstance(course_data.get("modules"), list):
                modules = course_data.get("modules")

            # Calculate syllabus statistics
            total_modules = len(modules)
            total_lessons = sum(len(m.get("lessons", [])) for m in modules) if modules else 0
            est_hours = round(total_lessons * 0.5, 1) if total_lessons > 0 else (round(total_modules * 1.5, 1) if total_modules > 0 else 2.0)

            # Update AppBar title
            app_bar.title = ft.Text(
                name,
                color=ft.Colors.ON_SURFACE,
                weight=ft.FontWeight.W_700,
                size=16,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            )

            # ── Helpers ───────────────────────────────────────────────────────
            def pill_badge(text: str, icon=None, bg=None, fg=None):
                controls = []
                if icon:
                    controls.append(ft.Icon(icon, size=12, color=fg or ft.Colors.PRIMARY))
                controls.append(ft.Text(text, size=11, color=fg or ft.Colors.PRIMARY, weight=ft.FontWeight.W_600))
                return ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                    border_radius=ft.BorderRadius.all(8),
                    bgcolor=bg or ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                    content=ft.Row(controls, tight=True, spacing=5),
                )

            def meta_stat_item(icon, label, value):
                return ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                    border_radius=ft.BorderRadius.all(10),
                    bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
                    content=ft.Row(
                        spacing=8,
                        tight=True,
                        controls=[
                            ft.Icon(icon, size=16, color=ft.Colors.PRIMARY),
                            ft.Column(
                                spacing=1,
                                tight=True,
                                controls=[
                                    ft.Text(label, size=10, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500),
                                    ft.Text(value, size=12, color=ft.Colors.ON_SURFACE, weight=ft.FontWeight.BOLD),
                                ],
                            ),
                        ],
                    ),
                )

            def lesson_type_icon(ltype: str):
                icons = {
                    "video": (ft.Icons.PLAY_CIRCLE_OUTLINE_ROUNDED, ft.Colors.BLUE_600),
                    "text": (ft.Icons.MY_LIBRARY_BOOKS_OUTLINED, ft.Colors.GREEN_600),
                    "cards": (ft.Icons.STYLE_ROUNDED, ft.Colors.PURPLE_600),
                    "assessment": (ft.Icons.QUIZ_ROUNDED, ft.Colors.AMBER_600),
                    "document": (ft.Icons.PICTURE_AS_PDF_ROUNDED, ft.Colors.RED_600),
                    "audio": (ft.Icons.HEADPHONES_ROUNDED, ft.Colors.TEAL_600),
                }
                return icons.get(ltype.lower(), (ft.Icons.ARTICLE_ROUNDED, ft.Colors.PRIMARY))

            # ── 1. Hero Canvas ────────────────────────────────────────────────
            badges_row = ft.Row(
                wrap=True,
                spacing=8,
                run_spacing=6,
                controls=[
                    pill_badge(category, icon=ft.Icons.CATEGORY_ROUNDED,
                               bg=ft.Colors.with_opacity(0.1, ft.Colors.PRIMARY), fg=ft.Colors.PRIMARY),
                    pill_badge("Instructor-Led" if is_supervised else "Self-Paced",
                               icon=ft.Icons.SCHOOL_ROUNDED if is_supervised else ft.Icons.AUTO_STORIES_ROUNDED,
                               bg=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE), fg=ft.Colors.ON_SURFACE),
                    pill_badge("Organisation" if is_public_val == "organisation" else "Public",
                               icon=ft.Icons.BUSINESS_ROUNDED if is_public_val == "organisation" else ft.Icons.PUBLIC_ROUNDED,
                               bg=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE), fg=ft.Colors.ON_SURFACE),
                ],
            )

            # Rating stars
            full_stars = int(rating)
            star_icons = [
                ft.Icon(ft.Icons.STAR_ROUNDED, color=ft.Colors.AMBER_400, size=16)
                for _ in range(min(5, full_stars))
            ]

            hero_stats_strip = ft.Row(
                wrap=True,
                spacing=8,
                run_spacing=8,
                controls=[
                    meta_stat_item(ft.Icons.STAR_ROUNDED, "Rating", f"{rating} ★"),
                    meta_stat_item(ft.Icons.PEOPLE_ALT_OUTLINED, "Learners", f"{enrolled_count} Enrolled"),
                    meta_stat_item(ft.Icons.TIMELAPSE_ROUNDED, "Duration", f"~{est_hours} Hours"),
                    meta_stat_item(ft.Icons.LAYERS_OUTLINED, "Curriculum", f"{total_modules} M • {total_lessons} L"),
                    meta_stat_item(ft.Icons.WORKSPACE_PREMIUM_OUTLINED, "Certificate", "Included"),
                ],
            )

            hero_left = ft.Column(
                spacing=16,
                controls=[
                    badges_row,
                    ft.Text(
                        name,
                        size=28,
                        weight=ft.FontWeight.W_800,
                        color=ft.Colors.ON_SURFACE,
                    ),
                    ft.Text(
                        description,
                        size=14,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        max_lines=3,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    hero_stats_strip,
                ],
            )

            # Hero Image / Thumbnail Frame
            hero_image_content = ft.Container(
                border_radius=ft.BorderRadius.all(16),
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                shadow=ft.BoxShadow(
                    blur_radius=16,
                    color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
                    offset=ft.Offset(0, 4),
                ),
                content=ft.Stack(
                    controls=[
                        ft.Image(
                            src=image_url if image_url else "assets/placeholder.png",
                            fit=ft.BoxFit.COVER,
                            width=float("inf"),
                            height=220,
                        ),
                        # Enrolled Banner Overlay
                        ft.Container(
                            top=12,
                            right=12,
                            visible=is_already_enrolled,
                            padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                            border_radius=ft.BorderRadius.all(20),
                            bgcolor=ft.Colors.PRIMARY,
                            content=ft.Row(
                                tight=True,
                                spacing=4,
                                controls=[
                                    ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.ON_PRIMARY, size=13),
                                    ft.Text("Enrolled", color=ft.Colors.ON_PRIMARY, size=11, weight=ft.FontWeight.BOLD),
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
                padding=ft.Padding.all(24),
                margin=ft.Margin.only(bottom=24),
                content=ft.ResponsiveRow(
                    columns=12,
                    spacing=24,
                    run_spacing=24,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(content=hero_left, col={"xs": 12, "md": 7}),
                        ft.Container(content=hero_image_content, col={"xs": 12, "md": 5}),
                    ],
                ),
            )

            # ── 2. What You'll Learn ──────────────────────────────────────────
            def objective_chip(obj_text: str):
                return ft.Container(
                    col={"xs": 12, "sm": 6},
                    padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                    border_radius=ft.BorderRadius.all(10),
                    bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)),
                    content=ft.Row(
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                        controls=[
                            ft.Container(
                                width=20,
                                height=20,
                                border_radius=ft.BorderRadius.all(10),
                                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.CHECK_ROUNDED, size=13, color=ft.Colors.PRIMARY),
                            ),
                            ft.Text(obj_text, size=13, color=ft.Colors.ON_SURFACE, expand=True, weight=ft.FontWeight.W_500),
                        ],
                    ),
                )

            effective_objectives = objectives if objectives else [f"Master key principles and practical concepts in {name}"]
            objectives_grid = ft.ResponsiveRow(
                columns=12,
                spacing=10,
                run_spacing=10,
                controls=[objective_chip(obj) for obj in effective_objectives],
            )

            what_you_learn_card = ft.Container(
                bgcolor=ft.Colors.SURFACE,
                border_radius=ft.BorderRadius.all(16),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                padding=ft.Padding.all(20),
                content=ft.Column(
                    spacing=16,
                    controls=[
                        ft.Row(
                            spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, color=ft.Colors.PRIMARY, size=20),
                                ft.Text("What You'll Learn", size=17, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                            ],
                        ),
                        objectives_grid,
                    ],
                ),
            )

            # ── 3. Interactive Curriculum Accordions ──────────────────────────
            module_accordion_items = []
            if modules:
                for idx, mod in enumerate(modules, 1):
                    mod_title = mod.get("title", f"Module {idx}")
                    mod_lessons = mod.get("lessons", [])
                    num_lessons = len(mod_lessons)

                    lessons_list_col = ft.Column(spacing=6)
                    for l_idx, lesson in enumerate(mod_lessons, 1):
                        l_title = lesson.get("title", f"Lesson {l_idx}")
                        l_type = lesson.get("type") or lesson.get("lesson_type") or "text"
                        l_icon, l_color = lesson_type_icon(l_type)
                        l_completed = lesson.get("is_completed", False)

                        badge_controls = []
                        if l_completed:
                            badge_controls.append(
                                ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=15, color=ft.Colors.GREEN_600)
                            )
                        badge_controls.append(
                            ft.Container(
                                padding=ft.Padding.symmetric(horizontal=8, vertical=2),
                                border_radius=ft.BorderRadius.all(6),
                                bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                                content=ft.Text(l_type.upper(), size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                            )
                        )

                        def make_lesson_click(enrolled):
                            def on_click(_):
                                if enrolled:
                                    page.go(f"/courses/{course_id}/view")
                                else:
                                    page.show_dialog(
                                        ft.SnackBar(
                                            content=ft.Text("Enroll in this course to start learning!"),
                                            bgcolor=ft.Colors.PRIMARY,
                                            duration=ft.Duration(milliseconds=2000),
                                        )
                                    )
                            return on_click

                        lesson_row = ft.Container(
                            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                            border_radius=ft.BorderRadius.all(8),
                            bgcolor=ft.Colors.with_opacity(0.025, ft.Colors.ON_SURFACE),
                            ink=True,
                            on_click=make_lesson_click(is_already_enrolled),
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Row(
                                        spacing=10,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                        expand=True,
                                        controls=[
                                            ft.Icon(l_icon, size=16, color=l_color),
                                            ft.Text(f"{l_idx}. {l_title}", size=13, color=ft.Colors.ON_SURFACE, expand=True),
                                        ],
                                    ),
                                    ft.Row(
                                        spacing=6,
                                        tight=True,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                        controls=badge_controls,
                                    ),
                                ],
                            ),
                        )
                        lessons_list_col.controls.append(lesson_row)

                    if not mod_lessons:
                        lessons_list_col.controls.append(
                            ft.Container(
                                padding=ft.Padding.all(12),
                                alignment=ft.Alignment.CENTER_LEFT,
                                content=ft.Text("No lessons listed in this module yet.", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                            )
                        )

                    lessons_container = ft.Container(
                        content=lessons_list_col,
                        visible=(idx == 1),  # Expand first module by default
                        padding=ft.Padding.only(top=10, bottom=4, left=4, right=4),
                    )

                    chevron_icon = ft.Icon(
                        ft.Icons.KEYBOARD_ARROW_UP_ROUNDED if idx == 1 else ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED,
                        size=20,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    )

                    def make_toggle(container_ctrl, chevron_ctrl):
                        def toggle_module(e):
                            container_ctrl.visible = not container_ctrl.visible
                            chevron_ctrl.icon = (
                                ft.Icons.KEYBOARD_ARROW_UP_ROUNDED
                                if container_ctrl.visible
                                else ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED
                            )
                            page.update()
                        return toggle_module

                    header_btn = ft.Container(
                        ink=True,
                        border_radius=ft.BorderRadius.all(10),
                        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                        on_click=make_toggle(lessons_container, chevron_icon),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Row(
                                    spacing=12,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    expand=True,
                                    controls=[
                                        ft.Container(
                                            width=28,
                                            height=28,
                                            alignment=ft.Alignment.CENTER,
                                            border_radius=ft.BorderRadius.all(6),
                                            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
                                            content=ft.Text(f"{idx:02d}", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                                        ),
                                        ft.Column(
                                            spacing=2,
                                            tight=True,
                                            expand=True,
                                            controls=[
                                                ft.Text(mod_title, size=14, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                                                ft.Text(f"{num_lessons} lesson{'s' if num_lessons != 1 else ''}", size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                            ],
                                        ),
                                    ],
                                ),
                                chevron_icon,
                            ],
                        ),
                    )

                    module_card = ft.Container(
                        border_radius=ft.BorderRadius.all(12),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                        bgcolor=ft.Colors.SURFACE,
                        padding=ft.Padding.all(6),
                        content=ft.Column(
                            spacing=0,
                            controls=[header_btn, lessons_container],
                        ),
                    )
                    module_accordion_items.append(module_card)
            else:
                module_accordion_items.append(
                    ft.Container(
                        padding=ft.Padding.all(24),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Text("No curriculum modules available yet.", color=ft.Colors.ON_SURFACE_VARIANT, size=13),
                    )
                )

            curriculum_section = ft.Container(
                bgcolor=ft.Colors.SURFACE,
                border_radius=ft.BorderRadius.all(16),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                padding=ft.Padding.all(20),
                content=ft.Column(
                    spacing=16,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Row(
                                    spacing=10,
                                    controls=[
                                        ft.Icon(ft.Icons.PLAYLIST_PLAY_ROUNDED, color=ft.Colors.PRIMARY, size=22),
                                        ft.Text("Course Syllabus", size=17, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                                    ],
                                ),
                                ft.Text(
                                    f"{total_modules} Modules • {total_lessons} Lessons",
                                    size=12,
                                    weight=ft.FontWeight.W_600,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                            ],
                        ),
                        ft.Column(spacing=8, controls=module_accordion_items),
                    ],
                ),
            )

            # ── 4. Detailed Description & Instructor ──────────────────────────
            about_card = ft.Container(
                bgcolor=ft.Colors.SURFACE,
                border_radius=ft.BorderRadius.all(16),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                padding=ft.Padding.all(20),
                content=ft.Column(
                    spacing=12,
                    controls=[
                        ft.Row(
                            spacing=10,
                            controls=[
                                ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, color=ft.Colors.PRIMARY, size=20),
                                ft.Text("Course Overview", size=17, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                            ],
                        ),
                        ft.Text(
                            description,
                            size=14,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                            selectable=True,
                        ),
                    ],
                ),
            )

            # Instructor Card
            instructor_initials = "".join([part[0].upper() for part in author.split() if part])[:2] or "IN"
            instructor_card = ft.Container(
                bgcolor=ft.Colors.SURFACE,
                border_radius=ft.BorderRadius.all(16),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                padding=ft.Padding.all(20),
                content=ft.Column(
                    spacing=14,
                    controls=[
                        ft.Text("Instructor & Organisation", size=15, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                        ft.Row(
                            spacing=14,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Container(
                                    width=48,
                                    height=48,
                                    border_radius=ft.BorderRadius.all(24),
                                    bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                                    alignment=ft.Alignment.CENTER,
                                    content=ft.Text(instructor_initials, size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                                ),
                                ft.Column(
                                    spacing=2,
                                    tight=True,
                                    expand=True,
                                    controls=[
                                        ft.Text(author, size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                                        ft.Text(f"Verified Instructor • {org_name}", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
            )

            left_column_content = ft.Column(
                spacing=20,
                controls=[
                    what_you_learn_card,
                    curriculum_section,
                    about_card,
                    instructor_card,
                ],
            )

            # ── 5. Sticky Enrollment Card (Sidebar on desktop) ────────────────
            enrol_action_btn = ft.ElevatedButton(
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    tight=True,
                    spacing=8,
                    controls=[
                        ft.Icon(
                            ft.Icons.PLAY_ARROW_ROUNDED if is_already_enrolled else ft.Icons.ROCKET_LAUNCH_ROUNDED,
                            size=18,
                            color=ft.Colors.ON_PRIMARY,
                        ),
                        ft.Text(
                            "Continue Learning" if is_already_enrolled else "Enroll in Course",
                            size=15,
                            weight=ft.FontWeight.W_700,
                            color=ft.Colors.ON_PRIMARY,
                        ),
                    ],
                ),
                bgcolor=ft.Colors.PRIMARY,
                height=50,
                style=ft.ButtonStyle(
                    shape=ft.RoundedRectangleBorder(radius=12),
                    elevation=2,
                ),
                on_click=(
                    (lambda _: page.go(f"/courses/{course_id}/view"))
                    if is_already_enrolled
                    else handle_enrol_click
                ),
            )

            enrollment_status_banner = ft.Container(
                padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                border_radius=ft.BorderRadius.all(10),
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY if is_already_enrolled else ft.Colors.ON_SURFACE),
                content=ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(
                            ft.Icons.CHECK_CIRCLE_ROUNDED if is_already_enrolled else ft.Icons.LOCK_OPEN_ROUNDED,
                            size=16,
                            color=ft.Colors.PRIMARY if is_already_enrolled else ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Text(
                            "You are currently enrolled" if is_already_enrolled else "Free & Open Enrollment",
                            size=12,
                            weight=ft.FontWeight.W_600,
                            color=ft.Colors.PRIMARY if is_already_enrolled else ft.Colors.ON_SURFACE,
                        ),
                    ],
                ),
            )

            def check_perk(text: str):
                return ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.CHECK_ROUNDED, size=15, color=ft.Colors.PRIMARY),
                        ft.Text(text, size=12, color=ft.Colors.ON_SURFACE),
                    ],
                )

            sidebar_enrol_card = ft.Container(
                bgcolor=ft.Colors.SURFACE,
                border_radius=ft.BorderRadius.all(18),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                shadow=ft.BoxShadow(
                    blur_radius=16,
                    color=ft.Colors.with_opacity(0.06, ft.Colors.BLACK),
                    offset=ft.Offset(0, 4),
                ),
                padding=ft.Padding.all(22),
                content=ft.Column(
                    spacing=16,
                    controls=[
                        enrollment_status_banner,
                        enrol_action_btn,
                        ft.OutlinedButton(
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.CENTER,
                                tight=True,
                                spacing=8,
                                controls=[
                                    ft.Icon(ft.Icons.SHARE_ROUNDED, size=16, color=ft.Colors.PRIMARY),
                                    ft.Text("Share on WhatsApp", size=13, weight=ft.FontWeight.W_600, color=ft.Colors.PRIMARY),
                                ],
                            ),
                            height=44,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=12),
                                side=ft.BorderSide(1, ft.Colors.with_opacity(0.18, ft.Colors.PRIMARY)),
                            ),
                            on_click=open_whatsapp_share,
                        ),
                        ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                        ft.Text("This course includes:", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                        check_perk(f"{total_modules} Interactive study modules"),
                        check_perk(f"{total_lessons} Bite-sized learning lessons"),
                        check_perk("Practice flashcards & exam simulators"),
                        check_perk("Full access on mobile & desktop"),
                        check_perk("Official completion certificate"),
                        ft.Divider(height=1, color=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                        # Organisation Info
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.Icon(ft.Icons.BUSINESS_ROUNDED, size=15, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(f"Offered by {org_name}", size=12, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500),
                            ],
                        ),
                    ],
                ),
            )

            # ── 6. Assemble Responsive Grid ───────────────────────────────────
            responsive_grid = ft.ResponsiveRow(
                columns=12,
                spacing=24,
                run_spacing=24,
                controls=[
                    ft.Container(content=left_column_content, col={"xs": 12, "md": 7, "lg": 8}),
                    ft.Container(content=sidebar_enrol_card, col={"xs": 12, "md": 5, "lg": 4}),
                ],
            )

            main_container = ft.Container(
                padding=ft.Padding.symmetric(horizontal=20, vertical=16),
                alignment=ft.Alignment.TOP_CENTER,
                content=ft.Column(
                    spacing=0,
                    controls=[
                        hero_card,
                        responsive_grid,
                        ft.Container(height=32),
                    ],
                ),
            )

            content_socket.alignment = None
            content_socket.padding = 0
            content_socket.content = main_container
            page.update()

        except asyncio.TimeoutError:
            _show_error(
                "Connection timed out.",
                icon=ft.Icons.WIFI_OFF_ROUNDED,
                color=ft.Colors.ORANGE_400,
            )

        except Exception as ex:
            _show_error(
                f"Something went wrong ({type(ex).__name__}).",
                icon=ft.Icons.ERROR_OUTLINE_ROUNDED,
                color=ft.Colors.RED_400,
            )

    # ── error helper ──────────────────────────────────────────────────────────
    def _show_error(message: str, icon=ft.Icons.ERROR_OUTLINE_ROUNDED, color=ft.Colors.RED_400):
        content_socket.alignment = ft.Alignment.CENTER
        content_socket.content = ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
            controls=[
                ft.Icon(icon, size=48, color=color),
                ft.Text("Couldn't load course", size=16, weight=ft.FontWeight.W_600, color=ft.Colors.ON_SURFACE),
                ft.Text(message, size=13, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER),
                ft.Container(height=4),
                ft.ElevatedButton(
                    "Retry",
                    bgcolor=ft.Colors.PRIMARY,
                    color=ft.Colors.ON_PRIMARY,
                    height=42,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=10),
                        elevation=0,
                    ),
                    on_click=lambda _: page.run_task(load_course_info, course_id),
                ),
            ],
        )
        page.update()

    # ── trigger ───────────────────────────────────────────────────────────────
    page.run_task(load_course_info, course_id)

    # ── view ──────────────────────────────────────────────────────────────────
    view = ft.View(
        route=f"/courses/{course_id}",
        padding=0,
        bgcolor=ft.Colors.SURFACE,
        appbar=app_bar,
        scroll=ft.ScrollMode.AUTO,
        controls=[content_socket],
    )
    return view