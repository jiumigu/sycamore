"""自我运转 · 阶段账本（v3.65.0 第 2 轮）

覆盖 `docs/赎回期并入自我运转-实施清单-20261102.md` §2.6 的 5 条，另加 5 条边界。

三条口径缺陷各钉一条 —— 它们共同的长相是「**不报错、数看着合理**」：

① `support_until` 的 `avg_daily <= 0` 返回 `None` ⇒ 页面印「永不耗尽」。
   `None` 在别处代表「算不出来」，这里被读成「无穷」—— 0 被当成了 ∞。
② `compute_tier_stats` 用 `Sum('id')` 当笔数 ⇒ 2 条账单显示成 14 笔。
   账单 id 连续、量级相近，所以这个错**永远不会离谱到被一眼看出**。
③ 覆盖率不许夹到 100%：数字照实、进度条自己封顶。
   ⚠️ 2026-11-02 起分子**已剔睡眠**（与分母「每天可支配小时」同口径，v3.64.25 由 12h 调到 14h），
   所以 141.5% 那种「超 100%」正常不该再出现；仍保留不夹的处理方式。

另加一条红线：**六类小时之和必须等于 `covered_hours`**
（账本把除睡眠外的全部记录摊进六类，兜底的只单列、不排除）。
"""
import datetime as dt

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.selfrun.models import SelfRunStage
from apps.selfrun.readers import module_value
from apps.selfrun.services import stage_ledger
from apps.temporal.models import TaskMeta, TemporalTask
from apps.wealth.models import WealthBillList

pytestmark = pytest.mark.django_db

URL = '/api/selfrun'


@pytest.fixture
def client():
    return APIClient()


# ── 造数 ────────────────────────────────────────────────────
def _long_stage(*, days=10, principal=96000, status='active', end_days=0):
    """直接 ORM 造长阶段：要精确控制区间天数（「剩余天数」的分母就是它）。

    ⚠️ 走 API 也能建，但 `start_date` 是只读、{服务层默认今天}，
       于是总天数恒为 1 —— 算不出「剩余余额 ÷ 剩余天数」这条要测的公式。
    `end_days>0` ⇒ 终点落在今天之后，`remaining_days` 才不是 0
       （默认 `end=today` 时阶段已走完，允许日均必然是 `no_day_left`）。
    """
    today = timezone.localdate()
    return SelfRunStage.objects.create(
        name='三年赎回期', start_date=today - dt.timedelta(days=days - 1),
        end_date=today + dt.timedelta(days=end_days), status=status,
        ledger_config={'pool_principal': principal} if principal is not None else {},
    )


def _bill(days_ago, amount, *, period_tag='为自己', transaction_type='支出'):
    """一笔账单。`created_at` / `updated_at` 在库里是 NOT NULL 且**无默认值**
    （`managed=False` 的遗留表，测试库镜像 DDL 不跑迁移）⇒ 必须显式给。"""
    day = timezone.localdate() - dt.timedelta(days=days_ago)
    stamp = timezone.make_aware(dt.datetime.combine(day, dt.time(10, 0)))
    return WealthBillList.objects.create(
        transaction_type=transaction_type, date=stamp, category='测试',
        period_tag=period_tag, amount=amount,
        year=day.year, month=day.month, day=day.day,
        created_at=stamp, updated_at=stamp,
    )


def _task(name, days_ago, hours):
    """一条时间记录（`managed=False` 外部表，历史数据按本地时间存 ⇒ 用 naive）。"""
    day = timezone.localdate() - dt.timedelta(days=days_ago)
    start = dt.datetime.combine(day, dt.time(9, 0))
    iso = day.isocalendar()
    return TemporalTask.objects.create(
        task_name=name, task_type=name, start_time=start,
        end_time=start + dt.timedelta(hours=hours), duration_hours=hours,
        year=day.year, mon=f'{day.month:02d}', day=day.day, week=iso[1],
    )


