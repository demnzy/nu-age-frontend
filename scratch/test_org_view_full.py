import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import flet as ft
from unittest.mock import MagicMock, AsyncMock, patch
from src.org_view import organisations_view

mock_org_data = {
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
    "members": 15,
    "courses": 4,
    "staff": 3,
    "students": 12,
    "plan": {
        "name": "Enterprise Academy",
        "max_members": 100,
        "max_courses": 50,
        "price": 149.0,
        "features": ["AI Course Builder", "Branded Mobile Portal", "Custom Domain", "Priority 24/7 Support"]
    }
}

mock_members = [
    {"id": "owner-1234-uuid", "first_name": "Daniel", "last_name": "Davids", "email": "daniel@apex.edu", "role": "OWNER"},
    {"id": "user-2", "first_name": "Sarah", "last_name": "Connor", "email": "sarah@apex.edu", "role": "TEACHER"},
    {"id": "user-3", "first_name": "Alex", "last_name": "Rivera", "email": "alex.r@apex.edu", "role": "STUDENT"},
]

mock_courses = [
    {"id": "c-1", "name": "Distributed Systems", "description": "Cloud scale architecture.", "public": "true", "total_students": 25},
    {"id": "c-2", "name": "Internal Standards", "description": "Private org guidelines.", "public": "organisation", "total_students": 10},
]

mock_playlists = [
    {"id": "pl-1", "name": "Cloud Engineer Path", "description": "Master cloud systems."}
]

async def verify_org_dashboard():
    page = MagicMock(spec=ft.Page)
    page.width = 1200
    page.height = 850
    page.overlay = []
    page.controls = []
    page.route = "/organisations"
    page.session = MagicMock()
    page.session.store = {}
    page.shared_preferences = MagicMock()
    page.shared_preferences.get = AsyncMock(return_value="mock_jwt_token")
    page.show_dialog = MagicMock()
    page.go = MagicMock()
    page.update = MagicMock()
    page.launch_url = AsyncMock()
    page.set_clipboard = AsyncMock()

    print("Step 1: Instantiating organisations_view...")
    view = await organisations_view(page)
    assert view.route == "/organisations"
    print("  [OK] View instantiated cleanly.")

    print("Step 2: Mocking network and calling show_dashboard...")
    with patch("src.org_view.get_organisation_members", AsyncMock(return_value=mock_members)), \
         patch("src.org_view.get_organisation_courses", AsyncMock(return_value=mock_courses)), \
         patch("src.org_view.get_org_playlists", AsyncMock(return_value=mock_playlists)):

        # Content socket is inside view.controls[0].content
        content_socket = view.controls[0].content
        
        # In organisations_view, fetch_org_status was registered via page.run_task
        assert len(page.run_task.call_args_list) > 0
        fetch_task = page.run_task.call_args_list[0][0][0]
        
        with patch("src.org_view.get_my_organisation", AsyncMock(return_value=mock_org_data)):
            await fetch_task()

        dashboard_col = content_socket.content
        assert isinstance(dashboard_col, ft.Column), f"Expected Column, got {type(dashboard_col)}"
        print("  [OK] Dashboard view rendered into content socket!")
        
        # Check controls
        hero_card = dashboard_col.controls[0]
        body_container = dashboard_col.controls[1]
        print("  [OK] Hero card and body container found.")

        # Check bento cards
        bento_row = body_container.content.controls[0]
        print(f"  [OK] Bento row contains {len(bento_row.controls)} stat cards.")
        assert len(bento_row.controls) == 4

        # Check tab buttons
        tab_buttons = body_container.content.controls[2]
        print(f"  [OK] Tab buttons row contains {len(tab_buttons.controls)} tabs.")
        assert len(tab_buttons.controls) == 4

        # Verify switching to each tab
        print("Step 3: Testing tab switching across all 4 tabs...")
        # Tab 1: Members (index 1)
        tab_buttons.controls[1].on_click(None)
        print("  [OK] Switched to Members tab successfully.")

        # Tab 2: Playlists (index 2)
        tab_buttons.controls[2].on_click(None)
        print("  [OK] Switched to Playlists tab successfully.")

        # Tab 3: Organization Details (index 3)
        tab_buttons.controls[3].on_click(None)
        print("  [OK] Switched to Organization Details tab successfully.")

        # Tab 0: Courses (index 0)
        tab_buttons.controls[0].on_click(None)
        print("  [OK] Switched back to Courses tab successfully.")

    print("\nALL VERIFICATION TESTS COMPLETED SUCCESSFULLY WITH 0 ERRORS!")

if __name__ == "__main__":
    asyncio.run(verify_org_dashboard())
