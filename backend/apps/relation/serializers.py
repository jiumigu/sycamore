from rest_framework import serializers

from django.db import models

from .constants import ENERGY_LABELS, QUALITY_COLORS, QUALITY_ICONS
from .models import ConflictEvent, Interaction, ReaderGroup, ReaderInteraction, ReaderMonthlySummary, Relationship


class RelationshipSerializer(serializers.ModelSerializer):
    """关系档案序列化器"""

    quality_label = serializers.SerializerMethodField()
    quality_color = serializers.SerializerMethodField()
    quality_icon = serializers.SerializerMethodField()
    status_label = serializers.SerializerMethodField()
    interaction_count = serializers.SerializerMethodField()
    total_energy = serializers.SerializerMethodField()
    avg_energy = serializers.SerializerMethodField()
    relation_type = serializers.SerializerMethodField()
    last_interaction = serializers.SerializerMethodField()

    class Meta:
        model = Relationship
        fields = [
            'id', 'name', 'alias', 'met_date', 'met_place', 'met_scene',
            'identity_then', 'they_give_me', 'i_give_them',
            'current_status', 'status_label', 'current_quality',
            'quality_label', 'quality_color', 'quality_icon',
            'notes', 'tags', 'user_id', 'created_at', 'updated_at',
            'interaction_count', 'total_energy', 'avg_energy', 'relation_type',
            'last_interaction',
        ]
        read_only_fields = ['id', 'user_id', 'created_at', 'updated_at']

    def get_quality_label(self, obj):
        return dict(obj._meta.get_field('current_quality').choices).get(
            obj.current_quality, obj.current_quality
        )

    def get_quality_color(self, obj):
        return QUALITY_COLORS.get(obj.current_quality, '#9CA3AF')

    def get_quality_icon(self, obj):
        return QUALITY_ICONS.get(obj.current_quality, '⚪')

    def get_status_label(self, obj):
        return dict(obj._meta.get_field('current_status').choices).get(
            obj.current_status, obj.current_status
        )

    def get_interaction_count(self, obj):
        return getattr(obj, '_interaction_count', None) or obj.interactions.count()

    def get_total_energy(self, obj):
        if hasattr(obj, '_total_energy') and obj._total_energy is not None:
            return round(float(obj._total_energy), 1)
        agg = obj.interactions.aggregate(total=models.Sum('energy_score'))
        return round(float(agg['total'] or 0), 1)

    def get_last_interaction(self, obj):
        if hasattr(obj, '_last_interaction'):
            return obj._last_interaction
        last = obj.interactions.order_by('-happened_at').first()
        return last.happened_at.isoformat() if last else None

    def get_avg_energy(self, obj):
        val = getattr(obj, 'avg_energy', None)
        if val is not None:
            return round(float(val), 1)
        agg = obj.interactions.aggregate(avg=models.Avg('energy_score'))
        return round(float(agg['avg'] or 0), 1)

    def get_relation_type(self, obj):
        avg = self.get_avg_energy(obj)
        if avg >= 3:
            return 'nourishing'
        elif avg >= 0:
            return 'neutral'
        elif avg >= -3:
            return 'draining'
        return 'toxic'


class RelationshipListSerializer(serializers.ModelSerializer):
    """关系列表精简序列化器（含聚合统计）"""

    quality_label = serializers.SerializerMethodField()
    quality_color = serializers.SerializerMethodField()
    quality_icon = serializers.SerializerMethodField()
    status_label = serializers.SerializerMethodField()
    interaction_count = serializers.IntegerField(read_only=True)
    total_energy = serializers.FloatField(read_only=True)
    avg_energy = serializers.SerializerMethodField()
    relation_type = serializers.SerializerMethodField()
    last_interaction = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Relationship
        fields = [
            'id', 'name', 'alias', 'current_status', 'status_label',
            'current_quality', 'quality_label', 'quality_color', 'quality_icon',
            'tags', 'interaction_count', 'total_energy', 'avg_energy', 'relation_type',
            'last_interaction',
        ]

    def get_quality_label(self, obj):
        return QUALITY_ICONS.get(obj.current_quality, '⚪') + ' ' + \
            dict(obj._meta.get_field('current_quality').choices).get(
                obj.current_quality, obj.current_quality
            )

    def get_quality_color(self, obj):
        return QUALITY_COLORS.get(obj.current_quality, '#9CA3AF')

    def get_quality_icon(self, obj):
        return QUALITY_ICONS.get(obj.current_quality, '⚪')

    def get_avg_energy(self, obj):
        val = getattr(obj, 'avg_energy', None)
        if val is not None:
            return round(float(val), 1)
        agg = obj.interactions.aggregate(avg=models.Avg('energy_score'))
        return round(float(agg['avg'] or 0), 1)

    def get_relation_type(self, obj):
        avg = self.get_avg_energy(obj)
        if avg >= 3:
            return 'nourishing'
        elif avg >= 0:
            return 'neutral'
        elif avg >= -3:
            return 'draining'
        return 'toxic'

    def get_status_label(self, obj):
        return dict(obj._meta.get_field('current_status').choices).get(
            obj.current_status, obj.current_status
        )


