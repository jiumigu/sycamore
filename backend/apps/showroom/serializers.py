"""展厅 · 序列化器。

🔴 两条约定：

1. 预览只读接口不下发不可见项（`is_visible=False` 的在视图层过滤）。
2. 作品馆的「作品名」在源作品被删后（`work=NULL`）用 `title_snapshot` 兜底 ——
   快照哲学同 `works.WorkCapture`：源记录没了，仍看得出「当时策展的是哪件」。
"""
from rest_framework import serializers

# 🔴 media 结构校验唯一实现（works / showroom 共用）
from apps.core.media import validate_media_items

from .models import ShowroomCase, ShowroomProfile, ShowroomSkill, ShowroomWork


class ShowroomProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShowroomProfile
        fields = (
            'id', 'ip_name', 'tagline', 'positioning', 'bio',
            'email', 'wechat', 'other_contact', 'updated_at',
        )
        read_only_fields = ['id', 'updated_at']


class ShowroomCaseSerializer(serializers.ModelSerializer):
    media = serializers.ListField(
        child=serializers.DictField(), required=False, default=list,
    )

    class Meta:
        model = ShowroomCase
        fields = (
            'id', 'title', 'client', 'time_label', 'problem', 'result',
            'skill_tags', 'media', 'source_module', 'source_id',
            'is_visible', 'sort_order', 'created_at', 'updated_at',
        )
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_media(self, value):
        return validate_media_items(value)


class ShowroomSkillSerializer(serializers.ModelSerializer):
    level_display = serializers.CharField(source='get_level_display', read_only=True)

    class Meta:
        model = ShowroomSkill
        fields = ('id', 'name', 'level', 'level_display', 'is_visible', 'sort_order')
        read_only_fields = ['id']


class ShowroomWorkSerializer(serializers.ModelSerializer):
    """馆藏作品：引用 `works.Work`，带出作品名 / 摘要 / 类型。"""

    work_name = serializers.SerializerMethodField()
    work_summary = serializers.SerializerMethodField()
    work_kind = serializers.SerializerMethodField()
    work_kind_display = serializers.SerializerMethodField()
    media = serializers.ListField(
        child=serializers.DictField(), required=False, default=list,
    )

    class Meta:
        model = ShowroomWork
        fields = (
            'id', 'work', 'work_name', 'work_summary', 'work_kind', 'work_kind_display',
            'title_snapshot', 'curator_note', 'media', 'is_visible', 'sort_order', 'created_at',
        )
        read_only_fields = ['id', 'created_at', 'title_snapshot']

    def validate_media(self, value):
        return validate_media_items(value)

    def get_work_name(self, obj):
        if obj.work_id:
            return obj.work.name
        return obj.title_snapshot or None

    def get_work_summary(self, obj):
        return obj.work.summary if obj.work_id else ''

    def get_work_kind(self, obj):
        return obj.work.kind if obj.work_id else ''

    def get_work_kind_display(self, obj):
        return obj.work.get_kind_display() if obj.work_id else ''

    def validate(self, attrs):
        # 新建必须选一件作品；编辑允许只改导语 / 排序 / 显隐（work 不重传）。
        work = attrs.get('work', getattr(self.instance, 'work', None))
        if work is None:
            raise serializers.ValidationError({'work': '请选择一件作品'})
        return attrs

    def create(self, validated_data):
        # 落库时快照当时的作品名 —— 源作品改名 / 删除后，馆藏仍读得懂。
        validated_data['title_snapshot'] = validated_data['work'].name
        return super().create(validated_data)

    def update(self, instance, validated_data):
        work = validated_data.get('work')
        if work is not None:
            validated_data['title_snapshot'] = work.name
        return super().update(instance, validated_data)
