"""生存资源盘点 · 库存流水（v3.60.18 · P0）

覆盖：
  ① ⭐ **核心判据一：改库存只有一个写口** —— 建档 / 编辑 / 盘点三处的数量变化
     都必须留下流水，任何一处漏记就是「账变了但没记录」
  ② ⭐ **核心判据二：不做物理删除，只做「撤销」** —— 补反向流水、账正回来、历史全留
  ③ ⭐ **核心判据三：`delta = 0` 拒绝、改完 `< 0` 拒绝且**不夹到 0**
  ④ 发生时刻可以是过去、**不许是未来**
  ⑤ 原因留空时按类别的**消耗模式**自动预选（配餐 → 吃掉，其余 → 用掉）
  ⑥ 名称等三列是**当时的快照**：物品改名 / 删除都不回改历史
  ⑦ 列表**返回裸数组**（不是 `{count, results}`），顺序 = 新的在前
  ⑧ 🔴 `summary` 是静态段，**不能被 `<pk>` 抢**（被抢的症状是 404，像路由没注册）
  ⑨ 汇总**跨单位不相加**：桶内同单位才求和，绝不给「总消耗 X 件」这种合计数
  ⑩ 🔴 月界是 **aware datetime + 半开区间** —— 月初 00:00 整算本月、
     下月初 00:00 整不算（拿 `date` 去过滤 datetime 会报 naive 警告且语义隐式）

⚠️ 与 `test_survival_stocktake.py` / `test_survival_snapshot.py` 的分工：
   那两份测「数过了」与「系统算的结论」；这份测「**库存怎么变的**」。
   三张表各记一件事，刻意不合并（合并后分不清「被吃掉的」与「被脚本改的」）。

新表由 conftest 的 session 级 `django_db_setup` 补齐 ——
`--no-migrations --reuse-db` 下新表不会自动出现。
"""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.wealth.models import (
    SurvivalCategory,
    SurvivalFlow,
    SurvivalItem,
    SurvivalUnit,
)
from apps.wealth.services import survival_flow as flw
from apps.wealth.services import survival_service as ssvc
from apps.wealth.services import survival_stocktake as stk

BASE = '/api/wealth/survival/flows/'


# ──────────────────────────────────────────────────────────────
# 造数
# ──────────────────────────────────────────────────────────────

def _setup(
    name='午餐肉罐头', quantity=10, category_name='吃',
    consume_mode='meal', unit_name='罐', **item_kwargs,
):
    """一件最简单的物品 → (category, unit, item)

    ⚠️ 类别与单位用 `get_or_create` **复用**：同一用例里造第二件物品时，
       再建同名类别会撞 `UniqueConstraint(user_id, name)`，
       报出来是 IntegrityError —— 看着像实现错，其实是造数写得太粗。
    """
    category, _ = SurvivalCategory.objects.get_or_create(
        user_id=1, name=category_name,
        defaults={'consume_mode': consume_mode, 'aggregate_mode': 'sum'},
    )
    unit, _ = SurvivalUnit.objects.get_or_create(
        user_id=1, category=category, name=unit_name,
        defaults={'base_unit': unit_name, 'to_base_rate': 1},
    )
    item = SurvivalItem.objects.create(
        user_id=1, category=category, name=name, quantity=quantity,
        unit=unit, status='stocked', **item_kwargs,
    )
    return category, unit, item


def _client():
    return APIClient()


