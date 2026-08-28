"""健康统计服务 — 步数统计与里程碑（由 services.py 拆分）"""

from datetime import date, datetime, timedelta

from django.db import models
from django.db.models import DateField
from django.db.models.functions import Cast
from django.utils import timezone

from ..constants import (
    HEALTH_MILESTONE_SIZE,
    HEALTH_TARGET_STEPS,
    HEALTH_TOTAL_MILESTONES,
    HTYPE_LABELS,
)
from ..models import HealthRecord

class HealthStatsService:
    """健康统计服务（1亿步目标）"""

    @staticmethod
    def get_summary() -> dict:
        qs = HealthRecord.objects.all()
        total_steps = qs.aggregate(s=models.Sum('total'))['s'] or 0

        if total_steps == 0:
            return {
                'total_steps': 0, 'target_steps': HEALTH_TARGET_STEPS,
                'progress_percent': 0, 'completed_milestones': 0,
                'total_milestones': HEALTH_TOTAL_MILESTONES,
                'next_milestone_distance': HEALTH_MILESTONE_SIZE,
                'daily_avg': 0, 'days_active': 0, 'max_daily': 0,
                'longest_streak': 0, 'this_month_steps': 0,
                'prediction': None,
                'current_milestone': {
                    'number': 1, 'start': 0, 'end': HEALTH_MILESTONE_SIZE,
                    'current': 0, 'remaining': HEALTH_MILESTONE_SIZE,
                    'progress_in_milestone': 0,
                },
            }

        total_steps = float(total_steps)
        progress_percent = round(total_steps / HEALTH_TARGET_STEPS * 100, 2)

        completed = int(total_steps // HEALTH_MILESTONE_SIZE)
        current_milestone_num = min(completed + 1, HEALTH_TOTAL_MILESTONES)
        in_milestone = float(total_steps % HEALTH_MILESTONE_SIZE)
        next_remaining = HEALTH_MILESTONE_SIZE - in_milestone

        days_active = HealthStatsService._count_active_days()
        max_daily = float(qs.aggregate(m=models.Max('total'))['m'] or 0)

        # 日均步数
        if days_active > 0:
            daily_avg = round(total_steps / days_active, 0)
        else:
            daily_avg = 0

        # 最长连续运动天数
        longest_streak = HealthStatsService._calc_longest_streak()

        # 本月步数
        now = timezone.now()
        this_month_steps = HealthStatsService._get_month_steps(now.year, now.month)

        prediction = HealthStatsService._calc_prediction(total_steps, daily_avg)

        return {
            'total_steps': total_steps,
            'target_steps': HEALTH_TARGET_STEPS,
            'progress_percent': progress_percent,
            'completed_milestones': completed,
            'total_milestones': HEALTH_TOTAL_MILESTONES,
            'next_milestone_distance': next_remaining,
            'daily_avg': daily_avg,
            'days_active': days_active,
            'max_daily': max_daily,
            'longest_streak': longest_streak,
            'this_month_steps': this_month_steps,
            'current_milestone': {
                'number': current_milestone_num,
                'start': completed * HEALTH_MILESTONE_SIZE,
                'end': current_milestone_num * HEALTH_MILESTONE_SIZE,
                'current': total_steps,
                'remaining': next_remaining,
                'progress_in_milestone': round(
                    in_milestone / HEALTH_MILESTONE_SIZE * 100, 2
                ),
            },
            'prediction': prediction,
        }

    @staticmethod
    def get_milestones() -> list:
        """获取50个里程碑完成状态"""
        total_steps = float(
            HealthRecord.objects.all().aggregate(s=models.Sum('total'))['s'] or 0
        )
        completed = int(total_steps // HEALTH_MILESTONE_SIZE)

        # 获取里程碑达成日期（每天累计步数 ≥ milestone 阈值的最小日期）
        milestone_dates = HealthStatsService._calc_milestone_dates(completed)

        result = []
        for i in range(1, HEALTH_TOTAL_MILESTONES + 1):
            start = (i - 1) * HEALTH_MILESTONE_SIZE
            end = i * HEALTH_MILESTONE_SIZE
            is_completed = i <= completed
            is_current = i == completed + 1 or (i == completed and completed == HEALTH_TOTAL_MILESTONES)

            entry = {
                'number': i,
                'start': start,
                'end': end,
                'is_completed': is_completed,
                'is_current': is_current,
            }

            if is_completed and i in milestone_dates:
                entry['completed_date'] = milestone_dates[i]['date']
                entry['days_taken'] = milestone_dates[i]['days_taken']

            if is_current and not is_completed:
                entry['current_progress'] = float(total_steps % HEALTH_MILESTONE_SIZE)
                entry['progress_percent'] = round(
                    (total_steps - start) / HEALTH_MILESTONE_SIZE * 100, 2
                )

            result.append(entry)

        return {'milestones': result, 'total_steps': total_steps}

    @staticmethod
    def get_daily_trend(days: int = 30) -> list:
        """获取每日步数趋势"""
        rows = (
            HealthRecord.objects.annotate(d=Cast('time', DateField()))
            .values('d')
            .annotate(total_steps=models.Sum('total'), record_count=models.Count('hid'))
            .order_by('d')
        )
        data = {
            r['d']: {'total_steps': float(r['total_steps'] or 0), 'record_count': r['record_count']}
            for r in rows if r['d']
        }

        end = timezone.now()
        start = end - timedelta(days=days)
        result = []
        for i in range(days + 1):
            day = (start + timedelta(days=i)).date()
            entry = data.get(day, {'total_steps': 0, 'record_count': 0})
            result.append({
                'date': day.isoformat(),
                'total_steps': entry['total_steps'],
                'record_count': entry['record_count'],
            })

        return result

    @staticmethod
    def get_calendar(year: int | None = None, month: int | None = None) -> list:
        """获取日历热力图数据"""
        qs = HealthRecord.objects.all()
        if year and month:
            start = date(year, month, 1)
            end = date(year + (month == 12), month % 12 + 1, 1)
            qs = qs.filter(time__gte=start, time__lt=end)
        elif year:
            qs = qs.filter(time__gte=date(year, 1, 1), time__lt=date(year + 1, 1, 1))
        rows = (
            qs.annotate(d=Cast('time', DateField()))
            .values('d')
            .annotate(total_steps=models.Sum('total'), record_count=models.Count('hid'))
            .order_by('d')
        )
        return [
            {
                'date': r['d'].isoformat() if r['d'] else '',
                'total_steps': float(r['total_steps'] or 0),
                'record_count': r['record_count'],
            }
            for r in rows if r['d']
        ]

    @staticmethod
    def get_milestone_timeline() -> list:
        """获取里程碑达成时间线"""
        total_steps = float(
            HealthRecord.objects.all().aggregate(s=models.Sum('total'))['s'] or 0
        )
        completed = int(total_steps // HEALTH_MILESTONE_SIZE)
        milestone_dates = HealthStatsService._calc_milestone_dates(completed)

        result = []
        for i in range(1, completed + 1):
            info = milestone_dates.get(i, {})
            prev_date = milestone_dates.get(i - 1, {}).get('date')
            prev_date_obj = datetime.strptime(prev_date, '%Y-%m-%d').date() if prev_date else None

            entry = {
                'number': i,
                'start': (i - 1) * HEALTH_MILESTONE_SIZE,
                'end': i * HEALTH_MILESTONE_SIZE,
                'completed_date': info.get('date', ''),
                'days_taken': info.get('days_taken', 0),
            }

            if prev_date_obj and info.get('date'):
                cur = datetime.strptime(info['date'], '%Y-%m-%d').date()
                entry['days_since_previous'] = (cur - prev_date_obj).days
            else:
                entry['days_since_previous'] = None

            result.append(entry)

        return result

    @staticmethod
    def get_type_stats() -> list:
        """获取运动类型占比统计"""
        qs = HealthRecord.objects.values('htype').annotate(
            total_steps=models.Sum('total'),
            count=models.Count('hid'),
        ).order_by('-total_steps')

        grand_total = float(
            HealthRecord.objects.all().aggregate(s=models.Sum('total'))['s'] or 1
        )

        return [
            {
                'htype': t['htype'],
                'label': HTYPE_LABELS.get(t['htype'], '未知'),
                'total_steps': float(t['total_steps'] or 0),
                'count': t['count'],
                'percentage': round(float(t['total_steps'] or 0) / grand_total * 100, 2),
            }
            for t in qs if t['htype']
        ]

    @staticmethod
    def get_yearly_comparison() -> list:
        """获取年度步数对比"""
        qs = HealthRecord.objects.values('years').annotate(
            total_steps=models.Sum('total'),
            count=models.Count('hid'),
            avg_daily=models.Avg('total'),
        ).order_by('-years')

        return [
            {
                'year': t['years'],
                'total_steps': float(t['total_steps'] or 0),
                'count': t['count'],
                'avg_daily': round(float(t['avg_daily'] or 0), 0),
            }
            for t in qs if t['years']
        ]

    # ─── 内部辅助方法 ───

    @staticmethod
    def _count_active_days() -> int:
        """统计有运动记录的天数"""
        return HealthRecord.objects.annotate(d=Cast('time', DateField())).values('d').distinct().count()

    @staticmethod
    def _get_month_steps(year: int, month: int) -> float:
        """获取指定月份的总步数"""
        start = date(year, month, 1)
        end = date(year + (month == 12), month % 12 + 1, 1)
        total = HealthRecord.objects.filter(time__gte=start, time__lt=end).aggregate(
            s=models.Sum('total')
        )['s'] or 0
        return float(total)

    @staticmethod
    def _calc_longest_streak() -> int:
        """计算最长连续运动天数"""
        dates = list(
            HealthRecord.objects.annotate(d=Cast('time', DateField()))
            .values_list('d', flat=True).distinct().order_by('d')
        )

        if not dates:
            return 0

        max_streak = 1
        current_streak = 1
        prev = dates[0]

        for d in dates[1:]:
            if (d - prev).days == 1:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            elif (d - prev).days > 1:
                current_streak = 1
            prev = d

        return max_streak

    @staticmethod
    def _calc_prediction(total_steps: float, daily_avg: float) -> dict | None:
        """计算目标预测"""
        if daily_avg <= 0:
            return None

        remaining = HEALTH_TARGET_STEPS - total_steps
        days_needed = remaining / daily_avg
        target_date = timezone.now() + timedelta(days=int(days_needed))

        return {
            'target_date': target_date.strftime('%Y-%m-%d'),
            'days_remaining': int(days_needed),
            'daily_needed': round(daily_avg, 0),
        }

    @staticmethod
    def _calc_milestone_dates(completed: int) -> dict:
        """计算各里程碑达成日期"""
        rows = (
            HealthRecord.objects.annotate(d=Cast('time', DateField()))
            .values('d')
            .annotate(daily=models.Sum('total'))
            .order_by('d')
        )
        rows = [{'time__date': r['d'], 'daily': r['daily']} for r in rows if r['d']]

        milestone_dates = {}
        cumulative = 0.0
        prev_milestone = 0
        first_date = None

        for row in rows:
            date, daily_total = row['time__date'], row['daily']
            daily = float(daily_total or 0)
            if first_date is None:
                first_date = date

            cumulative += daily

            current_milestone = int(cumulative // HEALTH_MILESTONE_SIZE)
            for m in range(prev_milestone + 1, current_milestone + 1):
                if m > completed:
                    break
                milestone_dates[m] = {
                    'date': date.isoformat(),
                    'days_taken': (date - first_date).days if first_date else 0,
                }
            prev_milestone = current_milestone

        return milestone_dates

    @staticmethod
    def _calc_total_steps_years() -> dict:
        """计算每年的总步数（按月统计结果）"""
        qs = HealthRecord.objects.values('years').annotate(
            total_steps=models.Sum('total'),
            count=models.Count('hid'),
        ).order_by('years')

        result = {}
        for entry in qs:
            if entry['years']:
                result[entry['years']] = {
                    'total_steps': float(entry['total_steps'] or 0),
                    'count': entry['count'],
                }
        return result


