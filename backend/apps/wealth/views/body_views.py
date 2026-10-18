"""身上之物 · 视图层

**只做协议转换，一个判断都不在这里做** —— `satisfaction_blank_reason` 与四个计数
全部来自 `services/body_calc`（唯一真源），服务层只负责取数与组装。

⚠️ 列表 / 明细端点全部显式 `pagination_class = None`：
   被 DRF 全局分页包成 `{count, results}` 后，前端按数组消费会**静默显示为空**
   （项目硬坑③）—— 界面上看起来就是「一条都没有」。
"""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import WealthBodyNeed, WealthBodyPart
from ..serializers.body_serializers import (
    BodyMetaSerializer,
    BodyNeedFormSerializer,
    BodyNeedSerializer,
    BodyPartFormSerializer,
    BodyPartSerializer,
    BodySeedResultSerializer,
    BodySummarySerializer,
)
from ..services import body_service as svc


class BodyPartViewSet(viewsets.ModelViewSet):
    """部位：CRUD + 初始化默认部位

    ⚠️ 部位**必须可增删改**，不能写成固定枚举：用户列的六项里「指甲」是「手」的
       一部分 —— 一个互斥枚举混进不同质的成员，必然变成兜底桶
       （treasure 实测：「方法」类占 74%）。
    """

    queryset = WealthBodyPart.objects.all()
    serializer_class = BodyPartFormSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        return WealthBodyPart.objects.filter(user_id=1)

    def list(self, request, *args, **kwargs):
        return Response(BodyPartSerializer(svc.get_part_list(), many=True).data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            row = svc.create_part(dict(serializer.validated_data))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(BodyPartSerializer(row).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=kwargs.pop('partial', False),
        )
        serializer.is_valid(raise_exception=True)
        try:
            row = svc.update_part(instance.id, dict(serializer.validated_data))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(BodyPartSerializer(row).data)

    def destroy(self, request, *args, **kwargs):
        """其下还有位 → 400 + 可照做的提示，**不级联删除**"""
        instance = self.get_object()
        try:
            pk = svc.delete_part(instance.id)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'deleted': pk})

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        row = next(
            (r for r in svc.get_part_list() if r['id'] == instance.id), None,
        )
        return Response(BodyPartSerializer(row).data)

    @action(detail=False, methods=['post'])
    def seed(self, request):
        """初始化默认部位（幂等，**不预设任何位**）"""
        overwrite = str(request.data.get('overwrite', '')).lower() in ('1', 'true', 'yes')
        result = svc.seed_parts(overwrite=overwrite)
        return Response(BodySeedResultSerializer(result).data)


class BodyNeedViewSet(viewsets.ModelViewSet):
    """位：CRUD

    ⚠️ 刻意**不支持** `?ordering=`：排序在服务层定死（按部位的自定义顺序、
       再按最近录入）—— 本模块没有派生数值列，排序没有别的诉求，
       开了这个口子只会让前端多一份可以漂移的口径。
    """

    queryset = WealthBodyNeed.objects.all()
    serializer_class = BodyNeedFormSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        return WealthBodyNeed.objects.filter(user_id=1)

    def list(self, request, *args, **kwargs):
        q = request.query_params
        # `pending=1` 与顶部那个「还没搞定」的数字**同源**
        # （都走 body_service.is_pending），所以点进去看到的行数一定对得上。
        pending = str(q.get('pending') or '').lower() in ('1', 'true', 'yes')
        rows = svc.get_need_list(
            part_id=q.get('part') or None,
            find_status=q.get('find_status') or None,
            pending_only=pending,
            search=q.get('search') or None,
        )
        return Response(BodyNeedSerializer(rows, many=True).data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            row = svc.create_need(dict(serializer.validated_data))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(BodyNeedSerializer(row).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=kwargs.pop('partial', False),
        )
        serializer.is_valid(raise_exception=True)
        try:
            row = svc.update_need(instance.id, dict(serializer.validated_data))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(BodyNeedSerializer(row).data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        pk = svc.delete_need(instance.id)
        return Response({'deleted': pk})

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        row = svc.get_need(instance.id)
        return Response(BodyNeedSerializer(row).data)


class BodySummaryView(APIView):
    """顶部计数（只读、实时算）"""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response(BodySummarySerializer(svc.get_summary()).data)


class BodyMetaView(APIView):
    """口径与枚举的单一出口 —— 前端不硬编码任何文案或选项"""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response(BodyMetaSerializer(svc.get_meta()).data)
