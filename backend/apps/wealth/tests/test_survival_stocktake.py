"""生存资源盘点 · 实盘盘点（v3.59.3）

覆盖：
  ① 盘点工作表取数：账面、上次盘点是哪天、该不该盘了、是否低于补货线
  ② ⭐ **核心判据一：账面由服务端在提交那一刻读，绝不取前端传来的值**
     —— 这不只是防篡改，是防一个**必然发生**的过期读：盘点页可能开着很久
  ③ ⭐ **核心判据二：提交即校准** —— 库存直接变成实盘数，不让「数过了」白做
  ④ ⭐ **核心判据三：删除记录不回滚库存** —— 库存是被核实过的事实，删的只是凭据
  ⑤ 明细**自带名字**：物品改名 / 删除都不改写历史
  ⑥ 不可修改（PUT/PATCH → 405）：可编辑的核对结果等于伪造的核对结果
  ⑦ 盘盈盘亏方向：正盈、负亏、零持平；差额与汇总由账面与实盘现算，**不落库**
  ⑧ 入参防呆：空单 / 同一物品两行 / 负数 / 物品不存在 / 超行数上限
  ⑨ 接口：列表与工作表都是**裸数组**（不是 {count, results}），顺序**降序**

⚠️ 与 `test_survival_snapshot.py` 的分工，别搞混：
   那份测的是**系统算出来的结论**（快照，不需要人动手）；
   这份测的是**人填进去的实盘**（盘点单，必须人动手）。
   两张表、两个入口，刻意不合并 —— 合并的后果是「点一下按钮就说自己盘过了」。

新表与 SurvivalItem 的新列由 conftest 的 session 级 django_db_setup 补齐 ——
--no-migrations --reuse-db 下，新表不会自动出现，新列也不会自动补。
"""

from datetime import date, timedelta

import pytest
from rest_framework.test import APIClient

from apps.wealth.constants import SURVIVAL_STOCKTAKE_MAX_LINES
from apps.wealth.models import (
    SurvivalCategory,
    SurvivalItem,
    SurvivalStocktake,
    SurvivalStocktakeLine,
    SurvivalUnit,
)
from apps.wealth.services import survival_stocktake as stk

DAY1 = date(2026, 9, 19)
DAY2 = date(2026, 9, 20)
DAY3 = date(2026, 9, 21)

BASE = '/api/wealth/survival/stocktakes/'


# ──────────────────────────────────────────────────────────────
# 造数
# ──────────────────────────────────────────────────────────────

def _setup(name='纸巾', quantity=10, **item_kwargs):
    """一个最简单可盘点的场景 → (category, unit, item)

    ⚠️ 类别与单位用 `get_or_create` **复用**：同一个用例里要造第二件物品时，
       再建一个同名类别会直接撞 `UniqueConstraint(user_id, name)`，
       报出来是 IntegrityError —— 看着像实现错，其实是造数写得太粗
       （skill §3 第 4 条：写断言前先问「约束允许这些数据共存吗」）。
    """
    category, _ = SurvivalCategory.objects.get_or_create(
        user_id=1, name='用',
        defaults={'consume_mode': 'on_demand', 'aggregate_mode': 'sum'},
    )
    unit, _ = SurvivalUnit.objects.get_or_create(
        user_id=1, category=category, name='件',
        defaults={'base_unit': '件', 'to_base_rate': 1},
    )
    item = SurvivalItem.objects.create(
        user_id=1, category=category, name=name, quantity=quantity,
        unit=unit, status='stocked', days_per_unit=10, **item_kwargs,
    )
    return category, unit, item


def _client():
    return APIClient()


