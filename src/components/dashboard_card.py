import flet as ft


def get_continue_learning_card(
    course_name: str,
    progress: float,
    course_id: str | int,
    page: ft.Page,
    category: str | None = None,
    description: str | None = None,
    author: str | None = None,
    image_url: str | None = None,
    course_dict: dict | None = None,
):
    """
    LMS Course Card mirroring modern Dribbble/E-Studieses UI layout:
    - Top row: Course image/logo (with fallback tech/category icon) + Status pill (Ongoing / Done / Paused)
    - Middle: Bold course title + track subtitle + 2-line description summary
    - Progress: Thin progress track with circular indicator bead at the tip
    - Footer: Instructor mini avatar + name on left, and 'Continue' action on right
    - Interactive: Smooth hover lift, shadow, and click routing
    """
    c_dict = course_dict or {}

    # ── Resolve Course Data & Fallbacks ───────────────────────────────────────
    c_name = course_name or c_dict.get("name") or c_dict.get("title") or "Untitled Course"
    c_prog = float(progress if progress is not None else c_dict.get("progress", 0.0))
    c_id = course_id or c_dict.get("id")

    # Category / Track
    cat_obj = category or c_dict.get("category")
    if isinstance(cat_obj, dict):
        cat_name = cat_obj.get("name") or "General Track"
    elif isinstance(cat_obj, str) and cat_obj.strip():
        cat_name = cat_obj.strip()
    else:
        cat_name = "Course Track"

    # Description
    desc = description or c_dict.get("description") or c_dict.get("summary")
    if not desc:
        objs = c_dict.get("objectives")
        if isinstance(objs, list) and objs:
            desc = objs[0]
    if not desc or not isinstance(desc, str) or not desc.strip():
        desc = "Master core concepts and advance your skills with guided interactive modules."
    else:
        desc = desc.strip()

    # Instructor / Author (CourseOut returns admin: UserMin)
    auth_obj = (
        author
        or c_dict.get("admin")
        or c_dict.get("author")
        or c_dict.get("instructor")
        or c_dict.get("created_by")
        or c_dict.get("user")
    )
    if isinstance(auth_obj, dict):
        auth_name = (
            auth_obj.get("name")
            or f"{auth_obj.get('first_name', '')} {auth_obj.get('last_name', '')}".strip()
            or "Nu-age Instructor"
        )
    elif isinstance(auth_obj, str) and auth_obj.strip():
        auth_name = auth_obj.strip()
    else:
        auth_name = "Nu-age Instructor"

    # Image / Logo (prioritize actual course image returned from API)
    img_src = (
        image_url
        or c_dict.get("image_url")
        or c_dict.get("thumbnail_url")
        or c_dict.get("cover_image")
        or c_dict.get("course_image")
        or c_dict.get("image")
        or c_dict.get("thumbnail")
    )

    # ── Determine Status & Theme Palette ──────────────────────────────────────
    pct = max(0.0, min(c_prog, 100.0))
    if pct >= 100:
        status_label = "Done"
        status_color = ft.Colors.TEAL_400
        status_bg = ft.Colors.with_opacity(0.12, ft.Colors.TEAL_400)
        action_label = "Review"
    elif pct > 0:
        status_label = "Ongoing"
        status_color = ft.Colors.PRIMARY
        status_bg = ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY)
        action_label = "Continue"
    else:
        status_label = "Paused"
        status_color = ft.Colors.ORANGE_400
        status_bg = ft.Colors.with_opacity(0.12, ft.Colors.ORANGE_400)
        action_label = "Start"

    # Category icon helper for fallback
    name_lower = f"{c_name} {cat_name}".lower()
    if any(k in name_lower for k in ["web", "front", "react", "angular", "vue", "html", "css", "js", "code"]):
        fallback_icon = ft.Icons.CODE_ROUNDED
        icon_accent = ft.Colors.BLUE_400
    elif any(k in name_lower for k in ["back", "node", "python", "api", "database", "sql", "server", "django"]):
        fallback_icon = ft.Icons.STORAGE_ROUNDED
        icon_accent = ft.Colors.TEAL_500
    elif any(k in name_lower for k in ["mobile", "flutter", "android", "ios", "app"]):
        fallback_icon = ft.Icons.SMARTPHONE_ROUNDED
        icon_accent = ft.Colors.PURPLE_400
    elif any(k in name_lower for k in ["design", "ui", "ux", "figma", "sketch"]):
        fallback_icon = ft.Icons.BRUSH_ROUNDED
        icon_accent = ft.Colors.ORANGE_400
    elif any(k in name_lower for k in ["ai", "machine", "data", "deep", "neural"]):
        fallback_icon = ft.Icons.AUTO_AWESOME_ROUNDED
        icon_accent = ft.Colors.INDIGO_400
    else:
        fallback_icon = ft.Icons.SCHOOL_ROUNDED
        icon_accent = ft.Colors.PRIMARY

    # ── Top Row: Image / Icon + Status Pill ───────────────────────────────────
    if img_src:
        icon_widget = ft.Image(
            src=img_src,
            fit=ft.BoxFit.COVER,
            width=38,
            height=38,
            border_radius=ft.BorderRadius.all(10),
            error_content=ft.Icon(fallback_icon, size=20, color=icon_accent),
        )
    else:
        icon_widget = ft.Icon(fallback_icon, size=20, color=icon_accent)

    icon_box = ft.Container(
        width=38,
        height=38,
        border_radius=ft.BorderRadius.all(10),
        bgcolor=ft.Colors.TRANSPARENT if img_src else ft.Colors.with_opacity(0.10, icon_accent),
        alignment=ft.Alignment.CENTER,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=icon_widget,
    )

    status_pill = ft.Container(
        padding=ft.Padding.symmetric(horizontal=8, vertical=3.5),
        border_radius=ft.BorderRadius.all(12),
        bgcolor=status_bg,
        content=ft.Text(
            status_label,
            size=10,
            weight=ft.FontWeight.W_700,
            color=status_color,
        ),
    )

    header_row = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[icon_box, status_pill],
    )

    # ── Middle Row: Title, Subtitle, Description ─────────────────────────────
    title_text = ft.Text(
        c_name,
        size=14,
        weight=ft.FontWeight.W_700,
        color=ft.Colors.ON_SURFACE,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )

    cat_text = ft.Text(
        cat_name,
        size=10.5,
        weight=ft.FontWeight.W_500,
        color=ft.Colors.GREY_500,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )

    desc_text = ft.Text(
        desc,
        size=10.5,
        color=ft.Colors.GREY_600,
        max_lines=2,
        overflow=ft.TextOverflow.ELLIPSIS,
    )

    # ── Progress Bar with Circular Tip Indicator ─────────────────────────────
    bar_width = 222
    filled_width = max(5.0, (pct / 100.0) * bar_width) if pct > 0 else 0.0

    track_bg = ft.Container(
        left=0,
        top=3,
        width=bar_width,
        height=4,
        border_radius=ft.BorderRadius.all(2),
        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE),
    )

    track_fill = ft.Container(
        left=0,
        top=3,
        width=filled_width,
        height=4,
        border_radius=ft.BorderRadius.all(2),
        bgcolor=status_color,
    )

    # Indicator bead positioned at the end of progress fill (full 10px circle, vertically centered over the 4px track)
    bead_size = 10
    bead_left = max(0.0, min(filled_width - (bead_size / 2.0), bar_width - bead_size))
    track_bead = ft.Container(
        left=bead_left,
        top=0,
        width=bead_size,
        height=bead_size,
        border_radius=ft.BorderRadius.all(bead_size // 2),
        bgcolor=status_color,
        border=ft.Border.all(1.5, ft.Colors.SURFACE),
        shadow=ft.BoxShadow(
            blur_radius=3,
            color=ft.Colors.with_opacity(0.25, ft.Colors.BLACK),
            offset=ft.Offset(0, 1),
        ),
    )

    progress_stack = ft.Stack(
        height=10,
        width=bar_width,
        clip_behavior=ft.ClipBehavior.NONE,
        controls=[track_bg, track_fill, track_bead],
    )

    # ── Footer Row: Instructor Avatar/Name + Action Link ──────────────────────
    initials = "".join(p[:1].upper() for p in auth_name.split()[:2]) or "NU"
    instructor_avatar = ft.CircleAvatar(
        radius=9,
        content=ft.Text(initials, size=7.5, weight=ft.FontWeight.W_800),
        bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.PRIMARY),
        color=ft.Colors.PRIMARY,
    )

    instructor_text = ft.Text(
        auth_name,
        size=10.5,
        weight=ft.FontWeight.W_500,
        color=ft.Colors.GREY_600,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
        expand=True,
    )

    action_btn = ft.Text(
        action_label,
        size=11,
        weight=ft.FontWeight.W_700,
        color=status_color,
    )

    footer_row = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=6,
        controls=[
            ft.Row(
                spacing=5,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
                controls=[instructor_avatar, instructor_text],
            ),
            action_btn,
        ],
    )

    # ── Card Container ───────────────────────────────────────────────────────
    card = ft.Container(
        width=250,
        height=205,
        bgcolor=ft.Colors.SURFACE,
        border_radius=ft.BorderRadius.all(14),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
        padding=ft.Padding.symmetric(horizontal=14, vertical=12),
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        scale=1.0,
        shadow=ft.BoxShadow(
            blur_radius=8,
            color=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
            offset=ft.Offset(0, 3),
        ),
        animate_scale=ft.Animation(duration=250, curve=ft.AnimationCurve.EASE_OUT),
        ink=True,
        on_click=lambda _: page.go(f"/courses/{c_id}/view"),
        content=ft.Column(
            spacing=7,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                header_row,
                ft.Column(
                    spacing=2,
                    controls=[
                        title_text,
                        cat_text,
                    ],
                ),
                desc_text,
                progress_stack,
                footer_row,
            ],
        ),
    )

    # ── Hover Animation ──────────────────────────────────────────────────────
    def _on_hover(e: ft.HoverEvent):
        is_h = e.data == "true"
        card.scale = 1.03 if is_h else 1.0
        card.shadow = ft.BoxShadow(
            blur_radius=16 if is_h else 8,
            color=ft.Colors.with_opacity(0.14 if is_h else 0.06, ft.Colors.ON_SURFACE),
            offset=ft.Offset(0, 6 if is_h else 3),
        )
        card.update()

    card.on_hover = _on_hover
    return card