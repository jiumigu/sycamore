"""自我运转 · `bill_income` 取数器 —— 5 条（v3.62.33）

🔴 这一组钉住的是**同一类错**：两处各自都对，合起来是错的。

① **新鲜度取错了表**（§111.1）
   取数走账单明细（`wealth_bill_list`，可逐笔溯源），判「源过没过期」
   却拿了月结表 `MAX(yearmon)`。月结表一月一行、做完复盘才有一行 ⇒ 天生滞后。
   现场（2026-10-18）：账单侧 3 天前才记过、本期已取到 6,012.64 元，
   而月结表停在 47 天前 ⇒ 判 `stale` ⇒ `verdict='unknown'` ⇒
   界面写「取不到 · 本期不计入判定」。**数取到了，却被一句过期判词作废。**
   ⇒ 判据：**新鲜度必须由「取数那张表」给出**（`STALE_RULES.field` 也必须写对它）。

② **溯源行显示分类而不是子分类**（§111.2）
   分类是账本的大桶（「其他收入」这种，信息量接近零），
   子分类才说得清钱从哪来（「经营所得」/「意外来钱」）。

③ **备注键名对不上**（§111.3）
   后端给 `extra.notes`，前端 `ReadingCard` 读 `extra.note` ⇒ 备注一直没显示。
   两个键名都「看着很合理」，所以谁也没报错。

⚠️ 第 4 条是**反向守卫**：修 ① 不能顺手把「源真过期」这个判据关掉。
"""
import datetime as dt

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.selfrun.constants import STALE_RULES
from apps.selfrun.models import SelfRunMetric, SelfRunStage
from apps.selfrun.readers import bill_income
from apps.selfrun.services import compute_metric_reading
from apps.wealth.models import WealthBalanceList, WealthBillList

pytestmark = pytest.mark.django_db

URL = '/api/selfrun'


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def income_metric(client):
    """建一个只含「收入验证」的阶段，返回那条 metric。"""
    today = timezone.localdate()
    resp = client.post(f'{URL}/stages/', {
        'name': '收入测试阶段',
        'start_date': str(today - dt.timedelta(days=40)),
        'metrics': [{'template_key': 'income_verify'}],
    }, format='json')
    assert resp.status_code == 201, resp.data
    stage = SelfRunStage.objects.get()
    return stage.metrics.get(template_key='income_verify')


def _bill(days_ago, amount, *, category='其他收入', subcategory=None, notes=None):
    """造一笔收入账单。`date` 是 datetime ⇒ 用 `make_aware` 避免 naive 警告。

    ⚠️ `created_at` / `updated_at` 在模型上是 `null=True`，但**库里是 NOT NULL 且无默认值**
       （遗留表）⇒ 不显式给，INSERT 会撞 1048。测试库与开发库都不跑它的迁移，
       所以这一层只能由造数代码自己承担。
    """
    day = timezone.localdate() - dt.timedelta(days=days_ago)
    stamp = timezone.make_aware(dt.datetime.combine(day, dt.time(10, 0)))
    return WealthBillList.objects.create(
        transaction_type='收入',
        date=stamp,
        category=category,
        subcategory=subcategory,
        amount=amount,
        notes=notes,
        year=day.year, month=day.month, day=day.day,
        created_at=stamp, updated_at=stamp,
    )


def _monthly_row(yearmon, otherincome=0.0):
    """造一行月结表（`managed=False` 的遗留表，测试库里有镜像 DDL）。"""
    return WealthBalanceList.objects.create(yearmon=yearmon, otherincome=otherincome)


def _month_start():
    """取数区间的起点：本月 1 号，但**至少回看 6 天**。

    🔴 原本是 `today.replace(day=1)` —— 于是**每月 1–3 号这三天的用例必红**：
       造数用 `_bill(3, …)`（3 天前），月初时它落在**上个月**，
       而区间从本月 1 号起 ⇒ 取不到 ⇒ `final_value` 变 0。
       2026-11-01 跑全量时就撞上了（`assert 0 == 12.64`），
       看着像「取数器坏了」，其实是用例自己的日期炸弹。
       区间只负责「把造数包进去」，月结表滞后那件事仍由 `_monthly_row('2026-08')` 测到。
    """
    today = timezone.localdate()
    return min(today.replace(day=1), today - dt.timedelta(days=6))


