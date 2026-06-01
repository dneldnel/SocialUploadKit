from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from social_upload.browser.base import find_system_chrome_executable
from social_upload.browser.settings import SUPPORTED_SOCIAL_BROWSERS, browser_health, get_social_browser
from social_upload.platforms.douyin.login import resolve_account_file as resolve_douyin_account_file
from social_upload.platforms.douyin.models import (
    DouyinVideoUploadRequest,
    DouyinVisibility,
)
from social_upload.platforms.douyin.models import UploadMode as DouyinUploadMode
from social_upload.platforms.douyin.models import UploadStatusEvent as DouyinUploadStatusEvent
from social_upload.platforms.douyin.models import parse_publish_at, parse_tags
from social_upload.platforms.douyin.workflow import DouyinVideoUploadWorkflow, check_douyin_cookie, login_douyin
from social_upload.platforms.xhs.login import resolve_account_file as resolve_xhs_account_file
from social_upload.platforms.xhs.models import UploadMode as XhsUploadMode
from social_upload.platforms.xhs.models import UploadStatusEvent as XhsUploadStatusEvent
from social_upload.platforms.xhs.models import XhsVideoUploadRequest, parse_publish_at as parse_xhs_publish_at, parse_tags as parse_xhs_tags
from social_upload.platforms.xhs.workflow import XhsUploadWorkflow, check_xhs_cookie, login_xhs


def existing_file(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"文件不存在: {value}")
    return path


def add_browser_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--browser", choices=SUPPORTED_SOCIAL_BROWSERS, default=None, help="默认使用 cloakbrowser，可切换 patchright/playwright")
    headless_group = parser.add_mutually_exclusive_group()
    headless_group.add_argument("--headless", dest="headless", action="store_true", help="后台无头运行")
    headless_group.add_argument("--headed", dest="headless", action="store_false", help="打开可见浏览器窗口")
    parser.set_defaults(headless=True)
    parser.add_argument("--chrome-path", help="显式指定本机 Chrome 可执行文件路径")
    parser.add_argument("--downloaded-browser", action="store_true", help="不强制使用系统 Chrome，交给浏览器库默认浏览器")


def add_runtime_dir_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--runtime-dir", default=".social_upload", help="账号 cookie、二维码和截图的运行时目录")


def configure_runtime_browser_env(runtime_dir: str | Path) -> Path:
    root = Path(runtime_dir).expanduser().resolve()
    os.environ["SOCIAL_UPLOAD_CLOAKBROWSER_CACHE_DIR"] = str(root / "cloakbrowser")
    os.environ["SOCIAL_UPLOAD_CLOAKBROWSER_PROFILE_ROOT"] = str(root / "browser_profiles")
    return root


def _add_douyin_subparser(sub: argparse._SubParsersAction) -> None:
    douyin = sub.add_parser("douyin", help="抖音上传/登录")
    actions = douyin.add_subparsers(dest="action", required=True)

    login = actions.add_parser("login", help="扫码登录并保存 cookie")
    login.add_argument("--account", required=True)
    add_runtime_dir_arg(login)
    add_browser_flags(login)

    check = actions.add_parser("check", help="检查 cookie 是否有效")
    check.add_argument("--account", required=True)
    add_runtime_dir_arg(check)
    add_browser_flags(check)

    chrome = actions.add_parser("chrome", help="显示当前会优先使用的系统 Chrome")
    chrome.set_defaults(action="chrome")

    browser = actions.add_parser("browser", help="检测当前社媒发布浏览器")
    browser.add_argument("--browser", choices=SUPPORTED_SOCIAL_BROWSERS, default=None)
    add_runtime_dir_arg(browser)

    upload = actions.add_parser("upload-video", help="上传抖音视频；默认草稿模式，不点击发布")
    upload.add_argument("--account", required=True)
    upload.add_argument("--file", required=True, type=existing_file)
    upload.add_argument("--title", required=True)
    upload.add_argument("--desc", default="")
    upload.add_argument("--tags", default="")
    upload.add_argument("--thumbnail", type=existing_file)
    upload.add_argument("--schedule", help="定时发布时间，格式 YYYY-MM-DD HH:MM")
    upload.add_argument("--visibility", choices=[item.value for item in DouyinVisibility], default=DouyinVisibility.PUBLIC.value, help="作品可见性：public=公开，private=仅自己可见")
    upload.add_argument("--product-link", default="")
    upload.add_argument("--product-title", default="")
    upload.add_argument("--mode", choices=[mode.value for mode in DouyinUploadMode], default=DouyinUploadMode.DRAFT.value)
    upload.add_argument("--keep-open-seconds", type=int, default=0, help="草稿模式完成后保留浏览器秒数，便于人工确认")
    upload.add_argument("--dry-run", action="store_true", help="只校验参数和文件，不打开浏览器，不上传")
    upload.add_argument("--debug", action="store_true")
    add_runtime_dir_arg(upload)
    add_browser_flags(upload)


