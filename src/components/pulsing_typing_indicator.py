"""
Pulsing typing indicator bubble for Nu Age AI chatbots (Flet 1.1.2).
Replaces legacy text/spinners with modern 3-dot wave pulsing animation.
"""
from __future__ import annotations
import asyncio
from typing import Optional
import flet as ft


class PulsingTypingIndicator(ft.Row):
    """
    Sleek assistant typing indicator with 3 animated dots pulsing in a wave.
    Provides start() and stop() methods to control the pulsing animation.
    """
    def __init__(
        self,
        page: Optional[ft.Page] = None,
        accent: Optional[str] = None,
        show_avatar: bool = True,
        visible: bool = False,
    ):
        self.bound_page = page
        self.accent_color = accent or ft.Colors.PRIMARY
        self._animating = False

        # 3 pulsing dots with animated opacity and scale
        self.dot1 = ft.Container(
            width=6.5,
            height=6.5,
            border_radius=ft.BorderRadius.all(3.25),
            bgcolor=self.accent_color,
            opacity=0.35,
            scale=0.85,
            animate_opacity=ft.Animation(260, ft.AnimationCurve.EASE_IN_OUT),
            animate_scale=ft.Animation(260, ft.AnimationCurve.EASE_IN_OUT),
        )
        self.dot2 = ft.Container(
            width=6.5,
            height=6.5,
            border_radius=ft.BorderRadius.all(3.25),
            bgcolor=self.accent_color,
            opacity=0.35,
            scale=0.85,
            animate_opacity=ft.Animation(260, ft.AnimationCurve.EASE_IN_OUT),
            animate_scale=ft.Animation(260, ft.AnimationCurve.EASE_IN_OUT),
        )
        self.dot3 = ft.Container(
            width=6.5,
            height=6.5,
            border_radius=ft.BorderRadius.all(3.25),
            bgcolor=self.accent_color,
            opacity=0.35,
            scale=0.85,
            animate_opacity=ft.Animation(260, ft.AnimationCurve.EASE_IN_OUT),
            animate_scale=ft.Animation(260, ft.AnimationCurve.EASE_IN_OUT),
        )

        dots_row = ft.Row(
            spacing=4.5,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[self.dot1, self.dot2, self.dot3],
        )

        # Bubble container styled like an incoming assistant message
        bubble = ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=9),
            border_radius=ft.BorderRadius.only(
                top_left=12,
                top_right=12,
                bottom_right=12,
                bottom_left=3,
            ),
            bgcolor=ft.Colors.with_opacity(0.07, ft.Colors.ON_SURFACE),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
            content=dots_row,
        )

        row_controls = []
        if show_avatar:
            avatar = ft.Container(
                width=22,
                height=22,
                border_radius=ft.BorderRadius.all(11),
                bgcolor=ft.Colors.with_opacity(0.12, self.accent_color),
                alignment=ft.Alignment.CENTER,
                content=ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=12, color=self.accent_color),
            )
            row_controls.append(avatar)
        row_controls.append(bubble)

        super().__init__(
            spacing=6,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            visible=visible,
            controls=row_controls,
        )

    def start(self, page: Optional[ft.Page] = None):
        """Starts the 3-dot wave pulse animation."""
        p = page or self.bound_page or getattr(self, "page", None)
        self.visible = True
        self._animating = True
        if p and hasattr(p, "run_task"):
            p.run_task(self._pulse_loop)

    def stop(self):
        """Stops the wave pulse animation and resets dot states."""
        self._animating = False
        self.visible = False
        try:
            self.dot1.opacity = 0.35
            self.dot1.scale = 0.85
            self.dot2.opacity = 0.35
            self.dot2.scale = 0.85
            self.dot3.opacity = 0.35
            self.dot3.scale = 0.85
        except Exception:
            pass

    async def _pulse_loop(self):
        steps = [
            (1.0, 1.25, 0.35, 0.85, 0.35, 0.85),
            (0.35, 0.85, 1.0, 1.25, 0.35, 0.85),
            (0.35, 0.85, 0.35, 0.85, 1.0, 1.25),
        ]
        step_idx = 0
        while self._animating:
            if not self.visible:
                break
            o1, s1, o2, s2, o3, s3 = steps[step_idx]
            self.dot1.opacity = o1
            self.dot1.scale = s1
            self.dot2.opacity = o2
            self.dot2.scale = s2
            self.dot3.opacity = o3
            self.dot3.scale = s3
            try:
                if hasattr(self.dot1, "page") and self.dot1.page:
                    self.dot1.update()
                    self.dot2.update()
                    self.dot3.update()
                else:
                    break
            except Exception:
                break
            step_idx = (step_idx + 1) % len(steps)
            await asyncio.sleep(0.24)


def build_pulsing_typing_indicator(
    page: Optional[ft.Page] = None,
    accent: Optional[str] = None,
    show_avatar: bool = True,
    visible: bool = False,
) -> PulsingTypingIndicator:
    return PulsingTypingIndicator(page=page, accent=accent, show_avatar=show_avatar, visible=visible)

