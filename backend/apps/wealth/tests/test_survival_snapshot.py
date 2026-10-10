"""生存资源盘点 · 盘点快照（v3.59.0 二期）

覆盖：
  ① 落快照：综合三档 + 期望 + 短板 + 类别明细，全部如实落库
  ② ⭐ **核心不变量：快照一旦落库就不因后续改动而变**
     —— 加库存、改配方、给类别改名、删掉类别，历史点都必须保持原样
  ③ 同一天重复盘点**默认拒绝**（400 + 可照做的提示），不静默覆盖
  ④ 快照**不可修改**（PUT/PATCH → 405）：可编辑的历史等于伪造的历史
  ⑤ 趋势按日期**升序**（折线从左到右），列表按**倒序**（表格最近的在上）
     —— 两处顺序刻意相反，用例把两边都钉住，防止被「顺手统一」
  ⑥ 逐点差值与对比：空值不补 0（不知道 ≠ 没变化）；差值小于 epsilon 判「持平」
  ⑦ 两次之间改过类别构成或消耗模式 → 标注「不可直接比」并说明原因
  ⑧ `series` 里的空值保持 None，由前端画断点（补 0 会画出假线）
  ⑨ 接口：列表裸数组、limit 夹边界、删除后曲线少一点

新表由 conftest 的 session 级 django_db_setup 镜像建表 ——
--no-migrations --reuse-db 下新 managed 表不会自动出现。
"""

from datetime import date

import pytest
from rest_framework.test import APIClient

from apps.wealth.constants import (
    SURVIVAL_SNAPSHOT_DELTA_EPSILON,
    SURVIVAL_SNAPSHOT_MAX_LIMIT,
)
from apps.wealth.models import (
    SurvivalCategory,
    SurvivalItem,
    SurvivalSnapshot,
    SurvivalSnapshotCategory,
    SurvivalUnit,
)
from apps.wealth.services import survival_service as svc
from apps.wealth.services import survival_snapshot as snap

DAY1 = date(2026, 9, 19)
DAY2 = date(2026, 9, 20)
DAY3 = date(2026, 9, 21)


def _stock(quantity=10, days_per_unit=10, name='纸巾', mode='on_demand'):
    """一个最简单可算的场景：一件用 10 天、有 10 件 → 100 天左右

    刻意不用配餐类：快照要验的是「存下来会不会变」，
    配餐那套已经在 test_survival.py 里钉住了，这里引入只会让断言更难读。
    """
    category = SurvivalCategory.objects.create(
        user_id=1, name='用', consume_mode=mode, aggregate_mode='sum',
    )
    unit = SurvivalUnit.objects.create(
        user_id=1, category=category, name='件', base_unit='件', to_base_rate=1,
    )
    SurvivalItem.objects.create(
        user_id=1, category=category, name=name, quantity=quantity,
        unit=unit, days_per_unit=days_per_unit, status='stocked',
    )
    return category, unit


def _stock_uncomputable():
    """有物品但算不出来（没填单件可用天数）—— 用来验「空值不等于 0」"""
    category = SurvivalCategory.objects.create(
        user_id=1, name='穿', consume_mode='on_demand', aggregate_mode='sum',
    )
    unit = SurvivalUnit.objects.create(
        user_id=1, category=category, name='件', base_unit='件', to_base_rate=1,
    )
    SurvivalItem.objects.create(
        user_id=1, category=category, name='大衣', quantity=3,
        unit=unit, days_per_unit=None, status='stocked',
    )
    return category


