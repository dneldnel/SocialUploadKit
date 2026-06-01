from __future__ import annotations

# ── Phase 0 findings ─────────────────────────────────────────────────
# XHS Creator Platform tech stack (confirmed via HTML analysis 2026-05-23):
#   Vue 3 + Element Plus (library-element-plus)
#   Publish micro-frontend (project-publish-vue, project-publish-components)
#   COS SDK for video upload (library-cos-sdk)
#   mp4box for video processing (mp4box)
#   Shepherd.js for onboarding tours
#   Cropper.js for image cropping (library-cropper)
#   ONNX Runtime for ML inference (library-onnxruntime)
#
# Confirmed:
#   - URL endpoints (login, creator home, upload, manage) are reachable
#   - Frame toolkits were extracted from <script src=...> tags in page HTML
#   - Element Plus generates predictable CSS: el-input__inner, el-button, etc.
#   - Meta description confirms 视频上传 + 发布笔记 support
#
# Tech-stack-informed (headed-browser verification pending):
#   - Element Plus selectors are derived from known class conventions
#   - Login component selectors (custom Vue, not Element Plus)
#   - Upload progress indicators use Element Plus patterns (.el-progress, .el-upload-list)
#   - Shepherd.js tours may block interactions; dismiss with "我知道了"
#
# Known risks (headed Chrome needed to verify):
#   - XHS may show phone-verification / captcha during login
#   - Scheduled publish verified 2026-05-29: upload page renders
#     "更多设置 -> 定时发布" as a d-switch, then a d-datepicker input.
#   - Exact publish-button state transitions (disabled → enabled) need real-browser observation
#   - Cover/thumbnail upload path: cropper.js is bundled but usage TBD
# ──────────────────────────────────────────────────────────────────────

UPLOAD_URL = "https://creator.xiaohongshu.com/publish/publish"
CREATOR_HOME_URL = "https://creator.xiaohongshu.com/"
LOGIN_URL = "https://creator.xiaohongshu.com/login"
LOGIN_DONE_URL_PREFIX = "https://creator.xiaohongshu.com/"
MANAGE_URL_PREFIX = "https://creator.xiaohongshu.com/publish/manage"

# ── Text labels (used with get_by_text) ─────────────────────────────
TEXT_LOGIN_PHONE = "手机号登录"
TEXT_LOGIN_SMS = "短信登录"
TEXT_LOGIN_SCAN = "扫码登录"
TEXT_LOGIN_QR_TITLE = "APP扫一扫登录"
TEXT_LOGIN_QR_AGREEMENT = "扫码即同意"
TEXT_QRCODE_EXPIRED = "二维码已过期"
TEXT_GOT_IT = "我知道了"
TEXT_PUBLISH = "发布"
TEXT_PUBLISH_NOTE = "发布笔记"
TEXT_PUBLISH_SUCCESS = "发布成功"
TEXT_SAVE_DRAFT = "暂存离开"
TEXT_UPLOAD_VIDEO = "上传视频"
TEXT_UPLOADING = "上传中"
TEXT_UPLOAD_SUCCESS = "上传成功"
TEXT_DONE = "完成"
TEXT_CONFIRM = "确定"

# ── Login page ──────────────────────────────────────────────────────
# The login page uses a custom Vue component. The QR code is typically
# rendered inside a dedicated container div.
QRCODE_IMG = 'img[alt="二维码"], .qrcode-img img, canvas.qrcode-canvas'
LOGIN_CONTAINER = '.login-container, .qrcode-wrapper'
SCAN_TAB = f'div:has-text("{TEXT_LOGIN_SCAN}"), span:has-text("{TEXT_LOGIN_SCAN}")'
# Current XHS creator login defaults to SMS login. QR login is opened by a
# corner image inside the SSO wrapper, without stable alt text or button label.
QR_LOGIN_SWITCH = '.sso-login-wrapper img[src^="data:image/"]'

