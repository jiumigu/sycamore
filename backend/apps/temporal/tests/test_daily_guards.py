"""仪表盘「今天的三条线」：睡眠 / 午睡 / 流失（v3.64.13）

守五件事：

① **口径分两支尺子**：夜间睡眠按「醒来那一刻」归属日期，午睡/流失按开始时刻。
   混成一支就会出现「上午打开页面永远显示今天还没睡」—— 不报错、数字看着合理。
② **未记录 ≠ 达标**：`unrecorded` 是**独立一档**，没记就是没记，不拿 0 小时冒充。
③ **角色只用于睡眠类**：`TaskMeta.daily_role`，不看任务名 —— 改名不会让护栏静默失效。
   没配与「配了但今天没记」是**两种不同的没有**，文案必须分开。
④ **流失按 L1 归因**：与贡献图/统计页同一把尺子（`resolve_attribution` → 映射表的
   `default_attribution` + 兜底），而不是在护栏里另推一套 ——
   两套口径会得出两个都「看着合理」的数。
⑤ **批量改别的字段不能顺手清角色**：`daily_role` 不传 = 「别动」；空串 = 「退出护栏」。
   这两个若混为一谈，「改回不参与」会变成一个不发请求的假操作。
"""
import datetime as dt

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.temporal.models import TaskMeta, TemporalTask
from apps.temporal.services import contrib_excluded_names, compute_daily_guards

pytestmark = pytest.mark.django_db

GUARDS = '/api/temporal/tasks/daily_guards/'
BATCH = '/api/temporal/tasks/batch_set_meta/'


def _meta(name, role='', *, growth=False, activity_type='主动休息', attribution='维持'):
    return TaskMeta.objects.create(
        task_name=name, activity_type=activity_type,
        default_attribution=attribution, counts_growth=growth, daily_role=role,
    )


def _rec(name, start, hours):
    """`start` 写成 'YYYY-MM-DD HH:MM'，按本地时区上时区（USE_TZ=True）。"""
    naive = dt.datetime.strptime(start, '%Y-%m-%d %H:%M')
    TemporalTask.objects.create(
        task_name=name, start_time=timezone.make_aware(naive), duration_hours=hours,
        year=naive.year, mon=f'{naive.month:02d}', day=naive.day,
    )


def _line(data, key):
    return next(l for l in data['lines'] if l['key'] == key)


class TestWakeupDayAttribution:
    """夜间睡眠：按醒来那一刻归属 —— 这是全链路最容易做错的一处。"""

    def test_2300_sleep_counts_for_tomorrow(self):
        _meta('休息睡眠', 'sleep_night')
        _rec('休息睡眠', '2026-10-31 23:14', 8.0)      # 11-01 07:14 醒

        today = compute_daily_guards(dt.date(2026, 11, 1))
        sleep = _line(today, 'sleep')
        assert sleep['value_hours'] == 8.0
        assert sleep['status'] == 'ok'

        # 反过来：不算到入睡那天（否则 11-01 白天看会是「今天还没睡」）
        yesterday = compute_daily_guards(dt.date(2026, 10, 31))
        assert _line(yesterday, 'sleep')['value_hours'] is None
        assert _line(yesterday, 'sleep')['status'] == 'unrecorded'

    def test_same_day_two_sleeps_do_not_double_count(self):
        """一天两觉（00:05 与 23:19）：只有 00:05 那条醒来在当天。"""
        _meta('休息睡眠', 'sleep_night')
        _rec('休息睡眠', '2026-10-18 00:05', 7.0)      # 10-18 07:05 醒
        _rec('休息睡眠', '2026-10-18 23:19', 7.8)      # 10-19 07:07 醒

        d18 = _line(compute_daily_guards(dt.date(2026, 10, 18)), 'sleep')
        assert d18['value_hours'] == 7.0
        assert d18['status'] == 'off'
        assert d18['gap_text'] == '差 1 小时'

        d19 = _line(compute_daily_guards(dt.date(2026, 10, 19)), 'sleep')
        assert d19['value_hours'] == 7.8


