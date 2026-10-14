import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import flet as ft
from unittest.mock import AsyncMock, MagicMock

# Mock Page
class MockPage:
    def __init__(self):
        self.web = False
        self.route = "/courses"
        self.shared_preferences = MagicMock()
        self.shared_preferences.get = AsyncMock(return_value="mock_token")
        self.session = MagicMock()
        self.session.get = MagicMock(return_value=None)
        self.session.set = MagicMock()
        self.views = []
        self.theme_mode = ft.ThemeMode.DARK
        self._tasks = []

    def update(self):
        pass

    def run_task(self, handler, *args, **kwargs):
        pass

    def go(self, route):
        pass

    async def show_drawer(self):
        pass

    async def close_drawer(self):
        pass

    def open(self, control):
        pass

    def close(self, control):
        pass

async def test_instantiation():
    print("Testing get_enrolled_card...")
    from src.components.enrolled_card import get_enrolled_card
    page = MockPage()

    # 1. Idle card
    card_idle = get_enrolled_card(
        page,
        course_id="c-123",
        course_title="Introduction to Machine Learning with Neural Networks",
        course_category="Artificial Intelligence",
        course_author="Dr. Alex Rivera",
        image_url="https://images.unsplash.com/photo-1516321318423-f06f85e504b3",
        progress=45.0,
        rating=4.8,
    )
    assert card_idle is not None
    print("[OK] Idle card created successfully")

    # 2. Completed card (100%)
    card_completed = get_enrolled_card(
        page,
        course_id="c-456",
        course_title="Advanced Data Structures in Python",
        course_category="Computer Science",
        course_author="Jane Doe",
        image_url=None,
        progress=100.0,
        rating=5.0,
    )
    assert card_completed is not None
    print("[OK] Completed card created successfully")

    # 3. Test courses_view
    print("Testing courses_view...")
    from src.courses import courses_view
    view = await courses_view(page)
    assert view is not None
    assert view.route == "/courses"
    assert view.drawer is None # Side bar retired per user request
    assert len(view.controls) > 0
    print("[OK] courses_view created successfully (drawer retired)")
    print("ALL TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(test_instantiation())
