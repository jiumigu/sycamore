# -*- coding: utf-8 -*-
"""toolkit_city_coordinate.name 带类型化改名脚本（含 dry-run）
用法:
  dry-run:  python city_rename_typed.py --dry-run
  实际执行: python city_rename_typed.py --apply
规则:
  - 直辖市: name = full_name (北京市)
  - 地级市: name = full_name 去省前缀 (合肥市); 含自治州/地区/盟的用短名+州/地区/盟 (大理州)
  - 自治州: 短名 + 州 (黔东南州)
  - 区/县/县级市/旗/自治旗/乡/镇: 从 full_name 剥离省级前缀 + 父级区划前缀 (福清市/同安区/景宁畲族自治县)
  - 景区/其他: 保持不变
"""
import os
from collections import Counter

from apps.toolkit.models import CityCoordinate

PROV_SUFFIXES = ['壮族自治区', '回族自治区', '维吾尔自治区', '自治区', '特别行政区', '省', '市']
PARENT_TYPES = {'直辖市', '地级市', '自治州', '地区', '盟'}
CHILD_SUFFIX = {
    '县级市': '市', '区': '区', '县': '县', '旗': '旗',
    '自治旗': '自治旗', '乡': '乡', '镇': '镇',
}
KEEP_TYPES = {'景区', '其他'}


def strip_prov(full, prov):
    if full.startswith(prov):
        rest = full[len(prov):]
        for s in PROV_SUFFIXES:
            if rest.startswith(s):
                return rest[len(s):]
        return rest
    return full


def main(apply: bool):
    rows = list(CityCoordinate.objects.all())

    # 父级区划段: (segment, province)
    parents = []
    for r in rows:
        if r.city_type in PARENT_TYPES:
            parents.append((strip_prov(r.full_name, r.province), r.province))
    parents.sort(key=lambda x: -len(x[0]))

    plan = {}  # id -> new_name
    unchanged = []
    for r in rows:
        old = r.name
        if r.city_type in KEEP_TYPES:
            plan[r.id] = old
            continue
        if r.city_type == '直辖市':
            plan[r.id] = r.full_name
        elif r.city_type == '地级市':
            seg = strip_prov(r.full_name, r.province)
            if '自治州' in seg:
                plan[r.id] = old + '州'
            elif '地区' in seg:
                plan[r.id] = old + '地区'
            elif '盟' in seg:
                plan[r.id] = old + '盟'
            else:
                plan[r.id] = seg
        elif r.city_type == '自治州':
            plan[r.id] = old + '州'
        elif r.city_type == '地区':
            plan[r.id] = old + '地区'
        elif r.city_type == '盟':
            plan[r.id] = old + '盟'
        else:
            # 子级行政区
            rest = strip_prov(r.full_name, r.province)
            new = None
            for seg, prov in parents:
                if prov == r.province and rest.startswith(seg):
                    remainder = rest[len(seg):]
                    if remainder:
                        new = remainder
                    break
            if new is None:
                new = old + CHILD_SUFFIX.get(r.city_type, '')
            plan[r.id] = new

    # 统计
    changed = [(r, plan[r.id]) for r in rows if plan[r.id] != r.name]
    collisions = {n: c for n, c in Counter(plan.values()).items() if c > 1}
    print(f'总行数: {len(rows)}  改名: {len(changed)}  保持: {len(rows) - len(changed)}')
    print(f'改名后重名条目数: {len(collisions)} (涉及行 {sum(collisions.values())})')
    print('\n-- 按类型抽样 --')
    seen = set()
    for r, new in changed:
        if r.city_type not in seen:
            seen.add(r.city_type)
            print(f'  [{r.city_type}] {r.name} -> {new}   ({r.full_name})')
    # 再多打几个重点样例
    for key in ('福清', '福鼎', '同安', '大理', '黔东南', '芳苑', '景宁', '阿里'):
        for r, new in changed:
            if r.name == key:
                print(f'  [抽查] [{r.city_type}] {r.name} -> {new}   ({r.full_name})')
    print('\n-- 重名 TOP10 --')
    for n, c in sorted(collisions.items(), key=lambda x: -x[1])[:10]:
        print(f'  {n}: {c}')
    unchanged_rows = [r for r in rows if plan[r.id] == r.name]
    print(f'\n-- 未改动行类型分布: {dict(Counter(r.city_type for r in unchanged_rows))}')
    for r in unchanged_rows[:12]:
        print(f'  [{r.city_type}] {r.name}  ({r.full_name})')

    if apply:
        # 逐条 UPDATE（只改 name 字段，不删任何行）
        n = 0
        for r, new in changed:
            CityCoordinate.objects.filter(id=r.id).update(name=new)
            n += 1
        print(f'\n已执行 UPDATE {n} 行')
    else:
        print('\n(dry-run 未写库，APPLY=1 执行)')


main(apply=os.environ.get('APPLY') == '1')
