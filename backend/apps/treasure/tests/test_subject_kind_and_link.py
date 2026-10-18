"""好恶物档案馆：记录分型 + 三模块联动（v3.60.32）

覆盖三类「出错了也不会报错」的地方：

1. **类别文案按侧分流** —— 歹物侧若拿到好物侧文案，界面上是「🏪 好店」配
   一条 👎 歹物；不报错、不发失败请求，只能靠眼睛看出来。
2. **`subject_kind` 在 PUT 里被静默打回默认** —— 模型带 `default` 的字段，
   DRF 在非 partial 更新且请求未送时会用 default 填进 `validated_data`。
   把一条方法型记录改个名字，它就变成实物了。
3. **徽标回流** —— 取不到与「没评过」在响应里都是 `null`，所以徽标真值必须
   在物件列表上被断言出来，而不是靠界面看着对。
"""

import pytest
from rest_framework.test import APIClient

from apps.treasure.constants import CATEGORY_LABELS_BY_TYPE
from apps.treasure.models import GoodThing

pytestmark = pytest.mark.django_db

THINGS_URL = '/api/treasure/things/'


@pytest.fixture
def client():
    return APIClient()


# ──────────────────────────────────────────────────────────────
# 造数
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def prop_category():
    from apps.wealth.models import WealthPropertyCategory

    return WealthPropertyCategory.objects.create(user_id=1, name='家电')


@pytest.fixture
def prop(prop_category):
    from apps.wealth.models import WealthProperty

    return WealthProperty.objects.create(
        user_id=1, category=prop_category, name='空气炸锅',
    )


@pytest.fixture
def survival_category():
    from apps.wealth.models import SurvivalCategory

    return SurvivalCategory.objects.create(user_id=1, name='食品')


@pytest.fixture
def survival_item(survival_category):
    from apps.wealth.models import SurvivalItem

    return SurvivalItem.objects.create(
        user_id=1, category=survival_category, name='空气滤芯',
    )


def _create(**kwargs):
    payload = {'record_type': '好', 'name': '某物', **kwargs}
    return GoodThing.objects.create(**payload)


# ──────────────────────────────────────────────────────────────
# 一、类别文案按侧分流
# ──────────────────────────────────────────────────────────────

class TestCategoryLabelBySide:
    def test_two_sides_have_different_labels(self):
        """同一份 key，两侧文案必须不同 —— 否则「歹物里躺着好店」原样复现。"""
        good = CATEGORY_LABELS_BY_TYPE['好']
        bad = CATEGORY_LABELS_BY_TYPE['歹']
        assert set(good) == set(bad), '两侧 key 必须共用（分家会让迁移变成值重写）'
        for key in good:
            assert good[key] != bad[key], f'{key} 两侧文案相同，等于没分家'

    def test_serializer_returns_label_of_its_own_side(self, client):
        """歹物取到的是歹物侧文案，好物取到的是好物侧文案。"""
        _create(record_type='好', category='店', name='楼下那家面馆')
        _create(record_type='歹', category='店', name='商场里那家')

        rows = client.get(THINGS_URL).data
        by_name = {row['name']: row for row in rows}
        assert by_name['楼下那家面馆']['category_display'] == CATEGORY_LABELS_BY_TYPE['好']['店']
        assert by_name['商场里那家']['category_display'] == CATEGORY_LABELS_BY_TYPE['歹']['店']
        # 好物侧的「好店」绝不能出现在歹物上
        assert '好店' not in by_name['商场里那家']['category_display']

    def test_meta_exposes_both_sides(self, client):
        """label 只有后端一份 ⇒ meta 必须把两侧都发出来，前端不自己拼。"""
        payload = client.get(f'{THINGS_URL}meta/').data
        assert set(payload['categories_by_type']) == {'好', '歹'}
        assert payload['categories_by_type']['好'][0]['label'] != \
            payload['categories_by_type']['歹'][0]['label']
        assert [o['value'] for o in payload['subject_kind_options']] == ['实物', '方法']


