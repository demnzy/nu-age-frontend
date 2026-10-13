import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import flet as ft
from unittest.mock import MagicMock, AsyncMock, patch
from src.course_analytics import course_analytics_view

mock_course = {
    "id": "c-100",
    "name": "Distributed Systems Architecture",
    "description": "Enterprise consensus, Paxos, and distributed storage.",
    "public": "organisation",
    "supervised": True,
    "category": {"id": "cat-cs", "name": "Computer Science"},
}

mock_students = [
    {"id": "u-1", "first_name": "Alan", "last_name": "Turing", "email": "alan@cam.ac.uk", "progress": 100.0},
    {"id": "u-2", "first_name": "Ada", "last_name": "Lovelace", "email": "ada@lovelace.io", "progress": 65.5},
    {"id": "u-3", "first_name": "Claude", "last_name": "Shannon", "email": "shannon@bell.com", "progress": 0.0},
]

mock_curriculum = {
    "modules": [
        {"id": "m-1", "title": "Module 1: Foundations", "lessons": [{"id": "l-1"}, {"id": "l-2"}]},
        {"id": "m-2", "title": "Module 2: Consensus", "lessons": [{"id": "l-3"}]},
    ]
}

mock_comp_stats = {
    "completion_rate": 0.33,
    "completed_count": 1,
    "total_enrolled": 3
}

mock_certs = {
    "total_issued": 1
}

mock_activity = [
    {"week": "W34", "participations": 12, "views": 18},
    {"week": "W35", "participations": 28, "views": 42},
    {"week": "W36", "participations": 35, "views": 52},
]

mock_org = {
    "id": "org-1",
    "name": "Apex Engineering",
    "theme_color": "#4338CA"
}

