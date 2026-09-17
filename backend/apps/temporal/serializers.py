import os

from django.conf import settings
from rest_framework import serializers

from apps.core.models import UserProfile
from .models import OneDayPage, TaskMeta, TemporalTask


class TaskMetaSerializer(serializers.ModelSerializer):
    """L3 task_name → L2 活动类型 / L1 归因 映射序列化器"""

    class Meta:
        model = TaskMeta
        fields = [
            'id', 'task_name', 'activity_type', 'default_attribution',
            'is_system', 'note', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TemporalTaskSerializer(serializers.ModelSerializer):
    """任务时间记录序列化器（v0.3：列表额外返回 L1 归因 / L2 类型 解析字段）"""

    category_icon = serializers.SerializerMethodField()
    duration_display = serializers.SerializerMethodField()
    date = serializers.SerializerMethodField()
    activity_type = serializers.SerializerMethodField()
    attribution = serializers.SerializerMethodField()
    is_unclassified = serializers.SerializerMethodField()

    class Meta:
        model = TemporalTask
        fields = [
            'id', 'task_name', 'task_description', 'start_time', 'end_time',
            'duration', 'duration_hours', 'notes', 'tags', 'task_type',
            'year', 'mon', 'day', 'week', 'quarter',
            'category_level1', 'category_level2', 'category_color',
            'import_batch', 'updated_at',
            'category_icon', 'duration_display', 'date',
            'activity_type', 'attribution', 'is_unclassified',
        ]
        read_only_fields = ['id', 'year', 'mon', 'day', 'week', 'quarter',
                            'category_level1', 'category_level2', 'category_color',
                            'import_batch', 'updated_at',
                            'activity_type', 'attribution', 'is_unclassified']

    def get_category_icon(self, obj):
        from .constants import CATEGORY_ICONS
        return CATEGORY_ICONS.get(obj.category_level1, '📋')

    def get_duration_display(self, obj):
        if obj.duration_hours is not None:
            h = int(obj.duration_hours)
            m = int((obj.duration_hours - h) * 60)
            return f'{h:02d}:{m:02d}'
        return ''

    def get_date(self, obj):
        if obj.start_time:
            return obj.start_time.strftime('%Y-%m-%d')
        return ''

    def get_activity_type(self, obj):
        from .services import resolve_task_meta
        m = resolve_task_meta([obj.task_name]).get(obj.task_name)
        return m['activity_type'] if m else None

    def get_attribution(self, obj):
        from .services import resolve_attribution
        return resolve_attribution([obj.task_name]).get(obj.task_name)

    def get_is_unclassified(self, obj):
        from .services import resolve_task_meta
        m = resolve_task_meta([obj.task_name]).get(obj.task_name)
        return bool(m and m['is_unclassified'])


class TemporalTaskImportSerializer(serializers.Serializer):
    """CSV 导入序列化器"""

    file = serializers.FileField()


class CategoryTrendItemSerializer(serializers.Serializer):
    """趋势图单项序列化器"""

    period = serializers.CharField()
    categories = serializers.DictField(child=serializers.FloatField())


class BalanceWheelSerializer(serializers.Serializer):
    """平衡轮序列化器"""

    categories = serializers.ListField(child=serializers.DictField())


class TaskRankingSerializer(serializers.Serializer):
    """任务排行序列化器"""

    rankings = serializers.ListField(child=serializers.DictField())


class OneDayPageSerializer(serializers.ModelSerializer):
    """每日记录序列化器"""

    otype_display = serializers.SerializerMethodField()
    created_at = serializers.DateField(source='begin_date', format='%Y-%m-%d', read_only=True)
    logseq_file = serializers.SerializerMethodField()

    class Meta:
        model = OneDayPage
        fields = [
            'oid', 'years', 'oneday', 'page', 'total', 'title',
            'begin_date', 'otype', 'otype_display', 'update_date',
            'flag', 'remark', 'user_id', 'created_at', 'logseq_file',
        ]
        read_only_fields = ['oid', 'years', 'total', 'update_date']

    def get_otype_display(self, obj):
        return obj.get_otype_display()

    def get_logseq_file(self, obj):
        if not obj.begin_date:
            return None
        profile = UserProfile.objects.filter(user_id=obj.user_id or 1).first()
        if not profile or not profile.logseq_path:
            return None
        filename = obj.begin_date.strftime('%Y_%m_%d') + '.md'
        full_path = os.path.join(profile.logseq_path, filename)
        if os.path.exists(full_path):
            return full_path
        return None

    def validate_oneday(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError('字数不能为负数')
        return value

    def validate_page(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError('字数不能为负数')
        return value
