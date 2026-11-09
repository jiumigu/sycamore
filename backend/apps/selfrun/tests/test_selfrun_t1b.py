"""自我运转 · T1b 按期修订 + T1 模板库（可自定义）—— 20 条

🔴 这一组钉住两件**用户报过**的事：
   ① 「制定配置」要能**自定义 KPI 模板**（不再只是代码里写死的 9 条）；
   ② 「每周/每月都可以修订**下一周、下一月**的 KPI」——
      改下一期**不能**顺带把正在跑的这一期也改掉。
"""
import datetime as dt

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.selfrun.constants import (
    MODULE_VALUE_WHITELIST, READER_KEYS, READER_WHERE_KEYS,
)
from apps.selfrun.models import (
    SelfRunMetric, SelfRunMetricPlan, SelfRunStage, SelfRunTemplate,
)
from apps.selfrun.readers import period_range
from apps.selfrun.services import resolve_targets

pytestmark = pytest.mark.django_db

URL = '/api/selfrun'


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def stage(client):
    """一个含 3 条 KPI 的阶段（周 2 + 月 1），起点对齐本周一（避开残缺周）。"""
    today = timezone.localdate()
    resp = client.post(f'{URL}/stages/', {
        'name': '按期设定测试',
        'start_date': str(today - dt.timedelta(days=today.weekday())),
        'metrics': [
            {'template_key': 'grow_hours'},     # 周 · 12 / 5
            {'template_key': 'xuanzhi'},        # 周 · 6 / —
            {'template_key': 'painting'},       # 月 · 2 / —
        ],
    }, format='json')
    assert resp.status_code == 201, resp.data
    return SelfRunStage.objects.get()


def _m(stage, key):
    return stage.metrics.get(template_key=key)


def _week(offset):
    """第 `offset` 周的 period_key（0 = 本期，1 = 下一周，-1 = 上一周）。"""
    ref = timezone.localdate() + dt.timedelta(days=7 * offset)
    return period_range('weekly', ref)[2]


def _set(client, metric, period_key, scope, goal, floor, **extra):
    return client.post(f'{URL}/metrics/{metric.id}/plans/', {
        'period_key': period_key, 'scope': scope,
        'goal_value': goal, 'floor_value': floor, **extra,
    }, format='json')


# ── 1. `single` 只影响那一期（🔴 本期不许被顺带改掉）──────────
def test_single_plan_affects_only_that_period(client, stage):
    grow = _m(stage, 'grow_hours')
    assert float(grow.goal_value) == 12.0
    k0, k1, k2 = _week(0), _week(1), _week(2)

    resp = _set(client, grow, k1, 'single', 8, 4, note='下周有出行')
    assert resp.status_code == 201, resp.data
    assert resp.json()['written'] == {
        'selfrun_metric_plan': 1, 'selfrun_metric_log': 1,
    }

    # 下一期用新值
    g, f, src, plan = resolve_targets(grow, k1)
    assert (float(g), float(f), src) == (8.0, 4.0, 'single')
    assert plan is not None and plan.note == '下周有出行'

    # 🔴 本期**不受影响** —— 这正是「修订下一期」的全部意义
    g0, f0, src0, _ = resolve_targets(grow, k0)
    assert (float(g0), float(f0), src0) == (12.0, 5.0, 'metric')

    # 再往后一期也回落默认（`single` 不粘）
    g2, _, src2, _ = resolve_targets(grow, k2)
    assert (float(g2), src2) == (12.0, 'metric')

    # 阶段默认值**一个字符都没动**（改的是「这一期用什么数」，不是「这条 KPI 是多少」）
    grow.refresh_from_db()
    assert float(grow.goal_value) == 12.0


