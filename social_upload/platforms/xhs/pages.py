from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path

from social_upload.browser.base import BrowserPage

from . import selectors as S


class XhsLoginPage:
    def __init__(self, page: BrowserPage):
        self.page = page

    async def open(self) -> None:
        await self.page.goto(S.LOGIN_URL)

    async def _text_visible(self, text: str, *, exact: bool = False) -> bool:
        loc = self.page.get_by_text(text, exact=exact).first
        try:
            return bool(await loc.count() and await loc.is_visible())
        except Exception:
            return False

    async def _visible_qrcode_src(self) -> str:
        try:
            src = await self.page.eval_on_selector(
                "body",
                """root => {
                    const visibleBox = (el) => {
                        const rect = el.getBoundingClientRect();
                        const style = window.getComputedStyle(el);
                        return rect.width > 0 && rect.height > 0 &&
                            style.visibility !== 'hidden' && style.display !== 'none';
                    };
                    const imgs = Array.from(root.querySelectorAll(
                        '.sso-login-wrapper img[src^="data:image/"], img[alt*="二维码"], .qrcode-img img'
                    ));
                    const candidates = imgs
                        .map(el => ({ el, rect: el.getBoundingClientRect(), src: el.src || el.getAttribute('src') || '' }))
                        .filter(x => x.src.startsWith('data:image/') && visibleBox(x.el))
                        // The QR code is the large data image. The SMS/QR switch is a 64px corner icon.
                        .filter(x => x.rect.width >= 120 && x.rect.height >= 120)
                        .sort((a, b) => (b.rect.width * b.rect.height) - (a.rect.width * a.rect.height));
                    return candidates[0]?.src || '';
                }""",
            )
            return str(src or "")
        except Exception:
            return ""

    async def _ensure_qr_login_mode(self) -> None:
        if await self._visible_qrcode_src():
            return
        if await self._text_visible(S.TEXT_LOGIN_QR_TITLE) or await self._text_visible(S.TEXT_LOGIN_QR_AGREEMENT):
            return

        switch = self.page.locator(S.QR_LOGIN_SWITCH).first
        if await switch.count() and await switch.is_visible():
            await switch.click()
            await self.page.wait_for_timeout(1000)

    async def extract_qrcode_src(self) -> str:
        for _ in range(60):
            await self._ensure_qr_login_mode()
            src = await self._visible_qrcode_src()
            if src:
                return src
            await self.page.wait_for_timeout(500)
        raise RuntimeError("未获取到小红书登录二维码：页面可能未切到扫码登录，或小红书登录页结构已变化")

    async def is_login_completed(self) -> bool:
        if not self.page.url.startswith(S.LOGIN_DONE_URL_PREFIX):
            return False
        if "login" in self.page.url.lower():
            return False
        markers = [
            self.page.get_by_text(S.TEXT_LOGIN_SCAN, exact=True).first,
            self.page.get_by_text(S.TEXT_LOGIN_PHONE, exact=True).first,
            self.page.get_by_text(S.TEXT_LOGIN_SMS, exact=True).first,
            self.page.get_by_text(S.TEXT_LOGIN_QR_TITLE, exact=False).first,
            self.page.get_by_text(S.TEXT_LOGIN_QR_AGREEMENT, exact=False).first,
            self.page.get_by_text(S.TEXT_QRCODE_EXPIRED, exact=True).first,
            self.page.get_by_role("img", name="二维码").first,
        ]
        for marker in markers:
            if await marker.count() and await marker.is_visible():
                return False
        if await self._visible_qrcode_src():
            return False
        return True

    async def qrcode_expired_box_visible(self) -> bool:
        expired_text = self.page.get_by_text(S.TEXT_QRCODE_EXPIRED, exact=True).first
        return bool(await expired_text.count() and await expired_text.is_visible())

    async def refresh_qrcode(self) -> None:
        refresh_btn = self.page.get_by_text("刷新").first
        if await refresh_btn.count():
            await refresh_btn.click()
        else:
            qrcode_img = self.page.locator(S.QRCODE_IMG).first
            if await qrcode_img.count():
                await qrcode_img.click()