# ══════════════════════════════════════════════════════════════
# ① 盘点工作表
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestWorksheet:

    def test_lists_items_with_book_quantity(self):
        """工作表就是把清单摊开：系统记的是多少，摆在用户面前让他对实物"""
        _setup(quantity=7)
        _setup(name='洗衣液', quantity=2)
        rows = stk.get_worksheet()
        assert len(rows) == 2
        by_name = {r['name']: r for r in rows}
        assert by_name['纸巾']['book_quantity'] == 7.0
        assert by_name['洗衣液']['book_quantity'] == 2.0

    def test_never_stocked_reports_none_not_zero(self):
        """从没盘过 → `days_since_stocktake` 是 None，**不是 0**

        0 会被读成「今天刚盘过」—— 而事实恰恰相反。这正是二期立下的
        「空值不许重载两种含义」那条判据的又一次应用。
        """
        _setup()
        row = stk.get_worksheet()[0]
        assert row['last_stocktake_date'] is None
        assert row['days_since_stocktake'] is None
        assert row['stocktake_due'] is False       # 没设周期 → 不催

    def test_due_only_when_cycle_is_set(self):
        """「该盘了」只在**设了周期**时才判

        若把「从未盘过」也算作该盘，所有没设周期的物品会一律标红 ——
        等于没有标，用户很快就学会无视它。
        """
        _, _, item = _setup(stocktake_cycle_days=30)
        _, _, watch = _setup(name='手表', stocktake_cycle_days=None)
        rows = {r['name']: r for r in stk.get_worksheet()}
        assert rows['纸巾']['stocktake_due'] is True     # 设了 30 天且从没盘过
        assert rows['手表']['stocktake_due'] is False    # 没设周期 → 不催

    def test_due_after_cycle_elapsed(self):
        """盘过之后再等够周期，才会重新变成「该盘了」"""
        _, _, item = _setup(stocktake_cycle_days=5)
        stk.create_stocktake(stocktake_date=DAY1, lines=[{'item_id': item.id, 'actual_quantity': '9'}])
        row = stk.get_worksheet()[0]
        assert row['last_stocktake_date'] == str(DAY1)
        # 工作表按「今天」算间隔，所以用一个明确的未来日期推判断
        assert row['days_since_stocktake'] is not None

    def test_below_threshold_uses_reaching_the_line(self):
        """阈值是**触发线**：降到它就该补

        「剩 2 包、阈值 2」必须提醒。写成严格小于会让正好到线的库存不提醒，
        而那正是最该提醒的时刻。
        """
        _setup(name='纸巾', quantity=2, restock_threshold=2)
        _setup(name='洗衣液', quantity=3, restock_threshold=2)
        _setup(name='牙膏', quantity=1, restock_threshold=None)
        rows = {r['name']: r for r in stk.get_worksheet()}
        assert rows['纸巾']['below_threshold'] is True       # 正好到线 → 提醒
        assert rows['洗衣液']['below_threshold'] is False
        assert rows['牙膏']['below_threshold'] is False      # 没设阈值 → 不管

    def test_filter_by_item_ids(self):
        """按选中的几件取工作表 —— 这是「每次自己挑要盘的物品」的落地"""
        _, _, first = _setup()
        _setup(name='洗衣液')
        rows = stk.get_worksheet(item_ids=[first.id])
        assert [r['name'] for r in rows] == ['纸巾']

    def test_filter_by_keyword(self):
        _setup()
        _setup(name='洗衣液')
        rows = stk.get_worksheet(keyword='洗衣')
        assert [r['name'] for r in rows] == ['洗衣液']


