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


