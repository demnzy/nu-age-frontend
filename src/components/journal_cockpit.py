import flet as ft
import asyncio
from src.utils.file_opener import (
    show_page_snackbar,
    safe_set_clipboard,
    safe_open_dialog,
    safe_close_dialog,
    safe_update_dialog,
    run_after_modal_close,
    open_or_download_asset,
)
from src.utils.typing_animator import stream_typing_animation
from src.components.create_journal_modal import JOURNAL_COLORS, resolve_journal_color
from src.components.deck_inspector import open_deck_inspector
from src.components.chat_quota_modal import open_chat_quota_modal
from src.utils.ai_error_sanitizer import get_user_friendly_ai_error
from src.requests.study import (
    get_journal_details_api,
    update_journal_api,
    delete_journal_api,
    add_materials_to_journal_api,
    remove_material_from_journal_api,
    generate_journal_content_api,
    check_journal_generation_status_api,
    ask_journal_tutor_api,
    get_ai_tutor_quota_api,
    get_journal_due_cards_api,
    get_journal_questions_api,
)

# Session-level cache so tutor conversations persist when switching between
# Journal Flashcards / Quiz / Exam and returning to the Journal Cockpit.
_JOURNAL_CHAT_CACHE: dict[str, list] = {}



def resolve_journal_color_name(color_key: str | None) -> str:
    """Returns human-readable name for journal color (e.g. 'Teal', 'Indigo')."""
    cmap = {k: name for k, name, _ in JOURNAL_COLORS}
    return cmap.get(str(color_key).lower().strip(), "Notebook")

def _section_label(text: str, accent: str | None = None) -> ft.Text:
    return ft.Text(
        text.upper(),
        size=10.5,
        weight=ft.FontWeight.W_800,
        color=accent or ft.Colors.ON_SURFACE_VARIANT,
    )


