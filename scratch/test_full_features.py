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
    {"id": "c-3", "name": "Draft Course", "description": "Work in progress.", "public": "false", "total_students": 0},
]

mock_playlists = [
    {"id": "pl-1", "name": "Fullstack Cloud Path", "description": "Curated path.", "image_url": ""}
]

async def test_full_features():
    page = MagicMock(spec=ft.Page)
    page.width = 1200
    page.height = 800
    page.session = MagicMock()
    page.session.store = {
        "current_user": {"id": "owner-1234-uuid", "role": "OWNER"}
    }
    page.shared_preferences = MagicMock()
    page.shared_preferences.get = AsyncMock(return_value="mock_jwt_token")
    dialogs = []
    page.show_dialog = lambda d: dialogs.append(d)
    page.go = MagicMock()
    page.update = MagicMock()
    page.launch_url = AsyncMock()
    page.set_clipboard = AsyncMock()
    page.overlay = []

    tasks = []
    def run_task(handler, *args):
        tasks.append(asyncio.create_task(handler(*args)))
    page.run_task = run_task

    with patch("src.org_view.get_my_organisation", new=AsyncMock(return_value=mock_org)), \
         patch("src.org_view.get_organisation_members", new=AsyncMock(return_value=mock_members)), \
         patch("src.org_view.get_organisation_courses", new=AsyncMock(return_value=mock_courses)), \
         patch("src.org_view.get_org_playlists", new=AsyncMock(return_value=mock_playlists)):

        view = await organisations_view(page)
        
        # Await all background tasks started by page.run_task
        await asyncio.gather(*tasks)
        
        # view.controls[0] is ft.SafeArea(content=content_socket)
        safe_area = view.controls[0]
        content_socket = safe_area.content
        dashboard_col = content_socket.content
        assert isinstance(dashboard_col, ft.Column)
        
        hero = dashboard_col.controls[0]
        body = dashboard_col.controls[1]
        
        # Verify hero contains circular logo
        identity_area = hero.content.controls[1]
        logo_container = identity_area.content.controls[0].controls[0].content
        assert isinstance(logo_container.content, ft.CircleAvatar)
        print("Verified: Circular logo is present!")
        
        # Verify tab bar
        body_col = body.content
        tab_buttons = body_col.controls[2]
        tab_content_wrapper = body_col.controls[4]
        
        print(f"Verified: Tab buttons present with {len(tab_buttons.controls)} tabs.")
        
        # Test switching to Members tab (index 1)
        members_tab_btn = tab_buttons.controls[1]
        members_tab_btn.on_click(None)
        print("Switched to Members tab.")
        
        # Test switching to Playlists tab (index 2)
        playlists_tab_btn = tab_buttons.controls[2]
        playlists_tab_btn.on_click(None)
        print("Switched to Playlists tab.")
        
        # Test switching to Info tab (index 3)
        info_tab_btn = tab_buttons.controls[3]
        info_tab_btn.on_click(None)
        print("Switched to Info tab.")
        
        # Test switching back to Courses tab (index 0)
        courses_tab_btn = tab_buttons.controls[0]
        courses_tab_btn.on_click(None)
        print("Switched back to Courses tab.")
        
        # Verify courses tab has "Courses & Curricula" and "New Course" button
        tab_content = tab_content_wrapper.content.content
        section_header = tab_content.controls[0]
        section_title = section_header.controls[0].controls[0].value
        assert section_title == "Courses & Curricula"
        new_course_btn = section_header.controls[1]
        btn_text = new_course_btn.content.value if hasattr(new_course_btn.content, "value") else str(new_course_btn.content)
        assert "New Course" in btn_text
        new_course_btn.on_click(None)
        await asyncio.gather(*tasks)
        assert len(dialogs) >= 1
        print("Verified: Contextual 'New Course' button opens in-dashboard create modal!")

        # Check filter bar has All, Public, Campus, Drafts, Category, Instructor
        filter_bar = tab_content.controls[2]
        filter_labels = [
            c.content.value if isinstance(c.content, ft.Text) else c.content.controls[0].value
            for c in filter_bar.controls
        ]
        assert "All" in filter_labels
        assert "Public" in filter_labels
        assert "Campus" in filter_labels
        assert "Drafts" in filter_labels
        assert "Category" in filter_labels
        assert "Instructor" in filter_labels
        print(f"Verified: Course filter chips = {filter_labels}")

        # Check member tab contextual Invite Member button
        members_tab_btn.on_click(None)
        mem_content = tab_content_wrapper.content.content
        mem_section_header = mem_content.controls[0]
        assert mem_section_header.controls[0].controls[0].value == "Members & Faculty"
        invite_btn = mem_section_header.controls[1]
        invite_btn_text = invite_btn.content.value if hasattr(invite_btn.content, "value") else str(invite_btn.content)
        assert "Invite Member" in invite_btn_text
        invite_btn.on_click(None)
        page.go.assert_called_with(f"/organisations/{mock_org['id']}/invite-members")
        print("Verified: Contextual 'Invite Member' button in Members tab works!")

        # Check playlist tab contextual New Path button
        playlists_tab_btn.on_click(None)
        pl_content = tab_content_wrapper.content.content
        pl_section_header = pl_content.controls[0]
        assert pl_section_header.controls[0].controls[0].value == "Curated Learning Paths"
        new_path_btn = pl_section_header.controls[1]
        path_btn_text = new_path_btn.content.value if hasattr(new_path_btn.content, "value") else str(new_path_btn.content)
        assert "New Path" in path_btn_text
        new_path_btn.on_click(None)
        assert len(dialogs) >= 2
        print("Verified: Contextual 'New Path' button opens in-dashboard create modal!")

        print("ALL INTERACTIVE FEATURE TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(test_full_features())