# ── 2. `from` 从该期起一直生效，直到有更晚的 `from` ───────────
def test_from_plan_persists_until_a_later_one(client, stage):
    grow = _m(stage, 'grow_hours')
    k1, k2, k3 = _week(1), _week(2), _week(3)

    assert _set(client, grow, k2, 'from', 7, 3).status_code == 201

    # 该期之前不受影响
    assert resolve_targets(grow, k1)[2] == 'metric'
    # 该期起（**含该期**）一路生效
    for k in (k2, k3):
        g, f, src, _ = resolve_targets(grow, k)
        assert (float(g), float(f), src) == (7.0, 3.0, 'from')

    # 再来一条更晚的 `from` ⇒ 后者胜，且**不改写**之前那几期
    assert _set(client, grow, k3, 'from', 9, 3).status_code == 201
    assert float(resolve_targets(grow, k3)[0]) == 9.0
    assert float(resolve_targets(grow, k2)[0]) == 7.0


# ── 3. 同一期 `single` 压过 `from`（特例优先于长期）──────────
def test_single_beats_from_on_same_period(client, stage):
    grow = _m(stage, 'grow_hours')
    k2 = _week(2)
    assert _set(client, grow, k2, 'from', 7, 3).status_code == 201
    assert _set(client, grow, k2, 'single', 2, 1).status_code == 201

    g, f, src, _ = resolve_targets(grow, k2)
    assert (float(g), float(f), src) == (2.0, 1.0, 'single')
    # 下一期仍走 `from`
    assert resolve_targets(grow, _week(3))[2] == 'from'
    assert SelfRunMetricPlan.objects.filter(metric=grow).count() == 2   # 两条并存


# ── 4. 已归档的期不许再设目标 ⇒ 409 ──────────────────────────
def test_plan_into_closed_period_is_rejected(client, stage):
    grow = _m(stage, 'grow_hours')
    prev = _week(-1)
    closed = client.post(f'{URL}/periods/close/', {
        'period_type': 'weekly', 'period_key': prev,
    }, format='json')
    assert closed.status_code == 201, closed.data

    resp = _set(client, grow, prev, 'single', 10, 5)
    assert resp.status_code == 409
    assert '归档' in resp.json()['detail']
    assert SelfRunMetricPlan.objects.count() == 0        # 没有半截写入


# ── 5. 取消设定 ⇒ 回落到上一层口径 ───────────────────────────
def test_delete_plan_falls_back(client, stage):
    grow = _m(stage, 'grow_hours')
    k2 = _week(2)
    _set(client, grow, k2, 'from', 7, 3)
    r = _set(client, grow, k2, 'single', 2, 1)
    plan_id = r.json()['plan']['id']

    d = client.delete(f'{URL}/metrics/{grow.id}/plans/{plan_id}/')
    assert d.status_code == 200
    assert d.json()['written'] == {
        'selfrun_metric_plan': 1, 'selfrun_metric_log': 1,
    }
    assert not SelfRunMetricPlan.objects.filter(pk=plan_id).exists()

    # `single` 没了 ⇒ 落回 `from`
    g, _, src, _ = resolve_targets(grow, k2)
    assert (float(g), src) == (7.0, 'from')


# ── 6. 读数里要说清「这个目标从哪来」────────────────────────
def test_reading_reports_target_source(client, stage):
    grow = _m(stage, 'grow_hours')
    assert _set(client, grow, _week(0), 'single', 3, 1).status_code == 201

    body = client.get(f'{URL}/periods/current/?period_type=weekly').json()
    rows = {r['name']: r for r in body['period']['readings']}

    hit = rows['成长小时数']
    assert hit['target_source'] == 'single'
    assert hit['target_source_label'] == '本期设定'
    assert hit['goal_value'] == 3.0 and hit['floor_value'] == 1.0
    assert hit['plan_id'] is not None

    # 没设过的条目仍报「阶段默认」—— 三者必须能分辨，
    # 否则「我这周的目标怎么变了」永远说不清（而界面两处都「看着正常」）
    other = rows['宣纸']
    assert other['target_source'] == 'metric'
    assert other['plan_id'] is None


