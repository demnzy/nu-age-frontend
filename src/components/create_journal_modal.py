import flet as ft
import asyncio
from src.utils.file_opener import (
    show_page_snackbar,
    safe_open_dialog,
    safe_close_dialog,
    safe_update_dialog,
    run_after_modal_close,
)
from src.requests.study import (
    create_journal_api,
    create_multi_journal_api,
    generate_journal_content_api,
)

# Semantic accent colors for journals
JOURNAL_COLORS = [
    ("teal", "Teal", ft.Colors.TEAL_600),
    ("indigo", "Indigo", ft.Colors.INDIGO_600),
    ("purple", "Purple", ft.Colors.PURPLE_600),
    ("emerald", "Emerald", ft.Colors.GREEN_600),
    ("amber", "Amber", ft.Colors.AMBER_700),
    ("rose", "Rose", ft.Colors.PINK_600),
]

JOURNAL_COLOR_MAP = {k: v for k, _, v in JOURNAL_COLORS}


def resolve_journal_color(color_key: str | None) -> str:
    """Resolves a semantic journal color slug ('teal', 'emerald', 'rose', etc.) to a valid Flet color token."""
    if not color_key:
        return ft.Colors.TEAL_600
    return JOURNAL_COLOR_MAP.get(str(color_key).lower().strip(), ft.Colors.PRIMARY)


