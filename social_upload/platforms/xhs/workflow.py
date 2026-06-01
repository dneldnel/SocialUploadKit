from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from social_upload.browser.base import BrowserLaunchOptions

from .login import build_browser_session, check_xhs_cookie, login_xhs, resolve_account_file
from .models import (
    StatusCallback,
    UploadMode,
    UploadResult,
    UploadStage,
    UploadStatusEvent,
    XhsVideoUploadRequest,
)
from .pages import XhsPublishPage, XhsUploadHomePage


def _runtime_dir_for_account(account_file: Path) -> Path:
    if account_file.parent.name == "cookies":
        return account_file.parent.parent
    return Path(".social_upload").resolve()


def _screenshot_dir_for_account(account_file: Path) -> Path:
    path = _runtime_dir_for_account(account_file) / "screenshots"
    path.mkdir(parents=True, exist_ok=True)
    return path


class XhsUploadWorkflow:
    def __init__(self, request: XhsVideoUploadRequest, *, on_event: StatusCallback | None = None):
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

            await self.emit(UploadStage.AUTH_CHECK, "校验小红书 cookie", account_file=str(account_file))
            if not await check_xhs_cookie(
                account_file,
                browser=self.request.browser,
                headless=self.request.headless,
                use_system_chrome=self.request.use_system_chrome,
                executable_path=self.request.executable_path,
            ):
                raise RuntimeError(f"小红书 cookie 缺失或失效，请先登录: {account_file}")

            options = BrowserLaunchOptions(
                headless=self.request.headless,
                use_system_chrome=self.request.use_system_chrome,
                executable_path=self.request.executable_path,
                profile_name=account_file.stem,
            )
            async with build_browser_session(self.request.browser, options) as session:
                context = await session.new_context(storage_state=account_file)
                try:
                    page = await context.new_page()
                    home = XhsUploadHomePage(page)
                    publish_page = XhsPublishPage(page)

                    await self.emit(UploadStage.NAVIGATING, "打开小红书上传页")
                    await home.open()
                    await self.emit(UploadStage.UPLOADING, "选择视频文件并开始上传", file=str(self.request.video_file))
                    await home.upload_video(self.request.video_file)

                    await self.emit(UploadStage.FILLING_METADATA, "填写标题、描述和话题")
                    await publish_page.fill_title_and_description(
                        self.request.title,
                        self.request.description or self.request.title,
                        self.request.tags,
                    )

                    await self.emit(UploadStage.WAITING_UPLOAD, "等待视频上传完成")
                    await home.wait_video_uploaded(self.request.video_file)

                    if self.request.publish_at:
                        await self.emit(UploadStage.SETTING_SCHEDULE, "设置小红书定时发布")
                        await publish_page.set_schedule_time(self.request.publish_at)

                    screenshot_path: Path | None = None
                    if self.request.mode == UploadMode.DRAFT:
                        screenshot_path = _screenshot_dir_for_account(account_file) / f"xhs_draft_{account_file.stem}.png"
                        await self.emit(UploadStage.DRAFT_READY, "草稿模式：点击暂存离开，保存到小红书草稿")
                        try:
                            await publish_page.save_draft(timeout_seconds=90, screenshot_path=screenshot_path)
                        except Exception as draft_exc:
                            await context.storage_state(path=account_file)
                            await self.emit(
                                UploadStage.FAILED,
                                str(draft_exc),
                                screenshot_path=str(screenshot_path) if screenshot_path.exists() else None,
                                current_url=page.url,
                            )
                            return UploadResult(
                                success=False,
                                stage=UploadStage.FAILED,
                                message="小红书草稿暂存失败",
                                mode=self.request.mode,
                                account_file=account_file,
                                screenshot_path=screenshot_path if screenshot_path.exists() else None,
                                current_url=page.url,
                                error=str(draft_exc),
                            )
                        await publish_page.screenshot(screenshot_path)
                        await context.storage_state(path=account_file)
                        await self.emit(
                            UploadStage.DRAFT_READY,
                            "草稿模式完成：已暂存离开，未点击发布按钮",
                            screenshot_path=str(screenshot_path),
                            current_url=page.url,
                        )
                        if self.request.keep_open_seconds > 0:
                            await asyncio.sleep(self.request.keep_open_seconds)
                        return UploadResult(
                            success=True,
                            stage=UploadStage.DRAFT_READY,
                            message="草稿模式完成：已暂存离开，未实际上线",
                            mode=self.request.mode,
                            account_file=account_file,
                            screenshot_path=screenshot_path,
                            current_url=page.url,
                        )

                    # Publish mode — click publish and verify
                    await self.emit(UploadStage.PUBLISHING, "点击发布按钮")
                    publish_screenshot_path = (
                        _screenshot_dir_for_account(account_file)
                        / f"xhs_publish_{account_file.stem}_{datetime.now():%Y%m%d_%H%M%S}.png"
                    )
                    try:
                        await publish_page.publish(timeout_seconds=300, screenshot_path=publish_screenshot_path)
                    except Exception as pub_exc:
                        await context.storage_state(path=account_file)
                        await self.emit(UploadStage.FAILED, str(pub_exc))
                        return UploadResult(
                            success=False,
                            stage=UploadStage.FAILED,
                            message="小红书视频发布失败",
                            mode=self.request.mode,
                            account_file=account_file,
                            screenshot_path=publish_screenshot_path if publish_screenshot_path.exists() else None,
                            current_url=page.url,
                            error=str(pub_exc),
                        )

                    await context.storage_state(path=account_file)
                    await self.emit(UploadStage.PUBLISHED, "小红书视频发布成功", current_url=page.url)
                    return UploadResult(
                        success=True,
                        stage=UploadStage.PUBLISHED,
                        message="小红书视频发布成功",
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
                message="小红书视频上传失败",
                mode=self.request.mode,
                account_file=self.request.account_file,
                error=str(exc),
            )


__all__ = ["XhsUploadWorkflow", "check_xhs_cookie", "login_xhs"]
