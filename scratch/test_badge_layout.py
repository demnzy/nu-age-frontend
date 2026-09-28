import asyncio
import os
import sys
import flet as ft

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def create_avatar_component():
    avatar_circle = ft.CircleAvatar(
        radius=40,
        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
        foreground_image_src="https://example.com/pic.jpg",
        content=ft.Text("TA", size=28, weight=ft.FontWeight.W_800, color=ft.Colors.PRIMARY)
    )

    camera_badge = ft.Container(
        content=ft.Icon(ft.Icons.CAMERA_ALT_ROUNDED, size=15, color=ft.Colors.WHITE),
        width=32,
        height=32,
        border_radius=16,
        bgcolor=ft.Colors.PRIMARY,
        border=ft.Border.all(2.5, ft.Colors.WHITE),
        alignment=ft.Alignment.CENTER,
        shadow=ft.BoxShadow(blur_radius=6, color=ft.Colors.with_opacity(0.3, ft.Colors.BLACK), offset=ft.Offset(0, 2)),
    )

    # 100x100 bounds, avatar is 88x88 placed with 4px padding from top-left,
    # badge is 32x32 placed at bottom-right (bottom=2, right=2)
    # No clipping border_radius on the outer container!
    avatar_monogram = ft.Container(
        content=ft.Stack(
            controls=[
                ft.Container(
                    left=4,
                    top=4,
                    width=88,
                    height=88,
                    border_radius=44,
                    bgcolor=ft.Colors.WHITE,
                    alignment=ft.Alignment.CENTER,
                    shadow=ft.BoxShadow(blur_radius=18, color=ft.Colors.with_opacity(0.25, ft.Colors.BLACK), offset=ft.Offset(0, 4)),
                    content=avatar_circle,
                ),
                ft.Container(
                    content=camera_badge,
                    bottom=2,
                    right=2,
                )
            ],
            width=100,
            height=100,
        ),
        tooltip="Click to change profile photo",
        on_click=lambda e: print("Clicked!"),
    )
    return avatar_monogram

if __name__ == "__main__":
    comp = create_avatar_component()
    assert comp is not None
    print("[OK] Avatar component layout valid!")
