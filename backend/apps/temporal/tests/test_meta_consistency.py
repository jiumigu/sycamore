"""常量表（种子）与库（真源）的一致性治理（v3.60.37，2026-10-12）

背景：`TASK_TO_L2` 是**初始种子**，只在「库里还没有该 task_name」时生效
（`_ensure_task_meta` 建档 / `migrate_temporal_categories` 回填）；真源是
`temporal_task_meta` —— 所有统计都读库里的值。两者**允许**不一致。

但「允许」不等于「看不见」：`manage.py check_meta_consistency` 负责把三类差异摆出来。
本文件钉两件事：

① 种子表自身的**结构性不变量** —— 值写错会静默落进「未归类 / 灰兜底」，不报错；
② 命令的三类分类**不能退化** —— 造一条差异就应被认出来。

⚠️ 本文件**不**钉「种子表 == 库」。测试库里的 `temporal_task_meta` 是从种子表生成的
（或在用例里灌的），天然一致；**开发库与它的漂移**只能在真库上跑命令才看得见。
"""
import io
import json
from datetime import datetime

import pytest
from django.core.management import call_command

from apps.temporal.constants import (
    ACTIVITY_TYPE_PRESETS,
    ATTRIBUTION_CHOICES_LIST,
    LEGACY_FOUR_TO_L2,
    TASK_CATEGORY_MAPPING,
    TASK_TO_L2,
)
from apps.temporal.models import TaskMeta, TemporalTask


# ══════════════════════════════════════════════════════════════
# ① 种子表的结构性不变量（不需要库）
# ══════════════════════════════════════════════════════════════


class TestSeedTableInvariants:
    """种子表自身必须自洽 —— 写错一个值不会有任何报错，只会静默走兜底分支"""

    def test_every_l2_is_a_declared_preset(self):
        """种子里每个 L2 都必须在 ACTIVITY_TYPE_PRESETS 中声明"""
        presets = {p[0] for p in ACTIVITY_TYPE_PRESETS}
        bad = {tn: at for tn, (at, _) in TASK_TO_L2.items() if at not in presets}
        assert bad == {}, f'种子里出现未声明的 L2：{bad}'

    def test_every_l1_is_a_declared_attribution(self):
        """种子里每个 L1 都必须在 ATTRIBUTION_CHOICES_LIST 中声明"""
        valid = set(ATTRIBUTION_CHOICES_LIST)
        bad = {tn: a for tn, (_, a) in TASK_TO_L2.items() if a not in valid}
        assert bad == {}, f'种子里出现未声明的 L1：{bad}'

    def test_legacy_mapping_values_stay_in_four_categories(self):
        """`TASK_CATEGORY_MAPPING` 的值域**只能是四大类**

        它要被 `LEGACY_FOUR_TO_L2` 二次查表 —— 塞第五个值进去会 KeyError，
        而那个 KeyError 只发生在「真来了一个命中该行的新任务名」时（可能几个月后）。
        """
        assert set(TASK_CATEGORY_MAPPING.values()) <= set(LEGACY_FOUR_TO_L2)
        assert set(LEGACY_FOUR_TO_L2) == {'工作', '学习', '生活', '兴趣记录'}

    def test_legacy_mapping_is_subset_of_seed(self):
        """旧四分类表必须是种子表的**子集**

        若不是 ⇒ 「靠旧表兜住、但种子表没收录」的任务名会出现，此时
        `check_meta_consistency` 的 C 类条目 `via_legacy` 才会为 True。
        当前恒为 False，本用例钉住这个前提。
        """
        assert set(TASK_CATEGORY_MAPPING) <= set(TASK_TO_L2)

    def test_v03637_seed_values_are_pinned(self):
        """v3.60.37 三条订正 + 九条补录 —— 逐条钉住

        改错即失败：这是提醒「去跑一遍 `check_meta_consistency`」的信号，
        不是障碍（与 §1「插错位置它会立刻失败 —— 那是提醒」同一判据）。
        """
        assert TASK_TO_L2['运动健身'] == ('主动休息', '成长')
        assert TASK_TO_L2['迷谷知松'] == ('深度工作', '成长')   # 原写「兴趣记录」，与库长期不一致
        assert TASK_TO_L2['休闲娱乐'] == ('主动经历', '体验')   # 与库对齐
        for tn in ('兴趣爱好', 'ONEDAY', '刷短视频', '灰暗时光',
                   '午睡', 'DIKW计划', '休息睡眠', '拿起画笔', '精神滋养'):
            assert tn in TASK_TO_L2, f'{tn} 应自 v3.60.37 起被补录进种子表'

    def test_zombie_task_removed_from_both_tables(self):
        """「运动健康」是僵尸任务名（库与 TemporalTask 都没有）—— 两张表都不得再留

        留着它 ⇒ `check_meta_consistency` 会**永远**报一条 A 类差异，
        久而久之用户就不再读那份报告了（狼来了）。
        """
        assert '运动健康' not in TASK_TO_L2
        assert '运动健康' not in TASK_CATEGORY_MAPPING


# ══════════════════════════════════════════════════════════════
# ② check_meta_consistency 的三类分类不能退化
# ══════════════════════════════════════════════════════════════


