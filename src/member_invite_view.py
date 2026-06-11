import flet as ft
import asyncio
from src.requests.organisations import process_invite_token

def member_invite_view(page: ft.Page, token: str):
    page.theme_mode = ft.ThemeMode.LIGHT
    
    # ── Design Token Palette ──────────────────────────────────────────────────
    PAGE_BG        = "#F4F6FA"
    CARD_BG        = ft.Colors.WHITE
    TEXT_MAIN      = "#111827"   # Near-black
    TEXT_MUTED     = "#6B7280"   # Neutral grey

    # ── State Assets ─────────────────────────────────────────────────────────
    status_ring = ft.ProgressRing(color=ft.Colors.PRIMARY, stroke_width=3, width=40, height=40)
    
    status_icon = ft.Icon(
        ft.Icons.MARK_EMAIL_READ_ROUNDED, 
        color=ft.Colors.PRIMARY, 
        size=44, 
        visible=False
    )
    
    status_title = ft.Text(
        "Processing Invitation", 
        size=20, 
        weight=ft.FontWeight.W_700, 
        color=TEXT_MAIN,
        text_align=ft.TextAlign.CENTER
    )
    
    status_subtitle = ft.Text(
        "Securing a safe connection to the platform...", 
        size=13, 
        color=TEXT_MUTED,
        text_align=ft.TextAlign.CENTER,
        width=float("inf")
    )

    # ── Asynchronous Lifecycle Engine ──────────────────────────────────────────
    # ── Asynchronous Lifecycle Engine ──────────────────────────────────────────
    async def process_invitation_lifecycle():
        await asyncio.sleep(1.0) # Brief animation buffer

        try:
            # ── 1. Hit the Backend via Helper Function ────────────────────────
            data = await process_invite_token(token)
            
            # Check if our helper function caught an error
            if "error" in data:
                raise Exception(data["error"])
                
            # ── Scenario A: User Exists and was added to Org ──────────────────
            if data.get("status") in ["success", "already_member"]:
                status_ring.visible = False
                status_icon.icon = ft.Icons.CHECK_CIRCLE_ROUNDED
                status_icon.color = ft.Colors.GREEN_600
                status_icon.visible = True
                
                status_title.value = "Joined Successfully!"
                status_subtitle.value = "Your account is linked to the organization. Redirecting to Login..."
                page.update()
                
                await asyncio.sleep(2.0)
                page.go("/login")
                
            # ── Scenario B: User Needs to Sign Up ─────────────────────────────
            elif data.get("status") == "needs_signup":
                status_ring.visible = False
                status_icon.icon = ft.Icons.GROUP_ADD_ROUNDED
                status_icon.color = ft.Colors.AMBER_600
                status_icon.visible = True
                
                status_title.value = "Account Required"
                status_subtitle.value = "Valid organization found! Let's get your profile set up..."
                page.update()
                
                await asyncio.sleep(2.0)
                
                # Pass the token into the signup route so the backend doesn't forget them
                page.go(f"/signup?invite_token={token}")

        except Exception as ex:
            # Fallback Error State UI
            status_ring.visible = False
            status_icon.icon = ft.Icons.GPP_BAD_ROUNDED
            status_icon.color = ft.Colors.RED_600
            status_icon.visible = True
            status_title.value = "Invitation Invalid"
            status_subtitle.value = f"The security token is broken or expired. Reason: {str(ex)}"
            page.update()
    # Trigger processing sequence safely in the background
    page.run_task(process_invitation_lifecycle)

    # ── Component Layout Construction ─────────────────────────────────────────
    invite_card = ft.Container(
        width=400,
        padding=ft.padding.symmetric(horizontal=32, vertical=40),
        bgcolor=CARD_BG,
        border_radius=20,
        alignment=ft.Alignment.CENTER,
        shadow=ft.BoxShadow(
            blur_radius=24,
            spread_radius=0,
            color=ft.Colors.with_opacity(0.08, ft.Colors.BLACK),
            offset=ft.Offset(0, 8),
        ),
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=16,
            tight=True,
            controls=[
                ft.Container(
                    content=ft.Stack([status_ring, status_icon], alignment=ft.Alignment.CENTER),
                    height=60,
                    alignment=ft.Alignment.CENTER
                ),
                status_title,
                status_subtitle,
            ]
        )
    )

    return ft.View(
        route=f"/accept-invite",
        bgcolor=PAGE_BG,
        vertical_alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        padding=ft.padding.all(16),
        controls=[invite_card]
    )