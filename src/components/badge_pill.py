"""
src/components/badge_pill.py
──────────────────────────────────────────────────────────────────────────────
Universal, Glossy, Mobile-Optimized Badge Pill Component.
Provides:
- Luminous glassmorphic styling with subtle glowing borders & gradients.
- Strict mobile viewport boundaries with text truncation (never wraps to 2 lines).
- Usable across Chat message bubbles, direct headers, member profiles, and leaderboards.
──────────────────────────────────────────────────────────────────────────────
"""

import flet as ft
from typing import Optional, Dict, Any, Callable


# Icon mapping dictionary for robust fallback resolution
ICON_MAP = {
    # Academic & Learning
    "SCHOOL_ROUNDED": ft.Icons.SCHOOL_ROUNDED,
    "MENU_BOOK_ROUNDED": ft.Icons.MENU_BOOK_ROUNDED,
    "PSYCHOLOGY_ROUNDED": ft.Icons.PSYCHOLOGY_ROUNDED,
    "LIGHTBULB_ROUNDED": ft.Icons.LIGHTBULB_ROUNDED,
    "SCIENCE_ROUNDED": ft.Icons.SCIENCE_ROUNDED,
    "AUTO_STORIES_ROUNDED": ft.Icons.AUTO_STORIES_ROUNDED,
    
    # Honors & Milestones
    "STAR_ROUNDED": ft.Icons.STAR_ROUNDED,
    "WORKSPACE_PREMIUM_ROUNDED": ft.Icons.WORKSPACE_PREMIUM_ROUNDED,
    "MILITARY_TECH_ROUNDED": ft.Icons.MILITARY_TECH_ROUNDED,
    "EMOJI_EVENTS_ROUNDED": ft.Icons.EMOJI_EVENTS_ROUNDED,
    "DIAMOND_ROUNDED": ft.Icons.DIAMOND_ROUNDED,
    "SHIELD_ROUNDED": ft.Icons.SHIELD_ROUNDED,
    "VERIFIED_ROUNDED": ft.Icons.VERIFIED_ROUNDED,
    "AUTO_AWESOME_ROUNDED": ft.Icons.AUTO_AWESOME_ROUNDED,
    "LOCAL_FIRE_DEPARTMENT_ROUNDED": ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED,
    "BOLT_ROUNDED": ft.Icons.BOLT_ROUNDED,
    
    # Collaboration & Community
    "CAMPAIGN_ROUNDED": ft.Icons.CAMPAIGN_ROUNDED,
    "GROUPS_ROUNDED": ft.Icons.GROUPS_ROUNDED,
    "HANDSHAKE_ROUNDED": ft.Icons.HANDSHAKE_ROUNDED,
    "PUBLIC_ROUNDED": ft.Icons.PUBLIC_ROUNDED,
    "VOLUNTEER_ACTIVISM_ROUNDED": ft.Icons.VOLUNTEER_ACTIVISM_ROUNDED,
    "CELEBRATION_ROUNDED": ft.Icons.CELEBRATION_ROUNDED,
    "FORUM_ROUNDED": ft.Icons.FORUM_ROUNDED,
    
    # Logic, Coding & Mastery
    "CODE_ROUNDED": ft.Icons.CODE_ROUNDED,
    "TERMINAL_ROUNDED": ft.Icons.TERMINAL_ROUNDED,
    "ROCKET_LAUNCH_ROUNDED": ft.Icons.ROCKET_LAUNCH_ROUNDED,
    "SPEED_ROUNDED": ft.Icons.SPEED_ROUNDED,
    "CALCULATE_ROUNDED": ft.Icons.CALCULATE_ROUNDED,
    "FITNESS_CENTER_ROUNDED": ft.Icons.FITNESS_CENTER_ROUNDED,
    "FAVORITE_ROUNDED": ft.Icons.FAVORITE_ROUNDED,
    "EXPLORE_ROUNDED": ft.Icons.EXPLORE_ROUNDED,
    "SECURITY_ROUNDED": ft.Icons.SECURITY_ROUNDED,
    "TRENDING_UP_ROUNDED": ft.Icons.TRENDING_UP_ROUNDED,
    "LEADERBOARD_ROUNDED": ft.Icons.LEADERBOARD_ROUNDED,
}


def _hex_to_rgb(hex_str: str):
    hex_str = str(hex_str).strip().lstrip("#")
    if len(hex_str) == 3:
        hex_str = "".join([c * 2 for c in hex_str])
    if len(hex_str) >= 6:
        try:
            return int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
        except ValueError:
            pass
    return 76, 175, 80


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{max(0, min(255, r)):02x}{max(0, min(255, g)):02x}{max(0, min(255, b)):02x}"


