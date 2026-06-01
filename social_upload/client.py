from __future__ import annotations

from dataclasses import dataclass, field
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Coroutine

from social_upload.browser.settings import DEFAULT_SOCIAL_BROWSER, get_social_browser
from social_upload.platforms.douyin.login import check_douyin_cookie, login_douyin
from social_upload.platforms.douyin.models import (
    DouyinVideoUploadRequest,
    DouyinVisibility,
    UploadMode as DouyinUploadMode,
    UploadResult as DouyinUploadResult,
    UploadStatusEvent as DouyinUploadStatusEvent,
)
from social_upload.platforms.douyin.workflow import DouyinVideoUploadWorkflow
from social_upload.platforms.xhs.login import check_xhs_cookie, login_xhs
from social_upload.platforms.xhs.models import (
    UploadMode as XhsUploadMode,
    UploadResult as XhsUploadResult,
    UploadStatusEvent as XhsUploadStatusEvent,
    XhsVideoUploadRequest,
)
from social_upload.platforms.xhs.workflow import XhsUploadWorkflow
from social_upload.storage import CookieStorage, normalize_platform

StatusEvent = DouyinUploadStatusEvent | XhsUploadStatusEvent
StatusCallback = Callable[[StatusEvent], Coroutine[Any, Any, None] | None]
UploadResult = DouyinUploadResult | XhsUploadResult


@dataclass(slots=True)
class BrowserConfig:
    browser: str = DEFAULT_SOCIAL_BROWSER
    headless: bool = True
    use_system_chrome: bool = True
    executable_path: str | None = None


@dataclass(slots=True)
class UploadVideoInput:
    platform: str
    account_name: str
    video_file: Path | str
    title: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    mode: str = "draft"
    publish_at: datetime | None = None
    thumbnail_file: Path | str | None = None
    visibility: str = "public"
    product_link: str = ""
    product_title: str = ""
    keep_open_seconds: int = 0
    dry_run: bool = False
    debug: bool = False
    browser: str | None = None
    headless: bool | None = None
    use_system_chrome: bool | None = None
    executable_path: str | None = None


class AccountManager:
    def __init__(self, storage: CookieStorage, browser_config: BrowserConfig):
        self.storage = storage
        self.browser_config = browser_config

    def account_file(self, platform: str, account_name: str) -> Path:
        return self.storage.account_file(platform, account_name)

    def list(self, platform: str) -> list[str]:
        return self.storage.list_accounts(platform)

    def delete(self, platform: str, account_name: str) -> bool:
        return self.storage.delete_account(platform, account_name)

    async def login(
        self,
        platform: str,
        account_name: str,
        *,
        browser: str | None = None,
        headless: bool | None = None,
        use_system_chrome: bool | None = None,
        executable_path: str | None = None,
        on_event: StatusCallback | None = None,
    ) -> dict[str, Any]:
        platform = normalize_platform(platform)
        account_file = self.account_file(platform, account_name)
        kwargs = self._browser_kwargs(browser, headless, use_system_chrome, executable_path)
        if platform == "douyin":
            return await login_douyin(account_file, on_event=on_event, **kwargs)
        return await login_xhs(account_file, on_event=on_event, **kwargs)

    async def check(
        self,
        platform: str,
        account_name: str,
        *,
        browser: str | None = None,
        headless: bool | None = None,
        use_system_chrome: bool | None = None,
        executable_path: str | None = None,
    ) -> bool:
        platform = normalize_platform(platform)
        account_file = self.account_file(platform, account_name)
        kwargs = self._browser_kwargs(browser, headless, use_system_chrome, executable_path)
        kwargs["headless"] = True if headless is None else headless
        if platform == "douyin":
            return await check_douyin_cookie(account_file, **kwargs)
        return await check_xhs_cookie(account_file, **kwargs)

    def _browser_kwargs(
        self,
        browser: str | None,
        headless: bool | None,
        use_system_chrome: bool | None,
        executable_path: str | None,
    ) -> dict[str, Any]:
        return {
            "browser": get_social_browser(browser or self.browser_config.browser),
            "headless": self.browser_config.headless if headless is None else headless,
            "use_system_chrome": self.browser_config.use_system_chrome if use_system_chrome is None else use_system_chrome,
            "executable_path": executable_path or self.browser_config.executable_path,
        }


class SocialUploadClient:
    """Project-independent API for Douyin/XHS login, cookie checks and video upload."""

    def __init__(
        self,
        *,
        storage_dir: Path | str = ".social_upload",
        browser: str = DEFAULT_SOCIAL_BROWSER,
        headless: bool = True,
        use_system_chrome: bool = True,
        executable_path: str | None = None,
    ):
        self.storage = CookieStorage(storage_dir)
        self._configure_browser_runtime_env()
        self.browser_config = BrowserConfig(
            browser=browser,
            headless=headless,
            use_system_chrome=use_system_chrome,
            executable_path=executable_path,
        )
        self.accounts = AccountManager(self.storage, self.browser_config)

    def _configure_browser_runtime_env(self) -> None:
        os.environ["SOCIAL_UPLOAD_CLOAKBROWSER_CACHE_DIR"] = str(self.storage.runtime_dir / "cloakbrowser")
        os.environ["SOCIAL_UPLOAD_CLOAKBROWSER_PROFILE_ROOT"] = str(self.storage.runtime_dir / "browser_profiles")

    async def upload_video(self, request: UploadVideoInput, *, on_event: StatusCallback | None = None) -> UploadResult:
        platform = normalize_platform(request.platform)
        browser = get_social_browser(request.browser or self.browser_config.browser)
        headless = self.browser_config.headless if request.headless is None else request.headless
        use_system_chrome = (
            self.browser_config.use_system_chrome if request.use_system_chrome is None else request.use_system_chrome
        )
        executable_path = request.executable_path or self.browser_config.executable_path
        account_file = self.accounts.account_file(platform, request.account_name)

        if platform == "douyin":
            douyin_request = DouyinVideoUploadRequest(
                account_name=request.account_name,
                video_file=Path(request.video_file),
                title=request.title,
                description=request.description,
                tags=request.tags,
                mode=DouyinUploadMode(request.mode),
                account_file=account_file,
                thumbnail_file=Path(request.thumbnail_file) if request.thumbnail_file else None,
                publish_at=request.publish_at,
                visibility=DouyinVisibility(request.visibility),
                product_link=request.product_link,
                product_title=request.product_title,
                browser=browser,
                headless=headless,
                use_system_chrome=use_system_chrome,
                executable_path=executable_path,
                keep_open_seconds=request.keep_open_seconds,
                debug=request.debug,
                dry_run=request.dry_run,
            )
            return await DouyinVideoUploadWorkflow(douyin_request, on_event=on_event).run()

        xhs_request = XhsVideoUploadRequest(
            account_name=request.account_name,
            video_file=Path(request.video_file),
            title=request.title,
            description=request.description,
            tags=request.tags,
            mode=XhsUploadMode(request.mode),
            account_file=account_file,
            publish_at=request.publish_at,
            browser=browser,
            headless=headless,
            use_system_chrome=use_system_chrome,
            executable_path=executable_path,
            keep_open_seconds=request.keep_open_seconds,
            debug=request.debug,
            dry_run=request.dry_run,
        )
        return await XhsUploadWorkflow(xhs_request, on_event=on_event).run()