# ══════════════════════════════════════════════════════════════
# ① 唯一写口：正负数量都写对，且库存同步
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestRecordFlow:

    def test_negative_delta_consumes_and_syncs_quantity(self):
        """消耗：`delta = -2` ⇒ 库存 10 → 8，流水记 -2"""
        _, _, item = _setup(quantity=10)
        row = flw.record_flow(item.id, -2, reason='eat')

        item.refresh_from_db()
        assert float(item.quantity) == 8.0
        assert row['delta'] == -2.0
        assert row['channel'] == 'manual'
        assert SurvivalFlow.objects.count() == 1

    def test_positive_delta_restocks(self):
        """入库：`delta = +3` ⇒ 库存 8 → 11（正负在同一列，靠符号区分）"""
        _, _, item = _setup(quantity=8)
        flw.record_flow(item.id, 3, reason='buy')

        item.refresh_from_db()
        assert float(item.quantity) == 11.0

    def test_zero_delta_rejected(self):
        """`delta = 0` → 报错：写一条 0 的流水只是噪音"""
        _, _, item = _setup()
        with pytest.raises(ValueError):
            flw.record_flow(item.id, 0)
        assert SurvivalFlow.objects.count() == 0
        item.refresh_from_db()
        assert float(item.quantity) == 10.0

    def test_negative_result_rejected_and_not_clamped(self):
        """⭐ 改完会变负数 ⇒ 拒绝，**且库存一点没动**

        静默夹到 0 会把「我记错了」变成「没货了」—— 两种情况的处置相反：
        一个要改记录，一个要补货。界面上都显示 0，就再也分不出来了。
        """
        _, _, item = _setup(quantity=3)
        with pytest.raises(ValueError) as exc:
            flw.record_flow(item.id, -5)

        assert '负数' in str(exc.value)
        item.refresh_from_db()
        assert float(item.quantity) == 3.0          # ← 关键：没被夹到 0
        assert SurvivalFlow.objects.count() == 0    # ← 也没留下半条流水

    def test_past_time_allowed_future_rejected(self):
        """补记过去可以；**未来不行**（还没发生的事记不下来）"""
        _, _, item = _setup()

        past = timezone.now() - timedelta(days=2)
        row = flw.record_flow(item.id, -1, occurred_at=past, reason='eat')
        assert row['occurred_at'].startswith(str(timezone.localtime(past).date()))

        with pytest.raises(ValueError) as exc:
            flw.record_flow(item.id, -1, occurred_at=timezone.now() + timedelta(days=1))
        assert '未来' in str(exc.value)

    def test_reason_autofilled_by_consume_mode(self):
        """原因留空 ⇒ 按类别的**消耗模式**预选（判据对着 mode，不对着类别名）"""
        _, _, food = _setup(name='罐头', category_name='吃', consume_mode='meal')
        _, _, tool = _setup(name='洗衣液', category_name='用', consume_mode='on_demand')

        assert flw.record_flow(food.id, -1)['reason'] == 'eat'
        assert flw.record_flow(tool.id, -1)['reason'] == 'use'

    def test_gain_side_reason_not_guessed(self):
        """入库一侧**不猜原因**：买来的和人家送的都长一个样，猜错等于替用户编理由"""
        _, _, item = _setup()
        assert flw.record_flow(item.id, 2)['reason'] == ''

    def test_unknown_channel_and_reason_rejected(self):
        """渠道 / 原因只收枚举内的值 —— 拼错一个词就是一条查不出来的流水"""
        _, _, item = _setup()
        with pytest.raises(ValueError):
            flw.record_flow(item.id, -1, channel='手动')
        with pytest.raises(ValueError):
            flw.record_flow(item.id, -1, reason='吃掉了')

    def test_name_snapshot_survives_rename_and_delete(self):
        """⭐ 三列是**当时的快照**：改名不回改历史，物品删了历史仍在"""
        _, _, item = _setup(name='午餐肉罐头')
        row = flw.record_flow(item.id, -1, reason='eat')

        item.name = '改名后'
        item.save(update_fields=['name'])

        flow = SurvivalFlow.objects.get(id=row['id'])
        assert flow.item_name == '午餐肉罐头'      # ← 历史没被改写

        item.delete()
        flow.refresh_from_db()
        assert flow.item is None                    # SET_NULL
        assert flow.item_name == '午餐肉罐头'       # 名字还在


