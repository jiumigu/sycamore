from django.utils import timezone
from rest_framework import serializers

from apps.core.fields import AmountNumberField

from .models import TravelPlan, TravelPlanItem, TravelPlanStop, TravelRecord, TravelWish
from .services import TravelPlanService, resolve_place


def _money(value) -> float:
    """Decimal → number（出参统一 number：前端 `formatAmount` 遇字符串会渲染成 `¥—`）"""
    return round(float(value or 0), 2)


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
    """旅行计划子项序列化器

    `stop` 只读：条目的归属站点**只经由** `move` / `items` 端点写，
    不跟着通用 `items` 数组走 —— 那样前端可以塞一个别的计划的站点 id，
    条目就挂到别人家的路线上去了（跨计划串数据，界面上看不出来）。
    """

    estimate_cost = AmountNumberField(max_digits=10, decimal_places=2)

    class Meta:
        model = TravelPlanItem
        fields = ['id', 'item_type', 'name', 'estimate_cost', 'is_completed', 'completed_at', 'notes', 'sort_order', 'wish', 'stop']
        read_only_fields = ['id', 'stop']


class TravelPlanStopSerializer(serializers.ModelSerializer):
    """站点**写入**用（加一站 / 改天数·备注·城市）

    ⚠️ 出参不走这个序列化器（它没有 `subtotal` / `arrive_date` / 坐标），
       见 `TravelPlanStopReadSerializer`。
    """

    class Meta:
        model = TravelPlanStop
        fields = ['id', 'city', 'province', 'days', 'notes']
        read_only_fields = ['id']

    def validate_city(self, value: str) -> str:
        city = (value or '').strip()
        if not city:
            raise serializers.ValidationError('城市不能为空')
        return city

    def validate_days(self, value):
        # `null` = 天数待定，`0` = 路过不过夜 —— 两者是不同的事，都合法
        if value is not None and value < 0:
            raise serializers.ValidationError('天数不能为负')
        return value