# ══════════════════════════════════════════════════════════════
# ① 落快照
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestTakeSnapshot:
    """落一份快照：存的是结论，不是明细"""

    def test_stores_overall_and_category_rows(self):
        _stock()
        row = snap.take_snapshot(snapshot_date=DAY3, note='第一次盘')

        assert row['date'] == '2026-09-21'
        assert row['note'] == '第一次盘'
        assert row['source'] == 'manual'
        assert row['expected'] is not None
        assert row['shortest_category'] == '用'
        assert row['category_count'] == 1
        assert row['item_count'] == 1
        assert row['trustworthy'] is True

        assert len(row['categories']) == 1
        detail = row['categories'][0]
        assert detail['category_name'] == '用'
        assert detail['consume_mode'] == 'on_demand'
        assert detail['expected'] is not None

        assert SurvivalSnapshot.objects.count() == 1
        assert SurvivalSnapshotCategory.objects.count() == 1

    def test_three_scenarios_all_stored(self):
        _stock()
        row = snap.take_snapshot(snapshot_date=DAY3)

        days = row['days']
        assert days['optimistic'] > days['likely'] > days['pessimistic']
        # 乐观 = 撑最久：这条语义在任何一层都不能反过来
        assert row['expected'] is not None
        assert days['optimistic'] >= row['expected'] >= days['pessimistic']

    def test_null_is_not_zero(self):
        """算不出来的类别落库为 NULL，**不是 0**

        0 是「那天真的撑不了」这个结论；NULL 是「那天没算出这个数」。
        混起来会把「没填数据」显示成最坏结论。
        """
        _stock_uncomputable()
        row = snap.take_snapshot(snapshot_date=DAY3)

        assert row['expected'] is None
        assert row['days']['likely'] is None
        assert row['shortest_category'] is None
        detail = row['categories'][0]
        assert detail['expected'] is None

        stored = SurvivalSnapshotCategory.objects.get()
        assert stored.days_expected is None
        assert stored.days_likely is None

    def test_refuses_when_analysis_unavailable(self, monkeypatch):
        """数据没就绪时**不落空快照** —— 那会在曲线上留一个解释不清的点"""
        monkeypatch.setattr(
            svc, 'get_analysis',
            lambda *a, **k: {'available': False, 'reason': '数据表尚未建立'},
        )
        with pytest.raises(ValueError, match='数据表尚未建立'):
            snap.take_snapshot(snapshot_date=DAY3)
        assert SurvivalSnapshot.objects.count() == 0


# ══════════════════════════════════════════════════════════════
# ② ⭐ 核心不变量：历史不随后续改动而变
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestSnapshotIsImmutableHistory:
    """快照存的是「那时我以为能撑多久」—— 今天的修改不该改写昨天"""

    def test_stale_result_survives_inventory_change(self):
        _stock(quantity=10, days_per_unit=10)
        snap.take_snapshot(snapshot_date=DAY1)
        stored_before = float(SurvivalSnapshot.objects.get().days_expected)

        # 大补货：库存翻 10 倍
        SurvivalItem.objects.update(quantity=100)
        current = svc.get_analysis(DAY3)['overall']['expected']

        stored_after = float(SurvivalSnapshot.objects.get().days_expected)
        assert stored_after == stored_before       # 历史没变
        assert current > stored_before             # 当下确实变了
        # 这正是「存结论」而非「按今天重算」的意义所在：
        # 若快照只存明细，上面两个数会相等，曲线就会被追溯性改写。

    def test_category_rename_does_not_rewrite_history(self):
        category, _ = _stock()
        snap.take_snapshot(snapshot_date=DAY1)

        category.name = '口粮'
        category.save()

        head = snap.list_snapshots()[0]
        assert head['shortest_category'] == '用'          # 当时的最短类别名
        # 类别明细只在详情里（列表不带明细，免得列表接口越用越重）
        detail = snap.get_snapshot(head['id'])
        assert detail['categories'][0]['category_name'] == '用'

    def test_history_survives_category_delete(self):
        """删掉类别后历史点仍在 —— 历史自带名字，所以不阻塞删除"""
        category, unit = _stock()
        snap.take_snapshot(snapshot_date=DAY1)

        SurvivalItem.objects.all().delete()
        unit.delete()
        category.delete()

        detail = snap.get_snapshot(snap.list_snapshots()[0]['id'])
        assert detail['categories'][0]['category_name'] == '用'
        assert detail['categories'][0]['category_id'] is None
        assert detail['categories'][0]['expected'] is not None


# ══════════════════════════════════════════════════════════════
# ③ 同一天只留一份
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestSameDayGuard:
    """一天两个点会让曲线上出现竖直段，而且「哪份是真的」无法回答"""

    def test_duplicate_same_day_is_rejected(self):
        _stock()
        snap.take_snapshot(snapshot_date=DAY3, note='第一次')

        with pytest.raises(ValueError, match='已经盘点过'):
            snap.take_snapshot(snapshot_date=DAY3, note='第二次')

        assert SurvivalSnapshot.objects.count() == 1
        assert SurvivalSnapshot.objects.get().note == '第一次'   # 原快照未被动过

    def test_overwrite_replaces_and_keeps_single_row(self):
        _stock()
        snap.take_snapshot(snapshot_date=DAY3, note='旧')

        SurvivalItem.objects.update(quantity=100)
        row = snap.take_snapshot(snapshot_date=DAY3, note='新', overwrite=True)

        assert row['note'] == '新'
        assert SurvivalSnapshot.objects.count() == 1
        assert SurvivalSnapshotCategory.objects.count() == 1   # 旧明细被带走
        assert float(SurvivalSnapshot.objects.get().days_expected) > 0


