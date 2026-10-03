import asyncio
import sys
sys.path.insert(0, ".")
import flet as ft
from unittest.mock import MagicMock
from src.components.cohorts_hub import build_cohorts_tab

class MockPage:
    def __init__(self, loop):
        self.width = 1200
        self.height = 900
        self.theme_mode = ft.ThemeMode.LIGHT
        self.overlay = []
        self.session = MagicMock()
        self.session.store = {"auth_token": "mock-token", "current_user": {"id": "user-admin", "role": "teacher", "name": "Prof Smith"}}
        self.shared_preferences = MagicMock()
        fut = loop.create_future()
        fut.set_result("mock-token")
        self.shared_preferences.get = MagicMock(return_value=fut)

    def update(self):
        pass

    def run_task(self, fn, *args, **kwargs):
        pass

async def test_cohort_hub():
    loop = asyncio.get_running_loop()
    page = MockPage(loop)
    view = build_cohorts_tab(
        page=page,
        org_id="mock-org-id",
        token="mock-token",
        is_admin=True,
        org_data={"id": "mock-org-id", "name": "Tech Academy"},
        org_courses=[{"id": "c-1", "name": "Python 101"}],
        org_members=[{"id": "u-1", "first_name": "Alice", "last_name": "Smith", "email": "alice@test.com"}],
    )
    assert view is not None
    print("SUCCESS: build_cohorts_tab instantiated cleanly!")

if __name__ == "__main__":
    asyncio.run(test_cohort_hub())
