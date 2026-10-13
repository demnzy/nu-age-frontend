import flet as ft
from typing import Dict, Any, Callable, Optional


BUNDLE_GRADIENTS = {
    "purple_indigo": ("#6366F1", "#4338CA"),
    "emerald_teal": ("#059669", "#0D9488"),
    "amber_orange": ("#D97706", "#EA580C"),
    "rose_pink": ("#E11D48", "#BE123C"),
    "sky_blue": ("#0284C7", "#1D4ED8"),
}


class StudyBundleCard(ft.Container):
    """
    Descriptive, high-impact Study Bundle Card.
    Showcases multi-pack exam combos (e.g. JAMB Science Combo: Physics + Chem + Bio + Use of English),
    aggregate question counts, discount savings badge, and 1-click download trigger.
    """
    def __init__(
        self,
        bundle: Dict[str, Any],
        on_click_inspect: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_click_download: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.bundle = bundle
        self.bundle_id = str(bundle.get("id"))
        self.on_click_inspect = on_click_inspect
        self.on_click_download = on_click_download

        gradient_key = bundle.get("theme_gradient", "purple_indigo")
        c1, c2 = BUNDLE_GRADIENTS.get(gradient_key, BUNDLE_GRADIENTS["purple_indigo"])

        title = bundle.get("title", "Study Bundle")
        desc = bundle.get("description", "")
        category = bundle.get("category", "General Combo")
        price = bundle.get("price_coins", 0)
        orig_price = bundle.get("original_price_coins", price)
        discount = bundle.get("discount_percentage", 0)
        is_owned = bundle.get("is_owned", False)
        downloads = bundle.get("downloads_count", 0)
        packs = bundle.get("packs", [])
        packs_count = bundle.get("packs_count", len(packs))
        total_q = bundle.get("total_questions", 0)

        # Build subject chips from packs
        subject_chips = []
        for p in packs[:5]:
            p_title = p.get("title", "Pack")
            # shorten if long
            if len(p_title) > 20:
                p_title = p_title[:18] + "…"
            subject_chips.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=11, color=ft.Colors.WHITE),
                            ft.Text(p_title, size=11, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE),
                        ],
                        spacing=4,
                        tight=True,
                    ),
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=ft.BorderRadius.all(12),
                    bgcolor=ft.Colors.with_opacity(0.22, ft.Colors.BLACK),
                )
            )

        if len(packs) > 5:
            subject_chips.append(
                ft.Container(
                    content=ft.Text(f"+{len(packs) - 5} more", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE70),
                    padding=ft.Padding.symmetric(horizontal=6, vertical=3),
                    border_radius=ft.BorderRadius.all(10),
                    bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.BLACK),
                )
            )

        # Discount badge
        discount_badge = ft.Container()
        if discount and discount > 0:
            discount_badge = ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED, size=12, color="#FEF08A"),
                        ft.Text(f"{discount}% OFF", size=10, weight=ft.FontWeight.BOLD, color="#FEF08A"),
                    ],
                    spacing=3,
                    tight=True,
                ),
                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                border_radius=ft.BorderRadius.all(12),
                bgcolor=ft.Colors.with_opacity(0.28, ft.Colors.BLACK),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.4, "#FEF08A")),
            )

        # Pricing block
        price_widgets = []
        if is_owned:
            price_widgets.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=13, color="#A7F3D0"),
                            ft.Text("ALL IN VAULT", size=11, weight=ft.FontWeight.BOLD, color="#A7F3D0"),
                        ],
                        spacing=3,
                        tight=True,
                    ),
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                    border_radius=ft.BorderRadius.all(12),
                    bgcolor=ft.Colors.with_opacity(0.25, "#065F46"),
                )
            )
        elif price == 0:
            price_widgets.append(
                ft.Text("FREE COMBO", size=14, weight=ft.FontWeight.BOLD, color="#A7F3D0")
            )
        else:
            if orig_price > price:
                price_widgets.append(
                    ft.Text(
                        f"{orig_price} coins",
                        size=11,
                        color=ft.Colors.WHITE60,
                        style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH),
                    )
                )
            price_widgets.append(
                ft.Row(
                    [
                        ft.Icon(ft.Icons.MONETIZATION_ON_ROUNDED, size=14, color="#FDE047"),
                        ft.Text(f"{price}", size=15, weight=ft.FontWeight.W_800, color=ft.Colors.WHITE),
                        ft.Text("coins", size=11, color=ft.Colors.WHITE70),
                    ],
                    spacing=3,
                    tight=True,
                )
            )

        # Banner hero image
        banner_url = bundle.get("banner_url")
        banner_hero = None
        if banner_url and str(banner_url).strip():
            banner_hero = ft.Container(
                height=120,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                content=ft.Stack([
                    ft.Image(
                        src=str(banner_url).strip(),
                        height=120,
                        width=float("inf"),
                        fit=ft.BoxFit.COVER,
                    ),
                    ft.Container(
                        gradient=ft.LinearGradient(
                            begin=ft.Alignment.TOP_CENTER,
                            end=ft.Alignment.BOTTOM_CENTER,
                            colors=[ft.Colors.TRANSPARENT, ft.Colors.with_opacity(0.65, ft.Colors.BLACK)],
                        ),
                    ),
                ]),
            )

        card_content = ft.Column(
            [
                # Header row: Category / Bundle pill + Discount
                ft.Row(
                    [
                        ft.Row(
                            [
                                ft.Container(
                                    content=ft.Row(
                                        [
                                            ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=11, color=ft.Colors.WHITE),
                                            ft.Text("EXAM COMBO", size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                        ],
                                        spacing=3,
                                        tight=True,
                                    ),
                                    padding=ft.Padding.symmetric(horizontal=7, vertical=3),
                                    border_radius=ft.BorderRadius.all(10),
                                    bgcolor=ft.Colors.with_opacity(0.28, ft.Colors.BLACK),
                                ),
                                ft.Text(
                                    category.upper(),
                                    size=10,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.WHITE70,
                                ),
                            ],
                            spacing=6,
                            tight=True,
                        ),
                        discount_badge,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),

                # Title & description
                ft.Text(
                    title,
                    size=16,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.WHITE,
                    max_lines=2,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                ft.Text(
                    desc if desc else f"All-in-one exam prep bundle with {packs_count} full study packs.",
                    size=12,
                    color=ft.Colors.WHITE70,
                    max_lines=2,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ) if desc else ft.Container(),

                # Subject pills wrap
                ft.Row(
                    wrap=True,
                    controls=subject_chips,
                    spacing=6,
                    run_spacing=4,
                ),

                # Metrics row: Packs count + Questions count
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.COLLECTIONS_BOOKMARK_ROUNDED, size=13, color=ft.Colors.WHITE70),
                                    ft.Text(f"{packs_count} Study Packs", size=11, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE),
                                ],
                                spacing=4,
                                tight=True,
                            ),
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.QUIZ_ROUNDED, size=13, color=ft.Colors.WHITE70),
                                    ft.Text(f"{total_q} Questions CBT", size=11, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE),
                                ],
                                spacing=4,
                                tight=True,
                            ),
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.DOWNLOAD_ROUNDED, size=12, color=ft.Colors.WHITE60),
                                    ft.Text(f"{downloads}", size=11, color=ft.Colors.WHITE70),
                                ],
                                spacing=3,
                                tight=True,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                    border_radius=ft.BorderRadius.all(12),
                    bgcolor=ft.Colors.with_opacity(0.16, ft.Colors.BLACK),
                ),

                ft.Divider(height=1, color=ft.Colors.with_opacity(0.15, ft.Colors.WHITE)),

                # Footer row: Price + CTA button
                ft.Row(
                    [
                        ft.Row(price_widgets, spacing=6, tight=True, alignment=ft.MainAxisAlignment.START),
                        ft.ElevatedButton(
                            content=ft.Row(
                                [
                                    ft.Icon(
                                        ft.Icons.INVENTORY_2_ROUNDED if is_owned else ft.Icons.DOWNLOAD_ROUNDED,
                                        size=14,
                                        color=c2,
                                    ),
                                    ft.Text(
                                        "View Vault" if is_owned else "Inspect & Get",
                                        size=12,
                                        weight=ft.FontWeight.BOLD,
                                        color=c2,
                                    ),
                                ],
                                spacing=4,
                                tight=True,
                            ),
                            bgcolor=ft.Colors.WHITE,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=ft.BorderRadius.all(12)),
                                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                                elevation=3,
                            ),
                            on_click=lambda _: self._trigger_inspect(),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            ],
            spacing=10,
        )

        full_content = ft.Column(
            [
                *( [banner_hero] if banner_hero else [] ),
                ft.Container(
                    padding=ft.Padding.all(16),
                    content=card_content,
                ),
            ],
            spacing=0,
            tight=True,
        )

        super().__init__(
            content=full_content,
            col={"sm": 12, "md": 6, "lg": 6},
            border_radius=ft.BorderRadius.all(20),
            gradient=ft.LinearGradient(
                colors=[c1, c2],
                begin=ft.Alignment.TOP_LEFT,
                end=ft.Alignment.BOTTOM_RIGHT,
            ),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.22, ft.Colors.WHITE)),
            shadow=ft.BoxShadow(
                blur_radius=14,
                spread_radius=0,
                color=ft.Colors.with_opacity(0.2, c2),
                offset=ft.Offset(0, 4),
            ),
            padding=ft.Padding.all(0),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            animate=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
            on_click=lambda _: self._trigger_inspect(),
        )

    def _trigger_inspect(self):
        if self.on_click_inspect:
            self.on_click_inspect(self.bundle)
