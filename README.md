# social-upload-kit

抖音 / 小红书多账号上传工具库。

目标：把"登录、cookie、多账号、浏览器自动化上传"沉淀成独立库；每个业务项目只通过 adapter 把自己的视频、标题、正文、标签和结果状态接进来。

---

## 1. 能力边界

### 本库负责

- 抖音登录、扫码二维码保存、cookie 保存
- 小红书登录、扫码二维码保存、cookie 保存
- cookie 有效性检查
- 多平台 + 多账号隔离
- 上传视频到抖音 / 小红书
- 填写标题、正文、标签
- 抖音封面、可见性、商品链接、定时发布参数
- 小红书草稿 / 发布 / 定时发布基础流程
- 返回结构化事件和结构化结果
- 可配置运行时目录：cookies、二维码、截图都落在调用方指定目录

### 本库不负责

这些应该由业务项目 adapter 处理：

- 从业务项目数据库或 manifest 里找视频
- 生成标题、正文、标签
- 判断项目是否已完成、文件是否可发布
- 业务发布队列
- WebUI 页面、按钮、弹窗、轮询
- 把结果写回业务项目数据库 / JSON / 状态机
- 重试策略、并发调度、审计日志



---

## 2. 目录结构

```text
social-upload-kit/
  pyproject.toml
  README.md
  examples/
    minimal_upload.py
  social_upload/
    __init__.py
    client.py             # 项目无关高级 API：SocialUploadClient
    storage.py            # CookieStorage：runtime_dir / cookies / screenshots
    browser/
      base.py
      factory.py
      settings.py
      cloakbrowser_adapter.py
      patchright_adapter.py
      playwright_adapter.py
    platforms/
      douyin/
        login.py
        models.py
        pages.py
        selectors.py
        workflow.py
      xhs/
        login.py
        models.py
        pages.py
        selectors.py
        workflow.py
    cli/
      sau_cli.py
```

核心分层：

```text
业务项目 adapter
  -> SocialUploadClient / CLI
    -> platform workflow
      -> page object
        -> browser adapter
          -> cloakbrowser / patchright / playwright
```

---

## 3. 安装

### 3.1 本地开发安装

```bash
cd /path/to/social-upload-kit
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

默认依赖 `cloakbrowser` 与 `patchright`：

- `cloakbrowser`：默认浏览器，使用 patched Chromium 和稳定 fingerprint seed；二进制缓存固定在项目运行时目录内。
- `patchright`：fallback。
- `playwright`：可选 fallback。

建议先预下载 CloakBrowser 二进制，避免第一次上传时临时下载：

```bash
CLOAKBROWSER_CACHE_DIR="$PWD/.social_upload/cloakbrowser" \
CLOAKBROWSER_AUTO_UPDATE=false \
python -m cloakbrowser install
```

### 3.2 可选 Playwright fallback

```bash
pip install -e '.[playwright]'
```

### 3.3 检查浏览器

检查默认社媒发布浏览器：

```bash
social-upload douyin browser
social-upload xhs browser
```

强制检查某个 adapter：

```bash
social-upload xhs browser --browser cloakbrowser
social-upload xhs browser --browser patchright
```

检查系统 Chrome fallback：

```bash
social-upload douyin chrome
social-upload xhs chrome
```

也可以直接用模块入口：

```bash
python -m social_upload.cli.sau_cli douyin browser
```

---

## 4. 运行时目录和多账号

本库默认使用当前工作目录下的：

```text
.social_upload/
  cookies/
    douyin_<account>.json
    xhs_<account>.json
  screenshots/
    *.png
