"""赎回期 · 计算函数 + 端点退役回归

2026-11-02（v3.64.20）起本 app **无模型、无端点**：「三年赎回期」已经变成自我运转
下的一个长阶段，界面与接口都在那边（`GET /api/selfrun/stages/<pk>/ledger/`）。
这里只剩两件事要钉：

1. **计算函数的契约**：六类小时之和 == `covered_hours`、兜底也计入、笔数用 `Count`。
   这些口径与阶段账本共用同一份实现 —— 它们坏了，账本会**静默**给出合理但错的数。
2. **六条旧端点全部 404**：留着半死的接口比删干净更危险（旧页面还能写出另一套归因）。
"""
import datetime as dt

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.redemption import services
from apps.temporal.models import TemporalTask, TaskMeta
from apps.wealth.models import WealthBillList

pytestmark = pytest.mark.django_db

START = dt.date(2026, 10, 1)
END = dt.date(2029, 9, 30)


def _bill(days_ago, amount, *, period_tag='为自己', transaction_type='支出'):
    """一笔账单。`created_at` / `updated_at` 是 NOT NULL 且**无默认值**
    （`managed=False` 的遗留表，测试库镜像 DDL 不跑迁移）⇒ 必须显式给。"""
    day = timezone.localdate() - dt.timedelta(days=days_ago)
    stamp = timezone.make_aware(dt.datetime.combine(day, dt.time(10, 0)))
    return WealthBillList.objects.create(
        transaction_type=transaction_type, date=stamp, category='测试',
        period_tag=period_tag, amount=amount,
        year=day.year, month=day.month, day=day.day,
        created_at=stamp, updated_at=stamp,
    )


def _task(name, hours, *, when=dt.datetime(2026, 10, 5, 9, 0)):
    return TemporalTask.objects.create(
        task_name=name, task_type=name,
        start_time=when, end_time=when + dt.timedelta(hours=hours),
        duration_hours=hours, year=2026, mon='10', day=5, week=40,
    )


# ══════════════════════════════════════════════════════════════
# 一、计算函数
# ══════════════════════════════════════════════════════════════

class TestPoolBalance:
    def test_balance_includes_principal_inject_and_self_expense(self):
        """余额 = 本金 + 注入 − 为自己支出 + 为自己收入。

        🔴 注入是**参数**不是查表（v3.64.20）：函数连模型都不 import，
           才能被任意阶段复用；查哪张表由调用方决定。
        """
        _bill(1, 3000)                                     # 为自己支出
        _bill(2, 500, transaction_type='收入')              # 为自己收入
        _bill(3, 9999, period_tag='为别人')                 # 不算进池
        pool = services.compute_pool_balance(100000, START, END, injected=5000)
        assert pool['principal'] == 100000.0
        assert pool['injected'] == 5000.0
        assert pool['self_expense'] == 3000.0
        assert pool['self_income'] == 500.0
        assert pool['balance'] == 102500.0

    def test_window_is_half_open(self):
        """区间是 `[start, end)`：终点那天的记录不算，起点那天算。

        ⚠️ 半开是为了躲 `USE_TZ` 下 `__date` 的 `CONVERT_TZ` 坑；
           写成闭区间会让边界日**重复计入**（跨区间汇总时多一份）。
        """
        day = dt.datetime(2026, 10, 1, 10, 0)
        stamp = timezone.make_aware(day)
        WealthBillList.objects.create(
            transaction_type='支出', date=stamp, category='测试', period_tag='为自己',
            amount=100, year=2026, month=10, day=1,
            created_at=stamp, updated_at=stamp,
        )
        inside = services.compute_pool_balance(0, dt.date(2026, 10, 1), dt.date(2026, 10, 2))
        after = services.compute_pool_balance(0, dt.date(2026, 10, 2), dt.date(2026, 10, 3))
        assert inside['self_expense'] == 100.0
        assert after['self_expense'] == 0.0


