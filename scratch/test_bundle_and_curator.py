import asyncio
import sys
from unittest.mock import MagicMock

sys.path.insert(0, "c:/Users/Admin/Desktop/Code/NU-Front")

import flet as ft
from src.components.bundle_builder_modal import show_bundle_builder_dialog
from src.components.question_curator_modal import show_question_curator_dialog

async def test_bundle_and_curator():
    print("Testing Bundle Builder and Question Curator...")

    mock_page = MagicMock(spec=ft.Page)
    mock_page.width = 1100
    mock_page.height = 800
    mock_page.overlay = []
    mock_page.update = MagicMock()
    mock_page.run_task = MagicMock()

    sample_packs = [
        {
            "id": "pack-1",
            "title": "JAMB UTME 2024 Physics Exam Questions",
            "category": "JAMB UTME",
            "price_coins": 50,
            "pack_data": {"questions": [1, 2, 3], "flashcards": [1, 2]},
        },
        {
            "id": "pack-2",
            "title": "JAMB UTME 2024 Chemistry Exam Questions",
            "category": "JAMB UTME",
            "price_coins": 50,
            "pack_data": {"questions": [1, 2, 3, 4], "flashcards": [1, 2, 3]},
        },
    ]

    # 1. Test Bundle Builder Modal
    saved_payload = []
    def on_save_bundle(payload):
        saved_payload.append(payload)

    show_bundle_builder_dialog(
        page=mock_page,
        available_packs=sample_packs,
        existing_bundle=None,
        on_save=on_save_bundle,
    )
    assert len(mock_page.overlay) == 1
    bundle_dlg = mock_page.overlay[0]
    assert isinstance(bundle_dlg, ft.AlertDialog)
    print("[OK] Bundle Builder Dialog created and attached to overlay")

    # 2. Test Question Curator Dialog
    mock_page.overlay.clear()
    published_q = []
    def on_publish_curated(payload):
        published_q.append(payload)

    show_question_curator_dialog(
        page=mock_page,
        initial_questions=[{
            "question_text": "Sample Question",
            "options": ["A", "B", "C", "D"],
            "answer_index": 0,
            "topic": "Physics",
        }],
        pack_title="Physics Pack 2025",
        on_publish=on_publish_curated,
    )
    assert len(mock_page.overlay) == 1
    curator_dlg = mock_page.overlay[0]
    assert isinstance(curator_dlg, ft.AlertDialog)
    print("[OK] Question Curator Dialog created and attached to overlay")

    print("\nALL MODAL TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test_bundle_and_curator())