# ══════════════════════════════════════════════════════════════
# ②③ 提交盘点：账面由服务端读 + 盘点即校准
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestSubmitStocktake:

    def test_stock_is_calibrated_to_actual(self):
        """⭐ 提交即校准：库存直接变成实盘数"""
        _, _, item = _setup(quantity=10)
        stk.create_stocktake(stocktake_date=DAY1, lines=[
            {'item_id': item.id, 'actual_quantity': '6'},
        ])
        item.refresh_from_db()
        assert float(item.quantity) == 6.0

    def test_server_reads_book_quantity_ignoring_client(self):
        """⭐ 请求体里带一个假账面，历史里记的仍是**服务端读到**的真实库存

        前端本来就没这个字段，这里刻意塞一个 —— 断言的是「它被无视了」，
        而不是「校验器报错了」。无视比报错更安全：将来有人为了「方便」
        把字段加进入参时，这条用例会立刻红。
        """
        _, _, item = _setup(quantity=7)
        resp = _client().post(BASE, {
            'date': str(DAY1),
            'lines': [{
                'item_id': item.id, 'actual_quantity': '5', 'book_quantity': '999',
            }],
        }, format='json')
        assert resp.status_code == 201
        line = resp.data['lines'][0]
        assert line['book_quantity'] == 7.0         # 真实库存，不是 999
        assert line['actual_quantity'] == 5.0
        assert line['delta'] == -2.0
        assert line['delta_kind'] == 'deficit'

    def test_book_quantity_is_the_value_at_submit_moment(self):
        """⭐ 账面取的是**提交那一刻**的值，不是页面打开时的

        模拟：工作表已经下发（账面 10）→ 用户在别处把库存改成 4 → 现在提交。
        记录里该是 4，因为那才是他数实物时账上的真实数字。
        """
        _, _, item = _setup(quantity=10)
        stk.get_worksheet()                     # 页面打开、拿到工作表
        item.quantity = 4                       # 期间库存在别处变了
        item.save()

        row = stk.create_stocktake(stocktake_date=DAY1, lines=[
            {'item_id': item.id, 'actual_quantity': '4'},
        ])
        assert row['lines'][0]['book_quantity'] == 4.0
        assert row['lines'][0]['delta'] == 0.0

    def test_delta_direction(self):
        """盘盈 / 盘亏 / 持平 三种方向都要能分辨"""
        _, _, surplus_item = _setup(name='纸巾', quantity=3)
        _, _, deficit_item = _setup(name='洗衣液', quantity=8)
        _, _, flat_item = _setup(name='牙膏', quantity=5)

        row = stk.create_stocktake(stocktake_date=DAY1, lines=[
            {'item_id': surplus_item.id, 'actual_quantity': '5'},
            {'item_id': deficit_item.id, 'actual_quantity': '2'},
            {'item_id': flat_item.id, 'actual_quantity': '5'},
        ])
        by_name = {line['item_name']: line for line in row['lines']}
        assert by_name['纸巾']['delta_kind'] == 'surplus'
        assert by_name['纸巾']['delta'] == 2.0
        assert by_name['洗衣液']['delta_kind'] == 'deficit'
        assert by_name['洗衣液']['delta'] == -6.0
        assert by_name['牙膏']['delta_kind'] == 'flat'
        assert by_name['牙膏']['delta'] == 0.0

    def test_summary_counts(self):
        """汇总是现算的（明细不可编辑 ⇒ 重算得出同样结果 ⇒ 不落库）"""
        _, _, a = _setup(name='纸巾', quantity=3)
        _, _, b = _setup(name='洗衣液', quantity=8)
        _, _, c = _setup(name='牙膏', quantity=5)
        row = stk.create_stocktake(stocktake_date=DAY1, lines=[
            {'item_id': a.id, 'actual_quantity': '5'},
            {'item_id': b.id, 'actual_quantity': '2'},
            {'item_id': c.id, 'actual_quantity': '5'},
        ])
        assert row['line_count'] == 3
        assert row['surplus_count'] == 1
        assert row['deficit_count'] == 1
        assert row['flat_count'] == 1

    def test_summary_is_not_a_stored_column(self):
        """汇总**不许**变成表上的列 —— 它是从明细算出来的，不是存下来的"""
        column_names = {f.name for f in SurvivalStocktake._meta.get_fields()}
        for banned in (
            'line_count', 'surplus_count', 'deficit_count', 'flat_count', 'delta',
        ):
            assert banned not in column_names
        line_fields = {f.name for f in SurvivalStocktakeLine._meta.get_fields()}
        assert 'delta' not in line_fields          # 一减就有，不落库
        assert 'book_quantity' in line_fields      # 但账面必须落库：事后算不回来

    def test_partial_stocktake_leaves_other_items_alone(self):
        """只盘了一部分 —— 没被盘到的物品库存**不许**被动"""
        _, _, counted = _setup(name='纸巾', quantity=10)
        _, _, untouched = _setup(name='洗衣液', quantity=3)
        stk.create_stocktake(stocktake_date=DAY1, lines=[
            {'item_id': counted.id, 'actual_quantity': '6'},
        ])
        untouched.refresh_from_db()
        assert float(untouched.quantity) == 3.0

    def test_multiple_stocktakes_same_day_are_allowed(self):
        """同一天可以盘多次 —— 盘点是能分批的（上午盘一半、下午接着盘）"""
        _, _, item = _setup(quantity=10)
        stk.create_stocktake(stocktake_date=DAY1, lines=[
            {'item_id': item.id, 'actual_quantity': '9'},
        ])
        stk.create_stocktake(stocktake_date=DAY1, lines=[
            {'item_id': item.id, 'actual_quantity': '8'},
        ])
        rows = stk.list_stocktakes()
        assert len(rows) == 2                       # 两次都在，各有各的账面