# ──────────────────────────────────────────────────────────────
# 二、记录对象决定字段
# ──────────────────────────────────────────────────────────────

class TestSubjectKind:
    def test_method_kind_forces_category_empty(self, client):
        """方法型带了类别 ⇒ 服务端把它置空（不指望客户端记得送空串）。"""
        res = client.post(THINGS_URL, {
            'record_type': '好', 'subject_kind': '方法',
            'name': '看房技巧', 'category': '吃', 'method_group': '生活',
            'why_good': '省了很多时间',
        }, format='json')
        assert res.status_code == 201
        assert res.data['category'] == ''
        assert res.data['category_display'] == ''
        assert res.data['method_group'] == '生活'

    def test_physical_requires_category(self, client):
        """实物型不选类别 ⇒ 400，且落在 category 这个键上（前端才能定位）。"""
        res = client.post(THINGS_URL, {
            'record_type': '好', 'subject_kind': '实物',
            'name': '空气炸锅', 'why_good': '好用',
        }, format='json')
        assert res.status_code == 400
        assert 'category' in res.data

    def test_physical_clears_method_group(self, client):
        """实物型带方法归类 ⇒ 服务端置空（同一个「两处都要清」的判据）。"""
        res = client.post(THINGS_URL, {
            'record_type': '好', 'subject_kind': '实物',
            'name': '空气炸锅', 'category': '用', 'method_group': '工作',
            'why_good': '好用',
        }, format='json')
        assert res.status_code == 201
        assert res.data['method_group'] == ''

    def test_reject_category_not_in_enum(self, client):
        res = client.post(THINGS_URL, {
            'record_type': '好', 'subject_kind': '实物',
            'name': 'x', 'category': '方法', 'why_good': 'y',
        }, format='json')
        assert res.status_code == 400
        assert 'category' in res.data

    def test_put_without_subject_kind_keeps_existing(self, client):
        """🔴 PUT 只改名字，方法型必须**仍然是方法型**。

        模型上 `subject_kind` 有 `default='实物'`，DRF 在非 partial 更新且
        请求未送该字段时会用 default 填进 `validated_data` —— 没有
        `_keep_if_absent` 这道护栏的话，这次 PUT 会把它静默改回实物
        （连带那条记录的字段全变），而响应里一切正常。
        """
        thing = _create(
            subject_kind='方法', category='', method_group='学习', name='内化',
        )
        res = client.put(f'{THINGS_URL}{thing.id}/', {
            'record_type': '好', 'name': '内化（改名）',
            'why_good': '很有效',
        }, format='json')
        assert res.status_code == 200, res.data
        assert res.data['subject_kind'] == '方法', '未送 subject_kind 时被打回了默认值'
        assert res.data['method_group'] == '学习'

        thing.refresh_from_db()
        assert thing.subject_kind == '方法'
        assert thing.method_group == '学习'


# ──────────────────────────────────────────────────────────────
# 三、三模块联动
# ──────────────────────────────────────────────────────────────