# ── 7. 归档时按**当期生效值**冻结，且指纹跟着变 ───────────────
def test_fingerprint_follows_effective_target(client, stage):
    """🔴 按期改过目标的期，指纹必须与用默认值那期**不同** ——

    否则 T4 的「尺子断点」会把两段不可直接比的时期并成一段，而且**不报错**。
    """
    grow = _m(stage, 'grow_hours')
    k0, k1 = _week(0), _week(1)

    r0 = client.post(f'{URL}/periods/close/', {
        'period_type': 'weekly', 'period_key': k0,
    }, format='json')
    assert r0.status_code == 201, r0.data
    fp0 = r0.json()['period']['config_fingerprint']

    assert _set(client, grow, k1, 'single', 3, 1).status_code == 201
    r1 = client.post(f'{URL}/periods/close/', {
        'period_type': 'weekly', 'period_key': k1,
    }, format='json')
    assert r1.status_code == 201, r1.data
    fp1 = r1.json()['period']['config_fingerprint']

    assert fp1 != fp0                     # 换了尺子
    # 冻结读数里存的是**当时生效的**目标（以后重算也得出同一结果）
    frozen = {x['metric_id']: x for x in r1.json()['period']['readings']}
    assert frozen[grow.id]['goal_value'] == 3.0
    assert frozen[grow.id]['target_source'] == 'single'
    # 上一期的快照里仍是 12（归档后永不改变）
    old = {x['metric_id']: x for x in r0.json()['period']['readings']}
    assert old[grow.id]['goal_value'] == 12.0


# ── 8. 目标与底线仍要过方向校验 ──────────────────────────────
def test_plan_rejects_goal_below_floor(client, stage):
    grow = _m(stage, 'grow_hours')
    resp = _set(client, grow, _week(1), 'single', 2, 9)
    assert resp.status_code == 400
    assert '低于底线' in resp.json()['detail']
    assert SelfRunMetricPlan.objects.count() == 0


# ── 9. 省略 ≠ null：两条数必须显式传 ─────────────────────────
def test_plan_requires_explicit_lines(client, stage):
    grow = _m(stage, 'grow_hours')
    resp = client.post(f'{URL}/metrics/{grow.id}/plans/', {
        'period_key': _week(1), 'scope': 'single',
    }, format='json')
    assert resp.status_code == 400          # 「我没动这条底线」不许被读成「把底线删了」


# ── 10. 周期类型必须匹配（周 key 不给月度 KPI）───────────────
def test_period_key_type_must_match_metric(client, stage):
    painting = _m(stage, 'painting')        # monthly
    resp = _set(client, painting, _week(1), 'single', 1, None)
    assert resp.status_code == 400
    assert SelfRunMetricPlan.objects.count() == 0


# ── 11. 模板库可自定义：建 → 改 → 删 ─────────────────────────
def test_template_crud(client):
    listed = client.get(f'{URL}/templates/').json()
    assert len(listed['templates']) == 10           # autouse fixture 种的内置模板条数
    assert {'agg', 'source_kind', 'plan_scope'} <= set(listed['enum'])
    # 🔴 作品类型的候选**必须随接口下发**：前端下拉零副本，漏了这里就等于
    #    「按类型取数」那条在界面上没法选类型（看着像功能没做）。
    kinds = {o['value'] for o in listed['enum']['work_kind_options']}
    assert {'drawing', 'embroidery'} <= kinds

    created = client.post(f'{URL}/templates/', {
        'name': '晨跑', 'period_type': 'weekly', 'unit': '次',
        'direction': 'at_least', 'goal_value': 5, 'floor_value': 2,
        'goal_why': '太阳出来之前出门', 'agg': 'manual_sum', 'source_kind': 'manual',
        'source_config': {'kind': 'manual_sum'},
    }, format='json')
    assert created.status_code == 201, created.data
    assert created.json()['written'] == {'selfrun_template': 1}
    tpl = SelfRunTemplate.objects.get(name='晨跑')
    # 🔴 key 由**后端**生成 —— 前端自己编，撞了就是「来源指向别人的模板」
    assert tpl.key.startswith('custom_')

    patched = client.patch(f'{URL}/templates/{tpl.id}/', {'goal_value': 6}, format='json')
    assert patched.status_code == 200
    assert patched.json()['changed'] == ['goal_value']
    tpl.refresh_from_db()
    assert float(tpl.goal_value) == 6.0

    removed = client.delete(f'{URL}/templates/{tpl.id}/')
    assert removed.status_code == 200
    assert not SelfRunTemplate.objects.filter(pk=tpl.id).exists()


