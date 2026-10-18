from rest_framework import serializers

from .models import Book


class BookListSerializer(serializers.ModelSerializer):
    """列表用序列化器——轻量字段"""
    status_display = serializers.SerializerMethodField()
    recommend_display = serializers.SerializerMethodField()
    btype_display = serializers.SerializerMethodField()
    reading_depth_display = serializers.SerializerMethodField()

    class Meta:
        model = Book
        fields = [
            'bid', 'years', 'btitle', 'author', 'btype', 'btype_display',
            'status', 'status_display', 'recommend', 'recommend_display',
            'reading_depth', 'reading_depth_display', 'readDate',
            'tags', 'created_at', 'action_item',
        ]

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_recommend_display(self, obj):
        return obj.get_recommend_display()

    def get_btype_display(self, obj):
        return obj.get_btype_display()

    def get_reading_depth_display(self, obj):
        return obj.get_reading_depth_display()


class BookDetailSerializer(serializers.ModelSerializer):
    """详情用序列化器——完整字段"""
    status_display = serializers.SerializerMethodField()
    recommend_display = serializers.SerializerMethodField()
    btype_display = serializers.SerializerMethodField()
    reading_depth_display = serializers.SerializerMethodField()

    class Meta:
        model = Book
        fields = '__all__'

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_recommend_display(self, obj):
        return obj.get_recommend_display()

    def get_btype_display(self, obj):
        return obj.get_btype_display()

    def get_reading_depth_display(self, obj):
        return obj.get_reading_depth_display()


class BookCreateUpdateSerializer(serializers.ModelSerializer):
    """创建/更新用序列化器——带验证"""

    class Meta:
        model = Book
        fields = [
            'years', 'btitle', 'author', 'original_title', 'btype', 'status',
            'recommend', 'reading_depth', 'readDate', 'tags',
            'abandon_reason', 'closedop', 'openop', 'action_item',
        ]
        read_only_fields = ['bid', 'created_at', 'updated_at']

    def validate_btitle(self, value):
        if value:
            value = value.strip().lstrip('《').rstrip('》')
            if not value:
                raise serializers.ValidationError('书名不能为空')
        return value

    def validate_author(self, value):
        if value:
            value = value.strip()
        return value

    def validate_recommend(self, value):
        if value is not None and (value < 0 or value > 5):
            raise serializers.ValidationError('推荐指数必须在 0-5 之间')
        return value

    def validate_reading_depth(self, value):
        if value is not None and (value < 1 or value > 5):
            raise serializers.ValidationError('阅读深度必须在 1-5 之间')
        return value

    def validate(self, attrs):
        status = attrs.get('status')
        if status == '弃读':
            old_status = self.instance.status if self.instance else None
            if old_status != '弃读' and not attrs.get('abandon_reason'):
                raise serializers.ValidationError({'abandon_reason': '弃读时必须填写弃读原因'})
        return attrs


class BookBulkUpdateSerializer(serializers.Serializer):
    """批量改「阅读状态」/「阅读深度」（阅读管理页的批量工具条）。

    🔴 这里**故意只开这两个字段**，而且**状态里没有「弃读」**：
    弃读在 `BookCreateUpdateSerializer.validate` 里是**逐本必填原因**的，
    批量给一个统一原因会把「为什么弃」写成假话 —— 所以那条路只走单本编辑。

    ⚠️ 约束挡在**后端**（而不是靠前端少画一项）：这样越界调用得到的是 400，
    而不是「看起来成功了、其实写了一条假原因」。
    """

    BULK_STATUS_CHOICES = [c for c in Book.STATUS_CHOICES if c[0] != '弃读']

    bids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False,
        error_messages={'empty': '请提供要修改的编号列表'},
    )
    status = serializers.ChoiceField(choices=BULK_STATUS_CHOICES, required=False)
    reading_depth = serializers.ChoiceField(choices=Book.READING_DEPTH_CHOICES, required=False)

    def validate(self, attrs):
        # 两个字段都不给 ⇒ 这个请求没有任何事要做，直接说清楚（而不是回一个「改了 0 本」）
        if 'status' not in attrs and 'reading_depth' not in attrs:
            raise serializers.ValidationError('请至少提供 status 或 reading_depth 之一')
        return attrs


class BookStatsSerializer(serializers.Serializer):
    """统计数据序列化器"""
    total_count = serializers.IntegerField(default=0)
    completed_count = serializers.IntegerField(default=0)
    reading_count = serializers.IntegerField(default=0)
    abandoned_count = serializers.IntegerField(default=0)
    planned_count = serializers.IntegerField(default=0)
    month_count = serializers.IntegerField(default=0)
    year_count = serializers.IntegerField(default=0)
    avg_recommend = serializers.FloatField(default=0)
    status_stats = serializers.ListField(default=[])
    type_stats = serializers.ListField(default=[])
    year_stats = serializers.ListField(default=[])
    recommend_stats = serializers.ListField(default=[])
    depth_stats = serializers.ListField(default=[])
