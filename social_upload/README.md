# social_upload package

这是 `social-upload-kit` 的 Python 包目录。完整接入说明见仓库根目录 `README.md`。

包内核心入口：

- `social_upload.SocialUploadClient`
- `social_upload.UploadVideoInput`
- `social_upload.CookieStorage`
- `python -m social_upload.cli.sau_cli ...`

浏览器策略已同步当前 VideoLingo：

- 默认 `cloakbrowser`
- fallback：`patchright` / `playwright`
- CloakBrowser 二进制建议缓存到 `<runtime-dir>/cloakbrowser`
- 账号 profile seed 使用 cookie 文件 stem，保证同账号稳定 fingerprint
- persistent profile 目录预留在 `<runtime-dir>/browser_profiles`，默认关闭

常用检查：

```bash
python -m social_upload.cli.sau_cli xhs browser
python -m social_upload.cli.sau_cli xhs browser --browser cloakbrowser
```