def build_journal_cockpit(
    page: ft.Page,
    token: str,
    journal_id: str,
    vault_materials: list = None,
    on_back=None,
    on_start_flashcards=None,
    on_start_quiz=None,
    on_start_exam=None,
    on_configure_exam=None,
    on_open_material=None,
    on_journal_updated=None,
    user_plan: str = "free",
) -> ft.Control:
    """
    Course Journal Cockpit (Multi-Module Course Notebook):
    Matches the visual language, responsive scrolling viewport, and component
    architecture of the Single-Material Study Cockpit while providing:
    1. Top Navigation & Quick Action Bar
    2. Accent-Tinted Course Journal Hero Banner with readiness & primary CTA
    3. Constituent Course Syllabus (1–5 Modules) with in-place reader & cockpit jump
    4. 4-Card Practice & Simulation Grid (Flashcards, Browse Deck, Quick Quiz, Mock Exam)
    5. Dedicated Executive Course Study Guide Card (collapsible + full-screen reader)
    6. Grounded Course AI Tutor (Nu Owl) across all attached modules
    """
    vault_mats = vault_materials or []
    jid_str = str(journal_id)
    user_scope = str(getattr(page.session, "get", lambda k: None)("user_id") or (token[-16:] if token else "anon"))
    chat_cache_key = f"{user_scope}:{jid_str}"
    _update_journal_status_ui_slot = [None]
    def _update_journal_status_ui(data):
        if _update_journal_status_ui_slot[0]:
            _update_journal_status_ui_slot[0](data)

    state = {
        "journal": None,
        "materials": [],
        "chat_messages": list(_JOURNAL_CHAT_CACHE.get(chat_cache_key, [])),
        "is_loading": True,
        "is_chatting": False,
        "is_generating": False,
        "launching_action": None,  # "flashcards" | "browse" | "quiz" | "exam" | None
        "guide_collapsed": False,
        "tutor_minimized": False,
        "tutor_maximized": False,
        "polling_active": False,
        "unmounted": False,
        "plan_id": user_plan,
        "quota_info": {"is_unlimited": True, "plan": user_plan, "limit": -1, "used": 0, "remaining": -1, "locked": False} if (user_plan and user_plan != "free") else None,
    }

    loading_ring = ft.Container(
        alignment=ft.Alignment.CENTER,
        padding=ft.Padding.symmetric(vertical=80, horizontal=24),
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
            tight=True,
            controls=[
                ft.ProgressRing(width=32, height=32, stroke_width=2.8, color=ft.Colors.PRIMARY),
                ft.Text(
                    "Opening Course Journal...",
                    size=13.5,
                    weight=ft.FontWeight.W_700,
                    color=ft.Colors.ON_SURFACE_VARIANT,
                ),
            ],
        ),
    )

    # Outer scrollable root column matching _build_material_cockpit so content never bleeds off-screen
    cockpit_socket = ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=0,
        controls=[loading_ring],
    )

    async def _poll_generation():
        if state["polling_active"]:
            return
        state["polling_active"] = True
        try:
            for _ in range(60):  # Poll up to ~3 minutes
                await asyncio.sleep(2.5)
                if state["unmounted"]:
                    break
                stat_res = await check_journal_generation_status_api(token, jid_str)
                if not stat_res or stat_res.get("error"):
                    continue
                st = str(stat_res.get("status") or "").lower()
                if st == "error":
                    err_msg = stat_res.get("stage") or "An error occurred during synthesis."
                    show_page_snackbar(page, err_msg)
                    state["is_generating"] = False
                    _update_journal_status_ui(stat_res)
                    break

                still_gen = bool(stat_res.get("is_generating"))
                state["is_generating"] = still_gen
                _update_journal_status_ui(stat_res)
                if not still_gen and st == "completed":
                    show_page_snackbar(page, "Course Journal AI synthesis complete! ✨")
                    await _fetch_journal_data()
                    break
        except Exception as poll_err:
            print(f"[journal_cockpit] poll error: {poll_err}")
        finally:
            state["polling_active"] = False

    async def _fetch_journal_data():
        state["is_loading"] = True
        data = await get_journal_details_api(token, jid_str)
        state["is_loading"] = False
        if not data or data.get("error"):
            show_page_snackbar(page, data.get("error", "Failed to load Course Journal."))
            if on_back:
                state["unmounted"] = True
                on_back()
            return

        state["journal"] = data
        state["materials"] = data.get("materials", [])
        state["is_generating"] = bool(data.get("is_generating"))
        if on_journal_updated:
            try:
                on_journal_updated(data)
            except Exception:
                pass
        _render_cockpit()
        if state["is_generating"] and not state["polling_active"]:
            page.run_task(_poll_generation)

    # ── Modal 1: Module Question Bank & Notes Reader ─────────────────────────
    def _open_source_reader(mat_item: dict, color_token: str):
        from src.utils.file_opener import (
            synthesize_material_question_bank,
            export_text_or_markdown_as_pdf,
        )

        mid = str(mat_item.get("id"))
        m_title = mat_item.get("title") or "Course Module"
        m_content = mat_item.get("content") or ""

        vault_match = next((v for v in vault_mats if str(v.get("id")) == mid), None)
        if not m_content and vault_match:
            m_content = vault_match.get("content") or ""

        qbank_data = synthesize_material_question_bank(
            material_id=mid,
            title=m_title,
            raw_content=m_content,
            page=page,
        )
        final_markdown = qbank_data["markdown"]
        summary_label = qbank_data["summary_label"]
        reader_dlg = [None]

        def _close_reader(e=None):
            if reader_dlg[0]:
                safe_close_dialog(page, reader_dlg[0])

        async def _copy_source():
            if final_markdown:
                await safe_set_clipboard(page, final_markdown)
                show_page_snackbar(page, f"Copied '{m_title}' Question Bank to clipboard.")

        async def _export_question_bank_pdf(e=None):
            fname = f"{m_title} - Question Bank.pdf"
            ok = await export_text_or_markdown_as_pdf(
                page,
                fname,
                final_markdown,
                subtitle="Nu Age LMS • Question Bank",
            )
            if not ok:
                show_page_snackbar(page, "Could not generate PDF export.")

        def _jump_to_material(e=None):
            def _do_jump():
                if on_open_material:
                    target_mat = vault_match or mat_item
                    state["unmounted"] = True
                    on_open_material(target_mat)
            if reader_dlg[0]:
                run_after_modal_close(page, reader_dlg[0], _do_jump)
            else:
                _do_jump()

        dlg_w = min(740, int((page.width or 420) * 0.95))
        dlg_h = min(560, int((page.height or 680) * 0.75))

        content_controls = [
            ft.Container(
                expand=True,
                width=float("inf"),
                padding=ft.Padding.all(14),
                border_radius=ft.BorderRadius.all(12),
                bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                content=ft.Column(
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    controls=[
                        ft.SelectionArea(
                            content=ft.Markdown(
                                final_markdown,
                                selectable=True,
                                extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED,
                            )
                        )
                    ],
                ),
            )
        ]

        actions_list = [
            ft.TextButton(
                content=ft.Row(
                    spacing=5,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.PICTURE_AS_PDF_ROUNDED, size=14, color=color_token),
                        ft.Text("Export PDF", size=12, color=color_token, weight=ft.FontWeight.W_600),
                    ],
                ),
                on_click=lambda _: page.run_task(_export_question_bank_pdf),
            ),
            ft.TextButton(
                content=ft.Row(
                    spacing=5,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.CONTENT_COPY_ROUNDED, size=14),
                        ft.Text("Copy All", size=12),
                    ],
                ),
                on_click=lambda _: page.run_task(_copy_source),
            ),
        ]
        if on_open_material and (vault_match or mat_item.get("id")):
            actions_list.append(
                ft.OutlinedButton(
                    content=ft.Row(
                        spacing=5,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.OPEN_IN_NEW_ROUNDED, size=14, color=color_token),
                            ft.Text("Open Module Cockpit", size=12, weight=ft.FontWeight.W_600),
                        ],
                    ),
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
                    on_click=_jump_to_material,
                )
            )
        actions_list.append(
            ft.Button(
                "Done",
                bgcolor=color_token,
                color=ft.Colors.WHITE,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
                on_click=_close_reader,
            )
        )

        reader_dlg[0] = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=18),
            bgcolor=ft.Colors.SURFACE,
            title=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        spacing=10,
                        tight=True,
                        expand=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Container(
                                width=34,
                                height=34,
                                border_radius=ft.BorderRadius.all(9),
                                bgcolor=ft.Colors.with_opacity(0.12, color_token),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.MENU_BOOK_ROUNDED, color=color_token, size=18),
                            ),
                            ft.Column(
                                spacing=1,
                                tight=True,
                                expand=True,
                                controls=[
                                    ft.Text(
                                        m_title,
                                        size=14.5,
                                        weight=ft.FontWeight.W_800,
                                        max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                    ft.Text(
                                        summary_label,
                                        size=10.5,
                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                    ),
                                ],
                            ),
                        ],
                    ),
                    ft.IconButton(icon=ft.Icons.CLOSE_ROUNDED, icon_size=18, on_click=_close_reader),
                ],
            ),
            content=ft.Container(
                width=dlg_w,
                height=dlg_h,
                content=ft.Column(
                    spacing=10,
                    expand=True,
                    horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    controls=content_controls,
                ),
            ),
            actions=actions_list,
        )
        safe_open_dialog(page, reader_dlg[0], tag="journal_source_reader")

    # ── Modal 2: Full-Screen Executive Study Guide Reader ────────────────────
    def _open_full_study_guide_modal(e=None):
        j = state["journal"] or {}
        guide_text = (j.get("study_guide") or "").strip()
        color_token = resolve_journal_color(j.get("color"))
        j_title = j.get("title") or "Course Journal"

        if not guide_text:
            show_page_snackbar(page, "No Executive Study Guide generated yet. Tap 'Synthesize' to build one!")
            return

        guide_dlg = [None]

        def _close_guide_dlg(ev=None):
            if guide_dlg[0]:
                safe_close_dialog(page, guide_dlg[0])

        async def _copy_guide():
            await safe_set_clipboard(page, guide_text)
            show_page_snackbar(page, "Executive Study Guide copied to clipboard!")

        dlg_w = min(740, int((page.width or 420) * 0.94))
        dlg_h = min(560, int((page.height or 720) * 0.72))

        guide_dlg[0] = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=20),
            bgcolor=ft.Colors.SURFACE,
            title=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        spacing=10,
                        tight=True,
                        expand=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Container(
                                width=36,
                                height=36,
                                border_radius=ft.BorderRadius.all(10),
                                bgcolor=ft.Colors.with_opacity(0.12, color_token),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.MENU_BOOK_ROUNDED, color=color_token, size=19),
                            ),
                            ft.Column(
                                spacing=1,
                                tight=True,
                                expand=True,
                                controls=[
                                    ft.Text(
                                        f"Executive Study Guide: {j_title}",
                                        size=15,
                                        weight=ft.FontWeight.W_800,
                                        max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                    ft.Text(
                                        "Cross-module syllabus synthesis, key concepts & exam traps",
                                        size=11,
                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                    ),
                                ],
                            ),
                        ],
                    ),
                    ft.IconButton(icon=ft.Icons.CLOSE_ROUNDED, icon_size=18, on_click=_close_guide_dlg),
                ],
            ),
            content=ft.Container(
                width=dlg_w,
                height=dlg_h,
                padding=ft.Padding.all(16),
                border_radius=ft.BorderRadius.all(14),
                bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                content=ft.Column(
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                    controls=[
                        ft.SelectionArea(
                            content=ft.Markdown(
                                guide_text,
                                selectable=True,
                                extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED,
                                on_tap_link=lambda ev: None,
                            )
                        ),
                    ],
                ),
            ),
            actions=[
                ft.TextButton(
                    content=ft.Row(
                        spacing=5,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.CONTENT_COPY_ROUNDED, size=14),
                            ft.Text("Copy Guide", size=12),
                        ],
                    ),
                    on_click=lambda _: page.run_task(_copy_guide),
                ),
                ft.Button(
                    "Done",
                    bgcolor=color_token,
                    color=ft.Colors.WHITE,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
                    on_click=_close_guide_dlg,
                ),
            ],
        )
        safe_open_dialog(page, guide_dlg[0], tag="journal_study_guide")

    # ── Modal 3: Edit Course Journal Details ─────────────────────────────────
    def _open_edit_journal_dialog(e=None):
        j = state["journal"] or {}
        color_token = resolve_journal_color(j.get("color"))
        edit_dlg = [None]
        picked_color = [j.get("color") or "teal"]

        title_tf = ft.TextField(
            label="Journal Title *",
            value=j.get("title") or "",
            border_radius=ft.BorderRadius.all(10),
            filled=False,
            bgcolor=ft.Colors.TRANSPARENT,
            border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
            focused_border_color=ft.Colors.PRIMARY,
            text_size=13,
            text_style=ft.TextStyle(weight=ft.FontWeight.W_600),
            content_padding=ft.Padding.symmetric(horizontal=14, vertical=12),
            autofocus=True,
        )
        desc_tf = ft.TextField(
            label="Description (Optional)",
            value=j.get("description") or "",
            border_radius=ft.BorderRadius.all(10),
            filled=False,
            bgcolor=ft.Colors.TRANSPARENT,
            border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
            focused_border_color=ft.Colors.PRIMARY,
            multiline=True,
            min_lines=1,
            max_lines=2,
            text_size=12,
            content_padding=ft.Padding.symmetric(horizontal=14, vertical=10),
        )

        color_row = ft.Row(spacing=7, scroll=ft.ScrollMode.AUTO, controls=[])

        def _refresh_color_dots():
            color_row.controls = [
                ft.Container(
                    width=22,
                    height=22,
                    border_radius=ft.BorderRadius.all(11),
                    bgcolor=c_val,
                    border=ft.Border.all(2, ft.Colors.ON_SURFACE if picked_color[0] == c_key else ft.Colors.TRANSPARENT),
                    alignment=ft.Alignment.CENTER,
                    ink=True,
                    tooltip=c_name,
                    content=ft.Icon(ft.Icons.CHECK_ROUNDED, size=12, color=ft.Colors.WHITE) if picked_color[0] == c_key else None,
                    on_click=(lambda k=c_key: lambda _: _select_col(k))(),
                )
                for c_key, c_name, c_val in JOURNAL_COLORS
            ]

        def _select_col(k):
            picked_color[0] = k
            _refresh_color_dots()
            safe_update_dialog(page, edit_dlg[0])

        _refresh_color_dots()

        def _close_edit(ev=None):
            if edit_dlg[0]:
                safe_close_dialog(page, edit_dlg[0])

        save_btn = ft.Button(
            "Save Changes",
            bgcolor=color_token,
            color=ft.Colors.WHITE,
            height=38,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
        )

        async def _save_edits(ev=None):
            new_t = (title_tf.value or "").strip()
            if not new_t:
                show_page_snackbar(page, "Journal title cannot be empty.")
                return
            save_btn.disabled = True
            save_btn.content = ft.ProgressRing(width=15, height=15, stroke_width=2, color=ft.Colors.ON_PRIMARY)
            safe_update_dialog(page, edit_dlg[0])

            payload = {
                "title": new_t,
                "description": (desc_tf.value or "").strip(),
                "color": picked_color[0],
            }
            res = await update_journal_api(token, jid_str, payload)
            if res.get("id"):
                state["journal"]["title"] = res.get("title", new_t)
                state["journal"]["description"] = res.get("description", payload["description"])
                state["journal"]["color"] = res.get("color", picked_color[0])
                if on_journal_updated:
                    try:
                        on_journal_updated(state["journal"])
                    except Exception:
                        pass
                _close_edit()
                show_page_snackbar(page, "Journal details updated!")
                _render_cockpit()
            else:
                save_btn.disabled = False
                save_btn.content = ft.Text("Save Changes", color=ft.Colors.ON_PRIMARY)
                show_page_snackbar(page, res.get("error", "Could not update journal."))
                safe_update_dialog(page, edit_dlg[0])

        save_btn.on_click = lambda _: page.run_task(_save_edits)

        edit_dlg[0] = ft.AlertDialog(
            modal=True,
            shape=ft.RoundedRectangleBorder(radius=18),
            bgcolor=ft.Colors.SURFACE,
            title=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        spacing=10,
                        tight=True,
                        controls=[
                            ft.Container(
                                width=34,
                                height=34,
                                border_radius=ft.BorderRadius.all(10),
                                bgcolor=ft.Colors.with_opacity(0.12, color_token),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.EDIT_OUTLINED, color=color_token, size=18),
                            ),
                            ft.Text("Edit Course Journal", size=15, weight=ft.FontWeight.W_800),
                        ],
                    ),
                    ft.IconButton(icon=ft.Icons.CLOSE_ROUNDED, icon_size=18, on_click=_close_edit),
                ],
            ),
            content=ft.Container(
                width=min(440, int((page.width or 400) * 0.92)),
                content=ft.Column(
                    spacing=12,
                    tight=True,
                    controls=[
                        title_tf,
                        desc_tf,
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Text("Notebook Accent", size=11.5, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE_VARIANT),
                                color_row,
                            ],
                        ),
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=_close_edit),
                save_btn,
            ],
        )
        safe_open_dialog(page, edit_dlg[0], tag="journal_edit")

    # ── Main Cockpit Renderer ────────────────────────────────────────────────
    def _render_cockpit():
        j = state["journal"]
        if not j:
            return

        screen_w = page.width or 400
        is_mobile = bool(screen_w < 768)
        is_small = bool(screen_w < 460)

        mats = state["materials"]
        fc_count = int(j.get("flashcards_count", j.get("flashcard_count", 0)) or 0)
        q_count = int(j.get("questions_count", j.get("question_count", 0)) or 0)
        m_count = len(mats)
        is_gen = bool(state["is_generating"] or j.get("is_generating"))
        guide_text = (j.get("study_guide") or "").strip()
        color_token = resolve_journal_color(j.get("color"))
        j_title = j.get("title") or "Course Journal"
        j_desc = (j.get("description") or "").strip()

        def _handle_back(e=None):
            state["unmounted"] = True
            if on_back:
                on_back()

        # ── Regenerate / Synthesize Handler (3x Credits) ─────────────────────
        async def _do_regenerate(replace_existing: bool = False):
            if m_count == 0:
                show_page_snackbar(page, "Please attach at least 1 source module before generating.")
                return
            state["is_generating"] = True
            _update_journal_status_ui({
                "is_generating": True,
                "progress_percent": 15,
                "stage": "Starting synthesis across modules...",
                "flashcards_count": 0,
                "questions_count": 0 if replace_existing else q_count,
                "has_study_guide": bool(guide_text),
            })
            res = await generate_journal_content_api(token, jid_str, replace_existing=replace_existing)
            if res.get("status") == "processing":
                show_page_snackbar(page, "AI is synthesizing your Course Mock Exam! Questions and Study Guide will update automatically.")
                if not state["polling_active"]:
                    page.run_task(_poll_generation)
            else:
                state["is_generating"] = False
                _update_journal_status_ui({
                    "is_generating": False,
                    "progress_percent": 0,
                    "stage": "Ready",
                    "flashcards_count": 0,
                    "questions_count": q_count,
                    "has_study_guide": bool(guide_text),
                })
                show_page_snackbar(page, res.get("error", "Could not start generation."))

        def _confirm_regenerate(e=None):
            if m_count == 0:
                show_page_snackbar(page, "Please attach at least 1 source module before generating.")
                return

            # Edge case check: person has < 3 generation credits
            q_info = state.get("quota_info")
            if q_info and not q_info.get("is_unlimited", False):
                used = q_info.get("used", 0)
                limit = q_info.get("limit", 15)
                remaining = q_info.get("remaining", max(0, limit - used))
                if remaining < 3:
                    insuf_dlg = [None]
                    def _close_insuf(ev=None):
                        if insuf_dlg[0]:
                            safe_close_dialog(page, insuf_dlg[0])

                    def _go_store(ev=None):
                        _close_insuf()
                        page.navigate("/store")

                    insuf_dlg[0] = ft.AlertDialog(
                        modal=True,
                        shape=ft.RoundedRectangleBorder(radius=18),
                        bgcolor=ft.Colors.SURFACE,
                        title=ft.Row(
                            spacing=8,
                            controls=[
                                ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=ft.Colors.AMBER_600, size=20),
                                ft.Text("Insufficient AI Credits", size=15, weight=ft.FontWeight.W_800),
                            ],
                        ),
                        content=ft.Column(
                            tight=True,
                            spacing=8,
                            controls=[
                                ft.Text(
                                    "Synthesizing an integrated Course Mock Exam & Study Guide requires 3 AI Generation Credits.",
                                    size=12.5,
                                    weight=ft.FontWeight.W_600,
                                ),
                                ft.Text(
                                    f"You currently have {remaining} credit(s) remaining today (less than 3). Top up credits or upgrade in Store to synthesize.",
                                    size=12,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                            ],
                        ),
                        actions=[
                            ft.TextButton("Cancel", on_click=_close_insuf),
                            ft.Button(
                                content=ft.Row(
                                    spacing=6,
                                    tight=True,
                                    controls=[
                                        ft.Icon(ft.Icons.SHOPPING_BAG_ROUNDED, size=15, color=ft.Colors.ON_PRIMARY),
                                        ft.Text("Top Up in Store →", size=12, weight=ft.FontWeight.W_800, color=ft.Colors.ON_PRIMARY),
                                    ],
                                ),
                                bgcolor=ft.Colors.PRIMARY,
                                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
                                on_click=_go_store,
                            ),
                        ],
                    )
                    safe_open_dialog(page, insuf_dlg[0], tag="insufficient_synth_credits")
                    return

            conf_dlg = [None]

            def _close_conf(ev=None):
                if conf_dlg[0]:
                    safe_close_dialog(page, conf_dlg[0])

            if q_count > 0:
                dlg_content = ft.Column(
                    spacing=12,
                    tight=True,
                    controls=[
                        ft.Text(
                            f"This Course Journal currently has {q_count} Mock Exam questions. Choose how to synthesize (consumes 3 AI Generation Credits):",
                            size=12.5,
                            color=ft.Colors.ON_SURFACE,
                        ),
                        ft.Container(
                            padding=ft.Padding.all(12),
                            border_radius=ft.BorderRadius.all(10),
                            bgcolor=ft.Colors.with_opacity(0.04, color_token),
                            border=ft.Border.all(1, ft.Colors.with_opacity(0.18, color_token)),
                            content=ft.Column(
                                spacing=4,
                                tight=True,
                                controls=[
                                    ft.Text("• Expand Exam Pool: Generates new questions and adds them to your pool.", size=11.5, weight=ft.FontWeight.W_600),
                                    ft.Text("• Fresh Replacement: Clears existing questions and generates a brand new set.", size=11.5, color=ft.Colors.ON_SURFACE_VARIANT),
                                ],
                            ),
                        ),
                    ],
                )
                dlg_actions = [
                    ft.TextButton("Cancel", on_click=_close_conf),
                    ft.OutlinedButton(
                        "Fresh Replacement",
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=10),
                            side=ft.BorderSide(1, ft.Colors.with_opacity(0.25, ft.Colors.ON_SURFACE)),
                        ),
                        on_click=lambda _: (_close_conf(), page.run_task(_do_regenerate, True)),
                    ),
                    ft.Button(
                        content=ft.Row(
                            spacing=6,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.ADD_ROUNDED, size=15, color=ft.Colors.ON_PRIMARY),
                                ft.Text("Expand Pool", size=12, weight=ft.FontWeight.W_800, color=ft.Colors.ON_PRIMARY),
                            ],
                        ),
                        bgcolor=ft.Colors.PRIMARY,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
                        on_click=lambda _: (_close_conf(), page.run_task(_do_regenerate, False)),
                    ),
                ]
            else:
                dlg_content = ft.Text(
                    f"Synthesizing an integrated Course Mock Exam & Study Guide across all {m_count} module(s) consumes 3 AI Generation Credits.\n\nProceed?",
                    size=12.5,
                )
                dlg_actions = [
                    ft.TextButton("Cancel", on_click=_close_conf),
                    ft.Button(
                        content=ft.Row(
                            spacing=6,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=15, color=ft.Colors.ON_PRIMARY),
                                ft.Text("Synthesize (3x Credits)", size=12, weight=ft.FontWeight.W_800, color=ft.Colors.ON_PRIMARY),
                            ],
                        ),
                        bgcolor=ft.Colors.PRIMARY,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
                        on_click=lambda _: (_close_conf(), page.run_task(_do_regenerate, False)),
                    ),
                ]

            conf_dlg[0] = ft.AlertDialog(
                modal=True,
                shape=ft.RoundedRectangleBorder(radius=18),
                bgcolor=ft.Colors.SURFACE,
                title=ft.Row(
                    spacing=8,
                    controls=[
                        ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=color_token, size=20),
                        ft.Text("Synthesize Course Mock Exam", size=15, weight=ft.FontWeight.W_800),
                    ],
                ),
                content=dlg_content,
                actions=dlg_actions,
            )
            safe_open_dialog(page, conf_dlg[0], tag="journal_synth_confirm")

        # ── Delete Journal Handler ───────────────────────────────────────────
        async def _do_delete():
            res = await delete_journal_api(token, jid_str)
            if res.get("success"):
                show_page_snackbar(page, "Journal deleted. Individual materials remain safely in your vault.")
                state["unmounted"] = True
                if on_back:
                    on_back()
            else:
                show_page_snackbar(page, res.get("error", "Failed to delete journal."))

        def _confirm_delete(e=None):
            del_dlg = [None]

            def _close_del(ev=None):
                if del_dlg[0]:
                    safe_close_dialog(page, del_dlg[0])

            del_dlg[0] = ft.AlertDialog(
                modal=True,
                shape=ft.RoundedRectangleBorder(radius=18),
                bgcolor=ft.Colors.SURFACE,
                title=ft.Text("Delete Course Journal?", size=15, weight=ft.FontWeight.W_800),
                content=ft.Text(
                    "This removes this notebook container and generated journal cards. "
                    "Your underlying study materials in your Study Vault will NOT be deleted.",
                    size=12.5,
                ),
                actions=[
                    ft.TextButton("Cancel", on_click=_close_del),
                    ft.Button(
                        "Delete Journal",
                        bgcolor=ft.Colors.ERROR,
                        color=ft.Colors.ON_ERROR,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
                        on_click=lambda _: (_close_del(), page.run_task(_do_delete)),
                    ),
                ],
            )
            safe_open_dialog(page, del_dlg[0], tag="journal_delete_confirm")

        # ── Attach Vault Modules Dialog ──────────────────────────────────────
        def _open_attach_source_dialog(e=None):
            if len(mats) >= 5:
                show_page_snackbar(page, "Course Journals are capped at 5 sources maximum.")
                return

            attached_ids = {str(m.get("id")) for m in mats}
            available_vault = [v for v in vault_mats if str(v.get("id")) not in attached_ids]

            if not available_vault:
                show_page_snackbar(page, "All materials in your vault are already attached to this Journal.")
                return

            chosen_to_attach = set()
            attach_filter_q = [""]
            pick_dlg = [None]
            counter_lbl = ft.Text(
                f"{len(mats)} / 5 Modules",
                size=10.5,
                weight=ft.FontWeight.W_800,
                color=color_token,
            )
            counter_pill = ft.Container(
                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                border_radius=ft.BorderRadius.all(999),
                bgcolor=ft.Colors.with_opacity(0.12, color_token),
                content=counter_lbl,
            )

            def _close_pick(ev=None):
                if pick_dlg[0]:
                    safe_close_dialog(page, pick_dlg[0])

            attach_confirm_btn = ft.Button(
                "Attach Selected",
                bgcolor=ft.Colors.PRIMARY,
                color=ft.Colors.ON_PRIMARY,
                height=38,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
            )

            async def _do_attach():
                if not chosen_to_attach:
                    show_page_snackbar(page, "Select at least 1 module to attach.")
                    return
                attach_confirm_btn.disabled = True
                attach_confirm_btn.content = ft.ProgressRing(width=15, height=15, stroke_width=2, color=ft.Colors.ON_PRIMARY)
                safe_update_dialog(page, pick_dlg[0])

                res = await add_materials_to_journal_api(token, jid_str, list(chosen_to_attach))
                _close_pick()
                if res.get("id"):
                    show_page_snackbar(page, "Added modules to Course Journal! 📚")
                    await _fetch_journal_data()
                else:
                    show_page_snackbar(page, res.get("error", "Could not add modules."))

            attach_confirm_btn.on_click = lambda _: page.run_task(_do_attach)

            pick_col = ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, expand=True)

            def _on_attach_search(ev=None):
                attach_filter_q[0] = (attach_search_tf.value or "").strip().lower()
                _rebuild_pick_list()
                safe_update_dialog(page, pick_dlg[0])

            attach_search_tf = ft.TextField(
                hint_text="Search vault modules...",
                border=ft.InputBorder.NONE,
                filled=False,
                bgcolor=ft.Colors.TRANSPARENT,
                dense=True,
                text_size=12,
                hint_style=ft.TextStyle(size=12, color=ft.Colors.with_opacity(0.45, ft.Colors.ON_SURFACE)),
                content_padding=ft.Padding.symmetric(horizontal=4, vertical=8),
                expand=True,
                on_change=_on_attach_search,
            )

            attach_search_bar = ft.Container(
                height=36,
                padding=ft.Padding.symmetric(horizontal=10),
                border_radius=ft.BorderRadius.all(10),
                bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.14, ft.Colors.ON_SURFACE)),
                content=ft.Row(
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.SEARCH_ROUNDED, size=15, color=ft.Colors.ON_SURFACE_VARIANT),
                        attach_search_tf,
                    ],
                ),
            )

            def _rebuild_pick_list():
                pick_col.controls.clear()
                total_after = len(mats) + len(chosen_to_attach)
                counter_lbl.value = f"{total_after} / 5 Modules"
                q = attach_filter_q[0]
                filtered_avail = [
                    v for v in available_vault
                    if not q or q in (v.get("title") or "").lower()
                ]
                if not filtered_avail:
                    pick_col.controls.append(
                        ft.Container(
                            padding=ft.Padding.all(16),
                            alignment=ft.Alignment.CENTER,
                            content=ft.Text(f"No modules matching '{q}'", size=11.5, color=ft.Colors.ON_SURFACE_VARIANT),
                        )
                    )
                    return

                for v in filtered_avail:
                    vid = str(v.get("id"))
                    is_sel = vid in chosen_to_attach
                    stype = (v.get("source_type") or "text").lower()
                    v_icon = ft.Icons.PICTURE_AS_PDF_ROUNDED if "pdf" in stype else (
                        ft.Icons.CAMERA_ALT_ROUNDED if "photo" in stype else ft.Icons.DESCRIPTION_ROUNDED
                    )

                    def _toggle_v(ev=None, target_vid=vid):
                        if target_vid in chosen_to_attach:
                            chosen_to_attach.discard(target_vid)
                        else:
                            if len(mats) + len(chosen_to_attach) >= 5:
                                show_page_snackbar(page, "A Course Journal is capped at 5 sources.")
                                return
                            chosen_to_attach.add(target_vid)
                        _rebuild_pick_list()
                        safe_update_dialog(page, pick_dlg[0])

                    pick_col.controls.append(
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                            border_radius=ft.BorderRadius.all(10),
                            bgcolor=ft.Colors.with_opacity(0.08, color_token) if is_sel else ft.Colors.SURFACE,
                            border=ft.Border.all(
                                1.2 if is_sel else 1,
                                color_token if is_sel else ft.Colors.with_opacity(0.09, ft.Colors.ON_SURFACE),
                            ),
                            ink=True,
                            on_click=_toggle_v,
                            content=ft.Row(
                                spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Icon(
                                        ft.Icons.CHECK_CIRCLE_ROUNDED if is_sel else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED,
                                        size=18,
                                        color=color_token if is_sel else ft.Colors.with_opacity(0.35, ft.Colors.ON_SURFACE),
                                    ),
                                    ft.Icon(v_icon, size=15, color=color_token if is_sel else ft.Colors.ON_SURFACE_VARIANT),
                                    ft.Text(
                                        v.get("title") or "Untitled Material",
                                        size=12,
                                        weight=ft.FontWeight.W_700 if is_sel else ft.FontWeight.W_500,
                                        max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                        expand=True,
                                    ),
                                ],
                            ),
                        )
                    )

            _rebuild_pick_list()

            pick_dlg[0] = ft.AlertDialog(
                modal=True,
                shape=ft.RoundedRectangleBorder(radius=18),
                bgcolor=ft.Colors.SURFACE,
                title=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Row(
                            spacing=8,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.LIBRARY_ADD_ROUNDED, size=18, color=color_token),
                                ft.Text("Attach Vault Modules", size=15, weight=ft.FontWeight.W_800),
                            ],
                        ),
                        counter_pill,
                    ],
                ),
                content=ft.Container(
                    width=min(420, int((page.width or 400) * 0.92)),
                    height=min(280, max(150, len(available_vault) * 48 + 56)),
                    content=ft.Column(
                        spacing=10,
                        expand=True,
                        controls=[
                            attach_search_bar,
                            pick_col,
                        ],
                    ),
                ),
                actions=[
                    ft.TextButton("Cancel", on_click=_close_pick),
                    attach_confirm_btn,
                ],
            )
            safe_open_dialog(page, pick_dlg[0], tag="journal_attach_modules")

        # ── Launchers for Mock Exam & CBT Simulation ─────────────────────────
        async def _launch_journal_exam(e=None):
            if state["launching_action"]:
                return
            state["launching_action"] = "exam"
            qs = await get_journal_questions_api(token, jid_str, limit=30)
            state["launching_action"] = None
            if not qs:
                show_page_snackbar(page, "No mock exam questions found yet for this Journal. Tap 'Synthesize Mock Exam' to generate!")
                return
            if on_start_exam:
                state["unmounted"] = True
                on_start_exam(qs)

        async def _configure_journal_exam(e=None):
            if state["launching_action"]:
                return
            state["launching_action"] = "configure_exam"
            mids = [str(m.get("id")) for m in state["materials"] if m.get("id")]
            if on_configure_exam:
                state["unmounted"] = True
                try:
                    on_configure_exam(mids, j_title)
                except TypeError:
                    qs = await get_journal_questions_api(token, jid_str, limit=50)
                    on_configure_exam(qs)
                state["launching_action"] = None
                return
            qs = await get_journal_questions_api(token, jid_str, limit=50)
            state["launching_action"] = None
            if not qs:
                show_page_snackbar(page, "No mock exam questions found yet for this Journal. Tap 'Synthesize Mock Exam' to generate!")
                return
            if on_start_exam:
                state["unmounted"] = True
                on_start_exam(qs)

        # ── 1. Streamlined Top Navigation Bar (Matches _build_material_cockpit) ──
        back_label = "Back" if is_small else "Back to Study Hub"

        top_bar_right = []
        if guide_text:
            top_bar_right.append(
                ft.OutlinedButton(
                    content=ft.Row(
                        spacing=4,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.MENU_BOOK_ROUNDED, size=13, color=ft.Colors.ON_SURFACE),
                            ft.Text("Guide" if is_small else "Study Guide", size=10.5, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                        ],
                    ),
                    style=ft.ButtonStyle(
                        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                        side=ft.BorderSide(1, ft.Colors.with_opacity(0.20, ft.Colors.ON_SURFACE)),
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                    tooltip="Open full-screen Executive Study Guide",
                    on_click=_open_full_study_guide_modal,
                )
            )

        top_bar_right.append(
            ft.OutlinedButton(
                content=ft.Row(
                    spacing=4,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=13, color=color_token),
                        ft.Text("Synthesize" if not is_small else "AI Pack", size=10.5, weight=ft.FontWeight.W_700, color=color_token),
                    ],
                ),
                style=ft.ButtonStyle(
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    side=ft.BorderSide(1.2, ft.Colors.with_opacity(0.35, color_token)),
                    shape=ft.RoundedRectangleBorder(radius=8),
                ),
                tooltip="Synthesize or regenerate Course Mock Exam & Study Guide (3x Credits)",
                disabled=is_gen,
                on_click=_confirm_regenerate,
            )
        )

        top_bar_right.append(
            ft.PopupMenuButton(
                icon=ft.Icons.MORE_VERT_ROUNDED,
                icon_size=18,
                icon_color=ft.Colors.ON_SURFACE_VARIANT,
                tooltip="Journal Options",
                items=[
                    ft.PopupMenuItem(
                        content=ft.Row(
                            spacing=8,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.EDIT_OUTLINED, size=15, color=ft.Colors.ON_SURFACE),
                                ft.Text("Edit Journal Details", size=12.5),
                            ],
                        ),
                        on_click=_open_edit_journal_dialog,
                    ),
                    ft.PopupMenuItem(
                        content=ft.Row(
                            spacing=8,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.LIBRARY_ADD_ROUNDED, size=15, color=color_token),
                                ft.Text("Attach Vault Module...", size=12.5),
                            ],
                        ),
                        on_click=_open_attach_source_dialog,
                    ),
                    ft.PopupMenuItem(
                        content=ft.Row(
                            spacing=8,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=15, color=color_token),
                                ft.Text("Regenerate Mock Exam", size=12, color=color_token),
                            ],
                        ),
                        on_click=_confirm_regenerate,
                    ),
                    ft.PopupMenuItem(
                        content=ft.Row(
                            spacing=8,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.DELETE_OUTLINE_ROUNDED, size=15, color=ft.Colors.ERROR),
                                ft.Text("Delete Journal", size=12, color=ft.Colors.ERROR),
                            ],
                        ),
                        on_click=_confirm_delete,
                    ),
                ],
            )
        )

        top_bar = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.TextButton(
                    content=ft.Row(
                        spacing=5,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.ARROW_BACK_ROUNDED, size=15),
                            ft.Text(back_label, size=12.5, weight=ft.FontWeight.W_700),
                        ],
                    ),
                    on_click=_handle_back,
                ),
                ft.Row(
                    spacing=6,
                    tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=top_bar_right,
                ),
            ],
        )

        # ── 2. Course Journal Hero Banner (Matches _build_material_cockpit) ──
        hero_tag_pill = ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            border_radius=ft.BorderRadius.all(6),
            bgcolor=ft.Colors.with_opacity(0.14, color_token),
            content=ft.Row(
                spacing=5,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.AUTO_STORIES_ROUNDED, size=12, color=color_token),
                    ft.Text(
                        f"COURSE JOURNAL • {m_count}/5 MODULES",
                        size=9.5,
                        weight=ft.FontWeight.W_800,
                        color=color_token,
                    ),
                ],
            ),
        )

        status_pill_icon = ft.Icon(
            ft.Icons.AUTO_AWESOME_ROUNDED if is_gen else ft.Icons.CHECK_CIRCLE_ROUNDED,
            size=12,
            color=ft.Colors.PRIMARY if is_gen else ft.Colors.GREEN_700,
        )
        status_pill_text = ft.Text(
            "Synthesizing Pack..." if is_gen else "Notebook Ready",
            size=9.5,
            weight=ft.FontWeight.W_800,
            color=ft.Colors.PRIMARY if is_gen else ft.Colors.GREEN_700,
        )
        status_pill_badge = ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            border_radius=ft.BorderRadius.all(999),
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY if is_gen else ft.Colors.GREEN_700),
            content=ft.Row(
                spacing=5,
                tight=True,
                controls=[
                    status_pill_icon,
                    status_pill_text,
                ],
            ),
        )

        hero_subtitle = (
            j_desc
            if j_desc
            else (
                "Nu Age AI is synthesizing cross-module flashcards, exam questions & your Executive Study Guide..."
                if is_gen
                else f"Unified multi-module notebook combining {m_count} course source(s) with grounded Socratic tutoring."
            )
        )

        def _meta_chip(icon_name, text_label, accent=None):
            return ft.Container(
                padding=ft.Padding.symmetric(horizontal=8, vertical=3.5),
                border_radius=ft.BorderRadius.all(6),
                bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                content=ft.Row(
                    spacing=4,
                    tight=True,
                    controls=[
                        ft.Icon(icon_name, size=11, color=accent or ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(
                            text_label,
                            size=10,
                            weight=ft.FontWeight.W_700 if accent else ft.FontWeight.W_600,
                            color=ft.Colors.ON_SURFACE if accent else ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ],
                ),
            )

        hero_chips_row = ft.Row(
            spacing=6,
            run_spacing=6,
            tight=True,
            wrap=True,
            controls=[
                _meta_chip(ft.Icons.LAYERS_ROUNDED, f"{m_count}/5 Modules", color_token),
                _meta_chip(ft.Icons.TIMER_OUTLINED, f"{q_count} Mock Exam Questions" if q_count else "Exam Questions Pending", color_token if q_count else None),
                _meta_chip(
                    ft.Icons.VERIFIED_ROUNDED if guide_text else ft.Icons.AUTO_AWESOME_ROUNDED,
                    "Executive Guide Ready" if guide_text else "Grounded AI Tutor",
                ),
            ],
        )

        primary_generating_cta_btn = ft.FilledButton(
            content=ft.Row(
                spacing=7,
                tight=True,
                controls=[
                    ft.ProgressRing(width=13, height=13, stroke_width=2, color=ft.Colors.ON_PRIMARY),
                    ft.Text("Synthesizing Journal Pack...", size=12.5, weight=ft.FontWeight.W_800, color=ft.Colors.ON_PRIMARY),
                ],
            ),
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=30),
                bgcolor=ft.Colors.with_opacity(0.65, color_token),
                padding=ft.Padding.symmetric(horizontal=18, vertical=11),
            ),
            disabled=True,
        )

        primary_ready_cta_btn = ft.FilledButton(
            content=ft.Row(
                spacing=6,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, size=16, color=ft.Colors.WHITE),
                    ft.Text(f"Take Course Mock Exam ({q_count} Qs)", size=12.5, weight=ft.FontWeight.W_800, color=ft.Colors.WHITE),
                    ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=14, color=ft.Colors.WHITE),
                ],
            ),
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=30),
                bgcolor=color_token,
                padding=ft.Padding.symmetric(horizontal=18, vertical=11),
            ),
            on_click=lambda _: page.run_task(_launch_journal_exam),
        )

        primary_synth_cta_btn = ft.FilledButton(
            content=ft.Row(
                spacing=6,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=16, color=ft.Colors.WHITE),
                    ft.Text("Synthesize Mock Exam & Guide (3x Credits)", size=12.5, weight=ft.FontWeight.W_800, color=ft.Colors.WHITE),
                ],
            ),
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=30),
                bgcolor=color_token,
                padding=ft.Padding.symmetric(horizontal=18, vertical=11),
            ),
            on_click=_confirm_regenerate,
        )

        hero_cta_slot = ft.Container(
            content=primary_generating_cta_btn if is_gen else (primary_ready_cta_btn if q_count > 0 else primary_synth_cta_btn)
        )

        cta_row_controls = [hero_cta_slot]
        if guide_text:
            cta_row_controls.append(
                ft.OutlinedButton(
                    content=ft.Row(
                        spacing=6,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.MENU_BOOK_ROUNDED, size=15, color=color_token),
                            ft.Text("Open Study Guide", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                        ],
                    ),
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=30),
                        side=ft.BorderSide(1.2, ft.Colors.with_opacity(0.35, color_token)),
                        padding=ft.Padding.symmetric(horizontal=16, vertical=11),
                    ),
                    on_click=_open_full_study_guide_modal,
                )
            )

        # ── Ambient Generation Card (Modern non-blocking background status) ──
        ambient_gen_card = ft.Container(
            visible=is_gen,
            padding=ft.Padding.symmetric(horizontal=16, vertical=14),
            border_radius=ft.BorderRadius.all(14),
            bgcolor=ft.Colors.with_opacity(0.06, color_token),
            border=ft.Border.all(1.2, ft.Colors.with_opacity(0.25, color_token)),
            content=ft.Row(
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(
                        width=36,
                        height=36,
                        border_radius=ft.BorderRadius.all(10),
                        bgcolor=ft.Colors.with_opacity(0.12, color_token),
                        alignment=ft.Alignment.CENTER,
                        content=ft.ProgressRing(width=18, height=18, stroke_width=2.4, color=color_token),
                    ),
                    ft.Column(
                        spacing=2,
                        tight=True,
                        expand=True,
                        controls=[
                            ft.Row(
                                spacing=6,
                                tight=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Text(
                                        "Nu Age AI is synthesizing your course journal",
                                        size=12.5,
                                        weight=ft.FontWeight.W_800,
                                        color=ft.Colors.ON_SURFACE,
                                    ),
                                    ft.Container(
                                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                        border_radius=ft.BorderRadius.all(4),
                                        bgcolor=ft.Colors.with_opacity(0.12, color_token),
                                        content=ft.Text("Background", size=9.5, weight=ft.FontWeight.W_700, color=color_token),
                                    ),
                                ],
                            ),
                            ft.Text(
                                "Your study notes, flashcards and quiz questions are synthesizing in the background. Feel free to explore other courses—your notebook will be ready when you return.",
                                size=11,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                            ),
                        ],
                    ),
                ],
            ),
        )

        def _update_status_ui_impl(status_data: dict):
            st = str(status_data.get("status") or "completed").lower()
            still_gen = bool(status_data.get("is_generating", st in ("processing", "queued", "pending", "in_progress")))
            ambient_gen_card.visible = still_gen

            if still_gen:
                status_pill_icon.name = ft.Icons.AUTO_AWESOME_ROUNDED
                status_pill_icon.color = ft.Colors.PRIMARY
                status_pill_text.value = "Generating in Background"
                status_pill_text.color = ft.Colors.PRIMARY
                status_pill_badge.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY)
                hero_cta_slot.content = primary_generating_cta_btn
            else:
                status_pill_icon.name = ft.Icons.CHECK_CIRCLE_ROUNDED
                status_pill_icon.color = ft.Colors.GREEN_700
                status_pill_text.value = "Journal Ready"
                status_pill_text.color = ft.Colors.GREEN_700
                status_pill_badge.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.GREEN_700)
                hero_cta_slot.content = primary_ready_cta_btn

            try:
                page.update()
            except Exception:
                pass

        _update_journal_status_ui_slot[0] = _update_status_ui_impl

        hero_banner = ft.Container(
            width=float("inf"),
            border_radius=ft.BorderRadius.all(20),
            border=ft.Border.all(1.2, ft.Colors.with_opacity(0.26, color_token)),
            shadow=ft.BoxShadow(blur_radius=18, color=ft.Colors.with_opacity(0.06, color_token), offset=ft.Offset(0, 4)),
            gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
                colors=[
                    ft.Colors.with_opacity(0.18, color_token),
                    ft.Colors.with_opacity(0.04, color_token),
                    ft.Colors.SURFACE,
                ],
            ),
            padding=ft.Padding.all(18 if is_mobile else 22),
            content=ft.Column(
                spacing=12,
                tight=True,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            hero_tag_pill,
                            status_pill_badge,
                        ],
                    ),
                    ft.Column(
                        spacing=4,
                        tight=True,
                        controls=[
                            ft.Text(
                                j_title,
                                size=22 if is_small else 24,
                                weight=ft.FontWeight.W_900,
                                color=ft.Colors.ON_SURFACE,
                            ),
                            ft.Text(
                                hero_subtitle,
                                size=12.5,
                                color=ft.Colors.ON_SURFACE_VARIANT,
                                max_lines=2,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                    ),
                    hero_chips_row,
                    ft.Row(
                        spacing=8,
                        tight=True,
                        wrap=True,
                        controls=cta_row_controls,
                    ),
                    ambient_gen_card,
                ],
            ),
        )

        # ── 3. Constituent Course Syllabus (1–5 Modules) ─────────────────────
        module_rows = []
        for idx, m in enumerate(mats):
            mid = str(m.get("id"))
            m_title = m.get("title") or f"Module {idx + 1}"
            stype = (m.get("source_type") or "text").lower()
            m_content = m.get("content") or ""
            if not m_content:
                v_match = next((v for v in vault_mats if str(v.get("id")) == mid), None)
                if v_match:
                    m_content = v_match.get("content") or ""
            word_cnt = len(m_content.split()) if m_content else 0

            icon_name = ft.Icons.DESCRIPTION_ROUNDED
            type_tag = "Notes"
            if "pdf" in stype or m_title.lower().endswith(".pdf"):
                icon_name = ft.Icons.PICTURE_AS_PDF_ROUNDED
                type_tag = "PDF"
            elif "photo" in stype or "image" in stype:
                icon_name = ft.Icons.CAMERA_ALT_ROUNDED
                type_tag = "Image"
            elif "youtube" in stype or "url" in stype:
                icon_name = ft.Icons.PLAY_CIRCLE_FILL_ROUNDED
                type_tag = "Video"

            async def _remove_m(target_id=mid):
                res = await remove_material_from_journal_api(token, jid_str, target_id)
                if res.get("success"):
                    show_page_snackbar(page, "Module unlinked from journal.")
                    await _fetch_journal_data()
                else:
                    show_page_snackbar(page, res.get("error", "Could not unlink module."))

            def _jump_single_module(item=m):
                if on_open_material:
                    v_match = next((v for v in vault_mats if str(v.get("id")) == str(item.get("id"))), None)
                    state["unmounted"] = True
                    on_open_material(v_match or item)

            right_actions = [
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=9, vertical=5),
                    border_radius=ft.BorderRadius.all(8),
                    bgcolor=ft.Colors.with_opacity(0.08, color_token),
                    ink=True,
                    tooltip="View Question Bank & study notes",
                    on_click=(lambda item=m: lambda _: _open_source_reader(item, color_token))(),
                    content=ft.Row(
                        spacing=4,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.MENU_BOOK_ROUNDED, size=13, color=color_token),
                            ft.Text("Q-Bank" if is_small else "Question Bank", size=10.5, weight=ft.FontWeight.W_700, color=color_token),
                        ],
                    ),
                ),
            ]
            if on_open_material:
                right_actions.append(
                    ft.IconButton(
                        icon=ft.Icons.OPEN_IN_NEW_ROUNDED,
                        icon_size=15,
                        icon_color=ft.Colors.ON_SURFACE_VARIANT,
                        width=28,
                        height=28,
                        style=ft.ButtonStyle(padding=ft.Padding.all(0)),
                        tooltip="Open single-module cockpit",
                        on_click=(lambda item=m: lambda _: _jump_single_module(item))(),
                    )
                )
            right_actions.append(
                ft.IconButton(
                    icon=ft.Icons.REMOVE_CIRCLE_OUTLINE_ROUNDED,
                    icon_size=15,
                    icon_color=ft.Colors.ON_SURFACE_VARIANT,
                    width=28,
                    height=28,
                    style=ft.ButtonStyle(padding=ft.Padding.all(0)),
                    tooltip="Unlink module from journal (keeps in Vault)",
                    on_click=(lambda i=mid: lambda _: page.run_task(_remove_m, i))(),
                )
            )

            module_rows.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                    border_radius=ft.BorderRadius.all(12),
                    bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                    ink=True,
                    on_click=(lambda item=m: lambda _: _open_source_reader(item, color_token))(),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(
                                spacing=10,
                                tight=True,
                                expand=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Container(
                                        width=30,
                                        height=30,
                                        border_radius=ft.BorderRadius.all(8),
                                        bgcolor=ft.Colors.with_opacity(0.12, color_token),
                                        alignment=ft.Alignment.CENTER,
                                        content=ft.Text(
                                            f"{idx + 1:02d}",
                                            size=11,
                                            weight=ft.FontWeight.W_800,
                                            color=color_token,
                                        ),
                                    ),
                                    ft.Column(
                                        spacing=2,
                                        tight=True,
                                        expand=True,
                                        controls=[
                                            ft.Text(
                                                m_title,
                                                size=12.5,
                                                weight=ft.FontWeight.W_700,
                                                color=ft.Colors.ON_SURFACE,
                                                max_lines=1,
                                                overflow=ft.TextOverflow.ELLIPSIS,
                                            ),
                                            ft.Row(
                                                spacing=6,
                                                tight=True,
                                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                                controls=[
                                                    ft.Icon(icon_name, size=11, color=ft.Colors.ON_SURFACE_VARIANT),
                                                    ft.Text(
                                                        f"{type_tag} • {word_cnt:,} words" if word_cnt else type_tag,
                                                        size=10.5,
                                                        color=ft.Colors.ON_SURFACE_VARIANT,
                                                    ),
                                                ],
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            ft.Row(
                                spacing=4,
                                tight=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=right_actions,
                            ),
                        ],
                    ),
                )
            )

        empty_modules_box = ft.Container(
            padding=ft.Padding.symmetric(horizontal=18, vertical=20),
            border_radius=ft.BorderRadius.all(12),
            bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
            alignment=ft.Alignment.CENTER,
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=6,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.LIBRARY_BOOKS_OUTLINED, size=24, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text("No modules attached yet", size=12.5, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                    ft.Text(
                        "Attach up to 5 modules from your Study Vault to ground the AI Tutor and study pack.",
                        size=11,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
            ),
        )

        modules_syllabus_card = ft.Container(
            bgcolor=ft.Colors.SURFACE,
            border_radius=ft.BorderRadius.all(18),
            border=ft.Border.all(1.2, ft.Colors.with_opacity(0.14, color_token)),
            shadow=ft.BoxShadow(blur_radius=12, color=ft.Colors.with_opacity(0.03, color_token), offset=ft.Offset(0, 3)),
            padding=ft.Padding.all(16),
            content=ft.Column(
                spacing=12,
                tight=True,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(
                                spacing=8,
                                tight=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Container(
                                        width=30,
                                        height=30,
                                        border_radius=ft.BorderRadius.all(8),
                                        bgcolor=ft.Colors.with_opacity(0.12, color_token),
                                        alignment=ft.Alignment.CENTER,
                                        content=ft.Icon(ft.Icons.LAYERS_ROUNDED, size=16, color=color_token),
                                    ),
                                    ft.Column(
                                        spacing=1,
                                        tight=True,
                                        controls=[
                                            ft.Text("Course Syllabus & Attached Modules", size=13.5, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                            ft.Text("Tap any module to read its extracted notes or jump to its single-material cockpit", size=10.5, color=ft.Colors.ON_SURFACE_VARIANT),
                                        ],
                                    ),
                                ],
                            ),
                            ft.OutlinedButton(
                                content=ft.Row(
                                    spacing=4,
                                    tight=True,
                                    controls=[
                                        ft.Icon(ft.Icons.ADD_ROUNDED, size=14, color=color_token),
                                        ft.Text("Attach" if is_small else "Attach Module", size=11, weight=ft.FontWeight.W_700, color=color_token),
                                    ],
                                ),
                                style=ft.ButtonStyle(
                                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                                    shape=ft.RoundedRectangleBorder(radius=9),
                                ),
                                disabled=(m_count >= 5),
                                on_click=_open_attach_source_dialog,
                            ),
                        ],
                    ),
                    ft.Column(spacing=8, tight=True, controls=module_rows) if module_rows else empty_modules_box,
                ],
            ),
        )

        # ── 4. Dedicated Course Mock Exam Hub ────────────────────────────────
        exam_icon_box = ft.Container(
            width=44,
            height=44,
            border_radius=ft.BorderRadius.all(12),
            bgcolor=ft.Colors.with_opacity(0.12, color_token),
            alignment=ft.Alignment.CENTER,
            content=ft.Icon(ft.Icons.TIMER_OUTLINED, color=color_token, size=22),
        )

        exam_cbt_pill = ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            border_radius=ft.BorderRadius.all(6),
            bgcolor=ft.Colors.with_opacity(0.10, color_token),
            content=ft.Row(
                spacing=4,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.FLASH_ON_ROUNDED, size=11, color=color_token),
                    ft.Text(
                        "TIMED CBT SIMULATOR",
                        size=9.5,
                        weight=ft.FontWeight.W_800,
                        color=color_token,
                    ),
                ],
            ),
        )

        exam_metrics_row = ft.Row(
            spacing=8,
            wrap=True,
            controls=[
                _meta_chip(ft.Icons.HELP_OUTLINE_ROUNDED, f"{q_count} Exam Questions" if q_count else "Exam Questions Pending", color_token if q_count else None),
                _meta_chip(ft.Icons.SCHEDULE_ROUNDED, "~45 Mins Exam Length", None),
                _meta_chip(ft.Icons.ANALYTICS_OUTLINED, "Scored with Step-by-Step Explanations", None),
            ],
        )

        exam_start_btn = ft.Button(
            content=ft.Row(
                spacing=7,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, size=17, color=ft.Colors.WHITE),
                    ft.Text("Start Course Mock Exam", size=12.5, weight=ft.FontWeight.W_800, color=ft.Colors.WHITE),
                ],
            ),
            bgcolor=color_token,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=ft.Padding.symmetric(horizontal=18, vertical=11),
                elevation=0,
            ),
            disabled=(q_count == 0 or is_gen),
            on_click=lambda _: page.run_task(_launch_journal_exam),
        )

        exam_configure_btn = ft.OutlinedButton(
            content=ft.Row(
                spacing=6,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.TUNE_ROUNDED, size=15, color=ft.Colors.ON_SURFACE),
                    ft.Text("Configure Exam", size=12, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                ],
            ),
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                side=ft.BorderSide(1, ft.Colors.with_opacity(0.20, ft.Colors.ON_SURFACE)),
                padding=ft.Padding.symmetric(horizontal=14, vertical=11),
            ),
            disabled=(q_count == 0 or is_gen),
            on_click=lambda _: page.run_task(_configure_journal_exam),
        )

        exam_synth_btn = ft.Button(
            content=ft.Row(
                spacing=7,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=15, color=ft.Colors.ON_PRIMARY),
                    ft.Text("Synthesize Mock Exam (3x Credits)", size=12, weight=ft.FontWeight.W_800, color=ft.Colors.ON_PRIMARY),
                ],
            ),
            bgcolor=ft.Colors.PRIMARY,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=ft.Padding.symmetric(horizontal=16, vertical=11),
                elevation=0,
            ),
            disabled=is_gen,
            on_click=_confirm_regenerate,
        )

        exam_actions = [exam_start_btn]
        if on_configure_exam:
            exam_actions.append(exam_configure_btn)
        if q_count == 0:
            exam_actions = [exam_synth_btn]

        mock_exam_hub_card = ft.Container(
            bgcolor=ft.Colors.SURFACE,
            border_radius=ft.BorderRadius.all(18),
            border=ft.Border.all(1.2, ft.Colors.with_opacity(0.20, color_token)),
            shadow=ft.BoxShadow(blur_radius=14, color=ft.Colors.with_opacity(0.04, color_token), offset=ft.Offset(0, 3)),
            gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
                colors=[
                    ft.Colors.with_opacity(0.07, color_token),
                    ft.Colors.SURFACE,
                ],
            ),
            padding=ft.Padding.all(16),
            content=ft.Column(
                spacing=12,
                tight=True,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(
                                spacing=10,
                                tight=True,
                                expand=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    exam_icon_box,
                                    ft.Column(
                                        spacing=2,
                                        tight=True,
                                        expand=True,
                                        controls=[
                                            ft.Text("Comprehensive Course Mock Exam", size=14, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                            ft.Text(
                                                "Multi-module examination synthesizing principles and scenarios across all attached lectures",
                                                size=10.5,
                                                color=ft.Colors.ON_SURFACE_VARIANT,
                                                max_lines=1,
                                                overflow=ft.TextOverflow.ELLIPSIS,
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            exam_cbt_pill,
                        ],
                    ),
                    exam_metrics_row,
                    ft.Row(
                        spacing=8,
                        wrap=True,
                        controls=exam_actions,
                    ),
                ],
            ),
        )

        # ── 5. Executive Course Study Guide Card ─────────────────────────────
        async def _copy_study_guide():
            if guide_text:
                await safe_set_clipboard(page, guide_text)
                show_page_snackbar(page, "Executive Study Guide copied to clipboard!")

        def _toggle_guide_collapse(e=None):
            state["guide_collapsed"] = not state["guide_collapsed"]
            guide_body.visible = not state["guide_collapsed"]
            guide_chevron_btn.icon = ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED if state["guide_collapsed"] else ft.Icons.KEYBOARD_ARROW_UP_ROUNDED
            guide_chevron_btn.tooltip = "Expand Study Guide" if state["guide_collapsed"] else "Collapse Study Guide"
            page.update()

        if guide_text:
            guide_body = ft.Container(
                visible=not state["guide_collapsed"],
                height=340,
                padding=ft.Padding.all(14),
                border_radius=ft.BorderRadius.all(12),
                bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                content=ft.Column(
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                    controls=[
                        ft.SelectionArea(
                            content=ft.Markdown(
                                guide_text,
                                selectable=True,
                                extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED,
                                on_tap_link=lambda ev: None,
                            )
                        ),
                    ],
                ),
            )
        elif is_gen:
            guide_body = ft.Container(
                visible=not state["guide_collapsed"],
                padding=ft.Padding.symmetric(horizontal=20, vertical=24),
                border_radius=ft.BorderRadius.all(12),
                bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
                alignment=ft.Alignment.CENTER,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                    tight=True,
                    controls=[
                        ft.ProgressRing(width=22, height=22, stroke_width=2.2, color=color_token),
                        ft.Text("Synthesizing Executive Study Guide...", size=12.5, weight=ft.FontWeight.W_800),
                        ft.Text(
                            "Analyzing your attached modules to draft an overarching syllabus brief, concept connections, and exam pitfalls.",
                            size=11,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                ),
            )
        else:
            guide_body = ft.Container(
                visible=not state["guide_collapsed"],
                padding=ft.Padding.symmetric(horizontal=20, vertical=20),
                border_radius=ft.BorderRadius.all(12),
                bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    wrap=True,
                    spacing=12,
                    run_spacing=10,
                    controls=[
                        ft.Column(
                            spacing=3,
                            tight=True,
                            controls=[
                                ft.Text("Executive Syllabus Synthesis Not Generated Yet", size=12.5, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                ft.Text(
                                    "Your individual module flashcards & quizzes are already unified above. Synthesize a cross-module Study Guide & exam scenarios anytime.",
                                    size=11,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                            ],
                        ),
                        ft.Button(
                            content=ft.Row(
                                spacing=6,
                                tight=True,
                                controls=[
                                    ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=14, color=ft.Colors.WHITE),
                                    ft.Text("Synthesize Guide (3x Credits)", size=11.5, weight=ft.FontWeight.W_700, color=ft.Colors.WHITE),
                                ],
                            ),
                            bgcolor=color_token,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
                            on_click=_confirm_regenerate,
                        ),
                    ],
                ),
            )

        guide_header_actions = []
        if guide_text:
            guide_header_actions.extend([
                ft.IconButton(
                    icon=ft.Icons.OPEN_IN_FULL_ROUNDED,
                    icon_size=15,
                    icon_color=color_token,
                    tooltip="Open Full-Screen Reader",
                    style=ft.ButtonStyle(padding=ft.Padding.all(4)),
                    on_click=_open_full_study_guide_modal,
                ),
                ft.IconButton(
                    icon=ft.Icons.CONTENT_COPY_ROUNDED,
                    icon_size=15,
                    icon_color=ft.Colors.ON_SURFACE_VARIANT,
                    tooltip="Copy Study Guide",
                    style=ft.ButtonStyle(padding=ft.Padding.all(4)),
                    on_click=lambda _: page.run_task(_copy_study_guide),
                ),
            ])
        guide_chevron_btn = ft.IconButton(
            icon=ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED if state["guide_collapsed"] else ft.Icons.KEYBOARD_ARROW_UP_ROUNDED,
            icon_size=18,
            icon_color=ft.Colors.ON_SURFACE_VARIANT,
            tooltip="Expand Study Guide" if state["guide_collapsed"] else "Collapse Study Guide",
            style=ft.ButtonStyle(padding=ft.Padding.all(4)),
            on_click=_toggle_guide_collapse,
        )
        guide_header_actions.append(guide_chevron_btn)

        study_guide_card = ft.Container(
            bgcolor=ft.Colors.SURFACE,
            border_radius=ft.BorderRadius.all(18),
            border=ft.Border.all(1.2, ft.Colors.with_opacity(0.14, color_token)),
            shadow=ft.BoxShadow(blur_radius=12, color=ft.Colors.with_opacity(0.03, color_token), offset=ft.Offset(0, 3)),
            padding=ft.Padding.all(16),
            content=ft.Column(
                spacing=12,
                tight=True,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(
                                spacing=8,
                                tight=True,
                                expand=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Container(
                                        width=30,
                                        height=30,
                                        border_radius=ft.BorderRadius.all(8),
                                        bgcolor=ft.Colors.with_opacity(0.12, color_token),
                                        alignment=ft.Alignment.CENTER,
                                        content=ft.Icon(ft.Icons.MENU_BOOK_ROUNDED, size=16, color=color_token),
                                    ),
                                    ft.Column(
                                        spacing=1,
                                        tight=True,
                                        expand=True,
                                        controls=[
                                            ft.Text("Executive Course Study Guide", size=13.5, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                            ft.Text(
                                                "Cross-module syllabus synthesis, key formulas & exam pitfalls",
                                                size=10.5,
                                                color=ft.Colors.ON_SURFACE_VARIANT,
                                                max_lines=1,
                                                overflow=ft.TextOverflow.ELLIPSIS,
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            ft.Row(
                                spacing=2,
                                tight=True,
                                controls=guide_header_actions,
                            ),
                        ],
                    ),
                    guide_body,
                ],
            ),
        )

        # ── 6. Grounded Course AI Tutor (Nu Owl Multi-Module Coach) ──────────
        # ── 6. Course Journal AI Tutor (Nu Owl) (Matches _build_material_cockpit) ──
        ai_chat_messages = ft.Column(
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
            auto_scroll=True,
            expand=True,
        )

        avail_w = screen_w - (320 if screen_w >= 800 else 0) - 64
        max_bubble_width = min(560, max(210, int(avail_w * 0.82)))

        welcome_bubble = ft.Container(
            bgcolor=ft.Colors.with_opacity(0.06, color_token),
            border_radius=ft.BorderRadius.all(12),
            padding=ft.Padding.all(12),
            content=ft.Row(
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.START,
                controls=[
                    ft.Image(src="study_owl_mascot.png", width=26, height=26, fit=ft.BoxFit.CONTAIN),
                    ft.Column(
                        spacing=3,
                        tight=True,
                        expand=True,
                        controls=[
                            ft.Text("Nu Owl", size=10.5, weight=ft.FontWeight.W_800, color=color_token),
                            ft.Text(
                                f"I've read across all {m_count} module(s) in '{j_title}'. Ask me to connect concepts between lectures, explain formulas, or quiz you on exam traps!",
                                size=12,
                                color=ft.Colors.ON_SURFACE,
                            ),
                        ],
                    ),
                ],
            ),
        )

        ai_chat_messages.controls.append(welcome_bubble)

        def _user_bubble(user_text: str):
            bubble_w = min(max_bubble_width, max(80, int(len(user_text) * 8.5) + 36))
            return ft.Row(
                alignment=ft.MainAxisAlignment.END,
                controls=[
                    ft.Container(
                        bgcolor=color_token,
                        border_radius=ft.BorderRadius.all(14),
                        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                        width=bubble_w,
                        content=ft.Text(
                            user_text,
                            size=12,
                            color=ft.Colors.WHITE,
                            no_wrap=False,
                            selectable=True,
                        ),
                    ),
                ],
            )

        def _assistant_bubble(reply_text: str, is_animated: bool = False, is_error: bool = False):
            md_control = ft.Markdown(
                "" if (is_animated and not is_error) else reply_text,
                selectable=True,
                extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
                on_tap_link=lambda e: page.run_task(safe_set_clipboard, page, e.data),
            )
            hdr_color = ft.Colors.AMBER_600 if is_error else color_token
            hdr_title = "Nu Owl • Service Notice" if is_error else "Nu Owl"
            bubble_bg = ft.Colors.with_opacity(0.08, ft.Colors.AMBER_600) if is_error else ft.Colors.with_opacity(0.06, color_token)

            bubble_controls = [
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            spacing=6,
                            tight=True,
                            controls=[
                                ft.Image(src="study_owl_mascot.png", width=18, height=18, fit=ft.BoxFit.CONTAIN),
                                ft.Text(hdr_title, size=10, weight=ft.FontWeight.W_800, color=hdr_color),
                            ],
                        ),
                        ft.IconButton(
                            icon=ft.Icons.COPY_ROUNDED,
                            icon_size=13,
                            icon_color=ft.Colors.ON_SURFACE_VARIANT,
                            tooltip="Copy response",
                            on_click=lambda _, t=reply_text: page.run_task(safe_set_clipboard, page, t),
                        ),
                    ],
                ),
                md_control,
            ]
            bubble_container = ft.Container(
                bgcolor=bubble_bg,
                border_radius=ft.BorderRadius.all(12),
                padding=ft.Padding.all(12),
                content=ft.Column(
                    spacing=6,
                    tight=True,
                    controls=bubble_controls,
                ),
            )
            bubble_container._md_control = md_control
            bubble_container._full_text = reply_text
            return bubble_container

        # Load persisted messages from cache
        for msg in state["chat_messages"]:
            if msg.get("is_user") or msg.get("role") == "user":
                ai_chat_messages.controls.append(_user_bubble(msg.get("text", "")))
            else:
                ai_chat_messages.controls.append(_assistant_bubble(msg.get("text", "")))

        ai_input_tf = ft.TextField(
            hint_text=f"Ask a question across {j_title}...",
            border=ft.InputBorder.NONE,
            filled=False,
            bgcolor=ft.Colors.TRANSPARENT,
            text_size=13,
            multiline=True,
            min_lines=1,
            max_lines=4,
            expand=True,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=10),
            dense=True,
        )

        ai_send_btn = ft.IconButton(
            icon=ft.Icons.SEND_ROUNDED,
            icon_size=18,
            icon_color=color_token,
            tooltip="Send question",
        )
        ai_spinner = ft.ProgressRing(width=18, height=18, stroke_width=2.5, color=color_token, visible=False)

        clear_chat_btn = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
            icon_size=16,
            icon_color=ft.Colors.ON_SURFACE_VARIANT,
            tooltip="Clear conversation",
            visible=bool(state["chat_messages"]),
            style=ft.ButtonStyle(padding=ft.Padding.all(4)),
        )

        async def _clear_tutor_chat(e=None):
            state["chat_messages"].clear()
            _JOURNAL_CHAT_CACHE.pop(chat_cache_key, None)
            ai_chat_messages.controls.clear()
            ai_chat_messages.controls.append(welcome_bubble)
            clear_chat_btn.visible = False
            page.update()
            show_page_snackbar(page, "AI Tutor chat history cleared.")

        clear_chat_btn.on_click = lambda _: page.run_task(_clear_tutor_chat)

        quota_status_bar = ft.Container(
            visible=False,
            padding=ft.Padding.symmetric(horizontal=4, vertical=2),
        )

        def _apply_quota_ui(quota: dict):
            if not quota:
                return
            state["quota_info"] = quota
            is_unlimited = quota.get("is_unlimited", False)
            used = quota.get("used", 0)
            limit = quota.get("limit", 15)
            remaining = quota.get("remaining", max(0, limit - used))
            is_locked = quota.get("locked", False) or (not is_unlimited and used >= limit)

            if is_unlimited:
                ai_input_tf.disabled = False
                ai_send_btn.disabled = False
                ai_input_tf.hint_text = f"Ask a question across {j_title}..."
                quota_status_bar.content = ft.Row(
                    spacing=5,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=13, color=color_token),
                        ft.Text("Pro Scholar · Unlimited AI Tutor Queries", size=11, weight=ft.FontWeight.W_600, color=color_token),
                    ],
                )
                quota_status_bar.visible = True
            elif is_locked:
                ai_input_tf.disabled = True
                ai_send_btn.disabled = True
                ai_input_tf.hint_text = "Daily limit reached (15/15). Upgrade to Pro for unlimited queries."
                quota_status_bar.content = ft.Row(
                    spacing=6,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            spacing=6,
                            controls=[
                                ft.Icon(ft.Icons.LOCK_ROUNDED, size=13, color=ft.Colors.AMBER_600),
                                ft.Text(f"Daily limit reached ({limit}/{limit}) · Resets 00:00 UTC", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.AMBER_600),
                            ],
                        ),
                        ft.TextButton(
                            content=ft.Text("Upgrade to Pro", size=11, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY),
                            style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=8, vertical=2)),
                            on_click=lambda _: open_chat_quota_modal(page, quota),
                        ),
                    ],
                )
                quota_status_bar.visible = True
            else:
                ai_input_tf.disabled = False
                ai_send_btn.disabled = False
                ai_input_tf.hint_text = f"Ask a question across {j_title}..."
                quota_status_bar.content = ft.Row(
                    spacing=6,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            spacing=6,
                            controls=[
                                ft.Icon(ft.Icons.BOLT_ROUNDED, size=13, color=ft.Colors.GREY_500),
                                ft.Text(f"⚡ {used}/{limit} free queries used today ({remaining} left · Resets 00:00 UTC)", size=11, color=ft.Colors.GREY_500),
                            ],
                        ),
                        ft.TextButton(
                            content=ft.Text("Get Unlimited", size=11, weight=ft.FontWeight.W_700, color=color_token),
                            style=ft.ButtonStyle(padding=ft.Padding.symmetric(horizontal=8, vertical=2)),
                            on_click=lambda _: page.navigate("/store"),
                        ),
                    ],
                )
                quota_status_bar.visible = True
            page.update()

        async def _fetch_quota():
            try:
                quota = await get_ai_tutor_quota_api(token)
                _apply_quota_ui(quota)
            except Exception as q_err:
                print(f"[journal_cockpit] quota check error: {q_err}")

        page.run_task(_fetch_quota)

        typing_indicator = ft.Container(
            bgcolor=ft.Colors.with_opacity(0.04, color_token),
            border_radius=ft.BorderRadius.all(12),
            padding=ft.Padding.all(10),
            content=ft.Row(
                spacing=8,
                tight=True,
                controls=[
                    ft.ProgressRing(width=14, height=14, stroke_width=2, color=color_token),
                    ft.Text("Thinking and synthesizing across journal modules…", size=11, color=ft.Colors.GREY_500),
                ],
            ),
        )

        async def _send_ai_query(query_text: str):
            clean_q = (query_text or "").strip()
            if not clean_q or state.get("is_chatting"):
                return

            # Check if already locked
            if state.get("quota_info", {}).get("locked"):
                open_chat_quota_modal(page, state.get("quota_info", {}))
                return

            ai_input_tf.value = ""
            state["is_chatting"] = True
            ai_send_btn.visible = False
            ai_spinner.visible = True
            clear_chat_btn.visible = True
            page.update()

            # Append user message with bounded mobile width
            state["chat_messages"].append({"role": "user", "text": clean_q, "is_user": True})
            _JOURNAL_CHAT_CACHE[chat_cache_key] = list(state["chat_messages"])
            ai_chat_messages.controls.append(_user_bubble(clean_q))

            # Typing indicator bubble
            ai_chat_messages.controls.append(typing_indicator)
            page.update()

            conv_history = [
                {"role": ("user" if m.get("is_user") or m.get("role") == "user" else "assistant"), "content": m.get("text", "")}
                for m in state["chat_messages"][:-1]
            ]
            is_error = False
            try:
                res = await ask_journal_tutor_api(
                    token=token,
                    journal_id=jid_str,
                    query=clean_q,
                    conversation_history=conv_history,
                )
                if res.get("quota_locked"):
                    is_error = True
                    state.setdefault("quota_info", {})
                    state["quota_info"]["locked"] = True
                    state["quota_info"]["used"] = 15
                    state["quota_info"]["remaining"] = 0
                    _apply_quota_ui(state["quota_info"])
                    open_chat_quota_modal(page, state["quota_info"])
                    reply = get_user_friendly_ai_error(is_quota=True)
                elif res.get("is_ai_error") or res.get("error"):
                    is_error = True
                    reply = get_user_friendly_ai_error(res.get("error"))
                else:
                    quota_payload = res.get("quota")
                    if quota_payload:
                        _apply_quota_ui(quota_payload)
                    elif not state.get("quota_info", {}).get("is_unlimited", False):
                        curr_q = state.setdefault("quota_info", {"limit": 15, "used": 0, "remaining": 15, "is_unlimited": False})
                        curr_q["used"] = curr_q.get("used", 0) + 1
                        curr_q["remaining"] = max(0, curr_q.get("limit", 15) - curr_q["used"])
                        curr_q["locked"] = curr_q["used"] >= curr_q.get("limit", 15)
                        _apply_quota_ui(curr_q)
                    reply = res.get("reply") or res.get("message")
                    if not reply:
                        is_error = True
                        reply = get_user_friendly_ai_error()
            except Exception as ex:
                is_error = True
                print(f"[journal_cockpit] AI Tutor error: {ex}")
                reply = get_user_friendly_ai_error(str(ex))

            # Remove typing indicator
            if typing_indicator in ai_chat_messages.controls:
                ai_chat_messages.controls.remove(typing_indicator)

            # Safeguard conversation history: NEVER persist error messages into AI context memory!
            if not is_error:
                state["chat_messages"].append({"role": "assistant", "text": reply, "is_user": False})
                _JOURNAL_CHAT_CACHE[chat_cache_key] = list(state["chat_messages"])
            else:
                # If error occurred, pop the failed user prompt so next turn remains completely clean
                if state["chat_messages"] and state["chat_messages"][-1].get("is_user"):
                    state["chat_messages"].pop()
                    _JOURNAL_CHAT_CACHE[chat_cache_key] = list(state["chat_messages"])

            asst_bubble = _assistant_bubble(reply, is_animated=not is_error, is_error=is_error)
            ai_chat_messages.controls.append(asst_bubble)

            state["is_chatting"] = False
            ai_send_btn.visible = True
            ai_spinner.visible = False
            page.update()

            if not is_error:
                # Stream typing animation only for genuine assistant answers
                await stream_typing_animation(
                    target_control=asst_bubble._md_control,
                    full_text=reply,
                    page=page,
                    scroll_container=ai_chat_messages,
                    words_per_chunk=2,
                    chunk_interval_ms=25,
                )

        def _on_chip_click(p_val: str):
            if state.get("quota_info", {}).get("locked"):
                open_chat_quota_modal(page, state.get("quota_info", {}))
                return
            page.run_task(_send_ai_query, p_val)

        ai_send_btn.on_click = lambda _: page.run_task(_send_ai_query, ai_input_tf.value)
        ai_input_tf.on_submit = lambda _: page.run_task(_send_ai_query, ai_input_tf.value)

        # Quick Prompt Chips (Matches self_study.py)
        prompt_chips = [
            ("✨ Summarize themes", f"Please summarize the overarching concepts and themes across {j_title} in concise bullet points."),
            ("⚠️ Top 3 exam traps", f"What are the top 3 exam traps or common misconceptions across these modules?"),
            ("🔗 Connect concepts", f"Connect the core ideas and relationships between the attached modules in this journal."),
            ("❓ Quiz me with a question", f"Ask me a conceptual question based on these journal modules to test my active recall."),
        ]

        chips_row = ft.Row(
            spacing=6,
            scroll=ft.ScrollMode.HIDDEN,
            controls=[
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                    border_radius=ft.BorderRadius.all(14),
                    bgcolor=ft.Colors.with_opacity(0.06, color_token),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.2, color_token)),
                    ink=True,
                    on_click=lambda _, prompt=p_val: _on_chip_click(prompt),
                    content=ft.Text(p_lbl, size=11, weight=ft.FontWeight.W_600, color=color_token),
                )
                for p_lbl, p_val in prompt_chips
            ],
        )

        chat_box_h = (
            max(420, int((page.height or 760) * 0.68))
            if state["tutor_maximized"]
            else (260 if is_mobile else 320)
        )

        chat_box_container = ft.Container(
            height=chat_box_h,
            padding=ft.Padding.all(8),
            border_radius=ft.BorderRadius.all(12),
            bgcolor=ft.Colors.with_opacity(0.025, ft.Colors.ON_SURFACE),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.07, ft.Colors.ON_SURFACE)),
            content=ai_chat_messages,
        )

        maximize_btn = ft.IconButton(
            icon=ft.Icons.FULLSCREEN_EXIT_ROUNDED if state["tutor_maximized"] else ft.Icons.FULLSCREEN_ROUNDED,
            icon_size=17,
            icon_color=ft.Colors.ON_SURFACE_VARIANT,
            tooltip="Exit Focus Mode" if state["tutor_maximized"] else "Maximize Tutor",
            visible=not state["tutor_minimized"],
            style=ft.ButtonStyle(padding=ft.Padding.all(4)),
        )

        minimize_btn = ft.IconButton(
            icon=ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED if state["tutor_minimized"] else ft.Icons.KEYBOARD_ARROW_UP_ROUNDED,
            icon_size=18,
            icon_color=ft.Colors.ON_SURFACE_VARIANT,
            tooltip="Expand Tutor" if state["tutor_minimized"] else "Collapse Tutor",
            style=ft.ButtonStyle(padding=ft.Padding.all(4)),
        )

        def _toggle_tutor_minimize(e=None):
            state["tutor_minimized"] = not state["tutor_minimized"]
            tutor_body.visible = not state["tutor_minimized"]
            minimize_btn.icon = ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED if state["tutor_minimized"] else ft.Icons.KEYBOARD_ARROW_UP_ROUNDED
            minimize_btn.tooltip = "Expand Tutor" if state["tutor_minimized"] else "Collapse Tutor"
            maximize_btn.visible = not state["tutor_minimized"]
            page.update()

        def _toggle_tutor_maximize(e=None):
            if state["tutor_minimized"]:
                state["tutor_minimized"] = False
                tutor_body.visible = True
            state["tutor_maximized"] = not state["tutor_maximized"]
            new_h = (
                max(420, int((page.height or 760) * 0.68))
                if state["tutor_maximized"]
                else (260 if is_mobile else 320)
            )
            chat_box_container.height = new_h
            maximize_btn.icon = ft.Icons.FULLSCREEN_EXIT_ROUNDED if state["tutor_maximized"] else ft.Icons.FULLSCREEN_ROUNDED
            maximize_btn.tooltip = "Exit Focus Mode" if state["tutor_maximized"] else "Maximize Tutor"
            page.update()

        maximize_btn.on_click = _toggle_tutor_maximize
        minimize_btn.on_click = _toggle_tutor_minimize

        tutor_body = ft.Column(
            spacing=10,
            visible=not state["tutor_minimized"],
            controls=[
                chat_box_container,
                chips_row,
                quota_status_bar,
                ft.Container(
                    border_radius=ft.BorderRadius.all(12),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE)),
                    padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ai_input_tf,
                            ai_spinner,
                            ai_send_btn,
                        ],
                    ),
                ),
            ],
        )

        ai_tutor_card = ft.Container(
            bgcolor=ft.Colors.SURFACE,
            border_radius=ft.BorderRadius.all(18),
            border=ft.Border.all(1.2, ft.Colors.with_opacity(0.16, color_token)),
            shadow=ft.BoxShadow(blur_radius=14, color=ft.Colors.with_opacity(0.04, color_token), offset=ft.Offset(0, 3)),
            padding=ft.Padding.all(16),
            content=ft.Column(
                spacing=12,
                tight=True,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(
                                spacing=8,
                                tight=True,
                                expand=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Container(
                                        width=32,
                                        height=32,
                                        border_radius=ft.BorderRadius.all(16),
                                        bgcolor=ft.Colors.with_opacity(0.12, color_token),
                                        alignment=ft.Alignment.CENTER,
                                        content=ft.Image(src="study_owl_mascot.png", width=22, height=22, fit=ft.BoxFit.CONTAIN),
                                    ),
                                    ft.Column(
                                        spacing=1,
                                        tight=True,
                                        expand=True,
                                        controls=[
                                            ft.Text("Nu Owl", size=13.5, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                            ft.Text(
                                                f"Grounded Socratic dialogue across {m_count} course module(s)",
                                                size=10,
                                                color=ft.Colors.ON_SURFACE_VARIANT,
                                                max_lines=1,
                                                overflow=ft.TextOverflow.ELLIPSIS,
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            ft.Row(
                                spacing=2,
                                tight=True,
                                controls=[
                                    maximize_btn,
                                    minimize_btn,
                                    clear_chat_btn,
                                ],
                            ),
                        ],
                    ),
                    tutor_body,
                ],
            ),
        )

        # ── Assemble Responsive Scrollable Cockpit ───────────────────────────
        cockpit_socket.controls = [
            ft.Container(
                padding=ft.Padding.symmetric(
                    horizontal=14 if is_small else 24,
                    vertical=16,
                ),
                content=ft.Column(
                    spacing=16,
                    controls=[
                        top_bar,
                        hero_banner,
                        _section_label(f"CONSTITUENT COURSE MODULES ({m_count}/5)", accent=color_token),
                        modules_syllabus_card,
                        _section_label("CROSS-MODULE CBT MOCK EXAM", accent=color_token),
                        mock_exam_hub_card,
                        _section_label("EXECUTIVE COURSE STUDY GUIDE", accent=color_token),
                        study_guide_card,
                        _section_label("SOCRATIC COURSE TUTOR", accent=color_token),
                        ai_tutor_card,
                        ft.Container(height=32),
                    ],
                ),
            ),
        ]
        page.update()

    # Trigger initial load
    page.run_task(_fetch_journal_data)

    return cockpit_socket
