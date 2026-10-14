import sys
sys.path.insert(0, ".")
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import flet as ft

from src.course_builder import (
    course_builder_view,
    LESSON_TYPES,
    ensure_lesson_shape,
    ensure_module_shape,
    render_lesson_preview,
    validate_lesson,
)

class MockPage:
    def __init__(self, width=1200, height=800):
        self.width = width
        self.height = height
        self.overlay = []
        self.controls = []
        self.shared_preferences = MagicMock()
        fut = asyncio.Future()
        fut.set_result("fake-token")
        self.shared_preferences.get = MagicMock(return_value=fut)
        self.session = MagicMock()
        self.session.store = {"current_user": {"name": "Instructor", "role": "instructor"}}
        self.on_resize = None
        self.on_resized = None
        self.window = MagicMock()
        self.window.width = 1200
        self.route = "/courses/c100/build"

    def update(self):
        pass

    def go(self, route):
        pass

    def run_task(self, handler, *args, **kwargs):
        pass

async def test_all():
    print("Testing course_builder deep execution...")
    page = MockPage()

    sample_modules = [
        {
            "id": "mod_1",
            "title": "Module 1: Foundations",
            "lessons": [
                {"id": "l_vid", "title": "Video Lesson", "type": "video", "content": {"video_url": "https://example.com/v.mp4", "file_name": "v.mp4", "accompanying_text": "Notes"}},
                {"id": "l_aud", "title": "Audio Lesson", "type": "audio", "content": {"audio_path": "https://example.com/a.mp3", "file_name": "a.mp3", "accompanying_text": "Notes"}},
                {"id": "l_doc", "title": "Doc Lesson", "type": "document", "content": {"document_url": "https://example.com/d.pdf", "file_name": "d.pdf", "accompanying_text": "Notes"}},
                {"id": "l_txt", "title": "Text Lesson", "type": "text", "content": {"text": "# Markdown text"}},
                {"id": "l_crd", "title": "Cards Lesson", "type": "cards", "content": {"cards": [{"front": "Q1", "back": "A1"}, {"front": "Q2", "back": "A2"}]}},
                {"id": "l_ass", "title": "Assessment Lesson", "type": "assessment", "content": {"questions": [{"prompt": "Question 1", "choices": ["A", "B"], "answer": "A"}]}},
                {"id": "l_scn", "title": "Scenario Lesson", "type": "scenario", "content": {"scenario": "A branching dilemma", "choices": [{"text": "Choice 1", "consequence": "Consequence 1"}, {"text": "Choice 2", "consequence": "Consequence 2"}]}},
            ]
        }
    ]

    with patch("src.course_builder.get_courses", new_callable=AsyncMock) as mock_get_c, \
         patch("src.course_builder.get_course_curriculum", new_callable=AsyncMock) as mock_get_curr:
        mock_get_c.return_value = [{"id": "c100", "name": "Deep Learning Course"}]
        mock_get_curr.return_value = {"modules": sample_modules}

        # First test preview rendering for all types
        print("Testing render_lesson_preview for each lesson type...")
        for lesson in sample_modules[0]["lessons"]:
            preview_col = render_lesson_preview(lesson, page)
            assert isinstance(preview_col, ft.Column)
        print("-> Preview rendering OK!")

        # Now test view instantiation
        print("Testing course_builder_view instantiation...")
        try:
            view = await course_builder_view(page, course_id="c100")
            print("-> course_builder_view instantiated successfully!")
        except Exception as e:
            print(f"FAILED during course_builder_view: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return

        # Next test interactions
        safe_area = view.controls[0]
        stack = safe_area.content
        row = stack.controls[0]
        curriculum_container = row.controls[0]
        editor_panel = row.controls[1]
        preview_overlay = stack.controls[1]

        curriculum_col = curriculum_container.content
        header_card = curriculum_col.controls[0]
        actions_card = curriculum_col.controls[1]
        module_card = curriculum_col.controls[2]
        mod_content = module_card.content
        lessons_col = mod_content.controls[1]

        print(f"Testing opening editor for each of {len(lessons_col.controls)} lessons...")
        for idx, l_card in enumerate(lessons_col.controls):
            l_type = sample_modules[0]["lessons"][idx]["type"]
            print(f"Clicking lesson card {idx} ({l_type})...")
            l_card.on_click(None)
            assert editor_panel.visible is True

            # Inspect editor controls
            editor_scroll_col = editor_panel.content.controls[1].content
            print(f"Editor controls rendered for {l_type}: {len(editor_scroll_col.controls)}")

        # Test text block formatting buttons
        print("Testing text editor formatting buttons...")
        # Open text lesson (idx 3)
        lessons_col.controls[3].on_click(None)
        editor_scroll_col = editor_panel.content.controls[1].content
        # Find the text_block column
        text_section = editor_scroll_col.controls[2]  # Section 0 is Navigation, 1 is Title, 2 is text block
        text_col = text_section.content.controls[1]
        fmt_bar = text_col.controls[0]
        status_lbl = text_col.controls[1]
        txt_input = text_col.controls[2]
        prev_container = text_col.controls[3]
        
        btn_row = fmt_bar.controls[1]
        print(f"Formatting buttons available: {len(btn_row.controls)}")
        assert len(btn_row.controls) >= 9, f"Expected at least 9 formatting buttons, got {len(btn_row.controls)}"
        
        # Test Bold button (index 1)
        bold_btn = btn_row.controls[1]
        print(f"Clicking Bold button... Initial text: {txt_input.value}")
        bold_btn.on_click(None)
        print(f"Text after bold click: {txt_input.value}")
        assert "**" in txt_input.value, "Bold syntax was not added"
        assert "bold" in status_lbl.value.lower(), f"Status feedback missing: {status_lbl.value}"
        
        # Test Underline button (index 3)
        underline_btn = btn_row.controls[3]
        underline_btn.on_click(None)
        print(f"Text after underline click: {txt_input.value}")
        assert "<u>" in txt_input.value, "Underline syntax was not added"

        # Verify Module more_menu items are ft.Text controls
        header_row = module_card.content.controls[0]
        more_menu = header_row.controls[4]
        for item in more_menu.items:
            assert isinstance(item.content, ft.Text), f"PopupMenuItem content must be ft.Text, got {type(item.content)}"
        print("-> Module more_menu PopupMenuItems correctly use ft.Text controls!")

        print("Testing Add Lesson picker...")
        add_lesson_btn = module_card.content.controls[2]
        add_lesson_btn.on_click(None)

        print("Testing Action Buttons on dedicated actions_card tile...")
        actions_row = actions_card.content
        add_mod_btn = actions_row.controls[0]
        ai_draft_btn = actions_row.controls[1]
        preview_btn = actions_row.controls[2]
        publish_btn = actions_row.controls[3]
        assert "Course" in publish_btn.text, f"Unexpected publish button text: {publish_btn.text}"
        print(f"Publish/Update button label: {publish_btn.text}")

        ai_draft_btn.on_click(None)

        print("Testing Add Module dialog...")
        add_mod_btn.on_click(None)

        print("Testing Full Preview dialog...")
        preview_btn.on_click(None)

        print("ALL TESTS COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test_all())
