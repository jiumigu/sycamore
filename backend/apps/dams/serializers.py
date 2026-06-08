from rest_framework import serializers

from .models import DamsAccessLog, DamsFileResource


class DamsFileResourceSerializer(serializers.ModelSerializer):
    """文件资源序列化器"""

    file_category_label = serializers.SerializerMethodField()

    class Meta:
        model = DamsFileResource
        fields = [
            'id', 'name', 'path', 'storage_location', 'file_category',
            'file_category_label', 'file_size_mb', 'access_count',
            'last_accessed_at', 'folder_depth', 'parent_folder',
            'is_duplicate', 'is_organized', 'user_id', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'user_id', 'created_at', 'updated_at']

    def get_file_category_label(self, obj):
        return dict(obj._meta.get_field('file_category').choices).get(
            obj.file_category, obj.file_category
        )


class DamsFileResourceListSerializer(serializers.ModelSerializer):
    """文件资源列表精简序列化器"""

    file_category_label = serializers.SerializerMethodField()

    class Meta:
        model = DamsFileResource
        fields = [
            'id', 'name', 'path', 'file_category', 'file_category_label',
            'file_size_mb', 'access_count', 'last_accessed_at',
            'is_duplicate', 'is_organized',
        ]

    def get_file_category_label(self, obj):
        return dict(obj._meta.get_field('file_category').choices).get(
            obj.file_category, obj.file_category
        )


class DamsAccessLogSerializer(serializers.ModelSerializer):
    """访问日志序列化器"""

    file_name = serializers.CharField(source='file.name', read_only=True)

    class Meta:
        model = DamsAccessLog
        fields = [
            'id', 'file', 'file_name', 'accessed_at', 'user_id', 'created_at',
        ]
        read_only_fields = ['id', 'user_id', 'created_at']
