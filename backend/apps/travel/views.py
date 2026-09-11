from django.db.models import Max
from django.utils import timezone

from rest_framework import status, views
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.toolkit.models import CityCoordinate

from .models import TravelPlan, TravelPlanItem, TravelRecord, TravelWish
from .serializers import TravelPlanItemSerializer, TravelPlanSerializer, TravelRecordSerializer, TravelWishSerializer
from .services import MapDataService, TravelPlanService, TravelStatsService, get_coordinates, get_province

# 心愿分类 → 计划子项类型（food/scenic/transport/hotel）
WISH_FOOD_CATEGORIES = {'美食', '夜市', '路线'}


def resolve_wish_coords(name: str, city: str):
    """心愿坐标解析：名称精确 → 名称模糊（景区优先）→ 城市定位。返回 (province, lng, lat)"""
    if name:
        row = CityCoordinate.objects.filter(name=name).first()
        if row:
            return row.province, row.lng, row.lat
        row = (
            CityCoordinate.objects.filter(city_type='景区', name__icontains=name).first()
            or CityCoordinate.objects.filter(name__icontains=name).first()
        )
        if row:
            return row.province, row.lng, row.lat
    if city:
        for cand in (city, f'{city}市', f'{city}州'):
            row = CityCoordinate.objects.filter(name=cand).first()
            if row:
                return row.province, row.lng, row.lat
        row = CityCoordinate.objects.filter(name__istartswith=city).order_by('id').first()
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
    """旅行计划 CRUD + 明细 + 统计"""

    queryset = TravelPlan.objects.all()
    serializer_class = TravelPlanSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return TravelPlan.objects.filter(user_id=1)

    def perform_create(self, serializer):
        plan = serializer.save(user_id=1)
        items_data = self.request.data.get('items', [])
        for item_data in items_data:
            TravelPlanItem.objects.create(plan=plan, **item_data)
        TravelPlanService.recalculate_total(plan)

    def perform_update(self, serializer):
        plan = serializer.save()
        # 编辑时带 items 则整体替换明细，未带（如仅改状态）则保留
        items_data = self.request.data.get('items')
        if items_data is not None:
            # 记录旧明细的心愿关联（按 类型|名称 复原），被移除的心愿回退为「想去」
            old_links = {f'{i.item_type}|{i.name}': i.wish_id for i in plan.items.all() if i.wish_id}
            plan.items.all().delete()
            for item_data in items_data:
                item = TravelPlanItem.objects.create(plan=plan, **item_data)
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

    @action(detail=True, methods=['get'])
    def items(self, request, pk=None):
        """计划子项列表"""
        plan = self.get_object()
        items = plan.items.all()
        return Response(TravelPlanItemSerializer(items, many=True).data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """统计所有计划费用"""
        return Response(TravelPlanService.get_stats())

    @action(detail=True, methods=['post'], url_path='toggle-item')
    def toggle_item(self, request, pk=None):
        """勾选/取消子项完成"""
        item_id = request.data.get('item_id')
        if not item_id:
            return Response({'error': '缺少 item_id'}, status=status.HTTP_400_BAD_REQUEST)
        plan = self.get_object()
        try:
            item = plan.items.get(id=item_id)
        except TravelPlanItem.DoesNotExist:
            return Response({'error': '子项不存在'}, status=status.HTTP_404_NOT_FOUND)
        item.is_completed = not item.is_completed
        item.completed_at = timezone.now() if item.is_completed else None
        item.save()
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
            prov, lng, lat = resolve_wish_coords(wish.name, wish.city)
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
        wish.save(update_fields=['status', 'visited_at'])
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
            dest = wish.city or wish.province or ''
            plan = TravelPlan.objects.create(
                user_id=1,
                name=f'{dest}之旅' if dest else '未命名行程',
                destination=dest,
                start_date=request.data.get('start_date') or None,
                status='计划中',
                notes='由旅行心愿单一键加入',
            )
        if plan.items.filter(wish=wish).exists():
            return Response({'error': '该心愿已在此计划中'}, status=status.HTTP_400_BAD_REQUEST)
        item_type = 'food' if wish.category in WISH_FOOD_CATEGORIES else 'scenic'
        next_sort = (plan.items.aggregate(m=Max('sort_order'))['m'] or 0) + 1
        item = TravelPlanItem.objects.create(
            plan=plan, wish=wish, item_type=item_type,
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