# ── ① 六类是**全部**记录（红线）──────────────────────────────
def test_six_buckets_cover_every_record():
    """六类之和 == `covered_hours`：兜底的那部分**单列但不排除**（睡眠除外）。

    回归（2026-11-02）：旧口径下没配规则的任务名被静默丢弃 ——
    「成长」偏低、「谋生」恒 0，覆盖率却显示 83% 看着很完整。
    """
    stage = _long_stage()
    TaskMeta.objects.create(task_name='写代码', activity_type='深度工作', default_attribution='成长')
    TaskMeta.objects.create(task_name='打零工', activity_type='浅层工作', default_attribution='谋生')
    _task('写代码', 1, 3.0)
    _task('打零工', 2, 2.0)
    _task('某个没登记的任务', 3, 1.5)      # 没有默认归因 ⇒ 走兜底

    ledger = stage_ledger(stage)
    time_block = ledger['time']

    assert time_block['covered_hours'] == 6.5
    assert round(sum(time_block['hours'].values()), 2) == 6.5      # 🔴 红线
    assert time_block['hours']['谋生'] == 2.0
    assert time_block['fallback_hours'] == 1.5


def test_sleep_excluded_and_reported():
    """睡眠不进六类、不进分子，但**必须报出来**（`excluded_sleep_hours`）。

    用户报的原话是「剔除睡眠时间」—— 但页面只说「已记录」，不说剔了多少，
    就等于把 12h 藏起来：「维持」凭空少一块，屏幕上没有任何线索。
    """
    stage = _long_stage()
    TaskMeta.objects.create(task_name='写代码', activity_type='深度工作', default_attribution='成长')
    _task('写代码', 1, 3.0)
    _task('休息睡眠', 2, 8.0)       # 常量名单，无需 TaskMeta
    _task('午睡', 3, 1.0)

    time_block = stage_ledger(stage)['time']
    assert time_block['covered_hours'] == 3.0
    assert time_block['excluded_sleep_hours'] == 9.0
    assert time_block['hours']['维持'] == 0.0
    assert round(time_block['covered_hours'] + time_block['excluded_sleep_hours'], 2) == 12.0
    # 成长占比的分母也不含睡眠 ⇒ 3/3 = 100%，而不是 3/12 = 25%
    assert time_block['toward_ratio'] == 1.0


def test_time_block_does_not_duplicate_days_elapsed():
    """区间天数只出在 `range` 一处 —— 两个键各给一个，改口径时必漏一个。"""
    ledger = stage_ledger(_long_stage(days=10))
    assert 'days_elapsed' not in ledger['time']
    assert ledger['range']['elapsed_days'] == 10


# ── ② 0 不是 ∞ ───────────────────────────────────────────────
def test_support_until_none_carries_reason():
    """没有任何「为自己」的账 ⇒ 不是「永不耗尽」，是「还没有速度可外推」。"""
    ledger = stage_ledger(_long_stage())
    pool = ledger['money']['pool']
    assert pool['avg_daily'] == 0
    assert pool['support_until'] is None
    assert pool['support_zero_reason'] == 'no_self_expense'


def test_support_until_computed_when_expense_exists():
    """有速度就照实外推，且原因码为 `None`（不是空串 / 不是 'ok'）。"""
    _bill(1, 600)
    ledger = stage_ledger(_long_stage())
    pool = ledger['money']['pool']
    assert pool['avg_daily'] > 0
    assert pool['support_until'] is not None
    assert pool['support_zero_reason'] is None


# ── ③ 笔数用 Count，不是 Sum('id') ──────────────────────────
def test_tier_counts_rows_not_id_sum():
    """2 条账单 ⇒ `count == 2`。

    🔴 旧实现 `Sum('id')`：两条 id=5、9 的账单会显示成 **14 笔**。
       这个错不会报错、也不会离谱到被一眼看出（id 连续、量级相近）。
    """
    _bill(1, 100, period_tag='为自己')
    _bill(2, 200, period_tag='为自己')
    ledger = stage_ledger(_long_stage())

    row = next(t for t in ledger['money']['tier'] if t['period_tag'] == '为自己')
    assert row['count'] == 2
    assert row['total'] == 300.0


