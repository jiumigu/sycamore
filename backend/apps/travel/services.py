"""旅行服务层 — 地理编码 / 地图聚合 / 统计"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from django.db.models import Avg, Count, Q, Sum

from .models import TravelPlan, TravelRecord, TravelWish

# ── 中国城市坐标库（省份→城市→经纬度）────────────────────────────
# 覆盖主要城市 + 数据中已有的具体地点

CITY_COORDS: dict[str, dict[str, tuple[float, float]]] = {
    '北京市': {'北京市': (39.9042, 116.4074)},
    '天津市': {'天津市': (39.1252, 117.1908)},
    '上海市': {'上海市': (31.2304, 121.4737)},
    '重庆市': {'重庆市': (29.4316, 106.9123)},
    '河北省': {
        '石家庄市': (38.0428, 114.5149), '唐山市': (39.6309, 118.1802),
        '秦皇岛市': (39.9355, 119.5997), '邯郸市': (36.6257, 114.5391),
    },
    '山西省': {
        '太原市': (37.8706, 112.5489), '大同市': (40.0768, 113.3001),
        '长治市': (36.1954, 113.1163),
    },
    '内蒙古自治区': {
        '呼和浩特市': (40.8422, 111.7518), '包头市': (40.6574, 109.8403),
    },
    '辽宁省': {
        '沈阳市': (41.6772, 123.4631), '大连市': (38.9140, 121.6147),
        '鞍山市': (41.1075, 122.9948),
    },
    '吉林省': {
        '长春市': (43.8171, 125.3235), '吉林市': (43.8378, 126.5494),
    },
    '黑龙江省': {
        '哈尔滨市': (45.8038, 126.5350), '大庆市': (46.5891, 125.1038),
    },
    '江苏省': {
        '南京市': (32.0602, 118.7969), '无锡市': (31.4912, 120.3114),
        '徐州市': (34.2044, 117.2858), '常州市': (31.8112, 119.9743),
        '苏州市': (31.2990, 120.5853), '南通市': (31.9811, 120.8937),
        '连云港市': (34.5967, 119.2211), '淮安市': (33.6102, 119.0153),
        '盐城市': (33.3477, 120.1636), '扬州市': (32.3950, 119.4129),
        '镇江市': (32.1849, 119.4250), '泰州市': (32.4554, 119.9228),
        '宿迁市': (33.9632, 118.2755),
    },
    '浙江省': {
        '杭州市': (30.2741, 120.1551), '宁波市': (29.8683, 121.5440),
        '温州市': (28.0015, 120.6994), '嘉兴市': (30.7468, 120.7555),
        '湖州市': (30.8938, 120.0883), '绍兴市': (30.0300, 120.5802),
        '金华市': (29.0791, 119.6474), '舟山市': (29.9853, 122.2072),
        '台州市': (28.6564, 121.4208), '丽水市': (28.4672, 119.9228),
        '衢州市': (28.9359, 118.8742),
    },
    '安徽省': {
        '合肥市': (31.8206, 117.2272), '芜湖市': (31.3528, 118.4329),
        '黄山市': (29.7152, 118.3375),
    },
    '福建省': {
        '福州市': (26.0745, 119.2964), '厦门市': (24.4798, 118.0894),
        '莆田市': (25.4540, 119.0077), '三明市': (26.2638, 117.6389),
        '泉州市': (24.8741, 118.6760), '漳州市': (24.5130, 117.6474),
        '南平市': (26.6415, 118.1777), '龙岩市': (25.0751, 117.0172),
        '宁德市': (26.6657, 119.5480),
    },
    '江西省': {
        '南昌市': (28.6829, 115.8582), '景德镇市': (29.2689, 117.1784),
        '九江市': (29.6620, 116.0019),
    },
    '山东省': {
        '济南市': (36.6512, 117.1201), '青岛市': (36.0671, 120.3826),
        '烟台市': (37.4638, 121.4479), '威海市': (37.5134, 122.1218),
        '泰安市': (36.2009, 117.0875),
    },
    '河南省': {
        '郑州市': (34.7466, 113.6254), '开封市': (34.7973, 114.3073),
        '洛阳市': (34.6181, 112.4539),
    },
    '湖北省': {
        '武汉市': (30.5928, 114.3055), '宜昌市': (30.6921, 111.2864),
        '襄阳市': (32.0090, 112.1224),
    },
    '湖南省': {
        '长沙市': (28.2282, 112.9388), '株洲市': (27.8279, 113.1339),
        '张家界市': (29.1171, 110.4792), '湘潭市': (27.8296, 112.9441),
    },
    '广东省': {
        '广州市': (23.1291, 113.2644), '深圳市': (22.5431, 114.0579),
        '珠海市': (22.2710, 113.5770), '东莞市': (23.0208, 113.7518),
        '佛山市': (23.0219, 113.1219),
    },
    '广西壮族自治区': {
        '南宁市': (22.8170, 108.3665), '桂林市': (25.2736, 110.2900),
        '北海市': (21.4725, 109.1204),
    },
    '海南省': {'海口市': (20.0440, 110.2000), '三亚市': (18.2528, 109.5120)},
    '四川省': {
        '成都市': (30.5728, 104.0668), '绵阳市': (31.4675, 104.6790),
        '乐山市': (29.5520, 103.7654),
    },
    '贵州省': {
        '贵阳市': (26.6470, 106.6302), '遵义市': (27.7255, 106.9274),
    },
    '云南省': {
        '昆明市': (25.0389, 102.7183), '大理市': (25.5916, 100.2299),
        '丽江市': (26.8721, 100.2299),
    },
    '西藏自治区': {'拉萨市': (29.6500, 91.1000)},
    '陕西省': {
        '西安市': (34.2611, 108.9423), '咸阳市': (34.3295, 108.7093),
    },
    '甘肃省': {'兰州市': (36.0611, 103.8343), '天水市': (34.5810, 105.7250)},
    '青海省': {'西宁市': (36.6171, 101.7782)},
    '宁夏回族自治区': {'银川市': (38.4864, 106.2325)},
    '新疆维吾尔自治区': {'乌鲁木齐市': (43.8266, 87.6169)},
    '台湾省': {'台北市': (25.0330, 121.5654)},
    '香港特别行政区': {'香港': (22.3193, 114.1694)},
    '澳门特别行政区': {'澳门': (22.1987, 113.5439)},
}

# 区县→地级市 映射（数据中出现的具体地点）
DISTRICT_TO_CITY: dict[str, str] = {
    '苍南县': '温州市', '平阳市': '温州市', '乐清市': '温州市', '泰顺县': '温州市',
    '海宁市': '嘉兴市',
    '市本级': '湖州市',
    '寿宁县': '宁德市', '福鼎市': '宁德市',
    '长泰县': '漳州市', '芗城区': '漳州市',
    '平潭县': '福州市', '晋安区': '福州市', '福清市': '福州市',
    '义乌市': '金华市', '东阳市': '金华市',
}

# 城市→省份 反向映射（自动生成）
CITY_TO_PROVINCE: dict[str, str] = {}
for prov, cities in CITY_COORDS.items():
    for city in cities:
        CITY_TO_PROVINCE[city] = prov


def get_province(city_name: str) -> str | None:
    """根据城市名/省份名获取所属省份"""
    if not city_name:
        return None
    # 直接匹配（全称省份名如 "浙江省"）
    if city_name in CITY_TO_PROVINCE:
        return CITY_TO_PROVINCE[city_name]
    # 本身就是省份名（如 "浙江省" 也在键中，但以防漏）
    if city_name.endswith('省'):
        return city_name
    # 缩写省份名（如 "浙江" → "浙江省"）
    short_to_full = {
        '北京': '北京市', '天津': '天津市', '上海': '上海市', '重庆': '重庆市',
        '河北': '河北省', '山西': '山西省', '辽宁': '辽宁省', '吉林': '吉林省',
        '黑龙江': '黑龙江省', '江苏': '江苏省', '浙江': '浙江省', '安徽': '安徽省',
        '福建': '福建省', '江西': '江西省', '山东': '山东省', '河南': '河南省',
        '湖北': '湖北省', '湖南': '湖南省', '广东': '广东省', '海南': '海南省',
        '四川': '四川省', '贵州': '贵州省', '云南': '云南省', '陕西': '陕西省',
        '甘肃': '甘肃省', '青海': '青海省', '台湾': '台湾省',
        '内蒙古': '内蒙古自治区', '广西': '广西壮族自治区',
        '西藏': '西藏自治区', '宁夏': '宁夏回族自治区',
        '新疆': '新疆维吾尔自治区',
        '香港': '香港特别行政区', '澳门': '澳门特别行政区',
    }
    if city_name in short_to_full:
        return short_to_full[city_name]

    # 城市名当省份名（如 "宁德市" → "福建省"）
    # 反向查找硬编码表：找包含此城市的省份
    for prov, cities in CITY_COORDS.items():
        if city_name in cities:
            return prov

    # 权威坐标表兜底（城市名 → 所属省份）
    for row in _coord_index().get(city_name, []) or _coord_index().get(strip_city_suffix(city_name), []):
        if row[1]:
            return get_province(row[1]) or row[1]

    return None


# 名称后缀（长的优先，避免「地区」只剥掉「区」）
_NAME_SUFFIXES = ('自治州', '自治县', '地区', '市', '州', '盟', '县', '区')


def strip_city_suffix(name: str) -> str:
    """剥掉行政区划后缀：温州市→温州、大理州→大理、福鼎市→福鼎"""
    for suffix in _NAME_SUFFIXES:
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


# 「名称写法 → [(全称, 省份, lat, lng)]」索引，进程内缓存
_coord_index_cache: dict[str, list[tuple[str, str, float, float]]] | None = None


def _coord_index() -> dict[str, list[tuple[str, str, float, float]]]:
    """构建坐标索引（全称 + 去后缀简称）

    同一写法可能跨省同名（「连江」「三门」），所以值是列表，解析时按省份过滤。
    行政区 / 景区 行排在「其他」类 POI 之前，与 `resolve_wish_coords` 口径一致。
    """
    global _coord_index_cache
    if _coord_index_cache is not None:
        return _coord_index_cache

    from apps.toolkit.models import CityCoordinate

    idx: dict[str, list[tuple[str, str, float, float]]] = defaultdict(list)
    ordered = [
        CityCoordinate.objects.exclude(city_type='其他'),
        CityCoordinate.objects.filter(city_type='其他'),
    ]
    for qs in ordered:
        rows = qs.values_list('name', 'province', 'lat', 'lng').iterator()
        for name, province, lat, lng in rows:
            if not name:
                continue
            for key in {name, strip_city_suffix(name)}:
                idx[key].append((name, province or '', float(lat), float(lng)))
    _coord_index_cache = idx
    return idx


def reset_coord_index() -> None:
    """清空坐标索引缓存（坐标表变更后 / 测试建库后调用）"""
    global _coord_index_cache
    _coord_index_cache = None


def resolve_place(city_name: str, province: str = '') -> tuple[str, float, float] | None:
    """名称 → (规范名, lat, lng)

    规范名取自权威坐标表的 `name`，用于把「温州」/「温州市」这类同一地点的不同写法
    归并成一个气泡（否则地图上会出现两个重叠气泡）。

    ① 权威坐标表 `toolkit_city_coordinate`：全称 / 简称精确匹配，带省份时本省优先
       （避免跨省同名撞车，也让县级市落到自己的真实位置而非上级市中心）
    ② 硬编码 `CITY_COORDS` / `DISTRICT_TO_CITY` 兜底（坐标表缺行时的保险）
    """
    name = (city_name or '').strip()
    if name:
        idx = _coord_index()
        cands = idx.get(name) or idx.get(strip_city_suffix(name)) or []
        if cands:
            # 索引条目为 (全称, 省份, lat, lng)
            if province:
                same = [c for c in cands if c[1] == province]
                if len(same) == 1:
                    return (same[0][0], same[0][2], same[0][3])
            return (cands[0][0], cands[0][2], cands[0][3])

    for _prov, cities in CITY_COORDS.items():
        if name in cities:
            lat, lng = cities[name]
            return (name, lat, lng)
    if name in DISTRICT_TO_CITY:
        parent = DISTRICT_TO_CITY[name]
        for _prov, cities in CITY_COORDS.items():
            if parent in cities:
                lat, lng = cities[parent]
                return (name, lat, lng)
    return None


def get_coordinates(city_name: str, province: str = '') -> tuple[float, float] | None:
    """获取城市/地点坐标，返回 (lat, lng)"""
    hit = resolve_place(city_name, province)
    return (hit[1], hit[2]) if hit else None


# ── 地级市归属解析（地市级热力图用）──────────────────────────────
# 旅行记录里的 tname 粒度混杂（地级市「温州市」、县级市「福鼎市」、区县「泰顺县」），
# parentnode 有时是省、有时是地级市。要按地级市着色，必须先把每条记录归到地级市。

_PREFECTURE_TYPES = ('地级市', '自治州', '地区', '盟')
_MUNICIPALITIES = ('北京市', '天津市', '上海市', '重庆市')
_pref_index_cache: dict[str, str] | None = None


def _prefecture_index() -> dict[str, str]:
    """构建「名称 → 地级市名」索引：全称（温州市）+ 去后缀简称（温州/大理/喀什）。

    只含地级市 / 自治州 / 地区 / 盟。首次调用时查库，进程内缓存。
    """
    global _pref_index_cache
    if _pref_index_cache is not None:
        return _pref_index_cache

    from apps.toolkit.models import CityCoordinate

    idx: dict[str, str] = {}
    rows = CityCoordinate.objects.filter(city_type__in=_PREFECTURE_TYPES).values_list('name', flat=True)
    for name in rows:
        if not name:
            continue
        idx.setdefault(name, name)
        for suffix in ('市', '州', '地区', '盟'):
            if name.endswith(suffix):
                idx.setdefault(name[: -len(suffix)], name)
                break
    _pref_index_cache = idx
    return idx


def reset_prefecture_index() -> None:
    """清空地级市索引缓存（测试建库后或坐标表变更后调用）

    坐标索引同样依赖坐标表，一起清掉，避免测试间互相污染。
    """
    global _pref_index_cache
    _pref_index_cache = None
    reset_coord_index()


def resolve_prefecture(city: str, parent: str = '') -> str:
    """把一条记录的「城市 + 上级」归到地级市，返回地级市名（无法判定返回 ''）

    ① `city` 本身是地级市（「温州市」/「温州」）→ 直接用它
    ② `parent` 是地级市（city 为县级市/区县，如「福鼎市 ← 宁德市」）→ 用 parent
    ③ `parent` 是直辖市（「北京市」）→ 返回 `city`（地图上直辖市按区渲染）
    """
    idx = _prefecture_index()
    c = (city or '').strip()
    p = (parent or '').strip()
    if c in idx:
        return idx[c]
    if p in idx:
        return idx[p]
    if p in _MUNICIPALITIES:
        return c
    return ''


def heat_level(count: int) -> str:
    """到访次数 → 热力档位（与前端图例一致：偶尔 / 多次 / 频繁 / 深度游）"""
    if count >= 5:
        return '深度游'
    if count >= 3:
        return '频繁'
    if count >= 2:
        return '多次'
    return '偶尔'


# ── 地图数据聚合 ──────────────────────────────────────────────


class MapDataService:
    """地图展示数据聚合"""

    @staticmethod
    def get_map_data(year_from: int | None = None, year_to: int | None = None) -> dict[str, Any]:
        """获取地级市热力图 + 城市气泡图数据"""
        qs = TravelRecord.objects.all()
        if year_from:
            qs = qs.filter(tyear__gte=year_from)
        if year_to:
            qs = qs.filter(tyear__lte=year_to)

        records = list(qs)

        # 地级市热力聚合（粒度下沉：整省一个色块 → 每个地级市各自着色）
        # 同时记录「来源城市」明细：县级市/区县的到访会并入所属地级市，
        # 明细让前端 tooltip 能解释「这 6 次里含福鼎市 1 次」。
        pref_count: dict[str, int] = defaultdict(int)
        pref_src: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for r in records:
            pref = resolve_prefecture(r.tname or '', r.parentnode or '')
            if pref:
                pref_count[pref] += 1
                pref_src[pref][(r.tname or '').strip()] += 1

        heatmap = [
            {
                'name': name,
                'count': count,
                'level': heat_level(count),
                'sources': [
                    {'city': city, 'count': n}
                    for city, n in sorted(pref_src[name].items(), key=lambda kv: (-kv[1], kv[0]))
                ],
            }
            for name, count in sorted(pref_count.items(), key=lambda kv: (-kv[1], kv[0]))
        ]

        # 城市气泡聚合（原始写法 → 坐标表规范名，同地点只留一个气泡）
        city_agg: dict[str, dict[str, Any]] = {}
        alias: dict[str, str] = {}
        # 排除非真实地名的关键词
        _skip_names = {'市本级', '本级', '市区', '城区'}
        for r in records:
            city = r.tname or ''
            if not city or city in _skip_names:
                continue
            canon = alias.get(city)
            if canon is None:
                prov = get_province(r.parentnode or '') or ''
                # 先查城市自身的真实坐标（县级市/区县也有独立点位），再退回上级坐标
                hit = resolve_place(city, prov) or resolve_place(r.parentnode or '', prov)
                if not hit:
                    continue
                canon = hit[0] or city
                alias[city] = canon
                if canon not in city_agg:
                    city_agg[canon] = {
                        'city': canon,
                        'province': prov,
                        'latitude': round(hit[1], 6),
                        'longitude': round(hit[2], 6),
                        'total_cost': 0,
                        'count': 0,
                        'ratings': [],
                        'years': [],
                        'has_cost': False,
                    }
            entry = city_agg[canon]
            entry['count'] += 1
            if r.tcost:
                entry['total_cost'] += r.tcost
                entry['has_cost'] = True
            if r.rating:
                entry['ratings'].append(r.rating)
            if r.tyear:
                entry['years'].append(r.tyear)

        bubbles = []
        for city, entry in city_agg.items():
            avg_rating = round(sum(entry['ratings']) / len(entry['ratings']), 1) if entry['ratings'] else None
            # 气泡大小：根据花费 + 访问次数综合
            cost_factor = entry['total_cost'] / 500 if entry['total_cost'] and entry['total_cost'] > 0 else 0
            count_factor = entry['count'] * 5
            size = max(10, min(50, int(cost_factor * 20 + count_factor)))
            bubbles.append({
                'city': entry['city'],
                'province': entry['province'],
                'latitude': entry['latitude'],
                'longitude': entry['longitude'],
                'value': entry['total_cost'] if entry['has_cost'] else None,
                'size': size,
                'rating': avg_rating,
                'years': sorted(set(entry['years'])),
                'count': entry['count'],
            })

        # 总览
        all_cities = set(r.tname for r in records if r.tname)
        all_provinces = set(get_province(r.parentnode or '') for r in records)
        all_provinces.discard(None)

        return {
            'heatmap': heatmap,
            'heat_max': max(pref_count.values(), default=0),
            'bubbles': bubbles,
            'total': {
                'cities': len(all_cities),
                'provinces': len(all_provinces),
                'total_cost': sum(r.tcost or 0 for r in records),
            },
        }


class TravelStatsService:
    """旅行统计"""

    @staticmethod
    def get_stats(year_from: int | None = None, year_to: int | None = None) -> dict[str, Any]:
        """获取旅行统计总览"""
        qs = TravelRecord.objects.all()
        if year_from:
            qs = qs.filter(tyear__gte=year_from)
        if year_to:
            qs = qs.filter(tyear__lte=year_to)

        records = list(qs)

        all_cities = set(r.tname for r in records if r.tname)
        all_provinces = set()
        for r in records:
            prov = get_province(r.parentnode or '')
            if prov:
                all_provinces.add(prov)

        total_cost = sum(r.tcost or 0 for r in records)
        ratings = [r.rating for r in records if r.rating]
        avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else None
        total_days = sum(r.duration_days or 0 for r in records)

        # 每年趋势
        yearly: dict[int, dict[str, float | int]] = defaultdict(lambda: {'count': 0, 'cost': 0.0})
        for r in records:
            if r.tyear:
                yearly[r.tyear]['count'] += 1
                yearly[r.tyear]['cost'] += r.tcost or 0
        yearly_trend = [
            {'year': y, 'count': d['count'], 'cost': d['cost']}
            for y, d in sorted(yearly.items())
        ]

        # 省份分布
        prov_count: dict[str, int] = defaultdict(int)
        for r in records:
            prov = get_province(r.parentnode or '')
            if prov:
                prov_count[prov] += 1
        prov_distribution = [
            {'province': prov, 'count': count}
            for prov, count in sorted(prov_count.items(), key=lambda x: -x[1])
        ]

        # 年份范围
        years = sorted(set(r.tyear for r in records if r.tyear))

        return {
            'overview': {
                'province_count': len(all_provinces),
                'city_count': len(all_cities),
                'total_cost': total_cost,
                'avg_rating': avg_rating,
                'total_days': total_days,
                'record_count': len(records),
            },
            'yearly_trend': yearly_trend,
            'province_distribution': prov_distribution,
            'years': years,
        }


class TravelPlanService:
    """旅行计划业务逻辑"""

    @staticmethod
    def recalculate_total(plan: TravelPlan) -> float:
        """重新计算计划总费用（全部子项预估费用之和）"""
        total = plan.items.aggregate(total=Sum('estimate_cost'))['total'] or 0
        plan.total_estimate = total
        plan.save(update_fields=['total_estimate', 'updated_at'])
        return float(total)

    @staticmethod
    def get_stats() -> dict[str, Any]:
        """统计所有计划费用"""
        plans = TravelPlan.objects.all()
        total_estimate = plans.aggregate(total=Sum('total_estimate'))['total'] or 0
        completed_plans = plans.filter(status='已完成').count()
        return {
            'total_plans': plans.count(),
            'total_estimate': float(total_estimate),
            'completed_plans': completed_plans,
        }


# ── 行程日志（打卡 → 记录 的中间层）────────────────────────────

# 归类为「吃」的心愿分类（与 views.WISH_FOOD_CATEGORIES 同口径）
FOOD_CATEGORIES = {'美食', '夜市', '路线'}

_PLACE_SUFFIXES = ('市', '地区', '自治州', '盟', '特别行政区')


def norm_place(city: str | None, province: str | None) -> str:
    """地点名：优先城市，缺省回落到省份"""
    place = (city or '').strip()
    if not place:
        place = (province or '').strip()
    return place


def place_key(city: str | None, province: str | None) -> str:
    """分组键：剥离行政后缀，兼容「南京」与「南京市」写成两组

    注意不剥离单字「州」，避免「杭州」被截断。
    """
    place = norm_place(city, province)
    for suffix in _PLACE_SUFFIXES:
        if place.endswith(suffix) and len(place) > len(suffix):
            return place[: -len(suffix)]
    return place


class TripLogService:
    """行程日志 — 把已打卡心愿按「日期 + 地点」聚合为一天一张卡

    设计意图：打卡不直接写 travel_list_info（历史表 managed=False，且一次行程
    会散成十几条足迹、污染地图热力与年份趋势），而是先聚合为可读日志，
    需要沉淀时再显式生成一条旅行记录。
    """

    @staticmethod
    def build(
        user_id: int = 1,
        date_from=None,
        date_to=None,
        plan_id: int | None = None,
        city: str | None = None,
    ) -> dict[str, Any]:
        qs = TravelWish.objects.filter(
            user_id=user_id, status='已打卡', visited_at__isnull=False,
        )
        if date_from:
            qs = qs.filter(visited_at__gte=date_from)
        if date_to:
            qs = qs.filter(visited_at__lte=date_to)
        if plan_id:
            qs = qs.filter(visit_plan_id=plan_id)
        if city:
            qs = qs.filter(city__icontains=city)

        wishes = list(qs.order_by('-visited_at', 'category', 'name'))

        groups: dict[tuple, dict[str, Any]] = {}
        for w in wishes:
            key = (w.visited_at, place_key(w.city, w.province))
            g = groups.get(key)
            if g is None:
                g = groups[key] = {
                    'date': w.visited_at,
                    'city': norm_place(w.city, w.province),
                    'province': w.province or '',
                    'district': w.district or '',
                    'items': [],
                    'record_tid': None,
                    'plan_ids': [],
                }
            g['items'].append({
                'id': w.id,
                'name': w.name,
                'category': w.category,
                'is_food': w.category in FOOD_CATEGORIES,
                'rating': w.visit_rating,
                'notes': w.visit_notes or '',
                'worth_revisit': bool(w.worth_revisit),
                'consolidated': w.visit_record_id is not None,
                'plan_id': w.visit_plan_id,
                'lng': w.lng,
                'lat': w.lat,
            })
            if w.visit_record_id and g['record_tid'] is None:
                g['record_tid'] = w.visit_record_id
            if w.visit_plan_id and w.visit_plan_id not in g['plan_ids']:
                g['plan_ids'].append(w.visit_plan_id)

        # 批量补足迹与行程名称，避免逐条查询
        record_ids = {g['record_tid'] for g in groups.values() if g['record_tid']}
        records = {r.tid: r for r in TravelRecord.objects.filter(tid__in=record_ids)} if record_ids else {}
        plan_ids = {pid for g in groups.values() for pid in g['plan_ids']}
        plans = {p.id: p for p in TravelPlan.objects.filter(id__in=plan_ids)} if plan_ids else {}

        days = []
        for g in groups.values():
            items = g['items']
            rec = records.get(g['record_tid']) if g['record_tid'] else None
            ratings = [i['rating'] for i in items if i['rating']]
            days.append({
                'date': g['date'].isoformat(),
                'city': g['city'],
                'province': g['province'],
                'district': g['district'],
                'items': items,
                'item_count': len(items),
                'summary': '、'.join(i['name'] for i in items),
                'avg_rating': round(sum(ratings) / len(ratings), 1) if ratings else None,
                'worth_count': sum(1 for i in items if i['worth_revisit']),
                'consolidated': rec is not None,
                'record': None if rec is None else {
                    'tid': rec.tid,
                    'tcost': rec.tcost,
                    'rating': rec.rating,
                    'companions': rec.companions or '',
                    'duration_days': rec.duration_days,
                    'tremark': rec.tremark or '',
                },
                'plans': [
                    {'id': pid, 'name': plans[pid].name}
                    for pid in g['plan_ids'] if pid in plans
                ],
            })

        days.sort(key=lambda d: d['date'], reverse=True)
        return {
            'days': days,
            'total_days': len(days),
            'total_items': sum(d['item_count'] for d in days),
            'pending_days': sum(1 for d in days if not d['consolidated']),
        }
