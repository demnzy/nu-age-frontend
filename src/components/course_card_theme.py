import flet as ft


def get_course_module_meta(modules_data=None, seed_key=None, progress: float = 0.0):
    """
    Computes total modules, completed modules (based on progress),
    and estimated duration using an arbitrary formula (1.5 hrs / module).
    """
    if isinstance(modules_data, list) and len(modules_data) > 0:
        total_modules = len(modules_data)
    elif isinstance(modules_data, (int, float)) and modules_data > 0:
        total_modules = int(modules_data)
    else:
        # Deterministic fallback based on course name/id hash (4 to 8 modules)
        seed = str(seed_key or "course")
        total_modules = (abs(hash(seed)) % 5) + 4

    # Arbitrary formula: ~1.5 hours per module
    est_hours = round(total_modules * 1.5, 1)
    if est_hours.is_integer():
        time_str = f"{int(est_hours)} hrs"
    else:
        time_str = f"{est_hours} hrs"

    # Completed modules based on percentage
    pct = max(0.0, min(float(progress or 0.0), 100.0))
    completed_modules = int(round((pct / 100.0) * total_modules))
    if pct > 0 and completed_modules == 0:
        completed_modules = 1
    if pct >= 100:
        completed_modules = total_modules

    return total_modules, completed_modules, time_str


# 4 Distinct Modern Pastel Themes matching the reference design:
# 1. Pink / Rose (UI/UX Designer)
# 2. Sky Blue (QA Engineer)
# 3. Warm Yellow (Recruiter)
# 4. Mint Green (Front-end Developer)
PALETTE_VARIANTS = {
    "rose": {
        "light": {
            "bg": "#FFF1F4",
            "border": "#FDE2E8",
            "badge_bg": "#FFE4E9",
            "accent": "#E11D48",
            "progress": "#18181B",
            "gradient": ["#F43F5E", "#FB7185"],
            "icon": ft.Icons.PALETTE_ROUNDED,
            "footer_bg": "#FFFFFF",
            "btn_bg": "#18181B",
            "btn_text": "#FFFFFF",
        },
        "dark": {
            "bg": "#221519",
            "border": "#3D1A23",
            "badge_bg": "#381B24",
            "accent": "#FB7185",
            "progress": "#FB7185",
            "gradient": ["#9F1239", "#BE123C"],
            "icon": ft.Icons.PALETTE_ROUNDED,
            "footer_bg": "#16171D",
            "btn_bg": "#FAFAFA",
            "btn_text": "#18181B",
        },
    },
    "sky": {
        "light": {
            "bg": "#F0F7FF",
            "border": "#DFEDFA",
            "badge_bg": "#E0F2FE",
            "accent": "#0284C7",
            "progress": "#18181B",
            "gradient": ["#0284C7", "#38BDF8"],
            "icon": ft.Icons.VERIFIED_USER_ROUNDED,
            "footer_bg": "#FFFFFF",
            "btn_bg": "#18181B",
            "btn_text": "#FFFFFF",
        },
        "dark": {
            "bg": "#121E2A",
            "border": "#1A344A",
            "badge_bg": "#183247",
            "accent": "#38BDF8",
            "progress": "#38BDF8",
            "gradient": ["#0369A1", "#0284C7"],
            "icon": ft.Icons.VERIFIED_USER_ROUNDED,
            "footer_bg": "#16171D",
            "btn_bg": "#FAFAFA",
            "btn_text": "#18181B",
        },
    },
    "amber": {
        "light": {
            "bg": "#FEFCE8",
            "border": "#FEF08A",
            "badge_bg": "#FEF3C7",
            "accent": "#B45309",
            "progress": "#18181B",
            "gradient": ["#D97706", "#FBBF24"],
            "icon": ft.Icons.EMOJI_PEOPLE_ROUNDED,
            "footer_bg": "#FFFFFF",
            "btn_bg": "#18181B",
            "btn_text": "#FFFFFF",
        },
        "dark": {
            "bg": "#221D12",
            "border": "#3E3319",
            "badge_bg": "#382E16",
            "accent": "#FBBF24",
            "progress": "#FBBF24",
            "gradient": ["#B45309", "#D97706"],
            "icon": ft.Icons.EMOJI_PEOPLE_ROUNDED,
            "footer_bg": "#16171D",
            "btn_bg": "#FAFAFA",
            "btn_text": "#18181B",
        },
    },
    "mint": {
        "light": {
            "bg": "#F0FDF4",
            "border": "#DCFCE7",
            "badge_bg": "#DCFCE7",
            "accent": "#15803D",
            "progress": "#18181B",
            "gradient": ["#059669", "#34D399"],
            "icon": ft.Icons.TERMINAL_ROUNDED,
            "footer_bg": "#FFFFFF",
            "btn_bg": "#18181B",
            "btn_text": "#FFFFFF",
        },
        "dark": {
            "bg": "#122318",
            "border": "#193C27",
            "badge_bg": "#173725",
            "accent": "#34D399",
            "progress": "#34D399",
            "gradient": ["#047857", "#059669"],
            "icon": ft.Icons.TERMINAL_ROUNDED,
            "footer_bg": "#16171D",
            "btn_bg": "#FAFAFA",
            "btn_text": "#18181B",
        },
    },
}

