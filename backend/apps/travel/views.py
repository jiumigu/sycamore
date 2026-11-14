from collections import defaultdict

from django.db import transaction
from django.db.models import Max, Prefetch
from django.utils import timezone
from django.utils.dateparse import parse_date

from rest_framework import serializers, status, views
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.toolkit.models import CityCoordinate

from .models import TravelPlan, TravelPlanItem, TravelPlanStop, TravelRecord, TravelWish
from .serializers import (
    TravelPlanItemSerializer,
    TravelPlanSerializer,
    TravelPlanStopReadSerializer,
    TravelPlanStopSerializer,
    TravelRecordSerializer,
    TravelWishSerializer,
)
from .services import (
    MapDataService,
    TravelPlanService,
    TravelStatsService,
    TripLogService,
    get_coordinates,
    get_province,
    place_key,
    resolve_place,
)

# 心愿分类 → 计划子项类型（food/scenic/transport/hotel）
WISH_FOOD_CATEGORIES = {'美食', '夜市', '路线'}


def _lookup_coord(qs, name: str, city: str):
    """在给定候选集内解析：名称精确 → 名称模糊（景区优先）→ 城市定位"""
    if name:
        row = qs.filter(name=name).first()
        if row:
            return row
        row = (
            qs.filter(city_type='景区', name__icontains=name).first()
            or qs.filter(name__icontains=name).first()
        )
        if row:
            return row
    if city:
        for cand in (city, f'{city}市', f'{city}州'):
            row = qs.filter(name=cand).first()
            if row:
                return row
        row = qs.filter(name__istartswith=city).order_by('id').first()
        if row:
            return row
    return None


def resolve_wish_coords(name: str, city: str, province: str = ''):
    """心愿坐标解析，返回 (province, lng, lat)

    解析顺序（避免短名跨省撞车，如「连江」台湾省连江县 /「三门」河南三门峡市）：
    ① 行政区/景区类行（排除 city_type='其他'）本省 → ② 行政区/景区类全国
    → ③ 含「其他」类行本省 → ④ 含「其他」类全国
    """
    base = CityCoordinate.objects.all()
    ordered = [base.exclude(city_type='其他'), base]
    for qs in ordered:
        if province:
            row = _lookup_coord(qs.filter(province=province), name, city)
            if row:
                return row.province, row.lng, row.lat
        row = _lookup_coord(qs, name, city)
        if row:
            return row.province, row.lng, row.lat
    return '', None, None


class TravelPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'


class TravelRecordListCreateView(views.APIView):
    """旅行记录 列表 / 创建"""

    permission_classes = [AllowAny]

    def get(self, request):
        qs = TravelRecord.objects.all().order_by('-tyear', '-ttime')

        # 筛选
        year = request.query_params.get('year')
        province = request.query_params.get('province')
        if year:
            qs = qs.filter(tyear=int(year))
        if province:
            qs = qs.filter(parentnode__contains=province)

        paginator = TravelPagination()
        page = paginator.paginate_queryset(qs, request)
        if page is not None:
            serializer = TravelRecordSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = TravelRecordSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = TravelRecordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        # 自动地理编码
        city_name = data.get('tname', '')
        if city_name and not data.get('latitude'):
            coord = get_coordinates(city_name)
            if coord:
                data['latitude'] = coord[0]
                data['longitude'] = coord[1]

        record = TravelRecord.objects.create(**data)
        return Response(TravelRecordSerializer(record).data, status=status.HTTP_201_CREATED)


class TravelRecordDetailView(views.APIView):
    """旅行记录 详情 / 更新 / 删除"""

    permission_classes = [AllowAny]

    def get_object(self, pk):
        try:
            return TravelRecord.objects.get(tid=pk)
        except TravelRecord.DoesNotExist:
            return None

    def get(self, _request, pk):
        record = self.get_object(pk)
        if not record:
            return Response({'error': '记录不存在'}, status=status.HTTP_404_NOT_FOUND)
        return Response(TravelRecordSerializer(record).data)

    def put(self, request, pk):
        record = self.get_object(pk)
        if not record:
            return Response({'error': '记录不存在'}, status=status.HTTP_404_NOT_FOUND)

        serializer = TravelRecordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        # 自动补全地理编码
        city_name = data.get('tname', '')
        if city_name and not data.get('latitude'):
            coord = get_coordinates(city_name)
            if coord:
                data['latitude'] = coord[0]
                data['longitude'] = coord[1]

        for key, value in data.items():
            setattr(record, key, value)
        record.save()
        return Response(TravelRecordSerializer(record).data)

    def delete(self, _request, pk):
        record = self.get_object(pk)
        if not record:
            return Response({'error': '记录不存在'}, status=status.HTTP_404_NOT_FOUND)
        record.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MapDataView(views.APIView):
    """地图展示数据 — 省份热力 + 城市气泡"""

    permission_classes = [AllowAny]

    def get(self, request):
        year_from = request.query_params.get('year_from')
        year_to = request.query_params.get('year_to')
        if year_from:
            year_from = int(year_from)
        if year_to:
            year_to = int(year_to)
        data = MapDataService.get_map_data(year_from, year_to)
        return Response(data)


