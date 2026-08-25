from rest_framework import serializers

from .models import LifeSample, ObsidianConfig


class LifeSampleSerializer(serializers.ModelSerializer):
    obsidian_full_path = serializers.SerializerMethodField()
    status_label = serializers.CharField(read_only=True)
    relevance_label = serializers.CharField(read_only=True)

    class Meta:
        model = LifeSample
        fields = [
            'id', 'name', 'alias', 'sample_type', 'tags',
            'summary', 'obsidian_path', 'obsidian_full_path',
            'my_note', 'related_goals', 'related_diary',
            'status', 'status_label', 'verified_at', 'reviewed_at',
            'relevance', 'relevance_label', 'relevance_reason',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at', 'verified_at', 'reviewed_at']

    def get_obsidian_full_path(self, obj: LifeSample) -> str:
        return obj.obsidian_full_path


class ObsidianConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = ObsidianConfig
        fields = ['id', 'enabled', 'vault_path', 'samples_folder', 'updated_at']
        read_only_fields = ['updated_at']


class ScanResultSerializer(serializers.Serializer):
    name = serializers.CharField()
    alias = serializers.CharField(required=False, default='')
    era = serializers.CharField(required=False, default='')
    region = serializers.CharField(required=False, default='')
    birth_year = serializers.IntegerField(required=False, allow_null=True, default=None)
    death_year = serializers.IntegerField(required=False, allow_null=True, default=None)
    type = serializers.CharField(required=False, default='historical')
    tags = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    summary = serializers.CharField(required=False, default='')
    path = serializers.CharField()
    filename = serializers.CharField()
    modified_at = serializers.CharField(required=False, default='')
    exists = serializers.BooleanField(required=False, default=True)
