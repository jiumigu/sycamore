"""作品 · 后端 —— 27 条

🔴 这一组钉住三件最容易静默出错的事：

① **身份键必须是 `(source_type, source_id)` 复合** ——
   `source_id` 是跨七张源表的裸 id（里程碑 3 / 摘录 3 / 主题 3 / 档案 3），
   只按 id 去重会**把两件事静默并成一条**（项目铁律）。
② **合成可逆** —— 删掉一件作品，它的来源要**全部回到待提炼**，一条都不丢。
③ **列表是裸数组** —— DRF 全局分页会包成 `{count, results}`，
   前端按数组取用即「假 0」（项目高频硬坑 ②）。
"""
import datetime as dt

import pytest
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.models import SystemPreset
from apps.works import services
from apps.works.constants import DEFAULT_WORK_CHANNELS, WORK_CHANNEL_PRESET_TYPE
from apps.works.models import Work, WorkCapture

pytestmark = pytest.mark.django_db

URL = '/api/works'


@pytest.fixture
def client():
    return APIClient()


# ══════════════════════════════════════════════════════════════
# 一、打勾（幂等 + 身份键）
# ══════════════════════════════════════════════════════════════

class TestCapture:

    def test_capture_is_idempotent(self):
        """同一来源重复打勾 ⇒ 只有一条（重试/重复点击不该产生两件）。"""
        services.capture('milestone', 7, '第一次')
        services.capture('milestone', 7, '第二次')
        assert WorkCapture.objects.count() == 1

    def test_recapture_keeps_original_title(self):
        """重复打勾**不覆盖** `title` —— 「当时勾的是哪一条」是快照。"""
        services.capture('milestone', 7, '当时的标题')
        services.capture('milestone', 7, '后来的标题')
        assert WorkCapture.objects.get().title == '当时的标题'

    def test_different_type_same_id_are_two_rows(self):
        """🔴 跨类型同 id **不许合并**（身份键是复合键）。

        ⚠️ 七个来源共用同一个 id 空间 ⇒ 这一条必须覆盖**全部**来源：
        漏一个，那个来源就会在「同号」时静默吃掉另一条。
        """
        for src, title in (
            ('milestone', '里程碑三'), ('inbox', '收件箱三'), ('book', '书三'),
            ('diary', '日记三'), ('quote', '摘录三'), ('ask', '问答三'),
            ('treasure', '档案三'),
        ):
            services.capture(src, 3, title)
        assert WorkCapture.objects.count() == 7
        assert {c.source_type for c in WorkCapture.objects.all()} == {
            'milestone', 'inbox', 'book', 'diary', 'quote', 'ask', 'treasure',
        }

    def test_quote_and_ask_sources_accepted(self):
        """v3.62.0 同日加的两个来源（摘录 / AI 问答）—— 打勾与取消都要能用。

        这两个新来源**不是新设计**：与其余四个走同一条服务层路径。
        这里只钉住「白名单认它们」这一件事（漏了就是 400，而 400 在界面上
        表现得像「点了没反应」）。
        """
        for src in ('quote', 'ask'):
            obj, created = services.capture(src, 11, f'{src} 的标题', '摘要')
            assert created is True
            assert obj.status == 'pending'
            services.uncapture(obj.id)
        assert WorkCapture.objects.count() == 0

    def test_treasure_source_accepted(self):
        """v3.62.12 加的第七个来源（档案馆）—— 同样是「不是新设计」的一条。

        ⚠️ 这条单独立用例（而不是并进上一条的循环）是为了**留痕**：
        日后有人想知道「档案馆是什么时候、按什么理由进来的」，
        看这里和 `constants.CAPTURE_SOURCE_CHOICES` 的注释就够了。
        """
        obj, created = services.capture('treasure', 37, '工作日报格式', '摘要')
        assert created is True
        assert obj.status == 'pending'
        assert obj.get_source_type_display() == '档案馆'
        services.uncapture(obj.id)
        assert WorkCapture.objects.count() == 0

    def test_recapture_after_drop_revives(self):
        """标过 `dropped` 的再打勾 ⇒ 改回 `pending`，**不新建第二条**。"""
        obj, _ = services.capture('book', 5, '一本书')
        obj.status = 'dropped'
        obj.save(update_fields=['status'])

        again, created = services.capture('book', 5, '一本书')
        assert created is False
        assert WorkCapture.objects.count() == 1
        assert again.status == 'pending'

    def test_unknown_source_type_rejected(self):
        with pytest.raises(Exception):
            services.capture('weibo', 1, '不存在的来源')

    def test_capture_requires_title(self):
        with pytest.raises(Exception):
            services.capture('milestone', 1, '')

    def test_uncapture_is_real_delete(self):
        """取消勾 = **真删**（标记不是流水，不适用「撤销 ≠ 删除」）。"""
        obj, _ = services.capture('milestone', 9, '一条')
        services.uncapture(obj.id)
        assert WorkCapture.objects.count() == 0

    def test_cannot_uncapture_used(self):
        """已收进作品的不许在这里删 —— 那会让作品凭空少一个来源。"""
        obj, _ = services.capture('milestone', 9, '一条')
        work = services.compose([obj.id], name='一件作品')
        assert work is not None
        with pytest.raises(Exception):
            services.uncapture(obj.id)
        assert WorkCapture.objects.count() == 1


