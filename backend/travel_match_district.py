"""
旅行心愿 district（区县）回填 — 用 toolkit_city_coordinate 的区/县坐标做最近邻匹配。

用法（经 manage.py shell 执行）:
  dry-run:  manage.py shell < travel_match_district.py
  实际执行: APPLY=1 manage.py shell < travel_match_district.py

规则:
  - 仅处理有经纬度且 district 为空的心愿
  - 候选 = city_type in ('区','县','县级市') 的坐标点
  - 最近邻 ≤ 60km 才回填（心能有城市坐标的会落到市中心所在区，属预期）
  - 同时补齐缺失的 province（区县行的 province 字段）
"""
import math
import os
import sys

from apps.toolkit.models import CityCoordinate
from apps.travel.models import TravelWish

APPLY = os.environ.get('APPLY') == '1'
MAX_KM = 60


def haversine(lng1, lat1, lng2, lat2):
    r = 6371
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


counties = list(
    CityCoordinate.objects.filter(city_type__in=['区', '县', '县级市']).exclude(lng=None)
)
print(f'候选区县点: {len(counties)}')

wishes = TravelWish.objects.filter(lng__isnull=False).exclude(lng=None)
todo = [w for w in wishes if not w.district]
print(f'待匹配心愿: {len(todo)} / 共 {wishes.count()} 条有坐标')

updates = []
missing = []
for w in todo:
    best, best_d = None, 1e9
    for c in counties:
        d = haversine(w.lng, w.lat, c.lng, c.lat)
        if d < best_d:
            best, best_d = c, d
    if best is not None and best_d <= MAX_KM:
        province = w.province or best.province
        updates.append((w.id, w.name, best.name, best_d, province))
    else:
        missing.append((w.name, w.city, round(best_d) if best else -1))

print(f'\n可回填: {len(updates)}  超出 {MAX_KM}km: {len(missing)}')
print('\n-- 回填预览(前 15) --')
for wid, name, dist, km, prov in updates[:15]:
    print(f'  {name} → {dist} ({km:.0f}km) [{prov}]')
print('\n-- 超距(前 10) --')
for name, city, km in missing[:10]:
    print(f'  {name} ({city}) 最近 {km}km')

if APPLY:
    by_id = {w.id: w for w in todo}
    for wid, _name, dist, _km, prov in updates:
        w = by_id[wid]
        w.district = dist
        if not w.province:
            w.province = prov
    TravelWish.objects.bulk_update([by_id[wid] for wid, *_ in updates], ['district', 'province'])
    print(f'\n✅ 已回填 {len(updates)} 条 district')
else:
    print('\n(dry-run 未写库，APPLY=1 执行)')
