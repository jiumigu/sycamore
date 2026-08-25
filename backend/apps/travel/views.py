from django.utils import timezone

from rest_framework import status, views
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .models import TravelPlan, TravelPlanItem, TravelRecord
from .serializers import TravelPlanItemSerializer, TravelPlanSerializer, TravelRecordSerializer
from .services import MapDataService, TravelPlanService, TravelStatsService, get_coordinates, get_province


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
            plan.items.all().delete()
            for item_data in items_data:
                TravelPlanItem.objects.create(plan=plan, **item_data)
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
        return Response(TravelPlanItemSerializer(item).data)
