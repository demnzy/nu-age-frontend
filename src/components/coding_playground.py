"""
Coding Playground Component for Nu-Age LMS.
Mirrors the clean, authentic arrangement and visual language of VS Code:
- Open editor file tabs across the top (e.g. main.py, query.sql, index.html)
- Dynamic palette adapting to Light and Dark modes (crisp, vibrant white in light mode, no dull muddy grey)
- Side-by-side desktop layout (Editor on left, Terminal/Input on right) and stacked mobile layout
- Full-width, compact Stdin input with 'Run with Input' shortcut
- Clean hidden scrollbars (scroll=ScrollMode.HIDDEN) eliminating bulky scroll tracks
- Minimal boilerplate code per file buffer
- Bottom VS Code Status Bar with line/col stats, UTF-8, and execution telemetry
"""

import asyncio
import os
import tempfile
import flet as ft
from src.utils.code_runner import (
    execute_python,
    execute_sql,
    execute_remote_code,
    execute_html,
    detects_stdin,
)
from src.utils.file_opener import show_page_snackbar, open_web_preview_modal

# Minimal, clean standard boilerplate per language
PLAYGROUND_FILES = [
    {
        "id": "python",
        "name": "Python",
        "filename": "main.py",
        "badge": "Offline",
        "icon": ft.Icons.CODE_ROUNDED,
        "color": ft.Colors.BLUE_400,
        "code": '# Python 3.12\nprint("Hello from Python!")\n',
    },
    {
        "id": "sql",
        "name": "SQL",
        "filename": "query.sql",
        "badge": "Offline",
        "icon": ft.Icons.STORAGE_ROUNDED,
        "color": ft.Colors.TEAL_400,
        "code": '-- SQLite In-Memory Database\nCREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, role TEXT);\nINSERT INTO users (name, role) VALUES (\'Alice\', \'Engineer\'), (\'Bob\', \'Designer\');\nSELECT * FROM users;\n',
    },
    {
        "id": "html",
        "name": "HTML",
        "filename": "index.html",
        "badge": "Offline",
        "icon": ft.Icons.HTML_ROUNDED,
        "color": ft.Colors.DEEP_ORANGE_400,
        "code": '<!DOCTYPE html>\n<html>\n<head>\n  <style>\n    body { font-family: sans-serif; padding: 20px; }\n    h1 { color: #4F46E5; }\n  </style>\n</head>\n<body>\n  <h1>Hello, World!</h1>\n  <p>Welcome to the Web Sandbox.</p>\n</body>\n</html>\n',
    },
    {
        "id": "javascript",
        "name": "JavaScript",
        "filename": "index.js",
        "badge": "Node.js",
        "icon": ft.Icons.JAVASCRIPT_ROUNDED,
        "color": ft.Colors.AMBER_400,
        "code": '// Node.js JavaScript\nconsole.log("Hello, World!");\n',
    },
    {
        "id": "typescript",
        "name": "TypeScript",
        "filename": "index.ts",
        "badge": "Compiler",
        "icon": ft.Icons.CODE_ROUNDED,
        "color": ft.Colors.LIGHT_BLUE_400,
        "code": '// TypeScript\nconst message: string = "Hello, World!";\nconsole.log(message);\n',
    },
    {
        "id": "cpp",
        "name": "C++",
        "filename": "main.cpp",
        "badge": "GCC 9.2",
        "icon": ft.Icons.TERMINAL_ROUNDED,
        "color": ft.Colors.CYAN_400,
        "code": '#include <iostream>\n\nint main() {\n    std::cout << "Hello, World!" << std::endl;\n    return 0;\n}\n',
    },
    {
        "id": "c",
        "name": "C",
        "filename": "main.c",
        "badge": "GCC 9.2",
        "icon": ft.Icons.TERMINAL_ROUNDED,
        "color": ft.Colors.BLUE_GREY_400,
        "code": '#include <stdio.h>\n\nint main() {\n    printf("Hello, World!\\n");\n    return 0;\n}\n',
    },
    {
        "id": "java",
        "name": "Java",
        "filename": "Main.java",
        "badge": "OpenJDK",
        "icon": ft.Icons.COFFEE_ROUNDED,
        "color": ft.Colors.ORANGE_400,
        "code": 'public class Main {\n    public static void main(String[] args) {\n        System.out.println("Hello, World!");\n    }\n}\n',
    },
    {
        "id": "go",
        "name": "Go",
        "filename": "main.go",
        "badge": "Compiler",
        "icon": ft.Icons.PLAY_ARROW_ROUNDED,
        "color": ft.Colors.CYAN_300,
        "code": 'package main\n\nimport "fmt"\n\nfunc main() {\n    fmt.Println("Hello, World!")\n}\n',
    },
    {
        "id": "rust",
        "name": "Rust",
        "filename": "main.rs",
        "badge": "Compiler",
        "icon": ft.Icons.SHIELD_ROUNDED,
        "color": ft.Colors.BROWN_400,
        "code": 'fn main() {\n    println!("Hello, World!");\n}\n',
    },
]


