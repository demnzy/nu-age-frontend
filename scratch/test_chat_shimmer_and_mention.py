import asyncio
import sys
import unittest
from unittest.mock import MagicMock, AsyncMock
import flet as ft

# Ensure imports work
sys.path.append(r"c:\Users\Admin\Desktop\Code\NU-Front")

from src.chat_view import chat_view
from src.components.shimmer_skeletons import collect_shimmer_boxes

class DummyPage:
    def __init__(self, theme_mode=ft.ThemeMode.DARK):
        self.theme_mode = theme_mode
        self.width = 1000
        self.route = "/nu-chat"
        self.overlay = []
        self.controls = []
        self.tasks = []
        self.shared_preferences = AsyncMock()
        self.shared_preferences.get = AsyncMock(return_value="test_token")
        self.shared_preferences.set = AsyncMock()
        self.update = MagicMock()

    def run_task(self, handler, *args, **kwargs):
        self.tasks.append((handler, args, kwargs))

async def run_tests():
    print("=== Testing Chat View WhatsApp Shimmer Skeleton & Mention Autocomplete ===")

    # Test 1: Dark Mode Chat View Instantiation
    page_dark = DummyPage(theme_mode=ft.ThemeMode.DARK)
    view_dark = await chat_view(page_dark)
    assert isinstance(view_dark, ft.View), "view_dark should be a ft.View"
    print("Test 1 Passed: Dark mode view instantiated cleanly.")

    # Test 2: Light Mode Chat View Instantiation
    page_light = DummyPage(theme_mode=ft.ThemeMode.LIGHT)
    view_light = await chat_view(page_light)
    assert isinstance(view_light, ft.View), "view_light should be a ft.View"
    print("Test 2 Passed: Light mode view instantiated cleanly.")

    # Find chat_list_panel and chat_list_scroll_col
    # Controls hierarchy: SafeArea -> Row -> [chat_list_panel, active_chat_panel]
    safe_area = view_dark.controls[0]
    row = safe_area.content
    chat_list_panel, active_chat_panel = row.controls[0], row.controls[1]
    chat_list_ui = chat_list_panel.content.controls[0]
    chat_list_scroll_col = chat_list_ui.controls[1]

    # Test 3: Verify WhatsApp Shimmer Skeleton on Initial Load
    # Initially is_loading_channels is True, so chat_list_scroll_col should contain 7 skeletons
    assert len(chat_list_scroll_col.controls) == 7, f"Expected 7 skeleton items, got {len(chat_list_scroll_col.controls)}"
    
    total_boxes = 0
    for idx, item in enumerate(chat_list_scroll_col.controls):
        boxes = collect_shimmer_boxes(item)
        assert len(boxes) >= 4, f"Skeleton {idx} should have at least 4 shimmer boxes (avatar, name, time, msg)"
        total_boxes += len(boxes)
    assert total_boxes >= 28, f"Expected at least 28 shimmer boxes across 7 items, got {total_boxes}"
    print(f"Test 3 Passed: 7 WhatsApp shimmer skeleton items rendered with {total_boxes} pulsing shimmer boxes.")

    # Test 4: Run fetch_initial_data with empty cache to test clean zero state
    import src.chat_view as cv_mod
    original_get_cached = cv_mod.get_cached_chat_channels
    original_get_channels = cv_mod.get_user_channels
    try:
        cv_mod.get_cached_chat_channels = lambda p: []
        cv_mod.get_user_channels = AsyncMock(return_value=[])

        fetch_task = next((t[0] for t in page_dark.tasks if t[0].__name__ == "fetch_initial_data"), None)
        assert fetch_task is not None, "fetch_initial_data task should be registered on page"
        await fetch_task()

        # Since mock returns no channels, it should transition to clean zero state
        assert len(chat_list_scroll_col.controls) == 1, f"Expected 1 zero-state container, got {len(chat_list_scroll_col.controls)}"
        zero_container = chat_list_scroll_col.controls[0]
        zero_col = zero_container.content
        texts = [c.value for c in zero_col.controls if isinstance(c, ft.Text)]
        assert "No chats yet" in texts, f"Expected 'No chats yet' in zero state, got {texts}"
        print("Test 4 Passed: Zero state cleanly transitions with no heavy green borders or dummy tiles.")
    finally:
        cv_mod.get_cached_chat_channels = original_get_cached
        cv_mod.get_user_channels = original_get_channels

    # Test 5: Verify Active Chat selection styling (neutral background, border=None)
    # Re-run fetch with the real SQLite cached channels
    await fetch_task()
    assert len(chat_list_scroll_col.controls) > 0, "Expected cached channels to be rendered"
    tile1 = chat_list_scroll_col.controls[0]
    assert tile1.border is None, f"Expected inactive tile border=None, got {tile1.border}"
    assert tile1.bgcolor == ft.Colors.TRANSPARENT, f"Expected inactive tile bgcolor=TRANSPARENT, got {tile1.bgcolor}"
    print(f"Test 5 Passed: {len(chat_list_scroll_col.controls)} channels rendered with border=None and transparent bgcolor.")

    # Find load_active_chat from tile click handler closure
    tile_click = tile1.on_click
    load_active_chat_fn = None
    for cell in tile_click.__closure__:
        val = cell.cell_contents
        if callable(val) and getattr(val, "__name__", "") == "load_active_chat":
            load_active_chat_fn = val
            break

    assert load_active_chat_fn is not None, "load_active_chat should be reachable from tile click"
    # Load first chat with valid channel id
    first_cid = "54578e7d-a7f4-40ca-a10a-bab6cb421305"
    await load_active_chat_fn(first_cid)

    # Now verify active tile styling: NO green border, neutral #262626
    tile1_active = chat_list_scroll_col.controls[0]
    assert tile1_active.border is None, f"Expected active tile border=None (no green border), got {tile1_active.border}"
    assert tile1_active.bgcolor == "#262626", f"Expected active tile bgcolor='#262626', got {tile1_active.bgcolor}"
    print("Test 6 Passed: Active chat tile rendered with border=None and sleek neutral #262626 background.")

    # Test 7: Verify Mention Autocomplete typing '@' without NameError
    active_layout = active_chat_panel.content
    assert isinstance(active_layout, ft.Column), "Active chat layout should be a Column"
    composer_stack = active_layout.controls[2]
    autocomplete_card = composer_stack.controls[0]
    composer_container = composer_stack.controls[1]
    input_bubble = composer_container.content.controls[1]
    msg_input = input_bubble.content

    # Populate candidate members list in load_active_chat closure
    for cell in load_active_chat_fn.__closure__:
        val = cell.cell_contents
        if isinstance(val, list) and not isinstance(val, (str, bytes)):
            val.append({"id": "user_42", "username": "alice_co", "name": "Alice Cooper", "profile_picture_url": "https://example.com/p.jpg"})
            val.append({"id": "user_43", "username": "bob_mentor", "name": "Bob Mentor", "profile_picture_url": None})

    # Trigger on_input_change with '@ali'
    msg_input.value = "@ali"
    event = MagicMock(control=msg_input, data="@ali")
    msg_input.on_change(event)

    # Check autocomplete_card is visible and contains matched member tiles
    assert autocomplete_card.visible is True, "autocomplete_card should be visible after typing '@ali'"
    autocomplete_list = autocomplete_card.content
    assert len(autocomplete_list.controls) > 0, "autocomplete_list should contain matched member tiles"
    print("Test 7 Passed: Mention autocomplete triggered successfully with @ali, avatar rendered with NO NameError.")

    print("\nALL 7 TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(run_tests())
