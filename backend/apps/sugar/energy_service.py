"""能量清单业务逻辑 — 自动同步奖励池（双倍快乐）"""

from datetime import datetime

from django.db import models, transaction as db_transaction

from apps.reward.services import RewardPoolService


class EnergyService:
    """能量清单业务逻辑"""

    def __init__(self):
        self.reward_service = RewardPoolService()

    @db_transaction.atomic
    def complete_task(self, *, template_id: int | None, content: str,
                      energy_gained: int, is_custom: bool,
                      completed_at: datetime | None = None,
                      user_id: int = 1) -> dict:
        """完成能量清单任务 → 记录 + 双倍奖励"""
        from .models import EnergyLog, EnergyTemplate

        if completed_at is None:
            completed_at = datetime.now()

        log = EnergyLog.objects.create(
            template_id=template_id,
            content=content,
            energy_gained=energy_gained,
            is_custom=is_custom,
            completed_at=completed_at,
            user_id=user_id,
        )

        # 双倍快乐分 → 奖励池
        reward_amount = energy_gained * 2
        self.reward_service.add_reward(
            source_id=log.id,
            source_type='energy',
            amount=reward_amount,
            transaction_type='energy_complete',
            description=f'完成能量清单：{content}，获得{reward_amount}元奖励（双倍快乐）',
        )

        log.reward_processed = True
        log.save(update_fields=['reward_processed'])

        self._update_daily_stats(user_id=user_id, stat_date=completed_at.date())

        return {
            'id': log.id,
            'content': log.content,
            'energy_gained': log.energy_gained,
            'reward_amount': float(reward_amount),
            'completed_at': log.completed_at.isoformat(),
        }

    @db_transaction.atomic
    def create_custom_template(self, *, content: str, default_energy: int,
                                category: str, icon: str = '✨',
                                estimated_seconds: int = 60,
                                user_id: int = 1) -> 'EnergyTemplate':
        """用户自定义能量清单模板"""
        from .models import EnergyTemplate

        return EnergyTemplate.objects.create(
            content=content,
            default_energy=default_energy,
            category=category,
            icon=icon,
            estimated_seconds=estimated_seconds,
            is_system=False,
            user_id=user_id,
            is_active=True,
        )

    @staticmethod
    def get_templates(user_id: int = 1) -> list:
        """获取可用模板列表（系统预设 + 用户自定义）"""
        from .models import EnergyTemplate

        return list(EnergyTemplate.objects.filter(
            is_active=True,
        ).filter(
            models.Q(is_system=True) | models.Q(user_id=user_id),
        ).order_by('sort_order', 'id'))

    @staticmethod
    def get_daily_completed(stat_date: datetime.date | None = None,
                            user_id: int = 1) -> list:
        """获取指定日期的已完成列表"""
        from .models import EnergyLog

        if stat_date is None:
            stat_date = datetime.now().date()

        return list(EnergyLog.objects.filter(
            user_id=user_id,
            completed_at__date=stat_date,
        ).select_related('template').order_by('completed_at'))

    @staticmethod
    def get_stats(user_id: int = 1) -> dict:
        """获取能量统计"""
        from django.db.models import Count, Sum
        from django.db.models.functions import TruncDate

        from .models import EnergyLog

        today = datetime.now().date()

        # 今日统计
        today_stats = EnergyLog.objects.filter(
            user_id=user_id, completed_at__date=today,
        ).aggregate(
            total_energy=Sum('energy_gained'),
            completed_count=Count('id'),
        )

        # 本周统计
        week_start = today.replace(day=today.day - today.weekday())
        week_stats = EnergyLog.objects.filter(
            user_id=user_id, completed_at__date__gte=week_start,
        ).aggregate(
            total_energy=Sum('energy_gained'),
            completed_count=Count('id'),
        )

        # 本月统计
        month_stats = EnergyLog.objects.filter(
            user_id=user_id,
            completed_at__year=today.year,
            completed_at__month=today.month,
        ).aggregate(
            total_energy=Sum('energy_gained'),
            completed_count=Count('id'),
        )

        # 连续打卡天数
        streak = EnergyService._calc_streak(user_id, today)

        return {
            'today': {
                'total_energy': today_stats['total_energy'] or 0,
                'completed_count': today_stats['completed_count'] or 0,
            },
            'week': {
                'total_energy': week_stats['total_energy'] or 0,
                'completed_count': week_stats['completed_count'] or 0,
            },
            'month': {
                'total_energy': month_stats['total_energy'] or 0,
                'completed_count': month_stats['completed_count'] or 0,
            },
            'streak': {
                'current': streak['current'],
                'longest': streak['longest'],
            },
        }

    @staticmethod
    def get_energy_trend(days: int = 30, user_id: int = 1) -> list:
        """获取能量趋势（每日汇总）"""
        from datetime import timedelta

        from django.db.models import Sum
        from django.db.models.functions import TruncDate

        from .models import EnergyLog

        start_date = datetime.now().date() - timedelta(days=days - 1)

        daily = (
            EnergyLog.objects
            .filter(user_id=user_id, completed_at__date__gte=start_date)
            .annotate(date=TruncDate('completed_at'))
            .values('date')
            .annotate(total_energy=Sum('energy_gained'))
            .order_by('date')
        )

        daily_map = {d['date']: d['total_energy'] for d in daily}
        result = []
        for i in range(days):
            d = start_date + timedelta(days=i)
            result.append({
                'date': d.isoformat(),
                'total_energy': daily_map.get(d, 0),
            })
        return result

    @staticmethod
    def _calc_streak(user_id: int, today: datetime.date) -> dict:
        """计算连续打卡天数"""
        from django.db.models import Count
        from django.db.models.functions import TruncDate

        from .models import EnergyLog

        # 获取所有有完成的日期（去重）
        dates = set(
            EnergyLog.objects
            .filter(user_id=user_id)
            .annotate(date=TruncDate('completed_at'))
            .values_list('date', flat=True)
            .distinct()
            .order_by('-date')
        )

        if not dates:
            return {'current': 0, 'longest': 0}

        # 计算当前连续
        current = 0
        check = today
        while check in dates:
            current += 1
            check -= datetime.timedelta(days=1)

        # 计算最长连续
        sorted_dates = sorted(dates)
        longest = 0
        streak = 1
        for i in range(1, len(sorted_dates)):
            if (sorted_dates[i] - sorted_dates[i - 1]).days == 1:
                streak += 1
            else:
                longest = max(longest, streak)
                streak = 1
        longest = max(longest, streak)

        return {'current': current, 'longest': longest}

    @staticmethod
    @db_transaction.atomic
    def _update_daily_stats(user_id: int, stat_date: datetime.date) -> None:
        """更新每日能量统计缓存"""
        from django.db.models import Count, Sum

        from .models import EnergyDailyStats, EnergyLog

        agg = EnergyLog.objects.filter(
            user_id=user_id,
            completed_at__date=stat_date,
        ).aggregate(
            total_energy=Sum('energy_gained'),
            completed_count=Count('id'),
        )

        EnergyDailyStats.objects.update_or_create(
            user_id=user_id,
            stat_date=stat_date,
            defaults={
                'total_energy': agg['total_energy'] or 0,
                'completed_count': agg['completed_count'] or 0,
            },
        )