class CodingPlayground(ft.Container):
    """
    Sleek, VS Code-modeled interactive programming playground.
    """

    def __init__(self, page: ft.Page):
        super().__init__(expand=True, padding=0)
        self.app_page = page
        self.current_lang = "python"
        self._panel_tab = "terminal"  # "terminal" or "input"

        # Maintain code and stdin buffers in memory across file tab switches
        self.code_buffers = {item["id"]: item["code"] for item in PLAYGROUND_FILES}
        self.stdin_buffers = {item["id"]: "" for item in PLAYGROUND_FILES}

        self._init_ui()

    def _get_palette(self) -> dict:
        is_dark = getattr(self.app_page, "theme_mode", None) == ft.ThemeMode.DARK if self.app_page else False
        if is_dark:
            return {
                "editor_bg": "#141418",
                "terminal_bg": "#101014",
                "terminal_header_bg": "#18181E",
                "toolbar_bg": "#18181E",
                "tabs_bar_bg": "#1B1B20",
                "active_tab_bg": "#141418",
                "inactive_tab_bg": "#1B1B20",
                "status_bar_bg": "#18181E",
                "card_bg": "#1E1E24",
                "border": "#2D2D36",
                "text": "#F3F4F6",
                "text_muted": "#9CA3AF",
                "code_text": "#F9FAFB",
                "input_bg": "#1A1A22",
                "pill_bg": "#22222A",
            }
        else:
            # Crisp, clean, vibrant Light Mode (No dull murky grey backgrounds!)
            return {
                "editor_bg": "#FFFFFF",
                "terminal_bg": "#FFFFFF",
                "terminal_header_bg": "#FAFAFA",
                "toolbar_bg": "#FFFFFF",
                "tabs_bar_bg": "#FAFAFA",
                "active_tab_bg": "#FFFFFF",
                "inactive_tab_bg": "#F1F3F5",
                "status_bar_bg": "#FFFFFF",
                "card_bg": "#FFFFFF",
                "border": "#E2E8F0",
                "text": "#0F172A",
                "text_muted": "#64748B",
                "code_text": "#0F172A",
                "input_bg": "#FFFFFF",
                "pill_bg": "#F1F5F9",
            }

    def _get_file_info(self, lang_id: str) -> dict:
        for f in PLAYGROUND_FILES:
            if f["id"] == lang_id:
                return f
        return PLAYGROUND_FILES[0]

    def _init_ui(self):
        palette = self._get_palette()
        active_info = self._get_file_info(self.current_lang)

        # ── 1. Top VS Code Toolbar & Breadcrumbs ──────────────────────────────
        self.breadcrumb_text = ft.Text(
            f"Workspace › {active_info['filename']}",
            size=12,
            weight=ft.FontWeight.W_500,
            color=palette["text_muted"],
        )

        self.engine_pill = ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
            border_radius=4,
            bgcolor=palette["pill_bg"],
            border=ft.Border.all(1, palette["border"]),
            content=ft.Row(
                spacing=5,
                tight=True,
                controls=[
                    ft.Icon(active_info["icon"], size=13, color=active_info["color"]),
                    ft.Text(f"{active_info['name']} ({active_info['badge']})", size=11, weight=ft.FontWeight.W_500, color=palette["text"]),
                ],
            ),
        )

        # Iconic Green Run Button
        self.run_btn_icon = ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, color=ft.Colors.WHITE, size=16)
        self.run_btn_spinner = ft.ProgressRing(width=14, height=14, stroke_width=2, color=ft.Colors.WHITE, visible=False)
        self.run_btn_text = ft.Text("Run", color=ft.Colors.WHITE, size=12, weight=ft.FontWeight.BOLD)

        self.run_btn = ft.FilledButton(
            content=ft.Row(
                spacing=5,
                tight=True,
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[self.run_btn_icon, self.run_btn_spinner, self.run_btn_text],
            ),
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.GREEN_600,
                color=ft.Colors.WHITE,
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            ),
            tooltip="Run Code (Executes in Sandbox)",
            on_click=lambda e: self.app_page.run_task(self._execute_code),
        )

        # Web Preview Button (HTML only)
        self.web_preview_btn = ft.FilledButton(
            content=ft.Row(
                spacing=5,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.OPEN_IN_BROWSER_ROUNDED, color=ft.Colors.WHITE, size=15),
                    ft.Text("Preview", color=ft.Colors.WHITE, size=12, weight=ft.FontWeight.BOLD),
                ],
            ),
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.DEEP_ORANGE_500,
                shape=ft.RoundedRectangleBorder(radius=6),
                padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            ),
            tooltip="Open Live Webpage Preview",
            visible=(self.current_lang == "html"),
            on_click=lambda e: self.app_page.run_task(self._open_web_preview_dialog),
        )

        self.copy_btn = ft.IconButton(
            icon=ft.Icons.CONTENT_COPY_ROUNDED,
            icon_size=16,
            icon_color=palette["text_muted"],
            tooltip="Copy Code",
            on_click=lambda e: self.app_page.run_task(self._copy_code),
        )

        self.reset_btn = ft.IconButton(
            icon=ft.Icons.REFRESH_ROUNDED,
            icon_size=16,
            icon_color=palette["text_muted"],
            tooltip="Reset to Default Boilerplate",
            on_click=self._reset_code,
        )

        self.clear_btn = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
            icon_size=16,
            icon_color=palette["text_muted"],
            tooltip="Clear Output",
            on_click=self._clear_console,
        )

        # Row 1: Workspace breadcrumb & Engine pill (scrollable to prevent mobile bleeding)
        self.workspace_row = ft.Row(
            spacing=8,
            scroll=ft.ScrollMode.HIDDEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(ft.Icons.TERMINAL_ROUNDED, size=16, color=ft.Colors.PRIMARY),
                self.breadcrumb_text,
                self.engine_pill,
            ],
        )

        # Row 2: Action buttons placed on their own row below (scrollable to prevent mobile cutoff)
        self.actions_row = ft.Row(
            spacing=6,
            scroll=ft.ScrollMode.HIDDEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                self.run_btn,
                self.web_preview_btn,
                self.copy_btn,
                self.reset_btn,
                self.clear_btn,
            ],
        )

        self.toolbar = ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            bgcolor=palette["toolbar_bg"],
            border_radius=8,
            border=ft.Border.all(1, palette["border"]),
            content=ft.Column(
                spacing=8,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=[
                    self.workspace_row,
                    self.actions_row,
                ],
            ),
        )

        # ── 2. VS Code File Tabs Row (Hidden Scrollbar) ───────────────────────
        self.tab_controls = {}
        file_tabs = []
        for f in PLAYGROUND_FILES:
            tab_container = self._build_file_tab(f, palette)
            self.tab_controls[f["id"]] = tab_container
            file_tabs.append(tab_container)

        self.file_tabs_bar = ft.Container(
            bgcolor=palette["tabs_bar_bg"],
            border_radius=ft.BorderRadius.only(top_left=8, top_right=8),
            border=ft.Border.only(
                bottom=ft.BorderSide(1, palette["border"])
            ),
            content=ft.Row(
                spacing=2,
                scroll=ft.ScrollMode.HIDDEN,
                controls=file_tabs,
            ),
        )

        # ── 3. Code Editor Box ────────────────────────────────────────────────
        self.code_input = ft.TextField(
            value=self.code_buffers[self.current_lang],
            multiline=True,
            min_lines=18,
            max_lines=28,
            border=ft.InputBorder.NONE,
            content_padding=ft.Padding.all(14),
            text_style=ft.TextStyle(
                font_family="Consolas, 'Courier New', monospace",
                size=13,
                color=palette["code_text"],
            ),
            cursor_color=ft.Colors.PRIMARY,
            on_change=self._on_code_change,
        )

        self.editor_box = ft.Container(
            expand=True,
            border_radius=8,
            bgcolor=palette["editor_bg"],
            border=ft.Border.all(1, palette["border"]),
            content=ft.Column(
                spacing=0,
                expand=True,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=[
                    self.file_tabs_bar,
                    self.code_input,
                ],
            ),
        )

        # ── 4. VS Code Terminal & Stdin Panel (Right/Bottom) ──────────────────
        self.terminal_tab_btn = ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            bgcolor=palette["editor_bg"],
            border=ft.Border.only(bottom=ft.BorderSide(2, ft.Colors.PRIMARY)),
            on_click=lambda e: self._switch_panel_tab("terminal"),
            content=ft.Row(
                spacing=5,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.TERMINAL_ROUNDED, size=14, color=ft.Colors.PRIMARY),
                    ft.Text("TERMINAL", size=11, weight=ft.FontWeight.BOLD, color=palette["text"]),
                ],
            ),
        )

        self.stdin_badge_dot = ft.Container(
            width=6,
            height=6,
            border_radius=3,
            bgcolor=ft.Colors.AMBER_500,
            visible=False,
        )

        self.stdin_tab_btn = ft.Container(
            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            bgcolor=ft.Colors.TRANSPARENT,
            border=ft.Border.only(bottom=ft.BorderSide(2, ft.Colors.TRANSPARENT)),
            on_click=lambda e: self._switch_panel_tab("input"),
            content=ft.Row(
                spacing=5,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.KEYBOARD_OUTLINED, size=14, color=palette["text_muted"]),
                    ft.Text("INPUT (STDIN)", size=11, weight=ft.FontWeight.W_500, color=palette["text_muted"]),
                    self.stdin_badge_dot,
                ],
            ),
        )

        self.status_pill_text = ft.Text("Ready", size=11, weight=ft.FontWeight.W_600, color=palette["text_muted"])
        self.status_pill = ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=3),
            border_radius=4,
            bgcolor=palette["pill_bg"],
            content=self.status_pill_text,
        )

        self.terminal_tabs_row = ft.Row(
            spacing=4,
            scroll=ft.ScrollMode.HIDDEN,
            controls=[
                self.terminal_tab_btn,
                self.stdin_tab_btn,
            ],
        )

        self.terminal_header = ft.Container(
            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            bgcolor=palette["terminal_header_bg"],
            border_radius=ft.BorderRadius.only(top_left=8, top_right=8),
            border=ft.Border.only(bottom=ft.BorderSide(1, palette["border"])),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(
                        content=self.terminal_tabs_row,
                        expand=True,
                    ),
                    self.status_pill,
                ],
            ),
        )

        # Terminal Output Content
        self.console_output = ft.Text(
            "Terminal ready.\nClick 'Run' to execute in sandbox...",
            font_family="Consolas, 'Courier New', monospace",
            size=12,
            color=palette["code_text"],
            selectable=True,
        )

        self.sql_table_container = ft.Column(
            scroll=ft.ScrollMode.HIDDEN,
            visible=False,
            spacing=8,
        )

        # Beginner note banner inside terminal if stdin is needed
        self.terminal_stdin_notice = ft.Container(
            visible=False,
            padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            border_radius=6,
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER_400),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.AMBER_400)),
            content=ft.Row(
                spacing=8,
                controls=[
                    ft.Icon(ft.Icons.TIPS_AND_UPDATES_ROUNDED, size=15, color=ft.Colors.AMBER_500),
                    ft.Text(
                        "Code requests user input! Click 'PROGRAM INPUT (STDIN)' tab above to supply inputs.",
                        size=11,
                        color=ft.Colors.AMBER_600 if not getattr(self.app_page, "theme_mode", None) == ft.ThemeMode.DARK else ft.Colors.AMBER_300,
                        expand=True,
                    ),
                ],
            ),
        )

        self.terminal_view = ft.Container(
            expand=True,
            padding=12,
            content=ft.Column(
                expand=True,
                scroll=ft.ScrollMode.HIDDEN,
                spacing=8,
                controls=[
                    self.terminal_stdin_notice,
                    self.console_output,
                    self.sql_table_container,
                ],
            ),
        )

        # Input (stdin) Tab Content: Full Width & Compact Proportions
        self.stdin_hint_card = ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            border_radius=6,
            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER_400),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.AMBER_400)),
            content=ft.Row(
                spacing=8,
                controls=[
                    ft.Icon(ft.Icons.TIPS_AND_UPDATES_ROUNDED, size=16, color=ft.Colors.AMBER_500),
                    ft.Text(
                        "Type responses here before running (put each answer on a new line).",
                        size=11,
                        weight=ft.FontWeight.W_500,
                        color=ft.Colors.AMBER_600 if not getattr(self.app_page, "theme_mode", None) == ft.ThemeMode.DARK else ft.Colors.AMBER_300,
                        expand=True,
                    ),
                ],
            ),
        )

        self.stdin_input = ft.TextField(
            label="Program Input (stdin)",
            hint_text="Enter input here before clicking Run (e.g. Alice)...",
            multiline=True,
            min_lines=1,
            max_lines=4,
            dense=True,
            border_radius=8,
            border_color=palette["border"],
            bgcolor=palette["input_bg"],
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=10),
            text_style=ft.TextStyle(font_family="Consolas, monospace", size=12, color=palette["text"]),
            label_style=ft.TextStyle(size=12, color=ft.Colors.PRIMARY),
            hint_style=ft.TextStyle(size=11, color=palette["text_muted"]),
            on_change=self._on_stdin_change,
        )

        self.stdin_action_row = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Text("Each answer on a new line", size=11, color=palette["text_muted"]),
                ft.FilledButton(
                    content=ft.Row(
                        spacing=4,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, size=14, color=ft.Colors.WHITE),
                            ft.Text("Run with Input", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ],
                    ),
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.GREEN_600,
                        shape=ft.RoundedRectangleBorder(radius=6),
                        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                    ),
                    on_click=lambda e: self.app_page.run_task(self._execute_code),
                ),
            ],
        )

        self.input_view = ft.Container(
            expand=True,
            padding=12,
            visible=False,
            content=ft.Column(
                spacing=10,
                scroll=ft.ScrollMode.HIDDEN,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=[
                    self.stdin_hint_card,
                    self.stdin_input,
                    self.stdin_action_row,
                ],
            ),
        )

        self.terminal_box = ft.Container(
            expand=True,
            border_radius=8,
            bgcolor=palette["terminal_bg"],
            border=ft.Border.all(1, palette["border"]),
            content=ft.Column(
                spacing=0,
                expand=True,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                controls=[
                    self.terminal_header,
                    self.terminal_view,
                    self.input_view,
                ],
            ),
        )

        # ── 5. Responsive Workspace Layout (Side-by-side Desktop, Stacked Mobile)
        workspace = ft.ResponsiveRow(
            spacing=10,
            run_spacing=10,
            controls=[
                ft.Container(
                    col={"xs": 12, "lg": 7},
                    content=self.editor_box,
                ),
                ft.Container(
                    col={"xs": 12, "lg": 5},
                    content=self.terminal_box,
                ),
            ],
        )

        # ── 6. Bottom VS Code Status Bar ──────────────────────────────────────
        self.status_line_col = ft.Text("Ln 1, Chars 0", size=11, color=palette["text_muted"])
        self.status_telemetry = ft.Text("0.0 ms", size=11, color=palette["text_muted"])

        self.status_bar = ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=4),
            bgcolor=palette["status_bar_bg"],
            border_radius=6,
            border=ft.Border.all(1, palette["border"]),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        spacing=8,
                        tight=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, size=13, color=ft.Colors.PRIMARY),
                            ft.Text("Ready", size=11, color=palette["text_muted"]),
                            ft.Text(" |  UTF-8  | ", size=11, color=palette["border"]),
                            self.status_line_col,
                        ],
                    ),
                    ft.Row(
                        spacing=8,
                        tight=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            self.status_telemetry,
                        ],
                    ),
                ],
            ),
        )

        # Assemble full IDE view with hidden scrollbar to eliminate bulky tracks
        self.content = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.HIDDEN,
            spacing=10,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[
                self.toolbar,
                workspace,
                self.status_bar,
            ],
        )

        self._check_stdin_detection()
        self._update_stats()

    def _build_file_tab(self, file_info: dict, palette: dict) -> ft.Container:
        is_active = (file_info["id"] == self.current_lang)

        tab_title = ft.Text(
            file_info["filename"],
            size=12,
            weight=ft.FontWeight.W_600 if is_active else ft.FontWeight.W_400,
            color=palette["text"] if is_active else palette["text_muted"],
        )

        tab_container = ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            bgcolor=palette["active_tab_bg"] if is_active else ft.Colors.TRANSPARENT,
            border=ft.Border.only(
                top=ft.BorderSide(2, ft.Colors.PRIMARY if is_active else ft.Colors.TRANSPARENT),
                right=ft.BorderSide(1, palette["border"]),
            ),
            content=ft.Row(
                spacing=6,
                tight=True,
                controls=[
                    ft.Icon(file_info["icon"], size=14, color=file_info["color"]),
                    tab_title,
                ],
            ),
            on_click=lambda e, lid=file_info["id"]: self._switch_language(lid),
        )
        return tab_container

    def _switch_language(self, lang_id: str):
        if lang_id == self.current_lang:
            return

        palette = self._get_palette()

        # 1. Save current editor buffer
        self.code_buffers[self.current_lang] = self.code_input.value or ""

        # 2. Update active language
        self.current_lang = lang_id
        active_info = self._get_file_info(lang_id)

        # 3. Update editor text
        self.code_input.value = self.code_buffers.get(lang_id, active_info["code"])
        self.stdin_input.value = self.stdin_buffers.get(lang_id, "")

        # 4. Update tab highlights
        for lid, container in self.tab_controls.items():
            is_active = (lid == self.current_lang)
            container.bgcolor = palette["active_tab_bg"] if is_active else ft.Colors.TRANSPARENT
            container.border = ft.Border.only(
                top=ft.BorderSide(2, ft.Colors.PRIMARY if is_active else ft.Colors.TRANSPARENT),
                right=ft.BorderSide(1, palette["border"]),
            )
            text_ctrl = container.content.controls[1]
            text_ctrl.weight = ft.FontWeight.W_600 if is_active else ft.FontWeight.W_400
            text_ctrl.color = palette["text"] if is_active else palette["text_muted"]

        # 5. Update breadcrumbs and engine pill
        self.breadcrumb_text.value = f"Workspace › {active_info['filename']}"
        self.engine_pill.content.controls[0].name = active_info["icon"]
        self.engine_pill.content.controls[0].color = active_info["color"]
        self.engine_pill.content.controls[1].value = f"{active_info['name']} ({active_info['badge']})"

        # 6. Show/Hide Web Preview button
        self.web_preview_btn.visible = (self.current_lang == "html")

        # 7. Update terminal & stdin checks
        self._check_stdin_detection()
        self._update_stats()
        self._clear_console()

        if self.app_page:
            self.app_page.update()

    def _switch_panel_tab(self, tab: str):
        self._panel_tab = tab
        palette = self._get_palette()
        is_term = (tab == "terminal")

        # Visual button highlights
        self.terminal_tab_btn.bgcolor = palette["editor_bg"] if is_term else ft.Colors.TRANSPARENT
        self.terminal_tab_btn.border = ft.Border.only(bottom=ft.BorderSide(2, ft.Colors.PRIMARY if is_term else ft.Colors.TRANSPARENT))
        self.terminal_tab_btn.content.controls[0].color = ft.Colors.PRIMARY if is_term else palette["text_muted"]
        self.terminal_tab_btn.content.controls[1].color = palette["text"] if is_term else palette["text_muted"]
        self.terminal_tab_btn.content.controls[1].weight = ft.FontWeight.BOLD if is_term else ft.FontWeight.W_500

        self.stdin_tab_btn.bgcolor = palette["editor_bg"] if not is_term else ft.Colors.TRANSPARENT
        self.stdin_tab_btn.border = ft.Border.only(bottom=ft.BorderSide(2, ft.Colors.PRIMARY if not is_term else ft.Colors.TRANSPARENT))
        self.stdin_tab_btn.content.controls[0].color = ft.Colors.PRIMARY if not is_term else palette["text_muted"]
        self.stdin_tab_btn.content.controls[1].color = palette["text"] if not is_term else palette["text_muted"]
        self.stdin_tab_btn.content.controls[1].weight = ft.FontWeight.BOLD if not is_term else ft.FontWeight.W_500

        # View visibility
        self.terminal_view.visible = is_term
        self.input_view.visible = not is_term

        if self.app_page:
            self.app_page.update()

    def _on_code_change(self, e):
        self._check_stdin_detection()
        self._update_stats()
        if self.app_page:
            self.app_page.update()

    def _on_stdin_change(self, e):
        self.stdin_buffers[self.current_lang] = self.stdin_input.value or ""

    def _check_stdin_detection(self):
        code = self.code_input.value or ""
        needs_stdin = detects_stdin(self.current_lang, code)
        is_sql = self.current_lang == "sql"
        is_html = self.current_lang == "html"

        # Show attention indicator on the Stdin tab and terminal notice
        should_alert = needs_stdin and not is_sql and not is_html
        self.stdin_badge_dot.visible = should_alert
        self.terminal_stdin_notice.visible = should_alert

    def _update_stats(self):
        code = self.code_input.value or ""
        lines = len(code.splitlines()) if code else 1
        chars = len(code)
        self.status_line_col.value = f"Ln {lines}, Chars {chars}"

    async def _copy_code(self, e=None):
        code = self.code_input.value or ""
        if self.app_page:
            try:
                if hasattr(self.app_page, "clipboard") and hasattr(self.app_page.clipboard, "set"):
                    res = self.app_page.clipboard.set(code)
                    if asyncio.iscoroutine(res):
                        await res
                elif hasattr(self.app_page, "set_clipboard"):
                    res = self.app_page.set_clipboard(code)
                    if asyncio.iscoroutine(res):
                        await res
            except Exception as ex:
                print(f"Clipboard copy error: {ex}")

            show_page_snackbar(
                self.app_page,
                ft.SnackBar(
                    content=ft.Text("Code copied to clipboard!", color=ft.Colors.WHITE, size=13),
                    bgcolor=ft.Colors.PRIMARY,
                    duration=2000,
                ),
            )

    def _reset_code(self, e=None):
        active_info = self._get_file_info(self.current_lang)
        self.code_input.value = active_info["code"]
        self.code_buffers[self.current_lang] = active_info["code"]
        self.stdin_input.value = ""
        self.stdin_buffers[self.current_lang] = ""
        self._clear_console()
        self._check_stdin_detection()
        self._update_stats()
        if self.app_page:
            self.app_page.update()

    def _clear_console(self, e=None):
        palette = self._get_palette()
        self.console_output.value = "Terminal ready.\nClick 'Run' to execute in sandbox..."
        self.console_output.color = palette["code_text"]
        self.sql_table_container.visible = False
        self.sql_table_container.controls.clear()
        self.status_pill_text.value = "Ready"
        self.status_pill_text.color = palette["text_muted"]
        self.status_pill.bgcolor = palette["pill_bg"]
        self.status_telemetry.value = "0.0 ms"
        if self.app_page:
            self.app_page.update()

    async def _execute_code(self):
        if self.run_btn.disabled:
            return

        palette = self._get_palette()
        self.run_btn.disabled = True
        self.run_btn_icon.visible = False
        self.run_btn_spinner.visible = True
        self.run_btn_text.value = "Running"
        self.status_pill_text.value = "Running…"
        self.status_pill_text.color = ft.Colors.AMBER_500
        self.status_pill.bgcolor = ft.Colors.with_opacity(0.15, ft.Colors.AMBER_400)
        self.console_output.value = "Executing in sandbox…"
        self.console_output.color = palette["text_muted"]
        self.sql_table_container.visible = False

        # Automatically switch to Terminal view when running
        if self._panel_tab != "terminal":
            self._switch_panel_tab("terminal")
        self.app_page.update()

        lang = self.current_lang
        code = self.code_input.value or ""
        stdin_val = self.stdin_input.value or ""

        try:
            if lang == "sql":
                res = await asyncio.to_thread(execute_sql, code)
                duration_ms = res.get("duration_ms", 0.0)
                self.status_telemetry.value = f"{duration_ms} ms"

                if res["success"]:
                    self.status_pill_text.value = f"Success ({duration_ms}ms)"
                    self.status_pill_text.color = ft.Colors.GREEN_600
                    self.status_pill.bgcolor = ft.Colors.with_opacity(0.15, ft.Colors.GREEN_500)

                    self.sql_table_container.controls.clear()
                    cols = res.get("columns", [])
                    rows = res.get("rows", [])

                    if cols and rows:
                        data_cols = [
                            ft.DataColumn(ft.Text(str(c), weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY, size=12))
                            for c in cols
                        ]
                        data_rows = [
                            ft.DataRow(
                                cells=[
                                    ft.DataCell(ft.Text(str(val), size=12, color=palette["text"]))
                                    for val in r
                                ]
                            )
                            for r in rows[:100]
                        ]
                        table = ft.DataTable(
                            columns=data_cols,
                            rows=data_rows,
                            border=ft.Border.all(1, palette["border"]),
                            border_radius=6,
                            heading_row_color=palette["pill_bg"],
                        )
                        self.sql_table_container.controls.append(table)
                        self.sql_table_container.visible = True
                        self.console_output.value = f"Query executed successfully in {duration_ms}ms ({len(rows)} rows returned):"
                        self.console_output.color = ft.Colors.GREEN_600
                    else:
                        self.console_output.value = f"Query executed successfully ({res.get('rowcount', 0)} rows affected)."
                        self.console_output.color = ft.Colors.GREEN_600
                else:
                    self.status_pill_text.value = "Error"
                    self.status_pill_text.color = ft.Colors.RED_500
                    self.status_pill.bgcolor = ft.Colors.with_opacity(0.15, ft.Colors.RED_400)
                    self.console_output.value = f"SQL ERROR:\n{res['error']}"
                    self.console_output.color = ft.Colors.RED_500

            elif lang == "python":
                res = await asyncio.to_thread(execute_python, code, test_input=stdin_val)
                duration_ms = res.get("duration_ms", 0.0)
                self.status_telemetry.value = f"{duration_ms} ms"

                if res["success"]:
                    self.status_pill_text.value = f"Success ({duration_ms}ms)"
                    self.status_pill_text.color = ft.Colors.GREEN_600
                    self.status_pill.bgcolor = ft.Colors.with_opacity(0.15, ft.Colors.GREEN_500)
                    self.console_output.value = res["output"] or "(Code executed successfully with no stdout output)"
                    self.console_output.color = palette["code_text"]
                else:
                    self.status_pill_text.value = "Error"
                    self.status_pill_text.color = ft.Colors.RED_500
                    self.status_pill.bgcolor = ft.Colors.with_opacity(0.15, ft.Colors.RED_400)
                    self.console_output.value = f"RUNTIME ERROR:\n{res['error']}"
                    self.console_output.color = ft.Colors.RED_500

            elif lang == "html":
                res = await asyncio.to_thread(execute_html, code)
                duration_ms = res.get("duration_ms", 0.0)
                self.status_telemetry.value = f"{duration_ms} ms"

                if res["success"]:
                    self.status_pill_text.value = f"Valid ({duration_ms}ms)"
                    self.status_pill_text.color = ft.Colors.GREEN_600
                    self.status_pill.bgcolor = ft.Colors.with_opacity(0.15, ft.Colors.GREEN_500)
                    self.console_output.value = f"HTML/WEB SANDBOX VALIDATION:\n{res['output']}\n\nClick 'Preview' in the top bar to view live in browser."
                    self.console_output.color = palette["code_text"]
                else:
                    self.status_pill_text.value = "HTML Error"
                    self.status_pill_text.color = ft.Colors.RED_500
                    self.status_pill.bgcolor = ft.Colors.with_opacity(0.15, ft.Colors.RED_400)
                    self.console_output.value = f"HTML ERROR:\n{res['error']}"
                    self.console_output.color = ft.Colors.RED_500

            else:
                res = await asyncio.to_thread(execute_remote_code, lang, code, test_input=stdin_val)
                duration_ms = res.get("duration_ms", 0.0)
                self.status_telemetry.value = f"{duration_ms} ms"

                if res.get("offline_blocked"):
                    self.status_pill_text.value = "Offline Blocked"
                    self.status_pill_text.color = ft.Colors.AMBER_500
                    self.status_pill.bgcolor = ft.Colors.with_opacity(0.15, ft.Colors.AMBER_400)
                    self.console_output.value = f"OFFLINE NOTICE:\n{res['error']}"
                    self.console_output.color = ft.Colors.AMBER_500
                elif res["success"]:
                    self.status_pill_text.value = f"Success ({duration_ms}ms)"
                    self.status_pill_text.color = ft.Colors.GREEN_600
                    self.status_pill.bgcolor = ft.Colors.with_opacity(0.15, ft.Colors.GREEN_500)
                    self.console_output.value = res["output"] or "(Code compiled and executed with no stdout output)"
                    self.console_output.color = palette["code_text"]
                else:
                    self.status_pill_text.value = "Error"
                    self.status_pill_text.color = ft.Colors.RED_500
                    self.status_pill.bgcolor = ft.Colors.with_opacity(0.15, ft.Colors.RED_400)
                    self.console_output.value = f"COMPILATION / RUNTIME ERROR:\n{res['error']}"
                    self.console_output.color = ft.Colors.RED_500

        except Exception as ex:
            self.status_pill_text.value = "Crash"
            self.status_pill_text.color = ft.Colors.RED_500
            self.status_pill.bgcolor = ft.Colors.with_opacity(0.15, ft.Colors.RED_400)
            self.console_output.value = f"EXECUTION CRASH:\n{ex}"
            self.console_output.color = ft.Colors.RED_500

        finally:
            self.run_btn.disabled = False
            self.run_btn_icon.visible = True
            self.run_btn_spinner.visible = False
            self.run_btn_text.value = "Run"
            self.app_page.update()

    async def _open_web_preview_dialog(self, e=None):
        code = self.code_input.value or "<h1>Empty HTML Document</h1>"
        try:
            open_web_preview_modal(self.app_page, code, title="Webpage Preview")
        except Exception as ex:
            print(f"Error presenting web preview: {ex}")
            if self.app_page:
                show_page_snackbar(
                    self.app_page,
                    ft.SnackBar(
                        content=ft.Text(f"Could not open preview: {ex}"),
                        bgcolor=ft.Colors.RED_700,
                    ),
                )