def test_template_rejects_goal_below_floor(client):
    resp = client.post(f'{URL}/templates/', {
        'name': '错的', 'period_type': 'weekly', 'direction': 'at_least',
        'goal_value': 1, 'floor_value': 5, 'agg': 'manual_sum',
        'source_kind': 'manual', 'source_config': {'kind': 'manual_sum'},
    }, format='json')
    assert resp.status_code == 400
    assert not SelfRunTemplate.objects.filter(name='错的').exists()


# ── 12. 自定义模板能被用来建阶段 ─────────────────────────────
def test_custom_template_can_build_stage(client):
    client.post(f'{URL}/templates/', {
        'name': '晨跑', 'period_type': 'weekly', 'unit': '次',
        'direction': 'at_least', 'goal_value': 5, 'floor_value': 2,
        'agg': 'manual_sum', 'source_kind': 'manual',
        'source_config': {'kind': 'manual_sum'},
    }, format='json')
    tpl = SelfRunTemplate.objects.get(name='晨跑')

    resp = client.post(f'{URL}/stages/', {
        'name': '用自定义模板开阶段',
        'metrics': [{'template_key': tpl.key}],
    }, format='json')
    assert resp.status_code == 201, resp.data
    m = SelfRunMetric.objects.get()
    assert m.name == '晨跑' and float(m.goal_value) == 5.0 and m.source_kind == 'manual'


# ── 13. 删模板**不影响已建阶段** ─────────────────────────────
def test_deleting_template_leaves_stage_intact(client, stage):
    grow = _m(stage, 'grow_hours')
    tpl = SelfRunTemplate.objects.get(key='grow_hours')

    resp = client.delete(f'{URL}/templates/{tpl.id}/')
    assert resp.status_code == 200
    assert resp.json()['used_by_metrics'] == 1      # 说清影响面

    grow.refresh_from_db()
    assert float(grow.goal_value) == 12.0           # 值不受影响
    assert float(grow.floor_value) == 5.0
    assert grow.template_key == 'grow_hours'        # 标记仍在（只是来源不再指向模板）
    assert SelfRunMetric.objects.filter(pk=grow.id).exists()
    # 阶段还能照常跑
    assert client.get(f'{URL}/periods/current/?period_type=weekly').status_code == 200


# ── 14. 期选项与「某一期的目标」两个接口 ─────────────────────
def test_period_options_and_targets(client, stage):
    body = client.get(f'{URL}/period-options/?period_type=weekly&count=4').json()
    opts = body['options']
    assert len(opts) == 5                            # 上一期 + 本期 + 往后 4 期
    assert opts[0]['offset'] == -1 and opts[1]['offset'] == 0
    assert opts[1]['label'] == '本期'
    keys = [o['key'] for o in opts]
    assert keys == sorted(keys)                       # 字符串序即时间序

    nxt = opts[2]['key']
    t = client.get(f'{URL}/targets/?period_type=weekly&period_key={nxt}').json()
    assert t['written'] == {}
    assert t['targets']['period_key'] == nxt
    assert t['targets']['is_current'] is False
    # 只列**本期类型**的 KPI（月度那条不该混进来）
    assert len(t['targets']['rows']) == 2
    assert {r['target_source'] for r in t['targets']['rows']} == {'metric'}

    # 设一条再看：来源要跟着变，且 `base_*` 仍是阶段默认
    grow = _m(stage, 'grow_hours')
    _set(client, grow, nxt, 'single', 20, 9)
    t2 = client.get(f'{URL}/targets/?period_type=weekly&period_key={nxt}').json()
    row = next(r for r in t2['targets']['rows'] if r['metric_id'] == grow.id)
    assert row['target_source'] == 'single'
    assert row['goal_value'] == 20.0 and row['base_goal'] == 12.0
    assert row['plan_count'] == 1


