# -*- coding: utf-8 -*-
"""旅行足迹地图：地级市热力汇总测试

背景：热力原先按「省」着色（整省一个色块），粒度太粗；现下沉到地级市。
记录里的 `tname` 粒度混杂（地级市/县级市/区县），`parentnode` 有时是省、
有时是地级市，所以要把每条记录归到地级市再聚合。
"""
import pytest
from rest_framework.test import APIClient

from apps.toolkit.models import CityCoordinate
from apps.travel.models import TravelRecord
from apps.travel.services import (
    MapDataService,
    get_coordinates,
    heat_level,
    reset_coord_index,
    reset_prefecture_index,
    resolve_place,
    resolve_prefecture,
)

MAP_URL = '/api/travel/map/data/'

# 测试库的 toolkit_city_coordinate 是空表，按需造最小地级市样本
PREFECTURES = [
    ('温州市', '浙江省', '地级市'),
    ('宁德市', '福建省', '地级市'),
    ('金华市', '浙江省', '地级市'),
    ('大理州', '云南省', '地级市'),
    ('喀什地区', '新疆维吾尔自治区', '地区'),
]
MUNICIPALITIES = [('北京市', '北京市', '直辖市')]


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def prefectures(db):
    """播种地级市样本并清空索引缓存（缓存是进程级的，必须显式失效）"""
    for name, prov, ctype in PREFECTURES + MUNICIPALITIES:
        CityCoordinate.objects.create(
            name=name, full_name=f'{prov}{name}', province=prov, city_type=ctype,
            lng=120.0, lat=28.0,
        )
    reset_prefecture_index()
    yield
    reset_prefecture_index()


def _rec(city, parent, year=2024, cost=0, rating=None):
    return TravelRecord.objects.create(
        tname=city, parentnode=parent, tyear=year, tcost=cost, rating=rating,
    )


# ===== 归属解析 =====

def test_resolve_prefecture_by_full_and_short_name(prefectures):
    """① tname 本身就是地级市（全称或简称）"""
    assert resolve_prefecture('温州市', '浙江省') == '温州市'
    assert resolve_prefecture('温州', '浙江') == '温州市'
    assert resolve_prefecture('大理', '云南') == '大理州'
    assert resolve_prefecture('喀什', '新疆') == '喀什地区'


def test_resolve_prefecture_from_parent(prefectures):
    """② tname 是县级市/区县 → 归到 parentnode 的地级市"""
    assert resolve_prefecture('福鼎市', '宁德市') == '宁德市'
    assert resolve_prefecture('泰顺县', '温州市') == '温州市'
    assert resolve_prefecture('义乌市', '金华市') == '金华市'


def test_resolve_prefecture_municipality_keeps_district(prefectures):
    """③ 直辖市：地图按区渲染，保留区名而不是塌成「北京市」"""
    assert resolve_prefecture('朝阳区', '北京市') == '朝阳区'
    assert resolve_prefecture('北京市', '北京市') == '北京市'


def test_resolve_prefecture_unknown_returns_empty(prefectures):
    """④ 无从判定的（parent 只是省且 city 不是地级市）返回空串，由调用方跳过"""
    assert resolve_prefecture('某某县', '某省') == ''
    assert resolve_prefecture('', '') == ''
    assert resolve_prefecture('三沙市', '海南省') == ''


# ===== 档位映射 =====

@pytest.mark.parametrize('count,expected', [
    (1, '偶尔'), (2, '多次'), (3, '频繁'), (4, '频繁'), (5, '深度游'), (12, '深度游'),
])
def test_heat_level(count, expected):
    assert heat_level(count) == expected


# ===== 汇总 =====

def test_map_data_aggregates_by_prefecture(prefectures):
    """县级市与地级市混写时，应合并到同一个地级市计数"""
    _rec('温州市', '浙江省')
    _rec('温州', '浙江')
    _rec('泰顺县', '温州市')       # 县级 → 温州市
    _rec('福鼎市', '宁德市')       # 县级市 → 宁德市
    _rec('宁德', '福建')

    data = MapDataService.get_map_data()
    heat = {h['name']: h for h in data['heatmap']}

    assert heat['温州市']['count'] == 3
    assert heat['温州市']['level'] == '频繁'
    assert heat['宁德市']['count'] == 2
    assert heat['宁德市']['level'] == '多次'
    assert data['heat_max'] == 3


def test_map_data_heatmap_sorted_desc_and_has_level(prefectures):
    """热力按次数倒序，且每项带档位"""
    for _ in range(5):
        _rec('温州市', '浙江省')
    _rec('宁德市', '福建省')

    data = MapDataService.get_map_data()
    names = [h['name'] for h in data['heatmap']]
    assert names == ['温州市', '宁德市']
    assert data['heatmap'][0]['level'] == '深度游'
    assert data['heatmap'][1]['level'] == '偶尔'
    assert 'province' not in data['heatmap'][0]      # 旧字段已移除
    assert 'intensity' not in data['heatmap'][0]