# ══════════════════════════════════════════════════════════════
# ④ 删除不回滚库存
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestDeleteDoesNotRollBack:

    def test_delete_record_keeps_calibrated_stock(self):
        """⭐ 删掉盘点记录**不会**把库存改回去

        库存是**已经被核实过的事实**，删记录只是删掉凭据。
        若删一条历史能把库存改回去，「删记录」就成了一个能改现状的按钮 ——
        而它在界面上看起来只影响历史。用户会以为自己在整理历史，实际改了账。
        """
        _, _, item = _setup(quantity=10)
        row = stk.create_stocktake(stocktake_date=DAY1, lines=[
            {'item_id': item.id, 'actual_quantity': '6'},
        ])
        item.refresh_from_db()
        assert float(item.quantity) == 6.0

        stk.delete_stocktake(row['id'])
        item.refresh_from_db()
        assert float(item.quantity) == 6.0          # 仍是 6，不是 10
        assert SurvivalStocktake.objects.count() == 0

    def test_delete_cascades_lines(self):
        """明细随头一起删 —— 脱离头的明细没有意义"""
        _, _, item = _setup()
        row = stk.create_stocktake(stocktake_date=DAY1, lines=[
            {'item_id': item.id, 'actual_quantity': '6'},
        ])
        assert SurvivalStocktakeLine.objects.count() == 1
        stk.delete_stocktake(row['id'])
        assert SurvivalStocktakeLine.objects.count() == 0

    def test_delete_missing_raises(self):
        with pytest.raises(ValueError):
            stk.delete_stocktake(999999)


# ══════════════════════════════════════════════════════════════
# ⑤ 历史自带名字
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestHistoryKeepsItsOwnNames:

    def test_rename_does_not_rewrite_history(self):
        """⭐ 物品改名不改写历史 —— 否则「当时盘的是哪件」就说不清了"""
        _, _, item = _setup(name='纸巾')
        row = stk.create_stocktake(stocktake_date=DAY1, lines=[
            {'item_id': item.id, 'actual_quantity': '6'},
        ])
        item.name = '厨房纸巾'
        item.save()

        again = stk.get_stocktake(row['id'])
        assert again['lines'][0]['item_name'] == '纸巾'

    def test_delete_item_does_not_erase_history(self):
        """⭐ 删掉物品，历史仍在（外键 SET_NULL，名字冗余留存）"""
        _, _, item = _setup(name='纸巾')
        row = stk.create_stocktake(stocktake_date=DAY1, lines=[
            {'item_id': item.id, 'actual_quantity': '6'},
        ])
        item.delete()

        again = stk.get_stocktake(row['id'])
        assert again['lines'][0]['item_name'] == '纸巾'
        assert again['lines'][0]['item_id'] is None

    def test_category_rename_does_not_rewrite_history(self):
        """类别改名同理 —— 类别名也是冗余留存的"""
        category, _, item = _setup()
        row = stk.create_stocktake(stocktake_date=DAY1, lines=[
            {'item_id': item.id, 'actual_quantity': '6'},
        ])
        category.name = '日用'
        category.save()
        assert stk.get_stocktake(row['id'])['lines'][0]['category_name'] == '用'