# ── 15. 取数器必须是注册表里的（早报一格，别等取数那刻 500）───
def test_template_rejects_unknown_reader(client):
    """🔴 未知 `kind` 要到**取数那一刻**才抛（`run_reader` 直接 `ValueError`）。

    不在建模板时就拦的话，表现是「模板建好了、阶段建好了、某一页 500」——
    错误离「你刚点的那个按钮」太远了。
    """
    resp = client.post(f'{URL}/templates/', {
        'name': '瞎写的', 'period_type': 'weekly', 'source_kind': 'auto',
        'source_config': {'kind': 'sql_anything'},
    }, format='json')
    assert resp.status_code == 400
    assert '取数器' in resp.json()['detail']
    assert not SelfRunTemplate.objects.filter(name='瞎写的').exists()


def test_template_requires_module_value_whitelist_key(client):
    """`module_value` 的键必须**完全命中白名单**（写错会直接报错，所以早拦一格）"""
    bad = client.post(f'{URL}/templates/', {
        'name': '资产盘点2', 'period_type': 'monthly', 'source_kind': 'auto',
        'source_config': {'kind': 'module_value', 'where': {'key': 'wealth.typo'}},
    }, format='json')
    assert bad.status_code == 400
    assert '白名单' in bad.json()['detail']

    good = client.post(f'{URL}/templates/', {
        'name': '资产盘点2', 'period_type': 'monthly', 'source_kind': 'auto',
        'source_config': {'kind': 'module_value', 'where': {'key': 'wealth.snapshot_fresh'}},
    }, format='json')
    assert good.status_code == 201, good.data


def test_template_manual_kind_is_normalized(client):
    """手工项也必须有一个注册表内的 `kind`（不给就归一化成 `manual_sum`）——
    取值仍旧走 `run_reader`，`kind` 空着照样会炸。"""
    resp = client.post(f'{URL}/templates/', {
        'name': '不写 kind 的手工项', 'period_type': 'weekly', 'source_kind': 'manual',
        'source_config': {},
    }, format='json')
    assert resp.status_code == 201, resp.data
    assert SelfRunTemplate.objects.get(name='不写 kind 的手工项').source_config['kind'] == 'manual_sum'


# ── 16. 改模板不该动它**没暴露在界面上**的条件 ────────────────
def test_patch_name_keeps_hidden_where(client):
    """`bill_income` 带着 `transaction_type` / `category` 两个固定条件。

    🔴 只改个名字就把它们抹掉的话，表现是「改了个名字，收入验证的数就变了」——
    而且不报错。这条钉住「没传 `source_config` ⇒ 一个字都不动」。
    """
    tpl = SelfRunTemplate.objects.get(key='income_verify')
    before = dict(tpl.source_config.get('where') or {})
    assert before == {'transaction_type': '收入', 'category': '其他收入'}

    resp = client.patch(f'{URL}/templates/{tpl.id}/', {'name': '收入验证（改个名）'}, format='json')
    assert resp.status_code == 200
    assert resp.json()['changed'] == ['name']
    tpl.refresh_from_db()
    assert dict(tpl.source_config.get('where') or {}) == before


# ── 17. 模板接口把枚举一起下发（前端不抄第三份取数器清单）────
def test_template_enum_carries_readers_and_l2(client):
    enum = client.get(f'{URL}/templates/').json()['enum']

    # 取数器清单与常量真源**同集合**（前端那份是从这里来的，不是手抄的）
    assert {r['value'] for r in enum['readers']} == set(READER_KEYS)
    # 每个取数器都说清「还要补哪个字段」，与界面元信息一致
    assert {r['value']: r['where_key'] for r in enum['readers']} == READER_WHERE_KEYS
    # 模块值白名单随接口下发（写错会报错，所以给选不给填）
    assert enum['module_value_keys'] == list(MODULE_VALUE_WHITELIST)
    # `l2` 候选来自**库**（`temporal_task_meta`），拿不到时至少是个列表、不是 None
    assert isinstance(enum['l2_options'], list)
    for k in ('agg', 'source_kind', 'direction', 'period_type', 'plan_scope'):
        assert enum[k], f'枚举 {k} 不能为空'
