from decimal import Decimal

from django.db import transaction

from apps.reward.services import RewardPoolService


def _calculate_reward_amount(level_of_happiness) -> Decimal:
    """根据快乐程度计算奖励金额（5-20分制）"""
    v = float(level_of_happiness)
    if v <= 7:
        return Decimal('1')
    elif v <= 10:
        return Decimal('3')
    elif v <= 13:
        return Decimal('5')
    elif v <= 16:
        return Decimal('8')
    return Decimal('10')


class SugarRecordService:
    """小确幸业务逻辑 — 自动同步奖励池"""

    def __init__(self):
        self.reward_service = RewardPoolService()

    @transaction.atomic
    def create(self, **kwargs) -> 'SugarRecord':
        """创建小确幸记录并同步奖励池"""
        from .models import SugarRecord

        level = kwargs['level_of_happiness']
        reward = _calculate_reward_amount(level)

        record = SugarRecord.objects.create(reward_amount=reward, **kwargs)

        self.reward_service.add_reward(
            source_id=record.s_id,
            source_type='sugar',
            amount=reward,
            transaction_type='sugar_create',
            description=f'新增小确幸：{record.title}，获得{reward}元奖励',
        )

        record.reward_synced = True
        record.save(update_fields=['reward_synced'])

        return record

    @transaction.atomic
    def update(self, s_id: int, **kwargs) -> 'SugarRecord':
        """更新小确幸，快乐程度变化时调整奖励池"""
        from .models import SugarRecord

        record = SugarRecord.objects.get(s_id=s_id)
        old_amount = record.reward_amount

        for key, value in kwargs.items():
            setattr(record, key, value)

        if 'level_of_happiness' in kwargs:
            new_amount = _calculate_reward_amount(record.level_of_happiness)
            record.reward_amount = new_amount
            record.save()

            delta = new_amount - old_amount
            if delta != 0:
                desc = f'小确幸快乐程度变化：{record.title}，{old_amount}→{new_amount}'
                if delta > 0:
                    self.reward_service.adjust_reward(
                        source_id=s_id, source_type='sugar',
                        delta=delta, description=desc,
                    )
                else:
                    self.reward_service.deduct_reward(
                        source_id=s_id, source_type='sugar',
                        amount=abs(delta), reason='sugar_update',
                        description=desc,
                    )
        else:
            record.save()

        return record

    @transaction.atomic
    def delete(self, s_id: int) -> None:
        """删除小确幸并扣回奖励"""
        from .models import SugarRecord

        record = SugarRecord.objects.get(s_id=s_id)

        if record.reward_synced and record.reward_amount > 0:
            self.reward_service.deduct_reward(
                source_id=s_id, source_type='sugar',
                amount=record.reward_amount, reason='sugar_delete',
                description=f'删除小确幸：{record.title}，扣回{record.reward_amount}元',
            )

        record.delete()
