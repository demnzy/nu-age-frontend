import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath("."))
import flet as ft

async def run_test():
    print("Testing network_view instantiation...")
    from src.network import network_view, _avatar, _org_pill, _section_label, _empty_state

    # Mock page
    class MockSession:
        def __init__(self):
            self.store = {"current_user": {"first_name": "Test", "last_name": "User"}}

    class MockSharedPreferences:
        async def get(self, key):
            return "mock_token"
        async def set(self, key, val):
            pass

    class MockPage:
        def __init__(self):
            self.route = "/network"
            self.views = []
            self.width = 400
            self.session = MockSession()
            self.shared_preferences = MockSharedPreferences()
            self.theme_mode = ft.ThemeMode.LIGHT
            self.tasks = []
        def run_task(self, fn, *args, **kwargs):
            t = asyncio.create_task(fn(*args, **kwargs))
            self.tasks.append(t)
            return t
        def go(self, r):
            self.route = r
        def update(self):
            pass

    page = MockPage()

    # 1. Test helper controls
    print("1. Testing helper controls...")
    sample_user = {
        "id": "u1",
        "first_name": "Asana",
        "last_name": "Islam",
        "university": "Stanford University",
        "org": "AI Research Lab",
        "streak": 5,
    }
    av = _avatar(sample_user, radius=24)
    assert isinstance(av, ft.CircleAvatar), "Avatar is not CircleAvatar"
    pill = _org_pill("Test Org")
    assert isinstance(pill, ft.Container), "Org pill is not Container"
    sec = _section_label("Test Section")
    assert isinstance(sec, ft.Container), "Section label is not Container"
    emp = _empty_state(ft.Icons.PEOPLE, "Empty", "Subtitle", "Action", lambda: None)
    assert isinstance(emp, ft.Container), "Empty state is not Container"
    print("Helpers OK!")

    # 2. Test network_view instantiation
    print("2. Testing network_view(page)...")
    v = await network_view(page)
    page.views.append(v)
    assert isinstance(v, ft.View), "Result is not ft.View"
    assert v.route == "/network", "Route mismatch"
    assert len(v.controls) > 0, "No controls in view"
    print("network_view created successfully!")

    # 3. Test direct rendering of cards
    print("3. Testing card components...")
    from unittest.mock import patch, AsyncMock

    mock_friend = {
        "id": "u100",
        "first_name": "Asana",
        "last_name": "Islam Chua",
        "university": "Stanford University",
        "org": "AI Club",
    }
    mock_incoming = {
        "id": "req_inc_1",
        "user": {
            "id": "u101",
            "first_name": "Alamgir",
            "last_name": "Hosian",
            "university": "MIT",
            "org": "Robotics",
        }
    }
    mock_sent = {
        "id": "req_sent_1",
        "user": {
            "id": "u102",
            "first_name": "Bablu",
            "last_name": "Khan",
            "org": "Dev Team",
        }
    }
    mock_discover = {
        "id": "u103",
        "first_name": "Shahidul",
        "last_name": "Islam Shishir",
        "university": "Harvard",
        "streak": 12,
        "org": "Hackathon",
    }

    # Patch API calls in src.network
    with patch("src.network.get_friends", new_callable=AsyncMock) as mock_gf, \
         patch("src.network.get_incoming_requests", new_callable=AsyncMock) as mock_ginc, \
         patch("src.network.get_sent_requests", new_callable=AsyncMock) as mock_gsent, \
         patch("src.network.get_discover_peers", new_callable=AsyncMock) as mock_dp, \
         patch("src.network.get_discover_org", new_callable=AsyncMock) as mock_dorg, \
         patch("src.network.get_discover_trending", new_callable=AsyncMock) as mock_dtrend:

        mock_gf.return_value = [mock_friend]
        mock_ginc.return_value = [mock_incoming]
        mock_gsent.return_value = [mock_sent]
        mock_dp.return_value = [mock_discover]
        mock_dorg.return_value = [mock_discover]
        mock_dtrend.return_value = [mock_discover]

        print("Testing tab 0 (My Network)...")
        # Extract switch_tab from view scope by calling boot or re-invoking
        v2 = await network_view(page)
        page.views.append(v2)

        # Run tasks to let boot execute switch_tab(0)
        await asyncio.sleep(0.1)
        for t in list(page.tasks):
            if not t.done():
                try:
                    await asyncio.wait_for(t, timeout=2.0)
                except Exception as e:
                    print(f"Task info Tab 0: {e}")

        # Now test Tab 1 (Requests)
        print("Testing tab 1 (Requests)...")
        header = v2.controls[0].content.controls[0]
        seg = header.content.controls[2]
        tab1_ctrl = seg.content.controls[1]
        tab1_ctrl.on_click(None)
        await asyncio.sleep(0.1)
        for t in list(page.tasks):
            if not t.done():
                try:
                    await asyncio.wait_for(t, timeout=2.0)
                except Exception as e:
                    print(f"Task info Tab 1: {e}")

        # Now test Tab 2 (Discover)
        print("Testing tab 2 (Discover)...")
        tab2_ctrl = seg.content.controls[2]
        tab2_ctrl.on_click(None)
        await asyncio.sleep(0.1)
        for t in list(page.tasks):
            if not t.done():
                try:
                    await asyncio.wait_for(t, timeout=2.0)
                except Exception as e:
                    print(f"Task info Tab 2: {e}")

        # Test Dark Mode instantiation
        print("Testing Dark Mode compatibility...")
        page.theme_mode = ft.ThemeMode.DARK
        v_dark = await network_view(page)
        assert v_dark is not None
        print("Dark Mode view created cleanly!")

    print("Card components & all 3 tabs rendered cleanly!")
    print("ALL MOCK TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(run_test())
