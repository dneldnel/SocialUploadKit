"""Minimal adapter example.

Run from this repository root after installing the package:
    python examples/minimal_upload.py /absolute/path/to/video.mp4
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from social_upload import SocialUploadClient, UploadVideoInput


async def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python examples/minimal_upload.py /path/to/video.mp4")
        return 2

    client = SocialUploadClient(storage_dir=".social_upload", headless=True)

    result = await client.upload_video(
        UploadVideoInput(
            platform="xhs",
            account_name="main",
            video_file=Path(sys.argv[1]),
            title="示例标题",
            description="示例正文；真实项目应由 adapter 从自己的数据源生成。",
            tags=["示例", "自动上传"],
            mode="draft",
            dry_run=True,
        ),
        on_event=lambda event: print(event.to_dict()),
    )
    print(result.to_dict())
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
