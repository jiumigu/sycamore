"""三年赎回期 · 序列化器"""
from rest_framework import serializers

from .models import (
    RedemptionPeriod, RedemptionPoolInject, RedemptionAttrRule, RedemptionWeekSnapshot,
)


class RedemptionPeriodSerializer(serializers.ModelSerializer):
    """赎回期配置（单例）。pk 只读，其余可写；改起止/本金由视图层重算派生字段。"""

    class Meta:
        model = RedemptionPeriod
        fields = [
            'id', 'start_date', 'end_date', 'pool_principal', 'tracking_status',
            'paused_since', 'resume_at', 'baseline_toward_ratio', 'baseline_set_week',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'paused_since', 'resume_at']


class PoolInjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = RedemptionPoolInject
        fields = ['id', 'inject_date', 'amount', 'source', 'note', 'created_at']
        read_only_fields = ['id', 'created_at']


class AttrRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = RedemptionAttrRule
        fields = [
            'id', 'match_field', 'match_value', 'attribution', 'priority',
            'is_active', 'note', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class WeekSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = RedemptionWeekSnapshot
        fields = [
            'id', 'year', 'week', 'toward_hours', 'relation_hours', 'maintain_hours',
            'external_hours', 'drain_hours', 'covered_hours', 'theoretical_hours',
            'coverage_rate', 'toward_ratio', 'unit_cost', 'snapshot_at',
        ]
        read_only_fields = ['id', 'snapshot_at']
