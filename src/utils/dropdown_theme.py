"""
dropdown_theme.py
──────────────────────────────────────────────────────────────────────────────
Centralized styling and theme utilities for all ft.Dropdown controls across
Nu-Age LMS.

Guarantees:
- Clamped menu popup height (`menu_height=260` default) to prevent off-screen
  menu expansion and enable smooth vertical scrolling for multiple options.
- App-themed popup menu surface (`menu_style=ft.MenuStyle(...)`) matching
  light/dark theme tokens (`ft.Colors.SURFACE`, subtle hairline border, no surface tint).
- Standardized form input styling (`border_radius=10`, `dense=True`,
  `content_padding=ft.Padding.symmetric(horizontal=12, vertical=8)`,
  `focused_border_color=ft.Colors.PRIMARY`).
──────────────────────────────────────────────────────────────────────────────
"""

import flet as ft


def get_dropdown_menu_style(page: ft.Page | None = None) -> ft.MenuStyle:
    """Returns the standardized, clean popup menu style matching Nu-Age theming."""
    return ft.MenuStyle(
        bgcolor=ft.Colors.SURFACE,
        elevation=8,
        shape=ft.RoundedRectangleBorder(radius=10),
        side=ft.BorderSide(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
    )


def apply_dropdown_theme(
    dropdown: ft.Dropdown,
    menu_height: int = 260,
    border_radius: int = 10,
    dense: bool = True,
) -> ft.Dropdown:
    """
    Applies the Nu-Age application dropdown theme to any ft.Dropdown instance in-place.
    Ensures bounded scrollable menu popup, consistent borders, and theme token adherence.
    """
    if dropdown is None:
        return dropdown

    dropdown.dense = dense
    dropdown.menu_height = menu_height
    dropdown.menu_style = get_dropdown_menu_style()
    dropdown.border_radius = border_radius
    if not dropdown.border_color:
        dropdown.border_color = ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE)
    dropdown.focused_border_color = ft.Colors.PRIMARY
    if not dropdown.content_padding:
        dropdown.content_padding = ft.Padding.symmetric(horizontal=12, vertical=8)

    return dropdown


def create_styled_dropdown(
    label: str | None = None,
    value: str | None = None,
    options: list[ft.dropdown.Option] | None = None,
    hint_text: str | None = None,
    width: int | float | None = None,
    expand: bool | int | None = None,
    on_select=None,
    on_change=None,
    menu_height: int = 260,
    border_radius: int = 10,
    dense: bool = True,
    disabled: bool = False,
    visible: bool = True,
) -> ft.Dropdown:
    """Factory function to instantiate a pre-themed, scroll-bounded ft.Dropdown."""
    handler = on_select or on_change
    dd = ft.Dropdown(
        label=label,
        value=value,
        options=options or [],
        hint_text=hint_text,
        width=width,
        expand=expand,
        on_select=handler,
        disabled=disabled,
        visible=visible,
    )
    return apply_dropdown_theme(dd, menu_height=menu_height, border_radius=border_radius, dense=dense)
