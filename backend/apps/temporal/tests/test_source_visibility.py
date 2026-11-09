"""「来源可见」（v3.64.33）的回归守卫。

为什么这一层需要单独的测试
--------------------------
来源信息只存在 `TemporalTask.import_batch` 一列里，而且那一列是**哈希批次号**。
把它翻成人能读的来源词，全靠 `services.classify_source` 一份实现。这里的错法都很安静：

1. **把「未标注」和「其它来源」合成一个兜底桶** ⇒ 本来有批次号的记录被说成「来源不明」，
   线索被抹掉，而且界面上看起来完全正常；
2. **`import_batch__in=[None]` 永远不匹配** ⇒ 筛「未标注」得到 0 条，
   用户会读成「我没有来源不明的记录」；
3. **非法 source 值返回空列表** ⇒ 拼错一个字母，看到的是「这个来源一条都没有」；
4. **汇总加起来对不上总数** ⇒ 屏幕上几个数字各自合理，合计却漏掉一批；
5. **手工新增不写来源** ⇒ 新记录和「早期来源不明」混成同一个空值桶，事后分不开。

口径推导见 `.workbuddy/memory/TECH-NOTES.md` §158。
"""

from datetime import datetime

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.temporal.models import TemporalTask
from apps.temporal.services import (
    classify_source,
    label_unlabeled_source,
    list_record_sources,
    make_batch_id,
)

pytestmark = pytest.mark.django_db

URL = '/api/temporal/tasks/'


def _aware(text: str) -> datetime:
    return timezone.make_aware(datetime.strptime(text, '%Y-%m-%d %H:%M:%S'))


def _mk(task_name='代码编程', start='2026-03-02 09:00:00', hours=1.0, batch='import_20260101_0900_abcd'):
    s = _aware(start)
    return TemporalTask.objects.create(
        task_name=task_name, task_description='', start_time=s,
        end_time=s.replace(hour=s.hour + int(hours)),
        duration_hours=hours, notes='', tags=None, task_type=task_name,
        import_batch=batch, year=s.year, mon=f'{s.month:02d}', day=s.day,
        week=s.isocalendar()[1], quarter=(s.month - 1) // 3 + 1,
    )


@pytest.fixture
def client():
    return APIClient()


# ── 分类纯函数 ─────────────────────────────────────────────────────────

class TestClassifySource:
    """批次号 → 来源词。每条都对着一份真实库里出现过的值。"""

    def test_known_batches(self):
        cases = {
            'import_3c3fff90846d': ('csv', 'CSV 导入'),
            'import_20261107_1832_ab12': ('csv', 'CSV 导入'),
            'worklog': ('worklog', '工作日志'),
            'timer': ('timer', '实时计时'),
            'manual': ('manual', '手工录入'),
            'overtime_recon_2020_2022': ('overtime_recon', '加班反推'),
        }
        for batch, (kind, label) in cases.items():
            info = classify_source(batch)
            assert (info['kind'], info['label']) == (kind, label), batch

    def test_empty_is_unlabeled_not_other(self):
        """NULL 与空串都是「不知道从哪来」—— 不能落进 `other`（那是「知道有来源」）。"""
        for raw in (None, '', '   '):
            assert classify_source(raw)['kind'] == 'unlabeled'

    def test_unknown_batch_is_other_and_keeps_batch_id(self):
        """认不出的批次号必须把**原号亮出来**，别吞成「未标注」。

        🔴 这条是「两种空分开」的护栏：合成一个桶之后，
           界面上再也分不出「老数据」和「代码没认出来」。
        """
        info = classify_source('some_new_writer_v2')
        assert info['kind'] == 'other'
        assert info['batch'] == 'some_new_writer_v2'

    def test_prefix_is_case_and_order_sensitive(self):
        """先具体、后通用：`overtime_recon` 不会被当成 `import_` 处理。"""
        assert classify_source('overtime_recon_other_batch')['kind'] == 'overtime_recon'
        assert classify_source('Import_abc')['kind'] == 'other'   # 前缀大小写不做宽容


# ── 批次号生成 ─────────────────────────────────────────────────────────

class TestMakeBatchId:
    def test_shape_is_readable_and_prefix_kept(self):
        """带日期、仍以 `import_` 开头（分类和按批次回滚都靠这个前缀）。"""
        bid = make_batch_id(_aware('2026-11-07 18:32:00'))
        assert bid.startswith('import_20261107_1832_')
        assert len(bid) == len('import_20261107_1832_') + 4

    def test_same_minute_does_not_collide(self):
        """同一分钟连导两次不能撞号 —— 撞号 = 两批合并，事后无法区分。"""
        now = _aware('2026-11-07 18:32:00')
        ids = {make_batch_id(now) for _ in range(50)}
        assert len(ids) == 50


# ── 汇总接口 ───────────────────────────────────────────────────────────

