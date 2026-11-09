"""自我运转 · T3 复盘 —— 11 条（设计稿 §12 之 15–23 + 归档闸门 2 条）"""
import datetime as dt

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.selfrun.models import SelfRunCheckin, SelfRunMetric, SelfRunPeriod, SelfRunStage
from apps.temporal.models import TaskMeta, TemporalTask

pytestmark = pytest.mark.django_db

URL = '/api/selfrun'


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def stage(client):
    today = timezone.localdate()
    resp = client.post(f'{URL}/stages/', {
        'name': '测试阶段',
        'start_date': str(today - dt.timedelta(days=today.weekday())),
        'metrics': [
            {'template_key': 'grow_hours'},
            {'template_key': 'xuanzhi', 'goal_value': 6, 'floor_value': None},
            {'template_key': 'output_count'},
        ],
    }, format='json')
    assert resp.status_code == 201, resp.data
    return SelfRunStage.objects.get()


def _metric(stage, key):
    return stage.metrics.get(template_key=key)


def _seed_temporal(name, l2, days_ago_list, hours=1.0, counts_growth=True):
    """造一批时间记录 + 对应的映射行。

    🔴 `counts_growth` 默认 True：v3.64.11 起「成长计时」只看 `temporal_task_meta.counts_growth`，
       **不再**按 `activity_type == '深度工作'` 自动判定。造数若不打这个标记，
       成长小时数会取到 0 —— 看起来像取数器坏了，其实是造数没给口径。
    """
    TaskMeta.objects.get_or_create(
        task_name=name,
        defaults={'activity_type': l2, 'default_attribution': '关系',
                  'counts_growth': counts_growth},
    )
    today = timezone.localdate()
    for d in days_ago_list:
        TemporalTask.objects.create(
            task_name=name, start_time=timezone.make_aware(
                dt.datetime.combine(today - dt.timedelta(days=d), dt.time(9, 0)),
            ),
            duration_hours=hours, year=2026, mon='10', day=1,
        )


def _last_week_days_ago(offset=1):
    """上周的某天（offset=1 表示上周一）。"""
    return timezone.localdate().weekday() + offset


def _week_key(days_ago):
    ref = timezone.localdate() - dt.timedelta(days=days_ago)
    iso = ref.isocalendar()
    return f'{iso[0]}-W{iso[1]:02d}'


def _reading(period, name):
    return next(r for r in period.readings if r['name'] == name)


def _close(client, key, **extra):
    return client.post(f'{URL}/periods/close/', {
        'period_type': 'weekly', 'period_key': key, **extra,
    }, format='json')


# ── 15. 归档后 readings 冻结（改源数据也不变）─────────────────
def test_readings_frozen_after_close(client, stage):
    days = _last_week_days_ago(1)
    _seed_temporal('代码编程', '深度工作', [days, days + 1], hours=2.0)
    key = _week_key(days)

    assert _close(client, key).status_code == 201
    period = SelfRunPeriod.objects.get(period_key=key)
    frozen = _reading(period, '成长小时数')['final_value']
    assert frozen == 4.0

    # 归档之后又往那一周补录了 99 小时
    _seed_temporal('代码编程', '深度工作', [days], hours=99.0)

    period.refresh_from_db()
    assert _reading(period, '成长小时数')['final_value'] == frozen   # 仍是 4.0，不重算

    # 而「当前周期」接口仍是实时的（这就是 T2 与 T3 是两个不同问题的体现）
    resp = client.get(f'{URL}/periods/current/?period_type=weekly')
    assert resp.json()['live'] is True


# ── 16. 归档后 PATCH readings ⇒ 405 ──────────────────────────
def test_frozen_fields_reject_patch_with_405(client, stage):
    key = _week_key(_last_week_days_ago(1))
    _close(client, key)
    period = SelfRunPeriod.objects.get(period_key=key)

    for field, value in (('readings', []), ('status', 'on_track'),
                         ('config_fingerprint', 'x'), ('period_key', '2020-W01')):
        resp = client.patch(f'{URL}/periods/{period.id}/', {field: value}, format='json')
        assert resp.status_code == 405, f'{field} 应被拒绝'
        assert field in resp.json()['detail']

    period.refresh_from_db()
    assert period.status == 'no_record' or period.status != 'on_track'   # 没被改


# ── 17. 归档后 PATCH review_text ⇒ 成功且留痕 ─────────────────
def test_review_text_is_writable_after_close_with_trace(client, stage):
    key = _week_key(_last_week_days_ago(1))
    _close(client, key)
    period = SelfRunPeriod.objects.get(period_key=key)
    assert period.closed_at is not None

    resp = client.patch(f'{URL}/periods/{period.id}/',
                        {'review_text': '这周开始有点节奏了'}, format='json')
    assert resp.status_code == 200, resp.data

    period.refresh_from_db()
    assert period.review_text == '这周开始有点节奏了'
    assert len(period.review_edits) == 1
    assert 'days_after_close' in period.review_edits[0]     # 标「补写于归档后 N 天」

    # 再改一次 ⇒ 再追加一条（「当时的想法」与「事后的解释」不混）
    client.patch(f'{URL}/periods/{period.id}/',
                 {'review_text': '…后来想起 10-16 那天还做了一次交付'}, format='json')
    period.refresh_from_db()
    assert len(period.review_edits) == 2


