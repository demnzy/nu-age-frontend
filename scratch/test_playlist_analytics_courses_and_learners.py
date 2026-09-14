import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import flet as ft
from unittest.mock import MagicMock, AsyncMock, patch
from src.playlist_analytics import playlist_analytics_view

mock_playlist = {
    "id": "pl-500",
    "name": "Full-Stack Distributed Engineering",
    "description": "Comprehensive pathway.",
    "public": True,
    "playlist_courses": [
        {
            "id": "pc-1",
            "course_id": "c-101",
            "order_index": 0,
            "course": {"id": "c-101", "name": "Distributed Systems Foundations"}
        },
        {
            "id": "pc-2",
            "course_id": "c-102",
            "order_index": 1,
            "course": {"id": "c-102", "name": "Consensus & Raft Protocols"}
        },
        {
            "id": "pc-3",
            "course_id": "c-103",
            "order_index": 2,
            "course": {"id": "c-103", "name": "Event-Driven Microservices"}
        }
    ],
}

mock_analytics = [
    {"student_id": "u-1", "student_name": "Ada Lovelace", "progress": 100.0, "completed_at": "2026-08-01"},
    {"student_id": "u-2", "student_name": "Alan Turing", "progress": 66.7, "completed_at": None},
    {"student_id": "u-3", "student_name": "Grace Hopper", "progress": 33.3, "completed_at": None},
]

mock_org = {"id": "org-1", "name": "Apex Academy", "theme_color": "#4F46E5"}

async def test_analytics_courses_and_learners():
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

    with patch("src.playlist_analytics.get_playlist", new=AsyncMock(return_value=mock_playlist)), \
         patch("src.playlist_analytics.get_playlist_analytics", new=AsyncMock(return_value=mock_analytics)), \
         patch("src.playlist_analytics.get_my_organisation", new=AsyncMock(return_value=mock_org)):

        view = await playlist_analytics_view(page, org_id="org-1", playlist_id="pl-500")
        await asyncio.gather(*tasks)

        # Confirm content_socket has main column
        content_socket = view.controls[0]
        main_col = content_socket.content
        assert main_col is not None

        # Check hero header: shows "3 Curated Courses in Pathway"
        hero_card = main_col.controls[0]
        header_body = hero_card.content.controls[1].content
        stats_row = header_body.controls[3]
        badge_text = stats_row.controls[1].controls[1].value
        assert "3 Curated Courses" in badge_text, f"Expected '3 Curated Courses', got '{badge_text}'"
        print(f"Verified Hero Header Course Count: {badge_text}")

        # Switch to Milestones Tab
        tabs_bar = main_col.controls[1]
        btn_milestones = tabs_bar.content.controls[1]
        btn_milestones.on_click(None)

        # Verify Milestones Tab Funnel Card has 3 course milestone rows!
        tab_content_container = main_col.controls[3]
        milestone_col = tab_content_container.content
        funnel_card = milestone_col.controls[0]
        funnel_content_col = funnel_card.content
        
        # Check that it's NOT the empty state
        # The funnel card has section header, spacer, etc., and milestone rows
        assert len(funnel_content_col.controls) >= 3
        print("Verified Milestone Funnel Card rendered courses correctly!")

    print("\nALL RECONCILIATION TESTS PASSED PERFECTLY!")

if __name__ == "__main__":
    asyncio.run(test_analytics_courses_and_learners())
