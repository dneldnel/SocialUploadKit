from __future__ import annotations

import importlib.util
import os
import hashlib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOCIAL_BROWSER = "cloakbrowser"
SUPPORTED_SOCIAL_BROWSERS = ("cloakbrowser", "patchright", "playwright")
DEFAULT_CLOAKBROWSER_CACHE_DIR = REPO_ROOT / ".social_upload" / "cloakbrowser"
DEFAULT_CLOAKBROWSER_PROFILE_ROOT = REPO_ROOT / ".social_upload" / "browser_profiles"


def normalize_social_browser(browser: str | None = None) -> str:
    value = (browser or "").strip().lower()
    if not value:
        value = DEFAULT_SOCIAL_BROWSER
    if value not in SUPPORTED_SOCIAL_BROWSERS:
        raise ValueError(f"不支持的 browser: {browser}")
    return value


def _load_config_value(key: str) -> Any:
    try:
        from core.config_utils import load_global_key
    except Exception:
        return None
    try:
        return load_global_key(key)
    except Exception:
        return None


def get_social_browser(override: str | None = None) -> str:
    return normalize_social_browser(
        override
        or os.environ.get("SOCIAL_UPLOAD_BROWSER")
        or _load_config_value("social_upload.browser")
        or DEFAULT_SOCIAL_BROWSER
    )


def get_cloakbrowser_cache_dir() -> Path:
    configured = (
        os.environ.get("SOCIAL_UPLOAD_CLOAKBROWSER_CACHE_DIR")
        or os.environ.get("CLOAKBROWSER_CACHE_DIR")
        or _load_config_value("social_upload.cloakbrowser_cache_dir")
    )
    raw = str(configured or DEFAULT_CLOAKBROWSER_CACHE_DIR).strip()
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def _project_path_config(key: str, default: Path) -> Path:
    configured = _load_config_value(key)
    raw = str(configured or default).strip()
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = REPO_ROOT / path
    resolved = path.resolve()
    try:
        resolved.relative_to(REPO_ROOT)
    except ValueError:
        return default.resolve()
    return resolved


def get_cloakbrowser_profile_root() -> Path:
    configured = os.environ.get("SOCIAL_UPLOAD_CLOAKBROWSER_PROFILE_ROOT")
    if configured:
        path = Path(configured).expanduser()
        return (path if path.is_absolute() else REPO_ROOT / path).resolve()
    return _project_path_config("social_upload.cloakbrowser_profile_root", DEFAULT_CLOAKBROWSER_PROFILE_ROOT)


def get_cloakbrowser_locale() -> str | None:
    value = os.environ.get("SOCIAL_UPLOAD_CLOAKBROWSER_LOCALE") or _load_config_value("social_upload.cloakbrowser_locale")
    return str(value or "zh-CN").strip() or None


def get_cloakbrowser_timezone() -> str | None:
    value = os.environ.get("SOCIAL_UPLOAD_CLOAKBROWSER_TIMEZONE") or _load_config_value("social_upload.cloakbrowser_timezone")
    return str(value or "Asia/Shanghai").strip() or None


def use_cloakbrowser_persistent_profiles() -> bool:
    value = os.environ.get("SOCIAL_UPLOAD_CLOAKBROWSER_PERSISTENT_PROFILES")
    if value is not None:
        return value.strip().lower() in {"1", "true", "yes", "on"}
    value = _load_config_value("social_upload.cloakbrowser_persistent_profiles")
    return bool(False if value is None else value)


def sanitize_profile_name(profile_name: str | None) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(profile_name or "").strip())
    return safe or "default"


def stable_fingerprint_seed(profile_name: str | None) -> int:
    digest = hashlib.sha256(sanitize_profile_name(profile_name).encode("utf-8")).hexdigest()
    return 10000 + (int(digest[:12], 16) % 90000)


def get_cloakbrowser_profile_dir(profile_name: str | None) -> Path:
    return (get_cloakbrowser_profile_root() / sanitize_profile_name(profile_name)).resolve()


def cloakbrowser_predownload_command() -> str:
    cache_dir = get_cloakbrowser_cache_dir()
    return (
        f'CLOAKBROWSER_CACHE_DIR="{cache_dir}" '
        "CLOAKBROWSER_AUTO_UPDATE=false "
        "python -m cloakbrowser install"
    )


def configure_cloakbrowser_environment() -> Path:
    cache_dir = get_cloakbrowser_cache_dir()
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ["CLOAKBROWSER_CACHE_DIR"] = str(cache_dir)
    os.environ.pop("CLOAKBROWSER_BINARY_PATH", None)
    os.environ.setdefault("CLOAKBROWSER_AUTO_UPDATE", "false")
    return cache_dir


def browser_health(browser: str | None = None) -> dict[str, Any]:
    selected = get_social_browser(browser)
    result: dict[str, Any] = {
        "browser": selected,
        "ok": False,
        "package_installed": False,
    }
    if selected == "cloakbrowser":
        cache_dir = configure_cloakbrowser_environment()
        result.update(
            {
                "cache_dir": str(cache_dir),
                "predownload_command": cloakbrowser_predownload_command(),
                "profile_root": str(get_cloakbrowser_profile_root()),
                "persistent_profiles": use_cloakbrowser_persistent_profiles(),
                "timezone": get_cloakbrowser_timezone(),
                "locale": get_cloakbrowser_locale(),
            }
        )
        if importlib.util.find_spec("cloakbrowser") is None:
            result["message"] = "未安装 Python 包 cloakbrowser"
            return result
        result["package_installed"] = True
        try:
            from cloakbrowser import binary_info

            info = binary_info()
            result["binary_info"] = info
            result["ok"] = bool(info.get("installed"))
            result["message"] = "CloakBrowser 可用" if result["ok"] else "CloakBrowser 二进制尚未预下载"
        except Exception as exc:
            result["message"] = f"检测 CloakBrowser 失败: {type(exc).__name__}: {exc}"
        return result

    if importlib.util.find_spec(selected) is None:
        result["message"] = f"未安装 Python 包 {selected}"
        return result
    result["package_installed"] = True
    result["ok"] = True
    result["message"] = f"{selected} Python 包已安装"
    return result
