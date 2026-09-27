import asyncio
import os
import sys
sys.path.insert(0, os.path.abspath("."))
import flet as ft
from unittest.mock import MagicMock
from scratch.test_admin_and_profile_views import MockPage
from src.platform_admin_view import platform_admin_view

async def test_cards_rendering():
    mock_page = MockPage()
    mock_page.session.store.set("platform_admin_token", "test_tok")
    mock_page.session.store.set("platform_admin_user", {"username": "admin", "role": "Admin"})

    view = await platform_admin_view(mock_page)

    # Let's inspect the controls inside the view
    main_c = view.controls[0]
    dash_col = main_c.content
    header_bar = dash_col.controls[0]
    nav_container = dash_col.controls[1]
    active_content = dash_col.controls[2]

    # Verify initial tab is overview
    assert active_content.content is not None
    print("Initial tab rendered.")

    print("Success: UI assembled without any runtime AttributeErrors!")

if __name__ == "__main__":
    asyncio.run(test_cards_rendering())
