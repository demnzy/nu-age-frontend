import sys, os
sys.path.insert(0, os.path.abspath("."))
import flet as ft
from unittest.mock import MagicMock

def test_codelab_block_dropdown():
    mock_page = MagicMock(spec=ft.Page)
    mock_page.width = 1200
    mock_page.height = 800

    content = {
        "language": "cpp",
        "instructions": "Write C++ code",
        "starter_code": "#include <iostream>\nint main(){ return 0; }",
        "solution_code": "#include <iostream>\nint main(){ return 0; }",
        "test_cases": [{"description": "t1", "input": "", "expected_output": "0"}]
    }

    from src.course_builder import render_preview_code_lab_ui
    preview = render_preview_code_lab_ui({"content": content, "_page": mock_page})
    assert preview is not None
    print("[OK] Preview CodeLab UI rendered successfully for C++!")

    # Verify Dropdown instantiation with on_select
    available_languages = [
        ("python", "Python 3.12 (Offline Sandbox)", ft.Icons.TERMINAL_ROUNDED, ft.Colors.BLUE_600),
        ("sql", "SQLite 3 (Offline In-Memory)", ft.Icons.STORAGE_ROUNDED, ft.Colors.TEAL_600),
        ("cpp", "C++ (GCC 9.2 Container)", ft.Icons.CODE_ROUNDED, ft.Colors.CYAN_700),
    ]
    dropdown = ft.Dropdown(
        label="Programming Language / Runtime Environment",
        value="cpp",
        options=[ft.dropdown.Option(key=k, text=t) for k, t, _, _ in available_languages],
        border_radius=8,
        on_select=lambda e: None,
    )
    assert dropdown is not None
    assert dropdown.value == "cpp"
    print("[OK] Dropdown instantiated with on_select successfully!")

if __name__ == "__main__":
    test_codelab_block_dropdown()