class XhsUploadHomePage:
    def __init__(self, page: BrowserPage):
        self.page = page

    async def open(self) -> None:
        await self.page.goto(S.UPLOAD_URL)
        if str(self.page.url or "").startswith(S.UPLOAD_URL):
            return
        await self.page.wait_for_url(S.UPLOAD_URL + "**", timeout=10000)

    async def upload_video(self, video_file: Path) -> None:
        await self._set_video_input_files(video_file)

    async def _dismiss_blocking_tips(self) -> None:
        for text in (S.TEXT_GOT_IT, "知道了", "我知道啦"):
            try:
                btn = self.page.get_by_text(text, exact=False).first
                if await btn.count() and await btn.is_visible():
                    await btn.click()
                    await self.page.wait_for_timeout(300)
                    return
            except Exception:
                continue

    async def _click_video_upload_affordance(self) -> None:
        # Some XHS versions render the native input only after the user chooses
        # the video-upload mode/card. Text labels have been more stable than CSS.
        for text in (S.TEXT_UPLOAD_VIDEO, "视频上传"):
            try:
                loc = self.page.get_by_text(text, exact=False).first
                if await loc.count() and await loc.is_visible():
                    await loc.click()
                    await self.page.wait_for_timeout(500)
                    return
            except Exception:
                continue

    async def _mark_best_video_input(self) -> dict:
        try:
            data = await self.page.eval_on_selector(
                "body",
                r"""root => {
                    const visible = (el) => {
                        const r = el.getBoundingClientRect();
                        const s = window.getComputedStyle(el);
                        return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
                    };
                    const textOf = (el) => {
                        let cur = el;
                        for (let i = 0; cur && i < 6; i += 1, cur = cur.parentElement) {
                            const text = (cur.innerText || cur.textContent || '').replace(/\s+/g, ' ').trim();
                            if (text) return text.slice(0, 160);
                        }
                        return '';
                    };
                    const inputs = Array.from(root.querySelectorAll('input[type="file"]'));
                    inputs.forEach(el => el.removeAttribute('data-vl-xhs-video-input'));
                    const infos = inputs.map((el, idx) => {
                        const accept = (el.getAttribute('accept') || '').toLowerCase();
                        const text = textOf(el).toLowerCase();
                        let score = 0;
                        if (accept.includes('video')) score += 100;
                        if (/\.(mp4|mov|m4v|avi|wmv|mpeg|mpg|webm)/.test(accept)) score += 90;
                        if (text.includes('视频')) score += 30;
                        if (text.includes('上传')) score += 15;
                        if (el.closest('.el-upload,[class*="upload"],[class*="Upload"]')) score += 10;
                        if (visible(el)) score += 5;
                        if (accept.includes('image') || text.includes('封面') || text.includes('图片')) score -= 80;
                        return { idx, score, accept, text, visible: visible(el), outer: el.outerHTML.slice(0, 240) };
                    }).sort((a, b) => b.score - a.score);
                    const best = infos.find(x => x.score > 0) || infos[0];
                    if (best) inputs[best.idx].setAttribute('data-vl-xhs-video-input', '1');
                    return { found: !!best, best, inputs: infos.slice(0, 8), url: location.href };
                }""",
            )
            return data if isinstance(data, dict) else {}
        except Exception as exc:
            return {"found": False, "error": f"{type(exc).__name__}: {exc}", "url": str(self.page.url or "")}

    async def _set_video_input_files(self, video_file: Path) -> None:
        last_debug: dict = {}
        for attempt in range(60):
            await self._dismiss_blocking_tips()
            last_debug = await self._mark_best_video_input()
            marked = self.page.locator(S.UPLOAD_VIDEO_INPUT_MARKER).first
            if await marked.count():
                await marked.set_input_files(str(video_file))
                return
            # Fallback for lightweight fake pages/tests or older DOMs.
            direct = self.page.locator(S.UPLOAD_VIDEO_INPUT).first
            if await direct.count():
                await direct.set_input_files(str(video_file))
                return
            if attempt in {0, 2, 5, 10}:
                await self._click_video_upload_affordance()
            await self.page.wait_for_timeout(1000)
        raise RuntimeError(
            "未找到小红书视频上传 input；可能页面结构已变化、未进入视频上传模式，或登录后被风控/引导页拦截。"
            f" current_url={self.page.url}; debug={last_debug}"
        )

    async def wait_video_uploaded(self, video_file: Path | None = None) -> None:
        for _ in range(120):
            if await self._locator_visible(S.VIDEO_UPLOAD_FAILED):
                if not video_file:
                    raise RuntimeError("检测到小红书上传失败，且没有视频路径可重试")
                await self.retry_video_upload(video_file)
                await self.page.wait_for_timeout(2000)
                continue

            uploading_visible = await self._locator_visible(S.VIDEO_UPLOADING_INDICATOR)
            publish_ready = await self._locator_visible(S.PUBLISH_BUTTON, check_disabled=True)

            if publish_ready and not uploading_visible:
                await self.page.wait_for_timeout(2000)
                if not await self._locator_visible(S.VIDEO_UPLOADING_INDICATOR) and \
                        await self._locator_visible(S.PUBLISH_BUTTON, check_disabled=True):
                    return

            await self.page.wait_for_timeout(2000)
        raise RuntimeError("小红书视频上传等待超时")

    async def _locator_visible(self, selector: str, *, check_disabled: bool = False) -> bool:
        loc = self.page.locator(selector).first
        try:
            if await loc.count() == 0:
                return False
            if not await loc.is_visible():
                return False
            if check_disabled:
                disabled = await loc.get_attribute("disabled")
                if disabled is not None:
                    return False
            return True
        except Exception:
            return False

    async def retry_video_upload(self, video_file: Path) -> None:
        await self._set_video_input_files(video_file)


