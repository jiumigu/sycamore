import csv
import io
from collections import defaultdict
from datetime import datetime, date

from django.db import models, transaction
from django.db.models import Avg, Count, Sum
from django.utils import timezone

from .constants import CATEGORY_COLORS, TASK_CATEGORY_MAPPING
from .models import OneDayPage, TemporalTask


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
        stats = {'inserted': 0, 'updated': 0, 'skipped': 0}
        for (name, d), g in merged.items():
            category = TASK_CATEGORY_MAPPING.get(name, '维护与秩序')
            color = CATEGORY_COLORS.get(category, '#9CA3AF')

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
                'category_level1': category,
                'category_color': color,
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
                    category_level1=category,
                    category_color=color,
                    notes=g['notes'] or existing.notes,
                    import_batch=batch_id,
                    updated_at=timezone.now(),
                )
                stats['updated'] += 1
            else:
                TemporalTask.objects.create(**task_defaults)
                stats['inserted'] += 1

        # ── 自动刷新周度缓存 ──
        from apps.temporal.management.commands.refresh_weekly_cache import Command
        try:
            Command().handle()
            print('[CSV 导入] 周度缓存已刷新')
        except Exception as e:
            print(f'[CSV 导入] 缓存刷新失败: {e}')

        return stats


class TemporalStatsService:
    """时间统计服务"""

    @staticmethod
    def get_overview(year: int | None = None) -> dict:
        qs = TemporalTask.objects.all()
        if year:
            qs = qs.filter(year=year)

        total_hours = qs.aggregate(s=models.Sum('duration_hours'))['s'] or 0
        total_records = qs.count()
        active_days = qs.values('year', 'mon', 'day').distinct().count()

        cat_totals = qs.values('category_level1').annotate(
            hours=models.Sum('duration_hours'),
        ).order_by('-hours')

        production_pct = 0
        cat_breakdown = {}
        for c in cat_totals:
            cat_name = c['category_level1'] or '未分类'
            h = float(c['hours'] or 0)
            cat_breakdown[cat_name] = h

        if total_hours > 0 and '生产与创造' in cat_breakdown:
            production_pct = round((cat_breakdown['生产与创造'] / total_hours) * 100, 1)

        return {
            'total_hours': round(float(total_hours), 2),
            'total_records': total_records,
            'active_days': active_days,
            'production_percentage': production_pct,
            'category_breakdown': cat_breakdown,
        }

    @staticmethod
    def get_trend(year: int | None = None, group: str = 'month') -> list:
        qs = TemporalTask.objects.all()
        if year:
            qs = qs.filter(year=year)

        tasks = qs.values('start_time', 'duration_hours', 'category_level1')

        period_data = defaultdict(lambda: defaultdict(float))
        for t in tasks:
            st = t['start_time']
            if not st:
                continue
            cat = t['category_level1'] or '未分类'
            hours = float(t['duration_hours'] or 0)
            if group == 'month':
                key = st.strftime('%Y-%m')
            elif group == 'week':
                key = f"{st.year}-W{st.isocalendar()[1]:02d}"
            else:
                key = st.strftime('%Y-%m-%d')

            period_data[key][cat] += hours

        categories_order = ['生产与创造', '维护与秩序', '滋养与成长', '连接与记录']
        result = []
        for period in sorted(period_data.keys()):
            item = {'period': period}
            for cat in categories_order:
                item[cat] = round(period_data[period][cat], 2)
            other = round(sum(v for k, v in period_data[period].items() if k not in categories_order), 2)
            if other:
                item['其他'] = other
            result.append(item)

        return result

    @staticmethod
    def get_balance(year: int | None = None) -> dict:
        qs = TemporalTask.objects.all()
        if year:
            qs = qs.filter(year=year)

        total_hours = float(qs.aggregate(s=models.Sum('duration_hours'))['s'] or 0)
        cat_totals = qs.values('category_level1').annotate(
            hours=models.Sum('duration_hours'),
        )

        categories = []
        cat_map = {c['category_level1']: float(c['hours'] or 0) for c in cat_totals}

        for cat_name in ['生产与创造', '维护与秩序', '滋养与成长', '连接与记录']:
            hours = cat_map.get(cat_name, 0)
            pct = round((hours / total_hours) * 100, 1) if total_hours > 0 else 0
            categories.append({
                'name': cat_name,
                'hours': round(hours, 2),
                'percentage': pct,
                'color': CATEGORY_COLORS.get(cat_name, '#9CA3AF'),
            })

        return {'total_hours': round(total_hours, 2), 'categories': categories}

    @staticmethod
    def get_ranking(year: int | None = None, limit: int = 10) -> list:
        qs = TemporalTask.objects.all()
        if year:
            qs = qs.filter(year=year)

        rankings = qs.values('task_name', 'category_level1', 'category_color').annotate(
            total_hours=models.Sum('duration_hours'),
            record_count=models.Count('id'),
        ).order_by('-total_hours')[:limit]

        return [
            {
                'task_name': r['task_name'],
                'category': r['category_level1'] or '未分类',
                'color': r['category_color'] or '#9CA3AF',
                'total_hours': round(float(r['total_hours'] or 0), 2),
                'record_count': r['record_count'],
            }
            for r in rankings
        ]

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
            select={'month': "DATE_FORMAT(beginDate, '%%Y-%%m')"},
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
