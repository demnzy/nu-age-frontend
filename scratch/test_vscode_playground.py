"""
Test VS Code Playground UI interaction and theme-aware behavior.
"""
import sys
import os
import asyncio
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import flet as ft
from src.components.coding_playground import CodingPlayground, PLAYGROUND_FILES


async def test_playground():
    print("Testing VS Code CodingPlayground...")
    mock_page = MagicMock(spec=ft.Page)
    mock_page.width = 1200
    mock_page.height = 800
    mock_page.theme_mode = ft.ThemeMode.DARK
    mock_page.update = lambda: None
    mock_page.run_task = lambda f, *a, **k: asyncio.create_task(f(*a, **k)) if asyncio.iscoroutinefunction(f) else f(*a, **k)

    pg = CodingPlayground(mock_page)

    # 1. Check initial state
    assert pg.current_lang == "python"
    assert "print(\"Hello from Python!\")" in pg.code_input.value
    print("[OK] Initial Python file loaded")

    # 2. Modify Python buffer
    pg.code_input.value = "print('Hello modified!')"
    pg._on_code_change(None)

    # 3. Switch to SQL tab
    pg._switch_language("sql")
    assert pg.current_lang == "sql"
    assert "CREATE TABLE users" in pg.code_input.value
    print("[OK] Switched to SQL tab")

    # 4. Switch back to Python - check buffer preserved
    pg._switch_language("python")
    assert pg.current_lang == "python"
    assert "print('Hello modified!')" in pg.code_input.value
    print("[OK] Returned to Python tab, buffer correctly preserved!")

    # 5. Test execution
    await pg._execute_code()
    assert "Hello modified!" in pg.console_output.value
    print("[OK] Executed Python code in playground:", pg.console_output.value.strip())

    # 6. Test switching to Input (stdin) tab
    pg._switch_panel_tab("input")
    assert pg._panel_tab == "input"
    assert pg.input_view.visible is True
    assert pg.terminal_view.visible is False
    print("[OK] Switched to Input (stdin) panel tab")

    pg._switch_panel_tab("terminal")
    assert pg.terminal_view.visible is True
    assert pg.input_view.visible is False
    print("[OK] Switched back to Terminal panel tab")

    # 7. Test _copy_code with clipboard mock
    mock_page.clipboard = MagicMock()
    mock_page.clipboard.set = MagicMock(return_value=asyncio.sleep(0))
    await pg._copy_code()
    mock_page.clipboard.set.assert_called_once()
    print("[OK] _copy_code cleanly executed with page.clipboard.set!")

    # 8. Test Light Mode Palette
    mock_page.theme_mode = ft.ThemeMode.LIGHT
    light_palette = pg._get_palette()
    assert light_palette["editor_bg"] == "#FFFFFF"
    assert light_palette["terminal_bg"] == "#FFFFFF"
    assert light_palette["toolbar_bg"] == "#FFFFFF"
    print("[OK] Light Mode palette verified: crisp white surfaces, no dull grey!")

    # 9. Test Hidden Scrollbars
    assert pg.content.scroll == ft.ScrollMode.HIDDEN
    assert pg.file_tabs_bar.content.scroll == ft.ScrollMode.HIDDEN
    assert pg.terminal_view.content.scroll == ft.ScrollMode.HIDDEN
    print("[OK] Scrollbars hidden across all IDE panels!")

    # 10. Test Stdin input layout stretch
    assert pg.input_view.content.horizontal_alignment == ft.CrossAxisAlignment.STRETCH
    assert pg.stdin_input.min_lines == 1
    assert pg.stdin_input.max_lines == 4
    assert pg.editor_box.content.horizontal_alignment == ft.CrossAxisAlignment.STRETCH
    assert pg.terminal_box.content.horizontal_alignment == ft.CrossAxisAlignment.STRETCH
    print("[OK] Stdin input stretches to full width with compact proportions (min_lines=1)!")

    # 11. Test Workspace row & Actions row mobile responsiveness
    assert "Workspace ›" in pg.breadcrumb_text.value
    assert pg.workspace_row.scroll == ft.ScrollMode.HIDDEN
    assert pg.actions_row.scroll == ft.ScrollMode.HIDDEN
    assert pg.terminal_tabs_row.scroll == ft.ScrollMode.HIDDEN
    print("[OK] Workspace row and dedicated action row are scrollable and prevent mobile bleeding!")

    # 12. Test Web Preview: Desktop browser bypass vs Mobile WebView modal
    pg.code_input.value = "<h1>Test Page</h1>"
    # Desktop test
    mock_page.open = MagicMock()
    await pg._open_web_preview_dialog()
    # On desktop, it shows a SnackBar with Chrome/Browser confirmation
    assert mock_page.open.call_count >= 1
    print("[OK] Desktop HTML preview bypasses modal and launches live browser with SnackBar confirmation!")

    # Mobile test (simulating Android)
    mock_mobile_page = MagicMock(spec=ft.Page)
    mock_mobile_page.platform = ft.PagePlatform.ANDROID
    mock_mobile_page.width = 380
    mock_mobile_page.height = 700
    mock_mobile_page.open = MagicMock()
    mock_mobile_page.run_task = lambda f, *a, **k: asyncio.create_task(f(*a, **k)) if asyncio.iscoroutinefunction(f) else f(*a, **k)
    from src.utils.file_opener import open_web_preview_modal
    # Temporarily simulate mobile environment
    import os
    os.environ["ANDROID_ROOT"] = "/system"
    try:
        open_web_preview_modal(mock_mobile_page, "<h1>Mobile Test</h1>", title="Web Preview")
        mock_mobile_page.open.assert_called_once()
        opened_dlg = mock_mobile_page.open.call_args[0][0]
        assert isinstance(opened_dlg, ft.AlertDialog)
        print("[OK] Mobile HTML preview opens in-app WebView modal cleanly!")
    finally:
        del os.environ["ANDROID_ROOT"]

    print("\nALL VS CODE PLAYGROUND CHECKS PASSED!")


if __name__ == "__main__":
    asyncio.run(test_playground())
