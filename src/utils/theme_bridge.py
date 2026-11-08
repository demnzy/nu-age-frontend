"""
Theme Bridge & Shadcn UI Integration Layer for Nu-Age Frontend (Flet 1.1.2)
Provides:
1. Global Material-to-Lucide Icon Translation Engine (2,000+ vector icons).
2. Multi-Mode Theming Suite: Light, Dark, Midnight OLED (#000000), Nordic Slate (#0B0F19), and Warm Sepia/Paper (#F8F5EE).
3. Seamless integration between standard Flet controls and Shadcn UI components.
4. Dynamic responsive corner radiuses (8px mobile, 12px desktop).
"""

from __future__ import annotations
from typing import Any, Optional, Dict
import flet as ft

try:
    import flet_shadcn_ui as shad
    HAS_SHADCN = True
    LucideIcons = shad.LucideIcons
except ImportError:
    shad = None
    HAS_SHADCN = False
    LucideIcons = ft.Icons


# ─────────────────────────────────────────────────────────────────────────────
# 1. COMPREHENSIVE MATERIAL -> LUCIDE ICON MAPPING
# ─────────────────────────────────────────────────────────────────────────────
if HAS_SHADCN and shad:
    LUCIDE_ICON_MAP: Dict[str, Any] = {
        # Status & Checkmarks
        "CHECK": shad.LucideIcons.CHECK,
        "CHECK_ROUNDED": shad.LucideIcons.CHECK,
        "CHECK_CIRCLE": shad.LucideIcons.CHECK_CIRCLE_2,
        "CHECK_CIRCLE_ROUNDED": shad.LucideIcons.CHECK_CIRCLE_2,
        "CHECK_CIRCLE_OUTLINE": shad.LucideIcons.CHECK_CIRCLE,
        "CHECK_CIRCLE_OUTLINE_ROUNDED": shad.LucideIcons.CHECK_CIRCLE,
        "DONE_ALL": shad.LucideIcons.CHECK_CHECK,
        "DONE_ALL_ROUNDED": shad.LucideIcons.CHECK_CHECK,
        "FACT_CHECK": shad.LucideIcons.CLIPBOARD_CHECK,
        "FACT_CHECK_ROUNDED": shad.LucideIcons.CLIPBOARD_CHECK,

        # Actions & Editing
        "CLOSE": shad.LucideIcons.X,
        "CLOSE_ROUNDED": shad.LucideIcons.X,
        "CANCEL": shad.LucideIcons.X_CIRCLE,
        "CANCEL_ROUNDED": shad.LucideIcons.X_CIRCLE,
        "ADD": shad.LucideIcons.PLUS,
        "ADD_ROUNDED": shad.LucideIcons.PLUS,
        "ADD_CIRCLE": shad.LucideIcons.PLUS_CIRCLE,
        "ADD_CIRCLE_ROUNDED": shad.LucideIcons.PLUS_CIRCLE,
        "ADD_CIRCLE_OUTLINE": shad.LucideIcons.PLUS_CIRCLE,
        "ADD_CIRCLE_OUTLINE_ROUNDED": shad.LucideIcons.PLUS_CIRCLE,
        "EDIT": shad.LucideIcons.PENCIL,
        "EDIT_ROUNDED": shad.LucideIcons.PENCIL,
        "EDIT_NOTE": shad.LucideIcons.FILE_EDIT,
        "EDIT_NOTE_ROUNDED": shad.LucideIcons.FILE_EDIT,
        "DELETE": shad.LucideIcons.TRASH,
        "DELETE_ROUNDED": shad.LucideIcons.TRASH,
        "DELETE_OUTLINE": shad.LucideIcons.TRASH_2,
        "DELETE_OUTLINE_ROUNDED": shad.LucideIcons.TRASH_2,
        "REFRESH": shad.LucideIcons.REFRESH_CW,
        "REFRESH_ROUNDED": shad.LucideIcons.REFRESH_CW,
        "SEARCH": shad.LucideIcons.SEARCH,
        "SEARCH_ROUNDED": shad.LucideIcons.SEARCH,
        "SEARCH_OFF": shad.LucideIcons.SEARCH_X,
        "SEARCH_OFF_ROUNDED": shad.LucideIcons.SEARCH_X,
        "SHARE": shad.LucideIcons.SHARE_2,
        "SHARE_ROUNDED": shad.LucideIcons.SHARE_2,
        "COPY": shad.LucideIcons.COPY,
        "COPY_ROUNDED": shad.LucideIcons.COPY,
        "CONTENT_COPY": shad.LucideIcons.COPY,
        "CONTENT_COPY_ROUNDED": shad.LucideIcons.COPY,
        "DOWNLOAD": shad.LucideIcons.DOWNLOAD,
        "DOWNLOAD_ROUNDED": shad.LucideIcons.DOWNLOAD,
        "FILE_DOWNLOAD": shad.LucideIcons.DOWNLOAD,
        "FILE_DOWNLOAD_ROUNDED": shad.LucideIcons.DOWNLOAD,
        "UPLOAD": shad.LucideIcons.UPLOAD,
        "UPLOAD_ROUNDED": shad.LucideIcons.UPLOAD,
        "FILE_UPLOAD": shad.LucideIcons.UPLOAD,
        "FILE_UPLOAD_ROUNDED": shad.LucideIcons.UPLOAD,
        "SEND": shad.LucideIcons.SEND,
        "SEND_ROUNDED": shad.LucideIcons.SEND,
        "ATTACH_FILE": shad.LucideIcons.PAPERCLIP,
        "ATTACH_FILE_ROUNDED": shad.LucideIcons.PAPERCLIP,
        "MIC": shad.LucideIcons.MIC,
        "MIC_ROUNDED": shad.LucideIcons.MIC,
        "MIC_OFF": shad.LucideIcons.MIC_OFF,
        "MIC_OFF_ROUNDED": shad.LucideIcons.MIC_OFF,
        "PUSH_PIN": shad.LucideIcons.PIN,
        "PUSH_PIN_ROUNDED": shad.LucideIcons.PIN,
        "POLL": shad.LucideIcons.VOTE,
        "POLL_ROUNDED": shad.LucideIcons.VOTE,
        "CAMPAIGN": shad.LucideIcons.MEGAPHONE,
        "CAMPAIGN_ROUNDED": shad.LucideIcons.MEGAPHONE,
        "OPEN_IN_NEW": shad.LucideIcons.EXTERNAL_LINK,
        "OPEN_IN_NEW_ROUNDED": shad.LucideIcons.EXTERNAL_LINK,
        "LINK": shad.LucideIcons.LINK,
        "LINK_ROUNDED": shad.LucideIcons.LINK,
        "LINK_OFF": shad.LucideIcons.UNLINK,
        "LINK_OFF_ROUNDED": shad.LucideIcons.UNLINK,

        # Navigation & Arrows
        "ARROW_BACK": shad.LucideIcons.ARROW_LEFT,
        "ARROW_BACK_ROUNDED": shad.LucideIcons.ARROW_LEFT,
        "ARROW_FORWARD": shad.LucideIcons.ARROW_RIGHT,
        "ARROW_FORWARD_ROUNDED": shad.LucideIcons.ARROW_RIGHT,
        "ARROW_UPWARD": shad.LucideIcons.ARROW_UP,
        "ARROW_UPWARD_ROUNDED": shad.LucideIcons.ARROW_UP,
        "ARROW_DOWNWARD": shad.LucideIcons.ARROW_DOWN,
        "ARROW_DOWNWARD_ROUNDED": shad.LucideIcons.ARROW_DOWN,
        "CHEVRON_LEFT": shad.LucideIcons.CHEVRON_LEFT,
        "CHEVRON_LEFT_ROUNDED": shad.LucideIcons.CHEVRON_LEFT,
        "CHEVRON_RIGHT": shad.LucideIcons.CHEVRON_RIGHT,
        "CHEVRON_RIGHT_ROUNDED": shad.LucideIcons.CHEVRON_RIGHT,
        "KEYBOARD_ARROW_LEFT": shad.LucideIcons.CHEVRON_LEFT,
        "KEYBOARD_ARROW_LEFT_ROUNDED": shad.LucideIcons.CHEVRON_LEFT,
        "KEYBOARD_ARROW_RIGHT": shad.LucideIcons.CHEVRON_RIGHT,
        "KEYBOARD_ARROW_RIGHT_ROUNDED": shad.LucideIcons.CHEVRON_RIGHT,
        "KEYBOARD_ARROW_DOWN": shad.LucideIcons.CHEVRON_DOWN,
        "KEYBOARD_ARROW_DOWN_ROUNDED": shad.LucideIcons.CHEVRON_DOWN,
        "KEYBOARD_ARROW_UP": shad.LucideIcons.CHEVRON_UP,
        "KEYBOARD_ARROW_UP_ROUNDED": shad.LucideIcons.CHEVRON_UP,
        "ARROW_DROP_DOWN": shad.LucideIcons.CHEVRON_DOWN,
        "ARROW_DROP_DOWN_ROUNDED": shad.LucideIcons.CHEVRON_DOWN,
        "ARROW_DROP_UP": shad.LucideIcons.CHEVRON_UP,
        "ARROW_DROP_UP_ROUNDED": shad.LucideIcons.CHEVRON_UP,
        "NAVIGATE_NEXT": shad.LucideIcons.CHEVRON_RIGHT,
        "NAVIGATE_NEXT_ROUNDED": shad.LucideIcons.CHEVRON_RIGHT,
        "NAVIGATE_BEFORE": shad.LucideIcons.CHEVRON_LEFT,
        "NAVIGATE_BEFORE_ROUNDED": shad.LucideIcons.CHEVRON_LEFT,

        # Learning, Courses & Study
        "SCHOOL": shad.LucideIcons.GRADUATION_CAP,
        "SCHOOL_ROUNDED": shad.LucideIcons.GRADUATION_CAP,
        "AUTO_STORIES": shad.LucideIcons.BOOK_OPEN,
        "AUTO_STORIES_ROUNDED": shad.LucideIcons.BOOK_OPEN,
        "AUTO_AWESOME": shad.LucideIcons.SPARKLES,
        "AUTO_AWESOME_ROUNDED": shad.LucideIcons.SPARKLES,
        "MENU_BOOK": shad.LucideIcons.BOOK_OPEN_CHECK,
        "MENU_BOOK_ROUNDED": shad.LucideIcons.BOOK_OPEN_CHECK,
        "BOOK": shad.LucideIcons.BOOK,
        "BOOK_ROUNDED": shad.LucideIcons.BOOK,
        "PLAYLIST_PLAY": shad.LucideIcons.LIST_MUSIC,
        "PLAYLIST_PLAY_ROUNDED": shad.LucideIcons.LIST_MUSIC,
        "QUIZ": shad.LucideIcons.HELP_CIRCLE,
        "QUIZ_ROUNDED": shad.LucideIcons.HELP_CIRCLE,
        "STYLE": shad.LucideIcons.LAYERS,
        "STYLE_ROUNDED": shad.LucideIcons.LAYERS,
        "PSYCHOLOGY": shad.LucideIcons.BRAIN,
        "PSYCHOLOGY_ROUNDED": shad.LucideIcons.BRAIN,
        "LOCAL_FIRE_DEPARTMENT": shad.LucideIcons.FLAME,
        "LOCAL_FIRE_DEPARTMENT_ROUNDED": shad.LucideIcons.FLAME,
        "BOLT": shad.LucideIcons.ZAP,
        "BOLT_ROUNDED": shad.LucideIcons.ZAP,
        "FLASH_ON": shad.LucideIcons.ZAP,
        "FLASH_ON_ROUNDED": shad.LucideIcons.ZAP,
        "LEADERBOARD": shad.LucideIcons.TROPHY,
        "LEADERBOARD_ROUNDED": shad.LucideIcons.TROPHY,
        "EMOJI_EVENTS": shad.LucideIcons.TROPHY,
        "EMOJI_EVENTS_ROUNDED": shad.LucideIcons.TROPHY,
        "WORKSPACE_PREMIUM": shad.LucideIcons.AWARD,
        "WORKSPACE_PREMIUM_ROUNDED": shad.LucideIcons.AWARD,
        "MILITARY_TECH": shad.LucideIcons.MEDAL,
        "MILITARY_TECH_ROUNDED": shad.LucideIcons.MEDAL,
        "TOKEN": shad.LucideIcons.COINS,
        "TOKEN_ROUNDED": shad.LucideIcons.COINS,
        "ROCKET_LAUNCH": shad.LucideIcons.ROCKET,
        "ROCKET_LAUNCH_ROUNDED": shad.LucideIcons.ROCKET,

        # Media & Playback
        "PLAY_ARROW": shad.LucideIcons.PLAY,
        "PLAY_ARROW_ROUNDED": shad.LucideIcons.PLAY,
        "PLAY_CIRCLE": shad.LucideIcons.PLAY_CIRCLE,
        "PLAY_CIRCLE_ROUNDED": shad.LucideIcons.PLAY_CIRCLE,
        "PLAY_CIRCLE_FILLED": shad.LucideIcons.PLAY_CIRCLE,
        "PLAY_CIRCLE_FILLED_ROUNDED": shad.LucideIcons.PLAY_CIRCLE,
        "PAUSE": shad.LucideIcons.PAUSE,
        "PAUSE_ROUNDED": shad.LucideIcons.PAUSE,
        "STOP": shad.LucideIcons.SQUARE,
        "STOP_ROUNDED": shad.LucideIcons.SQUARE,
        "VOLUME_UP": shad.LucideIcons.VOLUME_2,
        "VOLUME_UP_ROUNDED": shad.LucideIcons.VOLUME_2,
        "VOLUME_OFF": shad.LucideIcons.VOLUME_X,
        "VOLUME_OFF_ROUNDED": shad.LucideIcons.VOLUME_X,

        # Communication & Social
        "HOME": shad.LucideIcons.HOUSE,
        "HOME_ROUNDED": shad.LucideIcons.HOUSE,
        "CHAT_BUBBLE": shad.LucideIcons.MESSAGE_SQUARE,
        "CHAT_BUBBLE_ROUNDED": shad.LucideIcons.MESSAGE_SQUARE,
        "CHAT_BUBBLE_OUTLINE": shad.LucideIcons.MESSAGE_SQUARE,
        "CHAT_BUBBLE_OUTLINE_ROUNDED": shad.LucideIcons.MESSAGE_SQUARE,
        "FORUM": shad.LucideIcons.MESSAGES_SQUARE,
        "FORUM_ROUNDED": shad.LucideIcons.MESSAGES_SQUARE,
        "PERSON": shad.LucideIcons.USER,
        "PERSON_ROUNDED": shad.LucideIcons.USER,
        "PERSON_OUTLINE": shad.LucideIcons.USER,
        "PERSON_OUTLINE_ROUNDED": shad.LucideIcons.USER,
        "PERSON_ADD": shad.LucideIcons.USER_PLUS,
        "PERSON_ADD_ROUNDED": shad.LucideIcons.USER_PLUS,
        "PEOPLE": shad.LucideIcons.USERS,
        "PEOPLE_ROUNDED": shad.LucideIcons.USERS,
        "PEOPLE_ALT": shad.LucideIcons.USERS,
        "PEOPLE_ALT_ROUNDED": shad.LucideIcons.USERS,
        "GROUPS": shad.LucideIcons.USERS,
        "GROUPS_ROUNDED": shad.LucideIcons.USERS,
        "NOTIFICATIONS": shad.LucideIcons.BELL,
        "NOTIFICATIONS_ROUNDED": shad.LucideIcons.BELL,
        "NOTIFICATIONS_ACTIVE": shad.LucideIcons.BELL_RING,
        "NOTIFICATIONS_ACTIVE_ROUNDED": shad.LucideIcons.BELL_RING,
        "NOTIFICATIONS_OFF": shad.LucideIcons.BELL_OFF,
        "NOTIFICATIONS_OFF_ROUNDED": shad.LucideIcons.BELL_OFF,
        "PUBLIC": shad.LucideIcons.GLOBE,
        "PUBLIC_ROUNDED": shad.LucideIcons.GLOBE,
        "BUSINESS": shad.LucideIcons.BUILDING_2,
        "BUSINESS_ROUNDED": shad.LucideIcons.BUILDING_2,
        "CORPORATE_FARE": shad.LucideIcons.BUILDING,
        "CORPORATE_FARE_ROUNDED": shad.LucideIcons.BUILDING,
        "STOREFRONT": shad.LucideIcons.STORE,
        "STOREFRONT_ROUNDED": shad.LucideIcons.STORE,
        "STORE": shad.LucideIcons.STORE,
        "STORE_ROUNDED": shad.LucideIcons.STORE,

        # Alerts, Errors & Warnings
        "ERROR": shad.LucideIcons.ALERT_OCTAGON,
        "ERROR_ROUNDED": shad.LucideIcons.ALERT_OCTAGON,
        "ERROR_OUTLINE": shad.LucideIcons.ALERT_CIRCLE,
        "ERROR_OUTLINE_ROUNDED": shad.LucideIcons.ALERT_CIRCLE,
        "WARNING": shad.LucideIcons.ALERT_TRIANGLE,
        "WARNING_ROUNDED": shad.LucideIcons.ALERT_TRIANGLE,
        "WARNING_AMBER": shad.LucideIcons.ALERT_TRIANGLE,
        "WARNING_AMBER_ROUNDED": shad.LucideIcons.ALERT_TRIANGLE,
        "INFO": shad.LucideIcons.INFO,
        "INFO_ROUNDED": shad.LucideIcons.INFO,
        "INFO_OUTLINE": shad.LucideIcons.INFO,
        "INFO_OUTLINE_ROUNDED": shad.LucideIcons.INFO,
        "HELP": shad.LucideIcons.HELP_CIRCLE,
        "HELP_ROUNDED": shad.LucideIcons.HELP_CIRCLE,
        "HELP_OUTLINE": shad.LucideIcons.HELP_CIRCLE,
        "HELP_OUTLINE_ROUNDED": shad.LucideIcons.HELP_CIRCLE,

        # System, Security & Time
        "LOCK": shad.LucideIcons.LOCK,
        "LOCK_ROUNDED": shad.LucideIcons.LOCK,
        "LOCK_OUTLINE": shad.LucideIcons.LOCK,
        "LOCK_OUTLINE_ROUNDED": shad.LucideIcons.LOCK,
        "LOCK_OPEN": shad.LucideIcons.UNLOCK,
        "LOCK_OPEN_ROUNDED": shad.LucideIcons.UNLOCK,
        "VPN_KEY": shad.LucideIcons.KEY,
        "VPN_KEY_ROUNDED": shad.LucideIcons.KEY,
        "SECURITY": shad.LucideIcons.SHIELD,
        "SECURITY_ROUNDED": shad.LucideIcons.SHIELD,
        "TIMER": shad.LucideIcons.TIMER,
        "TIMER_ROUNDED": shad.LucideIcons.TIMER,
        "TIMER_OUTLINED": shad.LucideIcons.TIMER,
        "SCHEDULE": shad.LucideIcons.CLOCK,
        "SCHEDULE_ROUNDED": shad.LucideIcons.CLOCK,
        "ACCESS_TIME": shad.LucideIcons.CLOCK,
        "ACCESS_TIME_ROUNDED": shad.LucideIcons.CLOCK,
        "CALENDAR_TODAY": shad.LucideIcons.CALENDAR,
        "CALENDAR_TODAY_ROUNDED": shad.LucideIcons.CALENDAR,
        "DARK_MODE": shad.LucideIcons.MOON,
        "DARK_MODE_ROUNDED": shad.LucideIcons.MOON,
        "LIGHT_MODE": shad.LucideIcons.SUN,
        "LIGHT_MODE_ROUNDED": shad.LucideIcons.SUN,
        "SETTINGS": shad.LucideIcons.SETTINGS,
        "SETTINGS_ROUNDED": shad.LucideIcons.SETTINGS,
        "TUNE": shad.LucideIcons.SLIDERS,
        "TUNE_ROUNDED": shad.LucideIcons.SLIDERS,
        "FILTER_LIST": shad.LucideIcons.LIST_FILTER,
        "FILTER_LIST_ROUNDED": shad.LucideIcons.LIST_FILTER,
        "MORE_VERT": shad.LucideIcons.MORE_VERTICAL,
        "MORE_VERT_ROUNDED": shad.LucideIcons.MORE_VERTICAL,
        "MORE_HORIZ": shad.LucideIcons.MORE_HORIZONTAL,
        "MORE_HORIZ_ROUNDED": shad.LucideIcons.MORE_HORIZONTAL,
        "LOGOUT": shad.LucideIcons.LOG_OUT,
        "LOGOUT_ROUNDED": shad.LucideIcons.LOG_OUT,
        "LOGIN": shad.LucideIcons.LOG_IN,
        "LOGIN_ROUNDED": shad.LucideIcons.LOG_IN,
        "WIFI": shad.LucideIcons.WIFI,
        "WIFI_ROUNDED": shad.LucideIcons.WIFI,
        "WIFI_OFF": shad.LucideIcons.WIFI_OFF,
        "WIFI_OFF_ROUNDED": shad.LucideIcons.WIFI_OFF,
        "VISIBILITY": shad.LucideIcons.EYE,
        "VISIBILITY_ROUNDED": shad.LucideIcons.EYE,
        "VISIBILITY_OFF": shad.LucideIcons.EYE_OFF,
        "VISIBILITY_OFF_ROUNDED": shad.LucideIcons.EYE_OFF,
    }
