import asyncio
import os
import sys
import flet as ft

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.components.user_avatar import build_user_avatar, get_user_initials, get_avatar_color

class MockStore:
    def __init__(self, data=None):
        self._data = data or {}
    def get(self, key, default=None):
        return self._data.get(key, default)
    def set(self, key, value):
        self._data[key] = value

class MockSession:
    def __init__(self, data=None):
        self.store = MockStore(data)
    def get(self, key, default=None):
        return self.store.get(key, default)
    def set(self, key, value):
        self.store.set(key, value)

class MockPrefs:
    def __init__(self):
        self._data = {"auth_token": "mock_token"}
    async def get(self, key, default=None):
        return self._data.get(key, default)
    async def set(self, key, value):
        self._data[key] = value

class MockPage:
    def __init__(self):
        self.theme_mode = ft.ThemeMode.DARK
        self.width = 1000
        self.height = 800
        self.route = "/profile"
        self.views = []
        self.session = MockSession({
            "id": "11111111-1111-1111-1111-111111111111",
            "first_name": "Tobi",
            "last_name": "Ade",
            "username": "tobi_learner",
            "email": "tobi@nu-age.com",
            "role": "Student",
            "university": "University of Lagos",
            "streak": 5,
            "is_verified": True,
            "profile_picture_url": "https://nu-age.b-cdn.net/avatars/user_1/avatar_123.jpg"
        })
        self.shared_preferences = MockPrefs()
        self.client_storage = self.shared_preferences
        self.overlay = []
        self.controls = []
        self.window = self

    def update(self):
        pass

    def run_task(self, fn, *args, **kwargs):
        pass

    def go(self, route):
        self.route = route

async def test_all():
    print("Testing UserAvatar component...")
    av1 = build_user_avatar("Tobi Ade", "https://example.com/pic.jpg", radius=24, show_online_dot=True, is_online=True)
    assert isinstance(av1, (ft.Stack, ft.CircleAvatar, ft.Container)), f"Invalid type: {type(av1)}"
    
    av2 = build_user_avatar("Single", None, radius=18, is_group=True)
    assert isinstance(av2, ft.CircleAvatar)
    
    av3 = build_user_avatar("", None, radius=14)
    assert isinstance(av3, ft.CircleAvatar)
    assert get_user_initials("Tobi Ade") == "TA"
    assert get_user_initials("Tobi") == "TO"
    assert get_user_initials("") == "NU"
    print("[OK] UserAvatar component tests passed!")

    page = MockPage()

    print("Testing edit_profile_view...")
    from src.edit_profile import edit_profile_view
    view = await edit_profile_view(page)
    assert isinstance(view, ft.View)
    print("[OK] edit_profile_view instantiated successfully!")

    print("Testing profile_view...")
    from src.profile import profile_view
    p_view = await profile_view(page)
    assert isinstance(p_view, ft.View)
    print("[OK] profile_view instantiated successfully!")

    print("Testing member_profile_view...")
    from src.member_profile import member_profile_view
    m_view = await member_profile_view(page, identifier="some_id")
    assert isinstance(m_view, ft.View)
    print("[OK] member_profile_view instantiated successfully!")

    print("Testing chat_view...")
    from src.chat_view import chat_view
    c_view = await chat_view(page)
    assert isinstance(c_view, ft.View)
    print("[OK] chat_view instantiated successfully!")

    print("Testing dashboard_view...")
    from src.dashboard import dashboard_view
    d_view = await dashboard_view(page)
    assert isinstance(d_view, ft.View)
    print("[OK] dashboard_view instantiated successfully!")

    print("\nALL VIEWS INSTANTIATED AND VALIDATED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test_all())