class TestTierStats:
    def test_counts_rows_not_id_sum(self):
        """笔数按**行数**算，不是 id 之和。

        回归（2026-11-02）：旧实现 `annotate(cnt=Sum('id'))` —— 两条 id=5、9 的账单
        会显示成 **14 笔**。它不报错、也不离谱到被一眼看出（id 连续、量级相近）。
        """
        _bill(1, 100, period_tag='为自己')
        _bill(2, 200, period_tag='为自己')
        rows = {r['period_tag']: r for r in services.compute_tier_stats(START, END)}
        assert rows['为自己']['count'] == 2
        assert rows['为自己']['total'] == 300.0

    def test_empty_tag_goes_to_unmarked(self):
        _bill(1, 50, period_tag='')
        rows = {r['period_tag']: r for r in services.compute_tier_stats(START, END)}
        assert rows['unmarked']['count'] == 1


class TestTimeAttribution:
    def test_reads_mapping_table_only(self):
        """六类小时只认映射表那列，兜底也计入覆盖

        回归（2026-11-02）：此前这里按 `redemption_attr_rule` 是否命中统计，
        没配规则的任务名被**静默丢弃** —— 实测 2 天窗口 33.96h 只算了 20h，
        「成长」1.99h（真实 12.39h）、「谋生」恒为 0，全程不报错。
        """
        TaskMeta.objects.create(task_name='代码编程', activity_type='深度工作', default_attribution='成长')
        TaskMeta.objects.create(task_name='牛马工作', activity_type='浅层工作', default_attribution='谋生')
        for name, h in [('代码编程', 3.0), ('牛马工作', 2.0), ('某未登记任务', 1.5)]:
            _task(name, h)

        attr = services.compute_time_attribution(START, END)
        assert attr['covered_hours'] == 6.5      # 三条全算，不是「命中规则才算」
        assert attr['hours']['谋生'] == 2.0      # 旧口径下这一格恒为 0
        assert attr['hours']['成长'] == 4.5      # 3.0 有默认 + 1.5 兜底
        assert attr['fallback_hours'] == 1.5     # 兜底部分单独报出来，不混在明示归因里
        assert attr['toward_ratio'] == round(4.5 / 6.5, 4)

    def test_six_cells_sum_equals_covered(self):
        """🔴 跨轮验收红线：**六格之和 == `covered_hours`**。

        理由是屏幕上这六个数会被真的加起来。若总数按原始值取整，两者会差 0.0x
        （实测 33.96 被读成「六类加起来 34.00」），看起来就像「有一类没算进去」——
        而那正是本函数上一版真正的病。
        """
        TaskMeta.objects.create(task_name='A', activity_type='深度工作', default_attribution='成长')
        for name, h in [('A', 1.234), ('B', 2.345), ('C', 0.001)]:
            _task(name, h)
        attr = services.compute_time_attribution(START, END)
        assert round(sum(attr['hours'].values()), 2) == attr['covered_hours']

    def test_default_attribution_wins_over_activity_type(self):
        """归因只由映射表决定：`刷手机` 的 L2 是被动消耗，但默认归因说成长就是成长

        （旧口径下这里还有一层「外挂规则」可以覆盖 L2 与默认值；规则表退役后，
        唯一的判断依据就是 `temporal_task_meta.default_attribution`。）
        """
        TaskMeta.objects.create(task_name='刷手机', activity_type='被动消耗', default_attribution='成长')
        _task('刷手机', 1.5)
        attr = services.compute_time_attribution(START, END)
        assert attr['hours']['成长'] == 1.5
        assert attr['hours']['流失'] == 0.0


