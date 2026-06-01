from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable, Sequence

from social_upload.browser.base import BrowserPage

from . import selectors as S


class DouyinLoginPage:
    def __init__(self, page: BrowserPage):
        self.page = page

    async def open(self) -> None:
        await self.page.goto(S.CREATOR_HOME_URL)

    async def extract_qrcode_src(self) -> str:
        scan_tab = self.page.get_by_text(S.TEXT_LOGIN_SCAN, exact=True).first
        await scan_tab.wait_for(timeout=30000)
        qrcode_img = scan_tab.locator("..").locator("xpath=following-sibling::div[1]").locator(S.QRCODE_IMG).first
        if not await qrcode_img.count():
            qrcode_img = self.page.get_by_role("img", name="二维码").first
        await qrcode_img.wait_for(state="visible", timeout=30000)
        src = await qrcode_img.get_attribute("src")
        if not src:
            raise RuntimeError("未获取到抖音登录二维码")
        return src

    async def is_login_completed(self) -> bool:
        if not self.page.url.startswith(S.LOGIN_DONE_URL_PREFIX):
            return False
        markers = [
            self.page.get_by_text(S.TEXT_LOGIN_SCAN, exact=True).first,
            self.page.get_by_text(S.TEXT_LOGIN_PHONE, exact=True).first,
            self.page.get_by_text(S.TEXT_QRCODE_EXPIRED, exact=True).first,
            self.page.get_by_role("img", name="二维码").first,
        ]
        for marker in markers:
            if await marker.count() and await marker.is_visible():
                return False
        return True

    async def qrcode_expired_box_visible(self) -> bool:
        expired_box = self.page.get_by_text(S.TEXT_QRCODE_EXPIRED, exact=True).locator("..").first
        return bool(await expired_box.count() and await expired_box.is_visible())

    async def refresh_qrcode(self) -> None:
        await self.page.get_by_text(S.TEXT_QRCODE_EXPIRED, exact=True).locator("..").first.click()


class DouyinUploadHomePage:
    def __init__(self, page: BrowserPage):
        self.page = page

    async def open(self) -> None:
        await self.page.goto(S.UPLOAD_URL)
        await self.page.wait_for_url(S.UPLOAD_URL)

    async def upload_video(self, video_file: Path) -> None:
        await self.page.locator(S.UPLOAD_VIDEO_INPUT).set_input_files(str(video_file))

    async def switch_to_note(self) -> None:
        await self.page.get_by_text(S.TEXT_PUBLISH_NOTE, exact=True).click()
        await self.page.wait_for_timeout(1000)

    async def upload_images(self, image_files: Sequence[Path]) -> None:
        await self.page.locator(S.UPLOAD_IMAGE_INPUT).set_input_files([str(item) for item in image_files])

    async def wait_video_publish_page(self) -> None:
        while True:
            for url in S.VIDEO_PUBLISH_URLS:
                try:
                    await self.page.wait_for_url(url, timeout=3000)
                    return
                except Exception:
                    pass
            await self.page.wait_for_timeout(500)

    async def wait_note_publish_page(self) -> None:
        while True:
            try:
                await self.page.wait_for_url(S.NOTE_PUBLISH_URL_PATTERN, timeout=3000)
                return
            except Exception:
                await self.page.wait_for_timeout(500)