```

推荐每个业务项目显式传自己的 runtime/storage 目录：

```python
client = SocialUploadClient(storage_dir="/path/to/your-project/.social_upload")
```

CLI 对应参数：

```bash
social-upload xhs login --account main --runtime-dir /path/to/your-project/.social_upload --headed
```

账号隔离规则：

```text
platform + account_name -> 独立 cookie 文件
```

示例：

```text
.social_upload/cookies/douyin_my_account.json
.social_upload/cookies/douyin_华尔街小喇叭.json
.social_upload/cookies/xhs_my_account.json
```

注意：`.social_upload/` 是敏感运行时目录，必须加入业务项目 `.gitignore`。

---

## 4.1 CloakBrowser 说明

默认使用 `cloakbrowser`，`patchright` 和 `playwright` 作为 fallback。

运行时相关目录：

```text
<runtime-dir>/cloakbrowser/       # CloakBrowser patched Chromium 缓存
<runtime-dir>/browser_profiles/   # 预留 persistent profile 目录
<runtime-dir>/cookies/            # storage_state cookies
<runtime-dir>/screenshots/        # 上传/发布截图
```

当前默认仍以 `storage_state` cookie 文件为主，persistent profile 默认关闭，以降低从旧链路迁移的风险。每个账号会使用稳定的 `profile_name` / fingerprint seed：

```text
profile_name = <platform>_<account> cookie 文件 stem
```

可通过环境变量临时切换浏览器：

```bash
SOCIAL_UPLOAD_BROWSER=patchright social-upload xhs browser
SOCIAL_UPLOAD_BROWSER=cloakbrowser social-upload xhs browser
```

业务项目也可以在自己的配置系统里提供这些 key；如果没有配置系统，库会使用默认值：

```yaml
social_upload:
  browser: cloakbrowser
  cloakbrowser_cache_dir: .social_upload/cloakbrowser
  cloakbrowser_profile_root: .social_upload/browser_profiles
  cloakbrowser_persistent_profiles: false
  cloakbrowser_timezone: Asia/Shanghai
  cloakbrowser_locale: zh-CN
```

---

## 5. CLI 用法

### 5.1 登录

抖音：

```bash
social-upload douyin login \
  --account my_account \
  --runtime-dir /path/to/project/.social_upload \
  --headed
```

小红书：

```bash
social-upload xhs login \
  --account my_account \
  --runtime-dir /path/to/project/.social_upload \
  --headed
```

登录时会把二维码截图保存到：

```text
<runtime-dir>/cookies/<platform>_<account>_login_qrcode_YYYYmmdd_HHMMSS.png
```

### 5.2 检查 cookie

```bash
social-upload douyin check \
  --account my_account \
  --runtime-dir /path/to/project/.social_upload

social-upload xhs check \
  --account my_account \
  --runtime-dir /path/to/project/.social_upload
```

### 5.3 dry-run 上传

只校验参数和本地文件，不打开浏览器、不真正上传：

```bash
social-upload xhs upload-video \
  --account my_account \
  --runtime-dir /path/to/project/.social_upload \
  --file /absolute/path/to/video.mp4 \
  --title "标题" \
  --desc "正文" \
  --tags "财经,AI" \
  --mode draft \
  --dry-run
```

### 5.4 草稿模式上传

```bash
social-upload douyin upload-video \
  --account my_account \
  --runtime-dir /path/to/project/.social_upload \
  --file /absolute/path/to/video.mp4 \
  --thumbnail /absolute/path/to/cover.jpg \
  --title "标题" \
  --desc "正文" \
  --tags "财经,AI" \
  --visibility public \
  --mode draft \
  --headed \
  --keep-open-seconds 30
```

```bash
social-upload xhs upload-video \
  --account my_account \
  --runtime-dir /path/to/project/.social_upload \
  --file /absolute/path/to/video.mp4 \
  --title "标题" \
  --desc "正文" \
  --tags "财经,AI" \
  --mode draft \
  --headed \
  --keep-open-seconds 30
```

### 5.5 发布 / 定时发布

抖音立即发布：

```bash
social-upload douyin upload-video \
  --account my_account \
  --runtime-dir /path/to/project/.social_upload \
  --file /absolute/path/to/video.mp4 \
  --title "标题" \
  --desc "正文" \
  --tags "财经,AI" \
  --mode publish
```

抖音定时发布：

```bash
social-upload douyin upload-video \
  --account my_account \
  --runtime-dir /path/to/project/.social_upload \
  --file /absolute/path/to/video.mp4 \
  --title "标题" \
  --desc "正文" \
  --tags "财经,AI" \
  --mode publish \
  --schedule "2026-06-01 20:00"
```

小红书定时发布：

```bash
social-upload xhs upload-video \
  --account my_account \
  --runtime-dir /path/to/project/.social_upload \
  --file /absolute/path/to/video.mp4 \
  --title "标题" \
  --desc "正文" \
  --tags "财经,AI" \
  --mode publish \
  --schedule "2026-06-01 20:00"
```

安全建议：新接入项目先只开放 `draft`，确认链路稳定后再开放 `publish`。

---

## 6. Python API

### 6.1 创建 client

```python
from social_upload import SocialUploadClient