else:
    LUCIDE_ICON_MAP = {}


_BRIDGE_INSTALLED = False

def enable_lucide_icon_bridge():
    """
    Hooks into `ft.Icons.__class__.__getattr__` so that ANY legacy Material icon reference
    (e.g., ft.Icons.CHECK_CIRCLE_ROUNDED, ft.Icons.SEARCH_ROUNDED, ft.Icons.AUTO_AWESOME_ROUNDED)
    automatically resolves to its crisp stroke-based Lucide equivalent across the entire app.
    Unmapped icons gracefully fall back to the standard Flet Material font.
    """
    global _BRIDGE_INSTALLED
    if _BRIDGE_INSTALLED or not HAS_SHADCN or not shad:
        return

    orig_getattr = ft.Icons.__class__.__getattr__
    lucide_dir = set(dir(shad.LucideIcons))

    def _patched_getattr(self, name: str):
        clean_name = name.upper()
        # 1. Exact match in manual mapping table
        if clean_name in LUCIDE_ICON_MAP:
            return LUCIDE_ICON_MAP[clean_name]

        # 2. Normalized match (strip suffix variations)
        base = (
            clean_name.replace("_ROUNDED", "")
            .replace("_OUTLINED", "")
            .replace("_OUTLINE", "")
            .replace("_SHARP", "")
        )
        if base in LUCIDE_ICON_MAP:
            return LUCIDE_ICON_MAP[base]

        # 3. Direct match in Lucide enum
        if base in lucide_dir:
            return getattr(shad.LucideIcons, base)

        # 4. Unbroken fallback to Material Icons
        return orig_getattr(self, name)

    ft.Icons.__class__.__getattr__ = _patched_getattr
    _BRIDGE_INSTALLED = True