def test_map_data_year_filter(prefectures):
    """年份过滤仍生效"""
    _rec('温州市', '浙江省', year=2023)
    _rec('宁德市', '福建省', year=2025)

    data = MapDataService.get_map_data(year_from=2025)
    assert [h['name'] for h in data['heatmap']] == ['宁德市']


def test_map_data_empty(prefectures):
    """无记录时返回空热力且 heat_max 为 0"""
    data = MapDataService.get_map_data()
    assert data['heatmap'] == []
    assert data['heat_max'] == 0


# ===== 接口 =====

def test_map_data_api_returns_prefecture_names(client, prefectures):
    _rec('温州市', '浙江省')
    _rec('福鼎市', '宁德市')

    res = client.get(MAP_URL)
    assert res.status_code == 200
    heat = {h['name']: h['count'] for h in res.data['heatmap']}
    assert heat == {'温州市': 1, '宁德市': 1}
    assert res.data['heat_max'] == 1


# ===== 来源明细（解释「福鼎市去哪了」）=====

def test_heatmap_keeps_source_breakdown(prefectures):
    """县级市/区县的到访并入所属地级市，同时保留来源明细供 tooltip 展示"""
    _rec('宁德', '福建')
    _rec('福鼎市', '宁德市')
    _rec('寿宁县', '宁德市')

    heat = {h['name']: h for h in MapDataService.get_map_data()['heatmap']}
    entry = heat['宁德市']
    assert entry['count'] == 3
    assert {s['city']: s['count'] for s in entry['sources']} == {
        '宁德': 1, '福鼎市': 1, '寿宁县': 1,
    }


# ===== 气泡点位（权威坐标表驱动）=====

COORDS = [
    ('温州市', '浙江省', '地级市', 120.70, 28.00),
    ('宁德市', '福建省', '地级市', 119.55, 26.67),
    ('福鼎市', '福建省', '县级市', 120.22, 27.32),
    ('朝阳区', '北京市', '市辖区', 116.44, 39.92),
    ('朝阳区', '吉林省', '市辖区', 125.29, 43.83),
]


@pytest.fixture
def coords(db):
    """坐标表样本：地级市 + 县级市（有独立点位）+ 跨省同名"""
    for name, prov, ctype, lng, lat in COORDS:
        CityCoordinate.objects.create(
            name=name, province=prov, city_type=ctype, lng=lng, lat=lat,
        )
    reset_prefecture_index()
    yield
    reset_prefecture_index()


def test_resolve_place_uses_own_point_for_county_city(coords):
    """县级市有独立点位时用自己的坐标，而不是塌到上级市中心"""
    assert resolve_place('福鼎市', '福建省') == ('福鼎市', 27.32, 120.22)
    assert resolve_place('宁德市', '福建省') == ('宁德市', 26.67, 119.55)


def test_resolve_place_short_name_maps_to_canonical(coords):
    """简称归一到坐标表规范名（「温州」→「温州市」）"""
    assert resolve_place('温州')[0] == '温州市'
    assert resolve_place('宁德')[0] == '宁德市'


def test_resolve_place_is_province_aware(coords):
    """短名跨省：「朝阳」在北京与吉林各有一个区，按省份取对的那个"""
    assert resolve_place('朝阳', '北京市')[1] == 39.92
    assert resolve_place('朝阳', '吉林省')[1] == 43.83


def test_get_coordinates_falls_back_to_hardcoded(db):
    """坐标表没有的行，仍由硬编码表兜底（历史行为不回归）"""
    reset_coord_index()
    assert get_coordinates('北京市') == (39.9042, 116.4074)


def test_bubbles_merge_same_place_written_differently(coords):
    """「温州」与「温州市」是同一地点，只出一个气泡（否则两点重叠）"""
    _rec('温州', '浙江')
    _rec('温州市', '浙江省')

    bubbles = MapDataService.get_map_data()['bubbles']
    assert [b['city'] for b in bubbles] == ['温州市']
    assert bubbles[0]['count'] == 2


def test_bubbles_keep_county_city_on_its_own_point(coords):
    """福鼎市气泡落在自身坐标上，与宁德市区分开"""
    _rec('福鼎市', '宁德市')
    _rec('宁德市', '福建省')

    bubbles = {b['city']: b for b in MapDataService.get_map_data()['bubbles']}
    assert bubbles['福鼎市']['latitude'] == 27.32
    assert bubbles['宁德市']['latitude'] == 26.67