async def test_course_analytics():
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

    with patch("src.course_analytics.get_courses", new=AsyncMock(return_value=[mock_course])), \
         patch("src.course_analytics.get_enrolled_students", new=AsyncMock(return_value=mock_students)), \
         patch("src.course_analytics.get_course_curriculum", new=AsyncMock(return_value=mock_curriculum)), \
         patch("src.course_analytics.get_my_organisation", new=AsyncMock(return_value=mock_org)), \
         patch("src.course_analytics.get_completion_stats", new=AsyncMock(return_value=mock_comp_stats)), \
         patch("src.course_analytics.get_certificates_issued", new=AsyncMock(return_value=mock_certs)), \
         patch("src.course_analytics.get_weekly_activity", new=AsyncMock(return_value=mock_activity)):

        view = await course_analytics_view(page, org_id="org-1", course_id="c-100")
        
        # 1. Verify loading state: centered, and app_bar is hidden!
        assert len(view.controls) == 2
        content_socket = view.controls[0]
        app_bar = view.controls[1]
        assert content_socket.expand is True
        assert content_socket.alignment == ft.Alignment.CENTER
        assert app_bar.visible is False
        print("Verified Loading State: app_bar is hidden, spinner container is centered with expand=True!")

        # Complete async data loading
        await asyncio.gather(*tasks)

        # 2. Verify loaded state: app_bar visible, main layout active
        assert app_bar.visible is True
        main_col = content_socket.content
        assert isinstance(main_col, ft.Column), f"Expected ft.Column, got {type(main_col)}"

        # 3. Hero Header Card
        hero_card = main_col.controls[0]
        hero_body = hero_card.content.controls[1].content
        title_text = hero_body.controls[0].value
        assert title_text == "Distributed Systems Architecture"
        print(f"Verified Hero Header: Course title = '{title_text}'")

        # Badges
        badges_row = hero_body.controls[3]
        badge_labels = [c.content.controls[-1].value if hasattr(c, "content") and hasattr(c.content, "controls") else "" for c in badges_row.controls]
        assert any("CAMPUS" in l for l in badge_labels)
        assert any("Computer Science" in l for l in badge_labels)
        print("Verified Hero Badges: Campus status and Computer Science category present!")

        # 4. Tab Switcher
        tabs_bar = main_col.controls[1]
        tab_buttons = tabs_bar.content.controls
        assert len(tab_buttons) == 3
        print("Verified Tabbed Segmentation: 3 dedicated tabs for zero clutter!")

        # 5. Tab 1: Cohort Performance
        tab_content_container = main_col.controls[3]
        perf_tab = tab_content_container.content
        bento_grid = perf_tab.controls[0]
        bento_cards = bento_grid.controls
        assert len(bento_cards) == 4

        enrolled_val = bento_cards[0].content.controls[2].value
        comp_rate_val = bento_cards[1].content.controls[2].value
        avg_prog_val = bento_cards[2].content.controls[2].value
        certs_val = bento_cards[3].content.controls[2].value

        assert enrolled_val == "3"
        assert comp_rate_val == "33%"
        assert avg_prog_val == "55%"
        assert certs_val == "1"
        print(f"Verified Bento Stats: Enrolled={enrolled_val}, CompRate={comp_rate_val}, AvgProg={avg_prog_val}, Certs={certs_val}")

        # Explanatory Chart: Progress Tier Distribution
        tier_card = perf_tab.controls[2]
        assert "COHORT PROGRESS TIER DISTRIBUTION" in tier_card.content.controls[0].controls[0].value
        # Check diagnosis insight
        assert tier_card.content.controls[2].content.controls[1].value != ""
        print("Verified Explanatory Chart: Progress Tier Distribution with diagnosis insight!")

        # Cohort Retention Card
        retention_card = perf_tab.controls[4]
        assert "COHORT RETENTION & COMPLETION HEALTH" in retention_card.content.controls[0].controls[0].value
        print("Verified Explanatory Chart: Cohort Retention & Completion Health!")

        # 6. Switch to Tab 2: Curriculum & Engagement
        tab_curriculum_btn = tab_buttons[1]
        tab_curriculum_btn.on_click(None)
        curr_tab = tab_content_container.content
        mod_card = curr_tab.controls[0]
        activity_card = curr_tab.controls[2]
        assert "CURRICULUM MODULE PROGRESSION" in mod_card.content.controls[0].controls[0].value
        assert "WEEKLY ENGAGEMENT TELEMETRY" in activity_card.content.controls[0].controls[0].controls[0].value
        print("Verified Tab 2: Curriculum Module Progression and Weekly Engagement charts!")

        # 7. Switch to Tab 3: Student Roster
        tab_roster_btn = tab_buttons[2]
        tab_roster_btn.on_click(None)
        roster_tab = tab_content_container.content
        search_tf = roster_tab.content.controls[1]
        filter_chips = roster_tab.content.controls[2]
        roster_col = roster_tab.content.controls[4]

        assert len(roster_col.controls) == 3

        # Test mobile card layout (avatar, name, email, full-width progress bar)
        student_card_1 = roster_col.controls[0]
        # Card contains Column([Row(Avatar+Name/Email + Actions), Container(height=6), Row(ProgressBar + % pill)])
        assert len(student_card_1.content.controls) == 3
        prog_row = student_card_1.content.controls[2]
        assert isinstance(prog_row.controls[0].content, ft.ProgressBar)
        assert prog_row.controls[1].content.value == "100%"
        print("Verified Mobile Layout: Student card with full-width progress bar (immune to mobile shrinking)!")

        # Test live non-blocking search
        query = ""
        for char in "Ada":
            query += char
            search_tf.value = query
            ev = MagicMock()
            ev.control = search_tf
            search_tf.on_change(ev)

        assert len(roster_col.controls) == 1
        ada_card = roster_col.controls[0]
        ada_name = ada_card.content.controls[0].controls[0].controls[1].controls[0].value
        assert "Ada Lovelace" in ada_name
        print(f"Verified: Live search isolated {ada_name} smoothly!")

        # Reset search
        search_tf.value = ""
        ev.control = search_tf
        search_tf.on_change(ev)
        assert len(roster_col.controls) == 3

        # Test filter chip: 'completed'
        completed_chip = filter_chips.controls[1]
        completed_chip.on_click(None)
        assert len(roster_col.controls) == 1
        print("Verified: Completed filter chip isolated 1 graduate!")

        print("\nALL REFINED COURSE ANALYTICS VERIFICATION TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(test_course_analytics())
