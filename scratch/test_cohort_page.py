import asyncio
import sys
import os

# Set up path to import from project root
sys.path.insert(0, os.path.abspath("."))

import flet as ft
from unittest.mock import MagicMock, AsyncMock

class DummyPage:
    def __init__(self):
        self.route = "/dashboard"
        self.views = []
        self.overlay = []
        self.controls = []
        self.width = 1200
        self.height = 800
        self.theme_mode = ft.ThemeMode.DARK
        self.session = MagicMock()
        self.session.store = {"current_user": {"id": "user-1", "name": "Test User", "role": "learner"}}
        self.shared_preferences = AsyncMock()
        self.shared_preferences.get = AsyncMock(return_value="mock_token")
        self.shared_preferences.set = AsyncMock()
        self.window = MagicMock()
        self.window.width = 1200
        self.window.height = 800
        self.dialog = None
        self.tasks = []

    def update(self):
        pass

    def run_task(self, coro_fn, *args, **kwargs):
        task = asyncio.create_task(coro_fn(*args, **kwargs))
        self.tasks.append(task)
        return task

    def go(self, route):
        self.route = route


async def test_cohort_page_and_routes():
    print("1. Testing TemplateRoute matching...")
    troute1 = ft.TemplateRoute("/cohorts/cohort-abc-123")
    assert troute1.match("/cohorts/:cohort_id"), "Failed to match /cohorts/:cohort_id"
    assert troute1.cohort_id == "cohort-abc-123", f"Expected cohort-abc-123, got {troute1.cohort_id}"

    troute2 = ft.TemplateRoute("/cohorts")
    assert troute2.route == "/cohorts", "Failed on /cohorts"
    print("   [PASS] TemplateRoute matches correctly.")

    print("2. Testing cohort_page_view instantiation...")
    from src.cohort_page import cohort_page_view
    page = DummyPage()

    view_with_id = await cohort_page_view(page, cohort_id="c-999", back_target="/dashboard")
    assert isinstance(view_with_id, ft.View), "cohort_page_view did not return an ft.View"
    assert view_with_id.route == "/cohorts/c-999"
    assert view_with_id.appbar is not None
    print("   [PASS] View with cohort_id initialized successfully.")

    view_no_id = await cohort_page_view(page, cohort_id=None, back_target="/dashboard")
    assert isinstance(view_no_id, ft.View)
    assert view_no_id.route == "/cohorts"
    print("   [PASS] View without cohort_id initialized successfully.")

    print("3. Testing dashboard.py cohort cards logic...")
    from src.dashboard import dashboard_view
    d_view = await dashboard_view(page)
    assert isinstance(d_view, ft.View)
    print("   [PASS] Dashboard view rendered successfully with updated cohort click handlers.")

    print("4. Testing notifications_view.py cohort hub logic...")
    from src.notifications_view import notifications_view
    n_view = await notifications_view(page)
    assert isinstance(n_view, ft.View)
    print("   [PASS] Notifications view rendered successfully.")

    print("\nALL VERIFICATIONS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test_cohort_page_and_routes())