def _run(*args) -> dict:
    """跑命令并解析 `--json` 输出"""
    buf = io.StringIO()
    call_command('check_meta_consistency', '--json', *args, stdout=buf)
    return json.loads(buf.getvalue())


def _seed_db_from_seed_table():
    """把种子表原样灌进库 ⇒ 对齐态（三类差异均为空）"""
    for tn, (at, attr) in TASK_TO_L2.items():
        TaskMeta.objects.create(task_name=tn, activity_type=at, default_attribution=attr)


def _mk(task_name: str, day: str, hours: float):
    """造一条时间记录（只为让 drift/missing 带上用量）"""
    return TemporalTask.objects.create(
        task_name=task_name, start_time=datetime.fromisoformat(f'{day} 09:00:00'),
        duration_hours=hours, year=int(day[:4]), mon=day[5:7], day=int(day[8:10]))


@pytest.mark.django_db
class TestCheckMetaConsistencyCommand:
    """命令只读；分类不能退化 —— 三类差异各有一条用例"""

    def test_aligned_returns_ok(self):
        _seed_db_from_seed_table()
        p = _run()
        assert p['seed_count'] == p['db_count'] == len(TASK_TO_L2)
        assert (p['zombie'], p['drift'], p['missing'], p['invalid'], p['unclassified']) \
            == ([], [], [], [], []), p
        assert p['ok'] is True

    def test_reports_drift_with_usage(self):
        """库里值被改过 ⇒ B 类，且带用量 —— 影响面靠这两个数说话"""
        _seed_db_from_seed_table()
        TaskMeta.objects.filter(task_name='运动健身').update(default_attribution='维持')
        _mk('运动健身', '2026-10-01', 1.5)
        _mk('运动健身', '2026-10-02', 1.5)
        p = _run()
        assert p['ok'] is False
        assert [d['task_name'] for d in p['drift']] == ['运动健身']
        d = p['drift'][0]
        assert d['seed'] == ['主动休息', '成长']
        assert d['db'] == ['主动休息', '维持']
        assert d['records'] == 2 and d['hours'] == 3.0

    def test_reports_zombie(self):
        """种子表有、库里没有 ⇒ A 类"""
        _seed_db_from_seed_table()
        TaskMeta.objects.filter(task_name='阅读思考').delete()
        p = _run()
        assert p['ok'] is False
        assert p['zombie'] == ['阅读思考']

    def test_reports_missing(self):
        """库里有、种子表没有 ⇒ C 类（将来重建库会按「未归类」建档）"""
        _seed_db_from_seed_table()
        TaskMeta.objects.create(task_name='野生任务', activity_type='被动消耗', default_attribution='流失')
        p = _run()
        assert p['ok'] is False
        assert [m['task_name'] for m in p['missing']] == ['野生任务']
        assert p['missing'][0]['via_legacy'] is False

    def test_reports_unclassified(self):
        """未归类桶也要报（activity_type=未归类 或 归因为 None）"""
        _seed_db_from_seed_table()
        TaskMeta.objects.create(task_name='待定任务', activity_type='未归类', default_attribution=None)
        p = _run()
        assert p['ok'] is False
        assert p['unclassified'] == ['待定任务']

    def test_reports_invalid_value(self):
        """库中出现非法 L2 值 ⇒ D 类"""
        _seed_db_from_seed_table()
        TaskMeta.objects.create(task_name='越界任务', activity_type='不存在的类型', default_attribution='成长')
        p = _run()
        assert p['ok'] is False
        assert [d['task_name'] for d in p['invalid']] == ['越界任务']

    def test_drift_sorted_by_hours_desc(self):
        """B 类按影响面降序 —— 用户先看大的"""
        _seed_db_from_seed_table()
        TaskMeta.objects.filter(task_name='运动健身').update(default_attribution='维持')
        TaskMeta.objects.filter(task_name='心灵冥想').update(default_attribution='维持')
        _mk('心灵冥想', '2026-10-01', 5.0)
        _mk('运动健身', '2026-10-01', 1.0)
        p = _run()
        assert [d['task_name'] for d in p['drift']] == ['心灵冥想', '运动健身']

    def test_strict_exits_nonzero_on_diff(self):
        _seed_db_from_seed_table()
        TaskMeta.objects.create(task_name='野生任务', activity_type='被动消耗', default_attribution='流失')
        with pytest.raises(SystemExit) as e:
            call_command('check_meta_consistency', '--strict', stdout=io.StringIO())
        assert e.value.code == 1

    def test_strict_exits_zero_when_aligned(self):
        _seed_db_from_seed_table()
        call_command('check_meta_consistency', '--strict', stdout=io.StringIO())   # 不抛即通过

    def test_command_does_not_write(self):
        """🔴 只读保证：命令不得增删改任何一行"""
        _seed_db_from_seed_table()
        before = list(TaskMeta.objects.order_by('id').values_list('task_name', 'activity_type', 'default_attribution'))
        _run()
        after = list(TaskMeta.objects.order_by('id').values_list('task_name', 'activity_type', 'default_attribution'))
        assert before == after
