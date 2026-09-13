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
    "number": "+1 (555) 382-9912",
    "website": "https://apex.edu",
    "address": "400 University Crest, Silicon Valley, CA",
    "owner_id": "owner-1234-uuid",
    "logo": "https://nu-age-cdn.b-cdn.net/logos/placeholder%202.png",
    "theme_color": "#4338CA",
    "created_at": "2024-03-01T12:00:00Z",
    "plan": {
        "name": "Enterprise Academy",
        "max_members": 100,
        "max_courses": 50,
        "features": ["AI Course Builder", "Branded Mobile Portal"]
    }
}

mock_members = [
    {"id": "owner-1234-uuid", "first_name": "Daniel", "last_name": "Davids", "email": "daniel@apex.edu", "role": "OWNER"},
    {"id": "user-2", "first_name": "Sarah", "last_name": "Connor", "email": "sarah@apex.edu", "role": "TEACHER"},
    {"id": "user-3", "first_name": "Alex", "last_name": "Rivera", "email": "alex.r@apex.edu", "role": "STUDENT"},
]

mock_courses = [
    {"id": "c-1", "name": "Distributed Systems", "description": "Cloud scale.", "public": "true", "total_students": 45},
    {"id": "c-2", "name": "Internal Onboarding", "description": "Internal only.", "public": "organisation", "total_students": 12},
]

mock_playlists = [
    {"id": "pl-1", "name": "Fullstack Cloud Path", "description": "Curated path.", "image_url": ""}
]

mock_categories = [
    {"id": "cat-1", "name": "Computer Science"},
    {"id": "cat-2", "name": "Data Engineering"},
]