def _get_glossy_gradient_colors(base_hex: str, start_hex: Optional[str] = None, end_hex: Optional[str] = None):
    if start_hex and end_hex and start_hex != end_hex:
        return start_hex, end_hex
    try:
        r, g, b = _hex_to_rgb(base_hex)
        # Glossy top highlight: blend ~26% towards white
        top_r = int(r + (255 - r) * 0.26)
        top_g = int(g + (255 - g) * 0.26)
        top_b = int(b + (255 - b) * 0.26)
        # 3D raised depth: shade ~18% darker on bottom
        bot_r = int(r * 0.82)
        bot_g = int(g * 0.82)
        bot_b = int(b * 0.82)
        return _rgb_to_hex(top_r, top_g, top_b), _rgb_to_hex(bot_r, bot_g, bot_b)
    except Exception:
        return base_hex, base_hex


def build_glossy_badge_pill(
    badge: Optional[Dict[str, Any]],
    is_mobile: bool = False,
    max_width: int = 145,
    on_click: Optional[Callable] = None,
    show_icon: bool = True,
    icon_only: bool = False,
    max_chars: Optional[int] = 16,
) -> ft.Control:
    """
    Renders a glossy, 3D raised badge pill with full color (not a less opaque background).
    Guarantees no overflow, true pill hugging with no trailing empty space,
    high-contrast foreground, and supports icon-only mode when requested or when badge title is long.
    """
    if not badge or not isinstance(badge, dict):
        return ft.Container(visible=False)

    name = str(badge.get("name") or badge.get("title") or "Member").strip()
    color_hex = badge.get("color_hex") or "#4CAF50"
    icon_key = str(badge.get("icon") or "STAR_ROUNDED").upper()
    icon_data = ICON_MAP.get(icon_key, getattr(ft.Icons, icon_key, ft.Icons.STAR_ROUNDED))

    # Calculate luminance for perfect contrast on full color
    r, g, b = _hex_to_rgb(color_hex)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    foreground_color = "#111827" if luminance > 0.72 else "#FFFFFF"

    # Glossy 3D raised gradient with FULL color
    grad_start, grad_end = _get_glossy_gradient_colors(
        color_hex, badge.get("gradient_start"), badge.get("gradient_end")
    )
    gradient_bg = ft.LinearGradient(
        begin=ft.Alignment.TOP_CENTER,
        end=ft.Alignment.BOTTOM_CENTER,
        colors=[grad_start, grad_end],
    )

    # 3D raised shadow
    pill_shadow = ft.BoxShadow(
        blur_radius=5.5,
        color=ft.Colors.with_opacity(0.36, ft.Colors.BLACK),
        offset=ft.Offset(0, 2.5),
    )

    # Glossy reflective rim border
    rim_color = ft.Colors.with_opacity(0.40, ft.Colors.WHITE if luminance <= 0.72 else ft.Colors.BLACK)
    pill_border = ft.Border.all(1.0, rim_color)

    font_sz = 9.0 if is_mobile else 10.0
    icon_sz = 11.0 if is_mobile else 12.0
    h_pad = 5 if is_mobile else 6.5
    v_pad = 2 if is_mobile else 2.5

    # Determine if this should render in icon-only mode
    should_icon_only = icon_only or (max_chars is not None and len(name) > max_chars)

    desc = badge.get("description")
    tooltip_text = f"{name}: {desc}" if desc else name

    if should_icon_only:
        # Icon-only pill mode: sleek, compact, 3D raised glowing jewel
        return ft.Container(
            content=ft.Icon(icon_data, size=icon_sz + 1.2, color=foreground_color),
            padding=ft.Padding.symmetric(horizontal=h_pad + 1.0, vertical=v_pad + 0.5),
            border_radius=ft.BorderRadius.all(12),
            gradient=gradient_bg,
            border=pill_border,
            shadow=pill_shadow,
            ink=bool(on_click),
            on_click=on_click,
            tooltip=tooltip_text,
        )

    # Safe text control with high-contrast text on solid full color
    label_text = ft.Text(
        name,
        size=font_sz,
        weight=ft.FontWeight.W_800,
        color=foreground_color,
        max_lines=1,
        no_wrap=True,
        overflow=ft.TextOverflow.ELLIPSIS,
    )

    controls = []
    if show_icon:
        controls.append(ft.Icon(icon_data, size=icon_sz, color=foreground_color))

    # Tightly bounded text wrapper: hugs text without forced dead space
    char_w = 6.2 if is_mobile else 6.8
    est_w = int(len(name) * char_w) + 3
    max_text_w = max(20, max_width - (20 if show_icon else 8))
    
    if est_w > max_text_w:
        text_container = ft.Container(
            content=label_text,
            width=max_text_w,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )
    else:
        text_container = ft.Container(
            content=label_text,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )
    controls.append(text_container)

    return ft.Container(
        content=ft.Row(
            controls=controls,
            spacing=3.5,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.START,
        ),
        padding=ft.Padding.symmetric(horizontal=h_pad + 1.0, vertical=v_pad + 0.5),
        border_radius=ft.BorderRadius.all(12),
        gradient=gradient_bg,
        border=pill_border,
        shadow=pill_shadow,
        ink=bool(on_click),
        on_click=on_click,
        tooltip=tooltip_text,
    )