# ── 钱：本金与允许日均 ───────────────────────────────────────
def test_pool_balance_and_daily_allowance():
    """允许日均 = 剩余余额 ÷ 剩余天数，**由后端给**（前端零算）。

    2026-11-05 起不再下发 ¥/h 的「单位赎回成本 / 理论下限」：一个除已过小时、
    一个除全期小时，并排看必然得出「28.56 高于 11.74 ⇒ 超标」这种不成立的读法。
    现在只留一把尺子 —— 每天多少钱。
    """
    _bill(1, 800)
    # 10 天已过 + 20 天未到 ⇒ 总 30 天、剩 20 天
    ledger = stage_ledger(_long_stage(days=10, principal=96000, end_days=20))
    money = ledger['money']

    assert money['pool']['principal'] == 96000.0
    assert money['pool']['balance'] == 96000.0 - 800.0
    assert ledger['range']['remaining_days'] == 20
    assert money['daily_allowance'] == round((96000 - 800) / 20, 2)
    assert money['daily_allowance_zero_reason'] is None
    # 旧口径的三个键已退役 —— 留着就是第二把尺子的入口
    assert 'unit_cost' not in money
    assert 'unit_cost_floor' not in money


def test_daily_use_rate_is_avg_over_allowance():
    """预算占用 = 日均 ÷ 允许日均。日均分母是**实际天数**（v3.64.39 起），
    阶段第 10 天就除 10，不再摊到 30。"""
    _bill(1, 800)
    ledger = stage_ledger(_long_stage(days=10, principal=96000, end_days=20))
    money = ledger['money']
    # 800 ÷ 实际 10 天 ⇒ 日均 80（旧口径摊 30 天会读成 26.67）
    assert money['pool']['avg_daily'] == round(800 / 10, 2)
    assert money['daily_use_rate'] == round(money['pool']['avg_daily'] / money['daily_allowance'], 4)


def test_avg_daily_carries_sample_days():
    """日均必须带样本天数：阶段只走了 10 天，`thin` 要说「样本不足 30 天」。

    🔴 分母已改成实际天数 ⇒ 数值不再被稀释，`thin` 的含义也随之变了：
       从「这个数偏低、要另算一个真实速度」变成「样本短，速度可能还没经历月末大额」。
       但样本天数**仍要摆出来**，否则读者不知道 80 这个数是 10 天跑出来的。
    """
    _bill(1, 800)
    ledger = stage_ledger(_long_stage(days=10, principal=96000, end_days=20))
    money = ledger['money']

    assert money['avg_daily_sample_days'] == 10
    assert money['avg_daily_sample_thin'] is True
    # 只有一个日均，没有第二把尺子
    assert money['pool']['avg_daily'] == round(800 / 10, 2)
    assert 'avg_daily_sample_net_per_day' not in money


def test_no_principal_means_no_allowance_with_reason():
    """没设本金 ⇒ 允许日均是 `None` + 原因码，**不是 0**。

    允许值为 0 意味着「一花钱就超额」—— 那是个结论，不是默认值。
    """
    ledger = stage_ledger(_long_stage(principal=None, end_days=20))
    money = ledger['money']
    assert money['pool']['principal'] == 0.0
    assert money['daily_allowance'] is None
    assert money['daily_allowance_zero_reason'] == 'no_principal'
    assert money['daily_use_rate'] is None


