from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Coroutine

from social_upload.browser.settings import DEFAULT_SOCIAL_BROWSER

SUPPORTED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".webm", ".flv", ".wmv"}
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
MIN_SCHEDULE_LEAD_TIME = timedelta(hours=2)
StatusCallback = Callable[["UploadStatusEvent"], Coroutine[Any, Any, None] | None]


class UploadMode(str, Enum):
    DRAFT = "draft"
    PUBLISH = "publish"


class DouyinVisibility(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"


class UploadStage(str, Enum):
    VALIDATING = "validating"
    AUTH_CHECK = "auth_check"
    LOGIN_QRCODE = "login_qrcode"
    NAVIGATING = "navigating"
    UPLOADING = "uploading"
    FILLING_METADATA = "filling_metadata"
    WAITING_UPLOAD = "waiting_upload"
    SETTING_COVER = "setting_cover"
    SETTING_VISIBILITY = "setting_visibility"
    SETTING_SCHEDULE = "setting_schedule"
    DRAFT_READY = "draft_ready"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


@dataclass(slots=True)
class UploadStatusEvent:
    stage: UploadStage
    message: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"stage": self.stage.value, "message": self.message, "data": self.data}


@dataclass(slots=True)
class UploadResult:
    success: bool
    stage: UploadStage
    message: str
    mode: UploadMode = UploadMode.DRAFT
    account_file: Path | None = None
    screenshot_path: Path | None = None
    current_url: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "stage": self.stage.value,
            "message": self.message,
            "mode": self.mode.value,
            "account_file": str(self.account_file) if self.account_file else None,
            "screenshot_path": str(self.screenshot_path) if self.screenshot_path else None,
            "current_url": self.current_url,
            "error": self.error,
        }


@dataclass(slots=True)
class DouyinVideoUploadRequest:
    account_name: str
    video_file: Path
    title: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    mode: UploadMode = UploadMode.DRAFT
    account_file: Path | None = None
    thumbnail_file: Path | None = None
    publish_at: datetime | None = None
    visibility: DouyinVisibility = DouyinVisibility.PUBLIC
    product_link: str = ""
    product_title: str = ""
    browser: str = DEFAULT_SOCIAL_BROWSER
    headless: bool = True
    use_system_chrome: bool = True
    executable_path: str | None = None
    keep_open_seconds: int = 0
    debug: bool = True
    dry_run: bool = False

    def validate(self) -> None:
        if not self.account_name.strip():
            raise ValueError("account_name 必填")
        if not self.title.strip():
            raise ValueError("title 必填")

        self.video_file = Path(self.video_file).expanduser().resolve()
        if not self.video_file.is_file():
            raise FileNotFoundError(f"视频文件不存在: {self.video_file}")
        if self.video_file.suffix.lower() not in SUPPORTED_VIDEO_EXTENSIONS:
            raise ValueError(f"不支持的视频格式: {self.video_file.suffix}")

        if self.thumbnail_file:
            self.thumbnail_file = Path(self.thumbnail_file).expanduser().resolve()
            if not self.thumbnail_file.is_file():
                raise FileNotFoundError(f"封面图片不存在: {self.thumbnail_file}")
            if self.thumbnail_file.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
                raise ValueError(f"不支持的封面格式: {self.thumbnail_file.suffix}")

        if self.publish_at:
            now = datetime.now(tz=self.publish_at.tzinfo) if self.publish_at.tzinfo else datetime.now()
            if self.publish_at <= now + MIN_SCHEDULE_LEAD_TIME:
                raise ValueError("抖音定时发布必须晚于当前时间 2 小时以上")

        if isinstance(self.mode, str):
            self.mode = UploadMode(self.mode)
        if isinstance(self.visibility, str):
            self.visibility = DouyinVisibility(self.visibility)


def parse_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip().lstrip("#") for item in raw.split(",") if item.strip().lstrip("#")]


def parse_publish_at(raw: str | None) -> datetime | None:
    if not raw:
        return None
    return datetime.strptime(raw, "%Y-%m-%d %H:%M")