class TestStartDayAttribution:
    """午睡 / 流失：按开始时刻归属（都不跨日）。"""

    def test_nap_over_threshold(self):
        _meta('午睡', 'nap')
        _rec('午睡', '2026-11-01 12:38', 3.5)
        nap = _line(compute_daily_guards(dt.date(2026, 11, 1)), 'nap')
        assert nap['value_hours'] == 3.5
        assert nap['status'] == 'off'
        assert nap['status_text'] == '越线'
        assert nap['gap_text'] == '超 2 小时'

    def test_nap_within_threshold(self):
        _meta('午睡', 'nap')
        _rec('午睡', '2026-11-01 12:38', 1.2)
        nap = _line(compute_daily_guards(dt.date(2026, 11, 1)), 'nap')
        assert nap['status'] == 'ok'
        assert nap['status_text'] == '达标'


class TestLostIsAttributionDriven:
    """流失：只看 L1 归因，**不需要任何角色标记** —— 这正是换掉「游戏」那条线的收益。"""

    def test_multiple_lost_names_accumulate_without_any_role(self):
        """玩游戏 + 刷短视频 + 看小说 合起来才是「玩手机」，缺一项就低估。"""
        _meta('玩游戏', attribution='流失')
        _meta('刷短视频', attribution='流失')
        _meta('看小说', attribution='流失')
        _rec('玩游戏', '2026-11-01 10:00', 1.5)
        _rec('刷短视频', '2026-11-01 14:00', 2.0)
        _rec('看小说', '2026-11-01 21:00', 1.2)

        lost = _line(compute_daily_guards(dt.date(2026, 11, 1)), 'lost')
        assert lost['value_hours'] == 4.7
        assert lost['status'] == 'off'
        assert lost['gap_text'] == '超 0.7 小时'
        assert lost['record_count'] == 3
        # 归因线没有「角色」这回事，永远算「已配置」（只要台账里有归到流失的任务名）
        assert lost['configured'] is True

    def test_boundary_is_inclusive(self):
        """恰好 4 小时算达标 —— 门槛是「不超过」，不是「小于」。"""
        _meta('玩游戏', attribution='流失')
        _rec('玩游戏', '2026-11-01 10:00', 4.0)
        lost = _line(compute_daily_guards(dt.date(2026, 11, 1)), 'lost')
        assert lost['status'] == 'ok'
        assert lost['status_text'] == '达标'

    def test_non_lost_is_not_counted(self):
        """成长类任务不因为「坐着不动」就被算成流失。"""
        _meta('阅读思考', attribution='成长')
        _meta('玩游戏', attribution='流失')
        _rec('阅读思考', '2026-11-01 09:00', 3.0)
        _rec('玩游戏', '2026-11-01 20:00', 1.0)
        lost = _line(compute_daily_guards(dt.date(2026, 11, 1)), 'lost')
        assert lost['value_hours'] == 1.0

    def test_unclassified_defaults_to_growth_not_lost(self):
        """台账里没有的任务名走兜底归因「成长」——**绝不能兜到流失**，否则人人天天越线。"""
        _rec('某个还没归类的新任务', '2026-11-01 09:00', 5.0)
        lost = _line(compute_daily_guards(dt.date(2026, 11, 1)), 'lost')
        assert lost['value_hours'] is None
        assert lost['status'] == 'unrecorded'

    def test_lost_follows_mapping_table_not_l2(self):
        """🔴 判据是映射表那列（`default_attribution`），不是 L2 类型预设

        两条记录 L2 同为「被动消耗」，默认归因一条写「成长」一条写「流失」，
        只有后者算流失。防的是「另写一套按 L2 推归因」的实现 ——
        那样页面上的流失会与贡献图对不上，而且两边都「看着合理」。
        """
        _meta('某项消遣', activity_type='被动消耗', attribution='成长')
        _meta('某项消耗', activity_type='被动消耗', attribution='流失')
        _rec('某项消遣', '2026-11-01 15:00', 3.0)
        _rec('某项消耗', '2026-11-01 16:00', 4.5)
        lost = _line(compute_daily_guards(dt.date(2026, 11, 1)), 'lost')
        assert lost['value_hours'] == 4.5

    def test_other_day_is_not_counted(self):
        _meta('玩游戏', attribution='流失')
        _rec('玩游戏', '2026-10-31 20:00', 3.0)
        lost = _line(compute_daily_guards(dt.date(2026, 11, 1)), 'lost')
        assert lost['value_hours'] is None

    def test_late_night_lost_counts_for_start_day(self):
        """22:00 玩到凌晨 1 点：整段归**开始日**（跨日不劈半，午睡/流失同一支尺子）。"""
        _meta('玩游戏', attribution='流失')
        _rec('玩游戏', '2026-11-01 22:00', 3.0)
        assert _line(compute_daily_guards(dt.date(2026, 11, 1)), 'lost')['value_hours'] == 3.0
        assert _line(compute_daily_guards(dt.date(2026, 11, 2)), 'lost')['value_hours'] is None


