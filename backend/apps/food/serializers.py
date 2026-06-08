from rest_framework import serializers

from .models import FoodRecord


class FoodRecordSerializer(serializers.ModelSerializer):
    """美食记录序列化器"""

    category_display = serializers.SerializerMethodField()
    taste_level_display = serializers.SerializerMethodField()
    eat_time_display = serializers.SerializerMethodField()
    occasion_display = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = FoodRecord
        fields = [
            'id', 'name', 'dish_name', 'category', 'category_display',
            'province', 'city', 'location', 'latitude', 'longitude',
            'taste_level', 'taste_level_display', 'eat_date', 'eat_time', 'eat_time_display',
            'companions', 'occasion', 'occasion_display',
            'images', 'cover_image', 'image_url', 'rating', 'price', 'notes', 'tags',
            'want_visit_again', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_category_display(self, obj):
        return obj.get_category_display() if obj.category else None

    def get_taste_level_display(self, obj):
        return obj.get_taste_level_display()

    def get_eat_time_display(self, obj):
        return obj.get_eat_time_display() if obj.eat_time else None

    def get_occasion_display(self, obj):
        return obj.get_occasion_display() if obj.occasion else None

    def get_image_url(self, obj):
        image = getattr(obj, 'cover_image', None)
        if not image and getattr(obj, 'images', None):
            if isinstance(obj.images, list) and len(obj.images) > 0:
                image = obj.images[0]
        if image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(image)
            return image
        return None

    def validate_rating(self, value):
        if value is not None and (value < 1 or value > 5):
            raise serializers.ValidationError('评分必须在 1 ~ 5 之间')
        return value


class FoodRecordListSerializer(serializers.ModelSerializer):
    """美食列表轻量序列化器"""

    taste_level_display = serializers.SerializerMethodField()
    category_display = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = FoodRecord
        fields = [
            'id', 'name', 'dish_name', 'category', 'category_display',
            'city', 'location', 'taste_level', 'taste_level_display',
            'eat_date', 'cover_image', 'image_url', 'rating', 'price', 'notes',
            'want_visit_again',
        ]

    def get_taste_level_display(self, obj):
        return obj.get_taste_level_display()

    def get_category_display(self, obj):
        return obj.get_category_display() if obj.category else None

    def get_image_url(self, obj):
        image = getattr(obj, 'cover_image', None)
        if not image and getattr(obj, 'images', None):
            if isinstance(obj.images, list) and len(obj.images) > 0:
                image = obj.images[0]
        if image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(image)
            return image
        return None


class FoodStatsSerializer(serializers.Serializer):
    """美食统计序列化器"""

    total_records = serializers.IntegerField()
    total_cities = serializers.IntegerField()
    favorite_category = serializers.CharField(allow_null=True)
    favorite_category_count = serializers.IntegerField()
    avg_rating = serializers.FloatField()
    want_visit_again_count = serializers.IntegerField()
    this_month_count = serializers.IntegerField()


class FoodLocationSerializer(serializers.Serializer):
    """美食地点序列化器"""

    province = serializers.CharField()
    city = serializers.CharField()
    count = serializers.IntegerField()


class FoodMapDataSerializer(serializers.Serializer):
    """美食地图数据序列化器"""

    province = serializers.CharField()
    count = serializers.IntegerField()
    cities = serializers.ListField(child=serializers.DictField())