# ── Upload page: video input ────────────────────────────────────────
# Element Plus el-upload wraps a native file input. XHS has changed this
# several times: some versions use accept="video/*", while others use only
# extension lists such as .mp4/.mov. We mark the best runtime candidate in
# pages.py and then target it here.
UPLOAD_VIDEO_INPUT_MARKER = '[data-vl-xhs-video-input="1"]'
UPLOAD_VIDEO_INPUT = (
    f'{UPLOAD_VIDEO_INPUT_MARKER}, '
    '.el-upload input[type="file"][accept*="video"], '
    'input[type="file"][accept*="video"], '
    '.el-upload input[type="file"][accept*=".mp4"], '
    'input[type="file"][accept*=".mp4"], '
    '.el-upload input[type="file"][accept*=".mov"], '
    'input[type="file"][accept*=".mov"], '
    '.el-upload input[type="file"], '
    'input[type="file"]'
)

# ── Upload page: title ──────────────────────────────────────────────
# Element Plus input: .el-input__inner inside .el-input wrapper.
TITLE_INPUT = (
    '[data-vl-xhs-title-input="1"], '
    '.el-input__inner[placeholder*="标题"], '
    'input[placeholder*="填写标题"], '
    'input[placeholder*="标题"], '
    'input.el-input__inner'
)
TITLE_INPUT_MARKER = '[data-vl-xhs-title-input="1"]'

# ── Upload page: content / description ──────────────────────────────
# Element Plus textarea or a rich-text contenteditable div.
CONTENT_EDITOR = (
    '[data-vl-xhs-content-editor="1"], '
    '.el-textarea__inner[placeholder*="正文"], '
    'textarea[placeholder*="正文描述"], '
    'textarea[placeholder*="正文"], '
    '[contenteditable="true"][placeholder*="正文"], '
    '[contenteditable="true"][data-placeholder*="正文"], '
    '[contenteditable="true"][aria-label*="正文"], '
    '[role="textbox"][aria-label*="正文"]'
)
CONTENT_EDITOR_MARKER = '[data-vl-xhs-content-editor="1"]'

# ── Upload page: tags / topics ──────────────────────────────────────
# Element Plus el-select with filterable, or a dedicated tag input.
TAG_INPUT = (
    '.el-select__input[placeholder*="话题"], '
    'input[class*="topic"][placeholder*="话题"], '
    'input[placeholder*="话题"]'
)
TAG_RESULT = (
    '.tippy-box [role="option"], '
    '.tippy-content [role="option"], '
    '.tippy-box [class*="topic"], '
    '.tippy-content [class*="topic"], '
    '.tippy-box [class*="item"], '
    '.tippy-content [class*="item"], '
    '.el-select-dropdown__item, '
    '.el-select-dropdown__wrap [class*="item"], '
    'div[class*="topic-result"], div[class*="topic-list"]'
)

# ── Upload page: publish button ─────────────────────────────────────
# Element Plus primary button. XHS may use "发布" or "发布笔记".
PUBLISH_BUTTON = (
    'button.el-button--primary:has-text("发布"), '
    'button:has-text("发布笔记"), '
    'button:has-text("发布")'
)
SAVE_DRAFT_BUTTON = (
    '[role="button"]:has-text("暂存离开"), '
    '[role="button"]:has-text("保存草稿"), '
    '.el-button:has-text("暂存离开"), '
    '.el-button:has-text("保存草稿"), '
    'button:has-text("暂存离开"), '
    'button:has-text("暂存"), '
    'button:has-text("保存草稿")'
)

SCHEDULE_SWITCH = (
    '.post-time-switch-container .d-switch, '
    '.post-time-switch-container [role="switch"], '
    '.post-time-switch-container input[type="checkbox"], '
    '.post-time-switch-container:has-text("定时发布")'
)
SCHEDULE_DATETIME_INPUT = (
    '.date-picker-container input, '
    '.post-time-wrapper input.d-text, '
    'input[placeholder*="发布时间"], '
    'input[placeholder*="选择日期"]'
)

# ── Upload status indicators ────────────────────────────────────────
VIDEO_UPLOADED_MARKER = (
    'div[class*="upload-success"], '
    '[class*="upload-done"], '
    '.el-upload-list__item.is-success'
)
VIDEO_UPLOAD_FAILED = (
    '.el-upload-list__item.is-fail, '
    'div[class*="upload-fail"], '
    'div[class*="error"]:has-text("失败")'
)
VIDEO_UPLOADING_INDICATOR = (
    '.el-progress, '
    'div[class*="uploading"], '
    'span[class*="progress"]:has-text("上传")'
)
