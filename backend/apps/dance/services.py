from collections import defaultdict
from datetime import date, timedelta

from django.db import models
from django.utils import timezone

from .models import DanceRecord


class DanceStatsService:
    """舞蹈统计服务"""

    @staticmethod
    def get_overview() -> dict:
        qs = DanceRecord.objects.all()
        total_count = qs.count()
        if total_count == 0:
            return {
                'total_count': 0, 'total_teachers': 0, 'total_types': 0,
                'avg_score': 0, 'max_score': 0,
                'this_month_count': 0, 'last_month_count': 0,
                'monthly_change': 0,
                'favorite_teacher': '', 'favorite_teacher_count': 0,
                'most_type': '', 'most_type_count': 0,
            }

        avg_score = qs.aggregate(a=models.Avg('score'))['a'] or 0
        max_score = qs.aggregate(m=models.Max('score'))['m'] or 0
        total_teachers = qs.values('teacher_name').distinct().count()
        total_types = qs.values('dance_type').distinct().count()

        now = timezone.now()
        this_month = qs.filter(year=now.year, month=now.month).count()
        last_month = now.month - 1 or 12
        last_month_year = now.year if now.month > 1 else now.year - 1
        last_month_count = qs.filter(year=last_month_year, month=last_month).count()
        monthly_change = round(
            ((this_month - last_month_count) / last_month_count) * 100, 1
        ) if last_month_count > 0 else 0

        teacher_stats = qs.values('teacher_name').annotate(
            count=models.Count('id'),
        ).order_by('-count')
        favorite = teacher_stats.first()
        favorite_teacher = favorite['teacher_name'] if favorite else ''
        favorite_teacher_count = favorite['count'] if favorite else 0

        type_stats = qs.values('dance_type').annotate(
            count=models.Count('id'),
        ).order_by('-count')
        most_type = type_stats.first()
        most_type_name = most_type['dance_type'] if most_type else ''
        most_type_count = most_type['count'] if most_type else 0

        return {
            'total_count': total_count,
            'total_teachers': total_teachers,
            'total_types': total_types,
            'avg_score': round(float(avg_score), 1),
            'max_score': max_score,
            'this_month_count': this_month,
            'last_month_count': last_month_count,
            'monthly_change': monthly_change,
            'favorite_teacher': favorite_teacher,
            'favorite_teacher_count': favorite_teacher_count,
            'most_type': most_type_name,
            'most_type_count': most_type_count,
        }

    @staticmethod
    def get_trend(year: int | None = None) -> dict:
        qs = DanceRecord.objects.all()
        if year:
            qs = qs.filter(year=year)

        monthly = []
        months = qs.values('month').annotate(
            count=models.Count('id'),
            avg_score=models.Avg('score'),
        ).order_by('month')

        month_map = {m['month']: m for m in months}
        for m in range(1, 13):
            data = month_map.get(m, {})
            monthly.append({
                'month': m,
                'count': data.get('count', 0),
                'avg_score': round(float(data.get('avg_score') or 0), 1),
            })

        # Determine trend
        values = [m['count'] for m in monthly if m['count'] > 0]
        if len(values) >= 3:
            first_half = sum(values[:len(values) // 2]) / (len(values) // 2)
            second_half = sum(values[-(len(values) // 2):]) / (len(values) // 2)
            if second_half > first_half * 1.1:
                trend = 'increasing'
            elif second_half < first_half * 0.9:
                trend = 'decreasing'
            else:
                trend = 'stable'
        else:
            trend = 'stable'

        return {'monthly': monthly, 'trend': trend}

    @staticmethod
    def get_teachers() -> list:
        qs = DanceRecord.objects.values('teacher_name').annotate(
            count=models.Count('id'),
            avg_score=models.Avg('score'),
            avg_energy=models.Avg('energy_level'),
        ).order_by('-count')

        return [
            {
                'name': t['teacher_name'] or '未知',
                'count': t['count'],
                'avg_score': round(float(t['avg_score'] or 0), 1),
                'avg_energy': round(float(t['avg_energy'] or 0), 1),
            }
            for t in qs if t['teacher_name']
        ]

    @staticmethod
    def get_types() -> list:
        qs = DanceRecord.objects.values('dance_type').annotate(
            count=models.Count('id'),
            avg_score=models.Avg('score'),
        ).order_by('-count')

        return [
            {
                'name': t['dance_type'],
                'count': t['count'],
                'avg_score': round(float(t['avg_score'] or 0), 1),
            }
            for t in qs if t['dance_type']
        ]

    @staticmethod
    def get_score_trend() -> list:
        """按月聚合评分趋势"""
        qs = DanceRecord.objects.values('year', 'month').annotate(
            avg_score=models.Avg('score'),
            count=models.Count('id'),
        ).order_by('year', 'month')

        return [
            {
                'period': f"{d['year']}-{d['month']:02d}",
                'avg_score': round(float(d['avg_score'] or 0), 1),
                'count': d['count'],
            }
            for d in qs
        ]

    @staticmethod
    def get_calendar(year: int | None = None, month: int | None = None) -> list:
        qs = DanceRecord.objects.all()
        if year:
            qs = qs.filter(year=year)
        if month:
            qs = qs.filter(month=month)

        days = qs.values('study_time', 'dance_type', 'score', 'teacher_name', 'difficulty').order_by('study_time')

        result = []
        for d in days:
            result.append({
                'date': d['study_time'].isoformat() if d['study_time'] else '',
                'dance_type': d['dance_type'],
                'score': d['score'],
                'teacher': d['teacher_name'],
                'difficulty': d['difficulty'],
            })
        return result