# ══════════════════════════════════════════════════════════════
# ④ 列表与趋势的顺序（刻意相反）
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestOrdering:
    """列表倒序（表格最近的在上）/ 趋势升序（折线从左到右）"""

    def _seed_three(self):
        _stock(quantity=10)
        snap.take_snapshot(snapshot_date=DAY1)
        SurvivalItem.objects.update(quantity=20)
        snap.take_snapshot(snapshot_date=DAY2)
        SurvivalItem.objects.update(quantity=40)
        snap.take_snapshot(snapshot_date=DAY3)

    def test_list_is_descending(self):
        self._seed_three()
        rows = snap.list_snapshots()
        assert [r['date'] for r in rows] == ['2026-09-21', '2026-09-20', '2026-09-19']

    def test_trend_is_ascending(self):
        self._seed_three()
        points = snap.get_trend()['points']
        assert [p['date'] for p in points] == ['2026-09-19', '2026-09-20', '2026-09-21']

    def test_limit_is_clamped_not_rejected(self):
        """limit 超界夹到边界、非法值回落默认 —— 视角参数不值得甩 400"""
        self._seed_three()
        assert snap.get_trend(limit=SURVIVAL_SNAPSHOT_MAX_LIMIT + 999)['count'] == 3
        assert snap.get_trend(limit='abc')['count'] == 3
        assert snap.get_trend(limit=0)['count'] == 3
        assert snap.get_trend(limit=2)['count'] == 2
        # 只取 2 个时必须取**最近的**两个，而不是最早的
        assert [p['date'] for p in snap.get_trend(limit=2)['points']] == [
            '2026-09-20', '2026-09-21',
        ]


