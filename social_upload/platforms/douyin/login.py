from __future__ import annotations

import asyncio
import base64
from datetime import datetime
from pathlib import Path
from typing import Any

from social_upload.browser.base import BrowserLaunchOptions
from social_upload.browser.factory import build_browser_session
from social_upload.browser.settings import get_social_browser

from . import selectors as S
from .models import UploadStage, UploadStatusEvent, StatusCallback
from .pages import DouyinLoginPage


def resolve_runtime_dir(runtime_dir: Path | None = None) -> Path:
    return (runtime_dir or Path(".social_upload")).expanduser().resolve()


def resolve_account_file(account_name: str, runtime_dir: Path | None = None) -> Path:
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in account_name.strip())
    if not safe_name:
        raise ValueError("account_name 不能为空")
    path = resolve_runtime_dir(runtime_dir) / "cookies" / f"douyin_{safe_name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


async def emit(callback: StatusCallback | None, event: UploadStatusEvent) -> None:
    if not callback:
        return
    result = callback(event)
    if result is not None:
        await result


def save_qrcode_data_url(data_url: str, account_file: Path) -> Path:
    if not data_url.startswith("data:image/") or "," not in data_url:
        raise ValueError("二维码不是 data:image 格式")
    header, encoded = data_url.split(",", 1)
    if ";base64" not in header:
        raise ValueError("二维码不是 base64 编码")
    output = account_file.with_name(f"{account_file.stem}_login_qrcode_{datetime.now():%Y%m%d_%H%M%S}.png")
    output.write_bytes(base64.b64decode(encoded))
    return output


async def check_douyin_cookie(
    account_file: Path,
    *,
    browser: str | None = None,
    headless: bool = True,
    use_system_chrome: bool = True,
    executable_path: str | None = None,
) -> bool:
    if not account_file.exists():
        return False
    options = BrowserLaunchOptions(
        headless=headless,
        use_system_chrome=use_system_chrome,
        executable_path=executable_path,
        profile_name=account_file.stem,
    )
    async with build_browser_session(get_social_browser(browser), options) as session:
        context = await session.new_context(storage_state=account_file)
        try:
            page = await context.new_page()
            await page.goto(S.UPLOAD_URL)
            try:
                await page.wait_for_url(S.UPLOAD_URL, timeout=5000)
            except Exception:
                return False
            phone_login = await page.get_by_text(S.TEXT_LOGIN_PHONE).count()
            scan_login = await page.get_by_text(S.TEXT_LOGIN_SCAN).count()
            return not bool(phone_login or scan_login)
        finally:
            await context.close()


async def login_douyin(
    account_file: Path,
    *,
    browser: str | None = None,
    headless: bool = True,
    use_system_chrome: bool = True,
    executable_path: str | None = None,
    on_event: StatusCallback | None = None,
    poll_interval_seconds: int = 3,
    max_checks: int = 100,
) -> dict[str, Any]:
    options = BrowserLaunchOptions(
        headless=headless,
        use_system_chrome=use_system_chrome,
        executable_path=executable_path,
        profile_name=account_file.stem,
    )
    async with build_browser_session(get_social_browser(browser), options) as session:
        context = await session.new_context()
        qrcode_path: Path | None = None
        try:
            page = await context.new_page()
            login_page = DouyinLoginPage(page)
            await emit(on_event, UploadStatusEvent(UploadStage.NAVIGATING, "打开抖音创作者中心"))
            await login_page.open()
            await emit(on_event, UploadStatusEvent(UploadStage.LOGIN_QRCODE, "等待抖音登录二维码出现", {"current_url": page.url}))
            qrcode_src = await login_page.extract_qrcode_src()
            qrcode_path = save_qrcode_data_url(qrcode_src, account_file)
            await emit(
                on_event,
                UploadStatusEvent(
                    UploadStage.LOGIN_QRCODE,
                    "请使用抖音 App 扫码登录",
                    {"qrcode_path": str(qrcode_path), "account_file": str(account_file)},
                ),
            )

            for _ in range(max_checks):
                if await login_page.is_login_completed():
                    await page.wait_for_timeout(2000)
                    await context.storage_state(path=account_file)
                    return {
                        "success": True,
                        "message": "抖音登录成功",
                        "account_file": str(account_file),
                        "current_url": page.url,
                    }
                if await login_page.qrcode_expired_box_visible():
                    await login_page.refresh_qrcode()
                    await page.wait_for_timeout(1000)
                    qrcode_src = await login_page.extract_qrcode_src()
                    qrcode_path = save_qrcode_data_url(qrcode_src, account_file)
                    await emit(
                        on_event,
                        UploadStatusEvent(
                            UploadStage.LOGIN_QRCODE,
                            "二维码已刷新，请重新扫码",
                            {"qrcode_path": str(qrcode_path), "account_file": str(account_file)},
                        ),
                    )
                await asyncio.sleep(poll_interval_seconds)

            return {
                "success": False,
                "message": "等待扫码登录超时",
                "account_file": str(account_file),
                "qrcode_path": str(qrcode_path) if qrcode_path else None,
                "current_url": page.url,
            }
        finally:
            await context.close()