# ══════════════════════════════════════════════════════════════
# ② 三处「系统代记」：用户一次都不用填
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestAutoChannels:

    def test_stocktake_records_flow(self):
        """提交实盘盘点 ⇒ 自动一条 `stocktake` 流水，数量 = 实盘 − 账面"""
        _, _, item = _setup(quantity=10)
        stk.create_stocktake(lines=[{'item_id': item.id, 'actual_quantity': '7'}])

        flow = SurvivalFlow.objects.get()
        assert flow.channel == 'stocktake'
        assert flow.reason == 'correct'
        assert float(flow.delta) == -3.0
        item.refresh_from_db()
        assert float(item.quantity) == 7.0

    def test_stocktake_with_no_difference_writes_nothing(self):
        """⭐ 实盘 == 账面 ⇒ **不写流水**

        「数了数、跟账上一样」本身不是一次库存变化；记下来只是噪音，
        还会让「这个月吃掉多少」跟着虚高。
        """
        _, _, item = _setup(quantity=10)
        stk.create_stocktake(lines=[{'item_id': item.id, 'actual_quantity': '10'}])

        assert SurvivalFlow.objects.count() == 0

    def test_edit_quantity_records_flow(self):
        """编辑物品改了数量 ⇒ 自动一条 `edit` 流水（用户不必再解释一遍）"""
        _, _, item = _setup(quantity=10)
        ssvc.update_item(item.id, {'name': '午餐肉罐头', 'quantity': '6'})

        flow = SurvivalFlow.objects.get()
        assert flow.channel == 'edit'
        assert float(flow.delta) == -4.0
        item.refresh_from_db()
        assert float(item.quantity) == 6.0

    def test_edit_other_fields_writes_no_flow(self):
        """只改了名字没改数量 ⇒ **不写流水**（否则每次改名都多一条 0 变化的记录）"""
        _, _, item = _setup(quantity=10)
        ssvc.update_item(item.id, {'name': '改个名'})

        assert SurvivalFlow.objects.count() == 0

    def test_create_item_records_flow(self):
        """建档时的初始数量也留痕 ⇒ 第一笔库存不是「凭空出现」的"""
        category, _, _ = _setup(name='占位', quantity=0)
        row = ssvc.create_item({
            'category_id': category.id, 'name': '新买的罐头', 'quantity': '4',
        })

        flow = SurvivalFlow.objects.get()
        assert flow.channel == 'create'
        assert float(flow.delta) == 4.0
        assert flow.item_id == row['id']

    def test_create_item_with_zero_writes_no_flow(self):
        """初始数量 0 ⇒ 不写流水（0 变化不是变化）"""
        category, _, _ = _setup(name='占位', quantity=0)
        ssvc.create_item({
            'category_id': category.id, 'name': '以后要买的', 'quantity': '0',
        })
        assert SurvivalFlow.objects.count() == 0