class TestFreshnessFollowsBillTable:
    """🔴 ① 新鲜度必须跟着「取数那张表」走。"""

    def test_monthly_table_lagging_does_not_make_it_unknown(self, income_metric):
        """月结表停在两个月前、账单三天前刚记过 ⇒ **不是 stale**。

        这条就是 2026-10-18 的现场：数已经取到了，却因为另一张表的老化
        被判「取不到」。修法是让 `freshness_at` 来自 `WealthBillList.MAX(date)`。
        """
        _monthly_row('2026-08')          # 月结表停在很久以前（旧实现会判 47 天 ⇒ stale）
        _bill(3, 12.64, subcategory='经营所得')

        r = compute_metric_reading(income_metric, _month_start(), _month_start() + dt.timedelta(days=31))

        assert r['state'] == 'ok', f'月结表滞后不该影响这条：{r["freshness"]}'
        assert r['verdict'] != 'unknown'
        assert r['final_value'] == 12.64
        # 新鲜度报的是**账单表**那条记录的年龄，不是月结表的
        assert r['freshness']['days'] <= 7, r['freshness']
        assert r['freshness']['at'].startswith(str(timezone.localdate() - dt.timedelta(days=3)))

    def test_still_stale_when_bill_table_itself_is_old(self, income_metric):
        """反向守卫：账单表自己也一个多月没记 ⇒ `stale` 判据照常生效。

        ⚠️ 修 ① 时最容易犯的错是「把这条判据整个关掉」——
        那会让「真的断了记账」也显示成一个正常数。
        """
        _monthly_row('2026-08')
        _bill(45, 500.0, subcategory='经营所得')

        r = compute_metric_reading(income_metric, _month_start(), _month_start() + dt.timedelta(days=31))

        assert r['state'] == 'stale'
        assert r['verdict'] == 'unknown'
        assert r['freshness']['days'] > r['freshness']['limit']

    def test_stale_rule_points_at_the_table_being_read(self):
        """`STALE_RULES.field` 是文档性标注 —— 但它必须指向**取数那张表**。

        写成月结表的 `MAX(yearmon)`，后来人会照着它去「修」实现（本轮就是这么来的）。
        """
        assert STALE_RULES['bill_income']['field'] == 'MAX(date)'


class TestBreakdownReadability:
    """🔴 ②③ 溯源行要能回答「这笔钱从哪来」。"""

    def test_shows_subcategory_not_category(self, income_metric):
        # 按日期排序输出 ⇒ 先造 2 天前那条
        _bill(2, 6000.0, subcategory='意外来钱')
        _bill(1, 12.64, subcategory='经营所得')

        out = bill_income(income_metric, _month_start(), _month_start() + dt.timedelta(days=31))

        assert [b['l2'] for b in out['breakdown']] == ['意外来钱', '经营所得']

    def test_falls_back_to_category_when_no_subcategory(self, income_metric):
        """老记录常常没子分类 —— 回落到分类，**不留空格**。

        ⚠️ 分类必须命中模板的 `where.category='其他收入'`，
        否则整条被过滤掉、断言在空列表上「通过」（假绿）。
        """
        _bill(1, 100.0, category='其他收入', subcategory=None)

        out = bill_income(income_metric, _month_start(), _month_start() + dt.timedelta(days=31))

        assert len(out['breakdown']) == 1
        assert out['breakdown'][0]['l2'] == '其他收入'

    def test_note_key_matches_what_the_card_renders(self, income_metric):
        """前端 `ReadingCard` 读的是 `extra.note`（无 s）—— 后端就得给 `note`。"""
        _bill(1, 12.64, subcategory='经营所得', notes='公众号')

        out = bill_income(income_metric, _month_start(), _month_start() + dt.timedelta(days=31))

        extra = out['breakdown'][0]['extra']
        assert extra['note'] == '公众号'
        assert 'notes' not in extra, '旧键名留着只会让下一个人再猜一次'