# ── 18. 重复归档 ⇒ 409 ──────────────────────────────────────
def test_double_close_is_conflict(client, stage):
    key = _week_key(_last_week_days_ago(1))
    assert _close(client, key).status_code == 201
    again = _close(client, key)
    assert again.status_code == 409
    assert '已经归档过' in again.json()['detail']
    assert SelfRunPeriod.objects.filter(period_key=key).count() == 1


# ── 19. skipped 条目不进分母 ────────────────────────────────
def test_skipped_metric_not_counted(client, stage):
    xuanzhi = _metric(stage, 'xuanzhi')
    key = _week_key(_last_week_days_ago(1))
    resp = _close(client, key, skipped_metric_ids=[xuanzhi.id])
    assert resp.status_code == 201

    period = SelfRunPeriod.objects.get(period_key=key)
    row = _reading(period, '宣纸')
    assert row['skipped'] is True
    assert period.skipped_metric_ids == [xuanzhi.id]

    # 分母 = 3 - 1（跳过）= 2；而「宣纸」是 0 张、若不被跳过必然 miss
    from apps.selfrun.services import compute_period_status
    assert compute_period_status(stage, period.readings) == period.status


# ── 20. unknown / unconfigured 不进分母 ──────────────────────
def test_unknown_metric_not_counted(client, stage):
    """把一条 KPI 的两条线都清空 ⇒ `unconfigured` ⇒ `verdict=unknown` ⇒ 不进分母。"""
    out = _metric(stage, 'output_count')
    resp = client.patch(f'{URL}/metrics/{out.id}/',
                        {'goal_value': None, 'floor_value': None}, format='json')
    assert resp.status_code == 200, resp.data

    key = _week_key(_last_week_days_ago(1))
    _close(client, key)
    period = SelfRunPeriod.objects.get(period_key=key)
    row = _reading(period, '留下件数')
    assert row['state'] == 'unconfigured'
    assert row['verdict'] == 'unknown'

    counted = [r for r in period.readings if r['verdict'] != 'unknown' and not r.get('skipped')]
    assert len(counted) == 2                       # 3 条里排除了 1 条 unknown


# ── 21. is_partial 的周期不进阶段达标率 ──────────────────────
def test_partial_period_excluded_from_stage_rate(client):
    today = timezone.localdate()
    if today.weekday() == 0:
        pytest.skip('今天正好是周一，构造不出残缺周')

    client.post(f'{URL}/stages/', {
        'name': '周中起步',
        'start_date': str(today),                    # 周二起
        'metrics': [{'template_key': 'grow_hours'}],
    }, format='json')
    stage = SelfRunStage.objects.get()

    # 归档当期（起于周一是残缺周）
    this_mon = today - dt.timedelta(days=today.weekday())
    key = _week_key(today.weekday())                 # 本周
    assert _close(client, key).status_code == 201
    period = SelfRunPeriod.objects.get(period_key=key)
    assert period.is_partial is True

    from apps.selfrun.services import compute_stage_summary
    s = compute_stage_summary(stage)
    assert s['total_weeks'] == 1
    assert s['counted_weeks'] == 0                   # 🔴 残缺周不进阶段达标率
    assert s['partial_weeks'] == 1
    assert s['weekly_breakdown']['on_track'] == 0    # 也没有被算进「合格」


# ── 22. 补归档 > 7 天 ⇒ 显式标注 ────────────────────────────
def test_late_backfill_is_flagged(client, stage):
    old_days = timezone.localdate().weekday() + 22          # 3 周多以前
    key = _week_key(old_days)
    resp = _close(client, key)
    assert resp.status_code == 201
    body = resp.json()

    period = SelfRunPeriod.objects.get(period_key=key)
    assert period.is_backfilled is True
    assert period.backfilled_at is not None
    assert body['backfill_days'] > 7
    assert '事后补算' in body['note']

    # 7 天内的正常归档**不**标注（否则标注就失去意义了）
    key2 = _week_key(timezone.localdate().weekday() + 1)
    body2 = _close(client, key2).json()
    assert body2['note'] == ''
    assert SelfRunPeriod.objects.get(period_key=key2).is_backfilled is False