class TestSourceOverview:
    def test_kinds_sum_equals_total(self):
        """恒等式：各来源条数之和 == 总条数。加不起来就是在某处漏了一批。"""
        _mk('代码编程', '2026-03-02 09:00:00', 1.0, 'import_20260101_0900_aaaa')
        _mk('阅读思考', '2026-03-02 10:00:00', 1.0, 'import_20260101_0900_aaaa')
        _mk('牛马工作', '2026-03-02 11:00:00', 1.0, 'worklog')
        _mk('休息睡眠', '2026-03-02 12:00:00', 1.0, 'timer')
        _mk('手工补记', '2026-03-02 13:00:00', 1.0, 'manual')
        _mk('早期记录', '2026-03-02 14:00:00', 1.0, None)
        _mk('未知来源', '2026-03-02 15:00:00', 1.0, 'weird_batch')

        data = list_record_sources()
        assert data['total_records'] == 7
        assert sum(k['count'] for k in data['kinds']) == data['total_records']
        # 批次明细同样是 7 条（每批 1 条）—— 明细与汇总不能各算各的
        assert sum(i['count'] for i in data['items']) == data['total_records']
        assert data['unlabeled_count'] == 1

    def test_endpoint_is_read_only(self):
        """只读接口不能顺手建 TaskMeta / 刷周缓存（否则「看一眼」变成一次写入）。"""
        _mk('从未出现过的任务名', '2026-03-02 09:00:00', 1.0, 'import_20260101_0900_aaaa')
        from apps.temporal.models import TaskMeta
        before = (TemporalTask.objects.count(), TaskMeta.objects.count())
        res = APIClient().get(f'{URL}sources/')
        assert res.status_code == 200
        assert res.json()['total_records'] == before[0]
        assert (TemporalTask.objects.count(), TaskMeta.objects.count()) == before

    def test_kinds_follow_enum_order(self):
        """汇总按枚举固定顺序下发（不随数据量跳动），否则每次打开顺序都不一样。"""
        _mk('A', '2026-03-02 09:00:00', 1.0, 'timer')
        _mk('B', '2026-03-02 10:00:00', 1.0, None)
        order = [k['kind'] for k in list_record_sources()['kinds']]
        assert order == ['timer', 'unlabeled']


# ── 来源筛选 ───────────────────────────────────────────────────────────

class TestSourceFilter:
    def test_unlabeled_matches_null_and_empty_string(self):
        """🔴 `import_batch__in=[None]` 生成 `IN (NULL)`，永远不匹配。

        库里「未标注」同时有 NULL 与空串两种存法；只筛一种就会少报，
        而少报的症状正是「我没有来源不明的记录」。
        """
        _mk('空值记录', '2026-03-02 09:00:00', 1.0, None)
        _mk('空串记录', '2026-03-02 10:00:00', 1.0, '')
        _mk('CSV 记录', '2026-03-02 11:00:00', 1.0, 'import_20260101_0900_aaaa')

        data = APIClient().get('/api/temporal/tasks/', {'source': 'unlabeled'}).json()
        names = {r['task_name'] for r in data['results']}
        assert names == {'空值记录', '空串记录'}

    def test_invalid_source_is_400_not_empty_list(self):
        """拼错来源值必须报错 —— 空列表会被读成「这个来源一条都没有」。"""
        res = APIClient().get('/api/temporal/tasks/', {'source': 'csvv'})
        assert res.status_code == 400
        assert 'source' in res.json()

    def test_filter_by_kind(self):
        _mk('CSV 记录', '2026-03-02 09:00:00', 1.0, 'import_20260101_0900_aaaa')
        _mk('计时记录', '2026-03-02 10:00:00', 1.0, 'timer')
        data = APIClient().get('/api/temporal/tasks/', {'source': 'csv'}).json()
        assert [r['task_name'] for r in data['results']] == ['CSV 记录']


# ── 行级来源字段 ───────────────────────────────────────────────────────

class TestRowSourceFields:
    def test_list_row_carries_kind_and_label(self):
        _mk('代码编程', '2026-03-02 09:00:00', 1.0, 'import_20260101_0900_aaaa')
        row = APIClient().get('/api/temporal/tasks/').json()['results'][0]
        assert (row['source_kind'], row['source_label']) == ('csv', 'CSV 导入')

    def test_manual_create_stamps_manual(self):
        """手工新增必须自报家门：`import_batch` 是 read_only，只能在保存后补写。"""
        res = APIClient().post('/api/temporal/tasks/', {
            'task_name': '手工记的',
            'start_time': '2026-03-02 09:00:00',
            'end_time': '2026-03-02 10:00:00',
        }, format='json')
        assert res.status_code == 201
        row = TemporalTask.objects.get(id=res.json()['id'])
        assert row.import_batch == 'manual'
        assert res.json()['source_label'] == '手工录入'

    def test_client_cannot_forge_source(self):
        """前端塞 `import_batch` 应被忽略（read_only）—— 来源不能由调用方伪造。"""
        res = APIClient().post('/api/temporal/tasks/', {
            'task_name': '伪造来源',
            'start_time': '2026-03-02 09:00:00',
            'end_time': '2026-03-02 10:00:00',
            'import_batch': 'timer',
        }, format='json')
        assert res.status_code == 201
        assert TemporalTask.objects.get(id=res.json()['id']).import_batch == 'manual'

    def test_edit_does_not_change_source(self):
        """编辑（改备注/时刻）不能把来源改掉：CSV 导入的记录改完还是 CSV 导入。"""
        obj = _mk('代码编程', '2026-03-02 09:00:00', 1.0, 'import_20260101_0900_aaaa')
        APIClient().patch(f'/api/temporal/tasks/{obj.id}/', {'notes': '改了备注'}, format='json')
        obj.refresh_from_db()
        assert obj.import_batch == 'import_20260101_0900_aaaa'
        assert obj.notes == '改了备注'


