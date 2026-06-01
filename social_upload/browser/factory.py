from __future__ import annotations

from .base import BrowserLaunchOptions, BrowserSession
from .cloakbrowser_adapter import CloakBrowserSession
from .patchright_adapter import PatchrightBrowserSession
from .playwright_adapter import PlaywrightBrowserSession
from .settings import normalize_social_browser


def build_browser_session(browser: str, options: BrowserLaunchOptions) -> BrowserSession:
    normalized = normalize_social_browser(browser)
    if normalized == "cloakbrowser":
        return CloakBrowserSession(options)
    if normalized == "patchright":
        return PatchrightBrowserSession(options)
    if normalized == "playwright":
        return PlaywrightBrowserSession(options)
    raise ValueError(f"不支持的 browser: {browser}")