class TestSleepExcluded:
    """睡眠（夜间 + 午睡）**不进六类、不进分子**（2026-11-02）。

    为什么必须剔：覆盖率分母是「每天可支配小时」（常量 `THEORETICAL_DAILY_HOURS`，
    v3.64.25 由 12h 调到 14h），睡眠本来就不在这段时间里。分子却含睡眠 ⇒ 记录越全、覆盖率越高，
    实测两天冲到 **141.5%**，看上去像「记得比可支配的还多」。
    那不是记得多，是**同一屏上下两个数用了两把尺子**。
    """

    def test_night_sleep_and_nap_excluded(self):
        TaskMeta.objects.create(task_name='休息睡眠', activity_type='睡眠', default_attribution='维持')
        TaskMeta.objects.create(task_name='午睡', activity_type='睡眠', default_attribution='维持')
        TaskMeta.objects.create(task_name='代码编程', activity_type='深度工作', default_attribution='成长')
        for name, h in [('休息睡眠', 8.0), ('午睡', 1.5), ('代码编程', 3.0)]:
            _task(name, h)

        attr = services.compute_time_attribution(START, END)
        assert attr['hours']['维持'] == 0.0      # 睡眠原来是「维持」的大头，剔完这一格归零
        assert attr['hours']['成长'] == 3.0
        assert attr['covered_hours'] == 3.0
        assert attr['excluded_sleep_hours'] == 9.5
        assert round(sum(attr['hours'].values()), 2) == attr['covered_hours']

    def test_role_marked_sleep_name_excluded_even_if_not_in_list(self):
        """名单是**并集**：没写进常量、但标了「护栏角色」的任务名同样要剔。

        只认常量会让改过名的睡眠任务重新变成「维持」；只认角色会让还没标角色的
        那几天口径突然变宽。两者取并集才两边都不漏（与贡献图同一份名单）。
        """
        TaskMeta.objects.create(task_name='打盹', activity_type='睡眠', default_attribution='维持',
                                daily_role='nap')
        _task('打盹', 2.0)

        attr = services.compute_time_attribution(START, END)
        assert attr['hours']['维持'] == 0.0
        assert attr['covered_hours'] == 0.0
        assert attr['excluded_sleep_hours'] == 2.0

    def test_unmapped_sleep_is_not_counted_as_fallback(self):
        """没登记归因的睡眠任务**也不能**落进兜底「成长」。

        旧实现里它 `source == 'fallback'` ⇒ 8h 睡眠会被算成成长，成长占比凭空翻倍，
        而且不报错。剔睡眠必须在「摊进六类」之前做，不是在六类里挑出来减。
        """
        _task('休息睡眠', 8.0)          # 故意不建 TaskMeta
        _task('代码编程', 2.0)          # 同样没登记 ⇒ 兜底「成长」

        attr = services.compute_time_attribution(START, END)
        assert attr['hours']['成长'] == 2.0
        assert attr['fallback_hours'] == 2.0    # 只有那 2h 是兜底的
        assert attr['excluded_sleep_hours'] == 8.0

    def test_coverage_not_inflated_by_sleep(self):
        """回归数字：一天 8h 睡眠 + 10h 清醒记录 ⇒ 覆盖率 < 100%，**不是 150%**。

        ⚠️ 断言用 `THEORETICAL_DAILY_HOURS` 而不是写死 12：每天几小时可支配是**常量配置**
           （2026-11-05 用户从 12h 调到 14h），这条用例钉的是「分母 = 天数 × 常量、
           睡眠不进分子」这个口径本身，不该随配置值一起红。
        """
        day = dt.date(2026, 10, 5)      # 过去的一天 ⇒ 理论 = 1 天 × 常量
        _task('休息睡眠', 8.0, when=dt.datetime(2026, 10, 5, 0, 0))
        _task('代码编程', 10.0, when=dt.datetime(2026, 10, 5, 10, 0))

        attr = services.compute_time_attribution(day, day)
        assert attr['theoretical_hours'] == float(services.THEORETICAL_DAILY_HOURS)
        assert attr['theoretical_daily_hours'] == services.THEORETICAL_DAILY_HOURS
        assert attr['covered_hours'] == 10.0
        assert attr['coverage_rate'] == round(10.0 / services.THEORETICAL_DAILY_HOURS, 4)

    def test_covered_plus_excluded_equals_all_records(self):
        """🔴 这两个数在屏幕上是相邻的，用户真的会相加 ⇒ 必须等于全部记录。

        「已记录 21.76h」与「睡眠 12.20h 已剔除」相加应正好是区间里的 33.96h；
        差 0.0x 会读成「有一块时间没交代」。
        """
        for name, h in [('休息睡眠', 12.204), ('代码编程', 0.005), ('生活杂事', 0.005)]:
            _task(name, h)

        attr = services.compute_time_attribution(START, END)
        total = round(12.204 + 0.005 + 0.005, 2)
        assert round(attr['covered_hours'] + attr['excluded_sleep_hours'], 2) == total


