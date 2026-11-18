"""媒体缩略图（v3.64.72）

🔴 守三件事：

1. **列表缩略图必须真的变小**（不是只把 `src` 换了个名字）；
2. **原图不动** —— 缩略图是同目录的派生文件，删了它原图仍然完好；
3. **没生成时给 `None`，不假装** —— 前端据此回退原图，而不是拿到一个裂图 url。
"""
import io
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient

from apps.core.media import (
    has_thumb,
    make_thumb,
    thumb_url_for,
    validate_media_items,
    with_thumbs,
)
from apps.works.models import Work

URL = '/media/works/202611/big.jpg'


def _write_image(root, name='big.jpg', size=(1600, 1200), mode='RGB'):
    """造一张足够大的图：单色会被 JPEG 压到几 KB，加大面积噪声撑体积。"""
    p = Path(root) / 'works' / '202611' / name
    p.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new(mode, size, (200, 120, 90, 128) if mode != 'RGB' else (200, 120, 90))
    if mode == 'RGB':
        px = image.load()
        for x in range(0, size[0], 5):
            for y in range(0, size[1], 5):
                px[x, y] = ((x * 3) % 256, (y * 7) % 256, (x + y) % 256)
        image.save(p, 'JPEG', quality=95)
    else:
        image.save(p, 'PNG')
    return p


@pytest.fixture
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


class TestThumbUrl:
    def test_约定同目录加后缀(self):
        assert thumb_url_for('/media/works/202611/a.jpg') == '/media/works/202611/a_thumb.jpg'

    def test_png_也落成_jpg(self):
        """缩略图统一 jpg：png 缩略图常比 jpg 大一倍，而它只占 40px 的格子。"""
        assert thumb_url_for('/media/x/a.png') == '/media/x/a_thumb.jpg'


class TestMakeThumb:
    def test_生成且真的小(self, media_root):
        src = _write_image(media_root)
        out = make_thumb(URL)

        assert out == '/media/works/202611/big_thumb.jpg'
        dst = media_root / 'works' / '202611' / 'big_thumb.jpg'
        assert dst.is_file()
        with Image.open(dst) as im:
            assert max(im.size) == 200
        # 原图 1600×1200 q95 ⇒ 缩略图应小一个数量级（这里用 1/5 留余量）
        assert dst.stat().st_size < src.stat().st_size / 5

    def test_原图不动(self, media_root):
        src = _write_image(media_root)
        before = (src.stat().st_size, src.read_bytes()[:64])
        make_thumb(URL)
        assert (src.stat().st_size, src.read_bytes()[:64]) == before

    def test_幂等(self, media_root):
        _write_image(media_root)
        first = make_thumb(URL)
        second = make_thumb(URL)
        assert first == second
        assert (media_root / 'works' / '202611' / 'big_thumb.jpg').is_file()

    def test_透明区垫白底(self, media_root):
        """jpg 没有 alpha：直接转会把透明压成黑块。"""
        p = Path(media_root) / 'works' / '202611' / 'alpha.png'
        p.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGBA', (400, 400), (0, 0, 0, 0)).save(p)

        make_thumb('/media/works/202611/alpha.png')
        with Image.open(media_root / 'works' / '202611' / 'alpha_thumb.jpg') as im:
            r, g, b = im.convert('RGB').getpixel((5, 5))
        assert (r, g, b) == (255, 255, 255)

    def test_视频不生成(self, media_root):
        assert make_thumb('/media/works/202611/a.mp4') is None

    def test_原图不存在返回_none(self, media_root):
        assert make_thumb(URL) is None

    def test_坏图不抛(self, media_root):
        p = Path(media_root) / 'works' / '202611' / 'broken.jpg'
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b'not an image')
        assert make_thumb('/media/works/202611/broken.jpg') is None


class TestHasAndWithThumbs:
    def test_没生成过是_none(self, media_root):
        _write_image(media_root)
        assert has_thumb(URL) is False
        assert with_thumbs([{'type': 'image', 'url': URL}])[0]['thumb'] is None

    def test_生成后给_url(self, media_root):
        _write_image(media_root)
        make_thumb(URL)
        assert with_thumbs([{'type': 'image', 'url': URL}])[0]['thumb'] == (
            '/media/works/202611/big_thumb.jpg'
        )

    def test_视频不加这个键(self, media_root):
        """不是 `None`，是根本没有 —— 前端少一条分支。"""
        out = with_thumbs([{'type': 'video', 'url': '/media/v.mp4'}])
        assert 'thumb' not in out[0]

    def test_不改入参(self, media_root):
        _write_image(media_root)
        make_thumb(URL)
        src = [{'type': 'image', 'url': URL}]
        with_thumbs(src)
        assert src == [{'type': 'image', 'url': URL}]


class TestValidateDropsDerived:
    def test_回传的_thumb_不落库(self):
        """库里存了派生 url，换文件名后就指向不存在的文件 ⇒ 列表图裂、预览正常。"""
        out = validate_media_items([
            {'type': 'image', 'url': '/media/a.jpg', 'thumb': '/media/a_thumb.jpg', 'x': 1},
        ])
        assert out == [{'type': 'image', 'url': '/media/a.jpg'}]


class TestUploadAndEndpoint:
    def test_上传即生成缩略图(self, media_root):
        from apps.core.media import save_upload_file

        src = _write_image(media_root, 'tmp.jpg', (800, 600))
        buf = io.BytesIO()
        Image.open(src).save(buf, 'JPEG', quality=95)
        f = SimpleUploadedFile('up.jpg', buf.getvalue(), content_type='image/jpeg')

        url, media_type = save_upload_file(f, 'works')

        assert media_type == 'image'
        assert has_thumb(url) is True

    @pytest.mark.django_db
    def test_列表接口下发_thumb(self, media_root):
        _write_image(media_root)
        make_thumb(URL)
        Work.objects.create(
            name='带图的一件', kind='article', status='private',
            media=[{'type': 'image', 'url': URL}],
        )

        res = APIClient().get('/api/works/items/')

        assert res.status_code == 200
        rows = res.json()
        assert rows[0]['media'][0]['url'] == URL          # 预览仍用原图
        assert rows[0]['media'][0]['thumb'] == '/media/works/202611/big_thumb.jpg'
