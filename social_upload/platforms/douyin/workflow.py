from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from social_upload.browser.base import BrowserLaunchOptions

from .login import build_browser_session, check_douyin_cookie, login_douyin, resolve_account_file
from .models import (
    DouyinVideoUploadRequest,
    StatusCallback,
    UploadMode,
    UploadResult,
    UploadStage,
    UploadStatusEvent,
)
from .pages import DouyinPublishPage, DouyinUploadHomePage


def _runtime_dir_for_account(account_file: Path) -> Path:
    if account_file.parent.name == "cookies":
        return account_file.parent.parent
    return Path(".social_upload").resolve()


def _screenshot_dir_for_account(account_file: Path) -> Path:
    path = _runtime_dir_for_account(account_file) / "screenshots"
    path.mkdir(parents=True, exist_ok=True)
    return path


class DouyinVideoUploadWorkflow:
    def __init__(self, request: DouyinVideoUploadRequest, *, on_event: StatusCallback | None = None):
        self.request = request
        self.on_event = on_event

    async def emit(self, stage: UploadStage, message: str, **data) -> None:
        if not self.on_event:
            return
        event = UploadStatusEvent(stage, message, data)
        result = self.on_event(event)
        if result is not None:
            await result

    async def run(self) -> UploadResult:
        try:
            await self.emit(UploadStage.VALIDATING, "校验上传参数")
            self.request.validate()
            account_file = self.request.account_file or resolve_account_file(self.request.account_name)
            self.request.account_file = account_file

            if self.request.dry_run:
                await self.emit(UploadStage.DRAFT_READY, "dry-run 完成：未启动浏览器，未上传")
                return UploadResult(
                    success=True,
                    stage=UploadStage.DRAFT_READY,
                    message="dry-run 完成：参数和本地文件有效，未实际上传",
                    mode=self.request.mode,
                    account_file=account_file,
                )

            await self.emit(UploadStage.AUTH_CHECK, "校验抖音 cookie", account_file=str(account_file))
            if not await check_douyin_cookie(
                account_file,
                browser=self.request.browser,
                headless=True,
                use_system_chrome=self.request.use_system_chrome,
                executable_path=self.request.executable_path,
            ):
                raise RuntimeError(f"抖音 cookie 缺失或失效，请先登录: {account_file}")

            options = BrowserLaunchOptions(
                headless=self.request.headless,
                use_system_chrome=self.request.use_system_chrome,
                executable_path=self.request.executable_path,
                profile_name=account_file.stem,
            )
            async with build_browser_session(self.request.browser, options) as session:
                context = await session.new_context(storage_state=account_file, permissions=["geolocation"])
                try:
                    page = await context.new_page()
                    home = DouyinUploadHomePage(page)
                    publish_page = DouyinPublishPage(page)

                    await self.emit(UploadStage.NAVIGATING, "打开抖音上传页")
                    await home.open()
                    await self.emit(UploadStage.UPLOADING, "选择视频文件并开始上传", file=str(self.request.video_file))
                    await home.upload_video(self.request.video_file)
                    await home.wait_video_publish_page()

                    await self.emit(UploadStage.FILLING_METADATA, "填写标题、描述和话题")
                    await publish_page.fill_title_and_description(
                        self.request.title,
                        self.request.description or self.request.title,
                        self.request.tags,
                    )
                    await self.emit(UploadStage.WAITING_UPLOAD, "等待视频上传完成")
                    await publish_page.wait_video_uploaded(self.request.video_file)

                    if self.request.product_link and self.request.product_title:
                        await self.emit(UploadStage.FILLING_METADATA, "设置商品链接")
                        await publish_page.set_product_link(self.request.product_link, self.request.product_title)

                    if self.request.thumbnail_file:
                        await self.emit(UploadStage.SETTING_COVER, "上传封面")
                        await publish_page.set_thumbnail(
                            self.request.thumbnail_file,
                            on_progress=lambda message: self.emit(UploadStage.SETTING_COVER, message),
                        )

                    if await publish_page.resolve_cover_modal_if_present():
                        await self.emit(UploadStage.SETTING_COVER, "已确认抖音封面弹窗")

                    await publish_page.enable_third_party_sync_if_present()

                    await self.emit(UploadStage.SETTING_VISIBILITY, "设置作品可见性")
                    await publish_page.set_visibility(self.request.visibility.value)

                    if self.request.publish_at:
                        await self.emit(UploadStage.SETTING_SCHEDULE, "设置定时发布")
                        await publish_page.set_schedule_time(self.request.publish_at)

                    screenshot_path: Path | None = None
                    if self.request.mode == UploadMode.DRAFT:
                        screenshot_path = _screenshot_dir_for_account(account_file) / f"douyin_draft_{account_file.stem}.png"
                        await publish_page.screenshot(screenshot_path)
                        await context.storage_state(path=account_file)
                        await self.emit(
                            UploadStage.DRAFT_READY,
                            "草稿模式完成：已停在发布前，未点击发布按钮",
                            screenshot_path=str(screenshot_path),
                            current_url=page.url,
                        )
                        if self.request.keep_open_seconds > 0:
                            await asyncio.sleep(self.request.keep_open_seconds)
                        return UploadResult(
                            success=True,
                            stage=UploadStage.DRAFT_READY,
                            message="草稿模式完成：未点击发布按钮，未实际上线",
                            mode=self.request.mode,
                            account_file=account_file,
                            screenshot_path=screenshot_path,
                            current_url=page.url,
                        )

                    await self.emit(UploadStage.PUBLISHING, "点击发布按钮")
                    publish_screenshot_path = (
                        _screenshot_dir_for_account(account_file)
                        / f"douyin_publish_{account_file.stem}_{datetime.now():%Y%m%d_%H%M%S}.png"
                    )
                    await publish_page.publish(screenshot_path=publish_screenshot_path)
                    await context.storage_state(path=account_file)
                    await self.emit(UploadStage.PUBLISHED, "抖音视频发布成功", current_url=page.url)
                    return UploadResult(
                        success=True,
                        stage=UploadStage.PUBLISHED,
                        message="抖音视频发布成功",
                        mode=self.request.mode,
                        account_file=account_file,
                        current_url=page.url,
                    )
                finally:
                    await context.close()
        except Exception as exc:
            await self.emit(UploadStage.FAILED, str(exc))
            return UploadResult(
                success=False,
                stage=UploadStage.FAILED,
                message="抖音视频上传失败",
                mode=self.request.mode,
                account_file=self.request.account_file,
                error=str(exc),
            )


__all__ = ["DouyinVideoUploadWorkflow", "check_douyin_cookie", "login_douyin"]
