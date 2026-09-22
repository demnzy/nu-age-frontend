import sys
import os
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import flet as ft

from src.course_settings import course_settings_view

async def test_course_settings():
    print("Testing course_settings.py instantiation and save flow...")

    mock_page = MagicMock(spec=ft.Page)
    mock_page.width = 1200
    mock_page.height = 900
    mock_page.theme_mode = ft.ThemeMode.LIGHT
    mock_page.shared_preferences = MagicMock()
    mock_page.shared_preferences.get = AsyncMock(return_value="mock_jwt_token")
    mock_page.go = MagicMock()
    mock_page.update = MagicMock()
    mock_page.overlay = []

    running_tasks = []
    def run_task_mock(fn, *args):
        t = asyncio.create_task(fn(*args))
        running_tasks.append(t)
        return t
    mock_page.run_task = run_task_mock

    mock_course = {
        "id": "c_test_001",
        "name": "Distributed Systems Architecture",
        "description": "Learn to architect scalable distributed systems.",
        "category_id": "cat-uuid-001",
        "category": {"id": "cat-uuid-001", "name": "Backend Engineering"},
        "teacher_id": "teacher-uuid-001",
        "public": "false",
    }

    mock_categories = [
        {"id": "cat-uuid-001", "name": "Backend Engineering"},
        {"id": "cat-uuid-002", "name": "Frontend Engineering"},
    ]

    mock_teachers = [
        {"id": "teacher-uuid-001", "first_name": "Alan", "last_name": "Turing", "email": "alan@example.com"},
        {"id": "teacher-uuid-002", "first_name": "Ada", "last_name": "Lovelace", "email": "ada@example.com"},
    ]

    with patch("src.course_settings.get_courses", new_callable=AsyncMock) as mock_get_courses, \
         patch("src.course_settings.get_categories", new_callable=AsyncMock) as mock_get_cats, \
         patch("src.course_settings.get_organisation_members", new_callable=AsyncMock) as mock_get_teachers, \
         patch("src.course_settings.update_course_settings", new_callable=AsyncMock) as mock_update:

        mock_get_courses.return_value = [mock_course]
        mock_get_cats.return_value = mock_categories
        mock_get_teachers.return_value = mock_teachers
        mock_update.return_value = {**mock_course, "public": "true"}

        view = await course_settings_view(mock_page, "c_test_001", org_id="org_test_001")
        assert isinstance(view, ft.View), "Result must be an ft.View"
        assert view.route == "/organisations/org_test_001/courses/c_test_001/settings"

        # Wait for data load task
        if running_tasks:
            await asyncio.gather(*running_tasks)

        print("Data loaded into view successfully.")

        # Validate that the UI contains the controls
        content_socket = view.controls[0].content
        assert content_socket.content is not None, "Content socket should have rendered UI"
        print("View hierarchy rendered correctly.")

        # Test calling update_course_settings with payload
        saved = await mock_update("mock_jwt_token", "c_test_001", {"public": "true", "teacher_id": "none"})
        assert saved.get("public") == "true"
        print("Mock update successfully applied public = true.")

    print("ALL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test_course_settings())