class TravelPlanStopReadSerializer(serializers.Serializer):
    """站点**出参**：城市的规范名 / 坐标 / 到达日期 / 本站合计全部现算

    🔴 这里只做「组装」，所有数字来自 `TravelPlanService`（`arrive_dates` /
       `subtotals` / `resolve_place`），本文件不重新定义任何口径。

    - `city` = 坐标表里的规范名（「泉州」→「泉州市」），`city_input` = 用户填的原样；
    - `located=False` ⇒ 城市名没在坐标表里找到：照常列出来，但**不要画到地图上**
      （猜坐标就会落到海里）；
    - `days=null` ⇒ 「待定」，不是 0；`arrive_date` 随之算不出来（也给 `null`）。
    """

    id = serializers.IntegerField(read_only=True)
    order = serializers.IntegerField(read_only=True)
    city = serializers.SerializerMethodField()
    city_input = serializers.CharField(source='city', read_only=True)
    province = serializers.CharField(read_only=True)
    days = serializers.IntegerField(read_only=True, allow_null=True)
    arrive_date = serializers.SerializerMethodField()
    located = serializers.SerializerMethodField()
    lat = serializers.SerializerMethodField()
    lng = serializers.SerializerMethodField()
    subtotal = serializers.SerializerMethodField()
    counts = serializers.SerializerMethodField()
    notes = serializers.CharField(read_only=True)
    items = TravelPlanItemSerializer(many=True, read_only=True)

    def get_fields(self):
        """列表接口不带条目：`items` 键**整个不出现**，不是给个空数组

        🔴 空数组与「不展开」在界面上长得一样，但含义相反 —— 前者会被读成
           「这一站什么都没有」。
        """
        fields = super().get_fields()
        if not self.context.get('with_items'):
            fields.pop('items', None)
        return fields

    def _hit(self, obj):
        """按站缓存一次定位结果（一个站要出 city/lat/lng/located 四个字段）"""
        if not hasattr(obj, '_place_hit'):
            obj._place_hit = resolve_place(obj.city, obj.province)
        return obj._place_hit

    def get_city(self, obj) -> str:
        hit = self._hit(obj)
        return hit[0] if hit else obj.city

    def get_arrive_date(self, obj):
        day = self.context.get('dates', {}).get(obj.pk)
        return day.isoformat() if day else None

    def get_located(self, obj) -> bool:
        return self._hit(obj) is not None

    def get_lat(self, obj):
        hit = self._hit(obj)
        return hit[1] if hit else None

    def get_lng(self, obj):
        hit = self._hit(obj)
        return hit[2] if hit else None

    def get_subtotal(self, obj) -> float:
        return _money(self.context.get('subtotals', {}).get(obj.pk))

    def get_counts(self, obj) -> dict:
        counts = {key: 0 for key, _ in TravelPlanItem.ITEM_TYPES}
        for item in obj.items.all():
            counts[item.item_type] = counts.get(item.item_type, 0) + 1
        return counts


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
    """旅行计划序列化器（三层下发）

    ```
    计划
    ├── stops[]            按顺序的站点，各带本站合计与条目
    ├── transfer_items[]   「路上」——不归属任何城市的条目（城际交通）
    ├── stops_total / transfer_total / total_estimate
    └── total_days         全程天数（任一站未知 ⇒ null）
    ```

    ⚠️ **顶层 `items` 已删**（v3.64.52）：条目只出现在 `stops[].items` 与
       `transfer_items` 两处。同一批条目给三个出口，前端早晚会有一处读到旧的那份；
       而且列表页带上 100+ 条子项只为了算个路线串，不值当。

    🔴 `destination` 只读 = 派生值（最后一站的城市名，见
       `TravelPlanService.sync_destination`）。它给「列表页 / 导出 / 老接口」兜底，
       **不再是输入**：能填就有第二个真相，改完站点两边就打架，而界面上看不出来。
       建计划要指定城市，请走 `stops`（订单站：`[{city, days?, notes?}]`）。
    """

    total_estimate = AmountNumberField(max_digits=12, decimal_places=2, read_only=True)
    stops = serializers.SerializerMethodField()
    transfer_items = serializers.SerializerMethodField()
    stops_total = serializers.SerializerMethodField()
    transfer_total = serializers.SerializerMethodField()
    total_days = serializers.SerializerMethodField()

    class Meta:
        model = TravelPlan
        fields = [
            'id', 'name', 'destination', 'start_date', 'status', 'total_estimate',
            'notes', 'created_at', 'updated_at',
            'stops', 'transfer_items', 'stops_total', 'transfer_total', 'total_days',
        ]
        read_only_fields = ['id', 'destination', 'total_estimate', 'created_at', 'updated_at']

    # ── 派生值：每个计划只算一次（一个响应里三个字段要用同一份）──
    def _totals(self, plan) -> dict:
        if not hasattr(self, '_totals_cache'):
            self._totals_cache = {}
        if plan.pk not in self._totals_cache:
            self._totals_cache[plan.pk] = TravelPlanService.totals(plan)
        return self._totals_cache[plan.pk]

    def get_stops(self, plan):
        ctx = {
            **self.context,
            'dates': TravelPlanService.arrive_dates(plan),
            'subtotals': TravelPlanService.subtotals(plan),
        }
        # 计数要用到条目，列表页也一样（`with_items` 只决定要不要把条目本身吐出去）
        return TravelPlanStopReadSerializer(
            plan.stops.all(), many=True, context=ctx,
        ).data

    def get_transfer_items(self, plan):
        # 与站点下的条目同一批对象：`stop IS NULL` 就是「不属于任何城市」
        return TravelPlanItemSerializer(
            plan.items.filter(stop__isnull=True), many=True,
        ).data

    def get_stops_total(self, plan) -> float:
        return _money(self._totals(plan)['stops_total'])

    def get_transfer_total(self, plan) -> float:
        return _money(self._totals(plan)['transfer_total'])

    def get_total_days(self, plan):
        return TravelPlanService.total_days(plan)
