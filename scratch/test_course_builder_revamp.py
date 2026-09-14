import sys
sys.path.insert(0, ".")
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import flet as ft
from src.course_builder import (
    course_builder_view,
    LESSON_TYPES,
    LESSON_TYPE_ICONS,
    LESSON_TYPE_COLORS,
    LESSON_TYPE_DESCRIPTIONS,
    SIDEBAR_WIDTH,
    ensure_lesson_shape,
    ensure_module_shape,
)

class MockPage:
    def __init__(self, width=1200, height=800):
        self.width = width
        self.height = height
        self.overlay = []
        self.views = []
        self.client_storage = MagicMock()
        self.client_storage.get.return_value = "fake-token"
        self.shared_preferences = MagicMock()
        async def mock_sp_get(key):
            return "fake-token"
        self.shared_preferences.get = mock_sp_get
        self.theme_mode = ft.ThemeMode.DARK
        self.route = "/course-builder/test"
        self.session = MagicMock()
        self.session.store = {"current_user": {"name": "Test Instructor", "role": "instructor"}}
        self.on_resized = None

    def update(self):
        pass

    def go(self, route):
        pass

async def run_revamp_verification():
    print("[1/5] Testing Course Builder Studio Desktop Initialization...")
    page = MockPage(width=1200, height=800)

    mock_curriculum = {
        "modules": [
            {
                "id": "mod_1",
                "title": "Module 1: Foundations",
                "lessons": [
                    {"id": "l1", "title": "Intro Video", "type": "video", "content": {"video_url": "https://example.com/video.mp4"}},
                    {"id": "l2", "title": "Lecture Audio", "type": "audio", "content": {"audio_url": "https://example.com/audio.mp3"}},
                    {"id": "l3", "title": "Syllabus Document", "type": "document", "content": {"document_url": "https://example.com/doc.pdf"}},
                    {"id": "l4", "title": "Core Reading", "type": "text", "content": {"text": "# Reading text"}},
                    {"id": "l5", "title": "Flashcard Practice", "type": "cards", "content": {"cards": [{"front": "Front 1", "back": "Back 1"}]}},
                    {"id": "l6", "title": "Quiz Assessment", "type": "assessment", "content": {"questions": [{"prompt": "Question 1", "choices": ["A", "B"], "answer": "B"}]}},
                    {"id": "l7", "title": "Interactive Scenario", "type": "scenario", "content": {"scenario": "A decision to make.", "choices": [{"text": "Choice 1", "feedback": "Feedback 1"}]}},
                ]
            }
        ]
    }

    with patch("src.course_builder.get_courses", new_callable=AsyncMock) as mock_get_courses, \
         patch("src.course_builder.get_course_curriculum", new_callable=AsyncMock) as mock_get_curriculum:
        
        mock_get_courses.return_value = [{"id": "c_123", "name": "Deep Learning Studio"}]
        mock_get_curriculum.return_value = mock_curriculum

        view = await course_builder_view(page, course_id="c_123")
        assert isinstance(view, ft.View)
        assert view.route == "/courses/c_123/build"
        assert view.bottom_appbar is not None
        print("  [OK] ft.View initialized with bottom_appbar and responsive container hierarchy.")

        # Check Layout hierarchy
        safe_area = view.controls[0]
        stack = safe_area.content
        row = stack.controls[0]
        curriculum_container = row.controls[0]
        editor_panel = row.controls[1]
        preview_overlay = stack.controls[1]

        assert curriculum_container.visible is True
        assert editor_panel.visible is False
        assert preview_overlay.visible is False
        print("  [OK] Initial desktop state: Curriculum outline visible, editor panel and preview overlay hidden.")

        print("\n[2/5] Testing Lesson Type Picker Dialog & Visual Cards...")
        curriculum_col = curriculum_container.content
        module_block = curriculum_col.controls[1]
        module_content = module_block.content
        add_lesson_btn = module_content.controls[2]

        # Trigger Add Lesson
        add_lesson_btn.on_click(MagicMock())
        picker_dlg = page.overlay[-1]
        assert picker_dlg.open is True
        picker_col = picker_dlg.content.content
        assert len(picker_col.controls) == len(LESSON_TYPES)
        print(f"  [OK] Picker modal contains all {len(LESSON_TYPES)} visual lesson cards.")

        # Add new lesson via picker
        flashcard_card = [c for c in picker_col.controls if "Flashcards" in c.content.controls[1].controls[0].value][0]
        flashcard_card.on_click(MagicMock())
        assert picker_dlg.open is False
        assert editor_panel.visible is True
        print("  [OK] Selecting a card dismisses picker and immediately opens lesson in editor panel.")

        print("\n[3/5] Testing Editor Sections for all 7 Lesson Formats...")
        lessons_col = module_content.controls[1]
        # Iterate through all lessons and verify editor section generation
        for i, lesson_row in enumerate(lessons_col.controls):
            lesson_row.on_click(MagicMock())
            assert editor_panel.visible is True
            editor_content = editor_panel.content.controls[1].content
            assert len(editor_content.controls) > 0
            # Save & Close
            save_btn = editor_content.controls[-1]
            save_btn.on_click(MagicMock())
            assert editor_panel.visible is False
        print("  [OK] All 7 lesson types (plus new lesson) render modular editor sections without error.")

        print("\n[4/5] Testing Mobile Responsiveness & Layout Switching...")
        page.width = 450
        page.on_resized(MagicMock())
        # Open editor on mobile
        lessons_col.controls[0].on_click(MagicMock())
        assert curriculum_container.visible is False
        assert editor_panel.visible is True
        assert editor_panel.expand is True
        print("  [OK] Mobile mode: Curriculum hidden, editor expands to 100% viewport width.")

        # Close editor on mobile
        editor_content = editor_panel.content.controls[1].content
        save_btn = editor_content.controls[-1]
        save_btn.on_click(MagicMock())
        assert curriculum_container.visible is True
        assert editor_panel.visible is False
        print("  [OK] Mobile mode: Curriculum restored, editor hidden.")

        print("\n[5/5] Testing Desktop Re-expansion on Window Resize...")
        page.width = 1280
        page.on_resized(MagicMock())
        assert curriculum_container.visible is True
        assert editor_panel.visible is False

        # Open editor on desktop using current curriculum controls
        current_lessons_col = curriculum_col.controls[1].content.controls[1]
        current_lessons_col.controls[1].on_click(MagicMock())
        assert curriculum_container.visible is True
        assert editor_panel.visible is True
        assert editor_panel.width == SIDEBAR_WIDTH
        print(f"  [OK] Desktop mode: Curriculum and {editor_panel.width}px editor panel side-by-side simultaneously.")

        print("\n=======================================================")
        print("COURSE BUILDER REVAMP VERIFICATION PASSED COMPLETELY!")
        print("=======================================================")

if __name__ == "__main__":
    asyncio.run(run_revamp_verification())
