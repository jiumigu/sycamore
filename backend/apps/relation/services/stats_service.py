from django.db import connection
from django.db.models import Avg, Count, Q

from ..constants import DUE_REMINDER_DAYS
from ..models import Relationship


class StatsService:
    """关系统计服务"""

    @staticmethod
    def get_overview(user_id: int = 1) -> dict:
        """获取统计总览"""
        cursor = connection.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM relationship_relationship WHERE user_id = %s",
            [user_id],
        )
        total = cursor.fetchone()[0]

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

        cursor.execute(
            "SELECT COUNT(*) FROM relationship_interaction WHERE user_id = %s AND DATE_FORMAT(happened_at, '%%Y-%%m') = DATE_FORMAT(NOW(), '%%Y-%%m')",
            [user_id],
        )
        monthly_interactions = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COALESCE(SUM(energy_score), 0) FROM relationship_interaction WHERE user_id = %s",
            [user_id],
        )
        total_energy = round(float(cursor.fetchone()[0]), 1)

        # 上月互动数（用于环比）
        cursor.execute(
            """
            SELECT COUNT(*) FROM relationship_interaction
            WHERE user_id = %s
            AND DATE_FORMAT(happened_at, '%%Y-%%m') = DATE_FORMAT(DATE_SUB(NOW(), INTERVAL 1 MONTH), '%%Y-%%m')
            """,
            [user_id],
        )
        last_month = cursor.fetchone()[0]

        monthly_change = (
            round(
                (monthly_interactions - last_month) / last_month * 100, 1
            )
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
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT current_quality, COUNT(*) as cnt
            FROM relationship_relationship
            WHERE user_id = %s
            GROUP BY current_quality
            ORDER BY cnt DESC
            """,
            [user_id],
        )
        return [
            {'quality': r[0], 'count': r[1], 'label': dict(
                (('nourishing', '滋养型'), ('neutral', '中性'), ('draining', '消耗型'), ('toxic', '有害型'))
            ).get(r[0], r[0])}
            for r in cursor.fetchall()
        ]

    @staticmethod
    def get_energy_trend(relationship_id: int | None = None, user_id: int = 1, months: int = 6) -> list:
        """获取能量趋势（按月聚合）"""
        cursor = connection.cursor()

        if relationship_id:
            cursor.execute(
                """
                SELECT DATE_FORMAT(happened_at, '%%Y-%%m') as period,
                       SUM(energy_score) as total_energy,
                       COUNT(*) as count
                FROM relationship_interaction
                WHERE relationship_id = %s AND user_id = %s
                  AND happened_at >= DATE_SUB(NOW(), INTERVAL %s MONTH)
                GROUP BY period
                ORDER BY period ASC
                """,
                [relationship_id, user_id, months],
            )
        else:
            cursor.execute(
                """
                SELECT DATE_FORMAT(happened_at, '%%Y-%%m') as period,
                       SUM(energy_score) as total_energy,
                       COUNT(*) as count
                FROM relationship_interaction
                WHERE user_id = %s
                  AND happened_at >= DATE_SUB(NOW(), INTERVAL %s MONTH)
                GROUP BY period
                ORDER BY period ASC
                """,
                [user_id, months],
            )

        return [
            {
                'period': r[0],
                'total_energy': round(float(r[1] or 0), 1),
                'count': r[2],
            }
            for r in cursor.fetchall()
        ]

    @staticmethod
    def get_interaction_frequency(user_id: int = 1, months: int = 6) -> list:
        """获取互动频率（按月）"""
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT DATE_FORMAT(happened_at, '%%Y-%%m') as period,
                   COUNT(*) as count,
                   COUNT(DISTINCT relationship_id) as unique_people
            FROM relationship_interaction
            WHERE user_id = %s
              AND happened_at >= DATE_SUB(NOW(), INTERVAL %s MONTH)
            GROUP BY period
            ORDER BY period ASC
            """,
            [user_id, months],
        )
        return [
            {'period': r[0], 'count': r[1], 'unique_people': r[2]}
            for r in cursor.fetchall()
        ]

    @staticmethod
    def get_due_reminders(user_id: int = 1) -> list:
        """获取待提醒关系（超过30天未互动的active状态关系）"""
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT r.id, r.name, r.current_quality, r.tags,
                   MAX(i.happened_at) as last_interaction,
                   DATEDIFF(NOW(), MAX(i.happened_at)) as days_since
            FROM relationship_relationship r
            LEFT JOIN relationship_interaction i ON r.id = i.relationship_id
            WHERE r.user_id = %s AND r.current_status = 'active'
            GROUP BY r.id
            HAVING last_interaction IS NULL OR days_since >= %s
            ORDER BY last_interaction ASC
            """,
            [user_id, DUE_REMINDER_DAYS],
        )
        results = []
        for r in cursor.fetchall():
            results.append({
                'id': r[0],
                'name': r[1],
                'quality': r[2],
                'tags': r[3] or '',
                'last_interaction': r[4].isoformat() if r[4] else None,
                'days_since': r[5] if r[4] else None,
            })
        return results
