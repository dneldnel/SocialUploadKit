"""Project-independent Douyin/XHS browser upload toolkit."""

from social_upload.client import SocialUploadClient, UploadVideoInput
from social_upload.storage import CookieStorage

__all__ = [
    "CookieStorage",
    "SocialUploadClient",
    "UploadVideoInput",
    "browser",
    "platforms",
]
