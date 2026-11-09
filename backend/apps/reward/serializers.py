from rest_framework import serializers

from apps.core.fields import AmountNumberField

from .models import GiftList, RewardPool, RewardTransaction


class RewardPoolSerializer(serializers.Serializer):
    """奖励池概览"""
    balance = serializers.FloatField()
    total_earned = serializers.FloatField()
    total_withdrawn = serializers.FloatField()


class RewardTransactionSerializer(serializers.ModelSerializer):
    """奖励流水

    🔴 三个金额必须显式声明：`ModelSerializer` 给 `DecimalField` 默认
    `coerce_to_string=True` ⇒ 接口下发 `"5.00"` 字符串，而前端的
    `formatSignedAmount` 只认 number（`typeof !== 'number'` 就画 `—`）。
    原先靠 `rewardStore.fetchTransactions` 里三行 `Number()` 兜住，
    属于「补丁散在调用点」：换一个消费方（时间线 / 导出 / 新页面）
    就重新炸一次，故此处收口到后端。
    """
    transaction_type_display = serializers.SerializerMethodField()
    amount = AmountNumberField(max_digits=10, decimal_places=2)
    balance_before = AmountNumberField(max_digits=12, decimal_places=2)
    balance_after = AmountNumberField(max_digits=12, decimal_places=2)

    class Meta:
        model = RewardTransaction
        fields = '__all__'

    def get_transaction_type_display(self, obj):
        return obj.get_transaction_type_display()


class RewardSourceStatsSerializer(serializers.Serializer):
    """奖励来源统计"""
    sugar = serializers.FloatField()
    milestone = serializers.FloatField()
    goal_complete = serializers.FloatField()
    inbox_complete = serializers.FloatField()
    total = serializers.FloatField()
    milestone_detail = serializers.ListField()


class GiftListSerializer(serializers.ModelSerializer):
    """礼物清单序列化器"""

    # 🔴 两个价格必须显式声明：`ModelSerializer` 给 DecimalField 自动生成的是
    #    `coerce_to_string=True` 的字段 ⇒ 接口吐 `"800.00"`（字符串）。
    #    前端 `GiftCard` 用 `formatAmount(gift.expected_reward)` 渲染，
    #    而它第一句就是 `typeof value !== 'number' → EMPTY_AMOUNT`，
    #    于是**每个礼物的价格都显示成 `¥—`**（v3.63.16 实案）。
    #    而同一张卡片的「还差 ¥115.00」是 `get_needed` 方法字段（真 number），
    #    所以只坏价格一处，看着像「价格没填」——其实是类型不对。
    #    前端 store 里只给 progress / needed 补了 `Number()`，没补这两个，
    #    因此必须由后端保证下发的就是 number（前端 TS 类型也声明的是 number）。
    expected_reward = AmountNumberField(max_digits=10, decimal_places=2)
    # 兑换时留空 = 按参考价扣，所以这条确实会是 NULL ⇒ 必须 allow_null
    actual_reward = AmountNumberField(max_digits=10, decimal_places=2, required=False, allow_null=True)

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

    def _pool(self):
        """本次序列化共用一个池快照。

        🔴 不能在每个方法字段里各调用一次 `get_pool()`：它已改为**从流水聚合派生**
        （3 个 aggregate），而列表里每张卡片要 progress / needed / can_redeem 三个值
        ⇒ N 条礼物就是 3N 次聚合查询（6 条时实测 21 次 SQL）。
        放在实例上缓存：DRF 的 `ListSerializer` 用同一个 child 实例逐条序列化，
        所以整个列表只查一次；每次请求都是新实例，不存在跨请求读到旧值的问题。
        """
        if not hasattr(self, '_pool_cache'):
            from .services import RewardPoolService
            self._pool_cache = RewardPoolService.get_pool()
        return self._pool_cache

    def get_progress(self, obj):
        """计算进度百分比（奖励池余额/预期价格）"""
        pool = self._pool()
        if obj.expected_reward and obj.expected_reward > 0:
            return round((pool['balance'] / float(obj.expected_reward)) * 100, 1)
        return 0

    def get_needed(self, obj):
        """距兑换还需多少"""
        pool = self._pool()
        needed = float(obj.expected_reward) - pool['balance']
        return round(needed, 2) if needed > 0 else 0

    def get_can_redeem(self, obj):
        pool = self._pool()
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
