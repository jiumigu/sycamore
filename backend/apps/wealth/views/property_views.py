"""物件资产 · 视图层

**只做协议转换，一个除法都不在这里做** —— 派生值全部来自
`services/property_calc`（唯一真源），服务层只负责取数与组装。

⚠️ 列表 / 明细端点全部显式 `pagination_class = None`：
   被 DRF 全局分页包成 `{count, results}` 后，前端按数组消费会**静默显示为空**
   （项目硬坑③）—— 界面上看起来就是「一件家当都没有」。
"""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import WealthProperty, WealthPropertyCategory
from ..serializers.property_serializers import (
    PropertyCategoryFormSerializer,
    PropertyCategorySerializer,
    PropertyItemFormSerializer,
    PropertyItemSerializer,
    PropertyMetaSerializer,
    PropertySeedResultSerializer,
    PropertySummarySerializer,
)
from ..services import property_service as svc


class PropertyCategoryViewSet(viewsets.ModelViewSet):
    """物件类别：CRUD + 初始化默认类别

    ⚠️ 类别**只装用途**（家电 / 家具 / 数码 / 交通 / 家装 / 其他）。
       界面上「+ 新建类别」浮层里那行小字说的就是这件事 ——
       想说「它很大」或「它很贵」，用列表排序，不要建类别（设计文档 §4.3 专条）。
    """

    queryset = WealthPropertyCategory.objects.all()
    serializer_class = PropertyCategoryFormSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        return WealthPropertyCategory.objects.filter(user_id=1)

    def list(self, request, *args, **kwargs):
        rows = svc.get_category_list()
        return Response(PropertyCategorySerializer(rows, many=True).data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            row = svc.create_category(dict(serializer.validated_data))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            PropertyCategorySerializer(row).data, status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=kwargs.pop('partial', False),
        )
        serializer.is_valid(raise_exception=True)
        try:
            row = svc.update_category(instance.id, dict(serializer.validated_data))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PropertyCategorySerializer(row).data)

    def destroy(self, request, *args, **kwargs):
        """其下还有物件 → 400 + 可照做的提示，**不级联删除**"""
        instance = self.get_object()
        try:
            pk = svc.delete_category(instance.id)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'deleted': pk})

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        row = next(
            (r for r in svc.get_category_list() if r['id'] == instance.id), None,
        )
        return Response(PropertyCategorySerializer(row).data)

    @action(detail=False, methods=['post'])
    def seed(self, request):
        """初始化默认类别（幂等，**不预设任何物件**）"""
        overwrite = str(request.data.get('overwrite', '')).lower() in ('1', 'true', 'yes')
        result = svc.seed_property_categories(overwrite=overwrite)
        return Response(PropertySeedResultSerializer(result).data)


class PropertyItemViewSet(viewsets.ModelViewSet):
    """物件资产：CRUD + 保存前试算

    ⚠️ 刻意**不支持** `?ordering=`：排序在前端做 —— 一旦开到后端，
       `current_value`（派生值、不落库）就会被逼着落库，
       撕开「派生值不落库」这条口子（设计文档 §4.3 专条）。
    """

    queryset = WealthProperty.objects.all()
    serializer_class = PropertyItemFormSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        return WealthProperty.objects.filter(user_id=1)

    def list(self, request, *args, **kwargs):
        q = request.query_params
        rows = svc.get_item_list(
            category_id=q.get('category') or None,
            status=q.get('status') or None,
            condition=q.get('condition') or None,
            search=q.get('search') or None,
        )
        return Response(PropertyItemSerializer(rows, many=True).data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            row = svc.create_item(dict(serializer.validated_data))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            PropertyItemSerializer(row).data, status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=kwargs.pop('partial', False),
        )
        serializer.is_valid(raise_exception=True)
        try:
            row = svc.update_item(instance.id, dict(serializer.validated_data))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PropertyItemSerializer(row).data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        pk = svc.delete_item(instance.id)
        return Response({'deleted': pk})

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        row = svc.get_item(instance.id)
        return Response(PropertyItemSerializer(row).data)

    @action(detail=False, methods=['post'])
    def preview(self, request):
        """保存前试算（**不写库**）

        走的与保存**完全相同**的那段代码（`svc.preview_item` 造一个内存对象
        喂给同一个 `compute_property`），所以不会出现「试算一个数、保存另一个数」。

        ⚠️ 校验复用同一个表单序列化器：试算放行、一按保存报 400 比没有试算更误导。
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            row = svc.preview_item(dict(serializer.validated_data))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PropertyItemSerializer(row).data)


class PropertySummaryView(APIView):
    """首屏四卡（只读、实时算）"""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response(PropertySummarySerializer(svc.get_summary()).data)


class PropertyMetaView(APIView):
    """口径与枚举的单一出口 —— 前端不硬编码任何文案或选项"""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response(PropertyMetaSerializer(svc.get_meta()).data)
