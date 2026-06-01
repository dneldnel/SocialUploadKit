from __future__ import annotations

from pathlib import Path
from typing import Any

from .base import BrowserLaunchOptions, PlaywrightLikeContext, find_system_chrome_executable


class PatchrightBrowserSession:
    def __init__(self, options: BrowserLaunchOptions | None = None):
        self.options = options or BrowserLaunchOptions()
        self._playwright: Any = None
        self._browser: Any = None

    async def __aenter__(self) -> "PatchrightBrowserSession":
        try:
            from patchright.async_api import async_playwright
        except ModuleNotFoundError as exc:
            raise RuntimeError("缺少 patchright：请先安装 `pip install patchright`。") from exc

        self._playwright = await async_playwright().start()
        launch_kwargs: dict[str, Any] = {"headless": self.options.headless}
        if self.options.slow_mo_ms is not None:
            launch_kwargs["slow_mo"] = self.options.slow_mo_ms

        executable = self.options.executable_path
        if not executable and self.options.use_system_chrome:
            executable = find_system_chrome_executable()
        if executable:
            launch_kwargs["executable_path"] = executable
        elif self.options.channel:
            launch_kwargs["channel"] = self.options.channel

        self._browser = await self._playwright.chromium.launch(**launch_kwargs)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def new_context(
        self,
        *,
        storage_state: str | Path | None = None,
        permissions: list[str] | None = None,
    ) -> PlaywrightLikeContext:
        kwargs: dict[str, Any] = {}
        if storage_state is not None:
            kwargs["storage_state"] = str(storage_state)
        if permissions:
            kwargs["permissions"] = permissions
        return PlaywrightLikeContext(await self._browser.new_context(**kwargs))