client = SocialUploadClient(
    storage_dir="/path/to/project/.social_upload",
    browser="cloakbrowser",  # 默认值；也可传 patchright/playwright
    headless=True,
    use_system_chrome=True,
)
```

### 6.2 登录 / 检查账号

```python
await client.accounts.login("xhs", "my_account", headless=False)

valid = await client.accounts.check("douyin", "my_account")
accounts = client.accounts.list("xhs")
account_file = client.accounts.account_file("xhs", "my_account")
```

### 6.3 上传视频

```python
from social_upload import UploadVideoInput

result = await client.upload_video(
    UploadVideoInput(
        platform="xhs",
        account_name="my_account",
        video_file="/absolute/path/to/video.mp4",
        title="标题",
        description="正文",
        tags=["财经", "AI"],
        mode="draft",
    ),
    on_event=lambda event: print(event.to_dict()),
)

print(result.to_dict())
```

返回结果形状：

```json
{
  "success": true,
  "stage": "draft_ready",
  "message": "草稿模式完成：已暂存离开，未实际上线",
  "mode": "draft",
  "account_file": "/path/to/.social_upload/cookies/xhs_my_account.json",
  "screenshot_path": "/path/to/.social_upload/screenshots/xhs_draft_xhs_my_account.png",
  "current_url": "https://...",
  "error": ""
}
```

---

## 7. Adapter 接入方式

业务项目只需要写一个很薄的 adapter：

```text
业务项目数据结构
  -> adapter.build_upload_input()
  -> SocialUploadClient.upload_video()
  -> adapter.save_upload_result()
```

### 7.1 通用 adapter 示例

```python
from pathlib import Path
from social_upload import SocialUploadClient, UploadVideoInput

class MyProjectSocialUploadAdapter:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.client = SocialUploadClient(storage_dir=project_root / ".social_upload")

    def build_upload_input(self, item: dict) -> UploadVideoInput:
        return UploadVideoInput(
            platform=item["platform"],
            account_name=item["account_name"],
            video_file=item["video_file"],
            title=item["title"],
            description=item.get("description", ""),
            tags=item.get("tags", []),
            mode=item.get("mode", "draft"),
        )

    async def upload(self, item: dict) -> dict:
        request = self.build_upload_input(item)
        result = await self.client.upload_video(request)
        payload = result.to_dict()
        self.save_upload_result(item, payload)
        return payload

    def save_upload_result(self, item: dict, result: dict) -> None:
        # 写回你自己的数据库、JSON、任务队列状态即可
        item["upload_result"] = result
```



---

## 8. 新项目接入清单

1. 安装本库：`pip install -e /path/to/social-upload-kit`
2. 在新项目 `.gitignore` 加：`.social_upload/`
3. 决定账号名规范，例如 `main`、`my_account`、`brand_a`
4. 先扫码登录：`social-upload xhs login --account main --runtime-dir ... --headed`
5. 写 adapter：把项目里的素材转成 `UploadVideoInput`
6. 先跑 `dry_run=True`
7. 再跑 `mode="draft"`
8. 人工确认草稿无误后，再开放 `mode="publish"`
9. 把 `result.to_dict()` 写回业务项目状态
10. 为 adapter 写单元测试，mock `SocialUploadClient.upload_video()`，不要在单测里真打开浏览器

---

## 9. 测试建议

基础静态检查：

```bash
python -m compileall -q social_upload examples
python -m social_upload.cli.sau_cli douyin chrome
python -m social_upload.cli.sau_cli xhs chrome
```

参数链路 dry-run：

```bash
python -m social_upload.cli.sau_cli xhs upload-video \
  --account test \
  --runtime-dir .social_upload \
  --file /absolute/path/to/video.mp4 \
  --title "测试" \
  --mode draft \
  --dry-run
```

真实浏览器链路建议顺序：

```text
login headed -> check headless -> upload dry-run -> upload draft headed -> upload draft headless -> publish
```

---

## 10. 后续待整理

- 增加专门的 selector smoke test
- 把不同平台的 `UploadResult` 做成统一 dataclass
- 为 `SocialUploadClient` 增加同步 wrapper，方便非 async 项目调用
- 增加 SQLite / keychain cookie storage backend
- 把平台页面变化的诊断截图和 HTML snapshot 落盘
