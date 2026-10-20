"""
Centralized Typography Design System for Nu-Age LMS.
Provides curated font pairings, semantic hierarchy tokens, and real-time live preview switching.
"""
from typing import Dict, Any, Optional, Callable
import flet as ft

# ─────────────────────────────────────────────────────────────────────────────
# CURATED TYPOGRAPHY PRESETS
# ─────────────────────────────────────────────────────────────────────────────
TYPOGRAPHY_PRESETS: Dict[str, Dict[str, Any]] = {
    "modern": {
        "name": "Modern EdTech",
        "description": "Plus Jakarta Sans for punchy titles + Inter for fatigue-free screen reading.",
        "heading": "jakarta",
        "subheading": "jakarta",
        "body": "inter",
        "mono": "firacode",
        "badge": "Modern",
    },
    "editorial": {
        "name": "Editorial Academy",
        "description": "Outfit for crisp headers + Lora for warm, long-form literary immersion.",
        "heading": "outfit",
        "subheading": "outfit",
        "body": "lora",
        "mono": "firacode",
        "badge": "Academic",
    },
    "tech": {
        "name": "Futuristic Tech",
        "description": "Space Grotesk for geometric STEM titles + Inter for clean technical clarity.",
        "heading": "spacegrotesk",
        "subheading": "jakarta",
        "body": "inter",
        "mono": "firacode",
        "badge": "STEM & Tech",
    },
    "friendly": {
        "name": "Friendly Geometric",
        "description": "Poppins rounded titles + Inter body for accessible, welcoming study vibes.",
        "heading": "poppins",
        "subheading": "poppins",
        "body": "inter",
        "mono": "firacode",
        "badge": "Accessible",
    },
    "classic": {
        "name": "Nu-Age Classic",
        "description": "Original Montserrat geometric headers with Roboto body.",
        "heading": "montserrat",
        "subheading": "montserrat",
        "body": "roboto",
        "mono": "monospace",
        "badge": "Classic",
    },
}

DEFAULT_PRESET_KEY = "modern"


def get_current_preset_key(page: ft.Page) -> str:
    """Retrieves active typography preset from page session store or defaults to 'modern'."""
    try:
        from src.utils.session_utils import get_session_store
        store = get_session_store(page)
        if hasattr(store, "get"):
            stored = store.get("typography_preset")
            if stored and stored in TYPOGRAPHY_PRESETS:
                return stored
    except Exception:
        pass
    return getattr(page, "_active_typography_preset", DEFAULT_PRESET_KEY) or DEFAULT_PRESET_KEY


def set_current_preset_key(page: ft.Page, preset_key: str):
    """Sets and persists the active typography preset."""
    if preset_key not in TYPOGRAPHY_PRESETS:
        preset_key = DEFAULT_PRESET_KEY
    try:
        setattr(page, "_active_typography_preset", preset_key)
        from src.utils.session_utils import set_session_value
        set_session_value(page, "typography_preset", preset_key)
    except Exception:
        pass


def get_font_tokens(page_or_preset: Any) -> Dict[str, str]:
    """Resolves font family tokens (heading, subheading, body, mono) for the given page or preset key."""
    if isinstance(page_or_preset, str) and page_or_preset in TYPOGRAPHY_PRESETS:
        key = page_or_preset
    elif hasattr(page_or_preset, "route") or hasattr(page_or_preset, "fonts"):
        key = get_current_preset_key(page_or_preset)
    else:
        key = DEFAULT_PRESET_KEY

    preset = TYPOGRAPHY_PRESETS.get(key, TYPOGRAPHY_PRESETS[DEFAULT_PRESET_KEY])
    return {
        "heading": preset["heading"],
        "subheading": preset["subheading"],
        "body": preset["body"],
        "mono": preset["mono"],
    }


def get_heading_font(page_or_preset: Any = None) -> str:
    return get_font_tokens(page_or_preset)["heading"]


def get_subheading_font(page_or_preset: Any = None) -> str:
    return get_font_tokens(page_or_preset)["subheading"]


def get_body_font(page_or_preset: Any = None) -> str:
    return get_font_tokens(page_or_preset)["body"]


def get_mono_font(page_or_preset: Any = None) -> str:
    return get_font_tokens(page_or_preset)["mono"]


_typography_listeners = set()


def add_typography_listener(callback: Callable[[str], None]):
    """Registers a callback to be triggered when the typography preset changes system-wide."""
    _typography_listeners.add(callback)


def remove_typography_listener(callback: Callable[[str], None]):
    """Unregisters a previously registered typography change callback."""
    _typography_listeners.discard(callback)


