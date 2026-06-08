from django.db import connection

from ..constants import ENERGY_REVIEW_DAYS, ENERGY_THRESHOLDS


class QualityService:
    """关系质量诊断服务"""

    @staticmethod
    def update_relationship_quality(relationship_id: int, user_id: int) -> str | None:
        """根据最近N条互动的平均能量分，更新关系质量"""
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT energy_score FROM relationship_interaction
            WHERE relationship_id = %s AND user_id = %s
            ORDER BY happened_at DESC
            LIMIT %s
            """,
            [relationship_id, user_id, ENERGY_REVIEW_DAYS],
        )
        scores = [r[0] for r in cursor.fetchall()]
        if not scores:
            return None

        avg_energy = sum(scores) / len(scores)

        if avg_energy >= ENERGY_THRESHOLDS['nourishing']:
            new_quality = 'nourishing'
        elif avg_energy >= ENERGY_THRESHOLDS['neutral']:
            new_quality = 'neutral'
        elif avg_energy >= ENERGY_THRESHOLDS['draining']:
            new_quality = 'draining'
        else:
            new_quality = 'toxic'

        cursor.execute(
            "UPDATE relationship_relationship SET current_quality = %s, updated_at = NOW() WHERE id = %s",
            [new_quality, relationship_id],
        )
        return new_quality

    @staticmethod
    def recalculate_all(user_id: int = 1) -> int:
        """重新计算所有关系质量"""
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id FROM relationship_relationship WHERE user_id = %s", [user_id]
        )
        ids = [r[0] for r in cursor.fetchall()]
        for rid in ids:
            QualityService.update_relationship_quality(rid, user_id)
        return len(ids)
