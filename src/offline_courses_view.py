"""
src/offline_courses_view.py

The "Moodle-style" offline entry point: a screen reachable regardless of
connectivity or auth-token validity, listing whatever courses have been
downloaded locally. This is what solves the original gap — refresh
tokens only fix "don't re-login when online," this screen is the actual
"get into the app with zero network calls" path.

Reads only from SQLite (via local_db.py). Never calls the API directly —
if a full re-sync of course content is wanted, that's routed through
download_manager.download_course() explicitly (a "Refresh" action),
not implicit here.
"""

import asyncio
import flet as ft
from src.local_db import get_local_db
from src.download_manager import delete_downloaded_course, download_course, DownloadProgress
from src.progress_sync import sync_offline_progress, has_unsynced_progress, SyncResult


async def offline_courses_view(page: ft.Page) -> ft.View:
    db = get_local_db(page)

    sync_status_text = ft.Text("", size=12, color=ft.Colors.ON_SURFACE_VARIANT)
    sync_button = ft.TextButton("Sync now", icon=ft.Icons.SYNC_ROUNDED)
    course_list_column = ft.Column(spacing=12, expand=True,scroll=ft.ScrollMode.AUTO,)

    def get_downloaded_courses():
        return db.execute(
            """
            SELECT id, name, description, downloaded_at, total_size_bytes,
                   (SELECT COUNT(*) FROM downloaded_modules WHERE course_id = downloaded_courses.id) as module_count
            FROM downloaded_courses
            ORDER BY downloaded_at DESC
            """
        ).fetchall()

    def format_size(size_bytes: int) -> str:
        if not size_bytes:
            return "Text only"
        mb = size_bytes / (1024 * 1024)
        return f"{mb:.1f} MB" if mb >= 1 else f"{size_bytes // 1024} KB"

    async def handle_open_course(e, course_id: str):
        # Explicitly route to offline course view so main.py strictly loads
        # the offline SQLite-backed engine without probing or attempting network
        page.go(f"/courses/{course_id}/offline")

    async def handle_delete_course(e, course_id: str):
        async def confirm_delete(e):
            page.pop_dialog()
            await delete_downloaded_course(page, course_id)
            await refresh_list()

        def cancel_delete(e):
            page.pop_dialog()

        dialog = ft.AlertDialog(
            title=ft.Text("Remove downloaded course?"),
            content=ft.Text("This deletes the local copy. Your progress on this course is kept and won't be lost — only the downloaded content is removed."),
            actions=[
                ft.TextButton("Cancel", on_click=cancel_delete),
                ft.TextButton("Remove", on_click=confirm_delete, style=ft.ButtonStyle(color=ft.Colors.ERROR)),
            ],
        )
        page.show_dialog(dialog)

    def build_course_card(course_id, name, description, downloaded_at, size_bytes, module_count):
        return ft.Container(
            padding=16,
            border_radius=14,
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_PRIMARY)),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text(name, weight=ft.FontWeight.BOLD, size=16),
                                    ft.Text(
                                        f"{module_count} module{'s' if module_count != 1 else ''} · {format_size(size_bytes)}",
                                        size=12,
                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                icon_color=ft.Colors.ON_SURFACE_VARIANT,
                                tooltip="Remove download",
                                on_click=lambda e, cid=course_id: page.run_task(handle_delete_course, e, cid),
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.START,
                    ),
                    ft.FilledButton(
                        "Open",
                        icon=ft.Icons.PLAY_ARROW_ROUNDED,
                        on_click=lambda e, cid=course_id: page.run_task(handle_open_course, e, cid),
                    ),
                ],
                spacing=10,
            ),
        )

    async def refresh_list():
        courses = get_downloaded_courses()
        course_list_column.controls.clear()

        if not courses:
            course_list_column.controls.append(
                ft.Container(
                    padding=40,
                    alignment=ft.Alignment.CENTER,
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.DOWNLOAD_FOR_OFFLINE_OUTLINED, size=48, color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text("No courses downloaded yet", color=ft.Colors.ON_SURFACE_VARIANT),
                            ft.Text(
                                "Open a course while online and tap Download to view it here later.",
                                size=12,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                    ),
                )
            )
        else:
            for row in courses:
                course_list_column.controls.append(build_course_card(*row))

        await refresh_sync_status()
        if course_list_column.page:
            page.update()
        else:
            # Coroutine outran the mount (page.run_task started before
            # load_view finished appending `view` to page.views). Retry
            # shortly rather than silently leaving the loading spinner up
            # forever with no later trigger to repaint it.
            await asyncio.sleep(0.05)
            if course_list_column.page:
                page.update()

    async def refresh_sync_status():
        pending = await has_unsynced_progress(page)
        sync_button.visible = pending
        sync_status_text.value = (
            "You have unsynced progress — will sync automatically when online."
            if pending else
            "All progress synced."
        )
        if sync_status_text.page:
            page.update()

    async def handle_sync_click(e):
        sync_button.disabled = True
        sync_status_text.value = "Syncing..."
        page.update()

        result: SyncResult = await sync_offline_progress(page)

        if result.status == "done":
            sync_status_text.value = f"Synced {result.synced} of {result.total} updates."
        elif result.status == "nothing_to_sync":
            sync_status_text.value = "All progress synced."
        elif result.status == "error":
            sync_status_text.value = f"Sync failed: {result.error_message}"
        sync_button.disabled = False
        await refresh_sync_status()

    sync_button.on_click = handle_sync_click

    view = ft.View(
        route="/offline",
        bgcolor=ft.Colors.ON_PRIMARY,
        appbar=ft.AppBar(
            leading=ft.IconButton(
                ft.Icons.ARROW_BACK_ROUNDED,
                # Always goes to login, regardless of online/offline state.
                # This screen can be reached from many different failure
                # paths (cold-open-offline fallback, a connectivity
                # SnackBar mid-navigation, a normal /courses tap), so
                # there's no single reliable "came from" route to compute
                # the way course_page.py's back_target does — login is the
                # one destination that's always valid to land on.
                #
                # IMPORTANT: this must be set explicitly. Without a
                # `leading` control, Flet auto-generates a default back
                # arrow that pops the view stack directly (page.views.pop())
                # rather than going through page.go()/route_change — that
                # bypass is what caused the "back arrow leads nowhere and
                # freezes the whole UI" bug: page.route never actually
                # updated to match what was on screen, so every subsequent
                # tap kept re-evaluating stale route logic against a
                # mismatched state.
                on_click=lambda _: page.go("/"),
            ),
            title=ft.Text("Downloaded Courses"),
            bgcolor=ft.Colors.SURFACE,
        ),
        controls=[
            ft.SafeArea(
                expand=True,
                content=ft.Container(
                    padding=16,
                    content=ft.Column(
                        [
                            ft.Row(
                                [sync_status_text, sync_button], 
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                wrap=True
                            ),
                            ft.Divider(height=1),
                            course_list_column,
                        ],
                        spacing=12,
                        expand=True,
                    ),
                ),
            )
        ],
    )

    # IMPORTANT: do NOT call refresh_list()/page.update() here. This
    # coroutine is still being awaited by load_view/load_view_and_report
    # at this point — `view` has not been appended to page.views yet, so
    # none of its controls are mounted. Calling page.update() before that
    # append happens throws "Control must be added to the page first" (it
    # can also corrupt whatever the skeleton was mid-render, since
    # page.update() flushes the whole page, not just these controls).
    #
    # Instead: return the view with an empty/loading list, exactly like
    # course_page.py's content_socket pattern, and populate it via
    # page.run_task AFTER the caller has mounted it. refresh_list's own
    # `if X.page:` guards then correctly see these controls as mounted
    # once that task actually runs.
    course_list_column.controls.append(
        ft.Container(
            padding=40,
            alignment=ft.Alignment.CENTER,
            content=ft.ProgressRing(width=28, height=28, stroke_width=3),
        )
    )
    page.run_task(refresh_list)

    return view