def test_stage_ended_means_no_days_left():
    """阶段已到最后一天 ⇒ 没有「剩余天数」可分，允许日均 `None` + `no_day_left`。"""
    ledger = stage_ledger(_long_stage(days=10, principal=96000))
    money = ledger['money']
    assert ledger['range']['remaining_days'] == 0
    assert money['daily_allowance'] is None
    assert money['daily_allowance_zero_reason'] == 'no_day_left'


def test_net_inflow_is_not_no_self_expense():
    """净流入（进来的比花的多）⇒ `net_inflow`，**不是**「还没有一条账」。

    旧实现 `avg_daily <= 0` 一律报 `no_self_expense`，页面写「这段路还没有一条
    「为自己」的账」—— 而同一屏的档位分布里明明列着十几笔（用户截图实证）。
    说反话比不报更坏：读者会去补一条已经记过的账。
    """
    _bill(1, 300, transaction_type='收入')

    money = stage_ledger(_long_stage(days=10, principal=1000, end_days=20))['money']
    assert money['pool']['avg_daily'] < 0
    assert money['pool']['support_until'] is None
    assert money['pool']['support_zero_reason'] == 'net_inflow'
    # 比值同样没有意义：-10 ÷ 65 会显示成 -15%，看着像「省了」
    assert money['daily_use_rate'] is None
    assert money['daily_use_rate_zero_reason'] == 'net_inflow'


def test_pool_inject_marked_bill_counts_once():
    """标了「中途注入」的收入：算进注入，并**从净消耗里排除**（否则双算）。

    🔴 不排除的话，同一笔 500 既加进 `injected`、又通过 `self_income` 减少净消耗，
       余额会变成 2000 —— 而页面上两个数各自看着都合理，没人会发现。
    这条用例同时兜住 conftest 的镜像 DDL：若建表语句少了 `bill_id`，这里第一条就报
    `Unknown column`（那是「看着像迁移没跑」的头号误导）。
    """
    from apps.selfrun.models import SelfRunPoolInject

    bill = _bill(1, 500, transaction_type='收入')
    SelfRunPoolInject.objects.create(bill_id=bill.id)

    money = stage_ledger(_long_stage(days=10, principal=1000))['money']
    assert money['pool']['injected'] == 500.0
    assert money['pool']['self_income'] == 0.0     # 已被排除，不再减净消耗
    assert money['pool']['balance'] == 1500.0      # 1000 + 500，不是 2000


def test_pool_inject_outside_window_is_ignored():
    """窗口外的注入不算 —— 与本金、消耗同一把尺子（都按区间夹）。

    注入改成「标记账单」后，日期天然跟着账单走；阶段只有 10 天，
    40 天前那笔就不属于这本账（旧实现按阶段总量取，会把它算进来）。
    """
    from apps.selfrun.models import SelfRunPoolInject

    bill = _bill(40, 500, transaction_type='收入')
    SelfRunPoolInject.objects.create(bill_id=bill.id)

    money = stage_ledger(_long_stage(days=10, principal=1000))['money']
    assert money['pool']['injected'] == 0.0
    assert money['pool']['balance'] == 1000.0


def test_pool_inject_rejects_expense_bill():
    """支出不能标注入：它既会被当注入加钱、又正常减少余额 ⇒ 余额凭空变大。"""
    from apps.selfrun import services as ss

    bill = _bill(1, 100)      # 默认是支出
    with pytest.raises(ss.SelfRunError):
        ss.set_pool_inject(bill.id, True)


# ── ⑥ 作品：件数与明细必须同源（v3.64.29）──────────────────────
def _work(name, *, when):
    """一件作品，`created_at` 精确到时刻（`auto_now_add` 挡不住 update）。"""
    from apps.works.models import Work

    work = Work.objects.create(name=name)
    Work.objects.filter(id=work.id).update(created_at=timezone.make_aware(when))
    return work


