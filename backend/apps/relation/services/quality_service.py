from django.utils import timezone

from ..constants import ENERGY_REVIEW_DAYS, ENERGY_THRESHOLDS
from ..models import Interaction, Relationship


class QualityService:
    """关系质量诊断服务"""

    @staticmethod
    def update_relationship_quality(relationship_id: int, user_id: int) -> str | None:
        """根据最近N条互动的平均能量分，更新关系质量"""
        scores = list(
            Interaction.objects.filter(
                relationship_id=relationship_id, user_id=user_id
            )
            .order_by('-happened_at')
            .values_list('energy_score', flat=True)[:ENERGY_REVIEW_DAYS]
        )
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

        Relationship.objects.filter(id=relationship_id).update(
            current_quality=new_quality,
            updated_at=timezone.now(),
        )
        return new_quality

    @staticmethod
    def recalculate_all(user_id: int = 1) -> int:
        """重新计算所有关系质量"""
        ids = list(
            Relationship.objects.filter(user_id=user_id).values_list('id', flat=True)
        )
        for rid in ids:
            QualityService.update_relationship_quality(rid, user_id)
        return len(ids)