# ─────────────────────────────────────────────────────────────────────────────
# 2. MULTI-MODE SHADCN THEME PALETTES
# ─────────────────────────────────────────────────────────────────────────────
THEME_PALETTES = {
    # ── LIGHT THEMES ─────────────────────────────────────────────
    "light": {
        "key": "light",
        "name": "Classic Light",
        "icon": shad.LucideIcons.SUN if HAS_SHADCN else ft.Icons.LIGHT_MODE_ROUNDED,
        "is_dark": False,
        "theme_mode": ft.ThemeMode.LIGHT,
        "shad_scheme": getattr(shad.ColorScheme, "GREEN", "green") if HAS_SHADCN else "green",
        "primary": "#035800",
        "secondary": "#37BF14",
        "surface": "#FAFAFA",
        "card_bg": "#FFFFFF",
        "on_surface": "#1A1A1A",
        "on_primary": "#FAFAFAF8",
        "outline": "#E0E0E0",
        "scrim": "#ECE5DD",
        "tertiary": "#E6FAE5",
        "surface_container": "#F3F4F6",
        "surface_container_highest": "#E5E7EB",
        "muted": "#757575",
        "border_color": "#E5E7EB",
        "capsule_bg": "#FFFFFF",
    },
    "sepia": {
        "key": "sepia",
        "name": "Warm Paper",
        "icon": shad.LucideIcons.BOOK_OPEN if HAS_SHADCN else ft.Icons.MENU_BOOK_ROUNDED,
        "is_dark": False,
        "theme_mode": ft.ThemeMode.LIGHT,
        "shad_scheme": getattr(shad.ColorScheme, "GREEN", "green") if HAS_SHADCN else "green",
        "primary": "#1B4332",
        "secondary": "#2D6A4F",
        "surface": "#F8F5EE",
        "card_bg": "#FFFDF9",
        "on_surface": "#2A2421",
        "on_primary": "#FFFFFF",
        "outline": "#E6DEC8",
        "scrim": "#D8CFBA",
        "tertiary": "#EDE6D6",
        "surface_container": "#F4EFE6",
        "surface_container_highest": "#EADFCB",
        "muted": "#6E6359",
        "border_color": "#E6DEC8",
        "capsule_bg": "#FFFDF9",
    },

    # ── DARK THEMES ──────────────────────────────────────────────
    "dark": {
        "key": "dark",
        "name": "Classic Dark",
        "icon": shad.LucideIcons.MOON if HAS_SHADCN else ft.Icons.DARK_MODE_ROUNDED,
        "is_dark": True,
        "theme_mode": ft.ThemeMode.DARK,
        "shad_scheme": getattr(shad.ColorScheme, "GREEN", "green") if HAS_SHADCN else "green",
        "primary": "#4CAF50",
        "secondary": "#37BF14",
        "surface": "#121212",
        "card_bg": "#1E1E1E",
        "on_surface": "#E8E8E8",
        "on_primary": "#1A1717",
        "outline": "#2C2C2C",
        "scrim": "#302D2D",
        "tertiary": "#212121",
        "surface_container": "#1F2430",
        "surface_container_highest": "#2B3142",
        "muted": "#9E9E9E",
        "border_color": "#2C2C2C",
        "capsule_bg": "#1E1E1E",
    },
    "midnight": {
        "key": "midnight",
        "name": "Midnight OLED",
        "icon": shad.LucideIcons.SPARKLES if HAS_SHADCN else ft.Icons.AUTO_AWESOME_ROUNDED,
        "is_dark": True,
        "theme_mode": ft.ThemeMode.DARK,
        "shad_scheme": getattr(shad.ColorScheme, "GREEN", "green") if HAS_SHADCN else "green",
        "primary": "#00E676",
        "secondary": "#047857",
        "surface": "#000000",
        "card_bg": "#0A0A0A",
        "on_surface": "#FFFFFF",
        "on_primary": "#000000",
        "outline": "#1F1F1F",
        "scrim": "#141414",
        "tertiary": "#0F0F0F",
        "surface_container": "#0D0D0D",
        "surface_container_highest": "#1A1A1A",
        "muted": "#888888",
        "border_color": "#1A1A1A",
        "capsule_bg": "#0A0A0A",
    },
    "slate": {
        "key": "slate",
        "name": "Nordic Slate",
        "icon": shad.LucideIcons.COMPASS if HAS_SHADCN else ft.Icons.EXPLORE_ROUNDED,
        "is_dark": True,
        "theme_mode": ft.ThemeMode.DARK,
        "shad_scheme": getattr(shad.ColorScheme, "SLATE", "slate") if HAS_SHADCN else "slate",
        "primary": "#10B981",
        "secondary": "#6366F1",
        "surface": "#0B0F19",
        "card_bg": "#111827",
        "on_surface": "#F3F4F6",
        "on_primary": "#0B0F19",
        "outline": "#1F2937",
        "scrim": "#151C2E",
        "tertiary": "#1E293B",
        "surface_container": "#131D31",
        "surface_container_highest": "#1F2937",
        "muted": "#9CA3AF",
        "border_color": "#374151",
        "capsule_bg": "#111827",
    },
}

