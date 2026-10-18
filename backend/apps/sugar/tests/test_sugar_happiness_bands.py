"""小确幸快乐档位 —— constants.SUGAR_HAPPINESS_BANDS 的单一真源与下发出口。

这一轮的起因是「同一个分数在两处说两个词」：
录入弹窗写「非常开心」、列表写「很高兴」。根因是档位表被抄了四份
（后端 `_reward_label`、卡片里的 `happinessColor` / `happinessEmoji`、
弹窗里的 `happinessTexts`、以及一份没人用的 `REWARD_LABELS`）。
本文件钉住「只剩一份」这件事，防止以后又抄回去。
"""
import pytest
from rest_framework.test import APIClient

from apps.sugar.constants import (
    SUGAR_HAPPINESS_BANDS,
    SUGAR_HAPPINESS_MAX,
    SUGAR_HAPPINESS_MIN,
    resolve_happiness_band,
)
from apps.sugar.models import SugarRecord

RECORDS_URL = '/api/sugar/records/'
BANDS_URL = '/api/sugar/records/happiness_bands/'


def _post_sugar(level: float, title: str = '档位用例') -> dict:
    resp = APIClient().post(
        RECORDS_URL,
        {'title': title, 'time': '2025-01-07 12:00:00', 'level_of_happiness': level},
        format='json',
    )
    assert resp.status_code == 201, resp.data
    return resp.data


# ─── 一、档位边界（唯一真源本身） ───


@pytest.mark.parametrize(
    'level,expected',
    [
        (5, '小开心'),
        (7, '小开心'),      # 第 1 档上界（含）
        (7.1, '开心'),      # 跨过 7 就是第 2 档
        (10, '开心'),       # 第 2 档上界（含）
        (10.1, '很高兴'),
        (13, '很高兴'),
        (13.1, '超开心'),
        (16, '超开心'),
        (16.1, '幸福爆炸'),
        (20, '幸福爆炸'),   # 第 5 档上界（含）
    ],
)
def test_band_boundaries_are_inclusive_upper(level, expected) -> None:
    """每一档的 `max_level` 都是**含**的上界 —— 边界写错不会有任何报错，只会静默错档。"""
    assert resolve_happiness_band(level)['label'] == expected


@pytest.mark.parametrize('level,expected', [(3, '小开心'), (0, '小开心'), (25, '幸福爆炸'), (100, '幸福爆炸')])
def test_out_of_range_clamps_instead_of_raising(level, expected) -> None:
    """超出 5~20 时夹取到最近一档，**不抛异常、不返回 None**。

    库里真有 3.0 / 4.0（早于这条校验上线）。若这里留空，那几条记录在列表上
    会「有分数、没有词」，比夹取更难解释。
    """
    assert resolve_happiness_band(level)['label'] == expected


def test_bands_are_sorted_and_last_one_covers_max() -> None:
    """按升序排列，且最后一档的上界 == 允许的最大值。

    前端 `happinessBandOf` 是「第一个 max_level >= 分数」的线性查找 ——
    顺序一乱，整张表静默错档。
    """
    levels = [b['max_level'] for b in SUGAR_HAPPINESS_BANDS]
    assert levels == sorted(levels)
    assert len(set(levels)) == len(levels), '档位上界不许重复'
    assert levels[-1] == SUGAR_HAPPINESS_MAX
    assert len(SUGAR_HAPPINESS_BANDS) == 5


# ─── 二、接口下发（键名清单，新增 ⓘ 必配） ───


def test_bands_endpoint_key_contract() -> None:
    """顶层三个键齐备 —— 键名写错前端只会拿到 undefined 并静默不渲染。"""
    resp = APIClient().get(BANDS_URL)
    assert resp.status_code == 200
    assert set(resp.data.keys()) == {'min', 'max', 'bands'}
    assert resp.data['min'] == SUGAR_HAPPINESS_MIN
    assert resp.data['max'] == SUGAR_HAPPINESS_MAX
    assert len(resp.data['bands']) == len(SUGAR_HAPPINESS_BANDS)


