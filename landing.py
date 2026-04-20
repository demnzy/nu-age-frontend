import flet as ft

def main(page: ft.Page):
    page.title = "Nu-age | The Offline-First AI Learning Platform"
    page.padding = 0
    page.bgcolor = ft.Colors.WHITE
    page.theme_mode = ft.ThemeMode.LIGHT
    
    # Modern Typography & Theming
    page.fonts = {"Inter": "https://rsms.me/inter/font-files/Inter-Regular.woff2?v=3.19"}
    page.theme = ft.Theme(
        font_family="Inter", 
        color_scheme_seed=ft.Colors.INDIGO,
    )

    # =========================================================
    # 1. NAVBAR
    # =========================================================
    navbar = ft.Container(
        padding=ft.padding.symmetric(horizontal=50, vertical=20),
        bgcolor=ft.Colors.with_opacity(0.95, ft.Colors.WHITE),
        blur=ft.Blur(10, 10, ft.BlurTileMode.MIRROR),
        content=ft.Row([
            ft.Row([
                ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=ft.Colors.INDIGO_600, size=32),
                ft.Text("Nu-age.", size=26, weight=ft.FontWeight.W_900, color=ft.Colors.BLACK87),
            ], alignment=ft.MainAxisAlignment.START),
            
            ft.Row([
                ft.TextButton("Features", style=ft.ButtonStyle(color=ft.Colors.BLACK87)),
                ft.TextButton("Architecture", style=ft.ButtonStyle(color=ft.Colors.BLACK87)),
                ft.ElevatedButton("Live Demo", bgcolor=ft.Colors.BLACK87, color=ft.Colors.WHITE),
            ], alignment=ft.MainAxisAlignment.END, visible=not page.width < 700) 
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    )

    # =========================================================
    # 2. HERO SECTION (Gradient & High Contrast)
    # =========================================================
    hero_section = ft.Container(
        padding=ft.padding.symmetric(horizontal=40, vertical=100),
        gradient=ft.LinearGradient(
            begin=ft.Alignment.TOP_LEFT,
            end=ft.Alignment.BOTTOM_RIGHT,
            colors=[ft.Colors.INDIGO_50, ft.Colors.WHITE, ft.Colors.BLUE_50]
        ),
        content=ft.Column([
            ft.Container(
                padding=ft.padding.symmetric(horizontal=16, vertical=8),
                border_radius=20,
                bgcolor=ft.Colors.INDIGO_100,
                content=ft.Text("✨ Built for the Next Generation of Learners", color=ft.Colors.INDIGO_900, size=13, weight=ft.FontWeight.BOLD)
            ),
            ft.Text(
                "Education that works everywhere.\nPowered by AI.", 
                size=64, 
                weight=ft.FontWeight.W_900, 
                color=ft.Colors.BLACK87,
                text_align=ft.TextAlign.CENTER,
                height=1.1,
            ),
            ft.Container(height=10),
            ft.Text(
                "Nu-age is an offline-first, lightweight Learning Management System. \nAccess automated question banks, assess learners dynamically, and sync seamlessly.", 
                size=20, 
                color=ft.Colors.BLACK54,
                text_align=ft.TextAlign.CENTER
            ),
            ft.Container(height=40),
            ft.Row([
                ft.ElevatedButton(
                    content=ft.Container(
                        padding=ft.padding.symmetric(horizontal=20, vertical=15),
                        content=ft.Row([ft.Icon(ft.Icons.ANDROID, color=ft.Colors.WHITE), ft.Text("Download APK", size=16, weight="bold")])
                    ),
                    bgcolor=ft.Colors.INDIGO_600,
                    color=ft.Colors.WHITE,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
                ),
                ft.OutlinedButton(
                    content=ft.Container(
                        padding=ft.padding.symmetric(horizontal=20, vertical=15),
                        content=ft.Row([ft.Icon(ft.Icons.PLAY_CIRCLE_OUTLINE, color=ft.Colors.INDIGO_600), ft.Text("Watch Demonstration", size=16, weight="bold")])
                    ),
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))
                )
            ], alignment=ft.MainAxisAlignment.CENTER, wrap=True, spacing=20)
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    )

    # =========================================================
    # 3. INTERACTIVE FEATURES GRID 
    # =========================================================
    def on_card_hover(e):
        e.control.scale = 1.03 if e.data == "true" else 1.0
        e.control.shadow = ft.BoxShadow(blur_radius=30, color=ft.Colors.BLACK12, offset=ft.Offset(0, 10)) if e.data == "true" else ft.BoxShadow(blur_radius=10, color=ft.Colors.BLACK12, offset=ft.Offset(0, 4))
        e.control.update()

    def feature_card(icon, title, desc):
        return ft.Container(
            padding=40,
            border_radius=16,
            bgcolor=ft.Colors.WHITE,
            border=ft.border.all(1, ft.Colors.GREY_200),
            shadow=ft.BoxShadow(blur_radius=10, color=ft.Colors.BLACK12, offset=ft.Offset(0, 4)),
            scale=ft.Scale(1.0),
            animate_scale=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
            on_hover=on_card_hover,
            content=ft.Column([
                ft.Container(
                    padding=15, 
                    border_radius=12, 
                    bgcolor=ft.Colors.INDIGO_50, 
                    content=ft.Icon(icon, color=ft.Colors.INDIGO_600, size=35)
                ),
                ft.Text(title, size=22, weight=ft.FontWeight.W_800, color=ft.Colors.BLACK87,),
                ft.Text(desc, color=ft.Colors.BLACK54, size=16, height=1.5)
            ], spacing=20)
        )

    features_section = ft.Container(
        padding=ft.padding.symmetric(horizontal=50, vertical=100),
        bgcolor=ft.Colors.WHITE,
        content=ft.Column([
            ft.Text("Engineered for Resilience", size=38, weight=ft.FontWeight.W_900, text_align=ft.TextAlign.CENTER, ),
            ft.Container(height=50),
            ft.ResponsiveRow([
                ft.Column(col={"sm": 12, "md": 4}, controls=[
                    feature_card(
                        ft.Icons.WIFI_OFF_ROUNDED, 
                        "Offline-First Edge Node", 
                        "Keep learning without an internet connection. Nu-age caches your curriculum locally and automatically syncs to the FastAPI backend once connectivity is restored."
                    )
                ]),
                ft.Column(col={"sm": 12, "md": 4}, controls=[
                    feature_card(
                        ft.Icons.AUTO_AWESOME_MOTION_ROUNDED, 
                        "Automated Question Banks", 
                        "Powered by n8n workflow pipelines, exam data is dynamically extracted from PDFs to generate intelligent, randomized assessments on the fly."
                    )
                ]),
                ft.Column(col={"sm": 12, "md": 4}, controls=[
                    feature_card(
                        ft.Icons.SPEED_ROUNDED, 
                        "Lightweight Footprint", 
                        "Built with an optimized Flet/Flutter frontend. Nu-age delivers a premium, hardware-accelerated UX without the massive bloat of traditional web-wrapper platforms."
                    )
                ])
            ], spacing=30)
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    )

    # =========================================================
    # 4. FOOTER
    # =========================================================
    footer = ft.Container(
        padding=ft.padding.symmetric(horizontal=50, vertical=50),
        bgcolor=ft.Colors.BLACK87,
        content=ft.Row([
            ft.Row([
                ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=ft.Colors.WHITE, size=24),
                ft.Text("Nu-age.", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
            ]),
            ft.Text("© 2026 Project Nu-age. Designed for the Future.", color=ft.Colors.WHITE54),
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True)
    )

    # Assembly
    page.add(
        ft.Column([
            navbar,
            hero_section,
            features_section,
            footer
        ], spacing=0, scroll=ft.ScrollMode.AUTO)
    )

ft.app(target=main, view=ft.AppView.WEB_BROWSER)