# ── 历史空来源补记（v3.64.34）──────────────────────────────────────────

class TestBackfillManualSource:
    """`label_unlabeled_source` 是**数据修复**，不是分类 —— 边界比功能重要。

    它只该动「来源为空」的行；一旦跑顺了手，把已知来源也改掉，问题不会立刻显形
    （数字还在、只是从「CSV 导入」变成了「手工录入」），查起来要翻库对批次号。
    """

    def test_dry_run_reports_without_writing(self):
        obj = _mk('手工记的', '2026-03-02 09:00:00', 1.0, None)
        res = label_unlabeled_source('manual', dry_run=True)
        assert res['total'] == 1
        assert res['updated'] == 0
        assert res['dry_run'] is True
        assert res['rows'][0]['id'] == obj.id
        obj.refresh_from_db()
        assert obj.import_batch is None, '预演写库了'

    def test_apply_only_touches_empty_source(self):
        blank = _mk('手工记的', '2026-03-02 09:00:00', 1.0, None)
        empty = _mk('空串来源', '2026-03-03 09:00:00', 1.0, '')
        timer = _mk('计时的', '2026-03-04 09:00:00', 1.0, 'timer')
        csv = _mk('导入的', '2026-03-05 09:00:00', 1.0, 'import_20260101_0900_abcd')

        res = label_unlabeled_source('manual', dry_run=False)
        assert res['updated'] == 2, 'NULL 与空串都要算，且只算这两条'

        for o in (blank, empty):
            o.refresh_from_db()
            assert o.import_batch == 'manual'
        for o in (timer, csv):
            o.refresh_from_db()
            assert o.import_batch in ('timer', 'import_20260101_0900_abcd'), '已知来源被改写了'

    def test_ids_narrow_the_scope(self):
        """逐行否决：只给排除后剩下的 id，其它空来源行不动。"""
        keep = _mk('留下', '2026-03-02 09:00:00', 1.0, None)
        skip = _mk('跳过', '2026-03-03 09:00:00', 1.0, None)
        label_unlabeled_source('manual', ids=[keep.id], dry_run=False)
        keep.refresh_from_db()
        skip.refresh_from_db()
        assert keep.import_batch == 'manual'
        assert skip.import_batch is None

    def test_is_idempotent(self):
        _mk('手工记的', '2026-03-02 09:00:00', 1.0, None)
        assert label_unlabeled_source('manual', dry_run=False)['updated'] == 1
        again = label_unlabeled_source('manual', dry_run=False)
        assert again['total'] == 0 and again['updated'] == 0

    def test_rejects_bucket_kinds(self):
        """`unlabeled` / `other` 是兜底桶的名字，不是可写入的来源。"""
        for bad in ('unlabeled', 'other'):
            with pytest.raises(ValueError):
                label_unlabeled_source(bad)
        with pytest.raises(ValueError):
            label_unlabeled_source('不存在的来源')

    def test_backfill_makes_unlabeled_vanish(self):
        """补记之后，来源总览里「未标注」归零 —— 这才是这次修复的验收口径。"""
        _mk('手工记的', '2026-03-02 09:00:00', 1.0, None)
        assert list_record_sources()['unlabeled_count'] == 1
        label_unlabeled_source('manual', dry_run=False)
        overview = list_record_sources()
        assert overview['unlabeled_count'] == 0
        manual = next(k for k in overview['kinds'] if k['kind'] == 'manual')
        assert manual['count'] == 1
        # 手工录入是一个真实批次（裸词 'manual'），不是「一批一个」
        assert manual['batches'] == 1


class TestAtrackerKind:
    """旧库迁移也必须有名有姓 —— 它此前**完全不写**来源，重跑一次就灌一批空值。"""

    def test_atracker_batch_classified(self):
        info = classify_source('atracker')
        assert info['kind'] == 'atracker'
        assert info['label'] == '旧库迁移'
        assert info['hint'], '来源要有说明，否则界面上一堆看不懂的词'

    def test_atracker_is_not_unlabeled(self):
        assert classify_source('atracker')['kind'] != classify_source(None)['kind']
