import asyncio
import sys
import flet as ft
from unittest.mock import MagicMock, AsyncMock, patch

sys.path.insert(0, ".")

async def test_member_profile():
    from src.member_profile import member_profile_view
    
    mock_page = MagicMock(spec=ft.Page)
    mock_page.theme_mode = ft.ThemeMode.DARK
    mock_page.width = 800
    mock_page.height = 600
    mock_page.shared_preferences = AsyncMock()
    mock_page.shared_preferences.get = AsyncMock(return_value="mock_token")
    mock_page.go = MagicMock()
    mock_page.update = MagicMock()
    mock_page.run_task = MagicMock()
    mock_page.views = []

    mock_user_data = {
        "id": "user_abc_123",
        "first_name": "John",
        "last_name": "Doe",
        "username": "johndoe",
        "email": "john@example.com"
    }

    with patch("src.member_profile.get_member_profile", new=AsyncMock(return_value=mock_user_data)):
        view = await member_profile_view(mock_page, "user_abc_123")
        assert isinstance(view, ft.View)
        
        load_func = mock_page.run_task.call_args[0][0]
        await load_func()
        
        def find_buttons(ctrl):
            btns = []
            if isinstance(ctrl, ft.FilledButton):
                btns.append(ctrl)
            if hasattr(ctrl, "content") and ctrl.content:
                btns.extend(find_buttons(ctrl.content))
            if hasattr(ctrl, "controls") and ctrl.controls:
                for c in ctrl.controls:
                    btns.extend(find_buttons(c))
            return btns
        
        buttons = find_buttons(view)
        # Check every button with an on_click
        clickable = [b for b in buttons if b.on_click]
        assert len(clickable) > 0
        for b in clickable:
            b.on_click(None)
        
        mock_page.go.assert_called_with("/nu-chat?dm=user_abc_123")
        print("All buttons clicked and /nu-chat?dm=user_abc_123 route verified successfully!")

if __name__ == "__main__":
    asyncio.run(test_member_profile())
