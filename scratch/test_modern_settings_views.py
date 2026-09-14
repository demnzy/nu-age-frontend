import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import flet as ft
from unittest.mock import MagicMock, AsyncMock, patch

from src.course_settings import course_settings_view
from src.playlist_settings import playlist_settings_view

mock_course = {
    "id": "c-100",
    "name": "Distributed Systems Architecture",
    "description": "Mastering fault tolerance and consensus algorithms.",
    "public": "organisation",
    "category": {"name": "Computer Science"},
    "teacher_id": "t-1",
}

mock_teachers = [
    {"id": "t-1", "first_name": "Barbara", "last_name": "Liskov", "email": "barbara@nu.edu"},
    {"id": "t-2", "first_name": "Leslie", "last_name": "Lamport", "email": "leslie@nu.edu"},
]

mock_categories = [
    {"id": "cat-1", "name": "Computer Science"},
    {"id": "cat-2", "name": "Software Architecture"},
]

mock_students = [
    {"id": "s-1", "name": "Ada Lovelace", "email": "ada@nu.edu", "is_enrolled": True},
    {"id": "s-2", "name": "Alan Turing", "email": "alan@nu.edu", "is_enrolled": True},
    {"id": "s-3", "name": "Grace Hopper", "email": "grace@nu.edu", "is_enrolled": False},
]

mock_playlist = {
    "id": "pl-500",
    "name": "Cloud Systems & Reliability Pathway",
    "description": "Master distributed computing and resilience engineering.",
    "is_public": True,
    "org_id": "org-1",
    "playlist_courses": [
        {"id": "pc-1", "course_id": "c-100", "course": {"id": "c-100", "name": "Distributed Systems Architecture"}},
        {"id": "pc-2", "course_id": "c-101", "course": {"id": "c-101", "name": "Consensus & Paxos"}},
    ]
}

mock_org = {
    "id": "org-1",
    "name": "Apex Academy",
    "theme_color": "#4338CA"
}

async def run_tests():
    print("--- TESTING COURSE SETTINGS VIEW ---")
    page = MagicMock(spec=ft.Page)
    page.width = 1200
    page.height = 800
    page.views = []
    page.overlay = []
    page.shared_preferences = MagicMock()
    page.shared_preferences.get = AsyncMock(return_value="mock_jwt")
    page.session = MagicMock()
    page.session.store = MagicMock()
    page.session.store.get = lambda key: {"role": "ADMIN"} if key == "current_user" else "org-1"
    page.go = MagicMock()
    page.update = MagicMock()

    tasks = []
    def run_task(handler, *args):
        task = asyncio.create_task(handler(*args))
        tasks.append(task)
        return task
    page.run_task = run_task

    with patch("src.course_settings.get_courses", new=AsyncMock(return_value=[mock_course])), \
         patch("src.course_settings.get_categories", new=AsyncMock(return_value=mock_categories)), \
         patch("src.course_settings.get_organisation_members", new=AsyncMock(return_value=mock_teachers)), \
         patch("src.course_settings.get_my_organisation", new=AsyncMock(return_value=mock_org)), \
         patch("src.course_settings.get_enrolled_org_students", new=AsyncMock(return_value={"students": mock_students})):

        c_view = await course_settings_view(page, course_id="c-100", org_id="org-1")
        await asyncio.gather(*tasks)

        # Inspect controls
        safe_area = c_view.controls[0]
        socket = safe_area.content
        main_col = socket.content
        assert main_col is not None, "Expected main_col in content_socket"
        hero_card = main_col.controls[0]
        assert hero_card is not None
        print("  [OK] Course Settings: Hero Card rendered.")

        # Check General, Access, Enrollment, Danger cards
        cards_col = main_col.controls[1].content.content
        assert len(cards_col.controls) >= 4
        general_card = cards_col.controls[0]
        access_card = cards_col.controls[1]
        enroll_card = cards_col.controls[2]
        danger_card = cards_col.controls[3]
        print("  [OK] Course Settings: 4 distinct segmented cards present.")

        # Test Enrollment Modal invocation
        manage_roster_btn = enroll_card.content.controls[2].content.controls[2]
        manage_roster_btn.on_click(None)
        assert len(page.overlay) > 0, "Expected enrollment dialog in page.overlay"
        dlg = page.overlay[-1]
        assert isinstance(dlg, ft.AlertDialog)
        print("  [OK] Course Settings: Enrollment Dialog launched.")

        # Await any new task from dialog
        await asyncio.gather(*tasks)
        print("  [OK] Course Settings: Dialog loaded students cleanly.")

    print("\n--- TESTING PLAYLIST SETTINGS VIEW ---")
    page.overlay.clear()
    tasks.clear()

    with patch("src.playlist_settings.get_playlist", new=AsyncMock(return_value=mock_playlist)), \
         patch("src.playlist_settings.get_my_organisation", new=AsyncMock(return_value=mock_org)):

        p_view = await playlist_settings_view(page, playlist_id="pl-500")
        await asyncio.gather(*tasks)

        # Inspect controls
        safe_area = p_view.controls[0]
        socket = safe_area.content
        main_col = socket.content
        assert main_col is not None
        hero_card = main_col.controls[0]
        print("  [OK] Playlist Settings: Hero Card rendered.")

        cards_col = main_col.controls[1].content.content
        assert len(cards_col.controls) >= 3
        general_card = cards_col.controls[0]
        access_card = cards_col.controls[1]
        curriculum_card = cards_col.controls[2]
        print("  [OK] Playlist Settings: Segmented Cards present.")

        # Check curriculum card preview courses
        preview_col = curriculum_card.content.controls[2]
        assert len(preview_col.controls) == 2, f"Expected 2 preview course items, got {len(preview_col.controls)}"
        print(f"  [OK] Playlist Settings: {len(preview_col.controls)} mapped courses rendered in curriculum preview.")

    print("\nALL MODERN SETTINGS TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(run_tests())
