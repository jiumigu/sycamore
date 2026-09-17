from django.utils import timezone
from rest_framework import serializers

from .models import TravelPlan, TravelPlanItem, TravelRecord, TravelWish


class TravelRecordSerializer(serializers.Serializer):
    """旅行记录序列化器"""

    tid = serializers.IntegerField(read_only=True)
    parentnode = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    tname = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    tyear = serializers.IntegerField(allow_null=True, required=False)
    tcost = serializers.FloatField(allow_null=True, required=False)
    ttime = serializers.DateField(allow_null=True, required=False)
    tremark = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    duration_days = serializers.IntegerField(allow_null=True, required=False)
    rating = serializers.IntegerField(allow_null=True, required=False)
    companions = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    district = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    latitude = serializers.DecimalField(max_digits=10, decimal_places=6, allow_null=True, required=False)
    longitude = serializers.DecimalField(max_digits=10, decimal_places=6, allow_null=True, required=False)

    def validate_rating(self, value):
        if value is not None and (value < 1 or value > 5):
            raise serializers.ValidationError('满意度评分必须在 1-5 之间')
        return value


class TravelPlanItemSerializer(serializers.ModelSerializer):
    """旅行计划子项序列化器"""

    class Meta:
        model = TravelPlanItem
        fields = ['id', 'item_type', 'name', 'estimate_cost', 'is_completed', 'completed_at', 'notes', 'sort_order', 'wish']
        read_only_fields = ['id']


class TravelWishSerializer(serializers.ModelSerializer):
    """旅行心愿序列化器"""

    class Meta:
        model = TravelWish
        fields = ['id', 'name', 'category', 'province', 'city', 'district', 'lng', 'lat', 'status', 'visited_at', 'visit_rating', 'visit_notes', 'worth_revisit', 'visit_plan', 'visit_record_id', 'notes', 'created_at', 'updated_at']
        read_only_fields = ['id', 'visit_record_id', 'created_at', 'updated_at']

    def update(self, instance, validated_data):
        new_status = validated_data.get('status', instance.status)
        if new_status != '已打卡':
            validated_data['visited_at'] = None
        elif validated_data.get('visited_at') is None and instance.visited_at is None:
            validated_data['visited_at'] = timezone.localdate()
        return super().update(instance, validated_data)


class TravelPlanSerializer(serializers.ModelSerializer):
    """旅行计划序列化器"""

    items = TravelPlanItemSerializer(many=True, read_only=True)

    class Meta:
        model = TravelPlan
        fields = ['id', 'name', 'destination', 'start_date', 'status', 'total_estimate', 'notes', 'created_at', 'updated_at', 'items']
        read_only_fields = ['id', 'total_estimate', 'created_at', 'updated_at']