# ══════════════════════════════════════════════════════════════
# ⑤ 逐点差值与对比
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestDeltasAndComparison:

    def test_first_point_has_no_delta(self):
        _stock()
        snap.take_snapshot(snapshot_date=DAY1)
        point = snap.get_trend()['points'][0]
        assert point['delta_expected'] is None
        assert point['delta_kind'] is None
        assert point['days_since_previous'] is None

    def test_second_point_carries_delta_and_interval(self):
        _stock(quantity=10)
        snap.take_snapshot(snapshot_date=DAY1)
        SurvivalItem.objects.update(quantity=20)
        snap.take_snapshot(snapshot_date=DAY3)

        point = snap.get_trend()['points'][1]
        assert point['delta_expected'] is not None
        assert point['delta_kind'] == 'up'          # 补了货，撑得更久了
        assert point['days_since_previous'] == 2    # 19 号 → 21 号

    def test_small_change_is_flat(self):
        """变化小于 epsilon 判「持平」—— 「+0.0 天」是噪声不是结论"""
        _stock(quantity=10, days_per_unit=10)
        snap.take_snapshot(snapshot_date=DAY1)
        SurvivalItem.objects.update(quantity=10.01)     # 变化远小于 0.5 天
        snap.take_snapshot(snapshot_date=DAY2)

        point = snap.get_trend()['points'][1]
        assert point['delta_kind'] == 'flat'
        assert abs(point['delta_expected']) < SURVIVAL_SNAPSHOT_DELTA_EPSILON

    def test_delta_is_none_when_either_side_missing(self):
        """任一端算不出来 → 差值 None，**不是 0**

        0 会显示成「跟上期持平」—— 那是把「不知道」说成了结论。
        """
        _stock_uncomputable()
        snap.take_snapshot(snapshot_date=DAY1)
        snap.take_snapshot(snapshot_date=DAY2)

        point = snap.get_trend()['points'][1]
        assert point['delta_expected'] is None
        assert point['delta_kind'] is None

    def test_single_point_is_not_comparable(self):
        _stock()
        snap.take_snapshot(snapshot_date=DAY1)
        comparison = snap.get_trend()['comparison']
        assert comparison['comparable'] is False
        assert comparison['reason']
        assert snap.get_trend()['has_enough_points'] is False

    def test_no_snapshot_at_all(self):
        trend = snap.get_trend()
        assert trend['count'] == 0
        assert trend['has_enough_points'] is False
        assert trend['comparison']['comparable'] is False
        assert trend['comparison']['reason'] == '还没有任何盘点记录'

    def test_comparable_when_config_unchanged(self):
        _stock(quantity=10)
        snap.take_snapshot(snapshot_date=DAY1)
        SurvivalItem.objects.update(quantity=30)
        snap.take_snapshot(snapshot_date=DAY2)

        comparison = snap.get_trend()['comparison']
        assert comparison['comparable'] is True
        assert comparison['config_changed'] is False
        assert comparison['changed_categories'] == []
        assert comparison['reason'] == ''
        assert comparison['delta_item_count'] == 0
        assert comparison['latest_date'] == '2026-09-20'

    def test_config_change_is_flagged_not_hidden(self):
        """改了消耗模式 → 天数差里混着「换了算法」，必须标成不可直接比"""
        category, _ = _stock(quantity=10)
        snap.take_snapshot(snapshot_date=DAY1)

        category.consume_mode = 'time_based'
        category.save()
        snap.take_snapshot(snapshot_date=DAY2)

        comparison = snap.get_trend()['comparison']
        assert comparison['config_changed'] is True
        assert comparison['comparable'] is False
        assert '用' in comparison['changed_categories']
        assert '换了算法' in comparison['reason']

    def test_added_category_counts_as_config_change(self):
        _stock(quantity=10)
        snap.take_snapshot(snapshot_date=DAY1)

        second = SurvivalCategory.objects.create(
            user_id=1, name='数字', consume_mode='time_based', aggregate_mode='sum',
        )
        unit = SurvivalUnit.objects.create(
            user_id=1, category=second, name='册', base_unit='册', to_base_rate=1,
        )
        SurvivalItem.objects.create(
            user_id=1, category=second, name='书', quantity=5, unit=unit,
            days_per_unit=7, hours_per_unit=6, status='stocked',
        )
        snap.take_snapshot(snapshot_date=DAY2)

        comparison = snap.get_trend()['comparison']
        assert '数字' in comparison['changed_categories']
        assert comparison['comparable'] is False

    def test_config_diff_ignores_untouched_category(self):
        """没动过的类别不该出现在变动清单里 —— 宁可少报也不要误报"""
        _stock()
        snap.take_snapshot(snapshot_date=DAY1)
        SurvivalItem.objects.update(quantity=30)
        snap.take_snapshot(snapshot_date=DAY2)
        assert snap._config_diff(
            SurvivalSnapshot.objects.order_by('snapshot_date').first().id,
            SurvivalSnapshot.objects.order_by('-snapshot_date').first().id,
        ) == []


# ══════════════════════════════════════════════════════════════
# ⑥ series：空值保持 None（前端画断点）
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestSeries:

    def test_series_lengths_match_points(self):
        _stock(quantity=10)
        snap.take_snapshot(snapshot_date=DAY1)
        SurvivalItem.objects.update(quantity=20)
        snap.take_snapshot(snapshot_date=DAY2)

        trend = snap.get_trend()
        series = trend['series']
        size = len(trend['points'])
        for key in ('dates', 'expected', 'optimistic', 'pessimistic', 'cash_days', 'item_count'):
            assert len(series[key]) == size, key

    def test_series_keeps_null_instead_of_zero(self):
        """空值**补 0 会画出一条「那天物资归零」的假线**"""
        _stock_uncomputable()
        snap.take_snapshot(snapshot_date=DAY1)
        series = snap.get_trend()['series']
        assert series['expected'] == [None]
        assert series['optimistic'] == [None]
        assert series['item_count'] == [1]      # 件数是事实，仍然给

    def test_series_ascending_along_with_points(self):
        _stock(quantity=10)
        snap.take_snapshot(snapshot_date=DAY1)
        SurvivalItem.objects.update(quantity=20)
        snap.take_snapshot(snapshot_date=DAY2)
        series = snap.get_trend()['series']
        assert series['dates'] == ['2026-09-19', '2026-09-20']
        assert series['expected'][1] > series['expected'][0]


