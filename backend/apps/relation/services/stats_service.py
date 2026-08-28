from datetime import timedelta

from django.db.models import Avg, Count, DateField, Max, Q, Sum
from django.db.models.functions import Cast, TruncMonth
from django.utils import timezone

from ..constants import DUE_REMINDER_DAYS
from ..models import Interaction, Relationship


class StatsService:
    """关系统计服务"""

    @staticmethod
    def get_overview(user_id: int = 1) -> dict:
        """获取统计总览"""
        total = Relationship.objects.filter(user_id=user_id).count()

        # 按平均能量分计算关系类型计数
        type_counts = Relationship.objects.filter(user_id=user_id).annotate(
            avg_energy=Avg('interactions__energy_score'),
        ).aggregate(
            nourishing=Count('pk', filter=Q(avg_energy__gte=3)),
            neutral=Count('pk', filter=Q(avg_energy__gte=0, avg_energy__lt=3)),
            draining=Count('pk', filter=Q(avg_energy__gte=-3, avg_energy__lt=0)),
            toxic=Count('pk', filter=Q(avg_energy__lt=-3)),
        )
        nourishing = type_counts['nourishing']
        neutral = type_counts['neutral']
        draining = type_counts['draining']
        harmful = type_counts['toxic']

        now = timezone.now()
        first_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        next_month = first_this_month.replace(month=first_this_month.month % 12 + 1) if first_this_month.month < 12 else first_this_month.replace(year=first_this_month.year + 1, month=1)
        monthly_interactions = Interaction.objects.filter(
            user_id=user_id,
            happened_at__gte=first_this_month,
            happened_at__lt=next_month,
        ).count()

        total_energy = round(float(
            Interaction.objects.filter(user_id=user_id).aggregate(s=Sum('energy_score'))['s'] or 0
        ), 1)

        # 上月互动数（用于环比）
        last_month_start = (first_this_month - timedelta(days=1)).replace(day=1)
        last_month = Interaction.objects.filter(
            user_id=user_id,
            happened_at__gte=last_month_start,
            happened_at__lt=first_this_month,
        ).count()

        monthly_change = (
            round((monthly_interactions - last_month) / last_month * 100, 1)
            if last_month > 0
            else 0
        )

        return {
            'total_relationships': total,
            'nourishing_count': nourishing,
            'neutral_count': neutral,
            'draining_count': draining,
            'harmful_count': harmful,
            'monthly_interactions': monthly_interactions,
            'last_month_interactions': last_month,
            'monthly_change': monthly_change,
            'total_energy': total_energy,
        }

    @staticmethod
    def get_quality_distribution(user_id: int = 1) -> list:
        """获取关系质量分布"""
        labels = {
            'nourishing': '滋养型',
            'neutral': '中性',
            'draining': '消耗型',
            'toxic': '有害型',
        }
        rows = (
            Relationship.objects.filter(user_id=user_id)
            .values('current_quality')
            .annotate(count=Count('pk'))
            .order_by('-count')
        )
        return [
            {'quality': r['current_quality'], 'count': r['count'], 'label': labels.get(r['current_quality'], r['current_quality'])}
            for r in rows
        ]

    @staticmethod
    def get_energy_trend(relationship_id: int | None = None, user_id: int = 1, months: int = 6) -> list:
        """获取能量趋势（按月聚合）"""
        since = timezone.now() - timedelta(days=30 * months)
        qs = (
            Interaction.objects.filter(user_id=user_id, happened_at__gte=since, happened_at__isnull=False)
            .annotate(period=TruncMonth(Cast('happened_at', DateField())))
            .values('period')
            .annotate(total_energy=Sum('energy_score'), count=Count('pk'))
            .order_by('period')
        )
        if relationship_id:
            qs = qs.filter(relationship_id=relationship_id)

        return [
            {
                'period': r['period'].strftime('%Y-%m'),
                'total_energy': round(float(r['total_energy'] or 0), 1),
                'count': r['count'],
            }
            for r in qs
        ]

    @staticmethod
    def get_interaction_frequency(user_id: int = 1, months: int = 6) -> list:
        """获取互动频率（按月）"""
        since = timezone.now() - timedelta(days=30 * months)
        rows = (
            Interaction.objects.filter(user_id=user_id, happened_at__gte=since, happened_at__isnull=False)
            .annotate(period=TruncMonth(Cast('happened_at', DateField())))
            .values('period')
            .annotate(
                count=Count('pk'),
                unique_people=Count('relationship_id', distinct=True),
            )
            .order_by('period')
        )
        return [
            {'period': r['period'].strftime('%Y-%m'), 'count': r['count'], 'unique_people': r['unique_people']}
            for r in rows
        ]

    @staticmethod
    def get_due_reminders(user_id: int = 1) -> list:
        """获取待提醒关系（超过30天未互动的active状态关系）"""
        cutoff = timezone.now() - timedelta(days=DUE_REMINDER_DAYS)
        rows = (
            Relationship.objects.filter(user_id=user_id, current_status='active')
            .annotate(last_interaction=Max('interactions__happened_at'))
            .filter(Q(last_interaction__isnull=True) | Q(last_interaction__lte=cutoff))
            .order_by('last_interaction')
        )
        now = timezone.now()
        results = []
        for r in rows:
            results.append({
                'id': r.id,
                'name': r.name,
                'quality': r.current_quality,
                'tags': r.tags or '',
                'last_interaction': r.last_interaction.isoformat() if r.last_interaction else None,
                'days_since': (now - r.last_interaction).days if r.last_interaction else None,
            })
        return results