# ══════════════════════════════════════════════════════════════
# 二、合成 / 拆开（可逆）
# ══════════════════════════════════════════════════════════════

class TestCompose:

    def test_compose_marks_captures_used(self):
        a, _ = services.capture('milestone', 1, 'A')
        b, _ = services.capture('inbox', 2, 'B')
        work = services.compose([a.id, b.id], name='合成的一件', kind='article')

        assert Work.objects.count() == 1
        assert WorkCapture.objects.filter(work=work, status='used').count() == 2
        assert work.kind == 'article'

    def test_compose_requires_at_least_one_capture(self):
        """一条都不选 ⇒ 拒绝。

        理由：允许空选，它就从「把散的东西收成一件」退化成
        「又一个新建入口」—— 同一件事会有两个录入口（项目铁律）。
        """
        with pytest.raises(Exception):
            services.compose([], name='凭空一件')

    def test_compose_rejects_already_used(self):
        a, _ = services.capture('milestone', 1, 'A')
        services.compose([a.id], name='第一件')
        with pytest.raises(Exception):
            services.compose([a.id], name='第二件')

    def test_compose_rejects_missing_capture(self):
        with pytest.raises(Exception):
            services.compose([99999], name='不存在的一条')

    def test_delete_work_returns_captures_to_pending(self):
        """🔴 合成可逆：删作品 ⇒ 来源全部回到待提炼，一条都不丢。"""
        a, _ = services.capture('milestone', 1, 'A')
        b, _ = services.capture('diary', 2, 'B')
        work = services.compose([a.id, b.id], name='要删的')

        n = services.delete_work(work)
        assert n == 2
        assert Work.objects.count() == 0
        assert WorkCapture.objects.filter(status='pending', work__isnull=True).count() == 2


# ══════════════════════════════════════════════════════════════
# 三、接口形状
# ══════════════════════════════════════════════════════════════

