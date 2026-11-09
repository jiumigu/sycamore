"""作品 · 序列化器

🔴 两条约定：

1. **期标识只许后端一把尺子** —— `period_key` 复用 `selfrun.readers.period_range`
   （ISO 周 / 自然月），前端**零副本**。前端自己用 `Date` 算跨年会**静默差一周**。
2. **界面枚举随接口下发** —— `meta` 端点的形状与选集常量同源，前端不抄第二份。
"""
from django.utils import timezone
from rest_framework import serializers

# ⚠️ 复用自我运转的周期实现，**不另写一份** —— 期标识全项目只有一把尺子。
#    （反向依赖是安全的：`selfrun.readers` 只在函数内部 import 本 app 的模型。）
from apps.selfrun.readers import period_range
# 🔴 media 结构校验唯一实现（works / showroom 共用）
from apps.core.media import validate_media_items

from .constants import (
    CAPTURE_SOURCE_CHOICES,
    WORK_KIND_CHOICES,
    WORK_STATUS_CHOICES,
)
from .models import Work, WorkCapture


def _period_key(period_type, when):
    """`datetime` → `'2026-W43'` / `'2026-10'`（按本地时区取日）。"""
    if when is None or not period_type:
        return None
    return period_range(period_type, timezone.localtime(when).date())[2]


# ══════════════════════════════════════════════════════════════
# 出参
# ══════════════════════════════════════════════════════════════

class CaptureSerializer(serializers.ModelSerializer):
    source_type_display = serializers.CharField(source='get_source_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    work_name = serializers.CharField(source='work.name', read_only=True, default=None)
    period_key = serializers.SerializerMethodField()
    in_current_period = serializers.SerializerMethodField()

    class Meta:
        model = WorkCapture
        fields = (
            'id', 'source_type', 'source_type_display', 'source_id',
            'title', 'excerpt', 'status', 'status_display',
            'work', 'work_name', 'captured_at', 'period_key', 'in_current_period',
        )

    def get_period_key(self, obj):
        return _period_key(self.context.get('period_type'), obj.captured_at)

    def get_in_current_period(self, obj):
        """这条是不是「本期」勾的。

        ⚠️ 由**后端**判并下发，前端不自己比字符串 ——
           它得先知道「本期是哪一期」，而那是后端才知道的事。
        """
        current = self.context.get('current_period_key')
        return bool(current) and self.get_period_key(obj) == current


class WorkSerializer(serializers.ModelSerializer):
    kind_display = serializers.CharField(source='get_kind_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    origin = serializers.SerializerMethodField()
    period_key = serializers.SerializerMethodField()
    in_current_period = serializers.SerializerMethodField()

    class Meta:
        model = Work
        fields = (
            'id', 'name', 'summary', 'kind', 'kind_display',
            'status', 'status_display', 'channel', 'note', 'media',
            'created_at', 'updated_at', 'origin', 'period_key', 'in_current_period',
        )

    def get_origin(self, obj):
        """「从哪来」—— 它的来源清单（空 = 手动新建的）。"""
        return [
            {
                'id': c.id,
                'source_type': c.source_type,
                'source_type_display': c.get_source_type_display(),
                'title': c.title,
            }
            for c in obj.captures.all()
        ]

    def get_period_key(self, obj):
        return _period_key(self.context.get('period_type'), obj.created_at)

    def get_in_current_period(self, obj):
        """这件是不是**本期成形**的。

        ⚠️ 由后端判并下发（与 `WorkCapture.in_current_period` 同款）——
           前端要自己判就得先知道「本期是哪一期」，而那是后端才知道的事。
        """
        current = self.context.get('current_period_key')
        return bool(current) and self.get_period_key(obj) == current


# ══════════════════════════════════════════════════════════════
# 入参
# ══════════════════════════════════════════════════════════════

class WorkInputSerializer(serializers.ModelSerializer):
    """作品的新建 / 编辑（**不含来源** —— 来源由「合成」建立）。"""

    media = serializers.ListField(
        child=serializers.DictField(), required=False, default=list,
    )

    class Meta:
        model = Work
        fields = ('name', 'summary', 'kind', 'status', 'channel', 'note', 'media')

    def validate_name(self, value):
        v = (value or '').strip()
        if not v:
            raise serializers.ValidationError('给它起个名字')
        return v[:120]

    def validate_media(self, value):
        return validate_media_items(value)


class CaptureInputSerializer(serializers.Serializer):
    """打勾。

    ⚠️ `title` **由调用方给**（四个入口各自知道自己的标题），
       后端不回源表查 —— 那会让本模块反向依赖四个 app，
       而且源记录被删时（收件箱条目归档）就拿不到标题了。
    """

    source_type = serializers.ChoiceField(choices=CAPTURE_SOURCE_CHOICES)
    source_id = serializers.IntegerField()
    title = serializers.CharField(max_length=200)
    excerpt = serializers.CharField(
        max_length=300, required=False, allow_blank=True, default='',
    )


class ComposeSerializer(serializers.Serializer):
    capture_ids = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=False,
    )
    name = serializers.CharField(max_length=120)
    summary = serializers.CharField(
        max_length=200, required=False, allow_blank=True, default='',
    )
    kind = serializers.ChoiceField(choices=WORK_KIND_CHOICES, default='other')
    status = serializers.ChoiceField(choices=WORK_STATUS_CHOICES, default='private')
    channel = serializers.CharField(
        max_length=40, required=False, allow_blank=True, default='',
    )
    note = serializers.CharField(
        max_length=200, required=False, allow_blank=True, default='',
    )


class ChannelsSerializer(serializers.Serializer):
    values = serializers.ListField(child=serializers.CharField(max_length=40))
