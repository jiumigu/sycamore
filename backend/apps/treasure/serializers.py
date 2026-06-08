from rest_framework import serializers

from .models import GoodThing


class GoodThingSerializer(serializers.ModelSerializer):
    """好恶物双面档案序列化器"""

    category_display = serializers.SerializerMethodField()
    record_type_display = serializers.SerializerMethodField()

    class Meta:
        model = GoodThing
        fields = [
            'id', 'user_id', 'record_type', 'record_type_display',
            'name', 'category', 'category_display',
            'scene', 'why_good', 'still_available', 'where_to_find',
            'avoid_reason', 'consequence',
            'tags', 'rating', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_category_display(self, obj):
        return obj.get_category_display()

    def get_record_type_display(self, obj):
        return obj.get_record_type_display()