def test_ledger_works_count_and_items_are_same_source():
    """🔴 件数与明细出自**同一次**取数。

    从前账本自己写了一份 `_stage_work_count`，与 KPI 的 `readers.works_count`
    是同一件事的两份实现；加了明细之后一旦分叉，表现就是
    **「写着 2 件、点开 3 条」，而两个数各自看着都合理**。
    """
    stage = _long_stage(days=10)
    _work('第一件', when=dt.datetime.combine(
        timezone.localdate() - dt.timedelta(days=3), dt.time(14, 0)))
    _work('第二件', when=dt.datetime.combine(
        timezone.localdate() - dt.timedelta(days=1), dt.time(21, 40)))

    works = stage_ledger(stage)['works']
    assert works['count'] == 2
    assert len(works['items']) == works['count']
    assert works['truncated'] is False
    # 最近成形的排在前面（弹窗问的是「最近做了什么」，不是「最早」）
    assert [i['name'] for i in works['items']] == ['第二件', '第一件']


def test_ledger_works_include_last_day_of_range():
    """🔴 区间**最后一天**的作品必须算进来。

    `readers.works_count` 收的是半开上界 `[start, end)`，而账本的 `end` 是
    「区间最后一天」（inclusive）—— 忘了 +1 天，最后一天会整天漏掉；
    页面上只是少一件，不报错、也看不出少了。
    """
    stage = _long_stage(days=5)
    _work('最后一天深夜的那件', when=dt.datetime.combine(
        stage.end_date, dt.time(23, 50)))

    works = stage_ledger(stage)['works']
    assert works['count'] == 1
    assert works['items'][0]['name'] == '最后一天深夜的那件'


def test_ledger_works_item_time_is_local_not_utc():
    """🔴 下发的 `created_at` 必须是**本地时刻**。

    库里读出来是 UTC，直接 `isoformat()` 会发 `+00:00`，前端截前 16 位
    就成了「差 8 小时、但看着完全合理」的时间 —— 本项目最难发现的那类错。
    """
    stage = _long_stage(days=5)
    when = dt.datetime.combine(
        timezone.localdate() - dt.timedelta(days=1), dt.time(21, 40))
    _work('晚上九点四十', when=when)

    item = stage_ledger(stage)['works']['items'][0]
    assert item['created_at'].startswith(f'{when:%Y-%m-%d}T21:40')


def test_ledger_works_truncates_and_says_so():
    """超过上限 ⇒ `truncated` 必须为真，且 `limit` 随数据下发。

    只截断不说，用户会拿弹窗里那几条当全集 —— 又是一句「看着合理」的谎。
    """
    stage = _long_stage(days=10)
    day = timezone.localdate() - dt.timedelta(days=2)
    for i in range(51):
        _work(f'第{i}件', when=dt.datetime.combine(day, dt.time(0, 0)))

    works = stage_ledger(stage)['works']
    assert works['count'] == 51
    assert works['limit'] == 50
    assert len(works['items']) == 50
    assert works['truncated'] is True


# ── 子阶段 ──────────────────────────────────────────────────
def test_children_lists_all_sub_stages():
    long_stage = _long_stage(days=30)
    today = timezone.localdate()
    SelfRunStage.objects.create(
        name='第一个小阶段', parent=long_stage, status='closed',
        start_date=today - dt.timedelta(days=20), end_date=today - dt.timedelta(days=10),
    )
    SelfRunStage.objects.create(
        name='第二个小阶段', parent=long_stage, status='active',
        start_date=today - dt.timedelta(days=9), end_date=today,
    )

    children = stage_ledger(long_stage)['children']
    assert [c['name'] for c in children] == ['第一个小阶段', '第二个小阶段']
    # 区间与状态词由同一份实现给出（不是前端拼、也不是第二份三元表达式）
    assert children[0]['range_label'].endswith('（11 天）')
    assert children[1]['status_display'] == '进行中'
    # 还没归档过任何一期 ⇒ 三个数诚实表达「没判定过」
    assert children[1]['judged'] == 0
    assert children[1]['reach_rate'] is None


