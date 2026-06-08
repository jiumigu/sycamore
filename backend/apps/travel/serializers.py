from rest_framework import serializers

from .models import TravelRecord


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
