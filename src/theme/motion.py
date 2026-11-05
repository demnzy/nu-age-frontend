"""
src/theme/motion.py
──────────────────────────────────────────────────────────────────────────────
Centralized Motion, Animation Curves & Micro-Interaction Engine for NU-Front:
1. Standardized duration and curve tokens (responsive, non-blocking 120ms-340ms).
2. Hardware-accelerated transitions via Flet 0.86.5 native tweening.
3. Fluid tab cross-fading, accordion glides, card hover elevations, and drawers.
──────────────────────────────────────────────────────────────────────────────
"""

import asyncio
import flet as ft
from typing import Any, Callable, Dict, List, Optional, Tuple

# ─────────────────────────────────────────────────────────────────────────────
# 1. MOTION TOKENS (Responsive, Non-blocking Timings)
# ─────────────────────────────────────────────────────────────────────────────

DUR_MICRO = 120   # Micro-interactions, checkbox toggles, badge popups
DUR_FAST = 180    # Tab switches, hover lifts, icon rotations, button states
DUR_BASE = 240    # Accordions, modal steps, drawer slides, card flips
DUR_FLOW = 340    # View cross-fades, skeleton reveals, progress bar fills

CURVE_DECEL = ft.AnimationCurve.DECELERATE
CURVE_SMOOTH = ft.AnimationCurve.EASE_OUT_CUBIC
CURVE_SPRING = ft.AnimationCurve.EASE_OUT_BACK
CURVE_EMPHASIS = ft.AnimationCurve.EASE_IN_OUT_CUBIC
CURVE_EASE_OUT = ft.AnimationCurve.EASE_OUT
CURVE_EASE_IN = ft.AnimationCurve.EASE_IN


# ─────────────────────────────────────────────────────────────────────────────
# 2. SEAMLESS SWITCHERS (CROSS-FADES & STEP TRANSITIONS)
# ─────────────────────────────────────────────────────────────────────────────

def fade_switcher(
    content: Optional[ft.Control] = None,
    duration: int = DUR_FAST,
    reverse_duration: Optional[int] = None,
    expand: bool = True,
    align: ft.Alignment = ft.Alignment.TOP_CENTER,
    switch_in_curve: ft.AnimationCurve = CURVE_EASE_OUT,
    switch_out_curve: ft.AnimationCurve = CURVE_EASE_IN,
) -> ft.AnimatedSwitcher:
    """
    Returns an AnimatedSwitcher pre-configured for silky-smooth cross-fades
    between tab subviews, lesson steps, or content sockets.
    """
    return ft.AnimatedSwitcher(
        content=content or ft.Container(),
        transition=ft.AnimatedSwitcherTransition.FADE,
        duration=duration,
        reverse_duration=reverse_duration or max(100, int(duration * 0.75)),
        switch_in_curve=switch_in_curve,
        switch_out_curve=switch_out_curve,
        expand=expand,
        align=align,
    )


