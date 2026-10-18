from rest_framework import serializers

from .constants import (
    SUGAR_HAPPINESS_MAX,
    SUGAR_HAPPINESS_MIN,
    resolve_happiness_band,
)
from .models import EnergyLog, EnergyTemplate, SugarRecord, SugarTemplate


class SugarRecordSerializer(serializers.ModelSerializer):
    """小确幸记录序列化器"""

    reward_label = serializers.SerializerMethodField()
    reward_color = serializers.SerializerMethodField()
    category_display = serializers.SerializerMethodField()
    time = serializers.DateField(input_formats=['%Y-%m-%d', '%Y-%m-%d %H:%M:%S'], required=False)

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


class EnergyTemplateSerializer(serializers.ModelSerializer):
    """能量清单模板序列化器"""

    category_label = serializers.SerializerMethodField()
    estimated_minutes = serializers.SerializerMethodField()

    class Meta:
        model = EnergyTemplate
        fields = [
            'id', 'content', 'default_energy', 'category', 'category_label',
            'icon', 'estimated_seconds', 'estimated_minutes',
            'is_system', 'is_active', 'sort_order',
        ]
        read_only_fields = ['id', 'is_system']

    def get_category_label(self, obj):
        return obj.get_category_display()

    def get_estimated_minutes(self, obj):
        return round(obj.estimated_seconds / 60, 1)


class EnergyCompleteSerializer(serializers.Serializer):
    """完成能量清单请求序列化器"""

    template_id = serializers.IntegerField(required=False, allow_null=True)
    content = serializers.CharField(max_length=200)
    energy_gained = serializers.IntegerField(default=1, min_value=1, max_value=5)
    is_custom = serializers.BooleanField(default=False)
    completed_at = serializers.DateTimeField(required=False)


class EnergyLogSerializer(serializers.ModelSerializer):
    """能量清单完成记录序列化器"""

    template_icon = serializers.CharField(source='template.icon', read_only=True, default='✨')

    class Meta:
        model = EnergyLog
        fields = [
            'id', 'template', 'template_icon', 'content', 'energy_gained',
            'is_custom', 'completed_at', 'reward_processed', 'created_at',
        ]
        read_only_fields = ['id', 'reward_processed', 'created_at']