DEFAULT_THEME_KEY = "dark"


def get_theme_palette(key: Optional[str] = None) -> dict:
    """Returns the full palette token dictionary for the given theme key."""
    if not key or key not in THEME_PALETTES:
        return THEME_PALETTES[DEFAULT_THEME_KEY]
    return THEME_PALETTES[key]


def build_flet_theme(palette: dict, font_family: str = "inter") -> ft.Theme:
    """
    Constructs a native Flet ft.Theme configured with an ft.ColorScheme that exactly
    binds semantic color tokens (surface, primary, on_surface, outline, secondary, etc.)
    to the active Nu-Age theme preset.
    """
    surface = palette["surface"]
    card_bg = palette.get("card_bg", surface)
    primary = palette["primary"]
    secondary = palette.get("secondary", primary)
    on_surface = palette["on_surface"]
    on_primary = palette["on_primary"]
    outline = palette.get("outline", "#2C2C2C")
    scrim = palette.get("scrim", surface)
    tertiary = palette.get("tertiary", card_bg)
    surface_container = palette.get("surface_container", card_bg)
    surface_container_highest = palette.get("surface_container_highest", card_bg)

    return ft.Theme(
        font_family=font_family,
        color_scheme=ft.ColorScheme(
            primary=primary,
            secondary=secondary,
            surface=surface,
            on_surface=on_surface,
            on_primary=on_primary,
            on_secondary="#FFFFFF",
            outline=outline,
            scrim=scrim,
            tertiary=tertiary,
            surface_container=surface_container,
            surface_container_high=surface_container,
            surface_container_highest=surface_container_highest,
            surface_container_low=surface,
            surface_container_lowest=surface,
            surface_dim=surface,
            surface_bright=card_bg,
        ),
        page_transitions=ft.PageTransitionsTheme(
            android=ft.PageTransitionTheme.CUPERTINO,
            ios="cupertino",
        ),
    )


