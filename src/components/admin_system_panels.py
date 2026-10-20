"""
src/components/admin_system_panels.py
──────────────────────────────────────────────────────────────────────────────
Self-contained Super Admin panels mounted by platform_admin_view:
  • CategoriesPanel   – full CRUD for course categories
  • SystemToolsPanel  – re-engagement engine preview/run + OneSignal diagnostics
Each panel exposes `.control` (cached, built once) and `async load()`.
──────────────────────────────────────────────────────────────────────────────
"""

from typing import Any, Dict, List, Optional
import json
import flet as ft

from src.requests.platform_admin import (
    get_categories_admin,
    create_category_admin,
    update_category_admin,
    delete_category_admin,
    get_engine_preview_admin,
    run_engine_evaluations_admin,
    get_onesignal_diagnostics_admin,
)
from src.utils.file_opener import show_page_snackbar


def _btn_content(label: str, spinner: ft.ProgressRing, color) -> ft.Row:
    return ft.Row([spinner, ft.Text(label, size=12, weight=ft.FontWeight.BOLD, color=color)], tight=True, spacing=6)


def _card(palette: dict, content: ft.Control, padding: int = 16) -> ft.Container:
    return ft.Container(
        bgcolor=palette["card_bg"],
        border=ft.Border.all(1, palette["border"]),
        border_radius=14,
        padding=padding,
        content=content,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CATEGORIES
# ─────────────────────────────────────────────────────────────────────────────
class CategoriesPanel:
    def __init__(self, page: ft.Page, palette: dict, get_token):
        self.page = page
        self.p = palette
        self.get_token = get_token
        self.categories: List[Dict[str, Any]] = []
        self.query = ""
        self.is_loading = False
        self.error: Optional[str] = None
        self.body = ft.Column(spacing=10)
        self.search = ft.TextField(
            hint_text="Search categories…",
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            border_radius=10,
            height=40,
            text_size=12,
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=0),
            bgcolor=palette["surface"],
            on_change=self._on_search,
            expand=True,
        )
        self.count_text = ft.Text("", size=11, color=palette["text_muted"])
        self.control = ft.Column(
            spacing=14,
            controls=[
                _card(
                    palette,
                    ft.Column(
                        spacing=12,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                wrap=True,
                                spacing=12,
                                controls=[
                                    ft.Column(
                                        spacing=2,
                                        tight=True,
                                        controls=[
                                            ft.Row([
                                                ft.Icon(ft.Icons.CATEGORY_ROUNDED, color=palette["accent"], size=20),
                                                ft.Text("Course Categories", size=16, weight=ft.FontWeight.BOLD, color=palette["text"]),
                                            ], tight=True, spacing=8),
                                            ft.Text("Create, rename and remove the categories instructors file courses under.", size=11, color=palette["text_muted"]),
                                        ],
                                    ),
                                    ft.FilledButton(
                                        "New Category",
                                        icon=ft.Icons.ADD_ROUNDED,
                                        style=ft.ButtonStyle(bgcolor=palette["accent"], color=ft.Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=10)),
                                        on_click=lambda e: self._open_editor(None),
                                    ),
                                ],
                            ),
                            ft.Row([self.search], spacing=8),
                            self.count_text,
                        ],
                    ),
                ),
                self.body,
            ],
        )

    # ── data ────────────────────────────────────────────────────────────────
    async def load(self):
        self.is_loading = True
        self.error = None
        self._render()
        status, data = await get_categories_admin(self.get_token())
        if status == 200 and isinstance(data, list):
            self.categories = sorted(data, key=lambda c: str(c.get("name", "")).lower())
        else:
            self.error = (data.get("detail") if isinstance(data, dict) else None) or "Could not load categories."
        self.is_loading = False
        self._render()

    def _on_search(self, e=None):
        self.query = (self.search.value or "").strip().lower()
        self._render()

    # ── rendering ───────────────────────────────────────────────────────────
    def _render(self):
        p = self.p
        rows: List[ft.Control] = []
        shown = [
            c for c in self.categories
            if not self.query or self.query in str(c.get("name", "")).lower() or self.query in str(c.get("description", "")).lower()
        ]
        self.count_text.value = f"{len(shown)} of {len(self.categories)} categories" if self.categories else ""

        if self.is_loading and not self.categories:
            rows.append(_card(p, ft.Row([ft.ProgressRing(width=18, height=18, stroke_width=2, color=p["accent"]), ft.Text("Loading categories…", size=12, color=p["text_muted"])], spacing=10)))
        elif self.error:
            rows.append(_card(p, ft.Row([
                ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, color=p["danger"]),
                ft.Text(self.error, size=12, color=p["danger"], expand=True),
                ft.TextButton("Retry", on_click=lambda e: self.page.run_task(self.load)),
            ], spacing=10)))
        elif not shown:
            if self.query:
                title, sub = "No matching categories", f"Nothing matches “{self.search.value}”. Try a different term."
            else:
                title, sub = "No categories yet", "Tap “New Category” to create the first one."
            rows.append(_card(p, ft.Column([
                ft.Icon(ft.Icons.CATEGORY_OUTLINED, size=34, color=p["text_muted"]),
                ft.Text(title, size=14, weight=ft.FontWeight.BOLD, color=p["text"]),
                ft.Text(sub, size=11, color=p["text_muted"]),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6), padding=28))
        else:
            for c in shown:
                rows.append(self._row(c))

        self.body.controls = rows
        try:
            self.body.update()
            self.count_text.update()
        except Exception:
            pass

    def _row(self, c: Dict[str, Any]) -> ft.Control:
        p = self.p
        name = str(c.get("name", "Untitled"))
        return _card(
            p,
            ft.Row(
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
                controls=[
                    ft.Container(
                        width=38, height=38, border_radius=10,
                        bgcolor=ft.Colors.with_opacity(0.15, p["accent"]),
                        alignment=ft.Alignment.CENTER,
                        content=ft.Text(name[:1].upper(), size=16, weight=ft.FontWeight.W_800, color=p["accent"]),
                    ),
                    ft.Column(
                        expand=True, spacing=2, tight=True,
                        controls=[
                            ft.Text(name, size=13.5, weight=ft.FontWeight.BOLD, color=p["text"], max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(str(c.get("description", "")), size=11, color=p["text_muted"], max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                        ],
                    ),
                    ft.IconButton(ft.Icons.EDIT_ROUNDED, icon_size=18, tooltip="Edit", icon_color=p["info"], on_click=lambda e, cat=c: self._open_editor(cat)),
                    ft.IconButton(ft.Icons.DELETE_OUTLINE_ROUNDED, icon_size=18, tooltip="Delete", icon_color=p["danger"], on_click=lambda e, cat=c: self._confirm_delete(cat)),
                ],
            ),
            padding=12,
        )

    # ── dialogs ─────────────────────────────────────────────────────────────
    def _open_editor(self, existing: Optional[Dict[str, Any]]):
        p = self.p
        is_edit = existing is not None
        name_f = ft.TextField(label="Category name", value=(existing or {}).get("name", ""), border_radius=8, text_size=13, autofocus=True)
        desc_f = ft.TextField(label="Description", value=(existing or {}).get("description", ""), multiline=True, min_lines=2, max_lines=4, border_radius=8, text_size=13)
        err = ft.Text("", size=11, color=p["danger"], visible=False)
        spinner = ft.ProgressRing(width=14, height=14, stroke_width=2, color=ft.Colors.WHITE, visible=False)
        save_btn = ft.FilledButton(
            content=_btn_content("Save Changes" if is_edit else "Create Category", spinner, ft.Colors.WHITE),
            style=ft.ButtonStyle(bgcolor=p["accent"], shape=ft.RoundedRectangleBorder(radius=8)),
        )
        dlg = ft.AlertDialog(modal=True, shape=ft.RoundedRectangleBorder(radius=16), bgcolor=p["card_bg"])

        async def _save(ev=None):
            nm = (name_f.value or "").strip()
            ds = (desc_f.value or "").strip()
            if not nm or not ds:
                err.value = "Both a name and a description are required."
                err.visible = True
                dlg.update()
                return
            spinner.visible = True
            save_btn.disabled = True
            err.visible = False
            dlg.update()
            if is_edit:
                status, data = await update_category_admin(self.get_token(), str(existing["id"]), name=nm, description=ds)
            else:
                status, data = await create_category_admin(self.get_token(), nm, ds)
            if status in (200, 201):
                dlg.open = False
                self.page.update()
                show_page_snackbar(self.page, "Category updated." if is_edit else "Category created.")
                await self.load()
            else:
                spinner.visible = False
                save_btn.disabled = False
                err.value = (data.get("detail") if isinstance(data, dict) else None) or "Request failed."
                err.visible = True
                dlg.update()

        save_btn.on_click = lambda ev: self.page.run_task(_save, ev)
        dlg.title = ft.Row([
            ft.Icon(ft.Icons.CATEGORY_ROUNDED, color=p["accent"], size=20),
            ft.Text("Edit Category" if is_edit else "New Category", size=15, weight=ft.FontWeight.BOLD, color=p["text"]),
        ], tight=True, spacing=8)
        dlg.content = ft.Container(width=420, content=ft.Column([name_f, desc_f, err], tight=True, spacing=12))
        dlg.actions = [ft.TextButton("Cancel", on_click=lambda _: (setattr(dlg, "open", False), self.page.update())), save_btn]
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def _confirm_delete(self, cat: Dict[str, Any]):
        p = self.p
        spinner = ft.ProgressRing(width=14, height=14, stroke_width=2, color=ft.Colors.WHITE, visible=False)
        err = ft.Text("", size=11, color=p["danger"], visible=False)
        del_btn = ft.FilledButton(
            content=_btn_content("Delete", spinner, ft.Colors.WHITE),
            style=ft.ButtonStyle(bgcolor=p["danger"], shape=ft.RoundedRectangleBorder(radius=8)),
        )
        dlg = ft.AlertDialog(modal=True, shape=ft.RoundedRectangleBorder(radius=16), bgcolor=p["card_bg"])

        async def _do(ev=None):
            spinner.visible = True
            del_btn.disabled = True
            err.visible = False
            dlg.update()
            status, data = await delete_category_admin(self.get_token(), str(cat["id"]))
            if status in (200, 204):
                dlg.open = False
                self.page.update()
                show_page_snackbar(self.page, f"Deleted “{cat.get('name')}”.")
                await self.load()
            else:
                spinner.visible = False
                del_btn.disabled = False
                err.value = (data.get("detail") if isinstance(data, dict) else None) or "Could not delete. It may still be used by courses."
                err.visible = True
                dlg.update()

        del_btn.on_click = lambda ev: self.page.run_task(_do, ev)
        dlg.title = ft.Text("Delete category?", size=15, weight=ft.FontWeight.BOLD, color=p["text"])
        dlg.content = ft.Container(width=380, content=ft.Column([
            ft.Text(f"“{cat.get('name')}” will be permanently removed. Courses using it may be affected.", size=12, color=p["text_muted"]),
            err,
        ], tight=True, spacing=8))
        dlg.actions = [ft.TextButton("Cancel", on_click=lambda _: (setattr(dlg, "open", False), self.page.update())), del_btn]
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()


# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM TOOLS (engine + diagnostics)
# ─────────────────────────────────────────────────────────────────────────────
_TIER_OPTIONS = [
    ("", "Auto (best fit)"),
    ("1", "Tier 1 · Streak saver"),
    ("2", "Tier 2 · Duo partner"),
    ("3", "Tier 3 · Daytime nudge"),
    ("4", "Tier 4 · Inactivity"),
    ("5", "Tier 5 · Course progress"),
]


class SystemToolsPanel:
    def __init__(self, page: ft.Page, palette: dict, get_token):
        self.page = page
        self.p = palette
        self.get_token = get_token

        self.tier = ft.Dropdown(
            label="Tier", value="", border_radius=8, text_size=12, bgcolor=palette["surface"], expand=True,
            options=[ft.dropdown.Option(key=k, text=t) for k, t in _TIER_OPTIONS],
        )
        self.category = ft.TextField(label="Category (optional)", hint_text="e.g. course_progress", border_radius=8, text_size=12, expand=True)
        self.target_user = ft.TextField(label="Target user ID (optional)", hint_text="Leave blank for system-wide", border_radius=8, text_size=12)
        self.dry_run = ft.Switch(label="Dry run (no pushes sent)", value=True, active_color=palette["accent"])
        self.force = ft.Switch(label="Force (bypass quiet hours)", value=False, active_color=palette["accent"])

        self.preview_spin = ft.ProgressRing(width=14, height=14, stroke_width=2, color=ft.Colors.WHITE, visible=False)
        self.run_spin = ft.ProgressRing(width=14, height=14, stroke_width=2, color=ft.Colors.WHITE, visible=False)
        self.diag_spin = ft.ProgressRing(width=14, height=14, stroke_width=2, color=ft.Colors.WHITE, visible=False)

        self.preview_btn = ft.FilledButton(
            content=_btn_content("Preview my nudge", self.preview_spin, ft.Colors.WHITE),
            style=ft.ButtonStyle(bgcolor=palette["info"], shape=ft.RoundedRectangleBorder(radius=10)),
            on_click=lambda e: self.page.run_task(self._do_preview),
        )
        self.run_btn = ft.FilledButton(
            content=_btn_content("Run evaluation", self.run_spin, ft.Colors.WHITE),
            style=ft.ButtonStyle(bgcolor=palette["accent"], shape=ft.RoundedRectangleBorder(radius=10)),
            on_click=lambda e: self.page.run_task(self._do_run),
        )
        self.diag_btn = ft.FilledButton(
            content=_btn_content("Run diagnostics", self.diag_spin, ft.Colors.WHITE),
            style=ft.ButtonStyle(bgcolor=palette["purple"], shape=ft.RoundedRectangleBorder(radius=10)),
            on_click=lambda e: self.page.run_task(self._do_diag),
        )

        self.engine_result = ft.Container(visible=False)
        self.diag_result = ft.Container(visible=False)

        self.control = ft.Column(
            spacing=14,
            controls=[
                self._section(
                    "Re-engagement Engine", ft.Icons.NOTIFICATIONS_ACTIVE_ROUNDED, palette["accent"],
                    "Preview the nudge you would receive right now, or run the evaluator for everyone. Dry run is on by default.",
                    ft.Column(spacing=12, controls=[
                        ft.Row([self.tier, self.category], spacing=10),
                        self.target_user,
                        ft.Row([self.dry_run, self.force], wrap=True, spacing=16),
                        ft.Row([self.preview_btn, self.run_btn], wrap=True, spacing=10),
                        self.engine_result,
                    ]),
                ),
                self._section(
                    "Push Diagnostics (OneSignal)", ft.Icons.MONITOR_HEART_ROUNDED, palette["purple"],
                    "Queries OneSignal live for app status, subscriber counts, segments and the latest sent notifications.",
                    ft.Column(spacing=12, controls=[ft.Row([self.diag_btn]), self.diag_result]),
                ),
            ],
        )

    async def load(self):
        return

    def _section(self, title, icon, color, subtitle, body) -> ft.Control:
        p = self.p
        return _card(p, ft.Column(spacing=14, controls=[
            ft.Row([
                ft.Container(width=36, height=36, border_radius=10, bgcolor=ft.Colors.with_opacity(0.15, color), alignment=ft.Alignment.CENTER, content=ft.Icon(icon, color=color, size=20)),
                ft.Column(spacing=2, tight=True, expand=True, controls=[
                    ft.Text(title, size=15, weight=ft.FontWeight.BOLD, color=p["text"]),
                    ft.Text(subtitle, size=11, color=p["text_muted"]),
                ]),
            ], spacing=12),
            body,
        ]), padding=18)

    def _set_busy(self, btn, spinner, busy: bool):
        spinner.visible = busy
        btn.disabled = busy
        try:
            btn.update()
        except Exception:
            pass

    def _tier_val(self) -> Optional[int]:
        v = (self.tier.value or "").strip()
        return int(v) if v.isdigit() else None

    def _kv(self, k: str, v: Any, color=None) -> ft.Control:
        p = self.p
        return ft.Row([
            ft.Text(k, size=11, color=p["text_muted"], width=150),
            ft.Text(str(v), size=12, weight=ft.FontWeight.W_600, color=color or p["text"], selectable=True, expand=True),
        ], vertical_alignment=ft.CrossAxisAlignment.START)

    def _error_box(self, msg: str) -> ft.Control:
        p = self.p
        return ft.Container(
            bgcolor=p["danger_bg"], border_radius=10, padding=12,
            content=ft.Row([ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, color=p["danger"], size=18), ft.Text(msg, size=12, color=p["danger"], expand=True, selectable=True)], spacing=8),
        )

    def _show(self, holder: ft.Container, control: ft.Control):
        holder.content = control
        holder.visible = True
        try:
            holder.update()
        except Exception:
            pass

    # ── engine ──────────────────────────────────────────────────────────────
    async def _do_preview(self):
        self._set_busy(self.preview_btn, self.preview_spin, True)
        status, data = await get_engine_preview_admin(self.get_token(), self._tier_val(), (self.category.value or "").strip() or None)
        self._set_busy(self.preview_btn, self.preview_spin, False)
        p = self.p
        if status != 200 or not isinstance(data, dict):
            self._show(self.engine_result, self._error_box((data.get("detail") if isinstance(data, dict) else None) or "Preview failed."))
            return
        ctx = data.get("context") or {}
        nudge = data.get("nudge")
        rows: List[ft.Control] = [
            ft.Row([ft.Icon(ft.Icons.PREVIEW_ROUNDED, color=p["info"], size=18), ft.Text("Nudge preview", size=13, weight=ft.FontWeight.BOLD, color=p["text"])], spacing=6),
            self._kv("Streak", ctx.get("streak", 0)),
            self._kv("Last login", ctx.get("last_login_date") or "—"),
        ]
        if data.get("has_nudge") and isinstance(nudge, dict):
            title = nudge.get("title") or nudge.get("heading") or "(no title)"
            body = nudge.get("body") or nudge.get("message") or nudge.get("content") or ""
            rows.append(ft.Container(
                bgcolor=ft.Colors.with_opacity(0.10, p["accent"]), border_radius=12, padding=14,
                border=ft.Border.all(1, ft.Colors.with_opacity(0.35, p["accent"])),
                content=ft.Column(spacing=4, tight=True, controls=[
                    ft.Text(str(title), size=13.5, weight=ft.FontWeight.W_800, color=p["text"]),
                    ft.Text(str(body), size=12, color=p["text"]),
                ]),
            ))
            extras = {k: v for k, v in nudge.items() if k not in ("title", "heading", "body", "message", "content") and v not in (None, "")}
            for k, v in list(extras.items())[:6]:
                rows.append(self._kv(k, v))
        else:
            rows.append(ft.Text("No nudge would be sent right now for the selected filters.", size=12, color=p["text_muted"]))
        self._show(self.engine_result, ft.Container(bgcolor=p["surface"], border_radius=12, padding=14, content=ft.Column(rows, spacing=8)))

    async def _do_run(self):
        dry = bool(self.dry_run.value)
        if not dry:
            await self._confirm_live_run()
            return
        await self._run_engine(True)

    async def _confirm_live_run(self):
        p = self.p
        dlg = ft.AlertDialog(modal=True, shape=ft.RoundedRectangleBorder(radius=16), bgcolor=p["card_bg"])

        async def _go(ev=None):
            dlg.open = False
            self.page.update()
            await self._run_engine(False)

        dlg.title = ft.Row([ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=p["warning"]), ft.Text("Send real notifications?", size=15, weight=ft.FontWeight.BOLD, color=p["text"])], tight=True, spacing=8)
        scope = (self.target_user.value or "").strip() or "ALL eligible users"
        dlg.content = ft.Container(width=380, content=ft.Text(f"Dry run is OFF. This will write notifications and push to: {scope}.", size=12, color=p["text_muted"]))
        dlg.actions = [
            ft.TextButton("Cancel", on_click=lambda _: (setattr(dlg, "open", False), self.page.update())),
            ft.FilledButton("Send now", style=ft.ButtonStyle(bgcolor=p["danger"], shape=ft.RoundedRectangleBorder(radius=8)), on_click=lambda ev: self.page.run_task(_go, ev)),
        ]
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    async def _run_engine(self, dry: bool):
        self._set_busy(self.run_btn, self.run_spin, True)
        status, data = await run_engine_evaluations_admin(
            self.get_token(),
            dry_run=dry,
            force=bool(self.force.value),
            user_id=(self.target_user.value or "").strip() or None,
            preferred_tier=self._tier_val(),
            category=(self.category.value or "").strip() or None,
        )
        self._set_busy(self.run_btn, self.run_spin, False)
        p = self.p
        if status != 200 or not isinstance(data, dict):
            self._show(self.engine_result, self._error_box((data.get("detail") if isinstance(data, dict) else None) or "Evaluation failed."))
            return
        stats = data.get("stats") or {}
        records = stats.get("dispatched_records") or []
        rows: List[ft.Control] = [
            ft.Row([
                ft.Icon(ft.Icons.PLAY_CIRCLE_ROUNDED, color=p["success"], size=18),
                ft.Text("Evaluation complete" + (" (dry run)" if data.get("dry_run") else " (LIVE)"), size=13, weight=ft.FontWeight.BOLD, color=p["text"]),
            ], spacing=6),
        ]
        for k, v in stats.items():
            if k == "dispatched_records":
                continue
            rows.append(self._kv(k, v if not isinstance(v, (dict, list)) else json.dumps(v)[:200]))
        if records:
            rows.append(ft.Text(f"Dispatched records ({len(records)})", size=12, weight=ft.FontWeight.BOLD, color=p["text"]))
            for r in records[:8]:
                title = r.get("title", "") if isinstance(r, dict) else str(r)
                body = r.get("body", "") if isinstance(r, dict) else ""
                rows.append(ft.Container(
                    bgcolor=p["card_bg"], border_radius=8, padding=10,
                    content=ft.Column(spacing=2, tight=True, controls=[
                        ft.Text(str(title), size=12, weight=ft.FontWeight.W_700, color=p["text"]),
                        ft.Text(str(body), size=11, color=p["text_muted"]),
                    ]),
                ))
            if len(records) > 8:
                rows.append(ft.Text(f"…and {len(records) - 8} more", size=11, color=p["text_muted"]))
        self._show(self.engine_result, ft.Container(bgcolor=p["surface"], border_radius=12, padding=14, content=ft.Column(rows, spacing=8)))

    # ── diagnostics ─────────────────────────────────────────────────────────
    async def _do_diag(self):
        self._set_busy(self.diag_btn, self.diag_spin, True)
        status, data = await get_onesignal_diagnostics_admin(self.get_token())
        self._set_busy(self.diag_btn, self.diag_spin, False)
        p = self.p
        if status != 200 or not isinstance(data, dict):
            self._show(self.diag_result, self._error_box((data.get("detail") if isinstance(data, dict) else None) or "Diagnostics failed."))
            return
        if data.get("error"):
            self._show(self.diag_result, self._error_box(
                f"{data['error']} · app id configured: {data.get('app_id_configured')} · API key configured: {data.get('api_key_configured')}"
            ))
            return

        rows: List[ft.Control] = [
            self._kv("App ID", data.get("app_id", "—")),
            self._kv("REST key", data.get("key", "—")),
        ]
        app = data.get("app_info")
        if isinstance(app, dict) and "name" in app:
            rows.append(self._kv("App name", app.get("name"), p["success"]))
            for label, key in (("Subscribed users", "players"), ("Messageable users", "messageable_players")):
                if key in app:
                    rows.append(self._kv(label, f"{app[key]:,}" if isinstance(app[key], int) else app[key]))
        else:
            rows.append(self._kv("App info", json.dumps(app)[:200] if app else "—", p["danger"]))

        segs = data.get("segments")
        seg_list = segs.get("segments") if isinstance(segs, dict) else (segs if isinstance(segs, list) else None)
        rows.append(ft.Text("Segments", size=12, weight=ft.FontWeight.BOLD, color=p["text"]))
        if seg_list:
            rows.append(ft.Row(wrap=True, spacing=6, run_spacing=6, controls=[
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=4), border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.14, p["purple"]),
                    content=ft.Text(str(s.get("name", s)) if isinstance(s, dict) else str(s), size=11, color=p["text"]),
                ) for s in seg_list
            ]))
        else:
            rows.append(ft.Text("No segments returned.", size=11, color=p["text_muted"]))

        notifs = data.get("recent_notifications")
        n_list = notifs.get("notifications") if isinstance(notifs, dict) else None
        rows.append(ft.Text("Recent notifications", size=12, weight=ft.FontWeight.BOLD, color=p["text"]))
        if n_list:
            for n in n_list[:5]:
                head = (n.get("headings") or {}).get("en") or "(no heading)"
                content = (n.get("contents") or {}).get("en") or ""
                rows.append(ft.Container(
                    bgcolor=p["card_bg"], border_radius=8, padding=10,
                    content=ft.Column(spacing=2, tight=True, controls=[
                        ft.Text(str(head), size=12, weight=ft.FontWeight.W_700, color=p["text"]),
                        ft.Text(str(content), size=11, color=p["text_muted"], max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                        ft.Text(f"successful: {n.get('successful', 0)} · failed: {n.get('failed', 0)} · remaining: {n.get('remaining', 0)}", size=10, color=p["text_muted"]),
                    ]),
                ))
        else:
            rows.append(ft.Text("No recent notifications.", size=11, color=p["text_muted"]))
        self._show(self.diag_result, ft.Container(bgcolor=p["surface"], border_radius=12, padding=14, content=ft.Column(rows, spacing=8)))
