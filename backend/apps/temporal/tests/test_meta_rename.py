"""映射编辑器 · 改名 / 合并 / 删除（v3.64.55）

守的是三件**做错了也不会报错**的事：

① **改名必须连记录一起改**。只改 `temporal_task_meta.task_name` 而不管
   `temporal_task`，这个名字会变成 0h、旧名的时长从台账整体消失 —— 接口 200，
   数字只是「少了」，没有任何地方会报错。`meta_ledger` 是遍历 TaskMeta 的，
   所以「字典里有、记录里没有」= 凭空归零；「记录里有、字典里没有」= 隐形。
② **合并以目标为准**，且差异要在点确定之前说出来（`changed_attrs`）。
   不说的话，用户的「成长计时」会在一次合并里静默关掉。
③ **有记录的名字不许删**。删了不是删数据，是让那 N 小时从台账消失、按兜底归因
   计入 —— 比删数据更糟，因为它没声音。名字下真有量时的唯一出口是「合并」。
"""
import datetime as dt

import pytest
from rest_framework.test import APIClient

from apps.temporal.models import TaskMeta, TemporalTask, TimerSession

pytestmark = pytest.mark.django_db

RENAME = '/api/temporal/tasks/rename_task_name/'
DELETE = '/api/temporal/tasks/delete_task_name/'
LEDGER = '/api/temporal/tasks/meta_ledger/'


def _meta(name, activity_type='维护性事务', attribution='维持', *, growth=False, role='', note=''):
    return TaskMeta.objects.create(
        task_name=name, activity_type=activity_type, default_attribution=attribution,
        counts_growth=growth, daily_role=role, note=note,
    )


def _rec(name, hours, day='2026-08-01'):
    return TemporalTask.objects.create(
        task_name=name, start_time=dt.datetime.fromisoformat(f'{day} 09:00:00'),
        duration_hours=hours, year=int(day[:4]), mon=day[5:7], day=int(day[8:10]),
    )


def _rename(task_name, new_name, **extra):
    return APIClient().post(RENAME, {'task_name': task_name, 'new_name': new_name, **extra},
                            format='json')


def _ledger():
    r = APIClient().get(LEDGER)
    assert r.status_code == 200, r.data
    return {i['task_name']: i for i in r.data['items']}, r.data['summary']


# ══════════════════════════════════════════════════════════════
# ① 改名
# ══════════════════════════════════════════════════════════════

class TestRename:
    def test_records_follow_the_name(self):
        """改的是名字，不是记录 —— 记录必须一起搬，否则时长凭空归零"""
        _meta('冥想', '主动休息', '成长')
        _rec('冥想', 1.5)
        _rec('冥想', 2.5)

        r = _rename('冥想', '心灵冥想')
        assert r.status_code == 200, r.data
        assert r.data['merged'] is False
        assert r.data['moved_records'] == 2
        assert r.data['moved_hours'] == 4.0

        assert not TaskMeta.objects.filter(task_name='冥想').exists()
        assert TaskMeta.objects.get(task_name='心灵冥想').activity_type == '主动休息'
        assert TemporalTask.objects.filter(task_name='心灵冥想').count() == 2
        assert TemporalTask.objects.filter(task_name='冥想').count() == 0

    def test_ledger_total_hours_unchanged(self):
        """同一把尺子：改名前后的台账总时长必须分毫不差"""
        _meta('整理房间', '维护性事务', '维持')
        _meta('日常家务', '维护性事务', '维持')
        _rec('整理房间', 3.0)
        _rec('日常家务', 2.0)
        _before = _ledger()[1]['total_hours']

        assert _rename('整理房间', '整理收纳').status_code == 200
        assert _ledger()[1]['total_hours'] == _before

    def test_case_only_rename_does_not_delete_itself(self):
        """只改大小写：MySQL 的 ci 排序会把「自己」当成目标命中

        `filter(task_name='abc')` 在 `utf8mb4_general_ci` 下也能捞到 'Abc'，
        于是「改名」会被误判成「并到自己身上」—— 合并分支一删，这行就没了。
        判据必须按主键排掉自己。
        """
        _meta('abc', '维护性事务', '维持')
        _rec('abc', 1.0)

        r = _rename('abc', 'Abc')
        assert r.status_code == 200, r.data
        assert r.data['merged'] is False
        # ⚠️ 不能写 `filter(task_name='abc').count() == 0` 来证明「旧名没了」——
        #    ci 排序下这条查询连 'Abc' 一起命中，永远非 0。只能取实际值逐字比。
        assert list(TaskMeta.objects.values_list('task_name', flat=True)) == ['Abc']

    def test_keeps_attributes_and_moves_running_timer(self):
        """属性跟着名字走；正在跑的那段计时也要改，否则它一停止就把旧名写回来"""
        _meta('跑步', '运动健身', '维持', growth=True, role='nap')
        TimerSession.objects.create(
            task_name='跑步', start_time=dt.datetime(2026, 8, 1, 9, 0), status='running',
        )

        assert _rename('跑步', '慢跑').status_code == 200
        m = TaskMeta.objects.get(task_name='慢跑')
        assert (m.activity_type, m.default_attribution, m.counts_growth, m.daily_role) == (
            '运动健身', '维持', True, 'nap')
        assert TimerSession.objects.get().task_name == '慢跑'