def _add_xhs_subparser(sub: argparse._SubParsersAction) -> None:
    xhs = sub.add_parser("xhs", help="小红书上传/登录")
    actions = xhs.add_subparsers(dest="action", required=True)

    login = actions.add_parser("login", help="扫码登录并保存 cookie")
    login.add_argument("--account", required=True)
    add_runtime_dir_arg(login)
    add_browser_flags(login)

    check = actions.add_parser("check", help="检查 cookie 是否有效")
    check.add_argument("--account", required=True)
    add_runtime_dir_arg(check)
    add_browser_flags(check)

    chrome = actions.add_parser("chrome", help="显示当前会优先使用的系统 Chrome")
    chrome.set_defaults(action="chrome")

    browser = actions.add_parser("browser", help="检测当前社媒发布浏览器")
    browser.add_argument("--browser", choices=SUPPORTED_SOCIAL_BROWSERS, default=None)
    add_runtime_dir_arg(browser)

    upload = actions.add_parser("upload-video", help="上传小红书视频；默认草稿模式，不点击发布")
    upload.add_argument("--account", required=True)
    upload.add_argument("--file", required=True, type=existing_file)
    upload.add_argument("--title", required=True)
    upload.add_argument("--desc", default="")
    upload.add_argument("--tags", default="")
    upload.add_argument("--schedule", help="定时发布时间，格式 YYYY-MM-DD HH:MM；会切换为发布模式")
    upload.add_argument("--mode", choices=[mode.value for mode in XhsUploadMode], default=XhsUploadMode.DRAFT.value)
    upload.add_argument("--keep-open-seconds", type=int, default=0, help="草稿模式完成后保留浏览器秒数，便于人工确认")
    upload.add_argument("--dry-run", action="store_true", help="只校验参数和文件，不打开浏览器，不上传")
    upload.add_argument("--debug", action="store_true")
    add_runtime_dir_arg(upload)
    add_browser_flags(upload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m social_upload.cli.sau_cli")
    sub = parser.add_subparsers(dest="platform", required=True)
    _add_douyin_subparser(sub)
    _add_xhs_subparser(sub)
    return parser


def print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)