def test_bands_endpoint_each_item_key_contract() -> None:
    """每条档位三个键齐备，且与常量逐字一致。"""
    bands = APIClient().get(BANDS_URL).data['bands']
    for item, source in zip(bands, SUGAR_HAPPINESS_BANDS):
        assert set(item.keys()) == {'max_level', 'label', 'color'}
        assert item['max_level'] == source['max_level']
        assert item['label'] == source['label']
        assert item['color'] == source['color']


def test_bands_endpoint_rejects_retired_keys() -> None:
    """反向钉子：被否决的键不许冒出来。

    `emoji` / `icon` 是这一轮**刻意删掉**的东西（卡片上不再有表情），
    `desc` / `min_level` 是旧 `REWARD_LABELS` 里那套已经作废的写法。
    任何一条偷偷回来，都意味着有人又在别处重建了第二份档位表。
    """
    bands = APIClient().get(BANDS_URL).data['bands']
    for item in bands:
        for retired in ('emoji', 'icon', 'desc', 'min_level', 'min', 'max_level_exclusive'):
            assert retired not in item, f'被否决的键回来了：{retired}'


# ─── 三、两个出口同源（这是本轮的核心） ───


@pytest.mark.django_db
def test_record_label_matches_bands_endpoint() -> None:
    """跨端点一致性：列表里每条的 `reward_label`，都等于档位表算出来的那个词。

    这条就是「同一个分数只能说一个词」本身 —— 两个出口同源才不会
    「录入时看到 A、存完变成 B」。
    """
    levels = [5, 7, 8, 10, 12, 13, 14, 16, 17, 20]
    for level in levels:
        _post_sugar(level, title=f'同源 {level}')

    bands = APIClient().get(BANDS_URL).data['bands']
    listed = APIClient().get(RECORDS_URL, {'page_size': 50}).data['results']

    assert len(listed) == len(levels)
    for row in listed:
        level = float(row['level_of_happiness'])
        expected = next(b['label'] for b in bands if level <= b['max_level'])
        assert row['reward_label'] == expected
        assert row['reward_label'] == resolve_happiness_band(level)['label']


@pytest.mark.django_db
def test_record_color_matches_bands_endpoint() -> None:
    """`reward_color` 同样随记录下发，且与档位表一致。

    卡片上的进度条去掉之后，档位颜色只剩分数文字这一处承载 ——
    若前端自己按分数算颜色，那就是第二份边界。
    """
    for level in (6, 9, 12, 15, 19):
        _post_sugar(level, title=f'颜色 {level}')

    bands = APIClient().get(BANDS_URL).data['bands']
    listed = APIClient().get(RECORDS_URL, {'page_size': 50}).data['results']

    for row in listed:
        level = float(row['level_of_happiness'])
        expected = next(b['color'] for b in bands if level <= b['max_level'])
        assert row['reward_color'] == expected


@pytest.mark.django_db
def test_record_color_is_a_hex_string() -> None:
    """下发的是可直接用于样式的 16 进制色串，不是色名或索引。"""
    data = _post_sugar(12)
    assert data['reward_color'].startswith('#')
    assert len(data['reward_color']) == 7


# ─── 四、校验边界在这一个文件里 ───


@pytest.mark.django_db
def test_validation_uses_the_shared_limits() -> None:
    """校验拒绝 <5 / >20，且边界值本身可存 —— 与常量同源。"""
    for level in (SUGAR_HAPPINESS_MIN, SUGAR_HAPPINESS_MAX):
        _post_sugar(level, title=f'边界 {level}')

    below = APIClient().post(
        RECORDS_URL,
        {'title': '太小', 'time': '2025-01-07 12:00:00', 'level_of_happiness': SUGAR_HAPPINESS_MIN - 1},
        format='json',
    )
    above = APIClient().post(
        RECORDS_URL,
        {'title': '太大', 'time': '2025-01-07 12:00:00', 'level_of_happiness': SUGAR_HAPPINESS_MAX + 1},
        format='json',
    )
    assert below.status_code == 400
    assert above.status_code == 400
    assert SugarRecord.objects.count() == 2
