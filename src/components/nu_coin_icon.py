from typing import Optional
import flet as ft


def nu_coin_icon(size: float = 16, tooltip: Optional[str] = "Nu-Coins") -> ft.Image:
    """Returns a standardized high-fidelity Greek letter Nu (ν) coin icon.

    Uses `assets/nu_coin.svg` with raised 3D struck metallic gold bevels,
    micro-milled reeded rim, and Nu-Age emerald branding accents.
    """
    return ft.Image(
        src="nu_coin.svg",
        width=size,
        height=size,
        fit=ft.BoxFit.CONTAIN,
        tooltip=tooltip,
    )
