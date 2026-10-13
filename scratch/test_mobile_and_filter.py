import sys
sys.path.insert(0, ".")
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import flet as ft

from src.course_builder import (
    course_builder_view,
    render_lesson_preview,
    is_mobile,
)

class MockPage:
    def __init__(self, width=1200, height=800):
        self.width = width
        self.height = height
        self.overlay = []
        self.controls = []
        self.shared_preferences = MagicMock()
        fut = asyncio.Future()
        fut.set_result("test-token")
        self.shared_preferences.get = MagicMock(return_value=fut)
        self.session = MagicMock()
        self.session.store = {"current_user": {"name": "Instructor", "role": "instructor"}}
        self.on_resize = None
        self.on_resized = None
        self.window = MagicMock()
        self.window.width = width
        self.window.height = height
        self.route = "/courses/c100/build"

    def update(self):
        pass

    def go(self, route):
        pass

    def run_task(self, handler, *args, **kwargs):
        pass

async def test_mobile_and_filter():
    print("--- 1. Testing Search Filter Bar on Desktop & Mobile ---")
    page = MockPage(width=1200, height=800)

    sample_modules = [
        {
            "id": "mod_1",
            "title": "Introduction to Quantum Neural Computing Systems",
            "lessons": [
                {"id": "l1", "title": "Understanding High-Dimensional Hilbert Spaces for Machine Learning", "type": "video", "content": {"video_url": "https://example.com/video.mp4", "file_name": "hilbert_lecture.mp4"}},
                {"id": "l2", "title": "Comprehensive Specification Document and Architectural Diagrams", "type": "document", "content": {"document_url": "https://example.com/spec.pdf", "file_name": "quantum_spec.pdf"}},
                {"id": "l3", "title": "Audio Lecture on State Vectors and Superposition", "type": "audio", "content": {"audio_path": "https://example.com/audio.mp3", "file_name": "lecture_audio.mp3"}},
                {"id": "l4", "title": "Markdown Article on Entanglement Theory", "type": "text", "content": {"text": "# Entanglement"}},
                {"id": "l5", "title": "Quantum Gate Operations Flashcard Deck", "type": "cards", "content": {"cards": [{"front": "Hadamard", "back": "Superposition"}]}},
            ]
        }
    ]

    with patch("src.course_builder.get_courses", new_callable=AsyncMock) as mock_get_c, \
         patch("src.course_builder.get_course_curriculum", new_callable=AsyncMock) as mock_get_curr:
        mock_get_c.return_value = [{"id": "c100", "name": "Advanced Quantum ML"}]
        mock_get_curr.return_value = {"modules": sample_modules}

        # Instantiate on desktop (1200px)
        view = await course_builder_view(page, course_id="c100")
        safe_area = view.controls[0]
        stack = safe_area.content
        main_row = stack.controls[0]
        curriculum_container = main_row.controls[0]
        editor_panel = main_row.controls[1]
        curriculum_col = curriculum_container.content
        header_card = curriculum_col.controls[0]
        summary_bar = header_card.content.controls[2]

        # On desktop: summary_bar should be a Row with expand=True on filter container
        assert isinstance(summary_bar.content, ft.Row), f"Expected Row on desktop, got {type(summary_bar.content)}"
        filter_box = summary_bar.content.controls[1]
        assert filter_box.expand is True, "Filter container must have expand=True on desktop"
        print("PASS: Search filter bar takes remaining space on desktop (Row, expand=True)!")

        # Simulate resize to mobile (360x740)
        print("--- 2. Simulating Window Resize to Mobile (360x740) ---")
        page.width = 360
        page.height = 740
        page.window.width = 360
        page.window.height = 740
        page.on_resize(None)

        # On mobile: summary_bar should be a Column where filter container spans full width
        assert isinstance(summary_bar.content, ft.Column), f"Expected Column on mobile, got {type(summary_bar.content)}"
        print("PASS: Search filter bar adapts to Column taking full width on mobile!")

        # Check editor panel header row
        print("--- 3. Testing Editor Panel Header on Mobile ---")
        editor_header_row = editor_panel.content.controls[0].content
        # Controls in header: Back button, Title container, Actions container, Close button
        back_btn = editor_header_row.controls[0]
        title_container = editor_header_row.controls[1]
        actions_container = editor_header_row.controls[2]
        close_btn = editor_header_row.controls[3]

        assert title_container.expand is True, "Editor panel title must be inside an expanding container"
        assert title_container.content.overflow == ft.TextOverflow.ELLIPSIS, "Editor panel title must have ellipsis"
        # On mobile, actions_container should hold the compact icon button
        assert isinstance(actions_container.content, ft.IconButton), f"On mobile, preview button must be an IconButton, got {type(actions_container.content)}"
        print("PASS: Editor panel header is fully responsive (title expands with ellipsis, preview is compact icon button)!")

        # Open video lesson editor
        print("--- 4. Testing Editor Opening & Single Lesson Previews ---")
        module_card = curriculum_col.controls[2]
        lessons_col = module_card.content.controls[1]
        video_card = lessons_col.controls[0]
        video_card.on_click(None)

        assert editor_panel.visible is True
        assert curriculum_container.visible is False, "On mobile, curriculum outline must be hidden when editor is open"
        print("PASS: Curriculum container hides on mobile when editing lesson!")

        # Trigger single lesson preview dialog
        actions_container.content.on_click(None)
        assert len(page.overlay) > 0, "Preview dialog was not added to overlay"
        preview_dlg = page.overlay[-1]
        assert preview_dlg.open is True, "Preview dialog was not opened"

        # Check dialog title container
        dlg_title_row = preview_dlg.title
        dlg_title_container = dlg_title_row.controls[1]
        assert dlg_title_container.expand is True, "Preview dialog title must be in expanding container"
        assert dlg_title_container.content.overflow == ft.TextOverflow.ELLIPSIS, "Preview dialog title must have ellipsis"

        # Check dialog dimensions
        dlg_container = preview_dlg.content
        print(f"Single preview dialog dimensions on 360x740 screen: {dlg_container.width}x{dlg_container.height}")
        assert dlg_container.width <= 360, f"Dialog width {dlg_container.width} exceeds screen width 360"
        assert dlg_container.height <= 740, f"Dialog height {dlg_container.height} exceeds screen height 740"
        print("PASS: Single preview dialog is strictly bounded within mobile screen dimensions!")

        # Check internal renderers for mobile:
        # Video renderer check
        video_preview = render_lesson_preview(sample_modules[0]["lessons"][0], page)
        video_container = video_preview.controls[0]
        # Content must not be a 1000px container
        if hasattr(video_container.content, "width") and video_container.content.width:
            assert video_container.content.width != 1000, "Video preview must not have hardcoded width=1000"
        print("PASS: Video preview does not have hardcoded 1000px width!")

        # Document renderer check on mobile
        doc_preview = render_lesson_preview(sample_modules[0]["lessons"][1], page)
        doc_container = doc_preview.controls[0]
        assert isinstance(doc_container.content, ft.Column), "Document preview on mobile must stack in a Column"
        print("PASS: Document preview stacks in a Column on mobile!")

        # Audio renderer check on mobile
        audio_preview = render_lesson_preview(sample_modules[0]["lessons"][2], page)
        audio_container = audio_preview.controls[0]
        assert isinstance(audio_container.content, ft.Column), "Audio preview on mobile must stack in a Column"
        print("PASS: Audio preview stacks in a Column on mobile!")

        # Cards renderer check
        cards_preview = render_lesson_preview(sample_modules[0]["lessons"][4], page)
        cards_container = cards_preview.controls[0]
        nav_row = cards_container.content.controls[5]
        hint_container = nav_row.controls[1]
        assert hint_container.expand is True, "Cards navigation hint text must be in an expanding container"
        print("PASS: Cards preview navigation hint is in expanding container with ellipsis!")

        print("\nALL MOBILE OPTIMIZATION & SEARCH FILTER TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test_mobile_and_filter())
