import csv
import io
from collections import defaultdict
from datetime import datetime, date

from django.db import models, transaction
from django.db.models import Avg, Count, Sum
from django.utils import timezone

from .constants import (
    ACTIVITY_TYPE_COLORS,
    ATTRIBUTION_COLORS,
    ATTRIBUTION_ORDER,
    DEFAULT_FALLBACK_ATTR,
    LEGACY_FOUR_TO_L2,
    TASK_CATEGORY_MAPPING,
    TASK_TO_L2,
)
from .models import OneDayPage, TaskMeta, TemporalTask


def resolve_task_meta(task_names: list[str]) -> dict:
    """task_name(L3) → {activity_type(L2), is_unclassified}

    注：v0.3 语义订正后，L1 = 归因（见 resolve_attribution），不再有「自建聚合分组」层。
    """
    if not task_names:
        return {}
    rows = TaskMeta.objects.filter(task_name__in=task_names)
    out = {}
    for r in rows:
        out[r.task_name] = {
            'activity_type': r.activity_type,
            'is_unclassified': r.activity_type == '未归类',
        }
    return out


def resolve_attribution(task_names: list[str]) -> dict:
    """task_name(L3) → 价值归因（L1：投向/维持/外部/流失）

    优先级：redemption_attr_rule(override) > temporal_task_meta.default_attribution > 兜底'投向'
    """
    if not task_names:
        return {}
    from apps.redemption.models import RedemptionAttrRule

    rules = list(RedemptionAttrRule.objects.filter(is_active=True))
    meta_map = {m.task_name: m for m in TaskMeta.objects.filter(task_name__in=task_names)}

    def best(task_name: str, activity_type: str | None):
        cand = [r for r in rules if
                (r.match_field == 'task_name' and r.match_value == task_name) or
                (r.match_field == 'activity_type' and r.match_value == (activity_type or ''))]
        if not cand:
            return None
        cand.sort(key=lambda r: r.priority, reverse=True)
        return cand[0].attribution

    out = {}
    for tn in task_names:
        m = meta_map.get(tn)
        if not m:
            out[tn] = DEFAULT_FALLBACK_ATTR
            continue
        override = best(tn, m.activity_type)
        out[tn] = override or m.default_attribution or DEFAULT_FALLBACK_ATTR
    return out


def _ensure_task_meta(task_names: list[str]) -> int:
    """为新出现的 task_name 建 TaskMeta；命中 TASK_TO_L2 则带活动类型+归因，否则进未归类桶。幂等。

    返回本次新建的「未归类」task_name 数（提示用户前往映射编辑器完善）。
    """
    created_unclassified = 0
    for tn in task_names:
        if TaskMeta.objects.filter(task_name=tn).exists():
            continue
        if tn in TASK_TO_L2:
            at, attr = TASK_TO_L2[tn]
        elif tn in TASK_CATEGORY_MAPPING:
            at, attr = LEGACY_FOUR_TO_L2[TASK_CATEGORY_MAPPING[tn]]
        else:
            at, attr = '未归类', None
            created_unclassified += 1
        TaskMeta.objects.create(task_name=tn, activity_type=at, default_attribution=attr, is_system=False)
    return created_unclassified