def open_create_journal_modal(
    page: ft.Page,
    token: str,
    vault_materials: list = None,
    preselected_material_ids: list = None,
    on_journal_created=None,
    user_quota: dict = None,
):
    """
    Dialog allowing learners to create a Course Journal (Course Notebook):
    1. Multi-Input Batch Upload (up to 5 sources: PDF, docs, images, notes) - NO YouTube URLs.
    2. Group Existing Vault Materials (up to 5 sources).
    Enforces 3x slot and 3x credit economics with clean edge-case quota conformance.
    """
    vault_mats = vault_materials or []
    preselected = {str(x) for x in (preselected_material_ids or []) if x is not None}

    # Extract or prepare quota trackers for < 3 edge cases
    dlg_ref = [None]
    quota_state = {
        "mat_rem": None,
        "gen_rem": None,
    }
    if user_quota:
        m_lim = user_quota.get("mat_lim")
        m_used = user_quota.get("mat_used", 0)
        quota_state["mat_rem"] = None if m_lim is None else max(0, m_lim - m_used)
        g_lim = user_quota.get("gen_lim")
        g_used = user_quota.get("gen_used", 0)
        quota_state["gen_rem"] = None if g_lim is None else max(0, g_lim - g_used)

    # Edge case: If user has < 3 material slots remaining, automatically default to vault grouping (0 slots)
    initial_mode = "existing" if ((preselected or vault_mats) and preselected) or (quota_state["mat_rem"] is not None and quota_state["mat_rem"] < 3) else "multi_upload"
    active_mode = [initial_mode]
    selected_color = ["teal"]
    queued_files = []  # list of dicts: {"name": str, "bytes": bytes, "mime_type": str, "size_str": str}
    queued_notes = []  # list of dicts: {"title": str, "content": str}
    chosen_vault_ids = set(preselected)
    vault_search_query = [""]

    screen_w = page.width or 400
    is_mobile = bool(screen_w < 560)

    # ── Header Icon Badge (tints dynamically with chosen notebook accent) ──
    header_icon_ctrl = ft.Icon(
        ft.Icons.AUTO_STORIES_ROUNDED,
        color=resolve_journal_color(selected_color[0]),
        size=20,
    )
    header_badge = ft.Container(
        width=38,
        height=38,
        border_radius=ft.BorderRadius.all(11),
        bgcolor=ft.Colors.with_opacity(0.12, resolve_journal_color(selected_color[0])),
        alignment=ft.Alignment.CENTER,
        content=header_icon_ctrl,
    )

    # ── Crisp Outlined Form Inputs (Zero muddy grey filled=True background) ──
    title_tf = ft.TextField(
        label="Journal / Course Title *",
        hint_text="e.g. BIO 101: Cell Biology & Genetics",
        border_radius=ft.BorderRadius.all(10),
        filled=False,
        bgcolor=ft.Colors.TRANSPARENT,
        border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
        focused_border_color=ft.Colors.PRIMARY,
        text_size=13,
        text_style=ft.TextStyle(weight=ft.FontWeight.W_600),
        label_style=ft.TextStyle(size=12, color=ft.Colors.ON_SURFACE_VARIANT),
        hint_style=ft.TextStyle(size=12, color=ft.Colors.with_opacity(0.45, ft.Colors.ON_SURFACE)),
        content_padding=ft.Padding.symmetric(horizontal=14, vertical=12),
        autofocus=False,
    )

    desc_tf = ft.TextField(
        label="Description or Syllabus Scope (Optional)",
        hint_text="Key modules, exam topics, or study objectives...",
        border_radius=ft.BorderRadius.all(10),
        filled=False,
        bgcolor=ft.Colors.TRANSPARENT,
        border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
        focused_border_color=ft.Colors.PRIMARY,
        multiline=True,
        min_lines=1,
        max_lines=2,
        text_size=12,
        label_style=ft.TextStyle(size=11.5, color=ft.Colors.ON_SURFACE_VARIANT),
        hint_style=ft.TextStyle(size=11.5, color=ft.Colors.with_opacity(0.45, ft.Colors.ON_SURFACE)),
        content_padding=ft.Padding.symmetric(horizontal=14, vertical=10),
    )

    # ── Unified AI Synthesis & Quota Card ──
    quota_badge_text = ft.Text(
        "3 Slots • 3 AI Credits",
        size=9.5,
        weight=ft.FontWeight.W_800,
        color=ft.Colors.PRIMARY,
    )
    quota_badge_pill = ft.Container(
        padding=ft.Padding.symmetric(horizontal=7, vertical=2),
        border_radius=ft.BorderRadius.all(999),
        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
        content=quota_badge_text,
    )
    quota_sub_text = ft.Text(
        "Synthesizes a cross-module Mock Exam & Executive Study Guide.",
        size=10.5,
        color=ft.Colors.ON_SURFACE_VARIANT,
    )
    quota_icon = ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=ft.Colors.PRIMARY, size=18)
    quota_icon_box = ft.Container(
        width=32,
        height=32,
        border_radius=ft.BorderRadius.all(9),
        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
        alignment=ft.Alignment.CENTER,
        content=quota_icon,
    )

    initial_gen_val = bool(active_mode[0] == "multi_upload")
    if quota_state["gen_rem"] is not None and quota_state["gen_rem"] < 3:
        initial_gen_val = False

    def _on_auto_gen_changed(e=None):
        if auto_gen_switch.value and quota_state["gen_rem"] is not None and quota_state["gen_rem"] < 3:
            auto_gen_switch.value = False
            show_page_snackbar(page, f"Full synthesis requires 3 AI generation credits ({quota_state['gen_rem']} remaining). Creating without synthesis consumes 0 credits.")
        _update_quota_banner()
        safe_update_dialog(page, dlg_ref[0])

    auto_gen_switch = ft.Switch(
        value=initial_gen_val,
        active_color=ft.Colors.PRIMARY,
        scale=0.85,
        on_change=_on_auto_gen_changed,
    )

    ai_synthesis_card = ft.Container(
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        border_radius=ft.BorderRadius.all(12),
        bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.PRIMARY),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.16, ft.Colors.PRIMARY)),
        content=ft.Row(
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                quota_icon_box,
                ft.Column(
                    spacing=2,
                    tight=True,
                    expand=True,
                    controls=[
                        ft.Row(
                            spacing=6,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            wrap=True,
                            controls=[
                                ft.Text(
                                    "Synthesize AI Study Pack",
                                    size=12,
                                    weight=ft.FontWeight.W_800,
                                    color=ft.Colors.ON_SURFACE,
                                ),
                                quota_badge_pill,
                            ],
                        ),
                        quota_sub_text,
                    ],
                ),
                auto_gen_switch,
            ],
        ),
    )

    def _update_quota_banner():
        is_upload = (active_mode[0] == "multi_upload")
        gen_on = bool(auto_gen_switch.value)
        if is_upload:
            if gen_on:
                accent = ft.Colors.PRIMARY
                quota_icon.name = ft.Icons.AUTO_AWESOME_ROUNDED
                quota_badge_text.value = "3 Upload Slots • 3 AI Credits"
                quota_sub_text.value = "Uploads up to 5 sources & synthesizes unified Mock Exam & Study Guide."
            else:
                accent = ft.Colors.AMBER_700
                quota_icon.name = ft.Icons.CLOUD_UPLOAD_ROUNDED
                quota_badge_text.value = "3 Upload Slots • 0 Credits Now"
                quota_sub_text.value = "Saves up to 5 sources into one notebook. You can synthesize the AI Pack later."
        else:
            if gen_on:
                accent = ft.Colors.PRIMARY
                quota_icon.name = ft.Icons.AUTO_AWESOME_ROUNDED
                quota_badge_text.value = "0 Upload Slots • 3 AI Credits"
                quota_sub_text.value = "Uses existing vault modules & synthesizes a unified Mock Exam & Study Guide."
            else:
                accent = ft.Colors.TEAL_600
                quota_icon.name = ft.Icons.VERIFIED_ROUNDED
                quota_badge_text.value = "Free Vault Grouping (0 Credits)"
                quota_sub_text.value = "Combines existing modules for the Grounded AI Tutor & Mock Exam."

        quota_icon.color = accent
        quota_icon_box.bgcolor = ft.Colors.with_opacity(0.12, accent)
        quota_badge_text.color = accent
        quota_badge_pill.bgcolor = ft.Colors.with_opacity(0.12, accent)
        ai_synthesis_card.bgcolor = ft.Colors.with_opacity(0.04, accent)
        ai_synthesis_card.border = ft.Border.all(1, ft.Colors.with_opacity(0.18, accent))

    # ── Sources Counter Pill & Scrollable Container ──
    sources_count_text = ft.Text(
        "0 / 5 Sources",
        size=10.5,
        weight=ft.FontWeight.W_800,
        color=ft.Colors.ON_SURFACE_VARIANT,
    )
    sources_count_pill = ft.Container(
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
        border_radius=ft.BorderRadius.all(999),
        bgcolor=ft.Colors.with_opacity(0.07, ft.Colors.ON_SURFACE),
        content=sources_count_text,
    )

    sources_list_col = ft.Column(spacing=6, tight=True, scroll=ft.ScrollMode.AUTO)
    sources_list_container = ft.Container(
        height=168,
        content=sources_list_col,
    )

    action_buttons_container = ft.Container()
    vault_search_container = ft.Container(visible=False)

    def _close_dlg(e=None):
        if dlg_ref[0]:
            safe_close_dialog(page, dlg_ref[0])

    # ── File Picker Handler ──
    async def _handle_pick_files(e=None):
        total_curr = len(queued_files) + len(queued_notes)
        if total_curr >= 5:
            show_page_snackbar(page, "Course Journals are capped at a maximum of 5 sources.")
            return

        try:
            picker = ft.FilePicker()
            files_res = await picker.pick_files(
                allow_multiple=True,
                allowed_extensions=["pdf", "txt", "png", "jpg", "jpeg", "md"],
            )
            if not files_res:
                return
            picked_list = getattr(files_res, "files", None) if not isinstance(files_res, list) else files_res
            if not picked_list:
                return

            remaining_slots = 5 - total_curr
            if len(picked_list) > remaining_slots:
                show_page_snackbar(page, f"Added first {remaining_slots} file(s) (Course Journals max at 5 sources).")

            for f in picked_list[:remaining_slots]:
                content_bytes = b""
                if hasattr(f, "read"):
                    content_bytes = await f.read()
                elif hasattr(f, "path") and f.path:
                    try:
                        with open(f.path, "rb") as local_f:
                            content_bytes = local_f.read()
                    except Exception:
                        content_bytes = b""

                size_kb = max(1, len(content_bytes) // 1024)
                size_str = f"{size_kb} KB" if size_kb < 1024 else f"{size_kb / 1024:.1f} MB"

                mime = "application/pdf"
                if f.name.lower().endswith((".png", ".jpg", ".jpeg")):
                    mime = "image/jpeg"
                elif f.name.lower().endswith((".txt", ".md")):
                    mime = "text/plain"

                queued_files.append({
                    "name": f.name,
                    "bytes": content_bytes,
                    "mime_type": mime,
                    "size_str": size_str,
                })

            # Auto-fill journal title from first file if title is still blank
            if queued_files and not (title_tf.value and title_tf.value.strip()):
                first_name = queued_files[0]["name"].rsplit(".", 1)[0].replace("_", " ").replace("-", " ").strip()
                if first_name:
                    title_tf.value = first_name

            _update_sources_ui()
        except Exception as pick_err:
            print(f"[create_journal_modal] file pick error: {pick_err}")
            show_page_snackbar(page, f"Could not load selected files: {pick_err}")

    # ── Add Text Note Sheet (Clean Outlined Inputs) ──
    def _open_add_note_sheet(e=None):
        total_curr = len(queued_files) + len(queued_notes)
        if total_curr >= 5:
            show_page_snackbar(page, "Course Journals are capped at a maximum of 5 sources.")
            return

        note_title_tf = ft.TextField(
            label="Module / Note Title",
            hint_text=f"e.g. Lecture {len(queued_notes) + 1} Key Takeaways",
            border_radius=ft.BorderRadius.all(10),
            filled=False,
            bgcolor=ft.Colors.TRANSPARENT,
            border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
            focused_border_color=ft.Colors.PRIMARY,
            text_size=12.5,
            content_padding=ft.Padding.symmetric(horizontal=14, vertical=12),
            autofocus=True,
        )
        note_content_tf = ft.TextField(
            label="Study Notes / Text *",
            hint_text="Paste your lecture notes, transcription, or summary...",
            border_radius=ft.BorderRadius.all(10),
            filled=False,
            bgcolor=ft.Colors.TRANSPARENT,
            border_color=ft.Colors.with_opacity(0.18, ft.Colors.ON_SURFACE),
            focused_border_color=ft.Colors.PRIMARY,
            multiline=True,
            min_lines=4,
            max_lines=8,
            text_size=12,
            content_padding=ft.Padding.symmetric(horizontal=14, vertical=12),
        )

        sheet = [None]

        def _close_sheet(ev=None):
            if sheet[0]:
                sheet[0].open = False
                try:
                    if getattr(sheet[0], "page", None) is not None:
                        sheet[0].update()
                        return
                except Exception:
                    pass
                page.update()

        def _save_note(ev=None):
            c = note_content_tf.value.strip() if note_content_tf.value else ""
            if not c:
                show_page_snackbar(page, "Note content cannot be empty.")
                return
            t = note_title_tf.value.strip() if note_title_tf.value else f"Lecture Note {len(queued_notes) + 1}"
            queued_notes.append({"title": t, "content": c})
            if not (title_tf.value and title_tf.value.strip()):
                title_tf.value = t
            _close_sheet()
            _update_sources_ui()

        sheet[0] = ft.BottomSheet(
            content=ft.Container(
                padding=ft.Padding.all(20),
                bgcolor=ft.Colors.SURFACE,
                border_radius=ft.BorderRadius.only(top_left=20, top_right=20),
                content=ft.Column(
                    spacing=14,
                    tight=True,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Row(
                                    spacing=10,
                                    tight=True,
                                    controls=[
                                        ft.Container(
                                            width=32,
                                            height=32,
                                            border_radius=ft.BorderRadius.all(9),
                                            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                                            alignment=ft.Alignment.CENTER,
                                            content=ft.Icon(ft.Icons.EDIT_NOTE_ROUNDED, color=ft.Colors.PRIMARY, size=18),
                                        ),
                                        ft.Text("Add Lecture Note Source", size=15, weight=ft.FontWeight.W_800),
                                    ],
                                ),
                                ft.IconButton(icon=ft.Icons.CLOSE_ROUNDED, icon_size=18, on_click=_close_sheet),
                            ],
                        ),
                        note_title_tf,
                        note_content_tf,
                        ft.Row(
                            alignment=ft.MainAxisAlignment.END,
                            spacing=8,
                            controls=[
                                ft.TextButton("Cancel", on_click=_close_sheet),
                                ft.Button(
                                    content=ft.Row(
                                        spacing=6,
                                        tight=True,
                                        controls=[
                                            ft.Icon(ft.Icons.ADD_ROUNDED, size=15, color=ft.Colors.ON_PRIMARY),
                                            ft.Text("Add to Journal", size=12.5, weight=ft.FontWeight.W_700, color=ft.Colors.ON_PRIMARY),
                                        ],
                                    ),
                                    bgcolor=ft.Colors.PRIMARY,
                                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), elevation=0),
                                    on_click=_save_note,
                                ),
                            ],
                        ),
                    ],
                ),
            )
        )
        if hasattr(page, "show_dialog") and getattr(page, "_dialogs", None) is not None:
            page.show_dialog(sheet[0])
        else:
            page.overlay.append(sheet[0])
            sheet[0].open = True
            page.update()

    # ── Sleek Custom Vault Search Bar (Zero muddy grey fill) ──
    clear_search_btn = ft.IconButton(
        icon=ft.Icons.CLOSE_ROUNDED,
        icon_size=14,
        icon_color=ft.Colors.ON_SURFACE_VARIANT,
        tooltip="Clear filter",
        visible=False,
        width=26,
        height=26,
        style=ft.ButtonStyle(padding=ft.Padding.all(0)),
    )

    def _on_vault_search(e=None):
        q_raw = (vault_search_tf.value or "").strip().lower()
        vault_search_query[0] = q_raw
        clear_search_btn.visible = bool(q_raw)
        _update_sources_ui()

    def _clear_vault_search(e=None):
        vault_search_tf.value = ""
        vault_search_query[0] = ""
        clear_search_btn.visible = False
        _update_sources_ui()

    clear_search_btn.on_click = _clear_vault_search

    vault_search_tf = ft.TextField(
        hint_text="Search your Study Vault materials...",
        border=ft.InputBorder.NONE,
        filled=False,
        bgcolor=ft.Colors.TRANSPARENT,
        dense=True,
        text_size=12,
        hint_style=ft.TextStyle(size=12, color=ft.Colors.with_opacity(0.45, ft.Colors.ON_SURFACE)),
        content_padding=ft.Padding.symmetric(horizontal=4, vertical=8),
        expand=True,
        on_change=_on_vault_search,
    )

    vault_search_container.content = ft.Container(
        height=38,
        padding=ft.Padding.symmetric(horizontal=11),
        border_radius=ft.BorderRadius.all(10),
        bgcolor=ft.Colors.SURFACE,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.14, ft.Colors.ON_SURFACE)),
        content=ft.Row(
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(ft.Icons.SEARCH_ROUNDED, size=16, color=ft.Colors.ON_SURFACE_VARIANT),
                vault_search_tf,
                clear_search_btn,
            ],
        ),
    )

    def _update_sources_ui():
        sources_list_col.controls.clear()
        is_upload = (active_mode[0] == "multi_upload")
        total_sources = (len(queued_files) + len(queued_notes)) if is_upload else len(chosen_vault_ids)
        sources_count_text.value = f"{total_sources} / 5 Selected" if not is_upload else f"{total_sources} / 5 Added"

        if total_sources > 5:
            sources_count_text.color = ft.Colors.RED_600
            sources_count_pill.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.RED_600)
        elif total_sources > 0:
            sources_count_text.color = ft.Colors.PRIMARY
            sources_count_pill.bgcolor = ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY)
        else:
            sources_count_text.color = ft.Colors.ON_SURFACE_VARIANT
            sources_count_pill.bgcolor = ft.Colors.with_opacity(0.07, ft.Colors.ON_SURFACE)

        action_buttons_container.visible = is_upload
        vault_search_container.visible = (not is_upload and len(vault_mats) > 0)
        _update_quota_banner()

        if is_upload:
            if total_sources == 0:
                sources_list_col.controls.append(
                    ft.Container(
                        height=158,
                        padding=ft.Padding.symmetric(horizontal=16, vertical=16),
                        border_radius=ft.BorderRadius.all(11),
                        bgcolor=ft.Colors.SURFACE,
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)),
                        alignment=ft.Alignment.CENTER,
                        ink=True,
                        on_click=lambda _: page.run_task(_handle_pick_files),
                        content=ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=5,
                            tight=True,
                            controls=[
                                ft.Container(
                                    width=38,
                                    height=38,
                                    border_radius=ft.BorderRadius.all(19),
                                    bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.PRIMARY),
                                    alignment=ft.Alignment.CENTER,
                                    content=ft.Icon(ft.Icons.CLOUD_UPLOAD_OUTLINED, size=20, color=ft.Colors.PRIMARY),
                                ),
                                ft.Text(
                                    "Drop or select up to 5 course files",
                                    size=12,
                                    weight=ft.FontWeight.W_700,
                                    color=ft.Colors.ON_SURFACE,
                                ),
                                ft.Text(
                                    "Supports PDFs, slides, images & text notes.",
                                    size=10.5,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                            ],
                        ),
                    )
                )
            else:
                for idx, f in enumerate(queued_files):
                    def _rm_f(i=idx):
                        if 0 <= i < len(queued_files):
                            queued_files.pop(i)
                        _update_sources_ui()

                    ext_lower = f["name"].lower()
                    f_icon = ft.Icons.PICTURE_AS_PDF_ROUNDED if ext_lower.endswith(".pdf") else (
                        ft.Icons.IMAGE_ROUNDED if ext_lower.endswith((".png", ".jpg", ".jpeg")) else ft.Icons.DESCRIPTION_ROUNDED
                    )

                    sources_list_col.controls.append(
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=10, vertical=7),
                            border_radius=ft.BorderRadius.all(10),
                            bgcolor=ft.Colors.SURFACE,
                            border=ft.Border.all(1, ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)),
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Row(
                                        spacing=8,
                                        tight=True,
                                        expand=True,
                                        controls=[
                                            ft.Container(
                                                width=26,
                                                height=26,
                                                border_radius=ft.BorderRadius.all(7),
                                                bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.PRIMARY),
                                                alignment=ft.Alignment.CENTER,
                                                content=ft.Icon(f_icon, size=14, color=ft.Colors.PRIMARY),
                                            ),
                                            ft.Text(
                                                f["name"],
                                                size=11.5,
                                                weight=ft.FontWeight.W_600,
                                                color=ft.Colors.ON_SURFACE,
                                                max_lines=1,
                                                overflow=ft.TextOverflow.ELLIPSIS,
                                                expand=True,
                                            ),
                                            ft.Container(
                                                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                                border_radius=ft.BorderRadius.all(6),
                                                bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
                                                content=ft.Text(f["size_str"], size=9.5, color=ft.Colors.ON_SURFACE_VARIANT),
                                            ),
                                        ],
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.CLOSE_ROUNDED,
                                        icon_size=14,
                                        icon_color=ft.Colors.ON_SURFACE_VARIANT,
                                        width=26,
                                        height=26,
                                        style=ft.ButtonStyle(padding=ft.Padding.all(0)),
                                        tooltip="Remove file",
                                        on_click=lambda _, i=idx: _rm_f(i),
                                    ),
                                ],
                            ),
                        )
                    )

                for idx, n in enumerate(queued_notes):
                    def _rm_n(i=idx):
                        if 0 <= i < len(queued_notes):
                            queued_notes.pop(i)
                        _update_sources_ui()

                    word_cnt = len((n.get("content") or "").split())
                    sources_list_col.controls.append(
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=10, vertical=7),
                            border_radius=ft.BorderRadius.all(10),
                            bgcolor=ft.Colors.SURFACE,
                            border=ft.Border.all(1, ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)),
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Row(
                                        spacing=8,
                                        tight=True,
                                        expand=True,
                                        controls=[
                                            ft.Container(
                                                width=26,
                                                height=26,
                                                border_radius=ft.BorderRadius.all(7),
                                                bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.INDIGO_600),
                                                alignment=ft.Alignment.CENTER,
                                                content=ft.Icon(ft.Icons.EDIT_NOTE_ROUNDED, size=15, color=ft.Colors.INDIGO_600),
                                            ),
                                            ft.Text(
                                                n["title"],
                                                size=11.5,
                                                weight=ft.FontWeight.W_600,
                                                color=ft.Colors.ON_SURFACE,
                                                max_lines=1,
                                                overflow=ft.TextOverflow.ELLIPSIS,
                                                expand=True,
                                            ),
                                            ft.Container(
                                                padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                                border_radius=ft.BorderRadius.all(6),
                                                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.INDIGO_600),
                                                content=ft.Text(f"{word_cnt} words", size=9.5, color=ft.Colors.INDIGO_600),
                                            ),
                                        ],
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.CLOSE_ROUNDED,
                                        icon_size=14,
                                        icon_color=ft.Colors.ON_SURFACE_VARIANT,
                                        width=26,
                                        height=26,
                                        style=ft.ButtonStyle(padding=ft.Padding.all(0)),
                                        tooltip="Remove note",
                                        on_click=lambda _, i=idx: _rm_n(i),
                                    ),
                                ],
                            ),
                        )
                    )
        else:
            # Group Existing Vault mode
            q_filter = vault_search_query[0]
            filtered_vault = [
                m for m in vault_mats
                if not q_filter or q_filter in (m.get("title") or "").lower()
            ]

            if not vault_mats:
                sources_list_col.controls.append(
                    ft.Container(
                        height=158,
                        padding=ft.Padding.all(16),
                        border_radius=ft.BorderRadius.all(11),
                        bgcolor=ft.Colors.SURFACE,
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=5,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.FOLDER_OPEN_ROUNDED, size=24, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text("Your Study Vault is empty", size=12, weight=ft.FontWeight.W_700),
                                ft.Text(
                                    "Switch to 'Upload New' above to add PDFs or lecture notes.",
                                    size=10.5,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                            ],
                        ),
                    )
                )
            elif not filtered_vault:
                sources_list_col.controls.append(
                    ft.Container(
                        height=140,
                        padding=ft.Padding.all(16),
                        border_radius=ft.BorderRadius.all(11),
                        bgcolor=ft.Colors.SURFACE,
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=6,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.SEARCH_OFF_ROUNDED, size=22, color=ft.Colors.ON_SURFACE_VARIANT),
                                ft.Text(
                                    f"No materials matching '{q_filter}'",
                                    size=11.5,
                                    weight=ft.FontWeight.W_600,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                ),
                                ft.TextButton(
                                    "Clear Filter",
                                    on_click=_clear_vault_search,
                                ),
                            ],
                        ),
                    )
                )
            else:
                for m in filtered_vault:
                    mid = str(m.get("id"))
                    is_checked = mid in chosen_vault_ids
                    stype = (m.get("source_type") or "text").lower()
                    m_icon = ft.Icons.DESCRIPTION_ROUNDED
                    type_label = "Notes"
                    if "pdf" in stype:
                        m_icon = ft.Icons.PICTURE_AS_PDF_ROUNDED
                        type_label = "PDF"
                    elif "photo" in stype or "image" in stype:
                        m_icon = ft.Icons.CAMERA_ALT_ROUNDED
                        type_label = "Image"
                    elif "youtube" in stype or "url" in stype:
                        m_icon = ft.Icons.PLAY_CIRCLE_FILL_ROUNDED
                        type_label = "Video"

                    def _toggle_mat(e=None, target_id=mid):
                        if target_id in chosen_vault_ids:
                            chosen_vault_ids.remove(target_id)
                        else:
                            if len(chosen_vault_ids) >= 5:
                                show_page_snackbar(page, "Course Journals are capped at 5 sources maximum.")
                                return
                            chosen_vault_ids.add(target_id)
                        _update_sources_ui()

                    sources_list_col.controls.append(
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                            border_radius=ft.BorderRadius.all(10),
                            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY) if is_checked else ft.Colors.SURFACE,
                            border=ft.Border.all(
                                1.2 if is_checked else 1,
                                ft.Colors.PRIMARY if is_checked else ft.Colors.with_opacity(0.09, ft.Colors.ON_SURFACE),
                            ),
                            ink=True,
                            on_click=_toggle_mat,
                            content=ft.Row(
                                spacing=9,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Icon(
                                        ft.Icons.CHECK_CIRCLE_ROUNDED if is_checked else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED,
                                        size=18,
                                        color=ft.Colors.PRIMARY if is_checked else ft.Colors.with_opacity(0.35, ft.Colors.ON_SURFACE),
                                    ),
                                    ft.Icon(
                                        m_icon,
                                        size=15,
                                        color=ft.Colors.PRIMARY if is_checked else ft.Colors.ON_SURFACE_VARIANT,
                                    ),
                                    ft.Text(
                                        m.get("title") or "Untitled Material",
                                        size=12,
                                        weight=ft.FontWeight.W_700 if is_checked else ft.FontWeight.W_500,
                                        color=ft.Colors.ON_SURFACE,
                                        max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                        expand=True,
                                    ),
                                    ft.Container(
                                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                        border_radius=ft.BorderRadius.all(6),
                                        bgcolor=ft.Colors.with_opacity(0.10 if is_checked else 0.05, ft.Colors.PRIMARY if is_checked else ft.Colors.ON_SURFACE),
                                        content=ft.Text(
                                            type_label,
                                            size=9.5,
                                            weight=ft.FontWeight.W_600,
                                            color=ft.Colors.PRIMARY if is_checked else ft.Colors.ON_SURFACE_VARIANT,
                                        ),
                                    ),
                                ],
                            ),
                        )
                    )

        if dlg_ref[0] is not None:
            safe_update_dialog(page, dlg_ref[0])

    # ── Color Selection Swatches ──
    color_row = ft.Row(
        spacing=7,
        scroll=ft.ScrollMode.AUTO,
        controls=[
            ft.Container(
                width=22,
                height=22,
                border_radius=ft.BorderRadius.all(11),
                bgcolor=c_val,
                border=ft.Border.all(2, ft.Colors.ON_SURFACE if selected_color[0] == c_key else ft.Colors.TRANSPARENT),
                ink=True,
                tooltip=c_name,
                alignment=ft.Alignment.CENTER,
                content=ft.Icon(ft.Icons.CHECK_ROUNDED, size=12, color=ft.Colors.WHITE) if selected_color[0] == c_key else None,
                on_click=(lambda k=c_key: lambda _: _set_color(k))(),
            )
            for c_key, c_name, c_val in JOURNAL_COLORS
        ],
    )

    def _set_color(k):
        selected_color[0] = k
        accent_tok = resolve_journal_color(k)
        header_icon_ctrl.color = accent_tok
        header_badge.bgcolor = ft.Colors.with_opacity(0.12, accent_tok)
        for idx, (c_key, _, _) in enumerate(JOURNAL_COLORS):
            is_sel = (k == c_key)
            color_row.controls[idx].border = ft.Border.all(
                2, ft.Colors.ON_SURFACE if is_sel else ft.Colors.TRANSPARENT
            )
            color_row.controls[idx].content = (
                ft.Icon(ft.Icons.CHECK_ROUNDED, size=12, color=ft.Colors.WHITE) if is_sel else None
            )
        safe_update_dialog(page, dlg_ref[0])

    # ── Segmented Mode Pill Switcher ──
    mode_switch_row = ft.Container(
        border_radius=ft.BorderRadius.all(10),
        bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE),
        padding=ft.Padding.all(3),
        content=ft.Row(
            spacing=4,
            controls=[],
        ),
    )

    def _render_mode_switch():
        is_upload = (active_mode[0] == "multi_upload")

        def _set_mode(m):
            if active_mode[0] == m:
                return
            if m == "multi_upload" and quota_state["mat_rem"] is not None and quota_state["mat_rem"] < 3:
                show_page_snackbar(page, f"Multi-upload requires 3 material slots (you have {quota_state['mat_rem']} left). Grouping vault modules uses 0 slots!")
                return
            active_mode[0] = m
            gen_val = bool(m == "multi_upload")
            if quota_state["gen_rem"] is not None and quota_state["gen_rem"] < 3:
                gen_val = False
            auto_gen_switch.value = gen_val
            _render_mode_switch()
            _update_sources_ui()

        mode_switch_row.content.controls = [
            ft.Container(
                expand=True,
                padding=ft.Padding.symmetric(vertical=7, horizontal=8),
                border_radius=ft.BorderRadius.all(8),
                bgcolor=ft.Colors.SURFACE if is_upload else ft.Colors.TRANSPARENT,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)) if is_upload else None,
                alignment=ft.Alignment.CENTER,
                ink=True,
                on_click=lambda _: _set_mode("multi_upload"),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=5,
                    tight=True,
                    controls=[
                        ft.Icon(
                            ft.Icons.CLOUD_UPLOAD_ROUNDED,
                            size=14,
                            color=ft.Colors.PRIMARY if is_upload else ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Text(
                            "Upload New",
                            size=11.5,
                            weight=ft.FontWeight.W_700 if is_upload else ft.FontWeight.W_500,
                            color=ft.Colors.ON_SURFACE if is_upload else ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ],
                ),
            ),
            ft.Container(
                expand=True,
                padding=ft.Padding.symmetric(vertical=7, horizontal=8),
                border_radius=ft.BorderRadius.all(8),
                bgcolor=ft.Colors.SURFACE if not is_upload else ft.Colors.TRANSPARENT,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)) if not is_upload else None,
                alignment=ft.Alignment.CENTER,
                ink=True,
                on_click=lambda _: _set_mode("existing"),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=5,
                    tight=True,
                    controls=[
                        ft.Icon(
                            ft.Icons.FOLDER_SPECIAL_ROUNDED,
                            size=14,
                            color=ft.Colors.PRIMARY if not is_upload else ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        ft.Text(
                            f"Study Vault ({len(vault_mats)})",
                            size=11.5,
                            weight=ft.FontWeight.W_700 if not is_upload else ft.FontWeight.W_500,
                            color=ft.Colors.ON_SURFACE if not is_upload else ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ],
                ),
            ),
        ]

    _render_mode_switch()

    # ── Upload Action Buttons (Sleek Equal-Width Cards/Pills) ──
    def _build_upload_action_btn(icon_name, label_text, on_tap):
        return ft.Container(
            expand=not is_mobile,
            height=36,
            padding=ft.Padding.symmetric(horizontal=12),
            border_radius=ft.BorderRadius.all(9),
            bgcolor=ft.Colors.SURFACE,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.14, ft.Colors.ON_SURFACE)),
            alignment=ft.Alignment.CENTER,
            ink=True,
            on_click=on_tap,
            content=ft.Row(
                spacing=6,
                tight=True,
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    ft.Icon(icon_name, size=15, color=ft.Colors.PRIMARY),
                    ft.Text(label_text, size=11.5, weight=ft.FontWeight.W_700, color=ft.Colors.ON_SURFACE),
                ],
            ),
        )

    upload_files_btn = _build_upload_action_btn(
        ft.Icons.UPLOAD_FILE_ROUNDED,
        "Add Files (PDF, Image, TXT)",
        lambda _: page.run_task(_handle_pick_files),
    )
    paste_note_btn = _build_upload_action_btn(
        ft.Icons.EDIT_NOTE_ROUNDED,
        "Paste Lecture Note",
        _open_add_note_sheet,
    )

    action_buttons_container.content = (
        ft.Column(
            spacing=6,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[upload_files_btn, paste_note_btn],
        )
        if is_mobile
        else ft.Row(
            spacing=8,
            controls=[upload_files_btn, paste_note_btn],
        )
    )

    # ── Unified Sources Card Container ──
    sources_section_card = ft.Container(
        padding=ft.Padding.all(12),
        border_radius=ft.BorderRadius.all(14),
        bgcolor=ft.Colors.with_opacity(0.025, ft.Colors.ON_SURFACE),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)),
        content=ft.Column(
            spacing=10,
            tight=True,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Row(
                            spacing=6,
                            tight=True,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Icon(ft.Icons.LAYERS_ROUNDED, size=15, color=ft.Colors.PRIMARY),
                                ft.Text(
                                    "Constituent Modules",
                                    size=12,
                                    weight=ft.FontWeight.W_800,
                                    color=ft.Colors.ON_SURFACE,
                                ),
                            ],
                        ),
                        sources_count_pill,
                    ],
                ),
                mode_switch_row,
                action_buttons_container,
                vault_search_container,
                sources_list_container,
            ],
        ),
    )

    def _default_submit_content():
        return ft.Row(
            spacing=6,
            tight=True,
            controls=[
                ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=15, color=ft.Colors.ON_PRIMARY),
                ft.Text("Create Journal", size=13, weight=ft.FontWeight.W_800, color=ft.Colors.ON_PRIMARY),
            ],
        )

    submit_btn = ft.Button(
        content=_default_submit_content(),
        bgcolor=ft.Colors.PRIMARY,
        height=40,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=10),
            padding=ft.Padding.symmetric(horizontal=18),
            elevation=0,
        ),
    )

    async def _handle_submit(e=None):
        t = title_tf.value.strip() if title_tf.value else ""
        if not t:
            show_page_snackbar(page, "Please enter a title for the Course Journal.")
            return

        total_sources = (len(queued_files) + len(queued_notes)) if active_mode[0] == "multi_upload" else len(chosen_vault_ids)
        if total_sources == 0:
            show_page_snackbar(page, "Please add or select at least 1 source material for your Journal.")
            return
        if total_sources > 5:
            show_page_snackbar(page, "Course Journals are capped at 5 sources maximum.")
            return

        # Quota edge-case conformance: check slots before initiating multi-upload
        if active_mode[0] == "multi_upload" and quota_state["mat_rem"] is not None and quota_state["mat_rem"] < 3:
            show_page_snackbar(page, f"Multi-upload requires 3 material slots (you have {quota_state['mat_rem']} left). Please link existing vault materials or upgrade in Store.")
            return

        desc = desc_tf.value.strip() if desc_tf.value else ""
        col = selected_color[0]
        gen = bool(auto_gen_switch.value)

        # Quota edge-case conformance: check credits before generating
        if gen and quota_state["gen_rem"] is not None and quota_state["gen_rem"] < 3:
            gen = False
            show_page_snackbar(page, f"Creating journal without AI synthesis (you have {quota_state['gen_rem']} of 3 required credits).")

        submit_btn.disabled = True
        submit_btn.content = ft.Row(
            spacing=8,
            tight=True,
            controls=[
                ft.ProgressRing(width=15, height=15, stroke_width=2, color=ft.Colors.ON_PRIMARY),
                ft.Text("Creating...", size=12.5, weight=ft.FontWeight.W_700, color=ft.Colors.ON_PRIMARY),
            ],
        )
        safe_update_dialog(page, dlg_ref[0])

        try:
            if active_mode[0] == "multi_upload":
                pasted_texts = [n["content"] for n in queued_notes]
                pasted_titles = [n["title"] for n in queued_notes]
                res = await create_multi_journal_api(
                    token=token,
                    title=t,
                    description=desc,
                    color=col,
                    icon="book",
                    pasted_texts=pasted_texts,
                    pasted_titles=pasted_titles,
                    files_payload=queued_files,
                    auto_generate=gen,
                )
            else:
                res = await create_journal_api(
                    token=token,
                    title=t,
                    description=desc,
                    color=col,
                    icon="book",
                    material_ids=list(chosen_vault_ids),
                )
                if res.get("id") and gen:
                    gen_res = await generate_journal_content_api(token, str(res["id"]))
                    if gen_res.get("status") == "processing":
                        res["is_generating"] = True

            if res.get("id"):
                show_page_snackbar(page, f"Created Course Journal '{t}'! 📚")
                _close_dlg()
                if on_journal_created:
                    cb_res = on_journal_created(res)
                    if asyncio.iscoroutine(cb_res):
                        await cb_res
            else:
                err_msg = res.get("error") or "Failed to create journal."
                if res.get("code") == 402 or "credit" in err_msg.lower() or "expired" in err_msg.lower() or "quota" in err_msg.lower():
                    def _go_store(ev=None):
                        run_after_modal_close(page, store_dlg, lambda: page.navigate("/store"))

                    store_dlg = ft.AlertDialog(
                        shape=ft.RoundedRectangleBorder(radius=16),
                        bgcolor=ft.Colors.SURFACE,
                        title=ft.Row([
                            ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=ft.Colors.AMBER_400),
                            ft.Text("AI Generation Credits", weight=ft.FontWeight.BOLD, size=16),
                        ], spacing=8),
                        content=ft.Text(
                            err_msg if not err_msg.startswith("{") else "Generating a unified Course Journal requires 3 AI credits. Please recharge your credits in the Store to proceed.",
                            size=13,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        actions=[
                            ft.TextButton("Maybe Later", on_click=lambda _: safe_close_dialog(page, store_dlg)),
                            ft.Button(
                                "Go to Store",
                                icon=ft.Icons.SHOPPING_BAG_ROUNDED,
                                style=ft.ButtonStyle(bgcolor=ft.Colors.PRIMARY, color=ft.Colors.ON_PRIMARY),
                                on_click=_go_store,
                            ),
                        ],
                        actions_alignment=ft.MainAxisAlignment.END,
                    )
                    safe_open_dialog(page, store_dlg, tag="journal_store_credits")
                else:
                    show_page_snackbar(page, err_msg)
                submit_btn.disabled = False
                submit_btn.content = _default_submit_content()
                safe_update_dialog(page, dlg_ref[0])
        except Exception as err:
            show_page_snackbar(page, f"Error: {err}")
            submit_btn.disabled = False
            submit_btn.content = _default_submit_content()
            safe_update_dialog(page, dlg_ref[0])

    submit_btn.on_click = lambda _: page.run_task(_handle_submit)

    _update_sources_ui()

    cur_w = getattr(page, "width", None) or 400
    cur_h = getattr(page, "height", None) or 800
    is_mob = bool(cur_w < 580)

    content_box = ft.Container(
        width=min(480, int(cur_w * 0.92)),
        height=min(int(cur_h * 0.70), 550),
        content=ft.Column(
            spacing=12,
            tight=True,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                title_tf,
                desc_tf,
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text(
                            "Notebook Accent",
                            size=11.5,
                            weight=ft.FontWeight.W_700,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        color_row,
                    ],
                ),
                sources_section_card,
                ai_synthesis_card,
            ],
        ),
    )

    dlg_ref[0] = ft.AlertDialog(
        modal=True,
        shape=ft.RoundedRectangleBorder(radius=20),
        bgcolor=ft.Colors.SURFACE,
        title_padding=ft.Padding.only(left=16, right=10, top=16, bottom=6),
        content_padding=ft.Padding.symmetric(horizontal=14 if is_mob else 18, vertical=6),
        actions_padding=ft.Padding.only(left=16, right=16, top=6, bottom=14),
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
                        header_badge,
                        ft.Column(
                            spacing=1,
                            tight=True,
                            expand=True,
                            controls=[
                                ft.Text("New Course Journal", size=15 if is_mob else 16, weight=ft.FontWeight.W_800, color=ft.Colors.ON_SURFACE),
                                ft.Text(
                                    "Bundle up to 5 modules into one notebook",
                                    size=10.5 if is_mob else 11,
                                    color=ft.Colors.ON_SURFACE_VARIANT,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                            ],
                        ),
                    ],
                ),
                ft.IconButton(
                    icon=ft.Icons.CLOSE_ROUNDED,
                    icon_size=18,
                    icon_color=ft.Colors.ON_SURFACE_VARIANT,
                    on_click=_close_dlg,
                ),
            ],
        ),
        content=content_box,
        actions=[
            ft.TextButton(
                "Cancel",
                style=ft.ButtonStyle(color=ft.Colors.ON_SURFACE_VARIANT),
                on_click=_close_dlg,
            ),
            submit_btn,
        ],
    )

    async def _async_load_quota():
        if user_quota:
            return
        try:
            from src.requests.subscription import get_subscription_status
            from src.requests.study import get_ai_tutor_quota_api
            sub = await get_subscription_status(token)
            if sub and not sub.get("error"):
                m_lim = sub.get("materials_limit")
                m_used = sub.get("materials_count", 0)
                quota_state["mat_rem"] = None if m_lim is None else max(0, m_lim - m_used)
            g_quota = await get_ai_tutor_quota_api(token)
            if g_quota and not g_quota.get("is_unlimited", False):
                g_rem = g_quota.get("remaining")
                quota_state["gen_rem"] = g_rem
                if g_rem is not None and g_rem < 3:
                    auto_gen_switch.value = False
                    _update_quota_banner()
                    if dlg_ref[0]:
                        safe_update_dialog(page, dlg_ref[0])

            if quota_state["mat_rem"] is not None and quota_state["mat_rem"] < 3:
                if active_mode[0] == "multi_upload":
                    active_mode[0] = "existing"
                    _render_mode_switch()
                    _update_sources_ui()
                    if dlg_ref[0]:
                        safe_update_dialog(page, dlg_ref[0])
        except Exception:
            pass

    page.run_task(_async_load_quota)

    safe_open_dialog(page, dlg_ref[0], tag="create_journal_modal")
