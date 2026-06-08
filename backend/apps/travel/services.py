"""旅行服务层 — 地理编码 / 地图聚合 / 统计"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from django.db.models import Avg, Count, Q, Sum

from .models import TravelRecord

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
    # 反向查找 CITY_COORDS：找包含此城市的省份
    for prov, cities in CITY_COORDS.items():
        if city_name in cities:
            return prov

    return None


def get_coordinates(city_name: str) -> tuple[float, float] | None:
    """获取城市/地点坐标"""
    # 直接匹配
    for prov, cities in CITY_COORDS.items():
        if city_name in cities:
            return cities[city_name]
    # 区县 → 地级市
    if city_name in DISTRICT_TO_CITY:
        parent = DISTRICT_TO_CITY[city_name]
        for prov, cities in CITY_COORDS.items():
            if parent in cities:
                # 返回地级市坐标 + 小偏移避免重叠
                lat, lng = cities[parent]
                import random
                return (lat + random.uniform(-0.05, 0.05), lng + random.uniform(-0.05, 0.05))
    return None


# ── 地图数据聚合 ──────────────────────────────────────────────


class MapDataService:
    """地图展示数据聚合"""

    @staticmethod
    def get_map_data(year_from: int | None = None, year_to: int | None = None) -> dict[str, Any]:
        """获取省份热力图 + 城市气泡图数据"""
        qs = TravelRecord.objects.all()
        if year_from:
            qs = qs.filter(tyear__gte=year_from)
        if year_to:
            qs = qs.filter(tyear__lte=year_to)

        records = list(qs)

        # 省份热力聚合
        province_count: dict[str, int] = defaultdict(int)
        for r in records:
            prov = get_province(r.parentnode or '')
            if prov:
                province_count[prov] += 1

        heatmap = [
            {'province': prov, 'count': count, 'intensity': round(min(count / 10, 1), 2)}
            for prov, count in sorted(province_count.items(), key=lambda x: -x[1])
        ]

        # 城市气泡聚合（按 tname 去重聚合）
        city_agg: dict[str, dict[str, Any]] = {}
        # 排除非真实地名的关键词
        _skip_names = {'市本级', '本级', '市区', '城区'}
        for r in records:
            city = r.tname or ''
            if not city or city in _skip_names:
                continue
            if city not in city_agg:
                coord = get_coordinates(city)
                prov = get_province(r.parentnode or '')
                if not coord:
                    # 尝试用 parentnode 的坐标
                    coord = get_coordinates(r.parentnode or '')
                if not coord:
                    continue
                city_agg[city] = {
                    'city': city,
                    'province': prov or '',
                    'latitude': round(coord[0], 6),
                    'longitude': round(coord[1], 6),
                    'total_cost': 0,
                    'count': 0,
                    'ratings': [],
                    'years': [],
                    'has_cost': False,
                }
            entry = city_agg[city]
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
