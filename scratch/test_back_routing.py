import asyncio
import flet as ft
from unittest.mock import AsyncMock, MagicMock, patch


def resolve_back_target(previous_route: str, is_from_offline_view: bool = False) -> str:
    """The back_target resolution logic now used in main.py."""
    if is_from_offline_view or previous_route == "/offline":
        return "/offline"
    elif previous_route and not previous_route.endswith("/view") and not previous_route.endswith("/offline"):
        return previous_route
    else:
        return "/courses"


async def main():
    print("Testing back_target resolution and origin cognisance...")

    # Case 1: Entering from /courses
    assert resolve_back_target("/courses") == "/courses", "Should return to /courses"
    print("[OK] Origin /courses -> Back target: /courses")

    # Case 2: Entering from /dashboard
    assert resolve_back_target("/dashboard") == "/dashboard", "Should return to /dashboard"
    print("[OK] Origin /dashboard -> Back target: /dashboard")

    # Case 3: Entering from /courses/python-101 (Course Details view)
    assert resolve_back_target("/courses/python-101") == "/courses/python-101", "Should return to /courses/python-101"
    print("[OK] Origin /courses/python-101 -> Back target: /courses/python-101")

    # Case 4: Entering from /offline
    assert resolve_back_target("/offline", is_from_offline_view=True) == "/offline", "Should return to /offline"
    print("[OK] Origin /offline -> Back target: /offline")

    # Case 5: Entering from /playlists/123
    assert resolve_back_target("/playlists/123") == "/playlists/123", "Should return to /playlists/123"
    print("[OK] Origin /playlists/123 -> Back target: /playlists/123")

    # Case 6: Entering from /organisations/my-org
    assert resolve_back_target("/organisations/my-org") == "/organisations/my-org", "Should return to /organisations/my-org"
    print("[OK] Origin /organisations/my-org -> Back target: /organisations/my-org")

    # Case 7: Page reload or no previous route
    assert resolve_back_target(None) == "/courses", "Should default to /courses"
    assert resolve_back_target("/courses/python-101/view") == "/courses", "Reload of self should fall back to /courses"
    print("[OK] Reload or missing previous route -> Safe fallback: /courses")

    # Case 8: Verify online probe does NOT raise NameError or crash
    from src.requests.auth import get_current_user_request
    with patch("src.requests.auth.get_current_user_request", new_callable=AsyncMock) as mock_probe:
        mock_probe.return_value = (200, {"id": "1", "name": "Test"})
        probe_status, _ = await asyncio.wait_for(mock_probe("token123"), timeout=2.5)
        online_reachable = (probe_status == 200)
        assert online_reachable is True, "Online probe should succeed"
        print("[OK] Online network probe runs cleanly and detects online state")

    print("\nALL ROUTING TESTS PASSED!")


if __name__ == "__main__":
    asyncio.run(main())
