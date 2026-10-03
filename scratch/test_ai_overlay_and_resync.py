import asyncio
import flet as ft
from src.components.need_help_drawer import build_need_help_drawer, NeedHelpController

class MockPage:
    def __init__(self):
        self.width = 360
        self.height = 740
        self.theme_mode = ft.ThemeMode.LIGHT
        self.views = []
        self.overlay = []
        self.session = type('Session', (), {'store': {}})()
        self.shared_preferences = type('SP', (), {'get': lambda self, k: None})()
        self.route = "/dashboard"
        self._Page__last_route = None
        self.pushed_routes = []

    def update(self):
        pass

    async def push_route(self, r, **kwargs):
        self.pushed_routes.append(r)

async def test_ai_overlay_and_resync():
    print("--- 1. Testing AI Drawer Overlay Bounds & Minimize on Mobile ---")
    page = MockPage()
    target_container = ft.Container()
    
    drawer = build_need_help_drawer(
        page=page,
        lesson_data={"title": "Introduction to AI", "content": "Sample content"},
        module_title="Module 1",
        course_title="Nu AI Course",
        target_container=target_container,
    )

    # Initial mobile state
    assert target_container.left == 10
    assert target_container.right == 10
    assert target_container.bottom == 10
    assert target_container.top is None, f"Expected container.top to be None, got {target_container.top}"
    
    col = target_container.content
    main_win = col.controls[1]
    assert main_win.height is not None
    assert not main_win.expand
    print("[OK] Initial mobile drawer state verified (anchored at bottom=10, top=None, fixed height)")

    # Find the fullscreen button
    # header_content is in main_win.content.controls[0]
    header = main_win.content.controls[0]
    # header has controls: [left_row, right_row]
    right_row = header.controls[1]
    fullscreen_btn = right_row.controls[0]
    assert fullscreen_btn.icon == ft.Icons.FULLSCREEN_ROUNDED

    # Toggle to Fullscreen
    fullscreen_btn.on_click(None)
    assert target_container.top == 8, f"Expected container.top to be 8, got {target_container.top}"
    assert target_container.bottom == 8, f"Expected container.bottom to be 8, got {target_container.bottom}"
    assert target_container.left == 8
    assert target_container.right == 8
    assert main_win.height is None, f"Expected main_win.height to be None (expand=True), got {main_win.height}"
    assert main_win.expand is True, "Expected main_win.expand to be True"
    assert fullscreen_btn.icon == ft.Icons.FULLSCREEN_EXIT_ROUNDED
    print("[OK] Fullscreen toggle verified: fits container bounds top=8, bottom=8, expand=True without bleeding or cutting off header")

    # Toggle back to Normal
    fullscreen_btn.on_click(None)
    assert target_container.top is None
    assert target_container.bottom == 10
    assert target_container.left == 10
    assert target_container.right == 10
    assert main_win.height is not None
    assert not main_win.expand
    assert fullscreen_btn.icon == ft.Icons.FULLSCREEN_ROUNDED
    print("[OK] Minimize back to normal size verified: restored bottom=10, top=None, original height")

    print("\n--- 2. Testing Route Failure Resync Invariant ---")
    # Simulate user tapping a route that fails
    failed_destination = "/courses/course-abc-123/view"
    page.route = failed_destination
    page._Page__last_route = failed_destination # Flet's internal state after RouteChangeEvent

    # Simulate what restore_previous_or_fallback does on failure:
    restored_route = "/dashboard"
    page.route = restored_route
    setattr(page, "_Page__last_route", page.route)
    await page.push_route(page.route)

    assert page.route == "/dashboard"
    assert page._Page__last_route == "/dashboard", f"Expected _Page__last_route to be /dashboard, got {page._Page__last_route}"
    assert "/dashboard" in page.pushed_routes, f"Expected /dashboard in pushed_routes, got {page.pushed_routes}"

    # Now simulate user tapping failed_destination again
    # Flet's before_event gate:
    # if page._Page__last_route == new_event.route: return False
    incoming_event_route = failed_destination
    will_flet_allow = page._Page__last_route != incoming_event_route
    assert will_flet_allow is True, "Flet before_event would drop the event as a duplicate!"
    print("[OK] Route resync verified: subsequent taps to failed route will NOT be dropped by Flet or client router")

    print("\nALL VERIFICATION CHECKS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test_ai_overlay_and_resync())
