import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import flet as ft
from unittest.mock import MagicMock, AsyncMock, patch
from src.course_analytics import course_analytics_view
from src.playlist_analytics import playlist_analytics_view
from src.playlist_builder import playlist_builder_view

mock_course = {
    "id": "c-100",
    "name": "Distributed Systems Architecture",
    "description": "Enterprise scale distributed systems design.",
    "public": False,
    "category": {"name": "Computer Science"},
    "image_url": None,
}

mock_students = [
    {"student_id": "u-1", "student_name": "Ada Lovelace", "student_email": "ada@nu.edu", "progress": 100.0, "enrolled_at": "2026-08-01T10:00:00Z"},
    {"student_id": "u-2", "student_name": "Alan Turing", "student_email": "alan@nu.edu", "progress": 65.0, "enrolled_at": "2026-08-10T12:00:00Z"},
]

mock_org = {"id": "org-1", "name": "Apex Engineering", "theme_color": "#4338CA"}

mock_playlist = {
    "id": "pl-500",
    "name": "Full-Stack Distributed Engineering",
    "description": "Comprehensive pathway.",
    "public": True,
    "playlist_courses": [],
}

async def test_all_enhancements():
    page = MagicMock(spec=ft.Page)
    page.width = 1200
    page.height = 800
    page.views = []
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

    # 1. Test Course Analytics Tab Colors and School Cap Icon
    with patch("src.course_analytics.get_courses", new=AsyncMock(return_value=[mock_course])), \
         patch("src.course_analytics.get_enrolled_students", new=AsyncMock(return_value=mock_students)), \
         patch("src.course_analytics.get_course_curriculum", new=AsyncMock(return_value={"modules": []})), \
         patch("src.course_analytics.get_my_organisation", new=AsyncMock(return_value=mock_org)), \
         patch("src.course_analytics.get_completion_stats", new=AsyncMock(return_value={"completion_rate": 0.5, "completed_count": 1, "total_enrolled": 2})), \
         patch("src.course_analytics.get_certificates_issued", new=AsyncMock(return_value={"total_issued": 1})), \
         patch("src.course_analytics.get_weekly_activity", new=AsyncMock(return_value=[])):

        view = await course_analytics_view(page, org_id="org-1", course_id="c-100")
        await asyncio.gather(*tasks)
        tasks.clear()

        content_socket = view.controls[0]
        main_col = content_socket.content
        tabs_bar = main_col.controls[1]
        tab_buttons = tabs_bar.content.controls

        btn_perf = tab_buttons[0]
        btn_curriculum = tab_buttons[1]

        # Verify icon on curriculum button is SCHOOL_ROUNDED (grad cap)
        curriculum_icon = btn_curriculum.content.controls[0].icon
        assert curriculum_icon == ft.Icons.SCHOOL_ROUNDED, f"Expected SCHOOL_ROUNDED, got {curriculum_icon}"
        print("Verified: Curriculum tab icon is SCHOOL_ROUNDED (grad cap)!")

        # Check initial state: btn_perf is selected (white text/icon), btn_curriculum is unselected (non-white)
        assert btn_perf.content.controls[0].color == ft.Colors.WHITE
        assert btn_perf.content.controls[1].color == ft.Colors.WHITE
        assert btn_curriculum.content.controls[0].color == ft.Colors.ON_SURFACE_VARIANT
        assert btn_curriculum.content.controls[1].color == ft.Colors.ON_SURFACE

        # Switch to Curriculum tab
        btn_curriculum.on_click(None)

        # Verify: btn_perf is NOW unselected and its text/icon are NOT white!
        assert btn_perf.content.controls[0].color == ft.Colors.ON_SURFACE_VARIANT, f"Expected ON_SURFACE_VARIANT, got {btn_perf.content.controls[0].color}"
        assert btn_perf.content.controls[1].color == ft.Colors.ON_SURFACE, f"Expected ON_SURFACE, got {btn_perf.content.controls[1].color}"
        assert btn_perf.bgcolor == ft.Colors.TRANSPARENT

        # Verify: btn_curriculum is NOW selected (white text/icon, theme_color bgcolor)
        assert btn_curriculum.content.controls[0].color == ft.Colors.WHITE
        assert btn_curriculum.content.controls[1].color == ft.Colors.WHITE
        assert btn_curriculum.bgcolor == "#4338CA"
        print("Verified: Tab switching properly updates unfocused tab text & icon color away from white!")

    # 2. Test Playlist Analytics Tab Colors
    with patch("src.playlist_analytics.get_playlist", new=AsyncMock(return_value=mock_playlist)), \
         patch("src.playlist_analytics.get_playlist_analytics", new=AsyncMock(return_value=[])), \
         patch("src.playlist_analytics.get_my_organisation", new=AsyncMock(return_value=mock_org)):

        view = await playlist_analytics_view(page, org_id="org-1", playlist_id="pl-500")
        await asyncio.gather(*tasks)
        tasks.clear()

        content_socket = view.controls[0]
        main_col = content_socket.content
        tabs_bar = main_col.controls[1]
        tab_buttons = tabs_bar.content.controls

        btn_perf = tab_buttons[0]
        btn_milestones = tab_buttons[1]

        btn_milestones.on_click(None)
        assert btn_perf.content.controls[0].color == ft.Colors.ON_SURFACE_VARIANT
        assert btn_perf.content.controls[1].color == ft.Colors.ON_SURFACE
        print("Verified: Playlist analytics tab switching properly updates unfocused tab text & icon color away from white!")

    # 3. Test Playlist Builder (Analytics migrated out)
    with patch("src.playlist_builder.get_playlist", new=AsyncMock(return_value=mock_playlist)), \
         patch("src.playlist_builder.get_organisation_courses", new=AsyncMock(return_value=[])):

        view = await playlist_builder_view(page, playlist_id="pl-500")
        container = view.controls[0].content
        col = container.content
        assert len(col.controls) == 2 # Header Row + Curriculum Container
        print("Verified: Playlist builder is streamlined without analytics tabs!")

    # 4. Test Org View Playlist Card Actions
    with open("src/org_view.py", encoding="utf-8") as f:
        code = f.read()
        assert "EDIT_ROAD_ROUNDED" in code
        assert "BAR_CHART_ROUNDED" in code
        assert "/playlists/{pid}/analytics" in code
        print("Verified: Playlist card in org_view has Manage Roadmap and Pathway Analytics buttons matching course card!")

    print("\nALL ENHANCEMENT TESTS PASSED PERFECTLY!")

if __name__ == "__main__":
    asyncio.run(test_all_enhancements())