class TestApi:

    def test_work_list_is_bare_array(self, client):
        services.compose(
            [services.capture('milestone', 1, 'A')[0].id], name='一件',
        )
        resp = client.get(f'{URL}/items/')
        assert resp.status_code == 200
        assert isinstance(resp.json(), list), '列表必须是裸数组（不是 {count,results}）'

    def test_capture_list_is_bare_array(self, client):
        services.capture('milestone', 1, 'A')
        resp = client.get(f'{URL}/captures/')
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_capture_post_is_200_when_already_captured(self, client):
        """重复打勾返回 200（而不是 201）—— 让调用方**看得出没新建**。"""
        body = {'source_type': 'milestone', 'source_id': 5, 'title': '一条'}
        first = client.post(f'{URL}/captures/', body, format='json')
        second = client.post(f'{URL}/captures/', body, format='json')
        assert first.status_code == 201
        assert second.status_code == 200
        assert second.json()['created'] is False
        assert second.json()['written']['works_capture'] == 0

    def test_period_key_is_computed_by_backend(self, client):
        """期标识由后端下发（前端零计算 —— 自己算跨年会静默差一周）。"""
        from apps.selfrun.readers import period_range

        services.capture('milestone', 1, 'A')
        resp = client.get(f'{URL}/captures/?period_type=weekly')
        row = resp.json()[0]
        expected = period_range('weekly', timezone.localdate())[2]
        assert row['period_key'] == expected
        assert row['in_current_period'] is True

    def test_pending_count_equals_list_across_periods(self, client):
        """🔴 计数卡上的「待提炼 N」必须**等于明细列表的行数**。

        这正是「点数字看明细」那个浮层的前提：卡上写 8、点开只有 3，
        两边各自都对、合起来是错的，而且**不报错**（本项目最怕的那类失败）。

        ⚠️ 关键是**跨期**：上期勾了还没提炼的，既要在计数里（`overview` 不过滤期），
           也要在列表里（`captures` 只按 `status` / `source_type` 筛，
           `period_type` **只用来算 `in_current_period` 标志**）。
           哪天有人「顺手」给列表加上期过滤，这条就会红。
        """
        from apps.selfrun.readers import period_range

        old, _ = services.capture('milestone', 1, '上期勾的、还没提炼的')
        # `captured_at` 是 auto_now_add ⇒ 只能绕开它改（`.update()` 不触发）
        WorkCapture.objects.filter(id=old.id).update(
            captured_at=timezone.now() - dt.timedelta(days=40),
        )
        services.capture('inbox', 2, '本期勾的')

        overview = client.get(f'{URL}/overview/').json()
        rows = client.get(f'{URL}/captures/?period_type=weekly').json()

        assert overview['pending_captures'] == 2
        assert len(rows) == 2
        assert len([r for r in rows if r['status'] == 'pending']) == overview['pending_captures']

        # ⚠️ 得先确认那一行**真的是上一期的** —— 否则这条用例根本没验到跨期
        old_row = next(r for r in rows if r['id'] == old.id)
        assert old_row['in_current_period'] is False
        assert old_row['period_key'] != period_range('weekly', timezone.localdate())[2]

    def test_compose_endpoint_returns_written(self, client):
        cap = services.capture('inbox', 1, 'A')[0]
        resp = client.post(f'{URL}/compose/', {
            'capture_ids': [cap.id], 'name': '从接口合成',
            'kind': 'checklist', 'status': 'private',
        }, format='json')
        assert resp.status_code == 201
        assert resp.json()['written']['works_capture'] == 1
        assert resp.json()['work']['name'] == '从接口合成'

    def test_overview_counts(self, client):
        a, _ = services.capture('milestone', 1, 'A')
        services.capture('inbox', 2, 'B')
        work = services.compose([a.id], name='已发的一件', status='published')
        assert work.status == 'published'

        data = client.get(f'{URL}/overview/').json()
        assert data['total'] == 1
        assert data['published'] == 1
        assert data['pending_captures'] == 1
        assert data['total_captures'] == 2

    def test_meta_carries_key_names(self, client):
        """🔴 键名清单就是契约 —— 少了键，界面上只会『少一个下拉』，
        不报错、也看不出来（项目高频硬坑 ⑪）。"""
        data = client.get(f'{URL}/meta/').json()
        assert set(data) == {'kinds', 'statuses', 'sources', 'channels'}
        assert {k['value'] for k in data['kinds']} >= {'article', 'craft', 'other'}
        assert {s['value'] for s in data['statuses']} == {'private', 'ready', 'published'}
        assert {s['value'] for s in data['sources']} == {
            'milestone', 'inbox', 'book', 'diary', 'quote', 'ask', 'treasure',
        }


# ══════════════════════════════════════════════════════════════
# 四、出口去向清单（`GET` 不写库）
# ══════════════════════════════════════════════════════════════