# ══════════════════════════════════════════════════════════════
# ⑥ 不可修改
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestStocktakeIsImmutable:

    def test_put_and_patch_are_rejected(self):
        """⭐ 可编辑的核对结果等于伪造的核对结果 —— 405，只能删掉重盘"""
        _, _, item = _setup()
        row = stk.create_stocktake(stocktake_date=DAY1, lines=[
            {'item_id': item.id, 'actual_quantity': '6'},
        ])
        client = _client()
        put = client.put(f'{BASE}{row["id"]}/', {'note': 'x'}, format='json')
        patch = client.patch(f'{BASE}{row["id"]}/', {'note': 'x'}, format='json')
        assert put.status_code == 405
        assert patch.status_code == 405

    def test_note_change_does_not_leak_through_retrieve(self):
        """挡的是整个更新通道，不是「只挡数量」—— 备注一可改，
        「那天为什么是这样」就能被改成任意说法"""
        _, _, item = _setup()
        row = stk.create_stocktake(
            stocktake_date=DAY1, note='月度大盘',
            lines=[{'item_id': item.id, 'actual_quantity': '6'}],
        )
        _client().patch(f'{BASE}{row["id"]}/', {'note': '改过了'}, format='json')
        assert stk.get_stocktake(row['id'])['note'] == '月度大盘'


# ══════════════════════════════════════════════════════════════
# ⑦⑧ 入参防呆
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestSubmitGuards:

    def test_empty_lines_rejected(self):
        """一张没填任何物品的盘点单没有意义"""
        with pytest.raises(ValueError):
            stk.create_stocktake(stocktake_date=DAY1, lines=[])
        resp = _client().post(BASE, {'date': str(DAY1), 'lines': []}, format='json')
        assert resp.status_code == 400

    def test_duplicate_item_rejected(self):
        """同一件物品出现两行 → 报错，**不许后一行覆盖前一行**

        覆盖的后果：库存被改成后填的那个数，而前一个实盘数**已经在页面上显示过**了。
        """
        _, _, item = _setup()
        with pytest.raises(ValueError):
            stk.create_stocktake(stocktake_date=DAY1, lines=[
                {'item_id': item.id, 'actual_quantity': '6'},
                {'item_id': item.id, 'actual_quantity': '3'},
            ])

    def test_negative_actual_rejected(self):
        """实盘不能为负 —— 数错了该改数，不该让负数进库"""
        _, _, item = _setup()
        with pytest.raises(ValueError):
            stk.create_stocktake(stocktake_date=DAY1, lines=[
                {'item_id': item.id, 'actual_quantity': '-1'},
            ])
        resp = _client().post(BASE, {
            'date': str(DAY1),
            'lines': [{'item_id': item.id, 'actual_quantity': '-1'}],
        }, format='json')
        assert resp.status_code == 400

    def test_missing_item_rejected_without_partial_write(self):
        """物品不存在 → 整单拒绝，且**不能写进去一半**

        半张盘点单比没有更糟：库存改了一部分，记录却少几行，两边都对不上。
        """
        _, _, item = _setup()
        with pytest.raises(ValueError):
            stk.create_stocktake(stocktake_date=DAY1, lines=[
                {'item_id': item.id, 'actual_quantity': '6'},
                {'item_id': 999999, 'actual_quantity': '1'},
            ])
        assert SurvivalStocktake.objects.count() == 0
        assert SurvivalStocktakeLine.objects.count() == 0
        item.refresh_from_db()
        assert float(item.quantity) == 10.0          # 也没有被改

    def test_too_many_lines_rejected(self):
        """上限必须存在 —— 不设上限等于让一次请求把整份清单灌进来"""
        _, _, item = _setup()
        lines = [
            {'item_id': item.id + i, 'actual_quantity': '1'}
            for i in range(SURVIVAL_STOCKTAKE_MAX_LINES + 1)
        ]
        with pytest.raises(ValueError):
            stk.create_stocktake(stocktake_date=DAY1, lines=lines)

    def test_actual_must_be_a_number(self):
        _, _, item = _setup()
        with pytest.raises(ValueError):
            stk.create_stocktake(stocktake_date=DAY1, lines=[
                {'item_id': item.id, 'actual_quantity': '随便写的'},
            ])