# ── 23. 月度三问：answer=null（未答）≠ answer=false（答否）──
def test_monthly_three_questions_distinguish_null_from_false(client, stage):
    """🔴 v3.64.6 起：**没答完不许归档** —— 月度档位只来自三问。

    旧实现在 q3 未答时照样归档（2/3 = 67% 合格），「未答」被当成「答了否」之外
    的第三种状态，却又能推进结论；现在它连归档都推不过去，两件事彻底分开。
    """
    sheet = {
        'q1_income': {'answer': True},
        'q2_output': {'answer': True},
        'q3_runway': {'answer': None},           # 还没答
    }
    resp = client.post(f'{URL}/periods/close/', {
        'period_type': 'monthly', 'period_key': '2026-09', 'answer_sheet': sheet,
    }, format='json')
    assert resp.status_code == 400, resp.data
    assert '还有 1 个没答' in resp.data['detail']
    assert not SelfRunPeriod.objects.filter(period_key='2026-09').exists(), '被拦就不该落行'

    # 明确答「否」⇒ 2 是 1 否 = 67% ⇒ 合格（未答**既不当作否、也不当作是**，但不能不答）
    sheet2 = dict(sheet, q3_runway={'answer': False})
    ok = client.post(f'{URL}/periods/close/', {
        'period_type': 'monthly', 'period_key': '2026-09', 'answer_sheet': sheet2,
    }, format='json')
    assert ok.status_code == 201, ok.data
    period = SelfRunPeriod.objects.get(period_key='2026-09')
    # ⚠️ v3.62.45 档位由四档统一：≥80 我超棒 / ≥60 合格 / ≥40 及格 / <40 活着
    assert period.status == 'on_track'

    # 归档后补答成 3 个「是」⇒ 记录改了，**档位不动**（要改档得重开这一期）
    sheet3 = {k: {'answer': True} for k in ('q1_income', 'q2_output', 'q3_runway')}
    client.patch(f'{URL}/periods/{period.id}/', {'answer_sheet': sheet3}, format='json')
    period.refresh_from_db()
    assert period.answer_sheet['q3_runway']['answer'] is True
    assert period.status == 'on_track', '归档后补答不许改档'


# ── 24. 往**已归档**的周期补记 ⇒ 409（不静默接受）────────────
def test_checkin_into_closed_period_is_rejected(client, stage):
    """🔴 归档 = 定格。补记若被静默接受，明细账里有一笔、结论里没有，两边悄悄分家。

    边界也要钉住：**记到当前（未归档）周期是允许的** —— 闸门只拦已归档的那一期。
    """
    xuanzhi = _metric(stage, 'xuanzhi')
    days_ago = _last_week_days_ago(1)
    day = timezone.localdate() - dt.timedelta(days=days_ago)
    key = _week_key(days_ago)

    # 归档前补记 ⇒ 正常落库，并会进这次的定格值
    ok = client.post(f'{URL}/checkins/', {
        'metric': xuanzhi.id, 'value': 2, 'checkin_date': str(day),
    }, format='json')
    assert ok.status_code == 201, ok.data
    assert _close(client, key).status_code == 201
    period = SelfRunPeriod.objects.get(period_key=key)
    assert _reading(period, '宣纸')['final_value'] == 2.0

    before = SelfRunCheckin.objects.count()
    bad = client.post(f'{URL}/checkins/', {
        'metric': xuanzhi.id, 'value': 3, 'checkin_date': str(day),
    }, format='json')
    assert bad.status_code == 409
    assert '归档' in bad.json()['detail']
    assert SelfRunCheckin.objects.count() == before          # 没落库
    period.refresh_from_db()
    assert _reading(period, '宣纸')['final_value'] == 2.0     # 定格值没被改

    # 同样的东西记到**今天**（未归档）⇒ 允许
    today_ok = client.post(f'{URL}/checkins/', {
        'metric': xuanzhi.id, 'value': 1, 'checkin_date': str(timezone.localdate()),
    }, format='json')
    assert today_ok.status_code == 201, today_ok.data


# ── 25. 已归档周期里的那笔也**不能冲销**（冲销同样是新流水）──
def test_reverse_into_closed_period_is_rejected(client, stage):
    xuanzhi = _metric(stage, 'xuanzhi')
    days_ago = _last_week_days_ago(1)
    day = timezone.localdate() - dt.timedelta(days=days_ago)
    key = _week_key(days_ago)

    resp = client.post(f'{URL}/checkins/', {
        'metric': xuanzhi.id, 'value': 2, 'checkin_date': str(day),
    }, format='json')
    checkin_id = resp.json()['checkin']['id']
    assert _close(client, key).status_code == 201

    before = SelfRunCheckin.objects.count()
    bad = client.delete(f'{URL}/checkins/{checkin_id}/')
    assert bad.status_code == 409
    assert '归档' in bad.json()['detail']
    assert SelfRunCheckin.objects.count() == before
    assert SelfRunCheckin.objects.get(pk=checkin_id).value == 2      # 原记录还在

    # 出口在文案里：要么「重开这一期」，要么记到当前周期
    reopen = client.post(f'{URL}/periods/{SelfRunPeriod.objects.get(period_key=key).id}/reopen/',
                         {'reason': '那天记错了'}, format='json')
    assert reopen.status_code == 200, reopen.data
    assert client.delete(f'{URL}/checkins/{checkin_id}/').status_code == 200
