"""媒体上传与结构校验 —— **唯一实现**（showroom / works 共用）。

🔴 白名单与大小上限只此一份。works 与 showroom 的上传判据必须同源：
   改了一边漏了另一边，会**静默放行不该放的文件 / 误拦该放的文件**，
   而且不报错 —— 正是本项目最怕的那类失败。

⚠️ 类型由**扩展名**判定（image | video），调用方只存、不再判第二份。
"""
import logging
import os
import uuid
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from PIL import Image, ImageOps
from rest_framework import serializers

logger = logging.getLogger(__name__)

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
VIDEO_EXTS = {'.mp4', '.mov', '.webm', '.m4v'}
IMAGE_MAX_BYTES = 10 * 1024 * 1024     # 10MB
VIDEO_MAX_BYTES = 100 * 1024 * 1024    # 100MB

# ── 缩略图（v3.64.72）──────────────────────────────────────────
# 🔴 列表用缩略图、预览用原图：40px 的格子不该下载 400KB 的原图。
#    🔴 缩略图是**派生文件、不落库** —— 原图 url 是唯一真源，
#       `…/abc.jpg` ⇒ `…/abc_thumb.jpg`。这条约定只写在这里一份，两端都调它。
#    ⚠️ 扩展名统一 `.jpg`：缩略图只占 40px 的格子，保透明没意义，而 png 缩略图
#       常常比 jpg 大一倍（透明通道 + 无损）。
THUMB_SUFFIX = '_thumb'
THUMB_EXT = '.jpg'
THUMB_MAX_PX = 200          # 列表 40px、2 倍屏 80px，留到 200 供以后放大缩略图
THUMB_QUALITY = 78


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

    🔴 **只留 `type` / `url`**，多余键一律丢掉。`thumb` 是出参派生值，
       若被前端回传落库，改文件名后库里就留着一个指向不存在文件的 url ——
       界面上是「列表图裂、点开预览却正常」，很难查。
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
    return [{'type': item['type'], 'url': item['url']} for item in value]


# ══════════════════════════════════════════════════════════════
# 缩略图
# ══════════════════════════════════════════════════════════════

def _abs_path(url):
    """`/media/…` → 磁盘绝对路径；不在 `MEDIA_URL` 下返回 `None`。"""
    if not isinstance(url, str) or not url.startswith(settings.MEDIA_URL):
        return None
    return Path(settings.MEDIA_ROOT) / url[len(settings.MEDIA_URL):]


def thumb_url_for(url):
    """原图 url → 缩略图 url（约定：同目录 `{stem}_thumb.jpg`）。"""
    root, _ext = os.path.splitext(url)
    return f'{root}{THUMB_SUFFIX}{THUMB_EXT}'


def has_thumb(url):
    """缩略图文件是否已生成（**只探文件，不生成** —— GET 路径不写盘）。"""
    p = _abs_path(thumb_url_for(url)) if isinstance(url, str) else None
    return bool(p and p.is_file())


def make_thumb(url):
    """给一张**已落盘**的原图生成缩略图（幂等，可重复跑）。返回缩略图 url。

    ⚠️ 失败**不抛给上传方**：上传成功但没缩略图时，列表自动回退原图 ——
       功能仍然对，只是慢一点。这种情况 `with_thumbs()` 会下发 `thumb=None`，
       所以「没生成」与「生成失败」在界面上是同一个可见结果（都是原图），
       但都不会伪装成「这张图很小」。
    """
    if not isinstance(url, str):
        return None
    if os.path.splitext(url)[1].lower() not in IMAGE_EXTS:
        return None
    src = _abs_path(url)
    if not src or not src.is_file():
        return None
    dst = _abs_path(thumb_url_for(url))
    try:
        with Image.open(src) as raw:
            # 手机竖拍靠 EXIF 记方向，不转正的话缩略图会躺着
            with ImageOps.exif_transpose(raw) as upright:
                if upright.mode in ('RGBA', 'LA', 'P'):
                    rgba = upright.convert('RGBA')
                    # jpg 没有 alpha：垫白底，否则透明区变黑块
                    out = Image.new('RGB', rgba.size, (255, 255, 255))
                    out.paste(rgba, mask=rgba.getchannel('A'))
                else:
                    out = upright.convert('RGB')
                out.thumbnail((THUMB_MAX_PX, THUMB_MAX_PX), Image.LANCZOS)
                dst.parent.mkdir(parents=True, exist_ok=True)
                out.save(
                    dst, 'JPEG',
                    quality=THUMB_QUALITY, optimize=True, progressive=True,
                )
    except (OSError, ValueError) as exc:   # 坏图 / 截断 / 无写权限
        logger.warning('缩略图生成失败 %s: %s', url, exc)
        return None
    return thumb_url_for(url)


def with_thumbs(items):
    """出参用：给**图片**项补一个 `thumb`（没有生成过就 `None`，前端回退原图）。

    ⚠️ 视频不加这个键 —— 它没有缩略图，加个 `None` 只会让前端多一条分支。
    ⚠️ 这里只 `stat` 文件（每张一次），不生成：14 件 ≈ 0.1ms，不必为它加缓存；
       真要缓存，得先解决「补跑命令后进程里还是旧结论」这个旧坑（禁进程缓存）。
    """
    out = []
    for m in items or []:
        if not isinstance(m, dict):
            continue
        item = dict(m)
        url = item.get('url')
        if item.get('type') == 'image' and isinstance(url, str):
            item['thumb'] = thumb_url_for(url) if has_thumb(url) else None
        out.append(item)
    return out


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
    if media_type == 'image':
        make_thumb(url)   # 失败不阻断上传，见 make_thumb 的注释
    return url, media_type