# ══════════════════════════════════════════════════════════════
# ③ 撤销：补反向流水，不做物理删除
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestReverse:

    def test_reverse_creates_mirror_and_restores(self):
        """⭐ 撤销 = 补一条反向流水：账正回来、原记录留着"""
        _, _, item = _setup(quantity=10)
        original = flw.record_flow(item.id, -2, reason='eat')
        item.refresh_from_db()
        assert float(item.quantity) == 8.0

        mirror = flw.reverse_flow(original['id'])

        item.refresh_from_db()
        assert float(item.quantity) == 10.0          # ← 账正回来了
        assert mirror['delta'] == 2.0                # ← 反向
        assert mirror['reverses_id'] == original['id']
        assert mirror['reason'] == 'revert'
        assert SurvivalFlow.objects.count() == 2     # ← 原记录还在，没被删

    def test_original_marked_as_reverted_in_list(self):
        """列表里原流水带 `reverted=True` —— 前端据此不再显示「撤销」按钮"""
        _, _, item = _setup(quantity=10)
        original = flw.record_flow(item.id, -2, reason='eat')
        flw.reverse_flow(original['id'])

        rows = {r['id']: r for r in flw.list_flows()}
        assert rows[original['id']]['reverted'] is True
        assert rows[original['id']]['delta'] == -2.0

    def test_double_reverse_rejected(self):
        """⭐ 同一条流水撤销两次 ⇒ 拒绝（否则点两下就多扣一次）"""
        _, _, item = _setup(quantity=10)
        original = flw.record_flow(item.id, -2, reason='eat')
        flw.reverse_flow(original['id'])

        with pytest.raises(ValueError) as exc:
            flw.reverse_flow(original['id'])
        assert '已经撤销过' in str(exc.value)

        item.refresh_from_db()
        assert float(item.quantity) == 10.0

    def test_reversing_a_reversal_rejected(self):
        """冲销记录本身不能再被撤销 —— 否则链会越来越长、账越改越乱"""
        _, _, item = _setup(quantity=10)
        original = flw.record_flow(item.id, -2, reason='eat')
        mirror = flw.reverse_flow(original['id'])

        with pytest.raises(ValueError) as exc:
            flw.reverse_flow(mirror['id'])
        assert '冲销' in str(exc.value)

    def test_reverse_of_deleted_item_rejected(self):
        """物品已删除 ⇒ 没有可以改回来的库存，只保留历史"""
        _, _, item = _setup(quantity=10)
        original = flw.record_flow(item.id, -2, reason='eat')
        item.delete()

        with pytest.raises(ValueError) as exc:
            flw.reverse_flow(original['id'])
        assert '已删除' in str(exc.value)