class TestChannels:

    def test_get_does_not_write(self, client):
        """🔴 只读接口别 `get_or_create` —— 读一次就往库里塞一行是错的。"""
        assert SystemPreset.objects.filter(preset_type=WORK_CHANNEL_PRESET_TYPE).count() == 0
        data = client.get(f'{URL}/channels/').json()
        assert data['values'] == DEFAULT_WORK_CHANNELS
        assert SystemPreset.objects.filter(preset_type=WORK_CHANNEL_PRESET_TYPE).count() == 0

    def test_save_then_get(self, client):
        resp = client.put(
            f'{URL}/channels/', {'values': ['公众号', '贴墙上']}, format='json',
        )
        assert resp.status_code == 200
        assert client.get(f'{URL}/channels/').json()['values'] == ['公众号', '贴墙上']

    def test_save_dedups_and_rejects_empty(self, client):
        resp = client.put(
            f'{URL}/channels/', {'values': ['公众号', ' 公众号 ', '小红书']}, format='json',
        )
        assert resp.json()['values'] == ['公众号', '小红书']
        assert client.put(f'{URL}/channels/', {'values': []}, format='json').status_code == 400


# ══════════════════════════════════════════════════════════════
# 五、给自我运转的取数器留的接口（在 selfrun 侧另有用例）
# ══════════════════════════════════════════════════════════════

class TestPeriodBoundary:

    def test_work_created_at_drives_the_period(self):
        """作品的「属于哪一期」= 它的 `created_at`，**不落库**（派生值）。

        ⚠️ 这里只钉「改 `created_at` 就会换期」这个事实 ——
           取数口径的用例在 `selfrun/tests/test_selfrun_reader_works.py`。
        """
        from apps.selfrun.readers import period_range

        work = Work.objects.create(name='上周的一件')
        last_week = timezone.localdate() - dt.timedelta(days=7)
        Work.objects.filter(id=work.id).update(
            created_at=timezone.make_aware(dt.datetime.combine(last_week, dt.time(12, 0))),
        )
        work.refresh_from_db()
        assert period_range('weekly', timezone.localtime(work.created_at).date())[2] != \
            period_range('weekly', timezone.localdate())[2]


# ══════════════════════════════════════════════════════════════
# 六、媒体（图片 / 视频）
# ══════════════════════════════════════════════════════════════

class TestMedia:
    """作品媒体的上传 + `Work.media` 字段（图片 / 视频，非必填）。"""

    def test_upload_image(self, client, tmp_path):
        from django.core.files.uploadedfile import SimpleUploadedFile

        f = SimpleUploadedFile('shot.png', b'\x89PNG-fake', content_type='image/png')
        # 上传必须落临时目录，别污染真实 backend/media/（铁律：测试不碰真实数据）
        with override_settings(MEDIA_ROOT=tmp_path):
            resp = client.post(f'{URL}/media/', {'file': f}, format='multipart')
        assert resp.status_code == 200
        assert resp.json()['type'] == 'image'
        assert '/media/works/' in resp.json()['url']
        assert (tmp_path / 'works').exists()

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

    def test_work_with_media_roundtrip(self, client):
        """新建带 media 的作品 ⇒ 列表出参带同一份 media。"""
        media = [{'type': 'image', 'url': '/media/works/202610/a.png'}]
        resp = client.post(
            f'{URL}/items/',
            {'name': '带图作品', 'kind': 'craft', 'media': media},
            format='json',
        )
        assert resp.status_code == 201
        assert resp.json()['work']['media'] == media
        rows = client.get(f'{URL}/items/').json()
        assert rows[0]['media'] == media

    def test_work_rejects_bad_media_shape(self, client):
        """media 结构不合法必须 400 —— 脏数据进库前端会静默画空。"""
        resp = client.post(
            f'{URL}/items/',
            {'name': '坏结构', 'media': [{'type': 'movie', 'url': ''}]},
            format='json',
        )
        assert resp.status_code == 400
