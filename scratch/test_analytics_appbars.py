import asyncio
import flet as ft
from unittest.mock import AsyncMock, MagicMock
from src.course_analytics import course_analytics_view
from src.playlist_analytics import playlist_analytics_view


class MockPage:
    def __init__(self):
        self.views = []
        self.overlay = []
        self.width = 1200
        self.height = 800
        self.route = "/dashboard"
        self.session = MagicMock()
        self.session.store = MagicMock()
        self.session.store.get.return_value = None
        self.shared_preferences = AsyncMock()
        self.shared_preferences.get.return_value = "mock_token"
        self.run_task = MagicMock()
        self.update = MagicMock()
        self.go = MagicMock()


async def main():
    print("Testing Course Analytics and Playlist Analytics app bar structure...")
    page = MockPage()

    # Test course_analytics_view
    course_view = await course_analytics_view(page, org_id="test_org", course_id="test_course")
    assert isinstance(course_view, ft.View), "course_analytics_view should return ft.View"
    assert course_view.bottom_appbar is not None, "course_analytics_view should have bottom_appbar assigned"
    for ctrl in course_view.controls:
        assert not isinstance(ctrl, ft.BottomAppBar), f"Found BottomAppBar inside controls: {ctrl}"
    print("[OK] course_analytics_view has no BottomAppBar in controls, and has bottom_appbar assigned.")

    # Test playlist_analytics_view
    playlist_view = await playlist_analytics_view(page, org_id="test_org", playlist_id="test_playlist")
    assert isinstance(playlist_view, ft.View), "playlist_analytics_view should return ft.View"
    assert playlist_view.bottom_appbar is not None, "playlist_analytics_view should have bottom_appbar assigned"
    for ctrl in playlist_view.controls:
        assert not isinstance(ctrl, ft.BottomAppBar), f"Found BottomAppBar inside controls: {ctrl}"
    print("[OK] playlist_analytics_view has no BottomAppBar in controls, and has bottom_appbar assigned.")

    # Test _strip_redundant_appbars logic
    def _strip_redundant_appbars(controls: list) -> list:
        if not controls:
            return []
        cleaned = []
        for c in controls:
            if isinstance(c, (ft.BottomAppBar, ft.AppBar)):
                continue
            if isinstance(c, ft.Container) and isinstance(getattr(c, "content", None), (ft.BottomAppBar, ft.AppBar)):
                continue
            if isinstance(c, ft.Column) and hasattr(c, "controls") and c.controls:
                c.controls = [child for child in c.controls if not isinstance(child, (ft.BottomAppBar, ft.AppBar))]
            cleaned.append(c)
        return cleaned

    # Test with rogue bottom appbar in controls
    rogue_bar = ft.BottomAppBar(content=ft.Row([ft.Text("Rogue Bar")]))
    normal_content = ft.Container(content=ft.Text("Hello World"))
    wrapped_bar = ft.Container(content=ft.BottomAppBar())
    nested_col = ft.Column(controls=[ft.Text("Inside Column"), ft.BottomAppBar()])

    dirty_controls = [normal_content, rogue_bar, wrapped_bar, nested_col]
    cleaned = _strip_redundant_appbars(dirty_controls)

    assert len(cleaned) == 2, f"Expected 2 controls after stripping, got {len(cleaned)}"
    assert cleaned[0] is normal_content
    assert len(nested_col.controls) == 1, "Rogue bar inside column was not stripped"
    print("[OK] _strip_redundant_appbars correctly stripped rogue and nested app bars from controls.")

    print("\nALL CHECKS PASSED!")


if __name__ == "__main__":
    asyncio.run(main())