class TravelStatsView(views.APIView):
    """旅行统计总览"""

    permission_classes = [AllowAny]

    def get(self, request):
        year_from = request.query_params.get('year_from')
        year_to = request.query_params.get('year_to')
        if year_from:
            year_from = int(year_from)
        if year_to:
            year_to = int(year_to)
        data = TravelStatsService.get_stats(year_from, year_to)
        return Response(data)


class ProvinceListView(views.APIView):
    """到访省份列表"""

    permission_classes = [AllowAny]

    def get(self, _request):
        records = TravelRecord.objects.all().values_list('parentnode', flat=True).distinct()
        provinces = set()
        for p in records:
            if not p:
                continue
            prov = get_province(p)
            if prov:
                provinces.add(prov)
            elif p.endswith('市'):
                prov = get_province(p)
                if prov:
                    provinces.add(prov)
        result = [{'province': p} for p in sorted(provinces)]
        return Response(result)


class YearListView(views.APIView):
    """旅行年份列表"""

    permission_classes = [AllowAny]

    def get(self, _request):
        years = (
            TravelRecord.objects
            .filter(tyear__isnull=False)
            .values_list('tyear', flat=True)
            .distinct()
            .order_by('-tyear')
        )
        return Response([{'year': y} for y in years])


class TravelPlanViewSet(ModelViewSet):
    """旅行计划 CRUD + 站点（多城路线）+ 明细 + 统计

    三层结构见 `TravelPlanSerializer`：计划 → 站点（有序城市）→ 条目。
    条目 `stop IS NULL` 表示「不归属任何城市」（城际交通 / 还没归站）。
    """

    queryset = TravelPlan.objects.all()
    serializer_class = TravelPlanSerializer
    permission_classes = [AllowAny]

    #: `items` 数组里允许前端提交的键。其余键**不静默丢弃**，直接 400 ——
    #: 字段名写错就悄悄没写进去，是这类批量写入最难查的坑。
    ITEM_INPUT_FIELDS = ('item_type', 'name', 'estimate_cost', 'notes', 'sort_order', 'is_completed')

    def get_queryset(self):
        # 站点连条目一起预取：列表页 15 条计划 × 5 站，逐条 `.stops.prefetch_related()`
        # 会按计划数重复查站点表（N+1）
        return TravelPlan.objects.filter(user_id=1).prefetch_related(
            Prefetch('stops', queryset=TravelPlanStop.objects.prefetch_related('items')),
            'items',
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        # 列表页不展开条目（`items` 键整个不出现）：106 条子项只为列表算个路线串不值当
        ctx['with_items'] = getattr(self, 'action', None) != 'list'
        return ctx

    # ── 条目数组：创建 / 整体替换 ───────────────────────────────
    def _clean_item_rows(self, plan, rows, stops=None) -> list[dict]:
        """校验前端提交的 `items`，把 `stop` 换成**本计划**的站点对象

        🔴 `stop` 必须属于本计划。裸传 `TravelPlanItem(plan=p, stop=别人的站点)`
           是跨计划串数据 —— 列表里看不出来，只有地图上会突然多出一站。

        `stop_index` 只在**新建计划**时可用（按站点在 `stops` 数组里的下标指认，
        因为那时站点 id 还不存在）；给了 `stops` 就必须给下标，否则多站计划里
        条目会默认落到「路上」，用户建完发现预算跑到了城际交通里。
        """
        if not isinstance(rows, list):
            raise serializers.ValidationError({'items': '必须是数组'})
        # 默认归属站只算一次（每行都查一次就是 N 次查库，而且结果不可能变）
        fallback = TravelPlanService.sole_stop(plan) if plan is not None else None
        cleaned = []
        for row in rows:
            if not isinstance(row, dict):
                raise serializers.ValidationError({'items': '每一项必须是对象'})
            unknown = set(row) - set(self.ITEM_INPUT_FIELDS) - {'stop', 'stop_index'}
            if unknown:
                raise serializers.ValidationError(
                    {'items': f'不认识的字段：{"、".join(sorted(unknown))}'},
                )
            data = {k: row[k] for k in self.ITEM_INPUT_FIELDS if k in row}
            if 'stop_index' in row:
                index = row['stop_index']
                if not isinstance(index, int) or not 0 <= index < len(stops or []):
                    raise serializers.ValidationError(
                        {'items': f'stop_index={index} 超出站点范围（共 {len(stops or [])} 站）'},
                    )
                data['stop'] = stops[index]
            else:
                # 没写 `stop` 时：计划只有一站 ⇒ 就是那一站（单站是「多站路线」的特例，
                # 与迁移把老条目全挂到唯一一站上同一口径）；多站以上才留空「不归属城市」
                data['stop'] = self._own_stop(plan, row.get('stop')) or fallback
            cleaned.append(data)
        return cleaned

    #: 新建计划时随请求一起下的站点数组允许的键
    STOP_INPUT_FIELDS = ('city', 'province', 'days', 'notes')

    def _create_stops(self, plan, rows) -> list:
        """新建计划时按给定顺序建站（前端「一次把整条路线填完」）

        ⚠️ 空城市名报错而不是跳过：跳过会让后面几站整体前移一位，
           `stop_index` 全部错位，条目挂到隔壁城市上。
        """
        if not rows:
            return []
        if not isinstance(rows, list):
            raise serializers.ValidationError({'stops': '必须是数组'})
        created = []
        for i, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                raise serializers.ValidationError({'stops': f'第 {i} 站必须是对象'})
            unknown = set(row) - set(self.STOP_INPUT_FIELDS)
            if unknown:
                raise serializers.ValidationError(
                    {'stops': f'第 {i} 站有不认识的字段：{"、".join(sorted(unknown))}'},
                )
            city = str(row.get('city') or '').strip()
            if not city:
                raise serializers.ValidationError({'stops': f'第 {i} 站没有填城市'})
            days = row.get('days')
            if days is not None and (not isinstance(days, int) or days < 0):
                raise serializers.ValidationError({'stops': f'第 {i} 站的天数必须是非负整数'})
            created.append(TravelPlanService.add_stop(
                plan, city,
                province=row.get('province') or '',
                days=days,
                notes=row.get('notes') or '',
            ))
        return created

    def _own_stop(self, plan, stop_id):
        if stop_id in (None, ''):
            return None
        if plan is None:
            raise serializers.ValidationError({'items': '新建计划时还没有站点，不能指定 stop'})
        stop = plan.stops.filter(pk=stop_id).first()
        if stop is None:
            raise serializers.ValidationError({'items': f'站点 {stop_id} 不属于该计划'})
        return stop

    def _stop_payload(self, plan, stop) -> dict:
        """单个站点的出参（加站/改站后回给前端，字段与计划详情里的站点一致）"""
        ctx = {
            **self.get_serializer_context(),
            'with_items': True,
            'dates': TravelPlanService.arrive_dates(plan),
            'subtotals': TravelPlanService.subtotals(plan),
        }
        return TravelPlanStopReadSerializer(stop, context=ctx).data

    def perform_create(self, serializer):
        """建计划：可一次把整条路线（`stops`）和明细（`items`）带进来

        🔴 整段包事务：站点或条目校验失败时，**计划本身也不能留下** ——
           否则界面上多出一条「0 站 0 元」的空计划，用户以为创建成功了。

        ⚠️ `destination` 已转只读（派生值）。为兼容老调用方（脚本 / 旧前端），
           没有 `stops` 但传了 `destination` 时，仍把它当成**唯一一站**建出来；
           两者同时给则以 `stops` 为准（站点是真相，destination 是派生的）。
        """
        with transaction.atomic():
            plan = serializer.save(user_id=1)
            stops = self._create_stops(plan, self.request.data.get('stops'))
            if not stops:
                legacy_dest = str(self.request.data.get('destination') or '').strip()
                if legacy_dest:
                    stops = [TravelPlanService.add_stop(plan, legacy_dest)]
            rows = self._clean_item_rows(plan, self.request.data.get('items') or [], stops)
            for data in rows:
                TravelPlanItem.objects.create(plan=plan, **data)
            TravelPlanService.recalculate_total(plan)

    def perform_update(self, serializer):
        raw_items = self.request.data.get('items')
        plan_obj = self.get_object()
        # 同样先校验整份 items，再动库（整份替换里删到一半报错就是数据丢失）
        rows = None if raw_items is None else self._clean_item_rows(plan_obj, raw_items)

        plan = serializer.save()
        # 编辑时带 items 则整体替换明细，未带（如仅改状态）则保留
        if rows is not None:
            # 记录旧明细的心愿关联（按 类型|名称 复原），被移除的心愿回退为「想去」
            old_links = {f'{i.item_type}|{i.name}': i.wish_id for i in plan.items.all() if i.wish_id}
            plan.items.all().delete()
            for data in rows:
                item = TravelPlanItem.objects.create(plan=plan, **data)
                if not item.wish_id:
                    wid = old_links.get(f'{item.item_type}|{item.name}')
                    if wid:
                        item.wish_id = wid
                        item.save(update_fields=['wish'])
            new_wish_ids = {i.wish_id for i in plan.items.all() if i.wish_id}
            for wid in set(old_links.values()) - new_wish_ids:
                w = TravelWish.objects.filter(id=wid, status='已列入计划').first()
                if w:
                    w.status = '想去'
                    w.save(update_fields=['status'])
        TravelPlanService.recalculate_total(plan)

    def perform_destroy(self, instance):
        """删计划：**先删条目、再删站、最后删计划**

        🔴 `TravelPlanItem.stop` 是 `PROTECT`（删站时不许连带删掉用户手录的预算），
           但 Django 的 `ProtectedError` 会连**计划级联删除**一起挡下来 ——
           直接 `instance.delete()` 在「有计划 → 有站 → 站下有条目」时报 500。
           PROTECT 想拦的是「删一站」，不是「删整条计划」，所以这里显式按序删。
        """
        with transaction.atomic():
            instance.items.all().delete()
            instance.stops.all().delete()
            instance.delete()

    @action(detail=True, methods=['get', 'post'], url_path='items')
    def items(self, request, pk=None):
        """计划子项：GET 全量（含 `stop`），POST 新增一条（`stop` 可空 = 城际交通）"""
        plan = self.get_object()
        if request.method == 'GET':
            return Response(TravelPlanItemSerializer(plan.items.all(), many=True).data)

        ser = TravelPlanItemSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        stop = self._own_stop(plan, request.data.get('stop')) or TravelPlanService.sole_stop(plan)
        item = ser.save(plan=plan, stop=stop)
        TravelPlanService.recalculate_total(plan)
        return Response(TravelPlanItemSerializer(item).data, status=status.HTTP_201_CREATED)

    # ── 站点 ────────────────────────────────────────────────────
    @action(detail=True, methods=['post'], url_path='stops')
    def add_stop(self, request, pk=None):
        """加一站（默认追加到末尾）body: `{city, province?, days?, notes?}`"""
        plan = self.get_object()
        ser = TravelPlanStopSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        stop = TravelPlanService.add_stop(plan, **ser.validated_data)
        return Response(self._stop_payload(plan, stop), status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['patch', 'delete'], url_path=r'stops/(?P<stop_id>[0-9]+)')
    def stop_detail(self, request, pk=None, stop_id=None):
        """改一站（城市 / 天数 / 备注）或删一站

        删站有条目 ⇒ **400 并列出挡路的条目**，不级联：条目是用户手录的预算，
        连带删掉或改成「路上」都是在无声地改账。
        """
        plan = self.get_object()
        stop = plan.stops.filter(pk=stop_id).first()
        if stop is None:
            return Response({'error': '站点不存在'}, status=status.HTTP_404_NOT_FOUND)

        if request.method == 'DELETE':
            count = stop.items.count()
            if count:
                blocking = list(stop.items.all()[:5])
                return Response(
                    {
                        'error': f'这站下还有 {count} 条',
                        'blocking': [{'id': i.pk, 'name': i.name} for i in blocking],
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            stop.delete()
            TravelPlanService.recalculate_total(plan)  # 最后一站被删 ⇒ destination 要跟着回退
            return Response(status=status.HTTP_204_NO_CONTENT)

        ser = TravelPlanStopSerializer(stop, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        TravelPlanService.recalculate_total(plan)  # 改了城市 ⇒ 派生的 destination 跟着变
        return Response(self._stop_payload(plan, stop))

    @action(detail=True, methods=['post'], url_path='stops/reorder')
    def reorder_stops(self, request, pk=None):
        """一次重排全部站点 body: `{order: [31, 33, 32]}`

        🔴 **必须整份给**：只给一半会留下空洞顺序（1,3,7），下一站该用哪个
           `order` 就又要猜一次（见 `TravelPlanService.reorder_stops`）。
        """
        plan = self.get_object()
        raw = request.data.get('order')
        if not isinstance(raw, list) or not raw:
            return Response(
                {'error': 'order 必须是站点 id 数组（整份给）'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            ordered = [int(x) for x in raw]
        except (TypeError, ValueError):
            return Response(
                {'error': 'order 里的元素必须是整数 id'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            TravelPlanService.reorder_stops(plan, ordered)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        # 🔴 必须重新取一次：`plan` 是 `get_queryset()` 预取过的实例，
        #    `prefetch_related` 的缓存**不会**因为数据库被改了而失效，
        #    直接拿它序列化会吐出重排前的顺序（界面看起来「点了没反应」）。
        fresh = self.get_object()
        return Response({'stops': self.get_serializer(fresh).data['stops']})

    @action(detail=True, methods=['delete'], url_path=r'items/(?P<item_id>[0-9]+)')
    def delete_item(self, request, pk=None, item_id=None):
        """删一条条目

        🔴 这条端点存在的原因是：老界面靠「编辑弹窗整份替换 items」来删条目。
           Step 3 把弹窗的条目编辑器拿掉（它整份替换时会把所有条目重建，
           多站计划里新条目没有 `stop` ⇒ 全部掉进「路上」，归属静默丢失），
           没有它，加错一条就再也删不掉了。

        带心愿的条目被删 ⇒ 心愿退回「想去」，与 `perform_update` 整份替换同一口径。
        """
        plan = self.get_object()
        item = plan.items.filter(pk=item_id).first()
        if item is None:
            return Response({'error': '子项不存在'}, status=status.HTTP_404_NOT_FOUND)
        wish_id = item.wish_id
        item.delete()
        if wish_id:
            TravelWish.objects.filter(id=wish_id, status='已列入计划').update(status='想去')
        TravelPlanService.recalculate_total(plan)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path=r'items/(?P<item_id>[0-9]+)/move')
    def move_item(self, request, pk=None, item_id=None):
        """把条目挪到别站 / 挪到路上 body: `{stop: 32 | null}`

        `stop` 键**必须显式出现**（挪到路上就传 `null`）—— 用 `if 'stop' in data`
        判，不能按「取不到就当 null」，否则少传一个键会把条目悄悄从城市里摘走。
        """
        plan = self.get_object()
        item = plan.items.filter(pk=item_id).first()
        if item is None:
            return Response({'error': '子项不存在'}, status=status.HTTP_404_NOT_FOUND)
        if 'stop' not in request.data:
            return Response(
                {'error': '缺少 stop（挪到路上请显式传 null）'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        item.stop = self._own_stop(plan, request.data.get('stop'))
        item.save(update_fields=['stop'])
        TravelPlanService.recalculate_total(plan)
        return Response(TravelPlanItemSerializer(item).data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """统计所有计划费用"""
        return Response(TravelPlanService.get_stats())

    @action(detail=False, methods=['post'], url_path='route-preview')
    def route_preview(self, request):
        """路线 → 计划 预检：每站可带入的「想去」心愿"""
        destinations = [str(d).strip() for d in (request.data.get('destinations') or []) if str(d).strip()]
        if not destinations:
            return Response({'error': '至少需要一个目的地'}, status=status.HTTP_400_BAD_REQUEST)

        buckets: dict[str, list[TravelWish]] = defaultdict(list)
        for w in TravelWish.objects.filter(user_id=1, status='想去').order_by('category', 'name'):
            buckets[place_key(w.city, w.province)].append(w)

        stations = []
        for dest in destinations:
            matched = buckets.get(place_key(dest, ''), [])
            stations.append({
                'city': dest,
                # 能不能定位到坐标：推演页据此提示「这个名字地图上找不到」
                'located': resolve_place(dest, '') is not None,
                'wish_count': len(matched),
                'wishes': [
                    {
                        'id': w.id,
                        'name': w.name,
                        'category': w.category,
                        'is_food': w.category in WISH_FOOD_CATEGORIES,
                    }
                    for w in matched[:30]
                ],
            })
        return Response({'stations': stations})

    @action(detail=False, methods=['post'], url_path='from-route')
    def from_route(self, request):
        """由路线推演生成旅行计划（可把选中的本城心愿一并带入计划）"""
        origin = (request.data.get('origin') or '').strip()
        destinations = [str(d).strip() for d in (request.data.get('destinations') or []) if str(d).strip()]
        if not destinations:
            return Response({'error': '至少需要一个目的地'}, status=status.HTTP_400_BAD_REQUEST)

        route_name = (request.data.get('name') or '').strip()
        if not route_name:
            route_name = f'{destinations[0]}等 {len(destinations)} 站'
        destination = destinations[-1]

        raw_start = request.data.get('start_date')
        start_date = parse_date(str(raw_start)) if raw_start else None
        if raw_start and not start_date:
            return Response({'error': '出发日期格式应为 YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)

        route_desc = f'{" → ".join([origin] + destinations) if origin else " → ".join(destinations)}'
        plan = TravelPlan.objects.create(
            user_id=1,
            name=route_name,
            destination=destination,
            start_date=start_date,
            status='计划中',
            notes=f'由路线推演生成：{route_desc}',
        )

        # 一站一个站点，顺序即 destinations 的顺序；天数一律留空（推演阶段还不知道待几天）
        by_key: dict[str, TravelPlanStop] = {}
        for idx, dest in enumerate(destinations, start=1):
            by_key[place_key(dest, '')] = TravelPlanStop.objects.create(
                plan=plan, city=dest, order=idx,
            )

        sort = 0
        wish_ids = request.data.get('wish_ids') or []
        attached: list[TravelWish] = []
        unmatched: list[dict] = []
        if wish_ids:
            wishes = list(TravelWish.objects.filter(id__in=wish_ids, user_id=1))
            order = {wid: idx for idx, wid in enumerate(wish_ids)}
            wishes.sort(key=lambda w: order.get(w.id, 999))
            for w in wishes:
                # 心愿按它自己的城市落站，与推演页分桶用同一把尺子（place_key）。
                # 🔴 对不上站也**照样建条目**（`stop=NULL`）：用户勾了它就得进计划，
                #    只是落进「不归属任何城市」那一组，界面上几秒钟就能一键归站。
                #    丢掉才是真丢数据 —— 心愿状态还停在「想去」，事后没人知道少了一条。
                stop = by_key.get(place_key(w.city, w.province))
                if stop is None:
                    unmatched.append({'id': w.id, 'name': w.name, 'city': w.city})
                sort += 1
                TravelPlanItem.objects.create(
                    plan=plan,
                    stop=stop,
                    wish=w,
                    item_type='food' if w.category in WISH_FOOD_CATEGORIES else 'scenic',
                    name=w.name,
                    sort_order=sort,
                )
                attached.append(w)
        else:
            # 未选心愿时，为每个目的地建一条占位项，便于在计划页继续细化
            for dest in destinations:
                sort += 1
                TravelPlanItem.objects.create(
                    plan=plan, stop=by_key[place_key(dest, '')], item_type='scenic',
                    name=dest, sort_order=sort, notes='待细化',
                )

        if attached:
            TravelWish.objects.filter(
                id__in=[w.id for w in attached], status='想去',
            ).update(status='已列入计划')

        TravelPlanService.recalculate_total(plan)
        data = dict(TravelPlanSerializer(plan, context=self.get_serializer_context()).data)
        # 没落站的心愿显式回给前端（不静默丢），前端提示「这 2 条所在城市不在路线里」
        data['unmatched_wishes'] = unmatched
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='toggle-item')
    def toggle_item(self, request, pk=None):
        """勾选 / 取消勾选一个计划子项。

        请求体：`{'item_id': <int>, 'is_completed': <bool | 省略>}`

        - **省略** `is_completed` ⇒ 切换（保持前端既有行为，前端不传这个键）
        - **显式传** ⇒ 幂等设为该值。重试 / 双击不会把状态翻回去 ——
          旧实现是「永远取反」，同一个请求发两次等于什么都没做，
          而且用户网络抖动后重试会把刚勾上的又取消掉。

        🔴 口径订正（2026-10-18 第八轮审计 DQ-2）：**这条入口一直存在**，
           前端 `toggleTravelPlanItem()` 与后端这个 action 都在。
           「106 个子项 0 个完成」不是入口缺失，`is_completed` 字段也早就有了。
           ⇒ 审计报告里 DQ-2 的结论已作废，见报告 §2.7。
        """
        item_id = request.data.get('item_id')
        if not item_id:
            return Response({'error': '缺少 item_id'}, status=status.HTTP_400_BAD_REQUEST)
        plan = self.get_object()
        try:
            item = plan.items.get(id=item_id)
        except TravelPlanItem.DoesNotExist:
            return Response({'error': '子项不存在'}, status=status.HTTP_404_NOT_FOUND)

        raw = request.data.get('is_completed', None)
        target = (not item.is_completed) if raw is None else bool(raw)
        if target != item.is_completed:
            item.is_completed = target
            item.completed_at = timezone.now() if target else None
            item.save(update_fields=['is_completed', 'completed_at'])

        # 打卡联动心愿状态
        if item.wish_id:
            if item.is_completed:
                item.wish.status = '已打卡'
                item.wish.visited_at = timezone.localdate()
            else:
                item.wish.status = '已列入计划'
                item.wish.visited_at = None
            item.wish.save(update_fields=['status', 'visited_at'])
        return Response(TravelPlanItemSerializer(item).data)


class TravelWishViewSet(ModelViewSet):
    """旅行心愿单 CRUD + 加入计划 + 打卡"""

    queryset = TravelWish.objects.all()
    serializer_class = TravelWishSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        qs = TravelWish.objects.filter(user_id=1)
        category = self.request.query_params.get('category')
        status_q = self.request.query_params.get('status')
        province = self.request.query_params.get('province')
        city = self.request.query_params.get('city')
        search = self.request.query_params.get('search')
        if category:
            qs = qs.filter(category=category)
        if status_q:
            qs = qs.filter(status=status_q)
        if province:
            qs = qs.filter(province=province)
        if city:
            qs = qs.filter(city=city)
        if search:
            qs = qs.filter(name__icontains=search)
        return qs

    def perform_create(self, serializer):
        wish = serializer.save(user_id=1)
        if wish.lng is None or wish.lat is None:
            prov, lng, lat = resolve_wish_coords(wish.name, wish.city, wish.province)
            updates = {}
            if wish.lng is None and lng is not None:
                updates['lng'] = lng
            if wish.lat is None and lat is not None:
                updates['lat'] = lat
            if not wish.province and prov:
                updates['province'] = prov
            if updates:
                TravelWish.objects.filter(id=wish.id).update(**updates)
                for k, v in updates.items():
                    setattr(wish, k, v)

    @action(detail=True, methods=['post'])
    def mark_visited(self, request, pk=None):
        """打卡 / 取消打卡"""
        wish = self.get_object()
        if wish.status == '已打卡':
            # 取消打卡：有计划关联回到「已列入计划」，否则「想去」
            wish.status = '已列入计划' if wish.plan_items.exists() else '想去'
            wish.visited_at = None
        else:
            wish.status = '已打卡'
            wish.visited_at = request.data.get('visited_at') or timezone.localdate()
        wish.save(update_fields=['status', 'visited_at', 'updated_at'])
        return Response(TravelWishSerializer(wish).data)

    @action(detail=True, methods=['post'])
    def record_visit(self, request, pk=None):
        """打卡并记录：打卡日期 / 星级评分 / 打卡评价 / 是否值得反复

        已打卡的心愿再次调用即「修改记录」，未打卡的调用即「打卡 + 记录」。
        """
        wish = self.get_object()
        data = request.data
        fields = {'status', 'updated_at'}

        if 'visited_at' in data:
            raw = data.get('visited_at')
            if raw:
                parsed = parse_date(str(raw))
                if not parsed:
                    return Response({'error': '打卡日期格式应为 YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)
                wish.visited_at = parsed
            else:
                wish.visited_at = None
            fields.add('visited_at')
        if wish.visited_at is None:
            wish.visited_at = timezone.localdate()
            fields.add('visited_at')

        if 'visit_rating' in data:
            raw = data.get('visit_rating')
            if raw in (None, '', 'null'):
                wish.visit_rating = None
            else:
                try:
                    rating = int(raw)
                except (TypeError, ValueError):
                    rating = -1
                if rating < 1 or rating > 5:
                    return Response({'error': '评分应为 1-5 的整数'}, status=status.HTTP_400_BAD_REQUEST)
                wish.visit_rating = rating
            fields.add('visit_rating')

        if 'visit_notes' in data:
            wish.visit_notes = (data.get('visit_notes') or '').strip()
            fields.add('visit_notes')

        if 'worth_revisit' in data:
            raw = data.get('worth_revisit')
            wish.worth_revisit = raw is True or str(raw).lower() in ('true', '1', 'yes')
            fields.add('worth_revisit')

        if 'visit_plan' in data:
            raw_plan = data.get('visit_plan')
            if raw_plan in (None, '', 'null'):
                wish.visit_plan = None
            else:
                plan = TravelPlan.objects.filter(id=raw_plan, user_id=1).first()
                if not plan:
                    return Response({'error': '所属行程不存在'}, status=status.HTTP_404_NOT_FOUND)
                wish.visit_plan = plan
            fields.add('visit_plan')

        wish.status = '已打卡'
        wish.save(update_fields=sorted(fields))
        return Response(TravelWishSerializer(wish).data)

    @action(detail=True, methods=['post'])
    def add_to_plan(self, request, pk=None):
        """把心愿加入旅行计划（可指定已有计划，否则自动新建）"""
        wish = self.get_object()
        plan_id = request.data.get('plan_id')
        if plan_id:
            plan = TravelPlan.objects.filter(id=plan_id, user_id=1).first()
            if not plan:
                return Response({'error': '计划不存在'}, status=status.HTTP_404_NOT_FOUND)
        else:
            # 🔴 城市只认心愿自己的（`wish.city`）：条目要落在这座城的站上，
            #    让用户另填一个目的地就会出现「计划叫大理、条目挂在泉州」。
            #    `destination` 这一列已转只读派生，这里传了也会被站点覆盖。
            dest = wish.city or wish.province or ''
            name = (request.data.get('name') or '').strip() or (
                f'{dest}之旅' if dest else '未命名行程'
            )
            plan = TravelPlan.objects.create(
                user_id=1,
                name=name,
                destination=dest,
                start_date=request.data.get('start_date') or None,
                status='计划中',
                notes='由旅行心愿单一键加入',
            )
            # 新建的计划也要是一站路线，否则条目成了「不归属任何城市」，界面上没有站点可看
            if dest:
                TravelPlanService.add_stop(plan, dest)
        if plan.items.filter(wish=wish).exists():
            return Response({'error': '该心愿已在此计划中'}, status=status.HTTP_400_BAD_REQUEST)
        item_type = 'food' if wish.category in WISH_FOOD_CATEGORIES else 'scenic'
        next_sort = (plan.items.aggregate(m=Max('sort_order'))['m'] or 0) + 1
        # 落站规则与 from-route 一致：按城市找站，找不到就挂 null（不猜、不丢）
        stop = None
        if wish.city:
            key = place_key(wish.city, wish.province)
            stop = next(
                (s for s in plan.stops.all() if place_key(s.city, s.province) == key), None,
            )
        item = TravelPlanItem.objects.create(
            plan=plan, stop=stop, wish=wish, item_type=item_type,
            name=wish.name, sort_order=next_sort,
        )
        TravelPlanService.recalculate_total(plan)
        if wish.status == '想去':
            wish.status = '已列入计划'
            wish.save(update_fields=['status'])
        return Response({
            'plan': TravelPlanSerializer(plan).data,
            'item': TravelPlanItemSerializer(item).data,
        })

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """心愿统计：状态 × 分类"""
        qs = self.get_queryset()
        by_status = {s: qs.filter(status=s).count() for s, _ in TravelWish.STATUS_CHOICES}
        by_category = {c: qs.filter(category=c).count() for c, _ in TravelWish.CATEGORY_CHOICES}
        located = qs.filter(lng__isnull=False, lat__isnull=False).count()
        return Response({'total': qs.count(), 'located': located, 'by_status': by_status, 'by_category': by_category})


class TripLogView(views.APIView):
    """行程日志 — 已打卡心愿按「日期 + 地点」聚合为一天一张卡

    只读；打卡不直接写旅行记录表，沉淀由 consolidate 显式触发。
    """

    permission_classes = [AllowAny]

    def get(self, request):
        raw_from = request.query_params.get('from')
        raw_to = request.query_params.get('to')
        date_from = parse_date(str(raw_from)) if raw_from else None
        date_to = parse_date(str(raw_to)) if raw_to else None
        if raw_from and not date_from:
            return Response({'error': 'from 日期格式应为 YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)
        if raw_to and not date_to:
            return Response({'error': 'to 日期格式应为 YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)

        plan_id = request.query_params.get('plan')
        city = request.query_params.get('city')
        data = TripLogService.build(
            date_from=date_from,
            date_to=date_to,
            plan_id=int(plan_id) if plan_id else None,
            city=city or None,
        )
        return Response(data)


class TripLogConsolidateView(views.APIView):
    """把某天某地的打卡清单沉淀为一条旅行足迹（只新增记录，不改动存量）"""

    permission_classes = [AllowAny]

    def post(self, request):
        raw_date = request.data.get('date')
        if not raw_date:
            return Response({'error': '缺少 date（YYYY-MM-DD）'}, status=status.HTTP_400_BAD_REQUEST)
        visit_date = parse_date(str(raw_date))
        if not visit_date:
            return Response({'error': '日期格式应为 YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)

        city = (request.data.get('city') or '').strip()

        candidates = list(
            TravelWish.objects.filter(
                user_id=1, status='已打卡', visited_at=visit_date, visit_record_id__isnull=True,
            ).order_by('category', 'name')
        )
        if city:
            target = place_key(city, '')
            candidates = [w for w in candidates if place_key(w.city, w.province) == target]
        if not candidates:
            return Response({'error': '该日期没有待沉淀的打卡记录'}, status=status.HTTP_400_BAD_REQUEST)

        first = candidates[0]
        place = (city or first.city or first.province or '').strip()
        province = first.province or (get_province(place) or '')

        # 坐标：优先取打卡点均值，其次查城市坐标
        lngs = [float(w.lng) for w in candidates if w.lng is not None]
        lats = [float(w.lat) for w in candidates if w.lat is not None]
        if lngs and lats:
            longitude = round(sum(lngs) / len(lngs), 6)
            latitude = round(sum(lats) / len(lats), 6)
        else:
            coord = get_coordinates(place) or get_coordinates(first.city or '')
            latitude, longitude = (coord[0], coord[1]) if coord else (None, None)

        # 摘要（tremark 限 255）
        summary = request.data.get('tremark') or '、'.join(w.name for w in candidates)
        summary = summary.strip()[:255]
        if not summary:
            summary = f'{place}打卡'

        ratings = [w.visit_rating for w in candidates if w.visit_rating]
        payload = {'user_id': 1}

        raw_rating = request.data.get('rating')
        if raw_rating in (None, '', 'null'):
            payload['rating'] = round(sum(ratings) / len(ratings)) if ratings else None
        else:
            try:
                rating = int(raw_rating)
            except (TypeError, ValueError):
                return Response({'error': '满意度应为 1-5 的整数'}, status=status.HTTP_400_BAD_REQUEST)
            if rating < 1 or rating > 5:
                return Response({'error': '满意度应为 1-5 的整数'}, status=status.HTTP_400_BAD_REQUEST)
            payload['rating'] = rating

        raw_cost = request.data.get('tcost')
        if raw_cost in (None, '', 'null'):
            payload['tcost'] = None
        else:
            try:
                payload['tcost'] = float(raw_cost)
            except (TypeError, ValueError):
                return Response({'error': '花费应为数字'}, status=status.HTTP_400_BAD_REQUEST)

        raw_days = request.data.get('duration_days')
        if raw_days in (None, '', 'null'):
            payload['duration_days'] = 1
        else:
            try:
                payload['duration_days'] = max(1, int(raw_days))
            except (TypeError, ValueError):
                return Response({'error': '停留天数应为整数'}, status=status.HTTP_400_BAD_REQUEST)

        record = TravelRecord.objects.create(
            parentnode=province or None,
            tname=place or None,
            district=first.district or '',
            tyear=visit_date.year,
            ttime=visit_date,
            tremark=summary,
            companions=(request.data.get('companions') or '').strip()[:200],
            latitude=latitude,
            longitude=longitude,
            **payload,
        )

        TravelWish.objects.filter(id__in=[w.id for w in candidates]).update(visit_record_id=record.tid)

        return Response({
            'record': TravelRecordSerializer(record).data,
            'consolidated_ids': [w.id for w in candidates],
            'count': len(candidates),
        }, status=status.HTTP_201_CREATED)
