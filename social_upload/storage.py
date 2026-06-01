from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SUPPORTED_PLATFORMS = {"douyin", "xhs"}


def normalize_platform(platform: str) -> str:
    value = str(platform or "").strip().lower()
    if value not in SUPPORTED_PLATFORMS:
        raise ValueError(f"不支持的平台: {platform}; supported={sorted(SUPPORTED_PLATFORMS)}")
    return value


def safe_account_name(account_name: str) -> str:
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in account_name.strip())
    if not safe_name:
        raise ValueError("account_name 不能为空")
    return safe_name


@dataclass(slots=True)
class CookieStorage:
    """Filesystem cookie storage used by all project adapters.

    Layout:
        <runtime_dir>/cookies/douyin_<account>.json
        <runtime_dir>/cookies/xhs_<account>.json
        <runtime_dir>/screenshots/*.png
    """

    runtime_dir: Path | str = ".social_upload"

    def __post_init__(self) -> None:
        self.runtime_dir = Path(self.runtime_dir).expanduser().resolve()

    @property
    def cookies_dir(self) -> Path:
        path = Path(self.runtime_dir) / "cookies"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def screenshots_dir(self) -> Path:
        path = Path(self.runtime_dir) / "screenshots"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def account_file(self, platform: str, account_name: str) -> Path:
        platform = normalize_platform(platform)
        return self.cookies_dir / f"{platform}_{safe_account_name(account_name)}.json"

    def list_accounts(self, platform: str) -> list[str]:
        platform = normalize_platform(platform)
        prefix = f"{platform}_"
        result: list[str] = []
        for path in sorted(self.cookies_dir.glob(f"{prefix}*.json")):
            result.append(path.stem[len(prefix):])
        return result

    def has_account(self, platform: str, account_name: str) -> bool:
        return self.account_file(platform, account_name).is_file()

    def delete_account(self, platform: str, account_name: str) -> bool:
        path = self.account_file(platform, account_name)
        if not path.exists():
            return False
        path.unlink()
        return True
