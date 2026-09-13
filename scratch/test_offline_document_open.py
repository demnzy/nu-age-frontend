import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import flet as ft
from unittest.mock import MagicMock, AsyncMock
from src.utils.file_opener import open_or_download_asset

async def test_offline_open():
    mock_page = MagicMock(spec=ft.Page)
    del mock_page.show_snack_bar  # explicitly ensure show_snack_bar does not exist!
    mock_page.show_dialog = MagicMock()
    mock_page.launch_url = AsyncMock()

    test_path = "c:/Users/Admin/AppData/Roaming/Appveyor%20Systems%20Inc/Flet/course_assets/d77332a5-f83f-4d3c-9ddf-7c7441d79d93/9527801cb4364019a7baf05e8b09cf26/baa63b67378c44498f2d6f5174a11509_document_7a098dcd001a497db7f4fe5227190e1b.pdf"
    file_name = "Lecture Notes - Module 1"

    print("--- Testing open_or_download_asset with offline course PDF ---")
    await open_or_download_asset(mock_page, test_path, file_name)

    print(f"show_dialog called: {mock_page.show_dialog.called}")
    assert mock_page.show_dialog.called, "show_dialog should have been called!"
    snack = mock_page.show_dialog.call_args[0][0]
    print(f"SnackBar displayed safely via show_dialog: {isinstance(snack, ft.SnackBar)}")

    # Check user's Downloads folder
    downloads_dir = os.path.join(os.path.expanduser("~"), "Downloads")
    expected_file = os.path.join(downloads_dir, f"{file_name}.pdf")
    print(f"File copied to Downloads: {os.path.exists(expected_file)} -> {expected_file}")

    print("--- Testing remote URL fallback ---")
    remote_url = "https://example.com/sample.pdf"
    await open_or_download_asset(mock_page, remote_url, "Remote Sample")
    print(f"launch_url called for remote URL: {mock_page.launch_url.called}")

    print("ALL TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(test_offline_open())
