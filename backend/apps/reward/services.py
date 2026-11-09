"""奖励池服务 — 增删改查与统计"""

from datetime import datetime
from decimal import Decimal

from django.db import transaction as db_transaction

from .models import GiftList, RewardPool, RewardTransaction


def _to_decimal(value) -> Decimal:
    """金额归一 —— 写进奖励池的**唯一入口**。

    `RewardPool.balance / total_earned` 是 DecimalField，`Decimal += float`
    会抛 `TypeError: unsupported operand type(s) for +=: 'decimal.Decimal' and 'float'`。
    而调用方给的类型并不统一：serializer 的 `FloatField` 是 float、前端 JS 传的是
    float、`DecimalField` 给的是 Decimal ⇒ 在每个调用方各转一次必然漏，收在服务入口
    统一转一次（转成 str 再进 Decimal，避免 `Decimal(0.1)` 的二进制尾差）。
    """
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))



class RewardPoolService:
    """奖励池业务逻辑"""

    @staticmethod
    def _get_or_create_pool() -> RewardPool:
        pool = RewardPool.objects.first()
        if not pool:
            pool = RewardPool.objects.create()
        return pool

    @staticmethod
    @db_transaction.atomic
    def add_reward(*, source_id: int, source_type: str, amount: Decimal,
                   transaction_type: str, description: str = '') -> RewardTransaction:
        """增加奖励（里程碑完成/小确幸等）"""
        amount = _to_decimal(amount)
        pool = RewardPoolService._get_or_create_pool()
        old_balance = pool.balance

        pool.balance += amount
        pool.total_earned += amount
        pool.save()

        tx = RewardTransaction.objects.create(
            source_id=source_id,
            source_type=source_type,
            amount=amount,
            transaction_type=transaction_type,
            balance_before=old_balance,
            balance_after=pool.balance,
            description=description,
        )
        RewardPoolService._check_gift_availability()
        return tx

    @staticmethod
    @db_transaction.atomic
    def adjust_reward(*, source_id: int, source_type: str, delta: Decimal,
                      description: str = '') -> RewardTransaction | None:
        """调整奖励（里程碑金额变更时）"""
        delta = _to_decimal(delta)
        if delta == 0:
            return None

        pool = RewardPoolService._get_or_create_pool()
        old_balance = pool.balance

        pool.balance += delta
        if delta > 0:
            pool.total_earned += delta
        pool.save()

        tx_type = 'milestone_update'
        tx = RewardTransaction.objects.create(
            source_id=source_id,
            source_type=source_type,
            amount=delta,
            transaction_type=tx_type,
            balance_before=old_balance,
            balance_after=pool.balance,
            description=description,
        )
        RewardPoolService._check_gift_availability()
        return tx

    @staticmethod
    @db_transaction.atomic
    def deduct_reward(*, source_id: int, source_type: str, amount: Decimal,
                      reason: str = 'milestone_delete', description: str = '') -> RewardTransaction:
        """扣除奖励（删除已完成里程碑时）"""
        amount = _to_decimal(amount)
        pool = RewardPoolService._get_or_create_pool()
        old_balance = pool.balance

        pool.balance -= amount
        pool.total_withdrawn += amount
        pool.save()

        tx = RewardTransaction.objects.create(
            source_id=source_id,
            source_type=source_type,
            amount=-amount,
            transaction_type=reason,
            balance_before=old_balance,
            balance_after=pool.balance,
            description=description,
        )
        RewardPoolService._check_gift_availability()
        return tx

    @staticmethod
    def get_pool() -> dict:
        """奖励池概览 —— 三个数全部**从流水派生**。

        🔴 池表上的 `total_earned / total_withdrawn` 是独立累加字段，
        删流水、历史迁移、任何绕过 service 的写库都会让它与账本脱钩。
        2026-10-23 实测：字段 22,092.00 / 21,395.90，
        而流水实际正数 12,063.00、负数 11,378.00 —— 而且
        `earned - withdrawn = 696.10 ≠ 余额 685.00`，三个数字互相打架。

        流水的 `balance_before / balance_after` 从 0 起算、逐条连续
        （最早一条 before=0.00），才是唯一可信的账本 ⇒ 展示一律派生，
        两个累计字段不再作为真源（写入路径仍维护，只为兼容旧读法）。
        """
        from django.db.models import Q, Sum

        agg = RewardTransaction.objects.aggregate(
            income=Sum('amount', filter=Q(amount__gt=0)),
            expense=Sum('amount', filter=Q(amount__lt=0)),
        )
        income = agg['income'] or Decimal('0')
        expense = agg['expense'] or Decimal('0')
        return {
            'balance': float(income + expense),
            'total_earned': float(income),
            'total_withdrawn': float(-expense),
        }

    @staticmethod
    def get_stats_by_source() -> dict:
        """按来源统计**收入** —— 只算正数流水。

        🔴 口径必须与 `get_pool()['total_earned']` 同源：两者都只取正数，
        所以「四个来源之和 == 累计获得」是恒等式，百分比的分母也才对得上。
        混进负数（小确幸删除扣回、快乐程度调低）会让来源合计永远比累计获得
        少一截 —— 页面看起来就是「流水明细和总数对不上」。
        """
        from django.db.models import Sum

        income = RewardTransaction.objects.filter(amount__gt=0)

        sugar_total = income.filter(
            source_type='sugar',
        ).aggregate(total=Sum('amount'))['total'] or 0

        milestone_total = income.filter(
            source_type='milestone',
        ).aggregate(total=Sum('amount'))['total'] or 0

        milestone_detail = list(
            RewardTransaction.objects
            .filter(source_type='milestone', transaction_type='milestone_complete')
            .values('source_id', 'amount', 'description', 'created_at')
            .order_by('-created_at')
        )

        goal_complete_total = income.filter(
            source_type='goal_complete',
        ).aggregate(total=Sum('amount'))['total'] or 0

        inbox_complete_total = income.filter(
            source_type='inbox_complete',
        ).aggregate(total=Sum('amount'))['total'] or 0

        return {
            'sugar': float(sugar_total),
            'milestone': float(milestone_total),
            'goal_complete': float(goal_complete_total),
            'inbox_complete': float(inbox_complete_total),
            'total': float(sugar_total + milestone_total + goal_complete_total + inbox_complete_total),
            'milestone_detail': [
                {
                    'source_id': item['source_id'],
                    'amount': float(item['amount']),
                    'description': item['description'] or '',
                    'created_at': item['created_at'].strftime('%Y-%m-%d %H:%M:%S') if item['created_at'] else '',
                }
                for item in milestone_detail
            ],
        }

    # ────────── 礼物清单 ──────────

    @staticmethod
    @db_transaction.atomic
    def exchange_gift(gift_id: int, actual_reward: Decimal | None = None) -> dict:
        """兑换礼物"""
        from django.core.exceptions import ValidationError

        gift = GiftList.objects.get(id=gift_id)

        if gift.status != 'waiting':
            raise ValidationError(f'礼物当前状态为 {gift.get_status_display()}，不可兑换')

        pool = RewardPoolService._get_or_create_pool()
        if pool.balance < gift.expected_reward:
            raise ValidationError('奖励池余额不足')

        deduct_amount = actual_reward if actual_reward else gift.expected_reward
        old_balance = pool.balance

        pool.balance -= deduct_amount
        pool.total_withdrawn += deduct_amount
        pool.save()

        gift.status = 'redeemed'
        gift.redeemed_at = datetime.now()
        if actual_reward:
            gift.actual_reward = actual_reward
        gift.save()

        tx = RewardTransaction.objects.create(
            source_id=gift.id,
            source_type='gift',
            amount=-deduct_amount,
            transaction_type='gift_exchange',
            balance_before=old_balance,
            balance_after=pool.balance,
            description=f'兑换礼物：{gift.name}',
        )

        return {
            'gift': {
                'id': gift.id,
                'name': gift.name,
                'status': gift.status,
                'redeemed_at': gift.redeemed_at.isoformat() if gift.redeemed_at else None,
                'actual_reward': float(deduct_amount),
            },
            'reward_pool_balance': float(pool.balance),
        }

    @staticmethod
    def _check_gift_availability() -> None:
        """奖励池变动后自动检查礼物可兑换状态"""
        pool = RewardPoolService._get_or_create_pool()
        gifts = GiftList.objects.filter(status__in=['pending', 'waiting'])
        for gift in gifts:
            new_status = 'waiting' if pool.balance >= gift.expected_reward else 'pending'
            if gift.status != new_status:
                gift.status = new_status
                gift.save(update_fields=['status'])

    @staticmethod
    def get_gift_stats() -> dict:
        """获取礼物统计"""
        from django.db.models import Sum

        total = GiftList.objects.count()
        pending = GiftList.objects.filter(status='pending').count()
        waiting = GiftList.objects.filter(status='waiting').count()
        redeemed = GiftList.objects.filter(status='redeemed').count()
        cancelled = GiftList.objects.filter(status='cancelled').count()

        total_expected = GiftList.objects.aggregate(
            total=Sum('expected_reward'),
        )['total'] or 0

        total_redeemed = GiftList.objects.filter(
            status__in=['redeemed'],
        ).aggregate(
            total=Sum('actual_reward'),
        )['total'] or 0

        return {
            'total': total,
            'pending': pending,
            'waiting': waiting,
            'redeemed': redeemed,
            'cancelled': cancelled,
            'total_expected': float(total_expected),
            'total_redeemed': float(total_redeemed),
        }
