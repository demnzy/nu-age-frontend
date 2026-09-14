---
name: Flet v0.86.5 Styling Convention
description: Mandatory naming convention for Flet layout and styling structures.
---

# Flet v0.86.5 Styling Convention
When writing or modifying Flet frontend code, you MUST use the correct PascalCase structs for layout and styling properties, as required by Flet v0.86.5. 

Never use deprecated lowercase submodules.

**Correct Usage (PascalCase):**
- `margin=ft.Margin.only(top=10)` or `margin=ft.Margin.all(10)`
- `padding=ft.Padding.only(left=20)` or `padding=ft.Padding.symmetric(horizontal=16)`
- `alignment=ft.Alignment(0, 0)` or `alignment=ft.alignment.center`
- `border=ft.Border(...)`
- `border_radius=ft.BorderRadius(...)`

**Incorrect Usage:**
- `margin=ft.margin.only(...)` (Will throw AttributeError)
- `padding=ft.padding.only(...)` (Will throw AttributeError)

Always prioritize checking the official Flet v0.86.5 documentation (https://flet.dev/docs/controls/) before applying fixes or creating new UI layouts to ensure structural accuracy.