async def _dispatch_douyin(args: argparse.Namespace) -> int:
    if args.action == "chrome":
        print_json({"system_chrome": find_system_chrome_executable()})
        return 0
    if args.action == "browser":
        configure_runtime_browser_env(getattr(args, "runtime_dir", ".social_upload"))
        health = browser_health(getattr(args, "browser", None))
        print_json(health)
        return 0 if health.get("ok") else 1

    runtime_dir = configure_runtime_browser_env(args.runtime_dir)
    account_file = resolve_douyin_account_file(args.account, runtime_dir)
    use_system_chrome = not getattr(args, "downloaded_browser", False)
    executable_path = getattr(args, "chrome_path", None)
    browser = get_social_browser(getattr(args, "browser", None))

    if args.action == "login":
        result = await login_douyin(
            account_file,
            browser=browser,
            headless=args.headless,
            use_system_chrome=use_system_chrome,
            executable_path=executable_path,
            on_event=lambda event: print_json({"event": event.to_dict()}),
        )
        print_json(result)
        return 0 if result.get("success") else 1

    if args.action == "check":
        valid = await check_douyin_cookie(
            account_file,
            browser=browser,
            headless=True,
            use_system_chrome=use_system_chrome,
            executable_path=executable_path,
        )
        print_json({"valid": valid, "account_file": str(account_file)})
        return 0 if valid else 1

    if args.action == "upload-video":
        async def on_event(event: DouyinUploadStatusEvent) -> None:
            print_json({"event": event.to_dict()})

        request = DouyinVideoUploadRequest(
            account_name=args.account,
            video_file=args.file,
            title=args.title,
            description=args.desc,
            tags=parse_tags(args.tags),
            mode=DouyinUploadMode(args.mode),
            account_file=account_file,
            thumbnail_file=getattr(args, "thumbnail", None),
            publish_at=parse_publish_at(getattr(args, "schedule", None)),
            visibility=DouyinVisibility(getattr(args, "visibility", "public")),
            product_link=getattr(args, "product_link", ""),
            product_title=getattr(args, "product_title", ""),
            browser=browser,
            headless=args.headless,
            use_system_chrome=use_system_chrome,
            executable_path=executable_path,
            keep_open_seconds=args.keep_open_seconds,
            debug=getattr(args, "debug", False),
            dry_run=args.dry_run,
        )
        result = await DouyinVideoUploadWorkflow(request, on_event=on_event).run()
        print_json({"result": result.to_dict()})
        return 0 if result.success else 1

    raise RuntimeError(f"不支持的抖音动作: {args.action}")


async def _dispatch_xhs(args: argparse.Namespace) -> int:
    if args.action == "chrome":
        print_json({"system_chrome": find_system_chrome_executable()})
        return 0
    if args.action == "browser":
        configure_runtime_browser_env(getattr(args, "runtime_dir", ".social_upload"))
        health = browser_health(getattr(args, "browser", None))
        print_json(health)
        return 0 if health.get("ok") else 1

    runtime_dir = configure_runtime_browser_env(args.runtime_dir)
    account_file = resolve_xhs_account_file(args.account, runtime_dir)
    use_system_chrome = not getattr(args, "downloaded_browser", False)
    executable_path = getattr(args, "chrome_path", None)
    browser = get_social_browser(getattr(args, "browser", None))

    if args.action == "login":
        result = await login_xhs(
            account_file,
            browser=browser,
            headless=args.headless,
            use_system_chrome=use_system_chrome,
            executable_path=executable_path,
            on_event=lambda event: print_json({"event": event.to_dict()}),
        )
        print_json(result)
        return 0 if result.get("success") else 1

    if args.action == "check":
        valid = await check_xhs_cookie(
            account_file,
            browser=browser,
            headless=True,
            use_system_chrome=use_system_chrome,
            executable_path=executable_path,
        )
        print_json({"valid": valid, "account_file": str(account_file)})
        return 0 if valid else 1

    if args.action == "upload-video":
        async def on_event(event: XhsUploadStatusEvent) -> None:
            print_json({"event": event.to_dict()})

        request = XhsVideoUploadRequest(
            account_name=args.account,
            video_file=args.file,
            title=args.title,
            description=args.desc,
            tags=parse_xhs_tags(args.tags),
            mode=XhsUploadMode.PUBLISH if args.schedule else XhsUploadMode(args.mode),
            account_file=account_file,
            publish_at=parse_xhs_publish_at(getattr(args, "schedule", None)),
            browser=browser,
            headless=args.headless,
            use_system_chrome=use_system_chrome,
            executable_path=executable_path,
            keep_open_seconds=args.keep_open_seconds,
            debug=getattr(args, "debug", False),
            dry_run=args.dry_run,
        )
        result = await XhsUploadWorkflow(request, on_event=on_event).run()
        print_json({"result": result.to_dict()})
        return 0 if result.success else 1

    raise RuntimeError(f"不支持的小红书动作: {args.action}")


async def dispatch(args: argparse.Namespace) -> int:
    if args.platform == "douyin":
        return await _dispatch_douyin(args)
    if args.platform == "xhs":
        return await _dispatch_xhs(args)
    raise RuntimeError(f"不支持的平台: {args.platform}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        code = asyncio.run(dispatch(args))
    except Exception as exc:
        print_json({"error": str(exc), "type": exc.__class__.__name__})
        code = 1
    raise SystemExit(code)


if __name__ == "__main__":
    main()
