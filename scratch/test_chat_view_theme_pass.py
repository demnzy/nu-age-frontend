import sys
import os
import asyncio
sys.path.insert(0, os.path.abspath("."))

import flet as ft
from src.chat_view import chat_view, build_whatsapp_spans

class MockSharedPreferences:
    def __init__(self):
        self._store = {
            "auth_token": "mock_token_123",
            "user_id": "usr_test_123"
        }
    async def get(self, key):
        return self._store.get(key)
    async def set(self, key, value):
        self._store[key] = value
    async def remove(self, key):
        self._store.pop(key, None)

class MockSession:
    store = {"current_user": {"id": "usr_test_123", "role": "STUDENT", "username": "alice"}}

class MockPage:
    def __init__(self, theme_mode=ft.ThemeMode.DARK, width=1200):
        self.theme_mode = theme_mode
        self.width = width
        self.shared_preferences = MockSharedPreferences()
        self.session = MockSession()
        self.data = {}
        self.views = []
        self.overlay = []
        self.route = "/nu-chat"
        self.on_resize = None

    def go(self, r):
        self.route = r

    def update(self):
        pass

    def run_task(self, fn, *args, **kwargs):
        pass

async def test_chat_theming():
    print("--- 1. Testing Dark Mode chat_view Instantiation & Colors ---")
    page_dark = MockPage(theme_mode=ft.ThemeMode.DARK, width=1280)
    view_dark = await chat_view(page_dark)

    assert isinstance(view_dark, ft.View), "Should return ft.View"
    assert view_dark.route == "/nu-chat"
    assert view_dark.bgcolor == "#121212", f"Dark background should be #121212, got {view_dark.bgcolor}"
    print(f"Dark mode chat_view created successfully: bgcolor={view_dark.bgcolor}")

    print("\n--- 2. Testing Light Mode chat_view Instantiation & Colors ---")
    page_light = MockPage(theme_mode=ft.ThemeMode.LIGHT, width=1280)
    view_light = await chat_view(page_light)

    assert isinstance(view_light, ft.View), "Should return ft.View"
    assert view_light.route == "/nu-chat"
    assert view_light.bgcolor == "#FAFAFA", f"Light background should be #FAFAFA, got {view_light.bgcolor}"
    print(f"Light mode chat_view created successfully: bgcolor={view_light.bgcolor}")

    print("\n--- 3. Testing build_whatsapp_spans Contrast Engine ---")
    palette_dark = {"accent": "#4CAF50", "bubble_out_link": "#C8E6C9"}
    palette_light = {"accent": "#035800", "bubble_out_link": "#C8E6C9"}

    # Test incoming bubble link in light mode
    in_spans = build_whatsapp_spans("Check https://nuage.edu @admin", "#1A1A1A", palette_light, is_me=False)
    assert in_spans[1].style.color == "#035800", f"Incoming link should use primary #035800, got {in_spans[1].style.color}"
    assert in_spans[3].style.color == ft.Colors.AMBER_500, "Incoming @admin should be amber 500"

    # Test outgoing bubble link in light mode (where background is #035800)
    out_spans = build_whatsapp_spans("Check https://nuage.edu @admin", "#FFFFFF", palette_light, is_me=True)
    assert out_spans[1].style.color == "#C8E6C9", f"Outgoing link on green bubble must be light mint #C8E6C9, got {out_spans[1].style.color}"
    assert out_spans[3].style.color == ft.Colors.AMBER_300, "Outgoing @admin should be illuminated amber 300"
    print("WhatsApp rich text formatting high-contrast styling verified!")

    print("\n--- 4. Mobile Viewport Instantiation (360px) ---")
    page_mob = MockPage(theme_mode=ft.ThemeMode.DARK, width=360)
    view_mob = await chat_view(page_mob)
    assert view_mob is not None
    print("Mobile 360px chat_view initialized with responsive layout!")

    print("\nALL NU-CHAT COLOR PASS TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(test_chat_theming())
