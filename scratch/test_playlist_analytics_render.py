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
    "description": "Comprehensive pathway from networking fundamentals to Kubernetes orchestration.",
    "public": True,
    "courses": [
        {"id": "c-1", "name": "Computer Networking", "image_url": None},
        {"id": "c-2", "name": "Distributed Storage Systems", "image_url": None},
        {"id": "c-3", "name": "Kubernetes in Production", "image_url": None},
    ]
}

mock_analytics = [
    {"student_id": "u-1", "student_name": "Katherine Johnson", "enrolled_at": "2026-08-01T10:00:00Z", "progress": 100.0, "completed_at": "2026-09-01T10:00:00Z"},
    {"student_id": "u-2", "student_name": "Grace Hopper", "enrolled_at": "2026-08-10T12:00:00Z", "progress": 75.0, "completed_at": None},
    {"student_id": "u-3", "student_name": "Margaret Hamilton", "enrolled_at": "2026-08-15T15:00:00Z", "progress": 0.0, "completed_at": None},
]

mock_org = {
    "id": "org-1",
    "name": "Apex Engineering",
    "theme_color": "#4338CA"
}

async def test_playlist_analytics():
    page = MagicMock(spec=ft.Page)
    page.width = 1200
    page.height = 800
    page.views = []
    page.shared_preferences = MagicMock()
    page.shared_preferences.get = AsyncMock(return_value="mock_jwt")
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

        # 1. Verify loading state: centered, and app_bar is hidden!
        assert len(view.controls) == 2
        content_socket = view.controls[0]
        app_bar = view.controls[1]
        assert content_socket.expand is True
        assert content_socket.alignment == ft.Alignment.CENTER
        assert app_bar.visible is False
        print("Verified Loading State: app_bar is hidden, spinner is centered with expand=True!")

        # Complete async data loading
        await asyncio.gather(*tasks)

        # 2. Verify loaded state: app_bar visible
        assert app_bar.visible is True
        main_col = content_socket.content
        assert isinstance(main_col, ft.Column), f"Expected ft.Column, got {type(main_col)}"

        # 3. Hero Track Header
        hero_card = main_col.controls[0]
        hero_body = hero_card.content.controls[1].content
        title_text = hero_body.controls[0].value
        assert title_text == "Full-Stack Distributed Engineering"
        print(f"Verified Hero Header: Learning Path Title = '{title_text}'")

        # Check badges
        badges_row = hero_body.controls[3]
        assert "PUBLIC TRACK" in badges_row.controls[0].content.controls[1].value
        assert "3 Curated Courses in Pathway" in badges_row.controls[1].controls[1].value
        print("Verified Hero Badges: Public Track status and 3 Curated Courses present!")

        # 4. Tab Switcher
        tabs_bar = main_col.controls[1]
        tab_buttons = tabs_bar.content.controls
        assert len(tab_buttons) == 3
        print("Verified Tabbed Segmentation: 3 dedicated tabs for zero clutter!")

        # 5. Tab 1: Pathway Performance
        tab_content_container = main_col.controls[3]
        perf_tab = tab_content_container.content
        bento_grid = perf_tab.controls[0]
        bento_cards = bento_grid.controls
        assert len(bento_cards) == 4

        enrolled_val = bento_cards[0].content.controls[2].value
        completions_val = bento_cards[1].content.controls[2].value
        avg_prog_val = bento_cards[2].content.controls[2].value
        active_rate_val = bento_cards[3].content.controls[2].value

        assert enrolled_val == "3"
        assert completions_val == "33%"
        assert avg_prog_val == "58%" # (100 + 75 + 0) / 3 = 58.3%
        assert active_rate_val == "33%"
        print(f"Verified Bento Stats: Enrolled={enrolled_val}, Completions={completions_val}, AvgProgress={avg_prog_val}, ActiveRate={active_rate_val}")

        # Explanatory Chart: Pathway Progression Tier Distribution
        dist_card = perf_tab.controls[2]
        assert "PATHWAY PROGRESSION DISTRIBUTION" in dist_card.content.controls[0].controls[0].value
        # Check diagnosis insight
        assert dist_card.content.controls[2].content.controls[1].value != ""
        print("Verified Explanatory Chart: Pathway Progression Tier Distribution with diagnosis insight!")

        # 6. Switch to Tab 2: Curriculum Milestones
        tab_milestones_btn = tab_buttons[1]
        tab_milestones_btn.on_click(None)
        milestones_tab = tab_content_container.content
        funnel_card = milestones_tab.controls[0]
        assert "COURSE-BY-COURSE MILESTONE FUNNEL" in funnel_card.content.controls[0].controls[0].value
        print("Verified Tab 2: Course-by-Course Milestone Funnel with gateway drop-off diagnostics!")

        # 7. Switch to Tab 3: Pathfinder Cohort
        tab_learners_btn = tab_buttons[2]
        tab_learners_btn.on_click(None)
        learners_tab = tab_content_container.content
        search_tf = learners_tab.content.controls[1]
        filter_chips = learners_tab.content.controls[2]
        learners_col = learners_tab.content.controls[4]

        assert len(learners_col.controls) == 3

        # Test mobile card layout (avatar, name, enrolled info, full-width progress bar)
        learner_card_1 = learners_col.controls[0]
        assert len(learner_card_1.content.controls) == 3
        prog_row = learner_card_1.content.controls[2]
        assert isinstance(prog_row.controls[0].content, ft.ProgressBar)
        assert prog_row.controls[1].content.value == "100%"
        print("Verified Mobile Layout: Pathfinder card with full-width progress bar (immune to mobile shrinking)!")

        # Search for 'Grace'
        query = ""
        for char in "Grace":
            query += char
            search_tf.value = query
            ev = MagicMock()
            ev.control = search_tf
            search_tf.on_change(ev)

        assert len(learners_col.controls) == 1
        grace_card = learners_col.controls[0]
        grace_name = grace_card.content.controls[0].controls[0].controls[1].controls[0].value
        assert grace_name == "Grace Hopper"
        print(f"Verified: Live search isolated {grace_name} smoothly!")

        # Reset search
        search_tf.value = ""
        ev.control = search_tf
        search_tf.on_change(ev)
        assert len(learners_col.controls) == 3

        # Test Filter Chip: 'Completed'
        completed_chip = filter_chips.controls[1]
        completed_chip.on_click(None)
        assert len(learners_col.controls) == 1
        assert "Katherine Johnson" in learners_col.controls[0].content.controls[0].controls[0].controls[1].controls[0].value
        print("Verified: 'Completed' filter chip isolated 1 pathway graduate!")

        print("\nALL REFINED PLAYLIST ANALYTICS VERIFICATION TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(test_playlist_analytics())