# ══════════════════════════════════════════════════════════════
# ④ 接口
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestApi:

    def test_list_returns_bare_array(self):
        """⭐ 列表**返回数组**，不是 `{count, results}`

        DRF 全局分页会把裸数组包成对象，前端按数组消费即「假 0」——
        界面上什么都不显示，还没有报错。
        """
        _, _, item = _setup()
        flw.record_flow(item.id, -1, reason='eat')

        resp = _client().get(BASE)
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 1
        assert body[0]['channel_label'] == '手工登记'
        assert body[0]['reason_label'] == '吃掉'

    def test_default_order_newest_first(self):
        """默认排序 = 新的在前（`-occurred_at, -id`）"""
        _, _, item = _setup()
        now = timezone.now()
        flw.record_flow(item.id, -1, occurred_at=now - timedelta(hours=5), reason='eat')
        flw.record_flow(item.id, -1, occurred_at=now - timedelta(hours=1), reason='eat')

        rows = flw.list_flows()
        assert rows[0]['occurred_at'] > rows[1]['occurred_at']

    def test_summary_static_segment_not_shadowed_by_pk(self):
        """🔴 `summary/` 不能被 `flows/<pk>/` 抢走

        被抢的症状是 404 —— 看起来像「路由没注册」，而不是「路由顺序错了」。
        """
        _, _, item = _setup()
        flw.record_flow(item.id, -1, reason='eat')

        resp = _client().get(BASE + 'summary/')
        assert resp.status_code == 200
        body = resp.json()
        assert 'month' in body and 'by_unit' in body

    def test_create_via_api(self):
        """POST 记一笔（`delta` 为负 = 用掉）"""
        _, _, item = _setup(quantity=5)
        resp = _client().post(
            BASE, {'item_id': item.id, 'delta': '-2', 'reason': 'eat'}, format='json',
        )
        assert resp.status_code == 201
        assert resp.json()['delta'] == -2.0

        item.refresh_from_db()
        assert float(item.quantity) == 3.0

    def test_create_negative_result_returns_400_and_keeps_quantity(self):
        """接口层也要是 400 + 库存不动（不能变成 500）"""
        _, _, item = _setup(quantity=1)
        resp = _client().post(
            BASE, {'item_id': item.id, 'delta': '-5'}, format='json',
        )
        assert resp.status_code == 400
        item.refresh_from_db()
        assert float(item.quantity) == 1.0

    def test_create_batch_uses_one_timestamp(self):
        """⭐ 批量：时间与原因是**整批一个**，不把单件表单复制 N 份"""
        _, _, a = _setup(name='大米', quantity=1, unit_name='斤')
        _, _, b = _setup(name='面条', quantity=1, unit_name='包')
        at = (timezone.now() - timedelta(hours=2)).isoformat()

        resp = _client().post(BASE, {
            'occurred_at': at,
            'rows': [
                {'item_id': a.id, 'delta': '5'},
                {'item_id': b.id, 'delta': '3'},
            ],
        }, format='json')
        assert resp.status_code == 201
        body = resp.json()
        assert isinstance(body, list) and len(body) == 2
        assert body[0]['occurred_at'] == body[1]['occurred_at']   # ← 同一个时刻

        a.refresh_from_db()
        b.refresh_from_db()
        assert float(a.quantity) == 6.0
        assert float(b.quantity) == 4.0

    def test_batch_is_all_or_nothing(self):
        """⭐ 批量里有一笔会变负数 ⇒ **整批都不写**

        否则用户看到「保存失败」，库存却已经被改了一半 —— 而两边看起来都对。
        """
        _, _, a = _setup(name='大米', quantity=10)
        _, _, b = _setup(name='面条', quantity=1)

        resp = _client().post(BASE, {
            'rows': [
                {'item_id': a.id, 'delta': '-3'},
                {'item_id': b.id, 'delta': '-9'},   # ← 这一笔会变负数
            ],
        }, format='json')
        assert resp.status_code == 400

        a.refresh_from_db()
        b.refresh_from_db()
        assert float(a.quantity) == 10.0    # ← 前一笔也没写进去
        assert SurvivalFlow.objects.count() == 0

    def test_reverse_endpoint(self):
        """POST `flows/<id>/reverse/`"""
        _, _, item = _setup(quantity=10)
        original = flw.record_flow(item.id, -2, reason='eat')

        resp = _client().post(f'{BASE}{original["id"]}/reverse/')
        assert resp.status_code == 201
        assert resp.json()['reverses_id'] == original['id']

    def test_reverse_twice_returns_400(self):
        """重复撤销 ⇒ 400（不是 500）"""
        _, _, item = _setup(quantity=10)
        original = flw.record_flow(item.id, -2, reason='eat')
        _client().post(f'{BASE}{original["id"]}/reverse/')

        resp = _client().post(f'{BASE}{original["id"]}/reverse/')
        assert resp.status_code == 400

    def test_list_filter_by_item(self):
        """按物品筛 —— 物品详情里「这件东西怎么变少的」要能查"""
        _, _, a = _setup(name='大米')
        _, _, b = _setup(name='面条')
        flw.record_flow(a.id, -1, reason='eat')
        flw.record_flow(b.id, -1, reason='eat')

        resp = _client().get(BASE, {'item_id': a.id})
        body = resp.json()
        assert len(body) == 1
        assert body[0]['item_id'] == a.id


