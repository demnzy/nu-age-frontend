import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import flet as ft
from unittest.mock import MagicMock, AsyncMock, patch
from src.org_view import organisations_view

mock_org = {
    "id": "584b537e-6521-4852-a7e4-18f6c095126d",
    "name": "Apex Engineering Institute",
    "email": "contact@apex.edu",
    "owner_id": "owner-1234-uuid",
    "logo": "",
    "theme_color": "#4338CA",
    "plan": {"name": "Enterprise Academy", "max_members": 100, "max_courses": 50, "features": []}
}

mock_courses = [
    {"id": "c-1", "name": "Python FastTrack", "description": "Learn python quickly.", "public": "true", "total_students": 10},
    {"id": "c-2", "name": "Django Microservices", "description": "Backend API systems.", "public": "organisation", "total_students": 5},
    {"id": "c-3", "name": "Rust Fundamentals", "description": "Memory safety without GC.", "public": "organisation", "total_students": 2},
]

async def test_search_nonblocking():
    page = MagicMock(spec=ft.Page)
    page.width = 1200
    page.height = 800
    page.session = MagicMock()
    page.session.store = {"current_user": {"id": "owner-1234-uuid", "role": "OWNER"}}
    page.shared_preferences = MagicMock()
    page.shared_preferences.get = AsyncMock(return_value="mock_jwt_token")
    page.go = MagicMock()
    page.update = MagicMock()
    page.overlay = []
    page.show_dialog = MagicMock()

    tasks = []
    def run_task(handler, *args):
        task = asyncio.create_task(handler(*args))
        tasks.append(task)
        return task
    page.run_task = run_task

    with patch("src.org_view.get_my_organisation", new=AsyncMock(return_value=mock_org)), \
         patch("src.org_view.get_organisation_members", new=AsyncMock(return_value=[])), \
         patch("src.org_view.get_organisation_courses", new=AsyncMock(return_value=mock_courses)), \
         patch("src.org_view.get_org_playlists", new=AsyncMock(return_value=[])), \
         patch("src.org_view.get_categories", new=AsyncMock(return_value=[])):

        view = await organisations_view(page)
        await asyncio.gather(*tasks)

        tab_content = view.controls[0].content.content.controls[1].content.controls[4].content.content
        search_box = tab_content.controls[1]
        courses_grid = tab_content.controls[3]
        courses_grid.update = MagicMock()

        initial_search_box_id = id(search_box)
        assert len(courses_grid.controls) == 3

        # Simulate typing letter by letter: 'P', 'y', 't', 'h', 'o', 'n'
        query = ""
        for char in "Python":
            query += char
            search_box.value = query
            ev = MagicMock()
            ev.control = search_box
            search_box.on_change(ev)

            # Assert search box was NOT replaced in the tree
            current_search_box = tab_content.controls[1]
            assert id(current_search_box) == initial_search_box_id, "search_box must not be recreated on keystroke!"

        # After typing 'Python', only 1 course ('Python FastTrack') should match
        assert len(courses_grid.controls) == 1
        matched_card = courses_grid.controls[0].content
        matched_title = matched_card.content.controls[1].content.controls[0].value
        assert matched_title == "Python FastTrack"
        print(f"Verified: Typed 'Python' letter-by-letter without recreating search_box. Isolated: {matched_title}")

        # Clear search
        search_box.value = ""
        ev.control = search_box
        search_box.on_change(ev)
        assert len(courses_grid.controls) == 3
        print("Verified: Cleared search smoothly without recreating search_box!")

        print("\nALL SEARCH NON-BLOCKING TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(test_search_nonblocking())