def apply_typography_system_wide(page: ft.Page, preset_key: str, trigger_update: bool = True):
    """
    Applies the chosen typography preset across the entire application:
    1. Updates page session store and page instance state.
    2. Updates page.theme.font_family and page.dark_theme.font_family for global adoption.
    3. Persists preference to page.shared_preferences asynchronously.
    4. Notifies all registered UI listeners.
    5. Optionally calls page.update().
    """
    if preset_key not in TYPOGRAPHY_PRESETS:
        preset_key = DEFAULT_PRESET_KEY

    set_current_preset_key(page, preset_key)
    tokens = get_font_tokens(preset_key)
    body_font = tokens["body"]

    # 1. Update global theme default font family
    if getattr(page, "theme", None):
        page.theme.font_family = body_font
    if getattr(page, "dark_theme", None):
        page.dark_theme.font_family = body_font

    # 2. Persist to shared_preferences asynchronously if available
    try:
        if hasattr(page, "shared_preferences") and page.shared_preferences:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(page.shared_preferences.set("typography_preset", preset_key))
            except RuntimeError:
                pass
    except Exception:
        pass

    # 3. Notify any registered listeners
    for listener in list(_typography_listeners):
        try:
            listener(preset_key)
        except Exception as ex:
            print(f"[Typography] Listener error: {ex}")

    # 4. Trigger UI update if requested
    if trigger_update and hasattr(page, "update"):
        try:
            page.update()
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# LIVE TYPOGRAPHY SWITCHER MODAL / BUTTON
# ─────────────────────────────────────────────────────────────────────────────
def build_typography_switcher_button(
    page: ft.Page,
    on_preset_changed: Optional[Callable[[str], Any]] = None,
    button_height: int = 34,
) -> ft.Control:
    """
    Builds a sleek typography chip/button that displays the active preset name
    and opens a visual selection modal with live previews.
    """
    current_key = get_current_preset_key(page)

    label_text = ft.Text(
        f"Font: {TYPOGRAPHY_PRESETS[current_key]['name'].split()[0]}",
        size=11,
        weight=ft.FontWeight.W_600,
        color=ft.Colors.PRIMARY,
    )

    def open_modal(e=None):
        is_dark = page.theme_mode == ft.ThemeMode.DARK
        card_bg = "#1E222B" if is_dark else "#FFFFFF"
        card_border = ft.Colors.with_opacity(0.12, ft.Colors.WHITE) if is_dark else ft.Colors.with_opacity(0.10, ft.Colors.BLACK)
        text_primary = "#FFFFFF" if is_dark else "#1A1A1A"
        text_muted = "#94A3B8" if is_dark else "#64748B"

        dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=18),
            bgcolor=card_bg,
            title=ft.Row(
                [
                    ft.Container(
                        width=36,
                        height=36,
                        border_radius=10,
                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(ft.Icons.FONT_DOWNLOAD_ROUNDED, color=ft.Colors.PRIMARY, size=20),
                    ),
                    ft.Column(
                        [
                            ft.Text("Typography & Reading Style", weight=ft.FontWeight.BOLD, size=16, color=text_primary),
                            ft.Text("Choose your preferred aesthetic font pairing", size=11, color=text_muted),
                        ],
                        spacing=2,
                        tight=True,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

        preset_cards_col = ft.Column(spacing=10, tight=True)

        def select_preset(key: str):
            apply_typography_system_wide(page, key, trigger_update=True)
            label_text.value = f"Font: {TYPOGRAPHY_PRESETS[key]['name'].split()[0]}"
            dlg.open = False
            page.update()
            if callable(on_preset_changed):
                try:
                    on_preset_changed(key)
                except Exception as ex:
                    print(f"[Typography] Callback error: {ex}")

        active_k = get_current_preset_key(page)
        for p_key, p_info in TYPOGRAPHY_PRESETS.items():
            is_active = (p_key == active_k)
            border_clr = ft.Colors.PRIMARY if is_active else card_border
            active_bg = ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY) if is_active else ft.Colors.TRANSPARENT

            sample_card = ft.Container(
                ink=True,
                on_click=lambda e, k=p_key: select_preset(k),
                border_radius=12,
                padding=ft.Padding.all(12),
                bgcolor=active_bg,
                border=ft.Border.all(1.5 if is_active else 1, border_clr),
                content=ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Text(
                                            p_info["name"],
                                            size=13.5,
                                            weight=ft.FontWeight.BOLD,
                                            font_family=p_info["heading"],
                                            color=ft.Colors.PRIMARY if is_active else text_primary,
                                        ),
                                        ft.Container(
                                            content=ft.Text(p_info["badge"], size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                            border_radius=4,
                                            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                                        ),
                                    ],
                                    spacing=8,
                                    tight=True,
                                ),
                                ft.Text(
                                    "The quick brown fox jumps over the lazy dog.",
                                    size=12,
                                    font_family=p_info["body"],
                                    color=text_muted,
                                ),
                                ft.Text(
                                    f"Heading: {p_info['heading']} • Body: {p_info['body']}",
                                    size=10,
                                    color=ft.Colors.with_opacity(0.5, text_muted),
                                ),
                            ],
                            expand=True,
                            spacing=3,
                        ),
                        ft.Icon(
                            ft.Icons.CHECK_CIRCLE_ROUNDED if is_active else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED,
                            color=ft.Colors.PRIMARY if is_active else ft.Colors.with_opacity(0.3, text_muted),
                            size=20,
                        ),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
            preset_cards_col.controls.append(sample_card)

        dlg.content = ft.Container(
            content=ft.Column(
                [
                    preset_cards_col,
                ],
                tight=True,
                scroll=ft.ScrollMode.AUTO,
            ),
            width=460,
        )

        dlg.actions = [
            ft.TextButton(
                "Close",
                on_click=lambda e: (setattr(dlg, "open", False), page.update()),
                style=ft.ButtonStyle(color=text_muted),
            )
        ]
        page.show_dialog(dlg)
        page.update()

    btn = ft.Container(
        ink=True,
        on_click=open_modal,
        height=button_height,
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
        border_radius=8,
        bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.24, ft.Colors.PRIMARY)),
        tooltip="Typography & Font Pairings",
        content=ft.Row(
            [
                ft.Icon(ft.Icons.TEXT_FORMAT_ROUNDED, size=15, color=ft.Colors.PRIMARY),
                label_text,
            ],
            spacing=5,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )
    return btn