def scale_switcher(
    content: Optional[ft.Control] = None,
    duration: int = DUR_FAST,
    reverse_duration: Optional[int] = None,
    expand: bool = False,
    align: ft.Alignment = ft.Alignment.CENTER,
) -> ft.AnimatedSwitcher:
    """
    Returns an AnimatedSwitcher with scale transition for badges, icons, or floating chips.
    """
    return ft.AnimatedSwitcher(
        content=content or ft.Container(),
        transition=ft.AnimatedSwitcherTransition.SCALE,
        duration=duration,
        reverse_duration=reverse_duration or max(100, int(duration * 0.75)),
        switch_in_curve=CURVE_SPRING,
        switch_out_curve=CURVE_EASE_IN,
        expand=expand,
        align=align,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 3. INTERACTIVE TAB PILLS & SEGMENTED CONTROLS
# ─────────────────────────────────────────────────────────────────────────────

def animated_tab_pill(
    label: str,
    icon: Optional[str],
    is_selected: bool,
    on_click: Optional[Callable[[Any], None]],
    accent_color: str = ft.Colors.PRIMARY,
    on_accent_color: str = ft.Colors.ON_PRIMARY,
    card_bg: str = ft.Colors.SURFACE,
    is_narrow: bool = False,
    badge_count: Optional[int] = None,
    badge_color: Optional[str] = None,
) -> ft.Container:
    """
    Interactive tab pill button with smooth background, border, and scale animation.
    Eliminates abrupt color/border snapping when switching tabs.
    """
    padding = ft.Padding.symmetric(
        horizontal=10 if is_narrow else 14,
        vertical=7 if is_narrow else 9,
    )

    bg = ft.Colors.with_opacity(0.14 if is_selected else 0.0, accent_color)
    border_color = accent_color if is_selected else ft.Colors.TRANSPARENT
    text_color = accent_color if is_selected else ft.Colors.ON_SURFACE_VARIANT
    icon_color = accent_color if is_selected else ft.Colors.ON_SURFACE_VARIANT

    row_controls: List[ft.Control] = []
    if icon:
        row_controls.append(ft.Icon(icon, size=16 if is_narrow else 18, color=icon_color))

    row_controls.append(
        ft.Text(
            label,
            size=12 if is_narrow else 13,
            weight=ft.FontWeight.W_700 if is_selected else ft.FontWeight.W_500,
            color=text_color,
        )
    )

    if badge_count is not None and badge_count > 0:
        row_controls.append(
            ft.Container(
                content=ft.Text(
                    str(badge_count),
                    size=10,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.WHITE,
                ),
                bgcolor=badge_color or accent_color,
                border_radius=ft.BorderRadius.all(10),
                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
            )
        )

    return ft.Container(
        padding=padding,
        border_radius=ft.BorderRadius.all(12),
        bgcolor=bg,
        border=ft.Border.all(1.2, border_color),
        animate=ft.Animation(DUR_FAST, CURVE_EASE_OUT),
        animate_scale=ft.Animation(DUR_MICRO, CURVE_SPRING),
        scale=1.0,
        ink=True,
        on_click=on_click,
        content=ft.Row(
            spacing=6,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=row_controls,
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# 4. CARD HOVER LIFTS & MICRO-INTERACTIONS
# ─────────────────────────────────────────────────────────────────────────────

def attach_hover_lift(
    container: ft.Container,
    scale_hover: float = 1.015,
    elevation_normal: float = 0.0,
    elevation_hover: float = 4.0,
    accent_hover_color: Optional[str] = None,
    original_border: Optional[ft.Border] = None,
):
    """
    Attaches a smooth hover lift micro-interaction to any container:
    - Scales up by scale_hover (e.g. 1.015)
    - Elevates shadow smoothly
    - Gently highlights border if accent_hover_color is provided
    """
    container.animate_scale = ft.Animation(DUR_FAST, CURVE_SPRING)
    container.animate = ft.Animation(DUR_FAST, CURVE_SMOOTH)
    container.scale = 1.0

    orig_border = original_border or getattr(container, "border", None)

    def _on_hover(e):
        is_hovered = (e.data == "true")
        container.scale = scale_hover if is_hovered else 1.0
        if accent_hover_color:
            if is_hovered:
                container.border = ft.Border.all(1.2, accent_hover_color)
            else:
                container.border = orig_border
        try:
            container.update()
        except Exception:
            pass

    container.on_hover = _on_hover


# ─────────────────────────────────────────────────────────────────────────────
# 5. SMOOTH ACCORDIONS & COLLAPSIBLE MODULES
# ─────────────────────────────────────────────────────────────────────────────

def build_smooth_accordion(
    header_content: ft.Control,
    body_content: ft.Control,
    is_expanded: bool = False,
    on_toggle: Optional[Callable[[bool], None]] = None,
    chevron_icon: Optional[ft.Icon] = None,
    border_radius: int = 12,
    bgcolor: str = ft.Colors.SURFACE,
    border: Optional[ft.Border] = None,
) -> Tuple[ft.Container, Callable[[Any], None]]:
    """
    Builds a smoothly expanding accordion:
    - 180° chevron rotation with CURVE_EMPHASIS
    - Body crossfade & height expansion via fade_switcher
    Returns (accordion_container, toggle_callback).
    """
    state = {"expanded": is_expanded}

    chevron = chevron_icon or ft.Icon(
        ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED,
        size=20,
        color=ft.Colors.ON_SURFACE_VARIANT,
    )
    chevron.animate_rotation = ft.Animation(DUR_BASE, CURVE_EMPHASIS)
    chevron.rotate = 0.5 if is_expanded else 0.0

    body_slot = fade_switcher(
        content=body_content if is_expanded else ft.Container(height=0),
        duration=DUR_FAST,
        expand=False,
    )

    def _toggle(e=None):
        state["expanded"] = not state["expanded"]
        now_expanded = state["expanded"]
        chevron.rotate = 0.5 if now_expanded else 0.0
        body_slot.content = body_content if now_expanded else ft.Container(height=0)
        try:
            chevron.update()
            body_slot.update()
        except Exception:
            pass
        if on_toggle:
            try:
                on_toggle(now_expanded)
            except Exception:
                pass

    header_row = ft.Container(
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(content=header_content, expand=True),
                chevron,
            ],
        ),
        ink=True,
        on_click=_toggle,
    )

    accordion_container = ft.Container(
        border_radius=ft.BorderRadius.all(border_radius),
        bgcolor=bgcolor,
        border=border,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        animate=ft.Animation(DUR_FAST, CURVE_SMOOTH),
        content=ft.Column(
            spacing=0,
            tight=True,
            controls=[
                header_row,
                body_slot,
            ],
        ),
    )

    return accordion_container, _toggle


# ─────────────────────────────────────────────────────────────────────────────
# 6. STAGGERED ENTRANCES & PROGRESS ANIMATORS
# ─────────────────────────────────────────────────────────────────────────────

async def stagger_cards_entrance(
    card_containers: List[ft.Container],
    page: ft.Page,
    delay_seconds: float = 0.035,
    slide_offset_y: float = 0.06,
):
    """
    Animates a list of cards with a staggered fade-in + subtle slide-up.
    Card containers should be initialized with opacity=0.0 and offset=ft.Offset(0, slide_offset_y).
    """
    for card in card_containers:
        card.animate_opacity = ft.Animation(DUR_BASE, CURVE_DECEL)
        card.animate_offset = ft.Animation(DUR_BASE, CURVE_DECEL)
        card.opacity = 0.0
        card.offset = ft.Offset(0, slide_offset_y)

    for card in card_containers:
        card.opacity = 1.0
        card.offset = ft.Offset(0, 0)
        try:
            card.update()
        except Exception:
            break
        await asyncio.sleep(delay_seconds)