def test_long_stage_ledger_has_no_period_readings():
    """长阶段**只汇总、不判定** ⇒ 账本里不许出现它自己的 period 读数。"""
    long_stage = _long_stage()
    ledger = stage_ledger(long_stage)
    assert 'readings' not in ledger
    assert 'periods' not in ledger
    assert long_stage.periods.count() == 0
    for child in ledger['children']:
        assert 'readings' not in child


# ── 端点 ────────────────────────────────────────────────────
def test_ledger_endpoint_is_read_only(client):
    """`GET` 不写库：连 redis 都没配、本金也没有，也必须 200 并给出原因码。"""
    stage = _long_stage(principal=None)
    before = SelfRunStage.objects.count()

    resp = client.get(f'{URL}/stages/{stage.id}/ledger/')
    assert resp.status_code == 200
    body = resp.json()
    assert body['written'] == {}
    assert body['ledger']['money']['pool']['support_zero_reason'] == 'no_self_expense'
    assert SelfRunStage.objects.count() == before


def test_ledger_config_patch_updates_principal(client):
    stage = _long_stage(principal=None)
    resp = client.patch(
        f'{URL}/stages/{stage.id}/ledger-config/',
        {'pool_principal': 50000}, format='json',
    )
    assert resp.status_code == 200, resp.data
    stage.refresh_from_db()
    assert stage.ledger_config['pool_principal'] == 50000.0
    assert resp.json()['ledger']['money']['pool']['principal'] == 50000.0


def test_ledger_config_rejects_extra_keys(client):
    """🔴 多余键**报错**，不静默忽略 —— 否则「我改了终点」会变成一次无声的空操作。"""
    stage = _long_stage()
    resp = client.patch(
        f'{URL}/stages/{stage.id}/ledger-config/',
        {'pool_principal': 1, 'end_date': '2030-01-01'}, format='json',
    )
    assert resp.status_code == 400
    assert 'pool_principal' in resp.json()['detail']


@pytest.mark.parametrize('payload', [{}, {'pool_principal': 'abc'}, {'pool_principal': -1}])
def test_ledger_config_rejects_bad_values(client, payload):
    stage = _long_stage()
    resp = client.patch(
        f'{URL}/stages/{stage.id}/ledger-config/', payload, format='json',
    )
    assert resp.status_code == 400


# ── 取数器：runway 从「恒为 None」变成真算 ───────────────────
class _FakeMetric:
    source_config = {'kind': 'module_value', 'where': {'key': 'redemption.runway'}}


def test_runway_reader_returns_months():
    """可支撑月数 = 余额 ÷ 日均净支出 ÷ 30。

    回归（2026-11-02）：这里曾写死 `value=None`，理由是「月结表结余没填」——
    可赎回池的余额根本不依赖那张表（本金 + 注入 − 净支出 就能算）。
    一个「算不出来的白名单项」挂了大半年，而它一直算得出来。
    v3.64.20 起数据源换成**长阶段**（赎回期已不是一个模块）。
    """
    _long_stage(days=30, principal=100000)
    _bill(1, 900)      # 近 30 日净支出 900 ⇒ 日均 30

    today = timezone.localdate()
    start, end = today - dt.timedelta(days=7), today
    out = module_value(_FakeMetric(), start, end)

    assert out['value'] == round((100000 - 900) / 30 / 30, 2)
    assert out['count'] == 1
    # 溯源行：构成放进 facts，但不许靠「相加」凑出 value（那是除法，不是求和）
    facts = out['breakdown'][0]['extra']['facts']
    assert [f['label'] for f in facts] == ['现金池余额', '日均净支出', '日均样本天数']
    assert facts[2]['value'] == 30      # 满 30 天样本 ⇒ 与旧口径数值一致
    assert out['breakdown'][0]['value'] == out['value']


