"""
Adaptive Video Player for Nu-Age LMS.
Provides a unified video renderer supporting local videos, remote MP4/HLS streams,
and YouTube URLs across Web, Mobile, and Desktop platforms.

Features:
- Standard video files: Native playback via flet_video (libmpv).
- YouTube links on Web / Mobile: Embedded iframe via flet_webview (when supported).
- YouTube links on Windows Desktop: Asynchronous stream URL extraction via yt-dlp.
- Resilient Fallback: Cinema Card with high-res YouTube poster, pulsing play action,
  open in browser/app, and instant progress synchronization.
"""

import asyncio
import logging
import sys
from typing import Optional, Callable, Dict, Any

import flet as ft
import flet_video as ftv
from flet_video import Video, VideoMedia

from src.utils.youtube import (
    is_youtube_url,
    extract_youtube_id,
    get_youtube_embed_url,
    get_youtube_thumbnail_url,
    resolve_youtube_stream_url_async,
    is_network_available_async,
)

logger = logging.getLogger(__name__)


class AdaptiveVideoPlayer(ft.Container):
    """
    Highly adaptive video container that intelligently switches between:
    1. Native libmpv player (flet_video) for direct files/streams and extracted YouTube streams.
    2. WebView iframe embed on supported web/mobile environments.
    3. High-fidelity YouTube Cinema Card fallback for external streaming and resilient playback.
    """

    def __init__(
        self,
        media_url: str,
        title: str = "Lesson Video",
        autoplay: bool = False,
        aspect_ratio: float = 16 / 9,
        border_radius: int = 12,
        on_error: Optional[Callable] = None,
        on_load: Optional[Callable] = None,
        on_complete: Optional[Callable] = None,
        custom_controls: Optional[Any] = None,
        expand: bool = True,
        **kwargs,
    ):
        self.media_url = str(media_url or "").strip()
        self.title = title or "Lesson Video"
        self.autoplay = autoplay
        self.player_aspect_ratio = aspect_ratio
        self.on_error_callback = on_error
        self.on_load_callback = on_load
        self.on_complete_callback = on_complete
        self.custom_controls = custom_controls

        self._is_youtube = is_youtube_url(self.media_url)
        self._video_id = extract_youtube_id(self.media_url) if self._is_youtube else None
        self._stream_info: Optional[Dict[str, Any]] = None
        self._resolution_attempted = False
        self._player_control: Optional[Video] = None

        # Base container properties
        super().__init__(
            aspect_ratio=aspect_ratio,
            border_radius=ft.BorderRadius.all(border_radius),
            bgcolor="#0A0C10",
            border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            shadow=ft.BoxShadow(
                blur_radius=18,
                color=ft.Colors.with_opacity(0.28, ft.Colors.BLACK),
                offset=ft.Offset(0, 5),
            ),
            expand=expand,
            **kwargs,
        )

        if not self.media_url:
            self.content = self._build_empty_placeholder()
        elif not self._is_youtube:
            # Standard video media - directly initialize native Video
            self.content = self._build_native_player(self.media_url)
        else:
            # YouTube media - initial loading state while resolving stream
            self.content = self._build_youtube_loading_ui()

    def _get_page(self) -> Optional[ft.Page]:
        try:
            return self.page
        except Exception:
            return None

    def did_mount(self):
        super().did_mount()
        if self._is_youtube and not self._resolution_attempted:
            self._resolution_attempted = True
            current_page = self._get_page()
            if current_page:
                current_page.run_task(self._resolve_and_mount)
            else:
                try:
                    asyncio.create_task(self._resolve_and_mount())
                except Exception as e:
                    logger.warning("Could not schedule async stream resolution: %s", e)
                    self._mount_cinema_card()

    async def _resolve_and_mount(self):
        """Resolves YouTube stream or mounts platform-appropriate player."""
        current_page = self._get_page()
        is_web = getattr(current_page, "web", False) if current_page else False
        platform = getattr(current_page, "platform", None) if current_page else None
        platform_str = str(platform or "").lower()
        is_mobile = (
            platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS, getattr(ft.PagePlatform, "ANDROID_TV", None))
            or any(m in platform_str for m in ("android", "ios"))
        ) if platform else False
        is_windows = (
            (platform == ft.PagePlatform.WINDOWS)
            or sys.platform == "win32"
        ) and not is_web

        # 1. Web Client:
        # Avoid CanvasKit COEP cross-origin iframe rejection by rendering the
        # high-fidelity YouTube Cinema Card directly with instant launch support.
        if is_web:
            logger.info("Web client detected; mounting YouTube Cinema Card for %s", self._video_id)
            self._mount_cinema_card()
            if self.on_load_callback:
                self.on_load_callback(None)
            return

        # 2. Check Network Connectivity (Desktop & Mobile)
        try:
            is_online = await is_network_available_async(timeout=1.2)
        except Exception:
            is_online = True

        if not is_online:
            logger.info("Device is offline; mounting offline learning card for %s", self._video_id)
            self._mount_offline_card()
            return

        # 3. Mobile (Android / iOS): Native In-App WebView Player
        # On Android and iOS, embed YouTube directly inside the app using flet_webview.
        # This provides seamless in-app playback, touch controls, HD quality, fullscreen,
        # closed captions, and scrubbing without external redirects or yt-dlp dependencies.
        if is_mobile:
            try:
                from flet_webview import WebView, JavaScriptMode  # noqa: F401
                embed_url = get_youtube_embed_url(self._video_id, autoplay=self.autoplay)
                logger.info("Mobile platform detected (%s); mounting native in-app WebView player for %s", platform, self._video_id)
                
                # Mount WebView first so WebViewController is attached to the page
                webview = self._build_webview_player(embed_url=None)
                self.content = ft.Container(
                    content=webview,
                    expand=True,
                    bgcolor="#000000",
                    border_radius=self.border_radius,
                    clip_behavior=ft.ClipBehavior.HARD_EDGE,
                )
                self.update()

                # Explicitly enable unrestricted JavaScript execution before loading the YouTube page
                try:
                    await webview.set_javascript_mode(JavaScriptMode.UNRESTRICTED)
                    logger.info("Successfully set WebView JavaScriptMode to UNRESTRICTED")
                except Exception as js_ex:
                    logger.warning("Could not set JavaScriptMode on WebView: %s", js_ex)

                # Now load the YouTube embed request with JavaScript mode safely enabled
                try:
                    await webview.load_request(embed_url)
                    webview.url = embed_url
                except Exception as load_ex:
                    logger.warning("load_request failed (%s); updating url directly on WebView", load_ex)
                    webview.url = embed_url
                    try:
                        webview.update()
                    except Exception:
                        pass

                if self.on_load_callback:
                    self.on_load_callback(None)
                return
            except Exception as ex:
                logger.warning("Mobile WebView player initialization failed for %s: %s", self.media_url, ex)

        # 4. Progressive Stream URL Extraction via yt-dlp (Desktop)
        # Attempt progressive stream URL extraction on Desktop platforms.
        # This provides hardware-accelerated, native media playback via flet_video without
        # WebView JavaScript restrictions, COEP blocks, or embedded player errors.
        try:
            stream_info = await resolve_youtube_stream_url_async(self.media_url)
            if stream_info and stream_info.get("stream_url"):
                self._stream_info = stream_info
                direct_url = stream_info["stream_url"]
                headers = stream_info.get("http_headers") or {}
                if stream_info.get("title") and self.title in ("Lesson Video", ""):
                    self.title = stream_info["title"]
                logger.info("Successfully resolved YouTube stream for %s", self._video_id)
                self.content = self._build_native_player(direct_url, http_headers=headers)
                self.update()
                if self.on_load_callback:
                    self.on_load_callback(None)
                return
        except Exception as ex:
            logger.warning("Failed yt-dlp resolution for %s: %s", self.media_url, ex)

        # 5. Resilient Fallback to High-Fidelity Cinema Card
        # If stream extraction is unavailable (restricted/private/DRM), mount the Cinema Card
        # which lets the learner launch the video in YouTube app or browser with zero errors.
        logger.info("Stream extraction unavailable for %s; mounting Cinema Card.", self._video_id)
        self._mount_cinema_card()

    def _mount_cinema_card(self):
        """Mounts the YouTube Cinema Card."""
        self.content = self._build_cinema_card()
        try:
            self.update()
        except Exception:
            pass

    def _mount_offline_card(self):
        """Mounts the Offline Learning Card."""
        self.content = self._build_offline_card()
        try:
            self.update()
        except Exception:
            pass

    def _build_offline_card(self) -> ft.Container:
        """
        Displays an informative, beautifully styled Offline Learning Card
        when studying offline on desktop or mobile.
        """
        async def _handle_retry(e):
            self.content = self._build_youtube_loading_ui()
            self.update()
            if self.page:
                self.page.run_task(self._resolve_and_mount)
            else:
                try:
                    asyncio.create_task(self._resolve_and_mount())
                except Exception:
                    self._mount_offline_card()

        top_bar = ft.Container(
            padding=ft.Padding.only(left=12, top=10, right=12),
            content=ft.Row(
                [
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(ft.Icons.WIFI_OFF_ROUNDED, size=14, color=ft.Colors.AMBER_400),
                                ft.Text("Offline", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_400),
                            ],
                            spacing=5,
                            tight=True,
                        ),
                        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                        border_radius=ft.BorderRadius.all(20),
                        bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.AMBER_400),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.30, ft.Colors.AMBER_400)),
                    ),
                ],
                alignment=ft.MainAxisAlignment.START,
                wrap=True,
            ),
        )

        center_content = ft.Column(
            [
                ft.Container(
                    content=ft.Icon(ft.Icons.SIGNAL_WIFI_OFF_ROUNDED, size=36, color=ft.Colors.AMBER_400),
                    width=60,
                    height=60,
                    border_radius=ft.BorderRadius.all(30),
                    bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.AMBER_400),
                    alignment=ft.Alignment.CENTER,
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.25, ft.Colors.AMBER_400)),
                ),
                ft.Container(height=2),
                ft.Text(
                    self.title or "Video Lesson",
                    size=14,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.WHITE,
                    text_align=ft.TextAlign.CENTER,
                    max_lines=2,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                ft.Text(
                    "Requires internet connection.",
                    size=11,
                    color=ft.Colors.WHITE70,
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=4,
        )

        action_buttons = [
            ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.REFRESH_ROUNDED, size=13, color=ft.Colors.WHITE),
                        ft.Text("Retry", size=11, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE),
                    ],
                    tight=True,
                    spacing=5,
                ),
                padding=ft.Padding.symmetric(horizontal=12, vertical=7),
                border_radius=ft.BorderRadius.all(8),
                bgcolor=ft.Colors.with_opacity(0.20, ft.Colors.WHITE),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.20, ft.Colors.WHITE)),
                ink=True,
                on_click=_handle_retry,
            ),
        ]

        if self.on_complete_callback:
            action_buttons.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, size=13, color=ft.Colors.GREEN_ACCENT_200),
                            ft.Text("Mark Complete", size=11, weight=ft.FontWeight.W_600, color=ft.Colors.GREEN_ACCENT_200),
                        ],
                        tight=True,
                        spacing=5,
                    ),
                    padding=ft.Padding.symmetric(horizontal=12, vertical=7),
                    border_radius=ft.BorderRadius.all(8),
                    bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.GREEN_ACCENT_700),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.GREEN_ACCENT_400)),
                    ink=True,
                    on_click=self._handle_mark_complete,
                )
            )

        bottom_bar = ft.Container(
            padding=ft.Padding.only(left=12, right=12, bottom=10),
            content=ft.Row(
                action_buttons,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
                wrap=True,
                run_spacing=6,
            ),
        )

        return ft.Container(
            expand=True,
            bgcolor="#0A0C10",
            content=ft.Column(
                [
                    top_bar,
                    ft.Container(expand=True, content=center_content),
                    bottom_bar,
                ],
                expand=True,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
        )

    def _build_native_player(
        self,
        media_source: str,
        http_headers: Optional[Dict[str, str]] = None,
    ) -> Video:
        """Constructs a native flet_video.Video player."""
        def _handle_error(e):
            logger.warning("Video playback error for %s: %s", media_source, getattr(e, "data", e))
            if self._is_youtube:
                # If YouTube stream expired or failed during playback, fallback to Cinema Card
                self._mount_cinema_card()
            if self.on_error_callback:
                self.on_error_callback(e)

        def _handle_load(e):
            if self.on_load_callback:
                self.on_load_callback(e)

        controls_scheme = self.custom_controls
        if controls_scheme is None:
            current_page = self._get_page()
            is_mobile = (getattr(current_page, "platform", None) in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS)) if current_page else False
            if is_mobile:
                controls_scheme = ftv.AdaptiveVideoControls()
            else:
                controls_scheme = ftv.MaterialDesktopVideoControls(
                    visible_on_mount=True,
                    display_seek_bar=True,
                    play_and_pause_on_tap=True,
                    modify_volume_on_scroll=True,
                    toggle_fullscreen_on_double_press=True,
                )

        media = (
            VideoMedia(media_source, http_headers=http_headers)
            if http_headers
            else VideoMedia(media_source)
        )

        self._player_control = Video(
            expand=True,
            playlist=[media],
            autoplay=self.autoplay,
            volume=100,
            on_error=_handle_error,
            on_load=_handle_load,
            controls=controls_scheme,
        )
        return self._player_control

    def _build_webview_player(self, embed_url: Optional[str] = None) -> Any:
        """Constructs an in-app native WebView player for YouTube embeds."""
        from flet_webview import WebView

        def _on_web_error(e):
            logger.warning("WebView playback error for %s: %s", self.media_url, getattr(e, "data", e))
            if self.on_error_callback:
                self.on_error_callback(e)

        def _on_console(e):
            logger.debug("WebView console: %s", getattr(e, "message", e))

        return WebView(
            url=embed_url,
            expand=True,
            bgcolor="#000000",
            on_web_resource_error=_on_web_error,
            on_console_message=_on_console,
        )

    def _build_empty_placeholder(self) -> ft.Container:
        """Fallback for empty media URL."""
        return ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.VIDEOCAM_OFF_ROUNDED, size=44, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text("No video source provided", size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
            ),
        )

    def _build_youtube_loading_ui(self) -> ft.Stack:
        """Displays poster thumbnail with loading spinner while yt-dlp resolves stream."""
        thumbnail_url = get_youtube_thumbnail_url(self._video_id, quality="hq") if self._video_id else ""

        poster_layer = ft.Container(
            left=0,
            top=0,
            right=0,
            bottom=0,
            content=ft.Image(
                src=thumbnail_url,
                fit=ft.BoxFit.COVER,
                opacity=0.25,
            ) if thumbnail_url else None,
        )

        spinner_layer = ft.Container(
            left=0,
            top=0,
            right=0,
            bottom=0,
            alignment=ft.Alignment.CENTER,
            padding=20,
            content=ft.Column(
                [
                    ft.ProgressRing(width=36, height=36, stroke_width=3.2, color=ft.Colors.RED_400),
                    ft.Text(
                        "Connecting to YouTube stream...",
                        size=14,
                        weight=ft.FontWeight.W_600,
                        color=ft.Colors.WHITE,
                    ),
                    ft.Text(
                        "Optimizing high-definition playback",
                        size=12,
                        color=ft.Colors.WHITE60,
                    ),
                    ft.Container(height=4),
                    ft.TextButton(
                        content=ft.Row(
                            [
                                ft.Text("Watch directly on YouTube", size=12, color=ft.Colors.RED_ACCENT_100),
                                ft.Icon(ft.Icons.OPEN_IN_NEW_ROUNDED, size=13, color=ft.Colors.RED_ACCENT_100),
                            ],
                            tight=True,
                            spacing=6,
                        ),
                        on_click=self._handle_open_youtube,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
            ),
        )

        return ft.Stack([poster_layer, spinner_layer], expand=True)

    def _build_cinema_card(self) -> ft.Stack:
        """
        Sleek, high-production YouTube Cinema Card.
        Displays high-res thumbnail, dark cinematic gradient, play button,
        and external launcher button.
        """
        thumbnail_url = get_youtube_thumbnail_url(self._video_id, quality="maxres") if self._video_id else ""
        fallback_thumb = get_youtube_thumbnail_url(self._video_id, quality="hq") if self._video_id else ""

        # Background poster
        poster_image = ft.Container(
            left=0,
            top=0,
            right=0,
            bottom=0,
            content=ft.Image(
                src=thumbnail_url,
                error_content=ft.Image(src=fallback_thumb, fit=ft.BoxFit.COVER),
                fit=ft.BoxFit.COVER,
            ),
        )

        # Gradient overlay for contrast and sleek cinematic feel
        gradient_overlay = ft.Container(
            left=0,
            top=0,
            right=0,
            bottom=0,
            gradient=ft.LinearGradient(
                begin=ft.Alignment.TOP_CENTER,
                end=ft.Alignment.BOTTOM_CENTER,
                colors=[
                    ft.Colors.with_opacity(0.60, "#08090C"),
                    ft.Colors.with_opacity(0.40, "#08090C"),
                    ft.Colors.with_opacity(0.88, "#08090C"),
                ],
                stops=[0.0, 0.45, 1.0],
            ),
        )

        # Top badges
        top_bar = ft.Container(
            padding=ft.Padding.only(left=12, top=10, right=12),
            content=ft.Row(
                [
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(ft.Icons.PLAY_CIRCLE_FILLED_ROUNDED, size=14, color=ft.Colors.RED_ACCENT_400),
                                ft.Text("YouTube", size=10, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                            ],
                            spacing=5,
                            tight=True,
                        ),
                        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                        border_radius=ft.BorderRadius.all(20),
                        bgcolor=ft.Colors.with_opacity(0.50, ft.Colors.BLACK),
                        border=ft.Border.all(1, ft.Colors.with_opacity(0.25, ft.Colors.RED_ACCENT_400)),
                    ),
                    ft.Container(
                        content=ft.Text("HD", size=10, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE70),
                        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
                        border_radius=ft.BorderRadius.all(6),
                        bgcolor=ft.Colors.with_opacity(0.40, ft.Colors.BLACK),
                    ),
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
        )

        # Center Hero Play Action
        center_action = ft.Container(
            alignment=ft.Alignment.CENTER,
            content=ft.Column(
                [
                    ft.Container(
                        content=ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, size=38, color=ft.Colors.WHITE),
                        width=68,
                        height=68,
                        border_radius=ft.BorderRadius.all(34),
                        bgcolor=ft.Colors.RED_600,
                        alignment=ft.Alignment.CENTER,
                        shadow=ft.BoxShadow(
                            blur_radius=22,
                            color=ft.Colors.with_opacity(0.55, ft.Colors.RED_ACCENT_400),
                            offset=ft.Offset(0, 4),
                        ),
                        ink=True,
                        on_click=self._handle_open_youtube,
                        tooltip="Watch on YouTube",
                    ),
                    ft.Container(height=6),
                    ft.Text(
                        self.title,
                        size=15,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.WHITE,
                        text_align=ft.TextAlign.CENTER,
                        max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Text(
                        "Click to watch stream on YouTube",
                        size=12,
                        color=ft.Colors.WHITE70,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=4,
            ),
        )

        # Bottom Bar: controls & status
        action_buttons = [
            ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.OPEN_IN_NEW_ROUNDED, size=13, color=ft.Colors.WHITE),
                        ft.Text("Watch on YouTube", size=11, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE),
                    ],
                    tight=True,
                    spacing=5,
                ),
                padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                border_radius=ft.BorderRadius.all(8),
                bgcolor=ft.Colors.with_opacity(0.35, ft.Colors.WHITE),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.20, ft.Colors.WHITE)),
                ink=True,
                on_click=self._handle_open_youtube,
            ),
        ]

        if self.on_complete_callback:
            action_buttons.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, size=13, color=ft.Colors.GREEN_ACCENT_200),
                            ft.Text("Mark Watched", size=11, weight=ft.FontWeight.W_600, color=ft.Colors.GREEN_ACCENT_200),
                        ],
                        tight=True,
                        spacing=5,
                    ),
                    padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                    border_radius=ft.BorderRadius.all(8),
                    bgcolor=ft.Colors.with_opacity(0.20, ft.Colors.GREEN_ACCENT_700),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.35, ft.Colors.GREEN_ACCENT_400)),
                    ink=True,
                    on_click=self._handle_mark_complete,
                )
            )

        bottom_bar = ft.Container(
            padding=ft.Padding.only(left=12, right=12, bottom=10),
            content=ft.Row(
                action_buttons,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
                wrap=True,
                run_spacing=6,
            ),
        )

        card_layout = ft.Container(
            left=0,
            top=0,
            right=0,
            bottom=0,
            content=ft.Column(
                [
                    top_bar,
                    ft.Container(expand=True, content=center_action),
                    bottom_bar,
                ],
                expand=True,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
        )

        return ft.Stack(
            [
                poster_image,
                gradient_overlay,
                card_layout,
            ],
            expand=True,
        )

    async def _handle_open_youtube(self, e):
        """Launches the YouTube link in browser or external YouTube app."""
        target_url = self.media_url
        try:
            current_page = (e and getattr(e, "page", None)) or self._get_page()
            if current_page:
                await current_page.launch_url(target_url)
        except Exception as ex:
            logger.error("Failed to launch YouTube URL %s: %s", target_url, ex)

    def _handle_mark_complete(self, e):
        """Triggers the optional completion callback."""
        if self.on_complete_callback:
            try:
                self.on_complete_callback(e)
            except Exception as ex:
                logger.error("Error in on_complete callback: %s", ex)
