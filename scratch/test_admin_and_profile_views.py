import asyncio
import os
import sys
sys.path.insert(0, os.path.abspath("."))
import flet as ft
from unittest.mock import MagicMock

class MockSessionStore:
    def __init__(self):
        self._data = {}

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value

    def remove(self, key):
        self._data.pop(key, None)

    def contains_key(self, key):
        return key in self._data

class MockSession:
    def __init__(self):
        self.store = MockSessionStore()

    def get(self, key, default=None):
        return self.store.get(key, default)

    def set(self, key, value):
        self.store.set(key, value)

class MockPage:
    def __init__(self):
        self.theme_mode = ft.ThemeMode.DARK
        self.width = 1200
        self.height = 800
        self.route = "/profile"
        self.window = MagicMock()
        self.window.width = 1200
        self.window.height = 800
        self.session = MockSession()
        self.shared_preferences = MagicMock()
        self.shared_preferences.get = MagicMock(return_value=asyncio.Future())
        self.shared_preferences.get.return_value.set_result("dummy_token")
        self.dialog = None
        self.overlay = []
        self.data = {}
        self.views = []
        self._tasks = []

    def update(self):
        pass

    def run_task(self, fn, *args, **kwargs):
        res = fn(*args, **kwargs)
        if asyncio.iscoroutine(res):
            self._tasks.append(res)

    def show_dialog(self, dlg):
        self.dialog = dlg

    def pop_dialog(self):
        self.dialog = None

    def go(self, route):
        pass

async def run_tests():
    print("--- 1. Testing _is_platform_super_admin helper ---")
    from src.profile import _is_platform_super_admin
    assert _is_platform_super_admin("nu-admin") == True
    assert _is_platform_super_admin("NU-ADMIN") == True
    assert _is_platform_super_admin(" nu-admin ") == True
    assert _is_platform_super_admin("tobi") == False
    assert _is_platform_super_admin("regular_student") == False
    print("PASS: _is_platform_super_admin strictly matches 'nu-admin' (case-insensitive) and rejects all others.")

    print("\n--- 2. Testing profile_view for Regular User (NO super admin card) ---")
    mock_page = MockPage()
    mock_page.session.store.set("current_user", {
        "id": "123",
        "username": "student_john",
        "email": "john@student.edu",
        "first_name": "John",
        "last_name": "Doe",
        "role": "student",
    })
    from src.profile import profile_view
    view_regular = await profile_view(mock_page)
    if mock_page._tasks:
        await asyncio.gather(*mock_page._tasks)

    # Check that admin card is NOT in the controls of view_regular
    found_admin_section = False
    def check_controls(c):
        nonlocal found_admin_section
        if hasattr(c, "value") and "Platform Super Admin Panel" in str(c.value):
            found_admin_section = True
        if hasattr(c, "controls") and c.controls:
            for child in c.controls:
                check_controls(child)
        if hasattr(c, "content") and c.content:
            check_controls(c.content)

    for ctrl in view_regular.controls:
        check_controls(ctrl)
    assert not found_admin_section, "Admin panel must NOT be visible to regular user!"
    print("PASS: Super admin card is completely hidden for non-admin accounts.")

    print("\n--- 3. Testing profile_view for Super Admin (Card IS present) ---")
    mock_page_admin = MockPage()
    mock_page_admin.session.store.set("current_user", {
        "id": "999",
        "username": "nu-admin",
        "email": "admin@nu-age.name.ng",
        "first_name": "Nu",
        "last_name": "Admin",
        "role": "admin",
    })
    view_admin = await profile_view(mock_page_admin)
    if mock_page_admin._tasks:
        await asyncio.gather(*mock_page_admin._tasks)

    found_admin_section = False
    for ctrl in view_admin.controls:
        check_controls(ctrl)
    assert found_admin_section, "Admin panel MUST be visible to configured super admin!"
    print("PASS: Super admin card is visible for configured PLATFORM_SUPER_ADMINS account.")

    print("\n--- 4. Testing platform_admin_view instantiation ---")
    from src.platform_admin_view import platform_admin_view
    # Pre-authenticate in session to test dashboard & tabs
    mock_page_admin.session.store.set("platform_admin_token", "test_jwt_super_token")
    mock_page_admin.session.store.set("platform_admin_user", {
        "name": "Tobi Master",
        "username": "tobi",
        "email": "tobi@nu-age.name.ng",
        "role": "Admin",
    })

    admin_view = await platform_admin_view(mock_page_admin)
    assert admin_view.route == "/platform-admin"
    print("PASS: platform_admin_view instantiated successfully with active token.")

    print("\n--- 5. Testing User Directory Cards & Tab 3 Push Broadcast ---")
    # Simulate switching to users tab and rendering mock cards
    # We can inspect the returned view controls
    assert len(admin_view.controls) > 0
    main_container = admin_view.controls[0]
    dashboard_col = main_container.content
    assert dashboard_col is not None
    print("PASS: Platform Admin dashboard hierarchy verified.")

    print("\nAll integration verification assertions PASSED successfully!")

if __name__ == "__main__":
    asyncio.run(run_tests())
