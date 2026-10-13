import flet as ft
from src.components.notifications_drawer import NotificationManager


def _get_nav_theme(page: ft.Page, is_dark: bool = None) -> dict:
    if is_dark is None:
        is_dark = (page.theme_mode != ft.ThemeMode.LIGHT) if hasattr(page, "theme_mode") and page.theme_mode else True

    # Mode-cognizant design aligning with Nu-Age DARK_THEME / LIGHT_THEME in main.py
    if is_dark:
        primary = "#4CAF50"       # Official Nu-Age dark primary green
        surface = "#222222"       # Nu-Age dark surface
        outline = "#2C2C2C"       # Nu-Age dark outline / border
        on_surface_muted = "#9E9E9E"

        return {
            "is_dark": True,
            "capsule_bg": surface,
            "capsule_border": ft.Border.all(1, outline),
            "capsule_shadow": ft.BoxShadow(
                blur_radius=16,
                color=ft.Colors.with_opacity(0.40, ft.Colors.BLACK),
                offset=ft.Offset(0, 4),
            ),
            "active_pill_bg": ft.Colors.with_opacity(0.12, primary),
            "active_pill_border": ft.Border.all(1, ft.Colors.with_opacity(0.38, primary)),
            "active_color": ft.Colors.WHITE,
            "inactive_color": on_surface_muted,
            "inactive_hover": "#FFFFFF",
            "hover_bg": ft.Colors.with_opacity(0.18, ft.Colors.WHITE),
        }
    else:
        primary = "#035800"       # Official Nu-Age light primary green
        surface = "#FFFFFF"       # Crisp, elevated white surface against the light background
        outline = "#E0E0E0"       # Nu-Age light outline / border
        on_surface_muted = "#757575"

        return {
            "is_dark": False,
            "capsule_bg": surface,
            "capsule_border": ft.Border.all(1, outline),
            "capsule_shadow": ft.BoxShadow(
                blur_radius=14,
                color=ft.Colors.with_opacity(0.10, ft.Colors.BLACK),
                offset=ft.Offset(0, 4),
            ),
            "active_pill_bg": ft.Colors.with_opacity(0.12, primary),
            "active_pill_border": ft.Border.all(1, ft.Colors.with_opacity(0.28, primary)),
            "active_color": primary,
            "inactive_color": on_surface_muted,
            "inactive_hover": "#1A1A1A",
            "hover_bg": ft.Colors.with_opacity(0.06, ft.Colors.BLACK),
        }


class BottomAppBarThemeManager:
    """Manages active BottomAppBar instances and dispatches instantaneous theme updates
    across views whenever dark/light mode toggles anywhere in the app.
    """
    _active_bars = []

    @classmethod
    def register(cls, bar):
        cls._active_bars = [b for b in cls._active_bars if getattr(b, "bar", None) is not None]
        if bar not in cls._active_bars:
            cls._active_bars.append(bar)

    @classmethod
    def unregister(cls, bar):
        if bar in cls._active_bars:
            cls._active_bars.remove(bar)

    @classmethod
    def notify_theme_changed(cls, is_dark: bool = None):
        """Immediately updates all registered bottom app bars to reflect the new theme."""
        stale = []
        for bar in list(cls._active_bars):
            try:
                bar.update_theme(is_dark=is_dark)
            except Exception:
                stale.append(bar)
        for s in stale:
            if s in cls._active_bars:
                cls._active_bars.remove(s)