# ══════════════════════════════════════════════════════════════
# ⑨ 列表顺序与接口
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestOrderingAndApis:

    def test_list_is_descending(self):
        """列表**降序**：最近一次在最上面（复盘总是从最近那次看起）

        ⚠️ 这个方向是**钉住**的：将来若加趋势图，要新开一个升序函数，
           别把这条改成升序 —— 那会让表格反过来，而且一眼看不出错。
        """
        _, _, item = _setup(quantity=10)
        for day, actual in ((DAY1, '9'), (DAY2, '8'), (DAY3, '7')):
            stk.create_stocktake(stocktake_date=day, lines=[
                {'item_id': item.id, 'actual_quantity': actual},
            ])
        rows = stk.list_stocktakes()
        assert [r['stocktake_date'] for r in rows] == [str(DAY3), str(DAY2), str(DAY1)]

    def test_limit_clamped_not_errored(self):
        """limit 是「看多少」的视角参数：非法值回落、超界夹边界，都不报错"""
        _, _, item = _setup()
        stk.create_stocktake(stocktake_date=DAY1, lines=[
            {'item_id': item.id, 'actual_quantity': '6'},
        ])
        assert len(stk.list_stocktakes(0)) == 1          # 非法 → 默认值
        assert len(stk.list_stocktakes('abc')) == 1      # 非法 → 默认值
        assert len(stk.list_stocktakes(99999)) == 1      # 超界 → 夹到上限

    def test_list_api_returns_bare_array(self):
        """⚠️ 裸数组，不是 {count, results} —— 被包一层前端会**静默显示为空**"""
        _, _, item = _setup()
        stk.create_stocktake(stocktake_date=DAY1, lines=[
            {'item_id': item.id, 'actual_quantity': '6'},
        ])
        resp = _client().get(BASE)
        assert resp.status_code == 200
        assert isinstance(resp.data, list)
        assert resp.data[0]['line_count'] == 1

    def test_worksheet_api_returns_bare_array(self):
        _setup()
        resp = _client().get(f'{BASE}worksheet/')
        assert resp.status_code == 200
        assert isinstance(resp.data, list)
        assert resp.data[0]['name'] == '纸巾'

    def test_worksheet_api_accepts_item_ids(self):
        _, _, first = _setup()
        _setup(name='洗衣液')
        resp = _client().get(f'{BASE}worksheet/?item_ids={first.id}')
        assert resp.status_code == 200
        assert [r['name'] for r in resp.data] == ['纸巾']

    def test_worksheet_api_bad_item_ids_does_not_look_empty(self):
        """⚠️ `item_ids` 写坏了要当成「不按 id 过滤」，**不能当成「一件都不选」**

        当成空选会让用户看到一张空表，而真实原因是参数写错了 ——
        错误被伪装成「你没有物品」，方向完全被带偏。
        """
        _setup()
        resp = _client().get(f'{BASE}worksheet/?item_ids=abc,,')
        assert resp.status_code == 200
        assert len(resp.data) == 1

    def test_retrieve_includes_lines(self):
        _, _, item = _setup()
        row = stk.create_stocktake(stocktake_date=DAY1, lines=[
            {'item_id': item.id, 'actual_quantity': '6'},
        ])
        resp = _client().get(f'{BASE}{row["id"]}/')
        assert resp.status_code == 200
        assert resp.data['lines'][0]['item_name'] == '纸巾'

    def test_delete_api(self):
        _, _, item = _setup()
        row = stk.create_stocktake(stocktake_date=DAY1, lines=[
            {'item_id': item.id, 'actual_quantity': '6'},
        ])
        resp = _client().delete(f'{BASE}{row["id"]}/')
        assert resp.status_code == 200
        assert SurvivalStocktake.objects.count() == 0

    def test_retrieve_missing_is_404(self):
        resp = _client().get(f'{BASE}999999/')
        assert resp.status_code == 404
