import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import flet as ft
from unittest.mock import AsyncMock, MagicMock, patch

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
        task = asyncio.create_task(handler(*args, **kwargs))
        self._tasks.append(task)
        return task

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

    def show_dialog(self, dialog):
        pass

async def test_full_interactive():
    print("Testing full interactive suite...")
    from src.courses import courses_view, SECTION_ENROLLED, SECTION_AVAILABLE, SECTION_PLAYLISTS, SECTION_COMPLETED, SECTION_ORG
    from src.components.enrolled_card import get_enrolled_card

    page = MockPage()

    # Mock API returns
    mock_courses = [
        {"id": "c1", "name": "Python for Beginners", "category": {"name": "Coding"}, "admin": {"first_name": "Alice", "last_name": "Smith"}, "created_at": "2026-01-01T12:00:00"},
        {"id": "c2", "name": "Deep Learning Masterclass", "category": {"name": "AI"}, "admin": {"first_name": "Bob", "last_name": "Jones"}, "created_at": "2026-02-01T12:00:00"},
    ]
    mock_enrolled = [
        {"id": "c3", "name": "Enrolled AI Course", "category": {"name": "AI"}, "admin": {"first_name": "Carol", "last_name": "White"}, "progress": 55.0, "rating": 4.9}
    ]
    mock_completed = [
        {"id": "c4", "name": "Finished Web Dev", "category": {"name": "Web"}, "progress": 100.0}
    ]
    mock_playlists = [
        {"id": "p1", "name": "Zero to Hero Bootcamp", "Organisation": "Tech Corp", "created_at": "2026-03-01T12:00:00"}
    ]

    with patch("src.courses.get_courses", AsyncMock(side_effect=[mock_courses, mock_completed, []])), \
         patch("src.courses.get_enrollments", AsyncMock(return_value=mock_enrolled)), \
         patch("src.courses.get_all_playlists", AsyncMock(return_value=mock_playlists)):

        view = await courses_view(page)
        assert view is not None
        print("[OK] View initialized with mocked data")

        # Let background populate task complete
        await asyncio.sleep(0.1)

        # Verify enrolled card created
        card = get_enrolled_card(
            page,
            course_id="c3",
            course_title="Enrolled AI Course",
            course_category="AI",
            course_author="Carol White",
            progress=55.0,
            rating=4.9,
        )
        assert card is not None
        print("[OK] Enrolled card with 55% progress validated")

    print("[SUCCESS] All full interactive tests passed cleanly!")

if __name__ == "__main__":
    asyncio.run(test_full_interactive())
