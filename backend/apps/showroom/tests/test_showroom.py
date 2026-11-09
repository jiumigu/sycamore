"""展厅 · 后端 —— 钉住最容易静默出错的事

① 品牌单例 **GET 不写库**（只读别 `get_or_create`）。
② 案例 / 技能 / 作品列表是**裸数组**（DRF 全局分页会包成 `{count, results}`）。
③ 预览**只下发可见项**（`is_visible=False` 的不进 —— 策展的显隐开关才真正生效）。
④ 作品馆**只引用** `works.Work`：`title_snapshot` 是快照，源作品删了仍读得懂。
"""
import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.showroom.models import (
    ShowroomCase,
    ShowroomProfile,
    ShowroomSkill,
    ShowroomWork,
)
from apps.works.models import Work

pytestmark = pytest.mark.django_db

URL = '/api/showroom'


@pytest.fixture
def client():
    return APIClient()


class TestProfile:
    def test_get_does_not_write(self, client):
        """只读接口别 `get_or_create` —— 读一次就往库里塞一行是错的。"""
        assert ShowroomProfile.objects.count() == 0
        resp = client.get(f'{URL}/profile/')
        assert resp.status_code == 200
        assert resp.json()['ip_name'] == ''
        assert ShowroomProfile.objects.count() == 0

    def test_put_creates_then_reads(self, client):
        resp = client.put(
            f'{URL}/profile/',
            {'ip_name': '鸠羽岁安', 'tagline': '我自己正在用的方法，才敢交给你。'},
            format='json',
        )
        assert resp.status_code == 200
        assert ShowroomProfile.objects.count() == 1
        assert client.get(f'{URL}/profile/').json()['ip_name'] == '鸠羽岁安'


class TestLists:
    def test_case_list_is_bare_array(self, client):
        ShowroomCase.objects.create(title='一件')
        resp = client.get(f'{URL}/cases/')
        assert resp.status_code == 200
        assert isinstance(resp.json(), list), '列表必须是裸数组（不是 {count,results}）'

    def test_skill_list_is_bare_array(self, client):
        ShowroomSkill.objects.create(name='Python')
        resp = client.get(f'{URL}/skills/')
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_work_list_is_bare_array(self, client):
        work = Work.objects.create(name='一件手作', kind='craft')
        ShowroomWork.objects.create(work=work, title_snapshot='一件手作')
        resp = client.get(f'{URL}/works/')
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestPreview:
    def test_preview_only_visible(self, client):
        ShowroomCase.objects.create(title='可见', is_visible=True)
        ShowroomCase.objects.create(title='不可见', is_visible=False)
        data = client.get(f'{URL}/preview/').json()
        assert [c['title'] for c in data['cases']] == ['可见']

    def test_preview_has_stable_shape(self, client):
        """键名就是契约 —— 前端按这四个键取用，少了键 = 页面某一块静默空掉。"""
        data = client.get(f'{URL}/preview/').json()
        assert set(data) == {'profile', 'cases', 'skills', 'works'}


class TestWork:
    def test_create_snapshots_title(self, client):
        work = Work.objects.create(name='一件手作', kind='craft')
        resp = client.post(f'{URL}/works/', {'work': work.id}, format='json')
        assert resp.status_code == 201
        assert resp.json()['title_snapshot'] == '一件手作'
        assert resp.json()['work_name'] == '一件手作'

    def test_create_requires_work(self, client):
        resp = client.post(f'{URL}/works/', {}, format='json')
        assert resp.status_code == 400

    def test_work_name_falls_back_to_snapshot_after_source_deleted(self, client):
        """🔴 源作品被删（SET_NULL）后，馆藏仍靠快照读得懂「当时策展的是哪件」。"""
        work = Work.objects.create(name='一件手作', kind='craft')
        ShowroomWork.objects.create(work=work, title_snapshot='一件手作')
        work.delete()
        resp = client.get(f'{URL}/works/')
        row = resp.json()[0]
        assert row['work'] is None
        assert row['work_name'] == '一件手作'


class TestMeta:
    def test_meta_carries_skill_levels(self, client):
        """技能熟练度三级由后端下发，前端不写第二份文案。"""
        data = client.get(f'{URL}/meta/').json()
        assert {o['value'] for o in data['skill_levels']} == {'expert', 'proficient', 'familiar'}


class TestMedia:
    """媒体上传 + 案例 / 馆藏的 media 字段（图片 / 视频）。"""

    def test_upload_image(self, client, tmp_path):
        from django.core.files.uploadedfile import SimpleUploadedFile
        f = SimpleUploadedFile('proof.png', b'\x89PNG-fake', content_type='image/png')
        # 上传必须落临时目录，别污染真实 backend/media/（铁律：测试不碰真实数据）
        with override_settings(MEDIA_ROOT=tmp_path):
            resp = client.post(f'{URL}/media/', {'file': f}, format='multipart')
        assert resp.status_code == 200
        assert resp.json()['type'] == 'image'
        assert '/media/showroom/' in resp.json()['url']
        assert (tmp_path / 'showroom').exists()

    def test_upload_video(self, client, tmp_path):
        from django.core.files.uploadedfile import SimpleUploadedFile
        f = SimpleUploadedFile('demo.mp4', b'\x00\x00fake', content_type='video/mp4')
        with override_settings(MEDIA_ROOT=tmp_path):
            resp = client.post(f'{URL}/media/', {'file': f}, format='multipart')
        assert resp.status_code == 200
        assert resp.json()['type'] == 'video'

    def test_upload_rejects_unknown_ext(self, client):
        from django.core.files.uploadedfile import SimpleUploadedFile
        f = SimpleUploadedFile('evil.exe', b'MZ', content_type='application/octet-stream')
        resp = client.post(f'{URL}/media/', {'file': f}, format='multipart')
        assert resp.status_code == 400

    def test_upload_requires_file(self, client):
        resp = client.post(f'{URL}/media/', {}, format='multipart')
        assert resp.status_code == 400

    def test_case_with_media_roundtrip(self, client):
        media = [{'type': 'image', 'url': '/media/showroom/202610/a.png'}]
        resp = client.post(
            f'{URL}/cases/',
            {'title': '带图案例', 'media': media},
            format='json',
        )
        assert resp.status_code == 201
        assert resp.json()['media'] == media
        data = client.get(f'{URL}/preview/').json()
        assert data['cases'][0]['media'] == media

    def test_case_rejects_bad_media_shape(self, client):
        """media 结构不合法必须 400 —— 脏数据进库前端会静默画空。"""
        resp = client.post(
            f'{URL}/cases/',
            {'title': '坏结构', 'media': [{'type': 'movie', 'url': ''}]},
            format='json',
        )
        assert resp.status_code == 400

    def test_work_with_media(self, client):
        work = Work.objects.create(name='一件手作', kind='craft')
        media = [{'type': 'video', 'url': '/media/showroom/202610/b.mp4'}]
        resp = client.post(
            f'{URL}/works/',
            {'work': work.id, 'media': media},
            format='json',
        )
        assert resp.status_code == 201
        assert resp.json()['media'] == media