PALETTE_KEYS = ["rose", "sky", "amber", "mint"]


def get_card_palette(category: str | None = None, title: str | None = None, is_dark: bool = False):
    """
    Selects one of the 4 pastel themes based on category keyword,
    or falls back to a deterministic hash of the title.
    """
    cat_str = (category or "").lower()
    title_str = (title or "").lower()
    combined = f"{cat_str} {title_str}"

    if any(k in combined for k in ["ui", "ux", "design", "art", "creative", "figma", "graphic"]):
        key = "rose"
    elif any(k in combined for k in ["qa", "test", "quality", "security", "cloud", "devops", "engineer", "network"]):
        key = "sky"
    elif any(k in combined for k in ["recruiter", "hr", "talent", "business", "market", "manage", "lead", "finance"]):
        key = "amber"
    elif any(k in combined for k in ["front", "dev", "web", "code", "python", "javascript", "flutter", "react", "html"]):
        key = "mint"
    else:
        hash_idx = abs(hash(f"{cat_str}-{title_str}")) % len(PALETTE_KEYS)
        key = PALETTE_KEYS[hash_idx]

    variant = PALETTE_VARIANTS[key]
    mode = "dark" if is_dark else "light"
    return variant[mode]


def build_course_avatar(image_url: str | None, palette: dict, size: int = 82):
    """
    Builds the right-aligned image or a 3D-styled avatar placeholder.
    """
    if image_url:
        return ft.Container(
            width=size,
            height=size,
            border_radius=ft.BorderRadius.all(18),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.12, palette["accent"])),
            content=ft.Image(
                src=image_url,
                width=size,
                height=size,
                fit=ft.BoxFit.COVER,
                placeholder_src="/placeholder.png",
                placeholder_fit=ft.BoxFit.COVER,
                error_content=ft.Container(
                    width=size,
                    height=size,
                    gradient=ft.LinearGradient(
                        begin=ft.Alignment.TOP_LEFT,
                        end=ft.Alignment.BOTTOM_RIGHT,
                        colors=palette["gradient"],
                    ),
                    alignment=ft.Alignment.CENTER,
                    content=ft.Icon(palette["icon"], size=size * 0.45, color=ft.Colors.WHITE),
                ),
            ),
        )

    # 3D character/avatar placeholder with gradient backdrop
    return ft.Container(
        width=size,
        height=size,
        border_radius=ft.BorderRadius.all(18),
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        gradient=ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
            colors=palette["gradient"],
        ),
        shadow=ft.BoxShadow(
            blur_radius=10,
            color=ft.Colors.with_opacity(0.2, palette["accent"]),
            offset=ft.Offset(0, 3),
        ),
        alignment=ft.Alignment.CENTER,
        content=ft.Container(
            width=size * 0.65,
            height=size * 0.65,
            border_radius=ft.BorderRadius.all(size * 0.35),
            bgcolor=ft.Colors.with_opacity(0.25, ft.Colors.WHITE),
            alignment=ft.Alignment.CENTER,
            content=ft.Icon(palette["icon"], size=size * 0.42, color=ft.Colors.WHITE),
        ),
    )