class TestUnrecordedIsNotOk:
    """🔴 没记录就是没记录：不落成 0，也不落成达标。"""

    def test_unrecorded_has_null_value_and_neutral_status(self):
        _meta('午睡', 'nap')
        nap = _line(compute_daily_guards(dt.date(2026, 11, 1)), 'nap')
        assert nap['status'] == 'unrecorded'
        assert nap['status_text'] == '未记录'
        assert nap['value_hours'] is None      # 不是 0
        assert nap['value_text'] == '—'

    def test_unconfigured_says_so_instead_of_no_records(self):
        """没标角色 ≠ 今天没做：两句文案必须不同，否则用户会去翻记录找不存在的缺失。"""
        nap = _line(compute_daily_guards(dt.date(2026, 11, 1)), 'nap')
        assert nap['configured'] is False
        assert '还没标' in nap['detail_text']

        _meta('午睡', 'nap')
        nap2 = _line(compute_daily_guards(dt.date(2026, 11, 1)), 'nap')
        assert nap2['configured'] is True
        assert '还没标' not in nap2['detail_text']

    def test_configured_lines_counter(self):
        assert compute_daily_guards(dt.date(2026, 11, 1))['configured_lines'] == 0
        _meta('休息睡眠', 'sleep_night')
        _meta('午睡', 'nap')
        assert compute_daily_guards(dt.date(2026, 11, 1))['configured_lines'] == 2
        # 归因线（流失）也要算进「已落地」，否则提示永远说「还有 1 条没配」
        _meta('玩游戏', attribution='流失')
        assert compute_daily_guards(dt.date(2026, 11, 1))['configured_lines'] == 3

    def test_lost_unconfigured_says_no_name_points_to_lost(self):
        """台账里一个归到流失的任务名都没有 ⇒ 这条线永远不可能亮，必须说清是**配置**问题。"""
        lost = _line(compute_daily_guards(dt.date(2026, 11, 1)), 'lost')
        assert lost['configured'] is False
        assert '还没有任务名归到「流失」' in lost['detail_text']

        _meta('玩游戏', attribution='流失')
        lost2 = _line(compute_daily_guards(dt.date(2026, 11, 1)), 'lost')
        assert lost2['configured'] is True
        assert lost2['detail_text'] == '今天没有流失记录'


class TestEndpoint:
    def test_defaults_to_today(self):
        r = APIClient().get(GUARDS)
        assert r.status_code == 200
        assert r.data['date'] == timezone.localdate().isoformat()

    def test_accepts_date_param(self):
        r = APIClient().get(f'{GUARDS}?date=2026-11-01')
        assert r.status_code == 200
        assert r.data['date'] == '2026-11-01'

    def test_bad_date_is_400(self):
        assert APIClient().get(f'{GUARDS}?date=2026/11/01').status_code == 400