# ══════════════════════════════════════════════════════════════
# ⑤ 汇总：跨单位不相加
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestSummary:

    def test_never_adds_across_units(self):
        """⭐ 不同单位**分别成桶**，不给「总消耗 X 件」这种合计数

        「用掉 3 斤米」与「用掉 2 罐罐头」不可通约。合成一个数看起来最像答案，
        其实是最没有意义的数。
        """
        _, _, rice = _setup(name='大米', quantity=10, unit_name='斤')
        _, _, can = _setup(name='罐头', quantity=10, unit_name='罐')

        flw.record_flow(rice.id, -3, reason='eat')
        flw.record_flow(can.id, -2, reason='eat')

        row = flw.summarize_flows()
        by_unit = {r['unit_name']: r for r in row['by_unit']}
        assert by_unit['斤']['consumed'] == 3.0
        assert by_unit['罐']['consumed'] == 2.0
        assert 'total' not in row                 # ← 刻意不给跨单位合计

    def test_consumed_and_gained_counted_separately(self):
        """消耗与入库分开记：一个回答「吃掉多少」，一个回答「补了多少」"""
        _, _, item = _setup(quantity=10)
        flw.record_flow(item.id, -3, reason='eat')
        flw.record_flow(item.id, 8, reason='buy')

        row = flw.summarize_flows()
        assert row['count'] == 2
        assert row['consumed_count'] == 1
        assert row['gained_count'] == 1
        assert row['by_item'][0]['consumed'] == 3.0
        assert row['by_item'][0]['gained'] == 8.0
        assert row['by_item'][0]['net'] == 5.0

    def test_reversal_nets_out(self):
        """撤销后净效果归零 —— 冲销流水**照常计入**才算出正确净额"""
        _, _, item = _setup(quantity=10)
        original = flw.record_flow(item.id, -4, reason='eat')
        flw.reverse_flow(original['id'])

        row = flw.summarize_flows()
        assert row['count'] == 2
        assert row['by_unit'][0]['net'] == 0.0

    def test_month_filter_is_half_open(self):
        """月份过滤用半开区间 `[月初, 下月初)` —— 不写 `__month`（时区一漂就漏行）"""
        _, _, item = _setup(quantity=10)
        now = timezone.now()
        flw.record_flow(item.id, -1, occurred_at=now, reason='eat')

        this_month = f'{now.year:04d}-{now.month:02d}'
        assert flw.summarize_flows(month=this_month)['count'] == 1
        assert flw.summarize_flows(month='2020-01')['count'] == 0

    def test_bad_month_format_rejected(self):
        """月份写错 → 报错（不是静默按本月算，那会给出一个看着合理的错数）"""
        with pytest.raises(ValueError):
            flw.summarize_flows(month='2026/10')
        with pytest.raises(ValueError):
            flw.summarize_flows(month='2026-13')

    def test_month_bounds_are_timezone_aware(self):
        """🔴 月界必须是 **aware datetime**，不能是 `date`

        拿 `date` 去过滤 `occurred_at`（datetime 字段）时，Django 会把它摊成
        当天午夜的 **naive** datetime 再按当前时区猜一次 —— 既报
        RuntimeWarning，也把「按哪个时区算月界」变成了隐式约定。
        判据钉在类型上：谁把返回改回 `date`，这条就红。
        """
        start, end = flw._month_range('2026-10')
        assert timezone.is_aware(start) and timezone.is_aware(end)
        assert (start.year, start.month, start.day, start.hour) == (2026, 10, 1, 0)
        assert (end.year, end.month, end.day, end.hour) == (2026, 11, 1, 0)

    def test_month_boundary_is_half_open(self):
        """月初 00:00 整那笔**算**本月；下月初 00:00 整那笔**不算**（半开区间）

        ⚠️ 用 2020 年：`record_flow` 拒绝未来时刻，用本月会被自己挡掉。
        """
        _, _, item = _setup(quantity=10)
        start, end = flw._month_range('2020-01')

        flw.record_flow(item.id, -1, occurred_at=start, reason='eat')  # 月初整整
        flw.record_flow(item.id, -1, occurred_at=end, reason='eat')    # 下月初整整

        assert flw.summarize_flows(month='2020-01')['count'] == 1
        assert flw.summarize_flows(month='2020-02')['count'] == 1
        # 下发给界面的「到」是区间**最后一天**（半开区间的右端减一天，人才看得懂）
        assert flw.summarize_flows(month='2020-01')['date_to'] == '2020-01-31'
        assert flw.summarize_flows(month='2020-01')['date_from'] == '2020-01-01'