class NavPillItem:
    """An individual navigation item that expands into an illuminated pill when active,
    and collapses to icon-only when inactive. Optimally sized for mobile & desktop viewports.
    """

    def __init__(self, page: ft.Page, icon_name, route: str, label: str, on_navigate, is_rotated: bool = False, has_badge: bool = False):
        self.page = page
        self.icon_name = icon_name
        self.route = route
        self.label = label
        self.on_navigate = on_navigate
        self.is_rotated = is_rotated
        self.has_badge = has_badge
        self.is_active = False
        self._unread_count = 0

        is_desktop = (page.width >= 800) if hasattr(page, "width") and page.width else False

        self.icon_ctrl = ft.Icon(
            icon_name,
            size=20 if is_desktop else 19,
            rotate=ft.Rotate(angle=-0.5) if is_rotated else None,
        )
        self.label_ctrl = ft.Text(
            label,
            size=12 if is_desktop else 11,
            weight=ft.FontWeight.BOLD,
            no_wrap=True,
            visible=False,
        )
        self.badge_text = ft.Text(
            "",
            size=8 if not is_desktop else 9,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.WHITE,
        )
        self.badge_container = ft.Container(
            content=self.badge_text,
            bgcolor=ft.Colors.RED_600,
            border_radius=8,
            padding=ft.Padding.symmetric(horizontal=3, vertical=1) if not is_desktop else ft.Padding.symmetric(horizontal=4, vertical=1),
            visible=False,
        )

        self.row = ft.Row(
            controls=[self.icon_ctrl, self.label_ctrl, self.badge_container],
            spacing=4 if is_desktop else 3,
            tight=True,
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        h_pad = 8 if is_desktop else 5
        v_pad = 6 if is_desktop else 5

        self.container = ft.Container(
            content=self.row,
            border_radius=20,
            padding=ft.Padding.symmetric(horizontal=h_pad, vertical=v_pad),
            animate=ft.Animation(260, ft.AnimationCurve.EASE_OUT_CUBIC),
            animate_size=ft.Animation(260, ft.AnimationCurve.EASE_OUT_CUBIC),
            ink=True,
            tooltip=f"{label} ({route})",
            on_click=self._handle_click,
            on_hover=self._handle_hover,
        )

    def _handle_click(self, e):
        if self.on_navigate:
            self.on_navigate(self.route)

    def _handle_hover(self, e):
        if not self.is_active:
            theme = _get_nav_theme(self.page)
            is_hovered = (e.data == "true")
            self.icon_ctrl.color = theme["inactive_hover"] if is_hovered else theme["inactive_color"]
            self.container.bgcolor = theme["hover_bg"] if is_hovered else ft.Colors.TRANSPARENT
            try:
                self.container.update()
            except Exception:
                pass

    def update_badge(self, count: int):
        self._unread_count = count
        if self.has_badge:
            self.badge_text.value = str(count) if count <= 99 else "99+"
            self.badge_container.visible = (count > 0)

    def set_active(self, active: bool, theme: dict, is_desktop: bool = False):
        self.is_active = active
        self.label_ctrl.visible = active
        self.icon_ctrl.size = 20 if is_desktop else 19
        self.label_ctrl.size = 12 if is_desktop else 11
        self.row.spacing = 4 if is_desktop else 3

        self.icon_ctrl.color = theme["active_color"] if active else theme["inactive_color"]
        self.label_ctrl.color = theme["active_color"]
        self.container.bgcolor = theme["active_pill_bg"] if active else ft.Colors.TRANSPARENT
        self.container.border = theme["active_pill_border"] if active else None

        if active:
            h_pad = 12 if is_desktop else 8
            v_pad = 6 if is_desktop else 5
        else:
            h_pad = 8 if is_desktop else 5
            v_pad = 6 if is_desktop else 5

        self.container.padding = ft.Padding.symmetric(horizontal=h_pad, vertical=v_pad)


class PersistentBottomAppBar:
    """Persistent, stateful bottom navigation bar redesigned as a floating island capsule
    with smooth animated pill expansion for the active tab. Optimally responsive on both mobile and desktop.
    """

    def __init__(self, page: ft.Page):
        self.page = page
        self.current_route = page.route or "/dashboard"
        self.items: list[NavPillItem] = []
        self._nav_row = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[],
        )

        theme = _get_nav_theme(self.page)
        is_desktop = (page.width >= 800) if hasattr(page, "width") and page.width else False

        # Register instance for immediate global theme switching
        BottomAppBarThemeManager.register(self)

        self._capsule = ft.Container(
            content=self._nav_row,
            height=58 if is_desktop else 52,
            width=(560 if len(self.items) >= 6 else 490) if is_desktop else None,
            bgcolor=theme["capsule_bg"],
            border=theme["capsule_border"],
            border_radius=29 if is_desktop else 26,
            shadow=theme["capsule_shadow"],
            padding=ft.Padding.symmetric(horizontal=18, vertical=4) if is_desktop else ft.Padding.symmetric(horizontal=10, vertical=2),
            alignment=ft.Alignment.CENTER,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )

        self.bar = ft.BottomAppBar(
            bgcolor=ft.Colors.TRANSPARENT,
            elevation=0,
            height=76 if is_desktop else 68,
            padding=ft.Padding.only(left=16, right=16, bottom=12) if is_desktop else ft.Padding.only(left=8, right=8, bottom=8),
            content=ft.Container(
                alignment=ft.Alignment.CENTER,
                content=self._capsule,
            ),
        )

        # Wire responsive resize handler safely without clobbering existing handlers
        try:
            existing_on_resize = getattr(self.page, "on_resize", None)
            def _chained_resize(e):
                if callable(existing_on_resize):
                    try:
                        existing_on_resize(e)
                    except Exception:
                        pass
                self.responsive_update()
            self.page.on_resize = _chained_resize
        except Exception:
            pass

        self.refresh()
        try:
            NotificationManager.subscribe(self._update_unread_badge)
        except Exception:
            pass

    def _is_match(self, item_route: str, route: str) -> bool:
        if not route:
            return item_route == "/dashboard"
        clean = route.split("?")[0]
        if item_route == "/dashboard":
            return clean == "/dashboard"
        if item_route == "/courses":
            return clean == "/courses" or (clean.startswith("/courses/") and not clean.endswith("/view") and not clean.endswith("/offline"))
        if item_route == "/organisations":
            return clean == "/organisations" or clean.startswith("/organisations/")
        if item_route == "/nu-chat":
            return clean == "/nu-chat"
        if clean == "/notifications":
            return item_route == "/notifications"
        if item_route == "/profile":
            return clean in ("/profile", "/edit-profile")
        return clean == item_route

    def _update_unread_badge(self):
        try:
            count = NotificationManager.get_unread_count()
            for item in self.items:
                if item.has_badge:
                    item.update_badge(count)
            self.bar.update()
        except Exception:
            pass

    def _on_item_navigate(self, route: str):
        self.set_active_route(route)
        self.page.go(route)

    def refresh(self):
        user_data = (self.page.session.store.get("current_user") or {}) if hasattr(self.page, "session") and hasattr(self.page.session, "store") else {}
        role = str(user_data.get("role", "STUDENT")).upper()
        self.items.clear()

        nav_specs = [
            (ft.Icons.HOME_ROUNDED, "/dashboard", "Home", False, False),
            (ft.Icons.CHAT_BUBBLE_ROUNDED, "/nu-chat", "Chat", False, False),
            (ft.Icons.SCHOOL_ROUNDED, "/courses", "Learn", False, False),
            (ft.Icons.NOTIFICATIONS_ROUNDED, "/notifications", "Alerts", False, True),
        ]

        if role in ["ADMIN", "TEACHER", "OWNER", "SUPERADMIN"]:
            nav_specs.append(
                (ft.Icons.CORPORATE_FARE_ROUNDED, "/organisations", "Orgs", False, False)
            )

        nav_specs.append(
            (ft.Icons.PERSON_ROUNDED, "/profile", "Profile", False, False)
        )

        theme = _get_nav_theme(self.page)
        row_controls = []
        for icon_name, route, label, is_rot, has_bdg in nav_specs:
            item = NavPillItem(
                self.page,
                icon_name,
                route,
                label,
                on_navigate=self._on_item_navigate,
                is_rotated=is_rot,
                has_badge=has_bdg,
            )
            self.items.append(item)
            row_controls.append(item.container)

        self._nav_row.controls = row_controls

        # Sync badge count
        try:
            count = NotificationManager.get_unread_count()
            for itm in self.items:
                if itm.has_badge:
                    itm.update_badge(count)
        except Exception:
            pass

        if self.current_route:
            self.set_active_route(self.current_route)
        try:
            self.bar.update()
        except Exception:
            pass

    def responsive_update(self):
        """Adjusts capsule width and tab dimensions when the viewport resizes."""
        is_desktop = (self.page.width >= 800) if hasattr(self.page, "width") and self.page.width else False
        num_items = len(self.items)

        self._capsule.width = (560 if num_items >= 6 else 490) if is_desktop else None
        self._capsule.height = 58 if is_desktop else 52
        self._capsule.border_radius = 29 if is_desktop else 26
        self._capsule.padding = ft.Padding.symmetric(horizontal=18, vertical=4) if is_desktop else ft.Padding.symmetric(horizontal=10, vertical=2)

        self.bar.height = 76 if is_desktop else 68
        self.bar.padding = ft.Padding.only(left=16, right=16, bottom=12) if is_desktop else ft.Padding.only(left=8, right=8, bottom=8)

        theme = _get_nav_theme(self.page)
        for item in self.items:
            active = self._is_match(item.route, self.current_route)
            item.set_active(active, theme, is_desktop=is_desktop)

        try:
            self.bar.update()
        except Exception:
            pass

    def update_theme(self, is_dark: bool = None):
        """Immediately re-renders bottom appbar colors when dark/light mode toggles."""
        theme = _get_nav_theme(self.page, is_dark=is_dark)
        is_desktop = (self.page.width >= 800) if hasattr(self.page, "width") and self.page.width else False

        self._capsule.bgcolor = theme["capsule_bg"]
        self._capsule.border = theme["capsule_border"]
        self._capsule.shadow = theme["capsule_shadow"]

        for item in self.items:
            active = self._is_match(item.route, self.current_route)
            item.set_active(active, theme, is_desktop=is_desktop)

        try:
            self.bar.update()
        except Exception:
            pass

    def set_active_route(self, new_route: str):
        self.current_route = new_route
        theme = _get_nav_theme(self.page)
        is_desktop = (self.page.width >= 800) if hasattr(self.page, "width") and self.page.width else False
        num_items = len(self.items)

        # Dynamic desktop width: 560px for 6 items (org account), 490px for 5 items
        self._capsule.width = (560 if num_items >= 6 else 490) if is_desktop else None
        self._capsule.height = 58 if is_desktop else 52
        self._capsule.border_radius = 29 if is_desktop else 26
        self._capsule.padding = ft.Padding.symmetric(horizontal=18, vertical=4) if is_desktop else ft.Padding.symmetric(horizontal=10, vertical=2)
        self._capsule.bgcolor = theme["capsule_bg"]
        self._capsule.border = theme["capsule_border"]
        self._capsule.shadow = theme["capsule_shadow"]

        self.bar.height = 76 if is_desktop else 68
        self.bar.padding = ft.Padding.only(left=16, right=16, bottom=12) if is_desktop else ft.Padding.only(left=8, right=8, bottom=8)

        for item in self.items:
            active = self._is_match(item.route, new_route)
            item.set_active(active, theme, is_desktop=is_desktop)

        try:
            self.bar.update()
        except Exception:
            pass


def get_bottom_appbar(page: ft.Page) -> ft.BottomAppBar:
    """Backward-compatible helper that constructs a BottomAppBar instance."""
    return PersistentBottomAppBar(page).bar