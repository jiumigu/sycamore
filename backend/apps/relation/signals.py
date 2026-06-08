from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Interaction
from .services.quality_service import QualityService


@receiver(post_save, sender=Interaction)
def interaction_saved(sender, instance, created, **kwargs):
    """互动记录保存后，更新关系质量"""
    if instance.relationship_id and instance.user_id:
        QualityService.update_relationship_quality(
            instance.relationship_id, instance.user_id,
        )


@receiver(post_delete, sender=Interaction)
def interaction_deleted(sender, instance, **kwargs):
    """互动记录删除后，更新关系质量"""
    if instance.relationship_id and instance.user_id:
        QualityService.update_relationship_quality(
            instance.relationship_id, instance.user_id,
        )