class TestSupportUntil:
    def test_no_speed_gives_reason_not_infinity(self):
        """`avg_daily <= 0` 不是「永不耗尽」。

        回归（2026-11-02）：旧实现返回 `None`，页面 `|| '永不耗尽'` 就印成「钱花不完」。
        真实含义是「**还没有速度可外推**」—— `None` 在别处到处代表「算不出来」。
        """
        until, reason = services.compute_support_until(100000, 0)
        assert until is None
        assert reason == 'no_self_expense'

    def test_negative_balance_lands_in_the_past(self):
        """余额为负 ⇒ 日期落在过去。那是事实（已经超支），不夹到今天。"""
        until, reason = services.compute_support_until(-300, 100, anchor=dt.date(2026, 11, 2))
        assert reason is None
        assert until == '2026-10-30'


class TestUnitCost:
    def test_none_before_window_starts(self):
        """区间还一天没走到 ⇒ `None`（不是 0）。"""
        assert services.compute_unit_cost(
            dt.date(2099, 1, 1), dt.date(2099, 1, 2), 100,
        ) is None

    def test_divides_by_redeemed_hours(self):
        today = timezone.localdate()
        # 区间起点 = 今天 ⇒ 1 天 × 8h = 8h
        cost = services.compute_unit_cost(today, today + dt.timedelta(days=9), 800)
        assert cost == 100.0


# ══════════════════════════════════════════════════════════════
# 二、端点退役
# ══════════════════════════════════════════════════════════════

class TestEndpointsAreGone:
    """六条旧端点必须 404。

    🔴 留着「半活」的接口比删干净更危险：`POST /api/redemption/pause/` 若能调通，
       说明阶段暂停与赎回期暂停**各自存了一份状态**，两边迟早不一致。
    """

    @pytest.mark.parametrize('method,url', [
        ('get', '/api/redemption/'),
        ('put', '/api/redemption/'),
        ('post', '/api/redemption/pause/'),
        ('post', '/api/redemption/resume/'),
        ('get', '/api/redemption/stats/'),
        ('get', '/api/redemption/injects/'),
        ('post', '/api/redemption/sync-scenario/'),
        ('get', '/api/redemption/attr-rules/'),
    ])
    def test_gone(self, method, url):
        client = APIClient()
        resp = getattr(client, method)(url, {}, format='json')
        assert resp.status_code == 404, f'{method.upper()} {url} 仍可用（{resp.status_code}）'

    def test_no_models_left(self):
        """本 app 已无模型：三张表都退役或迁走，`apps.get_models()` 里不该再有它们。"""
        from django.apps import apps

        names = {m.__name__ for m in apps.get_app_config('redemption').get_models()}
        assert names == set()


# ══════════════════════════════════════════════════════════════
# 三、退役迁移的**顺序**（静态断言，不碰数据库）
# ══════════════════════════════════════════════════════════════

class TestRetireMigrationOrder:
    """`0010` 必须「先搬数据、再删表」，且排在 `selfrun 0009` 之后。

    🔴 为什么值得为顺序写一条测试：这个顺序**错了不报错**。
       - 先删表 ⇒ RunPython 读 `redemption_period` 时报「表不存在」，整条迁移中断；
       - 不依赖 `selfrun 0009` ⇒ `selfrun_pool_inject` 可能还没建，注水无处可放。
       两种都只在用户真正 `migrate` 的那一刻才暴露 —— 而那时已经在改生产数据了。
    """

    MODULE = (
        'apps.redemption.migrations.'
        '0010_delete_redemptionperiod_delete_redemptionpoolinject_and_more'
    )

    def test_run_python_comes_before_delete_model(self):
        from importlib import import_module

        from django.db import migrations

        mod = import_module(self.MODULE)
        ops = mod.Migration.operations
        kinds = [type(op).__name__ for op in ops]
        assert kinds[0] == 'RunPython', f'第一步必须是 RunPython，实际 {kinds}'
        assert all(k == 'DeleteModel' for k in kinds[1:]), f'删表之外不该有别的东西：{kinds}'
        assert len(kinds) == 4      # RunPython + 三个 DeleteModel
        assert isinstance(ops[0], migrations.RunPython)

    def test_depends_on_selfrun_new_table(self):
        from importlib import import_module

        mod = import_module(self.MODULE)
        deps = mod.Migration.dependencies
        assert ('selfrun', '0009_alter_selfrunstage_ledger_config_and_more') in deps
        assert ('redemption', '0009_delete_redemptionattrrule') in deps
