"""媒体上传与结构校验 —— **唯一实现**（showroom / works 共用）。

🔴 白名单与大小上限只此一份。works 与 showroom 的上传判据必须同源：
   改了一边漏了另一边，会**静默放行不该放的文件 / 误拦该放的文件**，
   而且不报错 —— 正是本项目最怕的那类失败。

⚠️ 类型由**扩展名**判定（image | video），调用方只存、不再判第二份。
"""
import os
import uuid
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
VIDEO_EXTS = {'.mp4', '.mov', '.webm', '.m4v'}
IMAGE_MAX_BYTES = 10 * 1024 * 1024     # 10MB
VIDEO_MAX_BYTES = 100 * 1024 * 1024    # 100MB


class MediaUploadError(Exception):
    """上传被拒：`message` 给用户看，`status` 决定 HTTP 码。"""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def validate_media_items(value):
    """media 结构校验：`[{type: 'image'|'video', url}]`。

    脏结构（type 写错 / url 为空）进来会在前端**静默画空**，
    所以必须在这里拦掉，而不是让它落库。
    """
    if not isinstance(value, list):
        raise serializers.ValidationError('media 必须是列表')
    for item in value:
        if (
            not isinstance(item, dict)
            or item.get('type') not in ('image', 'video')
            or not isinstance(item.get('url'), str)
            or not item['url']
        ):
            raise serializers.ValidationError(
                'media 每项必须是 {type: "image"|"video", url: "…"}',
            )
    return value


def save_upload_file(file, subdir):
    """保存上传文件到 `MEDIA_ROOT/<subdir>/YYYYMM/<uuid><ext>`，返回 `(url, type)`。

    ⚠️ `subdir` 标记「哪一模块的媒体」—— showroom 传 `'showroom'`，works 传 `'works'`。
    校验失败抛 `MediaUploadError`（调用方据此回 400 + message）。
    """
    if not file:
        raise MediaUploadError('未提供文件')

    ext = os.path.splitext(file.name)[1].lower()
    if ext in IMAGE_EXTS:
        media_type, max_bytes = 'image', IMAGE_MAX_BYTES
    elif ext in VIDEO_EXTS:
        media_type, max_bytes = 'video', VIDEO_MAX_BYTES
    else:
        raise MediaUploadError(f'不支持的文件类型：{ext or "(无扩展名)"}')
    if file.size > max_bytes:
        raise MediaUploadError(f'文件超过 {max_bytes // (1024 * 1024)}MB 上限')

    rel_dir = Path(subdir) / timezone.localtime().strftime('%Y%m')
    abs_dir = Path(settings.MEDIA_ROOT) / rel_dir
    abs_dir.mkdir(parents=True, exist_ok=True)
    filename = f'{uuid.uuid4().hex}{ext}'
    with open(abs_dir / filename, 'wb') as f:
        for chunk in file.chunks():
            f.write(chunk)

    url = f'{settings.MEDIA_URL}{rel_dir.as_posix()}/{filename}'
    return url, media_type
