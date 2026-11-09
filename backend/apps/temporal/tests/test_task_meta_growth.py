"""映射编辑器 · 「成长计时」开关（v3.64.11）

守三件事：

① **开关是唯一依据**：`temporal_task_meta.counts_growth` 决定每周状态的成长小时数。
   此前是隐式的「L2 活动类型 = 深度工作」—— 界面上看不见，想拉一个新分类进来
   只能把它塞进「深度工作」桶；把某项任务挪走又会顺手改掉成长口径。
② **台账要能看见它**：`meta_ledger` 下发 `counts_growth`，并支持 `growth_only` 筛选；
   概要里有 `growth_count` / `growth_hours`（改开关时能立刻看到动了多少量）。
③ **批量改别的东西不能顺手清掉它**：`counts_growth` 不传 = 「别动」。
   写成 `bool(data.get(...))` 就会「不传 ⇒ False ⇒ 整批清零」，且不报错。
"""
import datetime as dt

import pytest
from rest_framework.test import APIClient

from apps.temporal.models import TaskMeta, TemporalTask

pytestmark = pytest.mark.django_db

LEDGER = '/api/temporal/tasks/meta_ledger/'
BATCH = '/api/temporal/tasks/batch_set_meta/'


def _mk(name, activity_type, *, growth=False, attribution='成长'):
    return TaskMeta.objects.create(
        task_name=name, activity_type=activity_type,
        default_attribution=attribution, counts_growth=growth,
    )


def _hours(name, hours, day='2026-08-01'):
    TemporalTask.objects.create(
        task_name=name, start_time=dt.datetime.fromisoformat(f'{day} 09:00:00'),
        duration_hours=hours, year=int(day[:4]), mon=day[5:7], day=int(day[8:10]),
    )


def _ledger(query=''):
    r = APIClient().get(f'{LEDGER}{query}')
    assert r.status_code == 200, r.data
    return r.data


def _batch(payload, *, expect=200):
    r = APIClient().post(BATCH, payload, format='json')
    assert r.status_code == expect, r.data
    return r.data


class TestLedgerExposesGrowth:
    def test_row_carries_flag(self):
        """每一行都要带 `counts_growth`：前端那一列开关的值就来自它。"""
        _mk('写作', '深度工作', growth=True)
        _mk('刷手机', '被动消耗', growth=False)
        items = {i['task_name']: i for i in _ledger()['items']}
        assert items['写作']['counts_growth'] is True
        assert items['刷手机']['counts_growth'] is False

    def test_summary_counts_flagged_only(self):
        """概要的成长小计按标记算，**不按 L2** —— 这正是这次改口径的要点。"""
        _mk('写作', '深度工作', growth=True)
        _mk('投简历', '浅层工作', growth=True)      # 非深度工作，但勾了 ⇒ 要算
        _mk('刷手机', '被动消耗', growth=False)
        _hours('写作', 6)
        _hours('投简历', 2)
        _hours('刷手机', 100)
        s = _ledger()['summary']
        assert s['growth_count'] == 2
        assert s['growth_hours'] == 8.0

    def test_growth_only_filter(self):
        """筛选「仅计入成长计时」：与「仅未归类」是同级的筛选态，不是新维度。"""
        _mk('写作', '深度工作', growth=True)
        _mk('刷手机', '被动消耗', growth=False)
        names = [i['task_name'] for i in _ledger('?growth_only=1')['items']]
        assert names == ['写作']


class TestBatchSetGrowth:
    def test_growth_only_does_not_touch_l2(self):
        """只翻开关：L2 与归因都不动（`counts_growth` 缺席 = 别动，不是 False）"""
        _mk('写作', '深度工作', growth=False)

        d = _batch({'task_names': ['写作'], 'counts_growth': True})
        assert d['updated'] == 1
        row = TaskMeta.objects.get(task_name='写作')
        assert row.counts_growth is True
        assert row.activity_type == '深度工作'      # 没被顺手改掉
        assert row.default_attribution == '成长'    # 归因也没被顺手改掉

    def test_can_turn_it_off(self):
        _mk('写作', '深度工作', growth=True)
        _batch({'task_names': ['写作'], 'counts_growth': False})
        assert TaskMeta.objects.get(task_name='写作').counts_growth is False

    def test_absent_key_means_do_not_touch(self):
        """🔴 回归：批量改 L2 时**不传** `counts_growth` ⇒ 一个都不许清零。

        旧写法 `bool(request.data.get('counts_growth'))` 会让「不传」变成「全部关掉」——
        用户只是换个分类，成长计时整个归零，而且没有任何报错。
        """
        _mk('写作', '深度工作', growth=True)
        _batch({'task_names': ['写作'], 'activity_type': '浅层工作', 'keep_default': True})
        row = TaskMeta.objects.get(task_name='写作')
        assert row.activity_type == '浅层工作'
        assert row.counts_growth is True, '改 L2 不该顺手把成长计时清零'

    def test_both_fields_in_one_call(self):
        """同时改 L2 和开关：两个都落库（批量弹窗那条路径）。"""
        _mk('写作', '被动消耗', growth=False)
        _batch({'task_names': ['写作'], 'activity_type': '浅层工作',
                'counts_growth': True, 'keep_default': True})
        row = TaskMeta.objects.get(task_name='写作')
        assert row.activity_type == '浅层工作'
        assert row.counts_growth is True

    def test_unknown_name_is_an_error_not_a_silent_zero(self):
        """只改开关时，任务名不存在 ⇒ 400 且**不新建行**（否则会凭空多出一条「未归类」）。"""
        d = _batch({'task_names': ['查无此任务'], 'counts_growth': True}, expect=400)
        assert '查无此任务' in d['error']
        assert TaskMeta.objects.count() == 0

    def test_needs_one_of_two_fields(self):
        """什么都不给 ⇒ 400（不许回「已更新 0 个」让人以为生效了）。"""
        _mk('写作', '深度工作')
        _batch({'task_names': ['写作']}, expect=400)
