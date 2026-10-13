import asyncio
import sys
import flet as ft
from unittest.mock import MagicMock, AsyncMock

# Add src to sys.path
sys.path.insert(0, ".")

async def run_tests():
    print("=== 1. Testing NotificationManager and sync ===")
    from src.components.notifications_drawer import NotificationManager
    from src.services.notification_service import sync_learner_notifications
    from src.requests.notifications import get_user_notifications, mark_notification_read, mark_all_notifications_read

    NotificationManager.clear_all()
    assert NotificationManager.get_unread_count() == 0, "Initial unread count should be 0"

    # Add a mock backend notification
    nid = "backend_test_123"
    NotificationManager.upsert(
        notif_id=nid,
        title="Admin Mention",
        body="@admin Please review my assignment",
        category="chat",
        icon=ft.Icons.CHAT_BUBBLE_ROUNDED,
        action_label="Open",
        on_action=None
    )
    for n in NotificationManager.get_all():
        if n["id"] == nid:
            n["backend_id"] = "test_123"
            n["action_route"] = "/chat?channel=chan_456"

    assert NotificationManager.get_unread_count() == 1, "Unread count should be 1"
    NotificationManager.mark_read(nid)
    assert NotificationManager.get_unread_count() == 0, "Unread count should be 0 after marking read"
    print("NotificationManager test passed!")

    print("=== 2. Testing Notifications View Instantiation ===")
    from src.notifications_view import notifications_view
    mock_page = MagicMock(spec=ft.Page)
    mock_page.shared_preferences = AsyncMock()
    mock_page.shared_preferences.get = AsyncMock(return_value="mock_token")
    mock_page.session = MagicMock()
    mock_page.session.store = {}
    mock_page.width = 1200
    mock_page.height = 800
    mock_page.update = MagicMock()
    mock_page.go = MagicMock()
    mock_page.run_task = MagicMock()

    view = await notifications_view(mock_page)
    assert isinstance(view, ft.View), "Should return a ft.View"
    assert view.route == "/notifications", "Route should be /notifications"
    print("Notifications View Instantiation passed!")

    print("=== 3. Testing Chat View Instantiation and UI Components ===")
    from src.chat_view import chat_view
    chat_v = await chat_view(mock_page)
    assert isinstance(chat_v, ft.View), "Should return a ft.View"
    assert chat_v.route in ("/nu-chat", "/chat"), f"Route should be /nu-chat or /chat, got {chat_v.route}"
    print("Chat View Instantiation passed!")

    print("=== ALL INTEGRATION VERIFICATION TESTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    asyncio.run(run_tests())