def get_dynamic_radius(page: Optional[ft.Page] = None, base: int = 10) -> int:
    """
    Calculates responsive dynamic border radius:
    - Mobile screen (< 600px): tighter 8px to maximize viewport real estate.
    - Tablet / Desktop: modern 12px for softer elevated cards.
    """
    if not page or not hasattr(page, "width") or not page.width:
        return base
    w = page.width
    if w < 600:
        return 8
    elif w < 960:
        return 10
    return 12


def build_shad_theme(
    content: ft.Control,
    page: Optional[ft.Page] = None,
    theme_key: Optional[str] = None,
    radius: Optional[int | float] = None,
) -> ft.Control:
    """
    Wraps content in a Shadcn UI Theme configured for the active Nu-Age theme preset.
    """
    if not HAS_SHADCN or shad is None:
        return content

    if not theme_key and page and hasattr(page, "data") and isinstance(page.data, dict):
        theme_key = page.data.get("current_theme_key")

    palette = get_theme_palette(theme_key)
    dyn_radius = radius if radius is not None else get_dynamic_radius(page)
    scheme = palette.get("shad_scheme", shad.ColorScheme.GREEN)

    brightness = ft.Brightness.DARK if palette["is_dark"] else ft.Brightness.LIGHT

    try:
        return shad.Theme(
            color_scheme=scheme,
            brightness=brightness,
            radius=dyn_radius,
            content=content,
            expand=True if getattr(content, "expand", False) else None,
        )
    except Exception as ex:
        print(f"[ThemeBridge] Warning wrapping shad.Theme: {ex}")
        return content