class CSVImportService:
    """CSV 导入服务，支持去重合并"""

    REQUIRED_COLUMNS = ['任务名称', '开始时间', '持续时间（小时）']

    @staticmethod
    def _parse_datetime(s: str) -> datetime | None:
        """解析日期时间，支持 ISO 和中文字段格式"""
        if not s:
            return None
        s = s.strip()
        # ISO 格式：2026-06-03 23:29:36
        try:
            return datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            pass
        # 中文格式：2026年6月3日 23:29:36
        import re
        m = re.match(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日\s+(\d{1,2}):(\d{2}):(\d{2})', s)
        if m:
            return datetime(*map(int, m.groups()))
        return None

    @transaction.atomic
    def import_from_csv(self, file, batch_id: str) -> dict:
        # ── 读取文件内容 ──
        raw = file.read()
        print(f'[CSV 导入] 收到文件: {file.name!r}, 大小: {len(raw)} 字节')

        # 尝试解码（UTF-8 → GBK → 自动检测）
        content = None
        for enc in ('utf-8-sig', 'utf-8', 'gbk', 'gb2312', 'latin-1'):
            try:
                content = raw.decode(enc)
                if enc != 'utf-8':
                    print(f'[CSV 导入] 使用编码: {enc}')
                break
            except (UnicodeDecodeError, LookupError):
                continue
        if content is None:
            return {'error': '无法解码文件，请确认编码为 UTF-8 或 GBK', 'inserted': 0, 'updated': 0, 'skipped': 0}

        print(f'[CSV 导入] 文件前 500 字符:\n{content[:500]}')

        # ── 解析 CSV ──
        reader = csv.DictReader(io.StringIO(content))
        print(f'[CSV 导入] CSV 列名: {reader.fieldnames}')

        missing = [c for c in self.REQUIRED_COLUMNS if c not in reader.fieldnames]
        if missing:
            print(f'[CSV 导入] 缺少必要列: {missing}')
            return {'error': f'缺少必要列：{", ".join(missing)}', 'inserted': 0, 'updated': 0, 'skipped': 0}

        rows = []
        parse_errors = {'no_name': 0, 'no_time': 0, 'bad_duration': 0, 'bad_date': 0}
        for i, row in enumerate(reader, start=2):  # 行号从 2 开始（header 占第 1 行）
            name = (row.get('任务名称') or '').strip()
            start = row.get('开始时间', '').strip()
            dur_str = row.get('持续时间（小时）', '').strip()

            if not name:
                parse_errors['no_name'] += 1
                continue
            if not start:
                parse_errors['no_time'] += 1
                continue
            try:
                dur = float(dur_str) if dur_str else 0
            except ValueError:
                parse_errors['bad_duration'] += 1
                dur = 0
            if dur <= 0:
                parse_errors['bad_duration'] += 1
                continue
            try:
                start_dt = self._parse_datetime(start)
            except (ValueError, TypeError):
                start_dt = None
            if start_dt is None:
                parse_errors['bad_date'] += 1
                if i <= 5:
                    print(f'[CSV 导入] 第{i}行 日期解析失败: start={start!r}')
                continue

            rows.append({
                'name': name,
                'start_dt': start_dt,
                'date': start_dt.date(),
                'duration': dur,
                'description': (row.get('任务说明') or '').strip(),
                'end_time_str': (row.get('结束时间') or '').strip(),
                'notes': (row.get('附注') or '').strip(),
                'tags': (row.get('标签') or '').strip(),
            })

        print(f'[CSV 导入] 解析结果: 有效 {len(rows)} 行, 跳过详情: {parse_errors}')
        if rows:
            print(f'[CSV 导入] 首行样例: {rows[0]}')

        # ── 按 (任务名称, 日期) 去重合并（同一 CSV 内同一天同名任务累加时长） ──
        merged: dict[tuple[str, date], dict] = {}
        for r in rows:
            key = (r['name'], r['date'])
            end_dt = self._parse_datetime(r['end_time_str'])
            if key in merged:
                merged[key]['duration'] += r['duration']
                # 保留最晚的结束时间
                if end_dt and (not merged[key].get('end_dt') or end_dt > merged[key]['end_dt']):
                    merged[key]['end_dt'] = end_dt
            else:
                merged[key] = {
                    'name': r['name'],
                    'date': r['date'],
                    'start_dt': r['start_dt'],
                    'end_dt': end_dt,
                    'duration': r['duration'],
                    'description': r['description'],
                    'notes': r['notes'],
                    'tags': r['tags'],
                }

        print(f'[CSV 导入] 去重合并后: {len(merged)} 组')

        # ── 覆盖模式写入（用 year/mon/day 查找，避免 CONVERT_TZ 问题） ──
        # 注意：v0.3 起不再写入 category_level1/category_color（旧四大类字段停用），
        # 分类改走独立 managed 表 temporal_task_meta（由 migrate_temporal_categories 或下方自动建）。
        stats = {'inserted': 0, 'updated': 0, 'skipped': 0}
        for (name, d), g in merged.items():
            task_defaults = {
                'task_name': name,
                'task_description': g['description'],
                'start_time': g['start_dt'],
                'end_time': g['end_dt'],
                'duration_hours': g['duration'],
                'notes': g['notes'],
                'tags': g['tags'],
                'task_type': name,
                'year': d.year,
                'mon': f'{d.month:02d}',
                'day': d.day,
                'week': d.isocalendar()[1],
                'quarter': (d.month - 1) // 3 + 1,
                'import_batch': batch_id,
            }

            # 用 year+mon+day 查找（不走 start_time__date，避免 CONVERT_TZ 问题）
            existing = TemporalTask.objects.filter(
                task_name=name,
                year=d.year,
                mon=f'{d.month:02d}',
                day=d.day,
            ).first()

            if existing:
                # 持续时间完全相同 → 跳过
                existing_hours = float(existing.duration_hours or 0)
                if abs(existing_hours - g['duration']) < 0.01:
                    stats['skipped'] += 1
                    continue
                # 时长不同 → 更新
                TemporalTask.objects.filter(id=existing.id).update(
                    duration_hours=g['duration'],
                    end_time=g['end_dt'] or existing.end_time,
                    notes=g['notes'] or existing.notes,
                    import_batch=batch_id,
                    updated_at=timezone.now(),
                )
                stats['updated'] += 1
            else:
                TemporalTask.objects.create(**task_defaults)
                stats['inserted'] += 1

        # ── 自动为新出现的 task_name 建 L2 映射（命中 TASK_TO_L2 才建，否则进未归类桶）──
        stats['unclassified'] = _ensure_task_meta([name for name, _ in merged.keys()])

        # ── 自动刷新周度缓存 ──
        from apps.temporal.management.commands.refresh_weekly_cache import Command
        try:
            Command().handle()
            print('[CSV 导入] 周度缓存已刷新')
        except Exception as e:
            print(f'[CSV 导入] 缓存刷新失败: {e}')

        return stats


class TemporalStatsService:
    """时间统计服务（v0.3：聚合维度从 category_level1 改为 L1/L2）"""

    @staticmethod
    def get_overview(year: int | None = None) -> dict:
        qs = TemporalTask.objects.all()
        if year:
            qs = qs.filter(year=year)

        total_hours = qs.aggregate(s=models.Sum('duration_hours'))['s'] or 0
        total_records = qs.count()
        # order_by() 清序：避免 Django 把 start_time 注入 DISTINCT 列致去重失效
        active_days = qs.order_by().values('year', 'mon', 'day').distinct().count()

        rows = qs.values('task_name').annotate(h=models.Sum('duration_hours'))
        names = [r['task_name'] for r in rows]
        meta = resolve_task_meta(names)
        attr = resolve_attribution(names)

        attribution_breakdown = defaultdict(float)   # L1 归因
        activity_breakdown = defaultdict(float)      # L2 活动类型
        for r in rows:
            tn = r['task_name']
            h = float(r['h'] or 0)
            m = meta.get(tn)
            at = m['activity_type'] if m else '未归类'
            a = attr.get(tn, DEFAULT_FALLBACK_ATTR)
            activity_breakdown[at] += h
            attribution_breakdown[a] += h

        return {
            'total_hours': round(float(total_hours), 2),
            'total_records': total_records,
            'active_days': active_days,
            'attribution_breakdown': {k: round(v, 2) for k, v in attribution_breakdown.items()},
            'activity_breakdown': {k: round(v, 2) for k, v in activity_breakdown.items()},
            'completeness': TemporalStatsService.get_completeness(year),
        }

    @staticmethod
    def get_trend(year: int | None = None, group: str = 'month', level: str = 'l1') -> list:
        """趋势数据：level=l1(归因) / l2(活动类型) / l3(task_name)"""
        qs = TemporalTask.objects.all()
        if year:
            qs = qs.filter(year=year)

        tasks = qs.values('task_name', 'start_time', 'duration_hours')
        names = [t['task_name'] for t in tasks]
        meta = resolve_task_meta(names)
        attr = resolve_attribution(names)

        period_data = defaultdict(lambda: defaultdict(float))
        for t in tasks:
            st = t['start_time']
            if not st:
                continue
            tn = t['task_name']
            m = meta.get(tn)
            if level == 'l3':
                key2 = tn
            elif level == 'l2':
                key2 = (m['activity_type'] if m else '未归类')
            else:  # l1 = 价值归因
                key2 = attr.get(tn, DEFAULT_FALLBACK_ATTR)
            hours = float(t['duration_hours'] or 0)
            if group == 'month':
                p = st.strftime('%Y-%m')
            elif group == 'week':
                p = f"{st.year}-W{st.isocalendar()[1]:02d}"
            else:
                p = st.strftime('%Y-%m-%d')
            period_data[p][key2] += hours

        all_keys = set()
        for d in period_data.values():
            all_keys.update(d.keys())
        result = []
        for p in sorted(period_data.keys()):
            item = {'period': p}
            for k in sorted(all_keys):
                item[k] = round(period_data[p].get(k, 0.0), 2)
            result.append(item)
        return result

    @staticmethod
    def get_balance(year: int | None = None) -> dict:
        """平衡轮数据：按 L2 活动类型聚合（v0.3 改自 category_level1）"""
        qs = TemporalTask.objects.all()
        if year:
            qs = qs.filter(year=year)

        total_hours = float(qs.aggregate(s=models.Sum('duration_hours'))['s'] or 0)
        rows = qs.values('task_name').annotate(h=models.Sum('duration_hours'))
        meta = resolve_task_meta([r['task_name'] for r in rows])

        at_map = defaultdict(float)
        for r in rows:
            m = meta.get(r['task_name'])
            at = m['activity_type'] if m else '未归类'
            at_map[at] += float(r['h'] or 0)

        categories = []
        for at in sorted(at_map.keys()):
            h = round(at_map[at], 2)
            pct = round(h / total_hours * 100, 1) if total_hours > 0 else 0
            categories.append({
                'name': at,
                'hours': h,
                'percentage': pct,
                'color': ACTIVITY_TYPE_COLORS.get(at, '#9CA3AF'),
            })
        return {'total_hours': round(total_hours, 2), 'categories': categories}

    @staticmethod
    def get_sunburst(year: int | None = None) -> dict:
        """旭日/嵌套饼图数据（3 环）：L1 归因 → L2 活动类型 → L3 task_name"""
        qs = TemporalTask.objects.all()
        if year:
            qs = qs.filter(year=year)

        rows = qs.values('task_name').annotate(h=models.Sum('duration_hours'))
        names = [r['task_name'] for r in rows]
        meta = resolve_task_meta(names)
        attr = resolve_attribution(names)

        tree: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
        for r in rows:
            tn = r['task_name']
            h = float(r['h'] or 0)
            m = meta.get(tn)
            at = m['activity_type'] if m else '未归类'
            a = attr.get(tn, DEFAULT_FALLBACK_ATTR)
            tree[a][at][tn] += h

        def _ordered(keys, order):
            return sorted(keys, key=lambda n: (order.index(n) if n in order else 99, str(n)))

        groups = []
        for a in _ordered(tree.keys(), ATTRIBUTION_ORDER):
            l2_map = tree[a]
            l1_hours = sum(sum(l3.values()) for l3 in l2_map.values())
            children = []
            for at in _ordered(l2_map.keys(), []):
                l3_map = l2_map[at]
                children.append({
                    'name': at,
                    'hours': round(sum(l3_map.values()), 2),
                    'color': ACTIVITY_TYPE_COLORS.get(at, '#CBD5E1'),
                    'children': [
                        {'name': tn, 'hours': round(hv, 2)}
                        for tn, hv in sorted(l3_map.items(), key=lambda x: -x[1])
                    ],
                })
            groups.append({
                'name': a,
                'hours': round(l1_hours, 2),
                'color': ATTRIBUTION_COLORS.get(a, '#94A3B8'),
                'children': children,
            })
        return {'groups': groups}

    @staticmethod
    def get_168h_structure(year: int | None = None, weeks: int = 12) -> dict:
        """近 N 周 168h 结构：by_l1=归因 / by_l2=类型 / by_l3=task_name + 完整度"""
        qs = TemporalTask.objects.all()
        if year:
            qs = qs.filter(year=year)

        rows = qs.values('task_name', 'year', 'week').annotate(h=models.Sum('duration_hours'))
        names = [r['task_name'] for r in rows]
        meta = resolve_task_meta(names)
        attr = resolve_attribution(names)

        day_map = defaultdict(set)
        for d in qs.order_by().values('year', 'week', 'mon', 'day').distinct():
            day_map[(d['year'], d['week'])].add((d['mon'], d['day']))

        by_week = defaultdict(lambda: {
            'by_l1': defaultdict(float), 'by_l2': defaultdict(float), 'by_l3': defaultdict(float),
            'classified': 0.0,
        })
        for r in rows:
            tn = r['task_name']
            h = float(r['h'] or 0)
            yw = (r['year'], r['week'])
            m = meta.get(tn)
            at = (m['activity_type'] if m else '未归类')
            a = attr.get(tn, DEFAULT_FALLBACK_ATTR)
            by_week[yw]['by_l1'][a] += h
            by_week[yw]['by_l2'][at] += h
            by_week[yw]['by_l3'][tn] += h
            if m and m['activity_type'] != '未归类':
                by_week[yw]['classified'] += h

        result = []
        for yw in sorted(by_week.keys()):
            d = by_week[yw]
            days = len(day_map.get(yw, set()))
            denom = days * 16
            by_l1 = {k: round(v, 2) for k, v in d['by_l1'].items()}
            result.append({
                'year': yw[0],
                'week': yw[1],
                'by_l1': by_l1,
                'by_l2': {k: round(v, 2) for k, v in d['by_l2'].items()},
                'by_l3': {k: round(v, 2) for k, v in d['by_l3'].items()},
                # 兼容旧前端：赎回四色 == L1 归因
                'redemption_4color': by_l1,
                'completeness': round(d['classified'] / denom, 4) if denom else 0,
            })
        if weeks:
            result = result[-weeks:]
        return {'weeks': result}

    @staticmethod
    def get_completeness(year: int | None = None) -> dict:
        """记录完整度：已归类小时 / (16h/天 × 有记录天数)

        v0.2 决策 3：未归类参与总时长（灰显）但不参与完整度分母/分子。
        """
        qs = TemporalTask.objects.all()
        if year:
            qs = qs.filter(year=year)

        total = qs.aggregate(s=models.Sum('duration_hours'))['s'] or 0
        classified_names = list(
            TaskMeta.objects.exclude(activity_type='未归类').values_list('task_name', flat=True)
        )
        covered = qs.filter(task_name__in=classified_names).aggregate(s=models.Sum('duration_hours'))['s'] or 0
        days = qs.order_by().values('year', 'mon', 'day').distinct().count()
        denom = days * 16
        return {
            'total_hours': round(float(total), 2),
            'classified_hours': round(float(covered), 2),
            'completeness': round(covered / denom, 4) if denom else 0,
            'days_recorded': days,
            'denominator_hours_per_day': 16,
        }

    @staticmethod
    def get_ranking(year: int | None = None, limit: int = 10) -> list:
        """任务排行（L3 task_name），附 L2 活动类型与 L1 归因"""
        qs = TemporalTask.objects.all()
        if year:
            qs = qs.filter(year=year)

        rankings = list(
            qs.values('task_name').annotate(
                total_hours=models.Sum('duration_hours'),
                record_count=models.Count('id'),
            ).order_by('-total_hours')[:limit]
        )
        names = [r['task_name'] for r in rankings]
        meta = resolve_task_meta(names)
        attr = resolve_attribution(names)

        out = []
        for r in rankings:
            tn = r['task_name']
            at = (meta.get(tn) or {}).get('activity_type', '未归类')
            out.append({
                'task_name': tn,
                'activity_type': at,
                'attribution': attr.get(tn, DEFAULT_FALLBACK_ATTR),
                # 兼容旧键名
                'category': at,
                'color': ACTIVITY_TYPE_COLORS.get(at, '#9CA3AF'),
                'total_hours': round(float(r['total_hours'] or 0), 2),
                'record_count': r['record_count'],
            })
        return out

    @staticmethod
    def get_distribution(year: int | None = None) -> dict:
        qs = TemporalTask.objects.all()
        if year:
            qs = qs.filter(year=year)

        tasks = qs.values('start_time', 'duration_hours')
        slots = {'morning': 0.0, 'afternoon': 0.0, 'evening': 0.0}

        for t in tasks:
            st = t['start_time']
            if not st:
                continue
            hours = float(t['duration_hours'] or 0)
            h = st.hour
            if 6 <= h < 12:
                slots['morning'] += hours
            elif 12 <= h < 18:
                slots['afternoon'] += hours
            else:
                slots['evening'] += hours

        total = sum(slots.values())
        return {
            'morning': round(slots['morning'], 2),
            'afternoon': round(slots['afternoon'], 2),
            'evening': round(slots['evening'], 2),
            'morning_pct': round((slots['morning'] / total) * 100, 1) if total > 0 else 0,
            'afternoon_pct': round((slots['afternoon'] / total) * 100, 1) if total > 0 else 0,
            'evening_pct': round((slots['evening'] / total) * 100, 1) if total > 0 else 0,
        }

    @staticmethod
    def get_calendar(year: int | None = None) -> list:
        qs = TemporalTask.objects.all()
        if year:
            qs = qs.filter(year=year)

        days = qs.values('year', 'mon', 'day').annotate(
            total_hours=models.Sum('duration_hours'),
            record_count=models.Count('id'),
        ).order_by('year', 'mon', 'day')

        return [
            {
                'date': f"{d['year']}-{d['mon']}-{str(d['day']).zfill(2)}",
                'hours': round(float(d['total_hours'] or 0), 2),
                'count': d['record_count'],
            }
            for d in days
        ]


class OneDayPageService:
    """每日记录统计服务"""

    @staticmethod
    def get_stats():
        """获取全量统计信息"""
        total_count = OneDayPage.objects.count()

        type_stats = list(OneDayPage.objects.values('otype').annotate(
            count=Count('oid'),
            total_oneday=Sum('oneday'),
            total_page=Sum('page'),
            total_words=Sum('total'),
            avg_words=Avg('total'),
        ))

        year_stats = list(OneDayPage.objects.values('years').annotate(
            count=Count('oid'),
            total_oneday=Sum('oneday'),
            total_page=Sum('page'),
            total_words=Sum('total'),
            avg_words=Avg('total'),
        ).order_by('-years'))

        month_stats = list(OneDayPage.objects.extra(
            select={'month': "DATE_FORMAT(begin_date, '%%Y-%%m')"},
        ).values('month').annotate(
            count=Count('oid'),
            total_oneday=Sum('oneday'),
            total_page=Sum('page'),
            total_words=Sum('total'),
        ).order_by('-month')[:12])

        now = timezone.now()
        month_start = datetime(now.year, now.month, 1)
        month_count = OneDayPage.objects.filter(begin_date__gte=month_start).count()

        total_oneday = OneDayPage.objects.aggregate(total=Sum('oneday'))['total'] or 0
        total_page = OneDayPage.objects.aggregate(total=Sum('page'))['total'] or 0
        total_words = OneDayPage.objects.aggregate(total=Sum('total'))['total'] or 0
        avg_words = OneDayPage.objects.aggregate(avg=Avg('total'))['avg'] or 0

        return {
            'total_count': total_count,
            'month_count': month_count,
            'total_oneday': total_oneday,
            'total_page': total_page,
            'total_words': total_words,
            'avg_words': round(avg_words, 2),
            'type_stats': type_stats,
            'year_stats': year_stats,
            'month_stats': month_stats,
        }


class DailyLogAutoService:
    """每日默认日记自动生成服务"""

    @staticmethod
    def generate_default_log(user_id: int = 1) -> OneDayPage | None:
        """为今天生成默认日记（如果今天还没有任何日记）"""
        today = date.today()

        # 使用日期字段比较，兼容 DateField
        if OneDayPage.objects.filter(
            user_id=user_id,
            begin_date__year=today.year,
            begin_date__month=today.month,
            begin_date__day=today.day,
        ).exists():
            return None

        log = OneDayPage.objects.create(
            user_id=user_id,
            title='幸福未被发现，就叫做普通的一天',
            begin_date=today,
            otype='ONEDAY',
            oneday=0,
            page=0,
            total=0,
            years=str(today.year),
        )
        return log
