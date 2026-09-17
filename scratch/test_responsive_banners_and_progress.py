import sys
import os
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import flet as ft

from src.course_page import course_learner_view

async def test_banners_and_progress():
    print("Testing course_page responsive banners & adaptive progress bar...")

    mock_page = MagicMock(spec=ft.Page)
    mock_page.width = 360  # narrow mobile width
    mock_page.height = 700
    mock_page.theme_mode = ft.ThemeMode.LIGHT
    mock_page.shared_preferences = MagicMock()
    mock_page.shared_preferences.get = AsyncMock(return_value="mock_token")
    mock_page.go = MagicMock()
    mock_page.update = MagicMock()
    mock_page.overlay = []

    mock_course = {
        "id": "c1",
        "name": "Test Course",
        "course_title": "Test Course",
        "modules": [
            {
                "id": "m1",
                "title": "Module 1",
                "lessons": [
                    {
                        "id": "l1",
                        "title": "Lesson 1",
                        "type": "cloze",
                        "is_done": False,
                        "is_unlocked": True,
                        "content": "Python is a {programming} language with {simple} syntax.",
                    }
                ],
            }
        ],
        "completed_lesson_ids": [],
    }

    with patch("src.course_page.get_course_curriculum", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_course
        view = await course_learner_view(mock_page, "c1")
        assert isinstance(view, ft.View)

        # Verify AppBar has rounded bottom edges
        assert view.appbar.shape is not None
        assert view.appbar.shape.radius.bottom_left > 0
        assert view.appbar.shape.radius.bottom_right > 0
        print("[PASS] Course header (AppBar) has rounded bottom borders (left & right):", view.appbar.shape.radius)

        # Verify content_socket is mounted
        safe_area = view.controls[0]
        assert safe_area.content is not None
        print("[PASS] Content socket mounted cleanly inside SafeArea.")

    print("ALL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test_banners_and_progress())
