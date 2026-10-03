# Flet Version 0.86.5
- Our current version of Flet is **0.86.5**.
- **DO NOT** modify existing code solely to resolve Flet deprecation warnings (e.g., shared_preferences, go(), ElevatedButton) unless the user explicitly requests it.
- When the user provides a console output containing both runtime errors and deprecation warnings, focus strictly on resolving the runtime errors and ignore the warnings.

## Control & Property Conventions
- **Border Radius**: Always use `ft.BorderRadius.only(...)`, `ft.BorderRadius.all(...)`, or an integer/float (e.g., `border_radius=12`). Never call `ft.border_radius.only` (`ft.border_radius` is a module, not the class).
- **Image Fitting**: Always use `ft.BoxFit.CONTAIN`, `ft.BoxFit.COVER`, etc. on `ft.Image(fit=...)`. Do not use `ft.ImageFit` (it does not exist in Flet).
- **Padding & Margin**: Use `ft.Padding.symmetric(...)`, `ft.Padding.only(...)`, `ft.Padding.all(...)`, or integers.
- **FilePicker & Services**: `ft.FilePicker` is a `Service`, NOT a UI control. **NEVER** add `FilePicker` to `page.overlay` or `page.controls` (doing so causes the client to crash with `Unknown control: FilePicker`). Directly instantiate and await `ft.FilePicker().pick_files(...)` within event callbacks, matching `org_view.py`, `create_course.py`, and `self_study.py`.
- **PopupMenuItem**: Always pass `content=...` (e.g. `content="Rename Module"` or `content=ft.Text(...)`). Never pass `text=...` (`PopupMenuItem` does not have a `text` parameter in Flet 0.86.5).
- **TextField Styling**: Never pass `weight=...` directly to `ft.TextField`. Use `text_style=ft.TextStyle(weight=...)`.
- **Window Dimensions**: Never access `page.window_width`. Use `page.width` or safely check `getattr(page.window, "width", None)`.
- **TemplateRoute Matching**: Never chain pattern matching on a single `TemplateRoute` instance using `or` (e.g. `if troute.match(A) or troute.match(B):`), because a failed match clears extracted route parameters. Use separate `if` / `elif` branches or separate `TemplateRoute` instances.
- **Runtime Verification**: `py_compile` only checks static syntax. Always run a quick instantiation test of any new or modified view with a mock `Page` in the `.venv` Python environment to catch runtime `AttributeError`s before presenting results.

## Mobile Responsiveness & Viewport Bounding Invariants
- **Dynamic Mobile Bubble & Card Bounding**:
  - Never apply fixed pixel widths to chat message bubbles, discussion cards, or form containers on mobile.
  - Always bound text containers dynamically using screen width (e.g. `max_bubble_width = min(420, max(220, int(screen_width * 0.78)))`) and ensure all text controls have `text_align` or wrap properly within their flex parents.
- **Single-Column Mobile Forms**:
  - When rendering multi-field forms (e.g. registration, course creation, profile settings), multi-column paired rows must automatically convert to clean single-column vertical stacks on mobile screens (`< 920px`).
- **Drawer & Overlay Viewport Clamping**:
  - When expanding modal bottom sheets, AI drawers, or dialog overlays on mobile, NEVER leave the top edge unbounded.
  - Always clamp full-screen animated overlays within viewport boundaries (e.g. `top=8, bottom=8, left=8, right=8`) so navigation headers, close buttons, and prompt chips are never pushed off-screen.
- **Flex Expansion in Rows & Columns**:
  - NEVER instantiate `ft.Expanded(...)` (it does not exist in Flet and raises `AttributeError`). Set `expand=True` directly on child controls or wrap in `ft.Container(..., expand=True)`.
  - NEVER pass `constraints=ft.BoxConstraints(...)` to `ft.Container` in Flet 0.86.5. Use explicit responsive `width`/`height` or flex `expand=True`.

## Clipboard & Services Conventions
- **Clipboard Access**: NEVER call `page.set_clipboard(...)`. In Flet 0.86.5, `set_clipboard` does not exist on `Page` and will raise `AttributeError`.
  - Always use `await safe_set_clipboard(page, text)` from `src.utils.file_opener` (which calls `await page.clipboard.set(text)` or `await ft.Clipboard().set(text)`).
  - Always display copy confirmations using `show_page_snackbar(page, ...)`.

## Layout & Multi-Tasking UX Conventions
- **Desktop Companion Panels Over Draggable Overlays**:
  - When designing study assistants, document inspectors, or chat companions that learners use alongside active course content (videos, reading, quizzes), prefer a **collapsible right sidebar / split pane** (e.g. `width=380`, `ft.Row([main_content_area, ai_sidebar])`) over a floating, draggable window.
  - A side-by-side dock prevents obscuring active learning material, eliminates clumsy gesture drag physics, and allows simultaneous scrolling/watching without layout conflicts.
  - On mobile (< 768px), gracefully adapt to a non-intrusive collapsible bottom sheet or 1-tap minimize dock.

## UI Feedback & Interactive State Invariants
- **Async Button Feedback**: Whenever an action or submission button initiates an asynchronous network or background task (e.g. publishing topics, submitting replies, generating AI responses), the button MUST immediately switch to a loading state (e.g., `ft.ProgressRing` and disabled state) until the operation completes.
- **Category-Cognizant Zero States**: Filtered list views and tab categories must display context-aware empty states. Never display a generic "No items; create one here" message on filtered or terminal tabs (such as "Solved" or "Search Results"). Always provide relevant context and a clear action.

## Callback & Event Handler Invariants
- **Flexible Event Signatures**: Any UI event callback or toggle function (e.g., `toggle_need_help(e=None)`) must accept an optional event argument `e=None` so it can be invoked both directly and from Flet event triggers (`on_click=func`).