def test_runway_reader_none_when_no_expense():
    """没有速度可外推 ⇒ `None` + 原因码（不是 0：0 个月与算不出是相反的两件事）。"""
    _long_stage(days=30, principal=100000)

    today = timezone.localdate()
    out = module_value(_FakeMetric(), today - dt.timedelta(days=7), today)
    assert out['value'] is None
    assert out['issues'][0]['code'] == 'no_self_expense'


def test_runway_reader_without_long_stage():
    """连长阶段都没有 ⇒ 说清「还没有」，且**不许**顺手建一行。

    空态码从 `no_period` 改成 `no_long_stage`：赎回期单例没了，
    「没有配置」现在指的是「没有一个带本金的长阶段」。
    """
    out = module_value(_FakeMetric(), timezone.localdate(), timezone.localdate())
    assert out['value'] is None
    assert out['issues'][0]['code'] == 'no_long_stage'
    assert SelfRunStage.objects.count() == 0


# ── 跑道卡端点（v3.64.41）：仪表盘与 KPI 必须是同一把尺子 ─────
def test_runway_endpoint_matches_kpi():
    """`/runway/` 与 KPI `redemption.runway` 的数字**必须完全相等**。

    🔴 这是这条端点存在的全部意义：两张屏读同一个函数。任何一处另算一遍，
       都会出现「仪表盘 14.7、KPI 15.2」这种两个都看着合理的分叉 ——
       而分叉是静默的，没有任何报错会提示你。
    """
    _long_stage(days=30, principal=100000)
    _bill(1, 900)      # 近 30 日净支出 900 ⇒ 日均 30

    today = timezone.localdate()
    data = APIClient().get(f'{URL}/runway/').json()
    kpi = module_value(_FakeMetric(), today - dt.timedelta(days=7), today)

    assert data['months'] == kpi['value'] == round((100000 - 900) / 30 / 30, 2)
    assert data['sample_days'] == 30
    assert data['thin'] is False
    # 前端只查表、不猜键名 ⇒ 这批键缺一个就是「永远不显示」
    for key in ('months', 'support_until', 'covers_stage', 'sample_days', 'thin',
                'pool_balance', 'avg_daily', 'stage', 'issue', 'freshness_at'):
        assert key in data


def test_runway_endpoint_short_sample_says_shortfall():
    """阶段第 3 天：日均按 **3 天**算（不摊到 30 天），且「撑不到终点」要说出来。

    🔴 `covers_stage` 由后端判 —— 前端拿两个日期自己比是第二份口径，
       且 `USE_TZ` 下 `new Date()` 必然差 8 小时（错得合法、看不出来）。
    """
    _long_stage(days=3, principal=100000, end_days=1000)
    _bill(1, 900)      # 3 天 900 ⇒ 日均 300；余额 99100 ⇒ 约 330 天

    data = APIClient().get(f'{URL}/runway/').json()
    assert data['sample_days'] == 3
    assert data['thin'] is True
    assert data['avg_daily'] == 300.0
    assert data['covers_stage'] is False


def test_runway_covers_stage_none_without_end():
    """阶段没设终点 ⇒ `covers_stage=None`，**不是 `True`**。

    「没设终点」是没法回答，印成「撑得到」等于把「不知道」说成一个好消息。
    """
    stage = _long_stage(days=3, principal=100000)
    stage.end_date = None
    stage.save(update_fields=['end_date'])
    _bill(1, 900)

    data = APIClient().get(f'{URL}/runway/').json()
    assert data['months'] is not None
    assert data['covers_stage'] is None


def test_runway_endpoint_without_long_stage():
    """没有长阶段 ⇒ `no_long_stage` + `months=None`，且**不许**顺手建一行。"""
    data = APIClient().get(f'{URL}/runway/').json()
    assert data['issue']['code'] == 'no_long_stage'
    assert data['months'] is None
    assert data['stage'] is None
    assert SelfRunStage.objects.count() == 0