# ══════════════════════════════════════════════════════════════
# ② 合并（新名已存在）
# ══════════════════════════════════════════════════════════════

class TestMerge:
    def test_records_join_target_and_source_row_is_gone(self):
        _meta('冥想', '主动休息', '成长')
        _meta('心灵冥想', '主动休息', '成长')
        _rec('冥想', 1.0)
        _rec('心灵冥想', 2.0)

        r = _rename('冥想', '心灵冥想')
        assert r.status_code == 200, r.data
        assert r.data['merged'] is True
        assert r.data['moved_records'] == 1

        assert not TaskMeta.objects.filter(task_name='冥想').exists()
        assert TemporalTask.objects.filter(task_name='心灵冥想').count() == 2
        assert _ledger()[0]['心灵冥想']['total_hours'] == 3.0

    def test_target_attributes_win_and_differences_are_reported(self):
        """合并以目标为准 —— 但差异必须提前说出来，不能等用户发现成长计时关了"""
        _meta('冥想', '深度工作', '成长', growth=True, role='nap')
        _meta('心灵冥想', '主动休息', '维持')

        r = _rename('冥想', '心灵冥想')
        assert r.status_code == 200, r.data
        assert r.data['kept']['default_attribution'] == '维持'
        assert r.data['kept']['counts_growth'] is False
        assert set(r.data['changed_attrs']) == {'L2 类型', 'L1 归因', '成长计时', '护栏角色'}

        m = TaskMeta.objects.get(task_name='心灵冥想')
        assert (m.activity_type, m.default_attribution, m.counts_growth, m.daily_role) == (
            '主动休息', '维持', False, '')

    def test_source_note_is_not_lost(self):
        _meta('冥想', note='睡前十分钟')
        _meta('心灵冥想')

        assert _rename('冥想', '心灵冥想').status_code == 200
        assert '睡前十分钟' in TaskMeta.objects.get(task_name='心灵冥想').note


# ══════════════════════════════════════════════════════════════
# ③ 删除
# ══════════════════════════════════════════════════════════════

class TestDelete:
    def test_empty_name_can_be_deleted(self):
        """幽灵行（登记时写了一半的名字）就该能删掉"""
        _meta('冥想')

        r = APIClient().post(DELETE, {'task_name': '冥想'}, format='json')
        assert r.status_code == 200, r.data
        assert not TaskMeta.objects.filter(task_name='冥想').exists()

    def test_name_with_records_is_refused_and_nothing_changes(self):
        """有量时拒绝：删了不是删数据，是让那 N 小时从台账消失且不报错"""
        _meta('整理房间')
        _rec('整理房间', 5.0)

        r = APIClient().post(DELETE, {'task_name': '整理房间'}, format='json')
        assert r.status_code == 400
        assert '1 条记录' in r.data['error']
        assert TaskMeta.objects.filter(task_name='整理房间').exists()
        assert TemporalTask.objects.filter(task_name='整理房间').count() == 1

    def test_running_timer_blocks_delete(self):
        """0 记录但正在计时：删了下一步就复活"""
        _meta('摄影学习')
        TimerSession.objects.create(
            task_name='摄影学习', start_time=dt.datetime(2026, 8, 1, 9, 0), status='running',
        )

        r = APIClient().post(DELETE, {'task_name': '摄影学习'}, format='json')
        assert r.status_code == 400
        assert '正在计时' in r.data['error']


# ══════════════════════════════════════════════════════════════
# ④ 预演与校验
# ══════════════════════════════════════════════════════════════

class TestDryRunAndValidation:
    def test_dry_run_writes_nothing(self):
        _meta('冥想')
        _meta('心灵冥想')
        _rec('冥想', 4.0)
        before = list(TaskMeta.objects.order_by('pk').values_list('task_name', flat=True))

        r = _rename('冥想', '心灵冥想', dry_run=1)
        assert r.status_code == 200
        assert r.data['dry_run'] is True and r.data['merged'] is True
        assert r.data['moved_hours'] == 4.0
        assert list(TaskMeta.objects.order_by('pk').values_list('task_name', flat=True)) == before
        assert TemporalTask.objects.filter(task_name='冥想').count() == 1

    @pytest.mark.parametrize('old,new,word', [
        ('冥想', '   ', '不能为空'),
        ('冥想', '冥想', '新旧名字相同'),
        ('不存在的名字', 'x', '不在映射表里'),
        ('冥想', 'x' * 256, '255'),
    ])
    def test_bad_input_is_rejected_with_a_sentence(self, old, new, word):
        _meta('冥想')
        r = _rename(old, new)
        assert r.status_code == 400
        assert word in r.data['error']
        # 拒绝就是拒绝：一行都不许动
        assert TaskMeta.objects.filter(task_name='冥想').exists()
