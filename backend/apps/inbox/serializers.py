from rest_framework import serializers

from .models import InboxItem, InboxProcessLog


class InboxProcessLogSerializer(serializers.ModelSerializer):
    action_display = serializers.SerializerMethodField()

    class Meta:
        model = InboxProcessLog
        fields = [
            'id', 'inbox', 'action', 'action_display',
            'target_type', 'target_id', 'notes', 'user_id', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_action_display(self, obj):
        return obj.get_action_display()


class InboxItemSerializer(serializers.ModelSerializer):
    category_display = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    priority_display = serializers.SerializerMethodField()
    source_display = serializers.SerializerMethodField()

    class Meta:
        model = InboxItem
        fields = [
            'id', 'content', 'description',
            'category', 'category_display',
            'tags', 'status', 'status_display',
            'source', 'source_display',
            'target_type', 'target_id',
            'due_date', 'remind_at', 'processed_at',
            'priority', 'priority_display',
            'user_id', 'created_at', 'updated_at',
            'completion_note',
        ]
        read_only_fields = ['id', 'processed_at', 'created_at', 'updated_at', 'completion_note']

    def get_category_display(self, obj):
        return obj.get_category_display()

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_priority_display(self, obj):
        return obj.get_priority_display()

    def get_source_display(self, obj):
        return obj.get_source_display()


class InboxItemDetailSerializer(serializers.ModelSerializer):
    category_display = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    priority_display = serializers.SerializerMethodField()
    source_display = serializers.SerializerMethodField()
    process_logs = InboxProcessLogSerializer(many=True, read_only=True)

    class Meta:
        model = InboxItem
        fields = [
            'id', 'content', 'description',
            'category', 'category_display',
            'tags', 'status', 'status_display',
            'source', 'source_display',
            'target_type', 'target_id',
            'due_date', 'remind_at', 'processed_at',
            'priority', 'priority_display',
            'user_id', 'created_at', 'updated_at',
            'completion_note',
            'process_logs',
        ]
        read_only_fields = ['id', 'processed_at', 'created_at', 'updated_at', 'completion_note']

    def get_category_display(self, obj):
        return obj.get_category_display()

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_priority_display(self, obj):
        return obj.get_priority_display()

    def get_source_display(self, obj):
        return obj.get_source_display()


class BatchActionSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
    action = serializers.ChoiceField(choices=['complete', 'archive', 'delete', 'convert_to_goal', 'convert_to_milestone', 'convert_to_sugar'])
    target_type = serializers.CharField(required=False, allow_null=True)
    target_id = serializers.IntegerField(required=False, allow_null=True)


class InboxStatsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    pending = serializers.IntegerField()
    done_this_week = serializers.IntegerField()
    overdue = serializers.IntegerField()
    by_category = serializers.DictField()
    by_priority = serializers.DictField()
