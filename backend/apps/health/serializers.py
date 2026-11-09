from rest_framework import serializers

from .constants import CONVERSION_RATES
from .models import HealthRecord, MenstrualRecord, UserBodyInfo, WeightGoal, WeightGoalAdjustment, WeightMilestone, WeightRecord


class HealthRecordSerializer(serializers.ModelSerializer):
    """运动记录序列化器"""

    htype_label = serializers.SerializerMethodField()

    class Meta:
        model = HealthRecord
        fields = [
            'hid', 'steps', 'htype', 'htype_label', 'cofficient', 'total',
            'time', 'remark', 'years', 'user_id',
        ]
        read_only_fields = ['hid', 'total', 'years']

    def get_htype_label(self, obj):
        return dict(self.Meta.model._meta.get_field('htype').choices).get(obj.htype, '步数')

    def validate_steps(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError('步数不能为负数')
        if value is not None and value > 100000:
            raise serializers.ValidationError('单日步数不能超过10万步')
        return value

    def validate(self, attrs):
        htype = attrs.get('htype')
        steps = attrs.get('steps')
        cofficient = attrs.get('cofficient')

        if htype and htype != 1 and not cofficient:
            # 非步数运动类型需要转换系数，尝试使用默认值
            default_rate = CONVERSION_RATES.get(htype)
            if default_rate:
                attrs['cofficient'] = default_rate
            else:
                raise serializers.ValidationError(
                    {'cofficient': '非步数运动类型需要填写转换系数'}
                )

        if steps is not None:
            if htype == 1 or not htype:
                attrs['total'] = float(steps)
            elif attrs.get('cofficient'):
                attrs['total'] = float(steps) * attrs['cofficient']

        time_val = attrs.get('time')
        if time_val and not attrs.get('years'):
            attrs['years'] = str(time_val.year)

        return attrs


# ─── 体重管理 ───


class WeightRecordSerializer(serializers.ModelSerializer):
    """体重记录序列化器"""

    weight_jin = serializers.SerializerMethodField()
    bmi = serializers.SerializerMethodField()

    class Meta:
        model = WeightRecord
        fields = [
            'id', 'record_date', 'weight_kg', 'weight_jin', 'bmi',
            'body_fat', 'measure_time', 'notes', 'user_id',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'weight_jin', 'bmi', 'created_at', 'updated_at']

    def get_weight_jin(self, obj):
        return obj.weight_jin

    def get_bmi(self, obj):
        return obj.bmi


class WeightGoalSerializer(serializers.ModelSerializer):
    """体重目标序列化器"""

    target_weight_jin = serializers.SerializerMethodField()
    start_weight_jin = serializers.SerializerMethodField()
    monthly_target_jin = serializers.SerializerMethodField()

    class Meta:
        model = WeightGoal
        fields = [
            'id', 'user_id',
            'target_weight_kg', 'target_weight_jin',
            'start_weight_kg', 'start_weight_jin',
            'monthly_target_kg', 'monthly_target_jin',
            'start_date', 'expected_end_date', 'status',
            'current_month', 'current_month_start_weight', 'current_month_target',
            'is_active', 'completed_at', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'target_weight_jin', 'start_weight_jin', 'monthly_target_jin', 'created_at', 'updated_at']

    def get_target_weight_jin(self, obj):
        return obj.target_weight_jin

    def get_start_weight_jin(self, obj):
        return obj.start_weight_jin

    def get_monthly_target_jin(self, obj):
        return obj.monthly_target_jin


class WeightGoalAdjustmentSerializer(serializers.ModelSerializer):
    """目标调整记录序列化器"""

    class Meta:
        model = WeightGoalAdjustment
        fields = '__all__'
        read_only_fields = ['id', 'adjusted_at']


class WeightMilestoneSerializer(serializers.ModelSerializer):
    """月度里程碑序列化器"""

    class Meta:
        model = WeightMilestone
        fields = '__all__'
        read_only_fields = ['id', 'created_at']


class UserBodyInfoSerializer(serializers.ModelSerializer):
    """用户身体信息序列化器"""

    height_m = serializers.SerializerMethodField()

    class Meta:
        model = UserBodyInfo
        fields = ['id', 'user_id', 'height_cm', 'height_m', 'gender', 'age', 'created_at', 'updated_at']
        read_only_fields = ['id', 'height_m', 'created_at', 'updated_at']

    def get_height_m(self, obj):
        return obj.height_m


class WeightStatsSerializer(serializers.Serializer):
    """体重统计序列化器"""

    current_weight_kg = serializers.FloatField(allow_null=True)
    current_weight_jin = serializers.FloatField(allow_null=True)
    target_weight_kg = serializers.FloatField(allow_null=True)
    target_weight_jin = serializers.FloatField(allow_null=True)
    total_lost_kg = serializers.FloatField(allow_null=True)
    total_lost_jin = serializers.FloatField(allow_null=True)
    remaining_kg = serializers.FloatField(allow_null=True)
    remaining_jin = serializers.FloatField(allow_null=True)
    overall_progress = serializers.FloatField()
    monthly_lost_kg = serializers.FloatField(allow_null=True)
    monthly_lost_jin = serializers.FloatField(allow_null=True)
    monthly_target_kg = serializers.FloatField(allow_null=True)
    monthly_progress = serializers.FloatField()
    bmi = serializers.FloatField(allow_null=True)
    bmi_status = serializers.CharField(allow_null=True)
    remaining_days = serializers.IntegerField()


class WeightTrendSerializer(serializers.Serializer):
    """体重趋势数据序列化器"""

    records = serializers.ListField(child=serializers.DictField())
    milestones = serializers.ListField(child=serializers.DictField())
    target_weight_kg = serializers.FloatField(allow_null=True)


class MenstrualRecordSerializer(serializers.ModelSerializer):
    """好朋友记录序列化器"""

    class Meta:
        model = MenstrualRecord
        fields = '__all__'
        read_only_fields = ['id', 'created_at']
        # DRF 默认文案是英文（`Date has wrong format`），前端会把 4xx 原样
        # 透到提示条上，所以这里必须给中文 —— 报错要能直接看懂才知道改哪一格。
        extra_kwargs = {
            'start_date': {'error_messages': {'invalid': '开始日期格式应为 YYYY-MM-DD（如 2026-10-30）'}},
            'end_date': {'error_messages': {'invalid': '结束日期格式应为 YYYY-MM-DD；本次还没结束请留空'}},
        }
        # 唯一约束的报错也自己接管：DRF 自动生成的那条是
        # 「The fields user_id, start_date must make a unique set.」——
        # 英文，且说的是两个列名，用户看不出「这一天已经记过了」。
        validators = []

    def validate(self, attrs: dict) -> dict:
        """同一天只能记一次（`uk_menstrual_user_date` 的中文出口）。

        ⚠️ 这里替代的是 DRF 自动生成的 `UniqueTogetherValidator`（见 Meta.validators）。
        库层约束仍在，改不到这里时还有 DB 兜底。
        """
        start = attrs.get('start_date') or getattr(self.instance, 'start_date', None)
        user_id = attrs.get('user_id') or getattr(self.instance, 'user_id', 1)
        if start:
            qs = MenstrualRecord.objects.filter(user_id=user_id, start_date=start)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError({
                    'start_date': f'{start} 已经有一条记录，同一天只能记一次；要改请直接编辑那一条',
                })
        return attrs

    def _auto_duration(self, validated_data: dict) -> dict:
        """持续天数自动计算：未显式提供时由 end_date - start_date 得出"""
        if validated_data.get('duration_days') is None:
            start = validated_data.get('start_date') or getattr(self.instance, 'start_date', None)
            end = validated_data.get('end_date')
            if end is None:
                end = getattr(self.instance, 'end_date', None)
            if start and end:
                validated_data['duration_days'] = (end - start).days
        return validated_data

    def create(self, validated_data):
        validated_data = self._auto_duration(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data = self._auto_duration(validated_data)
        return super().update(instance, validated_data)
