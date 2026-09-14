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

async def test_live_view():
    page = MagicMock(spec=ft.Page)
    page.width = 1200
    page.height = 800
    page.session = MagicMock()
    page.session.store = {
        "current_user": {"id": "owner-1234-uuid", "role": "OWNER"}
    }
    page.shared_preferences = MagicMock()
    page.shared_preferences.get = AsyncMock(return_value="mock_jwt_token")
    page.show_dialog = MagicMock()
    page.go = MagicMock()
    page.update = MagicMock()
    page.launch_url = AsyncMock()
    page.set_clipboard = AsyncMock()
    page.overlay = []

    with patch("src.org_view.get_my_organisation", new=AsyncMock(return_value=mock_org)), \
         patch("src.org_view.get_organisation_members", new=AsyncMock(return_value=mock_members)), \
         patch("src.org_view.get_organisation_courses", new=AsyncMock(return_value=mock_courses)), \
         patch("src.org_view.get_org_playlists", new=AsyncMock(return_value=mock_playlists)):

        view = await organisations_view(page)
        assert isinstance(view, ft.View)
        print("Organisations view created successfully with title:", view.appbar.title.value if hasattr(view.appbar, 'title') else "Custom")
        
        # Verify socket content has loaded the dashboard
        socket = view.controls[0]
        # Let's see what's in socket.content
        assert socket.content is not None
        print("Socket content loaded successfully:", type(socket.content))
        print("SUCCESS! All checks passed.")

if __name__ == "__main__":
    asyncio.run(test_live_view())
