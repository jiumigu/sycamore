import os

from django.conf import settings
from rest_framework import serializers

from apps.core.models import UserProfile
from .models import OneDayPage, TemporalTask


class TemporalTaskSerializer(serializers.ModelSerializer):
    """任务时间记录序列化器"""

    category_icon = serializers.SerializerMethodField()
    duration_display = serializers.SerializerMethodField()
    date = serializers.SerializerMethodField()

    class Meta:
        model = TemporalTask
        fields = [
            'id', 'task_name', 'task_description', 'start_time', 'end_time',
            'duration', 'duration_hours', 'notes', 'tags', 'task_type',
            'year', 'mon', 'day', 'week', 'quarter',
            'category_level1', 'category_level2', 'category_color',
            'import_batch', 'updated_at',
            'category_icon', 'duration_display', 'date',
        ]
        read_only_fields = ['id', 'year', 'mon', 'day', 'week', 'quarter',
                            'category_level1', 'category_level2', 'category_color',
                            'import_batch', 'updated_at']

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