# ══════════════════════════════════════════════════════════════
# ⑦ 接口
# ══════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestSnapshotApi:

    def _client(self):
        return APIClient()

    def test_list_returns_bare_array(self):
        _stock()
        snap.take_snapshot(snapshot_date=DAY1)
        response = self._client().get('/api/wealth/survival/snapshots/')
        assert response.status_code == 200
        assert isinstance(response.data, list)
        assert len(response.data) == 1

    def test_create_returns_201_and_row(self):
        _stock()
        response = self._client().post(
            '/api/wealth/survival/snapshots/',
            {'date': '2026-09-21', 'note': '接口盘一次'}, format='json',
        )
        assert response.status_code == 201
        assert response.data['date'] == '2026-09-21'
        assert response.data['note'] == '接口盘一次'

    def test_create_duplicate_returns_400_with_actionable_detail(self):
        _stock()
        client = self._client()
        client.post('/api/wealth/survival/snapshots/', {'date': '2026-09-21'}, format='json')
        response = client.post(
            '/api/wealth/survival/snapshots/', {'date': '2026-09-21'}, format='json',
        )
        assert response.status_code == 400
        # 提示必须能照做：说明为什么拒绝、以及要怎么办
        assert '已经盘点过' in response.data['detail']
        assert '删' in response.data['detail']

    def test_overwrite_flag_is_honoured(self):
        _stock()
        client = self._client()
        client.post('/api/wealth/survival/snapshots/', {'date': '2026-09-21'}, format='json')
        response = client.post(
            '/api/wealth/survival/snapshots/',
            {'date': '2026-09-21', 'overwrite': True, 'note': '覆盖'}, format='json',
        )
        assert response.status_code == 201
        assert response.data['note'] == '覆盖'
        assert SurvivalSnapshot.objects.count() == 1

    def test_update_and_patch_are_405(self):
        """快照不可修改 —— 可编辑的历史等于伪造的历史"""
        _stock()
        pk = snap.take_snapshot(snapshot_date=DAY1)['id']
        client = self._client()

        put = client.put(f'/api/wealth/survival/snapshots/{pk}/', {'note': 'x'}, format='json')
        patch = client.patch(f'/api/wealth/survival/snapshots/{pk}/', {'note': 'x'}, format='json')
        assert put.status_code == 405
        assert patch.status_code == 405
        assert '不可修改' in put.data['detail']
        assert SurvivalSnapshot.objects.get().note == ''      # 一个字都没改

    def test_retrieve_includes_categories(self):
        _stock()
        pk = snap.take_snapshot(snapshot_date=DAY1)['id']
        response = self._client().get(f'/api/wealth/survival/snapshots/{pk}/')
        assert response.status_code == 200
        assert len(response.data['categories']) == 1
        assert response.data['categories'][0]['category_name'] == '用'

    def test_delete_removes_point_and_its_rows(self):
        _stock()
        pk = snap.take_snapshot(snapshot_date=DAY1)['id']
        response = self._client().delete(f'/api/wealth/survival/snapshots/{pk}/')
        assert response.status_code == 200
        assert SurvivalSnapshot.objects.count() == 0
        assert SurvivalSnapshotCategory.objects.count() == 0   # 明细被级联带走

    def test_trend_endpoint_shape(self):
        _stock(quantity=10)
        snap.take_snapshot(snapshot_date=DAY1)
        SurvivalItem.objects.update(quantity=30)
        snap.take_snapshot(snapshot_date=DAY2)

        response = self._client().get('/api/wealth/survival/snapshots/trend/')
        assert response.status_code == 200
        assert response.data['count'] == 2
        assert response.data['has_enough_points'] is True
        assert [p['date'] for p in response.data['points']] == ['2026-09-19', '2026-09-20']
        assert response.data['comparison']['comparable'] is True
        assert len(response.data['series']['dates']) == 2
        # 第一个点的差值是空，第二个点有 —— 空值传成 null 而不是 0
        assert response.data['points'][0]['delta_expected'] is None

    def test_trend_limit_query_param(self):
        _stock(quantity=10)
        for index, day in enumerate((DAY1, DAY2, DAY3)):
            snap.take_snapshot(snapshot_date=day)
        response = self._client().get('/api/wealth/survival/snapshots/trend/?limit=2')
        assert response.data['count'] == 2
        assert [p['date'] for p in response.data['points']] == ['2026-09-20', '2026-09-21']

    def test_delete_unknown_returns_404(self):
        response = self._client().delete('/api/wealth/survival/snapshots/9999/')
        assert response.status_code == 404