def build_shad_badge(
    text: str,
    variant: str = "secondary",
    icon: Any = None,
    on_click: Any = None,
) -> ft.Control:
    """Creates a modern Shadcn Badge control."""
    if not HAS_SHADCN or shad is None:
        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
            border_radius=8,
            bgcolor=ft.Colors.PRIMARY_CONTAINER if variant == "primary" else ft.Colors.SURFACE_CONTAINER_HIGHEST,
            content=ft.Row(
                [
                    ft.Icon(icon, size=12) if icon else ft.Container(),
                    ft.Text(text, size=11, weight=ft.FontWeight.W_600),
                ],
                tight=True,
                spacing=4,
            ),
        )

    var_map = {
        "primary": shad.BadgeVariant.PRIMARY,
        "secondary": shad.BadgeVariant.SECONDARY,
        "outline": shad.BadgeVariant.OUTLINE,
        "destructive": shad.BadgeVariant.DESTRUCTIVE,
    }
    target_var = var_map.get(variant.lower(), shad.BadgeVariant.SECONDARY)

    badge_content: ft.Control | str = text
    if icon:
        badge_content = ft.Row(
            [
                ft.Icon(icon, size=12),
                ft.Text(text, size=11, weight=ft.FontWeight.W_600),
            ],
            tight=True,
            spacing=4,
        )

    return shad.Badge(
        content=badge_content,
        variant=target_var,
        on_click=on_click,
    )


