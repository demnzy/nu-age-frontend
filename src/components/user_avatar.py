import flet as ft
from typing import Optional, Callable, Any

_PALETTES = [
    ("#6366F1", "#EEF2FF"), # Indigo
    ("#3B82F6", "#EFF6FF"), # Blue
    ("#0EA5E9", "#F0F9FF"), # Sky
    ("#10B981", "#ECFDF5"), # Emerald
    ("#F59E0B", "#FFFBEB"), # Amber
    ("#EC4899", "#FDF2F8"), # Pink
    ("#8B5CF6", "#F5F3FF"), # Violet
    ("#14B8A6", "#F0FDFA"), # Teal
]

def get_user_initials(name: str | None) -> str:
    """Extract up to 2 uppercase initials from a name string."""
    if not name or not name.strip():
        return "NU"
    parts = [p for p in name.strip().split() if p]
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    elif len(parts) == 1:
        return parts[0][:2].upper() if len(parts[0]) >= 2 else parts[0][0].upper()
    return "NU"

def get_avatar_color(name: str | None) -> tuple[str, str]:
    """Returns (bgcolor, text_color) deterministically derived from user's name."""
    if not name:
        return _PALETTES[0]
    idx = abs(hash(name)) % len(_PALETTES)
    return _PALETTES[idx]

def build_user_avatar(
    name: str = "",
    image_url: Optional[str] = None,
    radius: int = 20,
    is_online: bool = False,
    show_online_dot: bool = False,
    is_group: bool = False,
    on_click: Optional[Callable[[Any], Any]] = None,
    tooltip: Optional[str] = None,
    bgcolor: Optional[str] = None,
    text_color: Optional[str] = None,
    border_color: Optional[str] = None,
    border_width: float = 0,
) -> ft.Control:
    """
    Standardized, high-performance Avatar control compliant with Flet 0.86.5.
    - If image_url is provided, displays circular edge-optimized profile photo.
    - If image_url is absent or fails, falls back gracefully to deterministic initials monogram.
    - Displays group icon for channel clusters when is_group is True.
    - Supports real-time online presence dot and hover/click states.
    """
    initials = get_user_initials(name)
    def_bg, def_txt = get_avatar_color(name)
    bg = bgcolor or def_bg
    txt = text_color or "#FFFFFF"

    # Base CircleAvatar
    if is_group:
        base_avatar = ft.CircleAvatar(
            content=ft.Icon(ft.Icons.GROUPS_ROUNDED, color=ft.Colors.WHITE, size=max(12, int(radius * 1.1))),
            bgcolor=bg,
            radius=radius,
        )
    elif image_url and isinstance(image_url, str) and (image_url.startswith("http") or image_url.startswith("data:")):
        base_avatar = ft.CircleAvatar(
            foreground_image_src=image_url,
            bgcolor=bg,
            radius=radius,
            content=ft.Text(
                initials,
                size=max(8, int(radius * 0.58)),
                weight=ft.FontWeight.BOLD,
                color=txt,
            ),
        )
    else:
        base_avatar = ft.CircleAvatar(
            bgcolor=bg,
            radius=radius,
            content=ft.Text(
                initials,
                size=max(8, int(radius * 0.58)),
                weight=ft.FontWeight.BOLD,
                color=txt,
            ),
        )

    # Optional Border Wrap
    if border_width > 0 and border_color:
        diameter = radius * 2
        base_avatar = ft.Container(
            width=diameter + (border_width * 2),
            height=diameter + (border_width * 2),
            border_radius=radius + border_width,
            border=ft.Border.all(border_width, border_color),
            alignment=ft.Alignment.CENTER,
            content=base_avatar,
        )

    # Optional Online Status Dot
    if show_online_dot:
        dot_size = max(9, int(radius * 0.55))
        status_dot = ft.Container(
            width=dot_size,
            height=dot_size,
            bgcolor="#22C55E" if is_online else "#94A3B8",
            border=ft.Border.all(2, "#181B24"),
            shape=ft.BoxShape.CIRCLE,
        )
        total_dim = (radius * 2) + (int(border_width * 2) if border_width > 0 else 0)
        base_avatar = ft.Stack(
            controls=[
                base_avatar,
                ft.Container(
                    content=status_dot,
                    alignment=ft.Alignment(1.0, 1.0),
                    width=total_dim,
                    height=total_dim,
                ),
            ],
            width=total_dim,
            height=total_dim,
        )

    # Optional Interactive Click / Tooltip Wrap
    if on_click or tooltip:
        dim = (radius * 2) + (int(border_width * 2) if border_width > 0 else 0)
        return ft.Container(
            content=base_avatar,
            width=dim,
            height=dim,
            ink=bool(on_click),
            border_radius=radius,
            on_click=on_click,
            tooltip=tooltip,
        )

    return base_avatar
