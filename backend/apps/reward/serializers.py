from rest_framework import serializers

from .models import GiftList, RewardPool, RewardTransaction


class RewardPoolSerializer(serializers.Serializer):
    """奖励池概览"""
    balance = serializers.FloatField()
    total_earned = serializers.FloatField()
    total_withdrawn = serializers.FloatField()


class RewardTransactionSerializer(serializers.ModelSerializer):
    """奖励流水"""
    transaction_type_display = serializers.SerializerMethodField()

    class Meta:
        model = RewardTransaction
        fields = '__all__'

    def get_transaction_type_display(self, obj):
        return obj.get_transaction_type_display()


class RewardSourceStatsSerializer(serializers.Serializer):
    """奖励来源统计"""
    sugar = serializers.FloatField()
    milestone = serializers.FloatField()
    total = serializers.FloatField()
    milestone_detail = serializers.ListField()


class GiftListSerializer(serializers.ModelSerializer):
    """礼物清单序列化器"""

    category_display = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()
    needed = serializers.SerializerMethodField()
    can_redeem = serializers.SerializerMethodField()

    class Meta:
        model = GiftList
        fields = [
            'id', 'name', 'expected_reward', 'actual_reward',
            'status', 'status_display', 'category', 'category_display',
            'priority', 'image_url', 'link_url', 'notes',
            'progress', 'needed', 'can_redeem',
            'redeemed_at', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'status', 'redeemed_at', 'created_at', 'updated_at',
                            'progress', 'needed', 'can_redeem']

    def get_category_display(self, obj):
        return obj.get_category_display() if obj.category else None

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_progress(self, obj):
        """计算进度百分比（奖励池余额/预期价格）"""
        from .services import RewardPoolService
        pool = RewardPoolService.get_pool()
        if obj.expected_reward and obj.expected_reward > 0:
            return round((pool['balance'] / float(obj.expected_reward)) * 100, 1)
        return 0

    def get_needed(self, obj):
        """距兑换还需多少"""
        from .services import RewardPoolService
        pool = RewardPoolService.get_pool()
        needed = float(obj.expected_reward) - pool['balance']
        return round(needed, 2) if needed > 0 else 0

    def get_can_redeem(self, obj):
        from .services import RewardPoolService
        pool = RewardPoolService.get_pool()
        return obj.status == 'waiting' and pool['balance'] >= float(obj.expected_reward)


class GiftExchangeSerializer(serializers.Serializer):
    """兑换礼物序列化器"""

    actual_reward = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)


class GiftStatsSerializer(serializers.Serializer):
    """礼物统计序列化器"""

    total = serializers.IntegerField()
    pending = serializers.IntegerField()
    waiting = serializers.IntegerField()
    redeemed = serializers.IntegerField()
    cancelled = serializers.IntegerField()
    total_expected = serializers.FloatField()
    total_redeemed = serializers.FloatField()
