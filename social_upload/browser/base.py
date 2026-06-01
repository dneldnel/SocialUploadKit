from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, Sequence


@dataclass(slots=True)
class BrowserLaunchOptions:
    headless: bool = True
    use_system_chrome: bool = True
    channel: str = "chrome"
    executable_path: str | None = None
    slow_mo_ms: int | None = None
    profile_name: str | None = None


class BrowserLocator(Protocol):
    @property
    def first(self) -> "BrowserLocator": ...

    def nth(self, index: int) -> "BrowserLocator": ...
    def locator(self, selector: str) -> "BrowserLocator": ...
    async def click(self) -> None: ...
    async def fill(self, value: str) -> None: ...
    async def count(self) -> int: ...
    async def is_visible(self) -> bool: ...
    async def wait_for(self, *, state: str = "visible", timeout: int | None = None) -> None: ...
    async def get_attribute(self, name: str) -> str | None: ...
    async def set_input_files(self, files: str | Path | Sequence[str | Path]) -> None: ...


class BrowserPage(Protocol):
    @property
    def url(self) -> str: ...

    def locator(self, selector: str) -> BrowserLocator: ...
    def get_by_text(self, text: str, *, exact: bool = False) -> BrowserLocator: ...
    def get_by_role(self, role: str, *, name: str | None = None, exact: bool = False) -> BrowserLocator: ...
    async def goto(self, url: str) -> None: ...
    async def wait_for_url(self, url: str, *, timeout: int | None = None) -> None: ...
    async def wait_for_selector(self, selector: str, *, state: str | None = None, timeout: int | None = None) -> None: ...
    async def wait_for_timeout(self, timeout_ms: int) -> None: ...
    async def click(self, selector: str) -> None: ...
    async def press(self, key: str) -> None: ...
    async def type_text(self, text: str) -> None: ...
    async def screenshot(self, *, path: str | Path | None = None, full_page: bool = True) -> bytes | None: ...
    async def eval_on_selector(self, selector: str, expression: str) -> Any: ...


class BrowserContext(Protocol):
    async def new_page(self) -> BrowserPage: ...
    async def add_init_script(self, *, path: str | Path) -> None: ...
    async def storage_state(self, *, path: str | Path) -> None: ...
    async def close(self) -> None: ...


class BrowserSession(Protocol):
    async def __aenter__(self) -> "BrowserSession": ...
    async def __aexit__(self, exc_type, exc, tb) -> None: ...
    async def new_context(
        self,
        *,
        storage_state: str | Path | None = None,
        permissions: list[str] | None = None,
    ) -> BrowserContext: ...


def find_system_chrome_executable() -> str | None:
    """Return a local Chrome/Chromium executable if one is already installed."""
    env_keys = ("SOCIAL_UPLOAD_CHROME_PATH", "CHROME_PATH", "GOOGLE_CHROME_BIN")
    for key in env_keys:
        value = os.environ.get(key)
        if value and Path(value).expanduser().is_file():
            return str(Path(value).expanduser())

    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "C:/Program Files/Google/Chrome/Application/chrome.exe",
        "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    ]
    for candidate in candidates:
        if Path(candidate).is_file():
            return candidate
    return None


class PlaywrightLikeLocator:
    def __init__(self, locator: Any):
        self._locator = locator

    @property
    def first(self) -> "PlaywrightLikeLocator":
        return PlaywrightLikeLocator(self._locator.first)

    def nth(self, index: int) -> "PlaywrightLikeLocator":
        return PlaywrightLikeLocator(self._locator.nth(index))

    def locator(self, selector: str) -> "PlaywrightLikeLocator":
        return PlaywrightLikeLocator(self._locator.locator(selector))

    async def click(self) -> None:
        await self._locator.click()

    async def fill(self, value: str) -> None:
        await self._locator.fill(value)

    async def count(self) -> int:
        return await self._locator.count()

    async def is_visible(self) -> bool:
        try:
            return await self._locator.is_visible()
        except Exception:
            return False

    async def wait_for(self, *, state: str = "visible", timeout: int | None = None) -> None:
        kwargs = {"state": state}
        if timeout is not None:
            kwargs["timeout"] = timeout
        await self._locator.wait_for(**kwargs)

    async def get_attribute(self, name: str) -> str | None:
        return await self._locator.get_attribute(name)

    async def set_input_files(self, files: str | Path | Sequence[str | Path]) -> None:
        if isinstance(files, (str, Path)):
            payload: str | list[str] = str(files)
        else:
            payload = [str(item) for item in files]
        await self._locator.set_input_files(payload)


class PlaywrightLikePage:
    def __init__(self, page: Any):
        self._page = page

    @property
    def url(self) -> str:
        return self._page.url

    def locator(self, selector: str) -> PlaywrightLikeLocator:
        return PlaywrightLikeLocator(self._page.locator(selector))

    def get_by_text(self, text: str, *, exact: bool = False) -> PlaywrightLikeLocator:
        return PlaywrightLikeLocator(self._page.get_by_text(text, exact=exact))

    def get_by_role(self, role: str, *, name: str | None = None, exact: bool = False) -> PlaywrightLikeLocator:
        kwargs: dict[str, Any] = {"exact": exact}
        if name is not None:
            kwargs["name"] = name
        return PlaywrightLikeLocator(self._page.get_by_role(role, **kwargs))

    async def goto(self, url: str) -> None:
        await self._page.goto(url, wait_until="domcontentloaded", timeout=60000)

    async def wait_for_url(self, url: str, *, timeout: int | None = None) -> None:
        kwargs = {}
        if timeout is not None:
            kwargs["timeout"] = timeout
        await self._page.wait_for_url(url, **kwargs)

    async def wait_for_selector(self, selector: str, *, state: str | None = None, timeout: int | None = None) -> None:
        kwargs: dict[str, Any] = {}
        if state is not None:
            kwargs["state"] = state
        if timeout is not None:
            kwargs["timeout"] = timeout
        await self._page.wait_for_selector(selector, **kwargs)

    async def wait_for_timeout(self, timeout_ms: int) -> None:
        await self._page.wait_for_timeout(timeout_ms)

    async def click(self, selector: str) -> None:
        await self._page.click(selector)

    async def press(self, key: str) -> None:
        await self._page.keyboard.press(key)

    async def type_text(self, text: str) -> None:
        await self._page.keyboard.type(text)

    async def screenshot(self, *, path: str | Path | None = None, full_page: bool = True) -> bytes | None:
        kwargs: dict[str, Any] = {"full_page": full_page}
        if path is not None:
            kwargs["path"] = str(path)
        return await self._page.screenshot(**kwargs)

    async def eval_on_selector(self, selector: str, expression: str) -> Any:
        return await self._page.eval_on_selector(selector, expression)


class PlaywrightLikeContext:
    def __init__(self, context: Any):
        self._context = context

    async def new_page(self) -> PlaywrightLikePage:
        return PlaywrightLikePage(await self._context.new_page())

    async def add_init_script(self, *, path: str | Path) -> None:
        await self._context.add_init_script(path=str(path))

    async def storage_state(self, *, path: str | Path) -> None:
        await self._context.storage_state(path=str(path))

    async def close(self) -> None:
        await self._context.close()