class InteractionSerializer(serializers.ModelSerializer):
    """互动记录序列化器"""

    energy_label = serializers.SerializerMethodField()
    method_label = serializers.SerializerMethodField()
    quality_shift_label = serializers.SerializerMethodField()

    class Meta:
        model = Interaction
        fields = [
            'id', 'relationship', 'happened_at', 'method', 'method_label',
            'energy_score', 'energy_label', 'summary', 'quality_shift',
            'quality_shift_label', 'next_reminder', 'my_action',
            'user_id', 'created_at',
        ]
        read_only_fields = ['id', 'user_id', 'created_at']

    def get_energy_label(self, obj):
        for lo, hi, label in ENERGY_LABELS:
            if lo <= obj.energy_score <= hi:
                return label
        return ''

    def get_method_label(self, obj):
        return dict(obj._meta.get_field('method').choices).get(obj.method, obj.method)

    def get_quality_shift_label(self, obj):
        return dict(obj._meta.get_field('quality_shift').choices).get(
            obj.quality_shift, obj.quality_shift
        )

    def validate_energy_score(self, value):
        if value < -10 or value > 10:
            raise serializers.ValidationError('能量分范围为 -10 到 +10')
        return value


class ReaderGroupSerializer(serializers.ModelSerializer):
    """读者群体序列化器"""
    interaction_count = serializers.SerializerMethodField()

    class Meta:
        model = ReaderGroup
        fields = [
            'id', 'name', 'description', 'total_energy', 'interaction_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_interaction_count(self, obj):
        return obj.interactions.count()


class ReaderInteractionSerializer(serializers.ModelSerializer):
    """读者互动序列化器"""
    interaction_type_display = serializers.SerializerMethodField()
    batch_count = serializers.IntegerField(required=False, default=1)

    class Meta:
        model = ReaderInteraction
        fields = [
            'id', 'reader_group', 'reader_name', 'interaction_type',
            'interaction_type_display', 'content', 'article_title',
            'energy_score', 'tags', 'interaction_date', 'created_at',
            'batch_count',
        ]
        read_only_fields = ['id', 'created_at']
        extra_kwargs = {
            'reader_name': {'required': False},
        }

    def get_interaction_type_display(self, obj):
        return obj.get_interaction_type_display()

    def validate(self, data):
        batch_count = data.get('batch_count', 1)
        if not data.get('reader_name') and batch_count <= 1:
            raise serializers.ValidationError({'reader_name': '单条记录必须填写读者昵称'})
        if data.get('interaction_date') == '':
            data['interaction_date'] = None
        return data

    def create(self, validated_data):
        batch_count = validated_data.pop('batch_count', 1)
        if batch_count > 1:
            validated_data.setdefault('reader_name', '批量汇总')
            batch_note = validated_data.get('content', '') or ''
            validated_data['content'] = f'[批量汇总×{batch_count}] {batch_note}'.strip()
        return super().create(validated_data)


class ConflictEventSerializer(serializers.ModelSerializer):
    """成长记录序列化器"""
    contact_name = serializers.CharField(source='contact.name', read_only=True)

    class Meta:
        model = ConflictEvent
        fields = '__all__'


class ReaderMonthlySummarySerializer(serializers.ModelSerializer):
    """读者月末盘点序列化器"""
    group_name = serializers.CharField(source='reader_group.name', read_only=True)

    class Meta:
        model = ReaderMonthlySummary
        fields = '__all__'
        read_only_fields = ['id', 'user_id', 'created_at']
