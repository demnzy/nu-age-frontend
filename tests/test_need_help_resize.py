import unittest
from unittest.mock import MagicMock
import flet as ft

from src.components.need_help_drawer import build_need_help_drawer, NeedHelpController

class TestNeedHelpDrawerResize(unittest.TestCase):
    def setUp(self):
        self.page = MagicMock()
        self.page.width = 1200
        self.page.height = 800
        self.page.window = MagicMock()
        self.page.window.width = 1200
        self.page.window.height = 800
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.client_storage = MagicMock()
        self.page.client_storage.get.return_value = None

    def test_build_and_resize_flow(self):
        controller = NeedHelpController()
        drawer_socket = ft.Container()
        
        drawer = build_need_help_drawer(
            page=self.page,
            lesson_data={"title": "Introduction to Python", "content": "Variables and types"},
            module_title="Module 1",
            course_title="Python 101",
            course_id="test_course",
            controller=controller,
            target_container=drawer_socket,
        )
        self.assertIs(drawer, drawer_socket)
        
        # Initial desktop state: no absolute positioning
        self.assertIsNone(drawer_socket.left)
        self.assertIsNone(drawer_socket.top)
        self.assertIsNone(drawer_socket.right)
        self.assertIsNone(drawer_socket.bottom)
        
        # Simulate half-screen resize to 900px
        self.page.width = 900
        self.page.window.width = 900
        if controller.adapt_layout:
            controller.adapt_layout(is_desktop=False, page_w=900, page_h=800)
            
        # Mobile overlay state in Stack: absolute properties are set
        self.assertEqual(drawer_socket.left, 10)
        self.assertEqual(drawer_socket.right, 10)
        self.assertEqual(drawer_socket.bottom, 10)
        self.assertIsNone(drawer_socket.top)
        self.assertIsNotNone(drawer_socket.height)
        
        # Simulate maximize back to desktop 1400px
        self.page.width = 1400
        self.page.window.width = 1400
        if controller.adapt_layout:
            controller.adapt_layout(is_desktop=True, page_w=1400, page_h=800)
            
        # Desktop state: absolute positioning MUST be None so it can sit in ft.Row
        self.assertIsNone(drawer_socket.left)
        self.assertIsNone(drawer_socket.top)
        self.assertIsNone(drawer_socket.right)
        self.assertIsNone(drawer_socket.bottom)
        self.assertIsNone(drawer_socket.height)
        self.assertEqual(drawer_socket.width, 400)
        
        # Verify messages_col is an expandable, non-blocking ListView inside drawer_socket
        # Find ListView in drawer_socket controls
        found_listview = None
        def _search_lv(ctl):
            nonlocal found_listview
            if isinstance(ctl, ft.ListView):
                found_listview = ctl
                return
            if hasattr(ctl, "controls") and isinstance(ctl.controls, list):
                for c in ctl.controls:
                    _search_lv(c)
            if hasattr(ctl, "content") and ctl.content is not None:
                _search_lv(ctl.content)

        _search_lv(drawer_socket)
        self.assertIsNotNone(found_listview, "Expected an ft.ListView for chat message scrolling")
        self.assertTrue(found_listview.expand)
        self.assertFalse(found_listview.auto_scroll)
        
        # Verify safe mounting in ft.Row (desktop) without absolute positioning errors
        row = ft.Row([drawer_socket])
        self.assertIsNone(drawer_socket.left)
        self.assertIsNone(drawer_socket.top)
        self.assertIsNone(drawer_socket.right)
        self.assertIsNone(drawer_socket.bottom)

if __name__ == "__main__":
    unittest.main()