class TestRoleIsTheOnlySource:
    def test_role_drives_contrib_exclusion(self):
        """标成睡眠类的任务名自动进贡献图排除名单（与常量名单取并集）。"""
        _meta('小睡', 'nap')
        assert '小睡' in contrib_excluded_names()
        # 老名字仍在（常量兜底，防库没标时贡献图口径突然变宽）
        assert {'休息睡眠', '午睡'} <= contrib_excluded_names()

    def test_lost_role_gone_but_contrib_unaffected(self):
        """撤掉「游戏」角色后，流失类任务名照旧**不**进贡献图排除名单。"""
        _meta('玩游戏', attribution='流失')
        assert '玩游戏' not in contrib_excluded_names()


class TestBatchSetRole:
    def test_set_role_only_does_not_touch_l2(self):
        _meta('小睡', '', activity_type='休闲娱乐')
        r = APIClient().post(BATCH, {'task_names': ['小睡'], 'daily_role': 'nap'}, format='json')
        assert r.status_code == 200, r.data
        row = TaskMeta.objects.get(task_name='小睡')
        assert row.daily_role == 'nap'
        assert row.activity_type == '休闲娱乐'

    def test_empty_string_clears_role(self):
        """🔴 空串是**有效值**（退出护栏），必须真的落库，不能被 `if (role)` 吞掉。"""
        _meta('小睡', 'nap')
        r = APIClient().post(BATCH, {'task_names': ['小睡'], 'daily_role': ''}, format='json')
        assert r.status_code == 200, r.data
        assert TaskMeta.objects.get(task_name='小睡').daily_role == ''

    def test_absent_key_means_do_not_touch(self):
        _meta('休息睡眠', 'sleep_night', growth=True)
        APIClient().post(BATCH, {'task_names': ['休息睡眠'], 'counts_growth': False}, format='json')
        row = TaskMeta.objects.get(task_name='休息睡眠')
        assert row.counts_growth is False
        assert row.daily_role == 'sleep_night', '只翻成长计时不该把护栏角色清掉'

    def test_both_flags_in_one_call(self):
        _meta('写作', '', activity_type='深度工作')
        APIClient().post(
            BATCH, {'task_names': ['写作'], 'counts_growth': True, 'daily_role': 'nap'}, format='json',
        )
        row = TaskMeta.objects.get(task_name='写作')
        assert row.counts_growth is True
        assert row.daily_role == 'nap'

    def test_invalid_role_is_400(self):
        _meta('写作', '')
        r = APIClient().post(BATCH, {'task_names': ['写作'], 'daily_role': 'sleep'}, format='json')
        assert r.status_code == 400

    def test_game_role_is_rejected(self):
        """v3.64.13 撤掉的角色不能再被写进来 —— 否则下拉里没有、库里却有，没人看得出。"""
        _meta('玩游戏', '')
        r = APIClient().post(BATCH, {'task_names': ['玩游戏'], 'daily_role': 'game'}, format='json')
        assert r.status_code == 400


class TestLedgerExposesRole:
    def test_row_and_summary(self):
        _meta('休息睡眠', 'sleep_night')
        _meta('午睡', 'nap')
        _meta('刷手机', '')
        r = APIClient().get('/api/temporal/tasks/meta_ledger/')
        items = {i['task_name']: i for i in r.data['items']}
        assert items['休息睡眠']['daily_role'] == 'sleep_night'
        assert items['刷手机']['daily_role'] == ''
        assert r.data['summary']['role_count'] == 2

    def test_role_only_filter(self):
        _meta('休息睡眠', 'sleep_night')
        _meta('刷手机', '')
        r = APIClient().get('/api/temporal/tasks/meta_ledger/?role_only=1')
        assert [i['task_name'] for i in r.data['items']] == ['休息睡眠']
