from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .base import BrowserLaunchOptions, PlaywrightLikeContext
from .settings import (
    cloakbrowser_predownload_command,
    configure_cloakbrowser_environment,
    get_cloakbrowser_locale,
    get_cloakbrowser_profile_dir,
    get_cloakbrowser_timezone,
    stable_fingerprint_seed,
    use_cloakbrowser_persistent_profiles,
)


class CloakBrowserSession:
    def __init__(self, options: BrowserLaunchOptions | None = None):
        self.options = options or BrowserLaunchOptions()
        self._browser: Any = None
        self._context: Any = None
        self._launch_async: Any = None
        self._launch_persistent_context_async: Any = None

    async def __aenter__(self) -> "CloakBrowserSession":
        cache_dir = configure_cloakbrowser_environment()
        try:
            from cloakbrowser import binary_info, launch_async, launch_persistent_context_async
        except ModuleNotFoundError as exc:
            raise RuntimeError("缺少 cloakbrowser：请先安装 `pip install cloakbrowser`。") from exc

        info = binary_info()
        if not info.get("installed"):
            raise RuntimeError(
                "CloakBrowser 二进制尚未预下载。为避免运行中卡顿，请先执行："
                f"{cloakbrowser_predownload_command()}；当前项目缓存目录：{cache_dir}"
            )

        self._launch_async = launch_async
        self._launch_persistent_context_async = launch_persistent_context_async
        if not self._use_persistent_context:
            self._browser = await launch_async(**self._launch_kwargs())
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass

    @property
    def _use_persistent_context(self) -> bool:
        return bool(self.options.profile_name and use_cloakbrowser_persistent_profiles())

    def _launch_kwargs(self) -> dict[str, Any]:
        seed = stable_fingerprint_seed(self.options.profile_name)
        kwargs: dict[str, Any] = {
            "headless": self.options.headless,
            "humanize": True,
            "human_preset": "careful",
            "args": [f"--fingerprint={seed}"],
            "timezone": get_cloakbrowser_timezone(),
            "locale": get_cloakbrowser_locale(),
        }
        if self.options.slow_mo_ms is not None:
            kwargs["slow_mo"] = self.options.slow_mo_ms
        return kwargs

    async def _hydrate_cookies(self, context: Any, storage_state: str | Path | None) -> None:
        if not storage_state:
            return
        path = Path(storage_state)
        if not path.is_file():
            return
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            cookies = state.get("cookies") or []
            if cookies:
                await context.add_cookies(cookies)
        except Exception:
            return

    async def new_context(
        self,
        *,
        storage_state: str | Path | None = None,
        permissions: list[str] | None = None,
    ) -> PlaywrightLikeContext:
        if self._use_persistent_context:
            if self._context is None:
                profile_dir = get_cloakbrowser_profile_dir(self.options.profile_name)
                profile_dir.mkdir(parents=True, exist_ok=True)
                self._context = await self._launch_persistent_context_async(
                    user_data_dir=profile_dir,
                    **self._launch_kwargs(),
                )
                await self._hydrate_cookies(self._context, storage_state)
                if permissions:
                    await self._context.grant_permissions(permissions)
            return PlaywrightLikeContext(self._context)

        kwargs: dict[str, Any] = {}
        if storage_state is not None:
            kwargs["storage_state"] = str(storage_state)
        if permissions:
            kwargs["permissions"] = permissions
        return PlaywrightLikeContext(await self._browser.new_context(**kwargs))