class DouyinPublishPage:
    def __init__(self, page: BrowserPage):
        self.page = page

    async def fill_title_and_description(self, title: str, description: str, tags: list[str] | None = None) -> None:
        section = (
            self.page.get_by_text(S.TEXT_DESCRIPTION, exact=True)
            .locator("xpath=ancestor::div[2]")
            .locator("xpath=following-sibling::div[1]")
        )
        title_input = section.locator(S.TITLE_INPUT).first
        await title_input.wait_for(state="visible", timeout=10000)
        await title_input.fill(title[:30])

        editor = section.locator(S.DESCRIPTION_EDITOR).first
        await editor.wait_for(state="visible", timeout=10000)
        await editor.click()
        await self.page.press("Control+KeyA")
        await self.page.press("Delete")
        await self.page.type_text(description)
        for tag in tags or []:
            await self.page.type_text(" #" + tag)
            await self.page.press("Space")

    async def wait_video_uploaded(self, video_file: Path | None = None) -> None:
        while True:
            if await self.page.locator(S.VIDEO_UPLOADED_MARKER).count():
                return
            if await self.page.locator(S.VIDEO_UPLOAD_FAILED).count():
                if not video_file:
                    raise RuntimeError("检测到上传失败，且没有视频路径可重试")
                await self.retry_video_upload(video_file)
            await self.page.wait_for_timeout(2000)

    async def retry_video_upload(self, video_file: Path) -> None:
        await self.page.locator(S.UPLOAD_VIDEO_RETRY_INPUT).set_input_files(str(video_file))

    async def set_visibility(self, visibility: str) -> None:
        normalized = str(visibility or "public").strip().lower()
        label = {
            "public": S.TEXT_VISIBILITY_PUBLIC,
            "private": S.TEXT_VISIBILITY_PRIVATE,
        }.get(normalized)
        if not label:
            raise ValueError(f"不支持的抖音可见性: {visibility}")
        target = self.page.locator(S.VISIBILITY_RADIO.format(label=label)).first
        await target.wait_for(state="visible", timeout=10000)
        await self.resolve_cover_modal_if_present()
        try:
            await target.click()
        except Exception:
            if not await self.resolve_cover_modal_if_present(timeout_ms=6000):
                raise
            await target.click()
        await self.page.wait_for_timeout(500)

    async def set_schedule_time(self, publish_at: datetime) -> None:
        target_value = publish_at.strftime("%Y-%m-%d %H:%M")
        schedule_radio = self.page.locator(S.SCHEDULE_RADIO).first
        await schedule_radio.wait_for(state="visible", timeout=10000)
        await self.resolve_cover_modal_if_present()
        await schedule_radio.click()
        await self.page.wait_for_timeout(1000)

        date_input = self.page.locator(S.DATE_TIME_INPUT).first
        await date_input.wait_for(state="visible", timeout=10000)
        await date_input.click()
        await date_input.fill(target_value)
        await self.page.press("Enter")
        await self.page.wait_for_timeout(1000)
        await self._assert_schedule_time(target_value)

    @staticmethod
    def _normalize_datetime_text(value: str) -> str:
        return str(value or "").strip().replace("/", "-").replace("T", " ")[:16]

    async def _assert_schedule_time(self, target_value: str) -> None:
        actual = await self.page.eval_on_selector(
            S.DATE_TIME_INPUT,
            "el => el.value || el.getAttribute('value') || ''",
        )
        if self._normalize_datetime_text(str(actual)) != target_value:
            raise RuntimeError(
                "抖音定时发布时间未成功写入，已中止发布，避免误触发立即发布；"
                f"期望={target_value}，页面值={actual or '-'}"
            )

    async def set_thumbnail(
        self,
        thumbnail_file: Path | None,
        *,
        on_progress: Callable[[str], Awaitable[None] | None] | None = None,
    ) -> None:
        if not thumbnail_file:
            return
        await self.page.click(f'text="{S.TEXT_SELECT_COVER}"')
        modal = self.page.locator(S.COVER_MODAL)
        await self.page.wait_for_selector(S.COVER_MODAL)
        upload_input = modal.locator(S.COVER_UPLOAD_INPUT)
        await self.page.wait_for_timeout(1000)
        await upload_input.set_input_files(str(thumbnail_file))
        await self._emit_progress(on_progress, "封面文件已提交，等待抖音处理完成")
        done_button = await self._wait_cover_done_button_ready(modal, timeout_ms=60000)
        await done_button.click()
        await self._emit_progress(on_progress, "封面完成按钮已点击，等待弹窗关闭")
        await self.page.wait_for_selector(S.COVER_FOOTER, state="detached", timeout=30000)

    async def _emit_progress(
        self,
        on_progress: Callable[[str], Awaitable[None] | None] | None,
        message: str,
    ) -> None:
        if not on_progress:
            return
        result = on_progress(message)
        if result is not None:
            await result

    async def _wait_cover_done_button_ready(self, modal, *, timeout_ms: int):
        loop = asyncio.get_running_loop()
        deadline = loop.time() + max(0.01, timeout_ms / 1000)
        button = modal.locator(S.COVER_DONE).first
        await button.wait_for(state="visible", timeout=min(timeout_ms, 30000))
        last_state = ""
        while loop.time() < deadline:
            disabled_attr = await button.get_attribute("disabled")
            aria_disabled = await button.get_attribute("aria-disabled")
            class_name = await button.get_attribute("class") or ""
            disabled = (
                disabled_attr is not None
                or str(aria_disabled).lower() == "true"
                or "disabled" in class_name.lower()
            )
            last_state = f"disabled={disabled_attr!r}, aria-disabled={aria_disabled!r}, class={class_name!r}"
            if not disabled:
                return button
            await self.page.wait_for_timeout(500)
        raise RuntimeError(f"抖音封面处理超时：完成按钮仍不可点击；{last_state}")

    async def resolve_cover_modal_if_present(self, *, timeout_ms: int = 8000) -> bool:
        """Close/apply Douyin cover popups before interacting with the publish form.

        Douyin can auto-open a cover dialog after upload (including the horizontal
        cover dialog for vertical videos).  If it remains open, the portal catches
        pointer events and blocks controls such as visibility radio buttons.
        """
        loop = asyncio.get_running_loop()
        deadline = loop.time() + max(0.1, timeout_ms / 1000)
        changed = False
        used_escape = False

        while loop.time() < deadline:
            if await self.apply_auto_cover_if_required():
                changed = True
                await self.page.wait_for_timeout(500)

            if not await self._cover_blocking_layer_visible():
                return changed

            for label in (S.TEXT_DONE, S.TEXT_CONFIRM):
                if await self._click_visible_button(label):
                    changed = True
                    await self.page.wait_for_timeout(700)
                    break
            else:
                if not used_escape:
                    await self.page.press("Escape")
                    used_escape = True
                    changed = True
                    await self.page.wait_for_timeout(700)
                else:
                    await self.page.wait_for_timeout(500)

        return changed and not await self._cover_blocking_layer_visible()

    async def apply_auto_cover_if_required(self) -> bool:
        if not await self.page.get_by_text(S.TEXT_COVER_REQUIRED).first.is_visible():
            return False
        recommend_cover = self.page.locator(S.RECOMMEND_COVER).first
        if not await recommend_cover.count():
            return False
        await recommend_cover.click()
        await self.page.wait_for_timeout(1000)
        if await self.page.get_by_text(S.TEXT_COVER_CONFIRM).first.is_visible():
            await self.page.get_by_role("button", name=S.TEXT_CONFIRM).click()
            await self.page.wait_for_timeout(1000)
        return True

    async def _cover_blocking_layer_visible(self) -> bool:
        layer = self.page.locator(S.COVER_BLOCKING_LAYER)
        count = await layer.count()
        for index in range(count):
            try:
                if await layer.nth(index).is_visible():
                    return True
            except Exception:
                continue
        return False

    async def _click_visible_button(self, label: str) -> bool:
        button = self.page.get_by_role("button", name=label, exact=True)
        count = await button.count()
        for index in range(count):
            target = button.nth(index)
            try:
                if await target.is_visible():
                    await target.click()
                    return True
            except Exception:
                continue
        return False

    async def enable_third_party_sync_if_present(self) -> None:
        switch = self.page.locator(S.THIRD_PARTY_SWITCH)
        if not await switch.count():
            return
        class_name = await self.page.eval_on_selector(S.THIRD_PARTY_SWITCH, "div => div.className")
        if "semi-switch-checked" not in str(class_name):
            await switch.locator(S.THIRD_PARTY_SWITCH_INPUT).click()

    async def set_product_link(self, product_link: str, product_title: str) -> bool:
        if not product_link or not product_title:
            return True
        await self.page.wait_for_selector(f"text={S.TEXT_ADD_LABEL}", timeout=10000)
        dropdown = self.page.get_by_text(S.TEXT_ADD_LABEL).locator("..").locator("..").locator("..").locator(".semi-select").first
        if not await dropdown.count():
            return False
        await dropdown.click()
        await self.page.wait_for_selector('[role="listbox"]', timeout=5000)
        await self.page.locator(f'[role="option"]:has-text("{S.TEXT_CART}")').click()
        await self.page.wait_for_selector(S.PRODUCT_LINK_INPUT, timeout=5000)
        await self.page.locator(S.PRODUCT_LINK_INPUT).fill(product_link)
        add_button = self.page.locator(S.PRODUCT_ADD_LINK)
        button_class = await add_button.get_attribute("class") or ""
        if "disable" in button_class:
            return False
        await add_button.click()
        await self.page.wait_for_timeout(2000)
        if await self.page.locator(f"text={S.TEXT_PRODUCT_NOT_FOUND}").count():
            await self.page.locator(f'button:has-text("{S.TEXT_CONFIRM}")').click()
            return False
        return await self._finish_product_dialog(product_title)

    async def _finish_product_dialog(self, product_title: str) -> bool:
        await self.page.wait_for_selector(S.PRODUCT_SHORT_TITLE, timeout=10000)
        short_title = self.page.locator(S.PRODUCT_SHORT_TITLE)
        if not await short_title.count():
            return False
        await short_title.fill(product_title[:10])
        await self.page.wait_for_timeout(1000)
        finish = self.page.locator(S.PRODUCT_FINISH_BUTTON)
        if "disabled" not in (await finish.get_attribute("class") or ""):
            await finish.click()
            await self.page.wait_for_selector(S.MODAL_CONTENT, state="hidden", timeout=5000)
            return True
        cancel = self.page.locator(S.PRODUCT_CANCEL_BUTTON)
        if await cancel.count():
            await cancel.click()
        else:
            await self.page.locator(S.MODAL_CLOSE).click()
        await self.page.wait_for_selector(S.MODAL_CONTENT, state="hidden", timeout=5000)
        return False

    async def _body_hint_text(self, *, max_chars: int = 700) -> str:
        try:
            text = await self.page.eval_on_selector("body", "el => el.innerText")
        except Exception:
            return ""
        keywords = ("失败", "错误", "请", "上传", "发布", "封面", "检测", "实名", "登录", "审核", "处理中")
        lines = []
        for line in str(text or "").splitlines():
            line = line.strip()
            if line and any(key in line for key in keywords):
                lines.append(line)
        return "\n".join(lines)[:max_chars]

    async def _dismiss_guidance_popovers(self) -> None:
        # Douyin creator center often shows first-use guidance bubbles.  They can
        # cover controls but are safe to dismiss with "我知道了".
        for _ in range(4):
            try:
                button = self.page.get_by_role("button", name=S.TEXT_GOT_IT, exact=True)
                count = await button.count()
                if not count:
                    return
                target = button.nth(0)
                if not await target.is_visible():
                    return
                await target.click()
                await self.page.wait_for_timeout(300)
            except Exception:
                return

    async def publish(
        self,
        *,
        timeout_seconds: int = 240,
        screenshot_path: Path | None = None,
    ) -> Path | None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + max(0.01, float(timeout_seconds))
        last_click_at = 0.0
        attempts = 0
        last_error = ""

        while loop.time() < deadline:
            try:
                await self.page.wait_for_url(S.MANAGE_URL_PATTERN, timeout=1000)
                return None
            except Exception:
                pass

            try:
                await self._dismiss_guidance_popovers()
                await self.apply_auto_cover_if_required()

                # Do not spam the same publish button every 500ms.  If the first
                # click is blocked by validation, retry slowly and keep collecting
                # the page hint for the final error.
                if loop.time() - last_click_at >= 3:
                    button = self.page.get_by_role("button", name=S.TEXT_PUBLISH, exact=True)
                    count = await button.count()
                    if not count:
                        last_error = "未找到“发布”按钮"
                    else:
                        target = button.nth(count - 1) if count > 1 else button
                        if await target.is_visible():
                            await target.click()
                            attempts += 1
                            last_click_at = loop.time()
                        else:
                            last_error = "“发布”按钮不可见"

                try:
                    await self.page.wait_for_url(S.MANAGE_URL_PATTERN, timeout=3000)
                    return None
                except Exception as exc:
                    last_error = f"{type(exc).__name__}: {exc}"
                await self.page.wait_for_timeout(500)
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                await self.page.wait_for_timeout(800)

        saved_screenshot: Path | None = None
        if screenshot_path:
            try:
                saved_screenshot = await self.screenshot(screenshot_path)
            except Exception:
                saved_screenshot = None
        hints = await self._body_hint_text()
        parts = [
            f"点击发布后未进入作品管理页，已等待 {timeout_seconds} 秒",
            f"尝试点击发布 {attempts} 次",
            f"当前 URL: {self.page.url}",
        ]
        if last_error:
            parts.append(f"最后一次等待/点击结果: {last_error}")
        if saved_screenshot:
            parts.append(f"现场截图: {saved_screenshot}")
        if hints:
            parts.append(f"页面提示:\n{hints}")
        raise RuntimeError("；".join(parts))

    async def screenshot(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        await self.page.screenshot(path=path, full_page=True)
        return path


class DouyinNotePublishPage(DouyinPublishPage):
    async def publish_note(self) -> None:
        while True:
            try:
                button = self.page.get_by_role("button", name=S.TEXT_PUBLISH, exact=True)
                if await button.count():
                    await button.click()
                await self.page.wait_for_url(S.NOTE_MANAGE_URL_PATTERN, timeout=3000)
                return
            except Exception:
                await self.page.wait_for_timeout(500)
