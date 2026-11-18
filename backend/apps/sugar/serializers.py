from rest_framework import serializers

from apps.core.fields import AmountNumberField

from .constants import (
    SUGAR_HAPPINESS_MAX,
    SUGAR_HAPPINESS_MIN,
    resolve_happiness_band,
)
from .models import SugarRecord, SugarTemplate


class SugarRecordSerializer(serializers.ModelSerializer):
    """小确幸记录序列化器"""

    reward_label = serializers.SerializerMethodField()
    reward_color = serializers.SerializerMethodField()
    category_display = serializers.SerializerMethodField()
    time = serializers.DateField(input_formats=['%Y-%m-%d', '%Y-%m-%d %H:%M:%S'], required=False)
    # 🔴 必须显式声明：ModelSerializer 会给 DecimalField 生成 `coerce_to_string=True`
    #    的字段 ⇒ 接口吐出 `"9.00"`（字符串），而前端 `formatAmount` 只认 number
    #    （它有一句 `typeof value !== 'number' → 返回空值占位`），于是**有值也画成 `--`**。
    #
    # 🔴 但**不能直接用 `FloatField`**（v3.63.15 修）：它把**入参**也解析成 float，
    #    而 `RewardPool.balance` 是 DecimalField ⇒ `Decimal += float` 抛 TypeError。
    #    `perform_create` 里 `serializer.save()` 在 autocommit 下已提交、`add_reward()`
    #    随后才炸 ⇒ 小确幸记录写进去了、奖励池没加、前端只看到「操作失败」
    #    （2026-10-23 实案：s_id 77/78 落库，当日流水 0 条）。
    #    也不能改成 `DecimalField(coerce_to_string=False)` 了事：那样 `response.data`
    #    里是 Decimal，`test_api_returns_reward_amount_as_number_not_string` 会红。
    #    ⇒ 用 `AmountNumberField`：出参 number、入参 Decimal，两个方向各给一种类型。
    reward_amount = AmountNumberField(required=False)

    class Meta:
        model = SugarRecord
        fields = [
            's_id', 'years', 'month', 'title', 'level_of_happiness',
            'time', 'category', 'category_display', 'tags', 'joy_type', 'notes',
            'reward_amount', 'reward_synced', 'reward_label', 'reward_color',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['s_id', 'reward_synced', 'created_at', 'updated_at']

    def get_reward_label(self, obj) -> str:
        return _reward_label(obj.level_of_happiness)

    def get_reward_color(self, obj) -> str:
        """档位配色 —— 前端不按分数自己算颜色（那会是第二份档位边界）。"""
        return resolve_happiness_band(obj.level_of_happiness)['color']

    def get_category_display(self, obj):
        return obj.get_category_display() if obj.category else None

    def validate_level_of_happiness(self, value):
        if value < SUGAR_HAPPINESS_MIN or value > SUGAR_HAPPINESS_MAX:
            raise serializers.ValidationError(
                f'快乐程度必须在 {SUGAR_HAPPINESS_MIN} ~ {SUGAR_HAPPINESS_MAX} 之间'
            )
        return value


def _reward_label(level) -> str:
    """根据快乐程度返回档位词（5-20 分制，五档）。

    档位边界在 `constants.SUGAR_HAPPINESS_BANDS` —— 这里只取词，不写边界。
    """
    return resolve_happiness_band(level)['label']


class SugarTemplateSerializer(serializers.ModelSerializer):
    """小确幸模板序列化器"""

    category_display = serializers.SerializerMethodField()

    class Meta:
        model = SugarTemplate
        fields = [
            'id', 'user_id', 'category', 'category_display', 'name',
            'icon', 'points', 'duration', 'is_active', 'sort_order',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'user_id', 'created_at', 'updated_at']

    def get_category_display(self, obj):
        return obj.get_category_display()


class SugarCategoryStatsSerializer(serializers.Serializer):
    """分类统计序列化器"""

    category = serializers.CharField()
    count = serializers.IntegerField()
    total_reward = serializers.FloatField()
