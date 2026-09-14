import flet as ft


class PersistentBottomAppBar:
    """Persistent, stateful bottom navigation bar that updates active indicators in-place

    without re-creating controls or triggering Scaffold transitions.
    """

    def __init__(self, page: ft.Page):
        self.page = page
        self.current_route = page.route or "/dashboard"
        self.items = []
        self._nav_row = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_AROUND,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            intrinsic_height=True,
            controls=[],
        )
        self.bar = ft.BottomAppBar(
            bgcolor=ft.Colors.SURFACE,
            padding=0,
            height=75,
            border_radius=ft.BorderRadius.only(top_left=10, top_right=10),
            shadow_color=ft.Colors.BLACK26,
            content=ft.Container(
                height=75,
                content=self._nav_row,
            ),
        )
        self.refresh()

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
        if item_route == "/profile":
            return clean in ("/profile", "/edit-profile")
        return clean == item_route

    def _build_nav_item(self, icon_name, route, is_rotated=False):
        is_active = self._is_match(route, self.current_route)
        label_text = route.strip("/").capitalize()
        if label_text == "Dashboard" or not label_text:
            label_text = "Home"
        if route == "/courses":
            label_text = "Learn"

        btn = ft.IconButton(
            icon=icon_name,
            icon_size=25,
            mouse_cursor=ft.MouseCursor.CLICK,
            rotate=ft.Rotate(angle=-0.5) if is_rotated else None,
            on_click=lambda e, r=route: self.page.go(r),
            style=ft.ButtonStyle(
                color={
                    ft.ControlState.DEFAULT: ft.Colors.ON_PRIMARY if is_active else ft.Colors.PRIMARY,
                    ft.ControlState.HOVERED: ft.Colors.ON_PRIMARY,
                },
                bgcolor={
                    ft.ControlState.DEFAULT: ft.Colors.PRIMARY if is_active else ft.Colors.SURFACE,
                    ft.ControlState.HOVERED: ft.Colors.PRIMARY,
                },
            ),
        )
        txt = ft.Text(
            label_text,
            size=10,
            color=ft.Colors.PRIMARY if is_active else ft.Colors.ON_SURFACE_VARIANT,
            weight=ft.FontWeight.BOLD if is_active else ft.FontWeight.NORMAL,
        )
        self.items.append((route, btn, txt))
        return ft.Column(
            spacing=0,
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[btn, txt],
        )

    def refresh(self):
        user_data = (self.page.session.store.get("current_user") or {}) if hasattr(self.page, "session") and hasattr(self.page.session, "store") else {}
        role = str(user_data.get("role", "STUDENT")).upper()
        self.items.clear()

        nav_controls = [
            self._build_nav_item(ft.Icons.HOME_ROUNDED, "/dashboard"),
            self._build_nav_item(ft.Icons.SEND_ROUNDED, "/nu-chat", is_rotated=True),
            self._build_nav_item(ft.Icons.SCHOOL_ROUNDED, "/courses"),
        ]

        if role in ["ADMIN", "TEACHER"]:
            nav_controls.append(
                self._build_nav_item(ft.Icons.BUSINESS_SHARP, "/organisations")
            )

        nav_controls.append(
            self._build_nav_item(ft.Icons.ACCOUNT_CIRCLE, "/profile")
        )
        self._nav_row.controls = nav_controls

    def set_active_route(self, new_route: str):
        self.current_route = new_route
        for route, btn, txt in self.items:
            active = self._is_match(route, new_route)
            btn.style = ft.ButtonStyle(
                color={
                    ft.ControlState.DEFAULT: ft.Colors.ON_PRIMARY if active else ft.Colors.PRIMARY,
                    ft.ControlState.HOVERED: ft.Colors.ON_PRIMARY,
                },
                bgcolor={
                    ft.ControlState.DEFAULT: ft.Colors.PRIMARY if active else ft.Colors.SURFACE,
                    ft.ControlState.HOVERED: ft.Colors.PRIMARY,
                },
            )
            txt.color = ft.Colors.PRIMARY if active else ft.Colors.ON_SURFACE_VARIANT
            txt.weight = ft.FontWeight.BOLD if active else ft.FontWeight.NORMAL


def get_bottom_appbar(page: ft.Page) -> ft.BottomAppBar:
    """Backward-compatible helper that constructs a BottomAppBar instance."""
    return PersistentBottomAppBar(page).bar