class TestLinkAndBadge:
    def test_two_links_are_mutually_exclusive(self, client, prop, survival_item):
        """可空列上的约束 DRF 会静默放过 ⇒ 必须手写 validate。"""
        res = client.post(THINGS_URL, {
            'record_type': '好', 'subject_kind': '实物',
            'name': 'x', 'category': '用', 'why_good': 'y',
            'property': prop.id, 'survival_item': survival_item.id,
        }, format='json')
        assert res.status_code == 400
        assert 'survival_item' in res.data

    def test_one_thing_at_most_one_record(self, client, prop):
        """一件实物最多一条评价：第二条必须被拦在 400，而不是 500。"""
        _create(name='空气炸锅', category='用', property=prop)
        res = client.post(THINGS_URL, {
            'record_type': '歹', 'subject_kind': '实物',
            'name': '空气炸锅', 'category': '用', 'avoid_reason': '不好用',
            'property': prop.id,
        }, format='json')
        assert res.status_code == 400
        assert 'property' in res.data

    def test_badge_returned_on_property_list(self, client, prop):
        """徽标由后端随列表下发（不是前端拉全量档案自己建 map）。"""
        assert client.get('/api/wealth/property/items/').data[0]['treasure_badge'] is None

        _create(name='空气炸锅', category='用', property=prop)
        row = client.get('/api/wealth/property/items/').data[0]
        assert row['treasure_badge'] == '好'

    def test_badge_returned_on_survival_item_list(self, client, survival_item):
        assert client.get('/api/wealth/survival/items/').data[0]['treasure_badge'] is None

        _create(name='空气滤芯', category='用', property=None,
                survival_item=survival_item)
        row = client.get('/api/wealth/survival/items/').data[0]
        assert row['treasure_badge'] == '好'

    def test_deleting_property_keeps_the_review_text(self, client, prop):
        """物件删了，评价文字应当留下 —— 只失去关联（SET_NULL，不是 CASCADE）。"""
        thing = _create(name='空气炸锅', category='用', property=prop,
                        why_good='炸鸡很脆，值')
        prop.delete()

        thing.refresh_from_db()
        assert thing.property_id is None
        assert thing.why_good == '炸鸡很脆，值'

    def test_linked_name_is_downstream_on_list(self, client, prop):
        _create(name='空气炸锅', category='用', property=prop)
        row = client.get(THINGS_URL).data[0]
        assert row['linked_kind'] == 'property'
        assert row['linked_id'] == prop.id
        assert row['linked_name'] == '空气炸锅'
        # 列表**不**下发关联事实（那要对每条档案各算一次折旧）
        assert row['linked_facts'] is None

    def test_detail_carries_linked_facts(self, client, prop):
        thing = _create(name='空气炸锅', category='用', property=prop)
        row = client.get(f'{THINGS_URL}{thing.id}/').data
        assert row['linked_facts']['kind'] == 'property'
        assert row['linked_facts']['name'] == '空气炸锅'
        # 物件没填金额与日期 ⇒ 派生值是 None（**不是 0**）
        assert row['linked_facts']['age_months'] is None
        assert row['linked_facts']['current_value'] is None


# ──────────────────────────────────────────────────────────────
# 四、两个便捷性入口的接口形状
# ──────────────────────────────────────────────────────────────

class TestConvenienceEndpoints:
    def test_pending_reason_filter(self, client):
        """⭐ 待补理由出口：留空允许，但「留空」必须能被筛出来。"""
        _create(name='有理由', why_good='真的很好')
        _create(name='没理由', why_good='')
        _create(record_type='歹', name='歹物没理由', avoid_reason='')

        rows = client.get(f'{THINGS_URL}?pending_reason=1').data
        assert {r['name'] for r in rows} == {'没理由', '歹物没理由'}
        assert all(r['has_reason'] is False for r in rows)

    def test_link_candidates_shape_is_not_a_bare_array(self, client, prop):
        """⚠️ 这里**存在取数上限** ⇒ 必须把上限说出来，不能给裸数组。"""
        payload = client.get(f'{THINGS_URL}link_candidates/?search=空气').data
        assert set(payload) == {'rows', 'total', 'limit'}
        assert payload['total'] == 1
        assert payload['rows'][0]['name'] == '空气炸锅'
        assert payload['rows'][0]['source_label'] == '📦 物件资产'

    def test_link_candidates_empty_search_returns_nothing(self, client, prop):
        """空搜索词不给候选：那只会把两个池子全倒出来，而那不是「搜索」。"""
        payload = client.get(f'{THINGS_URL}link_candidates/').data
        assert payload['rows'] == []
        assert payload['total'] == 0

    def test_link_candidate_suggests_category(self, client, prop):
        """类别预填建议来自物件资产的类别名（「家电」→「用」）。"""
        payload = client.get(f'{THINGS_URL}link_candidates/?search=炸锅').data
        assert payload['rows'][0]['suggest_category'] == '用'
