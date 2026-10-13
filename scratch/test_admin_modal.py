import asyncio
import sys
from unittest.mock import MagicMock

sys.path.insert(0, "c:/Users/Admin/Desktop/Code/NU-Front")

import flet as ft
from src.platform_admin_view import platform_admin_view

async def run_test():
    page = MagicMock(spec=ft.Page)
    page.theme_mode = ft.ThemeMode.DARK
    page.width = 1200
    page.height = 900
    page.overlay = []
    page.update = MagicMock()

    view = await platform_admin_view(page)
    assert view is not None
    print("[OK] platform_admin_view created successfully")

if __name__ == "__main__":
    asyncio.run(run_test())