class XhsPublishPage:
    def __init__(self, page: BrowserPage):
        self.page = page

    async def _mark_best_text_target(self, *, kind: str) -> dict:
        marker_attr = "data-vl-xhs-title-input" if kind == "title" else "data-vl-xhs-content-editor"
        try:
            data = await self.page.eval_on_selector(
                "body",
                f"""root => {{
                    const kind = {kind!r};
                    const markerAttr = {marker_attr!r};
                    const visible = (el) => {{
                        const r = el.getBoundingClientRect();
                        const s = window.getComputedStyle(el);
                        return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
                    }};
                    const textAround = (el) => {{
                        const attrs = [
                            el.getAttribute('placeholder'),
                            el.getAttribute('aria-label'),
                            el.getAttribute('title'),
                            el.getAttribute('data-placeholder'),
                        ].filter(Boolean).join(' ');
                        const childPlaceholders = Array.from(el.querySelectorAll?.('[data-placeholder], [placeholder], [aria-label]') || [])
                            .map(child => child.getAttribute('data-placeholder') || child.getAttribute('placeholder') || child.getAttribute('aria-label') || '')
                            .filter(Boolean)
                            .join(' ');
                        let cur = el;
                        const pieces = [attrs, childPlaceholders];
                        for (let i = 0; cur && i < 6; i += 1, cur = cur.parentElement) {{
                            const text = (cur.innerText || cur.textContent || '').replace(/\\s+/g, ' ').trim();
                            if (text) pieces.push(text.slice(0, 220));
                        }}
                        return pieces.join(' ').toLowerCase();
                    }};
                    const markTarget = (el) => {{
                        if (kind !== 'content') return el;
                        return el.closest?.('[contenteditable="true"], [role="textbox"], .ProseMirror') || el;
                    }};
                    const selector = kind === 'title'
                        ? 'input, textarea, [contenteditable="true"], [role="textbox"]'
                        : 'textarea, [contenteditable="true"], [role="textbox"], .ProseMirror, [data-placeholder]';
                    const nodes = Array.from(root.querySelectorAll(selector));
                    nodes.forEach(el => el.removeAttribute(markerAttr));
                    const infos = nodes.map((el, idx) => {{
                        const tag = (el.tagName || '').toLowerCase();
                        const role = (el.getAttribute('role') || '').toLowerCase();
                        const editable = el.isContentEditable || tag === 'textarea' || tag === 'input' || role === 'textbox';
                        const text = textAround(el);
                        let score = 0;
                        const target = markTarget(el);
                        const targetClass = String(target.className || '');
                        const targetRole = (target.getAttribute('role') || '').toLowerCase();
                        const strongContentEditor = kind === 'content' && visible(el) && editable && (
                            targetClass.includes('ProseMirror') ||
                            target.classList?.contains('ProseMirror') ||
                            targetRole === 'textbox' ||
                            target.isContentEditable
                        );
                        if (kind === 'title') {{
                            if (text.includes('标题')) score += 100;
                            if (text.includes('更多赞')) score += 60;
                            if (tag === 'input') score += 20;
                            if (text.includes('正文') || text.includes('描述') || text.includes('地点') || text.includes('群聊')) score -= 80;
                        }} else {{
                            if (text.includes('正文')) score += 100;
                            if (text.includes('描述')) score += 90;
                            if (text.includes('真诚有价值')) score += 70;
                            if (tag === 'textarea') score += 30;
                            if (el.isContentEditable || role === 'textbox') score += 25;
                            if (el.classList?.contains('ProseMirror')) score += 35;
                            if (tag === 'p' && markTarget(el) !== el) score -= 40;
                            if (text.includes('标题') || text.includes('地点') || text.includes('群聊') || text.includes('搜索')) score -= 80;
                            if (strongContentEditor) score += 120;
                        }}
                        if (!editable) score -= 200;
                        if (visible(el)) score += 10;
                        return {{
                            idx, score, tag, role,
                            editable,
                            visible: visible(el),
                            strongContentEditor,
                            text: text.slice(0, 180),
                            outer: el.outerHTML.slice(0, 240),
                            targetTag: (target.tagName || '').toLowerCase(),
                            targetRole: target.getAttribute('role') || '',
                            targetOuter: target.outerHTML.slice(0, 240),
                        }};
                    }}).sort((a, b) => b.score - a.score);
                    const best = infos.find(x => x.score > 0);
                    if (best) markTarget(nodes[best.idx]).setAttribute(markerAttr, '1');
                    return {{ found: !!best, best, inputs: infos.slice(0, 10), url: location.href }};
                }}""",
            )
            return data if isinstance(data, dict) else {}
        except Exception as exc:
            return {"found": False, "error": f"{type(exc).__name__}: {exc}", "url": str(self.page.url or "")}

    async def _fill_text_target(self, *, kind: str, value: str) -> None:
        marker = S.TITLE_INPUT_MARKER if kind == "title" else S.CONTENT_EDITOR_MARKER
        fallback = S.TITLE_INPUT if kind == "title" else S.CONTENT_EDITOR
        label = "标题" if kind == "title" else "正文"
        last_debug: dict = {}
        for _ in range(10):
            last_debug = await self._mark_best_text_target(kind=kind)
            for selector in (marker, fallback):
                loc = self.page.locator(selector).first
                try:
                    if await loc.count() == 0:
                        continue
                    if not await loc.is_visible():
                        continue
                    try:
                        await loc.fill(value)
                    except Exception:
                        await loc.click()
                        await self.page.press("Control+KeyA")
                        await self.page.press("Delete")
                        await self.page.type_text(value)
                    return
                except Exception:
                    continue
            await self.page.wait_for_timeout(500)
        raise RuntimeError(
            f"小红书{label}填充失败：未找到{label}输入框，selector 可能已变化；"
            f"current_url={self.page.url}; debug={last_debug}"
        )

    @staticmethod
    def _normalize_tags(tags: list[str] | None) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in tags or []:
            tag = str(raw or "").strip().lstrip("#").strip()
            if not tag or tag in seen:
                continue
            normalized.append(tag)
            seen.add(tag)
        return normalized

    async def fill_title_and_description(self, title: str, description: str, tags: list[str] | None = None) -> None:
        normalized_tags = self._normalize_tags(tags)
        await self._fill_text_target(kind="title", value=title)

        if description:
            await self._fill_text_target(kind="content", value=description)

        if normalized_tags:
            if not description:
                await self._fill_text_target(kind="content", value="")
            if not await self._fill_dedicated_topic_input(normalized_tags):
                await self._append_inline_topics(normalized_tags)

    async def _fill_dedicated_topic_input(self, tags: list[str]) -> bool:
        try:
            tag_input = self.page.locator(S.TAG_INPUT).first
            if await tag_input.count() == 0 or not await tag_input.is_visible():
                return False
        except Exception:
            return False

        for tag in tags:
            try:
                await tag_input.fill(tag)
                await self.page.wait_for_timeout(700)
                await self._click_topic_result_if_visible()
            except Exception:
                return False
        return True

    async def _focus_content_end(self) -> None:
        last_debug: dict = {}
        for _ in range(10):
            last_debug = await self._mark_best_text_target(kind="content")
            for selector in (S.CONTENT_EDITOR_MARKER, S.CONTENT_EDITOR):
                loc = self.page.locator(selector).first
                try:
                    if await loc.count() == 0:
                        continue
                    if not await loc.is_visible():
                        continue
                    await loc.click()
                    await self._move_caret_to_end(selector)
                    return
                except Exception:
                    continue
            await self.page.wait_for_timeout(500)
        raise RuntimeError(
            "小红书话题填充失败：未找到可输入话题的正文编辑器；"
            f"current_url={self.page.url}; debug={last_debug}"
        )

    async def _move_caret_to_end(self, selector: str) -> None:
        try:
            await self.page.eval_on_selector(
                selector,
                """el => {
                    const target = el.matches?.('[contenteditable="true"], [role="textbox"], .ProseMirror')
                        ? el
                        : el.querySelector?.('[contenteditable="true"], [role="textbox"], .ProseMirror, textarea, input') || el;
                    target.focus?.();
                    if (typeof target.value === 'string') {
                        const end = target.value.length;
                        target.setSelectionRange?.(end, end);
                        return;
                    }
                    const range = document.createRange();
                    range.selectNodeContents(target);
                    range.collapse(false);
                    const sel = window.getSelection();
                    sel.removeAllRanges();
                    sel.addRange(range);
                }""",
            )
        except Exception:
            pass
        try:
            await self.page.press("End")
        except Exception:
            pass

    async def _append_inline_topics(self, tags: list[str]) -> None:
        await self._focus_content_end()
        for tag in tags:
            await self.page.type_text(f" #{tag} ")
            await self.page.wait_for_timeout(700)
            await self._click_topic_result_if_visible()

    async def _click_topic_result_if_visible(self) -> bool:
        try:
            result = self.page.locator(S.TAG_RESULT).first
            if await result.count() == 0 or not await result.is_visible():
                return False
            await result.click()
            await self.page.wait_for_timeout(500)
            return True
        except Exception:
            return False

    async def set_schedule_time(self, publish_at: datetime) -> None:
        target_value = publish_at.strftime("%Y-%m-%d %H:%M")
        if not await self._schedule_enabled():
            await self._click_schedule_switch()
            if not await self._schedule_enabled():
                raise RuntimeError("小红书定时发布开关未成功打开，页面结构可能已变化")

        date_input = self.page.locator(S.SCHEDULE_DATETIME_INPUT).first
        await date_input.wait_for(state="visible", timeout=10000)
        await date_input.click()
        await date_input.fill(target_value)
        await self.page.press("Enter")
        await self.page.wait_for_timeout(1000)
        await self._assert_schedule_time(target_value)

    async def _schedule_enabled(self) -> bool:
        try:
            return bool(await self.page.eval_on_selector(
                "body",
                """root => {
                    const box = root.querySelector('.post-time-wrapper input[type="checkbox"]');
                    if (box && box.checked) return true;
                    return !!root.querySelector('.date-picker-container input, .post-time-wrapper .d-datepicker input');
                }""",
            ))
        except Exception:
            return False

    async def _click_schedule_switch(self) -> None:
        schedule_switch = self.page.locator(S.SCHEDULE_SWITCH).first
        await schedule_switch.wait_for(state="visible", timeout=10000)
        try:
            await schedule_switch.click()
        except Exception:
            pass
        await self.page.wait_for_timeout(1000)
        if await self._schedule_enabled():
            return

        raw_page = getattr(self.page, "_page", None)
        if raw_page is not None:
            try:
                await raw_page.locator(".post-time-switch-container .d-switch").first.click(force=True)
                await self.page.wait_for_timeout(1000)
                if await self._schedule_enabled():
                    return
            except Exception:
                pass

        try:
            await self.page.eval_on_selector(
                "body",
                """root => {
                    const target = root.querySelector('.post-time-switch-container .d-switch, .post-time-switch-container input[type="checkbox"], .post-time-switch-container');
                    if (!target) throw new Error('schedule switch missing');
                    target.click();
                }""",
            )
        except Exception:
            raise
        await self.page.wait_for_timeout(1000)

    @staticmethod
    def _normalize_datetime_text(value: str) -> str:
        return str(value or "").strip().replace("/", "-").replace("T", " ")[:16]

    async def _assert_schedule_time(self, target_value: str) -> None:
        actual = await self.page.eval_on_selector(
            S.SCHEDULE_DATETIME_INPUT,
            "el => el.value || el.getAttribute('value') || ''",
        )
        if self._normalize_datetime_text(str(actual)) != target_value:
            raise RuntimeError(
                "小红书定时发布时间未成功写入，已中止发布，避免误触发立即发布；"
                f"期望={target_value}，页面值={actual or '-'}"
            )

    async def screenshot(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        await self.page.screenshot(path=path, full_page=True)
        return path

    async def is_publish_button_visible(self) -> bool:
        publish_btn = self.page.locator(S.PUBLISH_BUTTON).first
        return bool(await publish_btn.count() and await publish_btn.is_visible())

    async def is_save_draft_button_visible(self) -> bool:
        clicked, _ = await self._save_draft_control_available(click=False)
        return clicked

    def _is_manage_url(self) -> bool:
        return str(self.page.url or "").startswith(S.MANAGE_URL_PREFIX)

    async def _wait_for_manage_url(self, *, timeout: int) -> bool:
        if self._is_manage_url():
            return True
        try:
            await self.page.wait_for_url(S.MANAGE_URL_PREFIX + "**", timeout=timeout)
            return True
        except Exception:
            return self._is_manage_url()

    async def publish(
        self,
        *,
        timeout_seconds: int = 300,
        screenshot_path: Path | None = None,
    ) -> Path | None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + max(0.01, float(timeout_seconds))
        last_click_at = 0.0
        attempts = 0
        last_error = ""

        while loop.time() < deadline:
            if await self._wait_for_manage_url(timeout=1000):
                return None

            try:
                current_url = self.page.url
                if "publish/publish" not in current_url and "creator" in current_url:
                    last_error = f"发布后跳转到非发布/管理页，不能视为成功: {current_url}"

                if "publish/publish" in current_url and loop.time() - last_click_at >= 5:
                    publish_btn = self.page.locator(S.PUBLISH_BUTTON).first
                    count = await publish_btn.count()
                    if not count:
                        last_error = "未找到“发布”按钮"
                    else:
                        if await publish_btn.is_visible():
                            disabled = await publish_btn.get_attribute("disabled")
                            if disabled is not None:
                                last_error = "“发布”按钮已禁用"
                            else:
                                await publish_btn.click()
                                attempts += 1
                                last_click_at = loop.time()
                        else:
                            last_error = "“发布”按钮不可见"

                if await self._wait_for_manage_url(timeout=3000):
                    return None
                last_error = f"尚未进入管理页: {self.page.url}"

                success_text = self.page.get_by_text(S.TEXT_PUBLISH_SUCCESS, exact=True).first
                if await success_text.count() and await success_text.is_visible():
                    return None

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
            f"点击发布后未进入管理页或成功页，已等待 {timeout_seconds} 秒",
            f"尝试点击发布 {attempts} 次",
            f"当前 URL: {self.page.url}",
        ]
        if last_error:
            parts.append(f"最后一次检查结果: {last_error}")
        if saved_screenshot:
            parts.append(f"现场截图: {saved_screenshot}")
        if hints:
            parts.append(f"页面提示:\n{hints}")
        raise RuntimeError("；".join(parts))

    async def _click_enabled_locator(self, locator) -> tuple[bool, str]:
        try:
            if await locator.count() == 0:
                return False, "count=0"
            if not await locator.is_visible():
                return False, "not visible"
            disabled = await locator.get_attribute("disabled")
            aria_disabled = await locator.get_attribute("aria-disabled")
            if disabled is not None or str(aria_disabled or "").lower() == "true":
                return False, "disabled"
            await locator.click()
            return True, "clicked"
        except Exception as exc:
            return False, f"{type(exc).__name__}: {exc}"

    async def _click_text_control_by_js(
        self,
        labels: list[str],
        *,
        click: bool = True,
        dialog_only: bool = False,
    ) -> tuple[bool, str]:
        labels_json = json.dumps(labels, ensure_ascii=False)
        action = "target.click();" if click else ""
        dialog_only_js = "true" if dialog_only else "false"
        try:
            result = await self.page.eval_on_selector(
                "body",
                f"""root => {{
                    const labels = {labels_json};
                    const dialogOnly = {dialog_only_js};
                    const norm = (value) => String(value || '').replace(/\\s+/g, '').trim();
                    const visible = (el) => {{
                        const rect = el.getBoundingClientRect();
                        const style = window.getComputedStyle(el);
                        return rect.width > 0 && rect.height > 0 &&
                            style.visibility !== 'hidden' &&
                            style.display !== 'none' &&
                            style.pointerEvents !== 'none';
                    }};
                    const disabled = (el) => {{
                        const cls = String(el.className || '').toLowerCase();
                        return el.disabled || el.getAttribute('disabled') !== null ||
                            el.getAttribute('aria-disabled') === 'true' ||
                            cls.includes('disabled') || cls.includes('is-disabled');
                    }};
                    const clickableFor = (el) => (
                        el.closest('button,[role="button"],a,.el-button,[class*="button"],[class*="Button"],[class*="btn"],[class*="Btn"]') || el
                    );
                    const nodes = Array.from(root.querySelectorAll(
                        'button,[role="button"],a,.el-button,[class*="button"],[class*="Button"],[class*="btn"],[class*="Btn"],span,div'
                    ));
                    const candidates = [];
                    for (const node of nodes) {{
                        const text = norm(node.innerText || node.textContent);
                        if (!text || !labels.some(label => text === norm(label) || text.includes(norm(label)))) continue;
                        if (text.length > 80 && !labels.some(label => text === norm(label))) continue;
                        const target = clickableFor(node);
                        if (!visible(target) || disabled(target)) continue;
                        const rect = target.getBoundingClientRect();
                        const style = window.getComputedStyle(target);
                        const targetText = norm(target.innerText || target.textContent);
                        const exact = labels.some(label => targetText === norm(label) || text === norm(label));
                        const inDialog = !!target.closest('[role="dialog"],.el-dialog,.modal,[class*="dialog"],[class*="Dialog"]');
                        if (dialogOnly && !inDialog) continue;
                        const sticky = style.position === 'fixed' || style.position === 'sticky';
                        candidates.push({{
                            target,
                            score: (exact ? 1000 : 0) + (inDialog ? 300 : 0) + (sticky ? 120 : 0) + Math.round(rect.top),
                            text: targetText || text,
                            tag: target.tagName,
                            cls: String(target.className || '').slice(0, 120),
                            rect: {{ x: rect.x, y: rect.y, width: rect.width, height: rect.height }},
                        }});
                    }}
                    candidates.sort((a, b) => b.score - a.score);
                    const best = candidates[0];
                    if (!best) return {{ clicked: false, reason: 'no visible text control' }};
                    const target = best.target;
                    {action}
                    return {{
                        clicked: true,
                        text: best.text,
                        tag: best.tag,
                        cls: best.cls,
                        rect: best.rect,
                    }};
                }}""",
            )
            if isinstance(result, dict) and result.get("clicked"):
                return True, str({k: v for k, v in result.items() if k != "clicked"})
            if isinstance(result, dict):
                return False, str(result.get("reason") or result)
            return False, str(result)
        except Exception as exc:
            return False, f"{type(exc).__name__}: {exc}"

    async def _save_draft_control_available(self, *, click: bool) -> tuple[bool, str]:
        errors: list[str] = []
        for label in (S.TEXT_SAVE_DRAFT, "保存草稿"):
            try:
                locator = self.page.get_by_role("button", name=label, exact=True).first
                clicked, detail = await self._click_enabled_locator(locator) if click else await self._locator_available(locator)
                if clicked:
                    return True, f"role button {label}: {detail}"
                errors.append(f"role button {label}: {detail}")
            except Exception as exc:
                errors.append(f"role button {label}: {type(exc).__name__}: {exc}")

        for selector in (S.SAVE_DRAFT_BUTTON,):
            locator = self.page.locator(selector).first
            clicked, detail = await self._click_enabled_locator(locator) if click else await self._locator_available(locator)
            if clicked:
                return True, f"selector {selector}: {detail}"
            errors.append(f"selector {selector}: {detail}")

        for label, exact in ((S.TEXT_SAVE_DRAFT, True), ("保存草稿", False), ("暂存", False)):
            try:
                locator = self.page.get_by_text(label, exact=exact).first
                clicked, detail = await self._click_enabled_locator(locator) if click else await self._locator_available(locator)
                if clicked:
                    return True, f"text {label}: {detail}"
                errors.append(f"text {label}: {detail}")
            except Exception as exc:
                errors.append(f"text {label}: {type(exc).__name__}: {exc}")

        clicked, detail = await self._click_text_control_by_js([S.TEXT_SAVE_DRAFT, "保存草稿", "暂存"], click=click)
        if clicked:
            return True, f"js text: {detail}"
        errors.append(f"js text: {detail}")
        return False, "; ".join(errors[-4:])

    async def _locator_available(self, locator) -> tuple[bool, str]:
        try:
            if await locator.count() == 0:
                return False, "count=0"
            if not await locator.is_visible():
                return False, "not visible"
            disabled = await locator.get_attribute("disabled")
            aria_disabled = await locator.get_attribute("aria-disabled")
            if disabled is not None or str(aria_disabled or "").lower() == "true":
                return False, "disabled"
            return True, "available"
        except Exception as exc:
            return False, f"{type(exc).__name__}: {exc}"

    async def _click_save_confirm_if_present(self) -> tuple[bool, str]:
        labels = ["确定", "确认"]
        for label in labels:
            try:
                loc = self.page.get_by_role("button", name=label, exact=True).first
                clicked, detail = await self._click_enabled_locator(loc)
                if clicked:
                    return True, f"confirm role {label}: {detail}"
            except Exception:
                pass
        clicked, detail = await self._click_text_control_by_js(["暂存离开", "保存草稿", "确定", "确认"], dialog_only=True)
        if clicked:
            return True, f"confirm js: {detail}"
        return False, detail

    async def _draft_box_saved_visible(self) -> bool:
        try:
            text = await self.page.eval_on_selector("body", "el => el.innerText")
        except Exception:
            return False
        normalized = str(text or "").replace(" ", "")
        return (
            "草稿箱" in normalized
            and "保存于" in normalized
            and ("视频笔记" in normalized or "图文笔记" in normalized)
        )

    async def save_draft(
        self,
        *,
        timeout_seconds: int = 90,
        screenshot_path: Path | None = None,
    ) -> Path | None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + max(0.01, float(timeout_seconds))
        last_click_at = 0.0
        attempts = 0
        last_error = ""

        while loop.time() < deadline:
            if await self._wait_for_manage_url(timeout=500):
                return None
            try:
                if "publish/publish" in self.page.url and loop.time() - last_click_at >= 5:
                    clicked, detail = await self._save_draft_control_available(click=True)
                    if clicked:
                        attempts += 1
                        last_click_at = loop.time()
                        last_error = f"已点击“暂存离开”: {detail}"
                    else:
                        last_error = f"未找到可点击的“暂存离开”控件: {detail}"

                confirmed, confirm_detail = await self._click_save_confirm_if_present()
                if confirmed:
                    last_error = f"已处理暂存确认: {confirm_detail}"

                if await self._wait_for_manage_url(timeout=3000):
                    return None
                if await self._draft_box_saved_visible():
                    return None

                success_text = self.page.get_by_text("保存成功", exact=False).first
                if await success_text.count() and await success_text.is_visible():
                    last_error = "看到“保存成功”提示，但仍停留在发布页，继续等待跳转到笔记管理页"

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
            f"点击暂存离开后未进入笔记管理页，已等待 {timeout_seconds} 秒",
            f"尝试点击暂存离开 {attempts} 次",
            f"当前 URL: {self.page.url}",
        ]
        if last_error:
            parts.append(f"最后一次检查结果: {last_error}")
        if saved_screenshot:
            parts.append(f"现场截图: {saved_screenshot}")
        if hints:
            parts.append(f"页面提示:\n{hints}")
        raise RuntimeError("；".join(parts))

    async def _body_hint_text(self, max_chars: int = 700) -> str:
        try:
            text = await self.page.eval_on_selector("body", "el => el.innerText")
        except Exception:
            return ""
        keywords = ("失败", "错误", "请", "上传", "发布", "检测", "实名", "登录", "审核", "处理中", "草稿箱", "保存于")
        lines = []
        for line in str(text or "").splitlines():
            line = line.strip()
            if line and any(key in line for key in keywords):
                lines.append(line)
        return "\n".join(lines)[:max_chars]
