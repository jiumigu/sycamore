"""综合进度看板 — 核心聚合器（由 services.py 拆分）"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.db.models import Sum

from ..constants import (
    BOOK,
    CONVERSION_RULES,
    HEALTH,
    MODULE_LIST,
    MODULE_META,
    MONTHLY_TARGET_RATIO,
    RADAR_MAX,
    SUGAR,
    TIMES,
    TRAVEL,
    WEALTH,
    WORDS,
    YEARLY_TARGET,
)

class ProgressAggregator:
    """核心聚合器 —— 从各模块读取原始数据，换算为统一进度点"""

    # ── 私有: 单模块年度聚合 ──────────────────────────────

    @staticmethod
    def _wealth_raw(year: int, month: int | None = None) -> float:
        """净收入 = wageincome + otherincome - outmoney"""
        from apps.wealth.models import WealthBalanceList

        qs = WealthBalanceList.objects.filter(yearmon__startswith=str(year))
        if month:
            qs = qs.filter(yearmon__endswith=f'-{str(month).zfill(2)}')

        agg = qs.aggregate(
            wage=Sum('wageincome'),
            other=Sum('otherincome'),
            out=Sum('outmoney'),
        )
        net = (agg['wage'] or 0) + (agg['other'] or 0) - (agg['out'] or 0)
        return max(net, 0.0)

    @staticmethod
    def _health_raw(year: int, month: int | None = None) -> float:
        from apps.health.models import HealthRecord

        qs = HealthRecord.objects.filter(time__year=year)
        if month:
            from datetime import date
            start = date(year, month, 1)
            if month == 12:
                end = date(year + 1, 1, 1)
            else:
                end = date(year, month + 1, 1)
            qs = qs.filter(time__range=(start, end))
        return qs.aggregate(s=Sum('total'))['s'] or 0

    @staticmethod
    def _times_raw(year: int, month: int | None = None) -> float:
        from apps.temporal.models import TemporalTask

        qs = TemporalTask.objects.filter(year=year)
        if month:
            qs = qs.filter(mon=str(month).zfill(2))
        return qs.aggregate(h=Sum('duration_hours'))['h'] or 0

    @staticmethod
    def _words_raw(year: int, month: int | None = None) -> float:
        from apps.temporal.models import OneDayPage

        qs = OneDayPage.objects.filter(begin_date__year=year)
        if month:
            qs = qs.filter(begin_date__month=month)
        return qs.aggregate(t=Sum('total'))['t'] or 0

    @staticmethod
    def _sugar_raw(year: int, month: int | None = None) -> float:
        from apps.sugar.models import SugarRecord

        qs = SugarRecord.objects.filter(time__year=year)
        if month:
            qs = qs.filter(time__month=month)
        return float(qs.aggregate(h=Sum('level_of_happiness'))['h'] or 0)

    @staticmethod
    def _travel_raw(year: int, month: int | None = None) -> int:
        from apps.travel.models import TravelRecord

        qs = TravelRecord.objects.filter(tyear=year)
        if month:
            qs = qs.filter(ttime__month=month)
        return qs.count()

    @staticmethod
    def _book_raw(year: int, month: int | None = None) -> int:
        from apps.book.models import Book

        qs = Book.objects.filter(
            status__in=['已完成', '通读', '精读'],
            readDate__year=year,
        )
        if month:
            qs = qs.filter(readDate__month=month)
        return qs.count()

    # ── 原始值获取路由 ─────────────────────────────────────

    _RAW_GETTERS: dict[str, callable] = {
        WEALTH: _wealth_raw,
        HEALTH: _health_raw,
        TIMES: _times_raw,
        WORDS: _words_raw,
        SUGAR: _sugar_raw,
        TRAVEL: _travel_raw,
        BOOK: _book_raw,
    }

    @classmethod
    def _get_raw_value(cls, module: str, year: int, month: int | None = None) -> float:
        return cls._RAW_GETTERS[module](year, month)

    # ── 原始值 → 进度点 ───────────────────────────────────

    @classmethod
    def _raw_to_points(cls, module: str, raw_value: float) -> float:
        rule = CONVERSION_RULES[module]
        rtype = rule.get('type', 'aggregate')
        if rtype == 'count' or rtype == 'count_completed':
            return float(raw_value)
        return raw_value / rule['divisor']

    # ── 单模块总览条目 ─────────────────────────────────────

    @classmethod
    def _module_entry(cls, module: str, year: int, month: int | None = None) -> dict:
        raw = cls._get_raw_value(module, year, month)
        points = cls._raw_to_points(module, raw)
        meta = MODULE_META[module]
        rule = CONVERSION_RULES[module]
        return {
            'module': module,
            'label': meta['label'],
            'color': meta['color'],
            'points': round(points, 2),
            'raw_value': round(raw, 2),
            'unit': rule['unit'],
        }

    # ── 公开: 可用年份 ─────────────────────────────────────

    @classmethod
    def get_available_years(cls) -> list[int]:
        """从所有模块收集有数据的年份"""
        from apps.wealth.models import WealthBalanceList
        from apps.health.models import HealthRecord
        from apps.temporal.models import OneDayPage, TemporalTask
        from apps.sugar.models import SugarRecord
        from apps.travel.models import TravelRecord
        from apps.book.models import Book

        year_sets = [
            set(WealthBalanceList.objects.values_list('yearmon', flat=True)),
            set(HealthRecord.objects.values_list('time__year', flat=True)),
            set(TemporalTask.objects.values_list('year', flat=True)),
            set(OneDayPage.objects.values_list('begin_date__year', flat=True)),
            set(SugarRecord.objects.values_list('time__year', flat=True)),
            set(TravelRecord.objects.values_list('tyear', flat=True)),
            set(Book.objects.filter(status='已完成').values_list('readDate__year', flat=True)),
        ]
        all_years: set[int] = set()
        for s in year_sets:
            for y in s:
                if y is not None:
                    if isinstance(y, str):
                        all_years.add(int(y[:4]))
                    else:
                        all_years.add(int(y))
        return sorted(all_years, reverse=True)

    # ── 公开: 年度总览 ─────────────────────────────────────

    @classmethod
    def get_yearly_overview(cls, year: int | None = None) -> dict:
        if year is None:
            year = datetime.now().year

        modules = [cls._module_entry(m, year) for m in MODULE_LIST]
        total = sum(m['points'] for m in modules)
        monthly_target = round(YEARLY_TARGET * MONTHLY_TARGET_RATIO, 2)

        return {
            'year': str(year),
            'total_points': round(total, 2),
            'yearly_target': YEARLY_TARGET,
            'monthly_target': monthly_target,
            'progress_percent': round(total / YEARLY_TARGET * 100, 2) if YEARLY_TARGET else 0,
            'remaining_points': round(max(YEARLY_TARGET - total, 0), 2),
            'modules': modules,
        }

    # ── 公开: 月度详情 ─────────────────────────────────────

    @classmethod
    def get_monthly_detail(cls, year: int | None = None, month: int | None = None) -> dict:
        from datetime import datetime

        if year is None:
            year = datetime.now().year
        if month is None:
            month = datetime.now().month

        modules = [cls._module_entry(m, year, month) for m in MODULE_LIST]
        total = sum(m['points'] for m in modules)
        monthly_target = round(YEARLY_TARGET * MONTHLY_TARGET_RATIO, 2)

        return {
            'year': str(year),
            'month': month,
            'total_points': round(total, 2),
            'month_target': monthly_target,
            'target_percent': round(total / monthly_target * 100, 2) if monthly_target else 0,
            'modules': modules,
        }

    # ── 公开: 月度趋势 ─────────────────────────────────────

    @classmethod
    def get_trend(cls, year: int | None = None) -> list[dict]:
        if year is None:
            year = datetime.now().year

        months = list(range(1, 13))
        monthly_target = round(YEARLY_TARGET * MONTHLY_TARGET_RATIO, 2)
        result: list[dict] = []

        for m in months:
            entry: dict[str, Any] = {'month': m, 'month_target': monthly_target}
            for mod in MODULE_LIST:
                raw = cls._get_raw_value(mod, year, m)
                entry[mod] = round(cls._raw_to_points(mod, raw), 2)
            entry['total_points'] = round(sum(entry[mod] for mod in MODULE_LIST), 2)
            result.append(entry)

        return result

    # ── 公开: 雷达图 ───────────────────────────────────────

    @classmethod
    def get_radar(cls, year: int | None = None) -> dict:
        if year is None:
            year = datetime.now().year

        indicators = []
        series_values = []

        for mod in MODULE_LIST:
            raw = cls._get_raw_value(mod, year)
            value = round(cls._raw_to_points(mod, raw), 2)
            meta = MODULE_META[mod]
            max_val = RADAR_MAX.get(mod, 100)
            indicators.append({
                'name': meta['label'],
                'max': max_val,
                'color': meta['color'],
            })
            series_values.append(value)

        return {
            'year': year,
            'indicators': indicators,
            'values': series_values,
        }

    # ── 公开: 模块详情钻取 ─────────────────────────────────

    @classmethod
    def get_module_detail(cls, module: str, year: int | None = None, month: int | None = None) -> dict:
        if module not in MODULE_LIST:
            return {'error': f'未知模块: {module}'}

        raw = cls._get_raw_value(module, year, month)
        points = cls._raw_to_points(module, raw)
        meta = MODULE_META[module]
        rule = CONVERSION_RULES[module]

        # 获取原始记录（最多 50 条）
        records = cls._get_raw_records(module, year, month)

        return {
            'module': module,
            'label': meta['label'],
            'color': meta['color'],
            'raw_value': round(raw, 2),
            'points': round(points, 2),
            'unit': rule['unit'],
            'record_count': len(records),
            'records': records[:50],
        }

    @classmethod
    def _get_raw_records(cls, module: str, year: int | None, month: int | None) -> list[dict]:
        """获取指定模块的原始记录摘要"""
        from datetime import datetime

        year = year or datetime.now().year

        if module == WEALTH:
            from apps.wealth.models import WealthBalanceList
            qs = WealthBalanceList.objects.filter(yearmon__startswith=str(year))
            if month:
                qs = qs.filter(yearmon__endswith=f'-{str(month).zfill(2)}')
            return [
                {'yearmon': r.yearmon, 'income': (r.wageincome or 0) + (r.otherincome or 0),
                 'expense': r.outmoney or 0, 'net': (r.wageincome or 0) + (r.otherincome or 0) - (r.outmoney or 0)}
                for r in qs.order_by('-yearmon')[:50]
            ]

        if module == HEALTH:
            from apps.health.models import HealthRecord
            qs = HealthRecord.objects.filter(time__year=year)
            if month:
                qs = qs.filter(time__month=month)
            return [
                {'date': r.time.isoformat() if r.time else '', 'steps': r.total or 0}
                for r in qs.order_by('-time')[:50]
            ]

        if module == TIMES:
            from apps.temporal.models import TemporalTask
            qs = TemporalTask.objects.filter(year=year)
            if month:
                qs = qs.filter(mon=str(month).zfill(2))
            return [
                {'task': r.task_name, 'hours': r.duration_hours or 0,
                 'date': r.start_time.isoformat() if r.start_time else ''}
                for r in qs.order_by('-start_time')[:50]
            ]

        if module == WORDS:
            from apps.temporal.models import OneDayPage
            qs = OneDayPage.objects.filter(begin_date__year=year)
            if month:
                qs = qs.filter(begin_date__month=month)
            return [
                {'date': r.begin_date.isoformat() if r.begin_date else '',
                 'title': r.title, 'words': r.total or 0}
                for r in qs.order_by('-begin_date')[:50]
            ]

        if module == SUGAR:
            from apps.sugar.models import SugarRecord
            qs = SugarRecord.objects.filter(time__year=year)
            if month:
                qs = qs.filter(time__month=month)
            return [
                {'title': r.title, 'happiness': float(r.level_of_happiness),
                 'date': r.time.isoformat() if r.time else ''}
                for r in qs.order_by('-time')[:50]
            ]

        if module == TRAVEL:
            from apps.travel.models import TravelRecord
            qs = TravelRecord.objects.filter(tyear=year)
            if month:
                qs = qs.filter(ttime__month=month)
            return [
                {'place': r.tname, 'cost': r.tcost or 0, 'date': r.ttime.isoformat() if r.ttime else ''}
                for r in qs.order_by('-ttime')[:50]
            ]

        if module == BOOK:
            from apps.book.models import Book
            qs = Book.objects.filter(status='已完成', readDate__year=year)
            if month:
                qs = qs.filter(readDate__month=month)
            return [
                {'title': r.btitle, 'author': r.author, 'date': r.readDate.isoformat() if r.readDate else ''}
                for r in qs.order_by('-readDate')[:50]
            ]

        return []
