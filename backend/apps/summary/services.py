"""综合进度看板 — 数据聚合服务"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from django.db.models import Q, Sum

from .constants import (
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


class QuarterlyWorkbenchService:
    """季度决策工作台 —— 生成季度对比报告、洞察与追问"""

    QUARTER_MONTHS = {
        1: (1, 2, 3),
        2: (4, 5, 6),
        3: (7, 8, 9),
        4: (10, 11, 12),
    }

    # ── 工具方法 ───────────────────────────────────────

    @staticmethod
    def _prev_quarter(year: int, quarter: int) -> tuple[int, int]:
        """返回上一个季度的 (year, quarter)"""
        if quarter == 1:
            return year - 1, 4
        return year, quarter - 1

    @staticmethod
    def _quarter_months(quarter: int) -> tuple[int, int, int]:
        return QuarterlyWorkbenchService.QUARTER_MONTHS[quarter]

    @classmethod
    def _quarter_range(cls, year: int, quarter: int) -> tuple[tuple[int, int], tuple[int, int]]:
        """返回季度的月份范围 [(year, month), (year, month)]"""
        months = cls._quarter_months(quarter)
        return (year, months[0]), (year, months[2])

    # ── 单模块季度聚合 ────────────────────────────────

    @classmethod
    def _module_quarter_raw(cls, module: str, year: int, quarter: int) -> float:
        months = cls._quarter_months(quarter)
        total = 0.0
        for m in months:
            total += ProgressAggregator._get_raw_value(module, year, m)
        return total

    @classmethod
    def _module_quarter_points(cls, module: str, year: int, quarter: int) -> float:
        raw = cls._module_quarter_raw(module, year, quarter)
        return ProgressAggregator._raw_to_points(module, raw)

    # ── 公开: 季度报告 ────────────────────────────────

    @classmethod
    def get_quarterly_report(cls, year: int, quarter: int) -> dict:
        """生成季度报告：7 模块聚合 + 与上季度 / 去年同期对比"""
        prev_y, prev_q = cls._prev_quarter(year, quarter)
        last_year_quarter = (year - 1, quarter)

        modules_data = []
        for mod in MODULE_LIST:
            cur = cls._module_quarter_points(mod, year, quarter)
            prev = cls._module_quarter_points(mod, prev_y, prev_q)
            last_year = cls._module_quarter_points(mod, *last_year_quarter)
            meta = MODULE_META[mod]
            rule = CONVERSION_RULES[mod]
            raw = cls._module_quarter_raw(mod, year, quarter)

            qoq_change = ((cur - prev) / prev * 100) if prev > 0 else (100 if cur > 0 else 0)
            yoy_change = ((cur - last_year) / last_year * 100) if last_year > 0 else (100 if cur > 0 else 0)

            modules_data.append({
                'module': mod,
                'label': meta['label'],
                'color': meta['color'],
                'points': round(cur, 2),
                'raw_value': round(raw, 2),
                'unit': rule['unit'],
                'prev_quarter_points': round(prev, 2),
                'qoq_change': round(qoq_change, 1),
                'last_year_points': round(last_year, 2),
                'yoy_change': round(yoy_change, 1),
            })

        total = sum(m['points'] for m in modules_data)
        prev_total = sum(m['prev_quarter_points'] for m in modules_data)
        last_year_total = sum(
            cls._module_quarter_points(mod, *last_year_quarter) for mod in MODULE_LIST
        ) if year - 1 >= 2000 else 0

        quarterly_target = YEARLY_TARGET / 4

        return {
            'year': year,
            'quarter': quarter,
            'label': f'{year}年Q{quarter}',
            'total_points': round(total, 2),
            'quarter_target': round(quarterly_target, 2),
            'target_percent': round(total / quarterly_target * 100, 2) if quarterly_target else 0,
            'prev_quarter_total': round(prev_total, 2),
            'qoq_change': round(
                ((total - prev_total) / prev_total * 100) if prev_total > 0 else (100 if total > 0 else 0), 1
            ),
            'last_year_total': round(last_year_total, 2),
            'yoy_change': round(
                ((total - last_year_total) / last_year_total * 100) if last_year_total > 0 else (100 if total > 0 else 0), 1
            ),
            'modules': modules_data,
        }

    # ── 公开: 生成洞察与追问 ──────────────────────────

    @classmethod
    def generate_questions(cls, year: int, quarter: int) -> list[dict]:
        """分析季度数据，生成针对性追问"""
        report = cls.get_quarterly_report(year, quarter)
        questions: list[dict] = []
        qk = 0  # question key counter

        # 1. 整体进度追问
        total = report['total_points']
        target = report['quarter_target']

        if total < target * 0.5:
            qk += 1
            questions.append({
                'question_key': f'overall_behind_{qk}',
                'question_category': 'target_behind',
                'question_text': f'Q{quarter} 只完成了目标的 {report["target_percent"]}%，差距较大。'
                                 f'哪个模块拖后腿最严重？下季度需要砍掉什么来补上？',
                'related_module': '',
            })
        elif total < target * 0.8:
            qk += 1
            questions.append({
                'question_key': f'overall_slightly_behind_{qk}',
                'question_category': 'target_behind',
                'question_text': f'Q{quarter} 完成了 {report["target_percent"]}%，还差一点。'
                                 f'哪些模块还有潜力可以挖掘？',
                'related_module': '',
            })

        # 2. 同比/环比显著变化追问
        for m in report['modules']:
            mod = m['module']
            # 环比显著下降
            if m['qoq_change'] <= -30:
                qk += 1
                questions.append({
                    'question_key': f'drop_qoq_{mod}_{qk}',
                    'question_category': 'drop',
                    'question_text': f'【{m["label"]}】环比暴跌 {abs(m["qoq_change"])}%'
                                    f'（{m["prev_quarter_points"]} → {m["points"]} 点）。'
                                    f'发生了什么？是外部因素还是主动选择？需要调整计划吗？',
                    'related_module': mod,
                })
            # 环比显著上升
            elif m['qoq_change'] >= 50:
                qk += 1
                questions.append({
                    'question_key': f'rise_qoq_{mod}_{qk}',
                    'question_category': 'improve',
                    'question_text': f'【{m["label"]}】环比飙升 {m["qoq_change"]}%'
                                    f'（{m["prev_quarter_points"]} → {m["points"]} 点）。'
                                    f'做对了什么？能否复制到其他模块？',
                    'related_module': mod,
                })
            # 同比显著下降
            if m['yoy_change'] <= -30:
                qk += 1
                questions.append({
                    'question_key': f'drop_yoy_{mod}_{qk}',
                    'question_category': 'drop',
                    'question_text': f'【{m["label"]}】同比去年同期下降 {abs(m["yoy_change"])}%'
                                    f'（去年 {m["last_year_points"]} → 今年 {m["points"]} 点）。'
                                    f'这个趋势值得关注，需要制定挽回计划吗？',
                    'related_module': mod,
                })

            # 最低分模块
            if m['points'] <= 1.0 and mod != TRAVEL:  # 旅行可能天然低频
                qk += 1
                questions.append({
                    'question_key': f'low_performer_{mod}_{qk}',
                    'question_category': 'low_performer',
                    'question_text': f'【{m["label"]}】本季度仅 {m["points"]} 点，几乎为零投入。'
                                     f'是暂时搁置还是已经放弃了这个维度？如果是放弃，需要从目标中移除吗？',
                    'related_module': mod,
                })

        # 3. 极端波动追问（找出变化最大的模块）
        changes = [(m['module'], m['label'], abs(m['qoq_change'])) for m in report['modules']]
        changes.sort(key=lambda x: x[2], reverse=True)
        if changes and changes[0][2] > 20:
            top_mod, top_label, top_change = changes[0]
            qk += 1
            questions.append({
                'question_key': f'biggest_swing_{qk}',
                'question_category': 'general',
                'question_text': f'Q{quarter} 变化最大的维度是「{top_label}」（波动 {top_change}%）。'
                                 f'如果只能做一件事来改善下个季度的整体进度，你会做什么？',
                'related_module': top_mod,
            })

        # 4. 年度进度预测
        ytd_ratio = cls._ytd_progress(year, quarter)
        if ytd_ratio < 0.5:
            qk += 1
            questions.append({
                'question_key': f'year_progress_{qk}',
                'question_category': 'target_behind',
                'question_text': f'已经过去 {quarter}/4 年，但只完成了全年目标的 {round(ytd_ratio * 100, 1)}%。'
                                 f'剩下的时间需要加倍投入。最重要的 1-2 个冲刺目标是什么？',
                'related_module': '',
            })

        # 如果没有明显问题，给一个正面追问
        if not questions:
            qk += 1
            questions.append({
                'question_key': f'all_good_{qk}',
                'question_category': 'general',
                'question_text': f'Q{quarter} 各项指标总体平稳。回顾这三个月，最让你有成就感的是什么？'
                                 f'下季度有什么新计划？',
                'related_module': '',
            })

        return questions

    @classmethod
    def _ytd_progress(cls, year: int, current_quarter: int) -> float:
        """计算年初到本季度结束的累计进度占全年目标的比例"""
        months_up_to = []
        for q in range(1, current_quarter + 1):
            months_up_to.extend(cls._quarter_months(q))
        total = 0.0
        for mod in MODULE_LIST:
            for m in months_up_to:
                total += ProgressAggregator._raw_to_points(mod, ProgressAggregator._get_raw_value(mod, year, m))
        return total / YEARLY_TARGET if YEARLY_TARGET else 0

    # ── 问答持久化 ────────────────────────────────────

    @classmethod
    def get_answers(cls, year: int, quarter: int) -> list[dict]:
        from .models import QuarterlyAnswer
        qs = QuarterlyAnswer.objects.filter(year=year, quarter=quarter).order_by('created_at')
        return [
            {
                'id': a.id,
                'question_key': a.question_key,
                'question_text': a.question_text,
                'question_category': a.question_category,
                'answer_text': a.answer_text,
                'related_module': a.related_module,
                'action_taken': a.action_taken,
                'updated_at': a.updated_at.isoformat() if a.updated_at else '',
            }
            for a in qs
        ]

    @classmethod
    def save_answer(cls, year: int, quarter: int, question_key: str, answer_text: str,
                    action_taken: bool = False) -> dict:
        from .models import QuarterlyAnswer
        obj, created = QuarterlyAnswer.objects.update_or_create(
            year=year,
            quarter=quarter,
            question_key=question_key,
            defaults={
                'answer_text': answer_text,
                'action_taken': action_taken,
            },
        )
        return {'id': obj.id, 'status': 'created' if created else 'updated'}

    @classmethod
    def get_insights(cls, year: int, quarter: int) -> list[dict]:
        """生成简洁的洞察摘要"""
        report = cls.get_quarterly_report(year, quarter)
        insights: list[dict] = []

        total = report['total_points']
        target = report['quarter_target']

        # 整体评估
        if total >= target:
            insights.append({
                'type': 'success',
                'icon': '🎯',
                'message': f'达标！Q{quarter} 完成 {total} 点，达到目标的 {report["target_percent"]}%',
            })
        elif total >= target * 0.8:
            insights.append({
                'type': 'warning',
                'icon': '⚠️',
                'message': f'接近达标：Q{quarter} 完成 {total} 点（目标的 {report["target_percent"]}%），还差 {round(target - total, 1)} 点',
            })
        else:
            insights.append({
                'type': 'danger',
                'icon': '🔻',
                'message': f'未达标：Q{quarter} 仅完成 {total} 点（目标的 {report["target_percent"]}%），差距 {round(target - total, 1)} 点',
            })

        # 环比趋势
        qoq = report['qoq_change']
        if qoq > 10:
            insights.append({
                'type': 'success',
                'icon': '📈',
                'message': f'环比上季度增长 {qoq}%，整体趋势向好',
            })
        elif qoq < -10:
            insights.append({
                'type': 'danger',
                'icon': '📉',
                'message': f'环比上季度下降 {abs(qoq)}%，需关注下滑趋势',
            })
        else:
            insights.append({
                'type': 'info',
                'icon': '➡️',
                'message': f'环比基本持平（{qoq}%），稳定性不错',
            })

        # 最佳/最差模块
        sorted_modules = sorted(report['modules'], key=lambda m: m['qoq_change'], reverse=True)
        if sorted_modules:
            best = sorted_modules[0]
            worst = sorted_modules[-1]
            if best['qoq_change'] > 0:
                insights.append({
                    'type': 'success',
                    'icon': '🏆',
                    'message': f'最佳表现：{best["label"]}（环比+{best["qoq_change"]}%，'
                               f'得分 {best["points"]}）',
                })
            if worst['qoq_change'] < 0:
                insights.append({
                    'type': 'danger',
                    'icon': '🐌',
                    'message': f'最需关注：{worst["label"]}（环比{worst["qoq_change"]}%，'
                               f'得分 {worst["points"]}）',
                })

        return insights
