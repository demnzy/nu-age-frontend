"""
Web security & COEP Patch for Flet Web.
Mitigates Cross-Origin Resource Policy (CORP) / CORS blocks for third-party media
such as Bunny CDN, external HLS, and remote video streams on web browsers.

Why this is required:
By default, Flet Web injects:
    Cross-Origin-Opener-Policy: same-origin
    Cross-Origin-Embedder-Policy: require-corp
    Access-Control-Allow-Origin: *

Under 'require-corp', Chromium/Firefox/Safari strictly forbid loading cross-origin
media (including HTML5 <video> / Bunny CDN *.b-cdn.net) unless the CDN explicitly sends
the response header 'Cross-Origin-Resource-Policy: cross-origin'.

Patching COEP to 'credentialless' preserves WebAssembly and CanvasKit cross-origin isolation
(for SharedArrayBuffer) while allowing the browser to load cross-origin media like Bunny CDN
without requiring the remote CDN to configure CORP headers.
"""

import logging
import sys

logger = logging.getLogger("flet_web_patch")
_IS_PATCHED = False


def patch_flet_web_coep() -> bool:
    """
    Patches Flet Web's internal FastAPI generator to use
    'Cross-Origin-Embedder-Policy: credentialless' instead of 'require-corp'.
    Safe to call across all platforms (Desktop, Web, Server).
    """
    global _IS_PATCHED
    if _IS_PATCHED:
        return True

    try:
        import flet_web.fastapi

        # 1. Access the real module behind flet_web.fastapi.app
        app_mod = sys.modules.get("flet_web.fastapi.app")
        if not app_mod or not hasattr(app_mod, "app"):
            return False

        orig_app = app_mod.app

        def patched_flet_fastapi_app(*args, **kwargs):
            sub_app = orig_app(*args, **kwargs)
            for m in getattr(sub_app, "user_middleware", []):
                cls = getattr(m, "cls", None)
                if cls and getattr(cls, "__name__", "") == "CustomHeadersMiddleware":
                    orig_dispatch = cls.dispatch

                    async def patched_dispatch(self, request, call_next):
                        response = await orig_dispatch(self, request, call_next)
                        if "Cross-Origin-Embedder-Policy" in response.headers:
                            response.headers["Cross-Origin-Embedder-Policy"] = "credentialless"
                        return response

                    cls.dispatch = patched_dispatch
            return sub_app

        # Apply patch to module references
        app_mod.app = patched_flet_fastapi_app
        flet_web.fastapi.app = patched_flet_fastapi_app

        if "flet.fastapi" in sys.modules:
            sys.modules["flet.fastapi"].app = patched_flet_fastapi_app

        _IS_PATCHED = True
        logger.info("[COEP Patch] Successfully patched Flet Web COEP header to 'credentialless'")
        return True

    except Exception as ex:
        # Non-fatal if flet_web is not installed (e.g. native desktop only)
        logger.debug("[COEP Patch] Skipped patching (flet_web unavailable): %s", ex)
        return False