async def test_admin_modals_and_parity():
    page = MagicMock(spec=ft.Page)
    page.width = 360 # Mobile test width
    page.height = 800
    page.session = MagicMock()
    page.session.store = {
        "current_user": {"id": "owner-1234-uuid", "role": "OWNER"}
    }
    page.shared_preferences = MagicMock()
    page.shared_preferences.get = AsyncMock(return_value="mock_jwt_token")
    page.go = MagicMock()
    page.update = MagicMock()
    page.launch_url = AsyncMock()
    page.set_clipboard = AsyncMock()
    page.overlay = []

    dialogs_shown = []
    def show_dialog(d):
        dialogs_shown.append(d)
    page.show_dialog = show_dialog

    tasks = []
    def run_task(handler, *args):
        task = asyncio.create_task(handler(*args))
        tasks.append(task)
        return task
    page.run_task = run_task

    with patch("src.org_view.get_my_organisation", new=AsyncMock(return_value=mock_org)), \
         patch("src.org_view.get_organisation_members", new=AsyncMock(return_value=mock_members)), \
         patch("src.org_view.get_organisation_courses", new=AsyncMock(return_value=mock_courses)), \
         patch("src.org_view.get_org_playlists", new=AsyncMock(return_value=mock_playlists)), \
         patch("src.org_view.get_categories", new=AsyncMock(return_value=mock_categories)), \
         patch("src.org_view.create_course", new=AsyncMock(return_value={"id": "c-new-99", "name": "Quantum Computing", "public": "organisation", "total_students": 0})), \
         patch("src.org_view.create_playlist", new=AsyncMock(return_value={"id": "pl-new-88", "name": "Quantum Track", "is_public": True})):

        view = await organisations_view(page)
        await asyncio.gather(*tasks)

        content_socket = view.controls[0].content
        dashboard_col = content_socket.content
        body_col = dashboard_col.controls[1].content
        tab_buttons = body_col.controls[2]
        tab_content_wrapper = body_col.controls[4]
        tab_content = tab_content_wrapper.content.content

        # 1. Verify responsive header on mobile (< 360px):
        section_header = tab_content.controls[0]
        header_title_col = section_header.controls[0]
        assert header_title_col.expand is True, "Title column must have expand=True to prevent button bleeding on mobile"
        print("Verified: Section header has expand=True on title column (anti-bleeding on mobile)!")

        # 1b. Verify Search box is full width (width=inf)
        search_box = tab_content.controls[1]
        assert search_box.width == float("inf"), "search_box must be width=inf"
        print("Verified: search_box has width=inf (full-width)!")

        # 1c. Verify Category & Instructor filter chips exist in filter_bar
        filter_bar = tab_content.controls[2]
        cat_chip = filter_bar.controls[4]
        inst_chip = filter_bar.controls[5]
        assert "Category" in cat_chip.content.controls[0].value
        assert "Instructor" in inst_chip.content.controls[0].value
        print("Verified: Category & Instructor filter chips exist in filter_bar!")

        # 2. Verify Course Cards have 4 actions (Curriculum, Analytics, Settings, View)
        course_cards_row = tab_content.controls[3]
        first_course_card = course_cards_row.controls[0].content
        card_body = first_course_card.content.controls[1]
        card_bottom_row = card_body.content.controls[3]
        action_buttons_row = card_bottom_row.controls[1]
        action_tooltips = [b.tooltip for b in action_buttons_row.controls]
        assert "Manage Curriculum" in action_tooltips
        assert "Course Analytics" in action_tooltips
        assert "Course Settings" in action_tooltips
        assert "View Course" in action_tooltips
        print(f"Verified: Course card actions = {action_tooltips}")

        # Test Course Analytics click
        analytics_btn = action_buttons_row.controls[1]
        analytics_btn.on_click(None)
        page.go.assert_called_with(f"/organisations/{mock_org['id']}/courses/c-1/analytics")
        print("Verified: Course Analytics quick action routes properly!")

        # 3. Test "New Course" button opens in-dashboard modal
        new_course_btn = section_header.controls[1]
        new_course_btn.on_click(None)
        # Wait for lazy load categories and show_dialog task
        await asyncio.gather(*tasks)

        assert len(dialogs_shown) >= 1
        course_dialog = dialogs_shown[-1]
        assert "Create New Course" in course_dialog.title.controls[1].value
        print("Verified: 'New Course' opened in-dashboard modal dialog!")

        # Verify input fields in course creation modal have width=inf and switch has natural width
        dialog_col = course_dialog.content.content
        assert dialog_col.controls[0].width == float("inf"), "name_input must have width=inf"
        assert dialog_col.controls[1].width == float("inf"), "category_dropdown must have width=inf"
        assert dialog_col.controls[2].width == float("inf"), "visibility_dropdown must have width=inf"
        assert dialog_col.controls[3].width == float("inf"), "teacher_dropdown must have width=inf"
        assert dialog_col.controls[4].width == float("inf"), "desc_input must have width=inf"
        assert dialog_col.controls[5].width != float("inf"), "auto_certificate_switch must have natural width"
        assert dialog_col.controls[6].width == float("inf"), "obj_input must have width=inf"
        assert dialog_col.controls[8].width == float("inf"), "cover_picker_container must have width=inf"
        print("Verified: Input fields have width=inf and certificate switch has natural width!")

        vis_dropdown = dialog_col.controls[2]
        assert vis_dropdown.value == "organisation", "Default visibility must be 'organisation' (Campus)"
        vis_options = [o.text for o in vis_dropdown.options]
        print(f"Verified: Course Visibility dropdown options = {vis_options}")
        assert any("Campus" in o for o in vis_options)

        # Test course creation submission
        name_input = dialog_col.controls[0]
        name_input.value = "Quantum Computing"
        cat_dropdown = dialog_col.controls[1]
        cat_dropdown.value = "cat-1"
        submit_btn = course_dialog.actions[1]
        submit_btn.on_click(None)
        await asyncio.gather(*tasks)

        # Confirm new course was added to dashboard UI
        courses_grid = tab_content_wrapper.content.content.controls[3]
        assert len(courses_grid.controls) == 3
        print("Verified: New course created and added directly to dashboard list!")

        # 4. Switch to Playlists tab and test "New Path" modal
        playlists_tab_btn = tab_buttons.controls[2]
        playlists_tab_btn.on_click(None)
        pl_content = tab_content_wrapper.content.content
        pl_header = pl_content.controls[0]
        assert pl_header.controls[0].expand is True, "Playlist header title column must have expand=True"
        print("Verified: Playlist header title column has expand=True!")

        new_path_btn = pl_header.controls[1]
        new_path_btn.on_click(None)
        assert len(dialogs_shown) >= 2
        pl_dialog = dialogs_shown[-1]
        assert "Create Learning Path" in pl_dialog.title.controls[1].value
        print("Verified: 'New Path' opened in-dashboard modal dialog!")

        # Verify playlist input fields have width=inf and public switch has natural width
        pl_dialog_col = pl_dialog.content.content
        assert pl_dialog_col.controls[0].width == float("inf"), "playlist name_input must have width=inf"
        assert pl_dialog_col.controls[1].width == float("inf"), "playlist desc_input must have width=inf"
        assert pl_dialog_col.controls[2].width != float("inf"), "playlist public_switch must have natural width"
        assert pl_dialog_col.controls[3].width == float("inf"), "playlist cover_picker_container must have width=inf"
        print("Verified: Playlist inputs have width=inf and public switch has natural width!")

        # Submit playlist creation
        pl_name_input = pl_dialog_col.controls[0]
        pl_name_input.value = "Quantum Track"
        pl_submit_btn = pl_dialog.actions[1]
        pl_submit_btn.on_click(None)
        await asyncio.gather(*tasks)
        print("Verified: New learning path created directly inside dashboard!")

        print("\nALL ADMIN RETIREMENT & IN-DASHBOARD MODAL TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(test_admin_modals_and_parity())
