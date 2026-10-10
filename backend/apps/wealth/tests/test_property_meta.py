"""物件资产 · 口径元信息（v3.60.0）

口径元信息是「后端算、前端只渲染」这条链路的末端：前端的气泡组件按固定结构渲染，
`key` 对不上就**静默不渲染** —— 界面上什么都不会出错，只是那行说明不见了。
换句话说，键名写错在界面上看不出来（项目硬坑⑪）。

所以这一份的核心是**键名清单**用例：把前端真正要的那几个键逐个念出来。
顺带钉住两条反向事实：
    ① 本模块**没有**体型档 / 价值档 / 重要度这一类字段（用户问过，答了「不加」）；
    ② 本模块**不设**绝对判定线（`bands` 恒为空数组）。
"""

from datetime import date

import pytest
from rest_framework.test import APIClient

from apps.wealth.constants import (
    PROPERTY_CONDITION_CHOICES,
    PROPERTY_METRIC_NOTES,
    PROPERTY_STATUS_CHOICES,
)
from apps.wealth.services import property_calc as calc

META = '/api/wealth/property/meta/'

# 🔴 前端要用的键名，**逐个念出来**
# 这几个键分别对应：首屏四卡（前四个）+ 明细行的净值列 + 「已用与计划」列
# + 表单年限那格 + 状况那列。少一个，对应的那一处就是空白，且不报错。
REQUIRED_METRIC_KEYS = frozenset({
    'in_use_count',       # 卡①：在用件数
    'total_amount',       # 卡②：原值合计
    'in_use_net_value',   # 卡③：在用净值合计
    'scrapped_count',     # 卡④：已报废
    'current_value',      # 明细行「现值」列
    'age_vs_lifespan',    # 明细行「已用 / 计划」列
    'lifespan_months',    # 表单「计划使用年限」那格的说明
    'condition',          # 状况列
})

# 体型 / 价值 / 重要度 —— 这三把尺子**明确不加**（用户问过，答了不加，见设计文档 §4.3）
BANNED_KEYS = frozenset({
    'size_class', 'size', 'value_tier', 'tier', 'importance', 'is_essential',
    'big_item', 'high_value', 'importance_level', 'grade', 'level',
})


def _codes_the_calc_can_emit() -> set[str]:
    """从计算引擎里**自动**收集原因码 —— 不写第二份清单。

    写死一份的话，以后加了一个原因码却忘了加文案，用例还是绿的，
    而界面上那个「—」点开就是一串英文码。
    """
    return {value for name, value in vars(calc).items() if name.startswith('ISSUE_')}


@pytest.mark.django_db
class TestMetaKeys:
    """键名写错在界面上看不出来 ⇒ 必须有一条用例把它念出来"""

    def test_endpoint_shape(self):
        api = APIClient()
        body = api.get(META).json()
        assert set(body) == {
            'statuses', 'conditions', 'metric_meta', 'issue_labels',
            'not_in_net_worth_note', 'subtitle',
        }

    def test_every_required_metric_key_is_present(self):
        api = APIClient()
        keys = {m['key'] for m in api.get(META).json()['metric_meta']}
        missing = REQUIRED_METRIC_KEYS - keys
        assert not missing, f'metric_meta 少了前端要用的键：{sorted(missing)}'

    def test_metric_meta_matches_the_single_source(self):
        """元信息就是 constants 里那份，不许多、不许少、顺序也别变"""
        api = APIClient()
        rows = api.get(META).json()['metric_meta']
        assert [m['key'] for m in rows] == list(PROPERTY_METRIC_NOTES)

    def test_metric_meta_is_a_bare_array(self):
        """气泡组件按数组消费 —— 被包成 `{count, results}` 就是一个气泡都不出来"""
        api = APIClient()
        rows = api.get(META).json()['metric_meta']
        assert isinstance(rows, list)
        assert len(rows) == len(PROPERTY_METRIC_NOTES)

    def test_every_bubble_has_the_full_structure(self):
        """字段缺一个就渲染不出来（同硬坑⑪）"""
        api = APIClient()
        for row in api.get(META).json()['metric_meta']:
            assert set(row) == {
                'key', 'label', 'unit', 'direction', 'formula', 'note', 'bands',
            }, f'{row["key"]} 结构不完整'
            assert row['label'] and row['note']
            assert isinstance(row['note'], list) and row['note']

    def test_options_come_from_the_single_source(self):
        """下拉选项不在前端硬编码 —— 枚举只有一个来源"""
        api = APIClient()
        body = api.get(META).json()
        assert [(o['value'], o['label']) for o in body['statuses']] == list(PROPERTY_STATUS_CHOICES)
        assert [(o['value'], o['label']) for o in body['conditions']] == list(PROPERTY_CONDITION_CHOICES)


@pytest.mark.django_db
class TestIssueLabels:
    def test_every_code_has_a_human_sentence(self):
        """点开那个「—」看到的必须是中文句子，不能是一串原因码"""
        api = APIClient()
        labels = api.get(META).json()['issue_labels']
        codes = _codes_the_calc_can_emit()
        assert codes, '没扫到原因码 —— 用例本身失效了'
        assert codes <= set(labels), f'这些原因码没有文案：{sorted(codes - set(labels))}'

    def test_labels_are_chinese(self):
        api = APIClient()
        for code, label in api.get(META).json()['issue_labels'].items():
            assert any('\u4e00' <= ch <= '\u9fff' for ch in label), f'{code} 的文案不是中文'


