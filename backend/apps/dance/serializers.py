from rest_framework import serializers

from .constants import DANCE_TYPE_ICONS
from .models import DanceRecord


class DanceRecordSerializer(serializers.ModelSerializer):
    """舞蹈记录序列化器"""

    type_icon = serializers.SerializerMethodField()
    weekinfo_label = serializers.SerializerMethodField()

    class Meta:
        model = DanceRecord
        fields = [
            'id', 'study_time', 'score', 'teacher_name', 'dance_type',
            'difficulty', 'weekinfo', 'remark', 'file_path',
            'year', 'month', 'quarter', 'duration_minutes', 'energy_level',
            'improvement_note', 'type_icon', 'weekinfo_label',
        ]
        read_only_fields = ['id', 'year', 'month', 'quarter', 'weekinfo']

    def get_type_icon(self, obj):
        return DANCE_TYPE_ICONS.get(obj.dance_type, '💃')

    def get_weekinfo_label(self, obj):
        return obj.weekinfo

    def validate_score(self, value):
        if value < 1 or value > 10:
            raise serializers.ValidationError('评分范围为 1-10')
        return value

    def validate_energy_level(self, value):
        if value is not None and (value < 1 or value > 5):
            raise serializers.ValidationError('体能消耗范围为 1-5')
        return value