def build_theme_switcher_button(
    page: ft.Page,
    on_theme_changed: Optional[Any] = None,
    button_height: int = 30,
) -> ft.Control:
    """
    Builds a theme chip button that displays the active theme preset
    and opens a visual selection modal with live swatches and previews.
    """
    current_key = page.data.get("current_theme_key", DEFAULT_THEME_KEY) if hasattr(page, "data") and isinstance(page.data, dict) else DEFAULT_THEME_KEY
    cur_p = get_theme_palette(current_key)

    label_text = ft.Text(
        f"Theme: {cur_p['name'].split()[0]}",
        size=11,
        weight=ft.FontWeight.W_600,
        color=ft.Colors.PRIMARY,
    )

    def open_theme_modal(e=None):
        cur_active = page.data.get("current_theme_key", DEFAULT_THEME_KEY) if hasattr(page, "data") and isinstance(page.data, dict) else DEFAULT_THEME_KEY
        cur_p = get_theme_palette(cur_active)
        is_dark = cur_p["is_dark"]
        card_bg = cur_p["card_bg"]
        border_clr = cur_p["outline"]
        text_primary = cur_p["on_surface"]
        text_muted = cur_p["muted"]

        dlg = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=16),
            bgcolor=card_bg,
            title=ft.Row(
                [
                    ft.Container(
                        width=34,
                        height=34,
                        border_radius=10,
                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Icon(LucideIcons.SPARKLES if HAS_SHADCN else ft.Icons.PALETTE_ROUNDED, color=ft.Colors.PRIMARY, size=18),
                    ),
                    ft.Column(
                        [
                            ft.Text("Theme & Visual Style", weight=ft.FontWeight.BOLD, size=15, color=text_primary),
                            ft.Text("Choose your preferred aesthetic workspace palette", size=10.5, color=text_muted),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                ],
                spacing=10,
            ),
        )

        def _select_theme(target_key: str):
            def _handler(ev):
                dlg.open = False
                set_fn = page.data.get("set_app_theme") if isinstance(page.data, dict) else None
                if callable(set_fn):
                    page.run_task(set_fn, target_key)
                if callable(on_theme_changed):
                    on_theme_changed(target_key)
                label_text.value = f"Theme: {THEME_PALETTES[target_key]['name'].split()[0]}"
                page.update()
            return _handler

        theme_cards = []
        for key, p in THEME_PALETTES.items():
            is_selected = (key == cur_active)
            swatch_surface = p["surface"]
            swatch_primary = p["primary"]
            swatch_sec = p["secondary"]

            swatch_row = ft.Row(
                [
                    ft.Container(width=14, height=14, border_radius=7, bgcolor=swatch_surface, border=ft.Border.all(1, ft.Colors.GREY_500)),
                    ft.Container(width=14, height=14, border_radius=7, bgcolor=swatch_primary),
                    ft.Container(width=14, height=14, border_radius=7, bgcolor=swatch_sec),
                ],
                spacing=4,
                tight=True,
            )

            card_border = ft.Border.all(1.5, ft.Colors.PRIMARY if is_selected else border_clr)
            card_bg_tile = ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY) if is_selected else (ft.Colors.with_opacity(0.03, ft.Colors.WHITE) if is_dark else ft.Colors.with_opacity(0.02, ft.Colors.BLACK))

            tile = ft.Container(
                padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                border_radius=12,
                border=card_border,
                bgcolor=card_bg_tile,
                ink=True,
                on_click=_select_theme(key),
                content=ft.Row(
                    [
                        ft.Icon(p["icon"], size=18, color=ft.Colors.PRIMARY if is_selected else text_muted),
                        ft.Column(
                            [
                                ft.Row(
                                    [
                                        ft.Text(p["name"], size=13, weight=ft.FontWeight.W_700 if is_selected else ft.FontWeight.W_600, color=text_primary),
                                        build_shad_badge("ACTIVE", variant="primary") if is_selected else ft.Container(),
                                    ],
                                    spacing=6,
                                    tight=True,
                                ),
                                ft.Text(
                                    "Pitch Black #000000 · AMOLED" if key == "midnight"
                                    else ("Cool Slate #0B0F19 · Minimalist" if key == "slate"
                                    else ("Matte Eggshell #F8F5EE · Reading" if key == "sepia"
                                    else ("Crisp White #FAFAFA · Standard" if key == "light"
                                    else "Neutral Charcoal #121212 · Standard"))),
                                    size=10,
                                    color=text_muted,
                                ),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                        swatch_row,
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
            theme_cards.append(tile)

        dlg.content = ft.Container(
            width=380,
            content=ft.Column(theme_cards, spacing=8, tight=True),
        )
        dlg.actions = [
            ft.TextButton(
                "Close",
                on_click=lambda _: (_close_modal(dlg), page.update()),
                style=ft.ButtonStyle(color=text_muted),
            )
        ]

        def _close_modal(d):
            d.open = False

        page.show_dialog(dlg)
        page.update()

    btn = ft.Container(
        height=button_height,
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
        border_radius=8,
        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.30, ft.Colors.PRIMARY)),
        ink=True,
        on_click=open_theme_modal,
        tooltip="Change Theme Preset (Light, Paper, Dark, OLED, Slate)",
        content=ft.Row(
            [
                ft.Icon(LucideIcons.PALETTE if HAS_SHADCN and hasattr(LucideIcons, "PALETTE") else LucideIcons.SPARKLES, size=13, color=ft.Colors.PRIMARY),
                label_text,
            ],
            spacing=5,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )
    return btn
