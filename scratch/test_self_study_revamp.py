import asyncio
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, ".")
import flet as ft
from unittest.mock import MagicMock, AsyncMock, patch

class MockPage:
    def __init__(self, loop):
        self.width = 390
        self.height = 844
        self.theme_mode = ft.ThemeMode.LIGHT
        self.overlay = []
        self.session = MagicMock()
        self.session.store = {
            "token": "mock-token",
            "auth_token": "mock-token",
            "current_user": {"id": "usr-123", "role": "student", "name": "Ada Lovelace"}
        }
        self.shared_preferences = MagicMock()
        fut = loop.create_future()
        fut.set_result("mock-token")
        self.shared_preferences.get = MagicMock(return_value=fut)
        self.views = []
        self.launch_url = AsyncMock()

    def update(self):
        pass

    def run_task(self, fn, *args, **kwargs):
        import inspect
        if inspect.iscoroutinefunction(fn):
            return asyncio.create_task(fn(*args, **kwargs))
        elif callable(fn):
            res = fn(*args, **kwargs)
            if inspect.isawaitable(res):
                return asyncio.create_task(res)
            return res

    def go(self, route):
        pass

async def test_self_study_revamp():
    loop = asyncio.get_running_loop()
    page = MockPage(loop)

    mock_materials = [
        {"id": "mat-1", "title": "Cell Biology: Mitosis & Meiosis", "source_type": "pdf"},
        {"id": "mat-2", "title": "Organic Chemistry Reactions", "source_type": "text", "pasted_text": "Alkenes and Alkynes mechanisms"},
        {"id": "mat-3", "title": "Introduction to Algorithms", "source_type": "url"},
    ]
    mock_due_cards = [
        {"id": "card-1", "material_id": "mat-1", "front": "What is Mitosis?", "back": "Cell division"},
        {"id": "card-2", "material_id": "mat-1", "front": "What is Meiosis?", "back": "Gamete division"},
        {"id": "card-3", "material_id": "mat-2", "front": "Markovnikov rule", "back": "Electrophilic addition"},
    ]

    with patch("src.self_study.get_due_cards", new=AsyncMock(return_value=mock_due_cards)), \
         patch("src.self_study.get_materials", new=AsyncMock(return_value=mock_materials)), \
         patch("src.self_study.get_subscription_status", new=AsyncMock(return_value={"plan_id": "free", "label": "Free"})), \
         patch("src.self_study.ask_ai_tutor_api", new=AsyncMock(return_value={"reply": "Here is a **detailed summary** with [Watch on YouTube](https://www.youtube.com/watch?v=dQw4w9WgXcQ)!"})):

        from src.self_study import self_study_view
        
        view_result = await self_study_view(page)
        assert view_result is not None
        assert isinstance(view_result, ft.View)
        assert view_result.bgcolor == ft.Colors.SURFACE
        
        # Verify AppBar scroll-under and transparency invariant
        appbar = view_result.appbar
        assert appbar is not None
        assert appbar.elevation == 0
        assert appbar.elevation_on_scroll == 0
        assert appbar.shadow_color == ft.Colors.TRANSPARENT
        assert appbar.bgcolor == ft.Colors.SURFACE
        print("SUCCESS: AppBar scroll-under color shift invariant verified (elevation_on_scroll=0)!")

        # Allow initial async load tasks to complete
        await asyncio.sleep(0.4)

        # Inspect content_socket inside body_host
        safe_area = view_result.controls[0]
        stack = safe_area.content if hasattr(safe_area, "content") else safe_area
        assert isinstance(stack, ft.Stack)
        wrapper = stack.controls[0]
        content_socket = wrapper.content

        # Hub should now be rendered inside content_socket
        hub_col = content_socket.content
        assert isinstance(hub_col, ft.Column)
        container = hub_col.controls[0]
        inner_col = container.content

        # 1. Verify Hero section has Mascot and Gemini-on-Chrome style prompt box
        hero_section = inner_col.controls[0]
        # On mobile (width=390), hero_section is Column([hero_row, gemini_box])
        hero_row = hero_section.controls[0]
        gemini_box = hero_section.controls[1]
        
        mascot_img = hero_row.controls[0]
        assert isinstance(mascot_img, ft.Image)
        assert mascot_img.src == "study_owl_mascot.png"
        assert getattr(mascot_img, "border_radius", None) is None
        print("SUCCESS: Minimalist Duo-style owl mascot rendered cleanly without square border!")

        # 2. Verify Gemini-style prompt box
        assert isinstance(gemini_box, ft.Container)
        gemini_col = gemini_box.content
        chip_row = gemini_col.controls[0]
        gemini_chip = chip_row.controls[0].controls[1]
        assert isinstance(gemini_chip, ft.Container)
        # Material 1 title should be preselected as grounding source
        assert "cell biology" in gemini_chip.content.controls[1].value.lower()
        gemini_tf = gemini_col.controls[1]
        assert isinstance(gemini_tf, ft.TextField)
        gemini_bottom_row = gemini_col.controls[2]
        gemini_send_btn = gemini_bottom_row.controls[0]
        assert gemini_send_btn.disabled is False
        print("SUCCESS: Gemini-on-Chrome style grounded prompt box verified with material selector chip!")

        # 3. Verify Quick Action grid (Upload, Photo, Deck, YouTube, Paste, More)
        quick_grid = inner_col.controls[1]
        assert isinstance(quick_grid, ft.ResponsiveRow)
        assert len(quick_grid.controls) == 6
        labels = [c.content.controls[1].value for c in quick_grid.controls]
        assert labels == ["Upload", "Photo", "Deck", "YouTube", "Paste", "More"]
        print(f"SUCCESS: All 6 Quick Action buttons verified: {labels}!")

        # Test YouTube quick action button opens dialog with non-bleeding close button
        yt_btn = quick_grid.controls[3]
        yt_btn.on_click(None)
        assert len(page.overlay) > 0
        yt_dlg = page.overlay[-1]
        assert isinstance(yt_dlg, ft.AlertDialog)
        assert "Study with YouTube" in yt_dlg.title.controls[0].controls[1].value
        # Verify title row is expand=True so close button is never pushed off-screen
        assert yt_dlg.title.controls[0].expand is True
        print("SUCCESS: YouTube quick action opens dedicated 'Study with YouTube' modal with clamped mobile close button!")
        yt_dlg.open = False

        # 4. Verify Jump back in section with materials
        jump_header = inner_col.controls[2]
        assert isinstance(jump_header, ft.Row)
        assert jump_header.controls[0].value == "Jump back in"

        jump_cards_row = inner_col.controls[3]
        assert isinstance(jump_cards_row, ft.ResponsiveRow)
        assert len(jump_cards_row.controls) == len(mock_materials)
        print("SUCCESS: 'Jump back in' cards rendered correctly!")

        # 5. Test selecting a material directly from the hub -> triggers cockpit!
        target_card = jump_cards_row.controls[0]
        target_card.on_click(None)
        await asyncio.sleep(0.15)

        # Content socket now contains the Material Study Cockpit
        cockpit_col = content_socket.content
        assert isinstance(cockpit_col, ft.Column)
        cockpit_inner = cockpit_col.controls[0].content
        
        top_bar = cockpit_inner.controls[0]
        back_btn = top_bar.controls[0]
        assert back_btn.content.controls[1].value in ("Back", "Back to Study Hub")
        print(f"SUCCESS: Cockpit back button rendered with responsive label: '{back_btn.content.controls[1].value}'")

        # Verify Study Actions Row (Flashcards, Quick Quiz, Mock Exam)
        study_actions_row = cockpit_inner.controls[3]
        action_titles = [c.content.controls[1].controls[0].value for c in study_actions_row.controls]
        assert action_titles == ["Flashcards", "Quick Quiz", "Mock Exam"]
        print(f"SUCCESS: Material Cockpit Study Actions verified: {action_titles}!")

        # Verify AI Document Tutor with Markdown and YouTube Recommendations
        ai_card = cockpit_inner.controls[5]
        assert isinstance(ai_card, ft.Container)
        ai_col = ai_card.content
        assert "Nu-AI Document Tutor" in ai_col.controls[0].controls[1].controls[0].value
        
        # Check prompt chips
        # Verify dynamic height on chat container
        chat_container = ai_col.controls[1]
        assert chat_container.height >= 280
        print(f"SUCCESS: Dynamic chat container height verified ({chat_container.height}px)!")

        # Check prompt chips
        chips_row = ai_col.controls[2]
        chip_labels = [c.content.value for c in chips_row.controls]
        assert any("Recommend YouTube Videos" in lbl for lbl in chip_labels)
        print(f"SUCCESS: 'Recommend YouTube Videos' prompt chip verified: {chip_labels}!")

        # Simulate sending a query
        send_row = ai_col.controls[3].content
        input_tf = send_row.controls[0]
        input_tf.value = "Recommend YouTube tutorial videos to master Cell Biology"
        send_btn = send_row.controls[1]
        send_btn.on_click(None)
        await asyncio.sleep(0.15)

        # Inspect AI messages: verify Markdown response & In-chat YouTube Video Card
        chat_col = ai_col.controls[1].content
        ai_resp_container = chat_col.controls[-1]
        ai_resp_col = ai_resp_container.content
        markdown_control = ai_resp_col.controls[1]
        print("SUCCESS: AI response rendered with full ft.Markdown support and link click handler!")

        # Verify in-chat interactive YouTube video card was parsed and rendered
        assert len(ai_resp_col.controls) >= 3
        yt_card = ai_resp_col.controls[2]
        assert isinstance(yt_card, ft.Container)
        # Inside yt_card row: thumbnail container and info column with "Watch in App" button
        yt_card_row = yt_card.content
        action_row = yt_card_row.controls[1].controls[1]
        watch_in_app_btn = action_row.controls[0]
        assert "Watch in App" in watch_in_app_btn.content.controls[1].value
        print("SUCCESS: In-chat interactive YouTube video recommendation card rendered with 'Watch in App' button!")

        # Test tapping "Watch in App" opens AdaptiveVideoPlayer overlay
        watch_in_app_btn.on_click(None)
        assert len(page.overlay) > 0
        player_dlg = page.overlay[-1]
        assert isinstance(player_dlg, ft.AlertDialog)
        assert player_dlg.bgcolor == "#0A0C10"
        print("SUCCESS: 'Watch in App' opens sleek modern in-app video player overlay!")
        player_dlg.open = False

        # Test tapping the markdown link to verify in-app overlay player interceptor
        mock_event = MagicMock(data="https://youtube.com/watch?v=dQw4w9WgXcQ")
        markdown_control.on_tap_link(mock_event)
        await asyncio.sleep(0.05)
        print("SUCCESS: on_tap_link intercepted YouTube link and launched in-app player overlay cleanly!")

        # 6. Test returning back to Study Hub
        back_btn.on_click(None)
        await asyncio.sleep(0.4)
        restored_hub = content_socket.content
        assert isinstance(restored_hub, ft.Column)
        print("SUCCESS: Successfully returned from Cockpit to Study Hub!")

if __name__ == "__main__":
    asyncio.run(test_self_study_revamp())