@pytest.mark.django_db
class TestNoSecondRuler:
    """反向钉子：本模块**不加**体型档 / 价值档 / 重要度。

    「大物件 / 高价值物件 / 小玩意儿」这三个词跨了三把尺子 ——
    大小是体积、高低是金额、小玩意儿是语义，硬塞进一个下拉框会让类别
    变成一锅乱炖；而类别上还挂着「默认年限预填」，混装会把预填变成**软兜底**。
    想要「大 / 贵」，用列表排序；那两件事都不需要落库。
    """

    def test_meta_exposes_no_tier_field(self):
        api = APIClient()
        body = api.get(META).json()
        found = set()

        def walk(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    if key in BANNED_KEYS:
                        found.add(key)
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(body)
        assert not found, f'元信息里出现了不该有的档位字段：{sorted(found)}'

    def test_the_model_has_no_tier_column(self):
        """不落库的字段，连列都不该有 —— 派生值不落库是同一把尺子"""
        from apps.wealth.models import WealthProperty, WealthPropertyCategory

        for model in (WealthProperty, WealthPropertyCategory):
            fields = {f.name for f in model._meta.get_fields()}
            assert not (fields & BANNED_KEYS), (
                f'{model.__name__} 出现了档位列：{sorted(fields & BANNED_KEYS)}'
            )


@pytest.mark.django_db
class TestTheNoteExplainsTheZeroedValue:
    """🔴 口径订正（2026-09-26）之后，气泡里的**说法**也必须跟着改。

    这一条钉的不是代码、是话：口径改了而界面上的解释没改，
    用户就会照旧以为「坏不坏都不影响数字」，然后把那个净值当成准数用 ——
    这比数字本身算错更难发现，因为解释看起来一直都对。
    """

    def test_net_value_note_mentions_the_broken_rule(self):
        api = APIClient()
        rows = {m['key']: m for m in api.get(META).json()['metric_meta']}
        text = ' '.join(rows['in_use_net_value']['note'])
        assert '损坏' in text, '净值气泡必须说清损坏件怎么算'
        assert '0' in text, '净值气泡必须说出「按 0 计」'
        assert '件数' in text, '必须同时说明件数照常算，否则会被读成「整件不算了」'

    def test_no_note_still_claims_condition_affects_nothing(self):
        """旧口径的措辞必须清干净 —— 留着就是一句「说得通、但已经假了」的解释。"""
        api = APIClient()
        rows = api.get(META).json()['metric_meta']
        banned = ('不影响任何数字', '完全不参与', '不参与任何算法', '不影响任何算法')
        for row in rows:
            blob = f"{row['formula']} {' '.join(row['note'])}"
            for phrase in banned:
                assert phrase not in blob, (
                    f'{row["key"]} 的气泡里还留着旧口径的说法：{phrase}'
                )

    def test_condition_is_exposed_but_has_no_thresholds(self):
        """状况是枚举、不是分数 —— 它没有「几分算坏」这种事"""
        api = APIClient()
        body = api.get(META).json()
        row = next(m for m in body['metric_meta'] if m['key'] == 'condition')
        assert row['bands'] == []
        assert [o['value'] for o in body['conditions']] == ['normal', 'broken']


@pytest.mark.django_db
class TestNoAbsoluteThresholds:
    """本模块**不设绝对判定线** —— `bands` 恒为空数组。

    「计划用 8 年、已经用了 10 年 2 月」不是一条判好坏的线，它只是两个数并排摆着。
    硬编一条线只会让人以为「超过 X 年就该换」，而那个 X 系统并不知道。
    """

    def test_every_band_list_is_empty(self):
        api = APIClient()
        for row in api.get(META).json()['metric_meta']:
            assert row['bands'] == [], f'{row["key"]} 凭空多了判定线'

    def test_direction_is_always_neutral(self):
        """净值高不代表好，超期也不代表坏 —— 这个模块不据方向上下色"""
        api = APIClient()
        for row in api.get(META).json()['metric_meta']:
            assert row['direction'] == 'neutral', f'{row["key"]} 带上了方向'

    def test_overdue_does_not_come_with_a_verdict(self):
        """把一台超期空调扫一遍 —— 数字里只该有事实，不该有结论

        超期在数据面上的痕迹只有两处：`is_overdue` 为真、`overdue_months` 为正。
        没有「建议更换」「健康度」「风险等级」这类字段。
        """
        api = APIClient()
        category = api.post('/api/wealth/property/categories/', {'name': '家电'}, format='json').json()
        row = api.post('/api/wealth/property/items/', {
            'category_id': category['id'],
            'name': '超期空调',
            'purchase_amount': '3000.00',
            'purchase_date': date(2016, 6, 1).isoformat(),
            'lifespan_months': 96,
            'status': 'in_use',
            'condition': 'normal',
        }, format='json').json()

        assert row['is_overdue'] is True
        assert row['overdue_months'] > 0
        assert row['remaining_months'] < 0            # 负多少就是超期多少
        assert row['current_value'] == '0.00'         # 早折完了 —— 0 是结论，不是「算不出」
        assert [k for k in row if 'suggest' in k or 'health' in k or 'risk' in k] == []


@pytest.mark.django_db
class TestPageCopyHasOneSource:
    def test_the_net_worth_disclaimer_is_explicit(self):
        """这句说明必须来自后端 —— 前端再写一份就会出现两处措辞"""
        api = APIClient()
        body = api.get(META).json()
        assert '净资产' in body['not_in_net_worth_note']
        assert body['subtitle']
