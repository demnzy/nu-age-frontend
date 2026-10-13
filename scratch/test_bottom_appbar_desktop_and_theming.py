import sys
import os
import math
sys.path.insert(0, os.path.abspath("."))

import flet as ft
from src.components.bottom_appbar import PersistentBottomAppBar, BottomAppBarThemeManager, _get_nav_theme

class MockSession:
    def __init__(self, role="ADMIN"):
        self.store = {"current_user": {"role": role, "username": "admin_user"}}

class MockPage:
    def __init__(self, width=1200, theme_mode=ft.ThemeMode.DARK, role="ADMIN", route="/profile"):
        self.width = width
        self.theme_mode = theme_mode
        self.route = route
        self.session = MockSession(role)
        self.data = {}
        self.views = []
        self.on_resize = None

    def go(self, r):
        self.route = r

    def update(self):
        pass

def run_tests():
    print("--- 1. Testing Desktop Dock with Org (6 tabs) ---")
    page_desktop_org = MockPage(width=1280, theme_mode=ft.ThemeMode.DARK, role="ADMIN", route="/profile")
    bar_desktop_org = PersistentBottomAppBar(page_desktop_org)

    assert len(bar_desktop_org.items) == 6, f"Expected 6 items, got {len(bar_desktop_org.items)}"
    labels = [it.label for it in bar_desktop_org.items]
    assert labels == ["Home", "Chat", "Learn", "Alerts", "Orgs", "Profile"], f"Unexpected items: {labels}"
    assert bar_desktop_org._capsule.width == 560, f"Expected capsule width 560 on desktop for 6 items, got {bar_desktop_org._capsule.width}"
    assert bar_desktop_org._capsule.padding.left == 18, f"Expected horizontal padding 18, got {bar_desktop_org._capsule.padding.left}"
    assert bar_desktop_org._capsule.clip_behavior == ft.ClipBehavior.ANTI_ALIAS, "ClipBehavior should be ANTI_ALIAS"

    profile_item = bar_desktop_org.items[-1]
    assert profile_item.is_active is True, "Profile should be active"
    assert profile_item.label_ctrl.visible is True, "Profile label should be visible"
    print(f"Desktop 6-tab Profile active padding: {profile_item.container.padding.left}px, width={bar_desktop_org._capsule.width}px")

    # Geometry verification
    # Capsule radius = 29, height = 58
    # Left/right padding = 18 -> distance from capsule outer tip = 18px
    # Available height inside capsule curve at 18px from tip:
    avail_h = 2 * math.sqrt(29**2 - (29 - 18)**2)
    profile_h = profile_item.icon_ctrl.size + (profile_item.container.padding.top * 2) + 2
    clearance = (avail_h - profile_h) / 2
    assert clearance > 8.0, f"Expected clearance > 8px, got {clearance:.2f}px"
    print(f"Profile pill height: {profile_h}px, Available capsule height at pill: {avail_h:.1f}px, Vertical clearance: {clearance:.1f}px -> ZERO OVERFLOW/BLEED!")

    print("\n--- 2. Testing Desktop Dock without Org (5 tabs) ---")
    page_desktop_student = MockPage(width=1280, theme_mode=ft.ThemeMode.DARK, role="STUDENT", route="/profile")
    bar_desktop_student = PersistentBottomAppBar(page_desktop_student)
    assert len(bar_desktop_student.items) == 5, f"Expected 5 items, got {len(bar_desktop_student.items)}"
    assert bar_desktop_student._capsule.width == 490, f"Expected capsule width 490 for 5 items, got {bar_desktop_student._capsule.width}"
    print(f"Desktop 5-tab width: {bar_desktop_student._capsule.width}px (gap spacing matched)")

    print("\n--- 3. Testing Mobile Responsive Viewport (360px) ---")
    page_mobile = MockPage(width=360, theme_mode=ft.ThemeMode.DARK, role="ADMIN", route="/profile")
    bar_mobile = PersistentBottomAppBar(page_mobile)
    assert bar_mobile._capsule.width is None, "Mobile width should be None (auto-expanding to screen)"
    assert bar_mobile._capsule.padding.left == 10, f"Mobile horizontal padding should be 10, got {bar_mobile._capsule.padding.left}"
    print("Mobile 6-tab layout correctly configured")

    print("\n--- 4. Testing Mode-Cognizance & Instantaneous Theme Switching ---")
    # Verify dark colors
    assert bar_desktop_org._capsule.bgcolor == "#222222", f"Expected #222222, got {bar_desktop_org._capsule.bgcolor}"
    assert profile_item.icon_ctrl.color == "#4CAF50", f"Expected #4CAF50, got {profile_item.icon_ctrl.color}"
    print(f"Dark mode verified: surface={bar_desktop_org._capsule.bgcolor}, active_primary={profile_item.icon_ctrl.color}")

    # Switch to Light Mode via BottomAppBarThemeManager
    BottomAppBarThemeManager.notify_theme_changed(is_dark=False)
    assert bar_desktop_org._capsule.bgcolor == "#FFFFFF", f"Expected #FFFFFF in light mode, got {bar_desktop_org._capsule.bgcolor}"
    assert profile_item.icon_ctrl.color == "#035800", f"Expected #035800 in light mode, got {profile_item.icon_ctrl.color}"
    assert bar_desktop_student._capsule.bgcolor == "#FFFFFF", "Student bar also updated to light mode"
    print(f"Light mode verified: surface={bar_desktop_org._capsule.bgcolor}, active_primary={profile_item.icon_ctrl.color}")

    # Switch back to Dark Mode
    BottomAppBarThemeManager.notify_theme_changed(is_dark=True)
    assert bar_desktop_org._capsule.bgcolor == "#222222", f"Expected #222222, got {bar_desktop_org._capsule.bgcolor}"
    assert profile_item.icon_ctrl.color == "#4CAF50", f"Expected #4CAF50, got {profile_item.icon_ctrl.color}"
    print("Instant mode switching confirmed across all registered bars!")

    print("\nALL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
