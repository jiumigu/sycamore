"""作品 · 视图层

🔴 三条贯穿性约定（与自我运转同款）：

1. **`GET` 一律不写库** —— 出口去向清单在没有那行时**下发默认值但不落库**
   （项目铁律：只读接口别 `get_or_create`）。
2. **每个写操作返回里带 `written`** —— 写了哪张表、几行，运行时可见。
3. **列表端点一律 `pagination_class = None` 返回裸数组**
   （DRF 全局分页会包成 `{count, results}` ⇒ 前端按数组取用即「假 0」）。

⚠️ **期标识只由后端算**（`?period_type=weekly|monthly`），前端不自己比字符串。
"""
from django.utils import timezone
from rest_framework import status as http
from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

# ⚠️ 复用自我运转的周期实现 —— 期标识全项目只有一把尺子。
from apps.selfrun.readers import period_range

from . import services
from .constants import (
    CAPTURE_SOURCE_CHOICES,
    WORK_KIND_CHOICES,
    WORK_STATUS_CHOICES,
)
from .models import Work, WorkCapture
from .serializers import (
    CaptureInputSerializer,
    CaptureSerializer,
    ChannelsSerializer,
    ComposeSerializer,
    WorkInputSerializer,
    WorkSerializer,
)

PERIOD_TYPES = ('weekly', 'monthly')


def _period_context(request):
    """把「当前是哪一期」算好塞进序列化器 —— 前端零计算。"""
    pt = request.query_params.get('period_type') or 'weekly'
    if pt not in PERIOD_TYPES:
        pt = 'weekly'
    return {
        'period_type': pt,
        'current_period_key': period_range(pt, timezone.localdate())[2],
    }


# ══════════════════════════════════════════════════════════════
# 作品
# ══════════════════════════════════════════════════════════════

class WorkViewSet(viewsets.ModelViewSet):
    """作品列表 / 新建 / 编辑 / 删除。

    删除 ⇒ 它的来源**回到待提炼**（合成可逆，一条都不丢）。
    """

    queryset = Work.objects.all()
    permission_classes = [AllowAny]
    pagination_class = None

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return WorkInputSerializer
        return WorkSerializer

    def get_queryset(self):
        qs = Work.objects.prefetch_related('captures')
        params = self.request.query_params
        kind = params.get('kind')
        if kind:
            qs = qs.filter(kind=kind)
        status_ = params.get('status')
        if status_:
            qs = qs.filter(status=status_)
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx.update(_period_context(self.request))
        return ctx

    def create(self, request, *args, **kwargs):
        ser = WorkInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        work = ser.save()
        return Response(
            {
                'work': WorkSerializer(work, context=self.get_serializer_context()).data,
                'written': {'works_work': 1},
            },
            status=http.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        work = self.get_object()
        ser = WorkInputSerializer(work, data=request.data, partial=partial)
        ser.is_valid(raise_exception=True)
        work = ser.save()
        return Response({
            'work': WorkSerializer(work, context=self.get_serializer_context()).data,
            'written': {'works_work': 1},
        })

    def destroy(self, request, *args, **kwargs):
        work = self.get_object()
        name = work.name
        n = services.delete_work(work)
        return Response({
            'detail': f'已删除「{name}」，{n} 条来源回到待提炼',
            'written': {'works_work': -1, 'works_capture': n},
        })


# ══════════════════════════════════════════════════════════════
# 待提炼（捕获）
# ══════════════════════════════════════════════════════════════

class CaptureViewSet(viewsets.ModelViewSet):
    """打勾 / 取消勾 / 列表。

    ⚠️ `POST` 是**幂等**的：同一来源重复打勾只留一条（200 而不是 201）。
       前端「完成某件事时顺手打勾」可能因为重试而调两次。
    ⚠️ `DELETE` 是**真删**（标记不是流水）；已收进作品的不许删。
    """

    queryset = WorkCapture.objects.select_related('work')
    permission_classes = [AllowAny]
    pagination_class = None
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'create':
            return CaptureInputSerializer
        return CaptureSerializer

    def get_queryset(self):
        qs = WorkCapture.objects.select_related('work')
        params = self.request.query_params
        status_ = params.get('status')
        if status_:
            qs = qs.filter(status=status_)
        source_type = params.get('source_type')
        if source_type:
            qs = qs.filter(source_type=source_type)
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx.update(_period_context(self.request))
        return ctx

    def create(self, request, *args, **kwargs):
        ser = CaptureInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj, created = services.capture(**ser.validated_data)
        return Response(
            {
                'capture': CaptureSerializer(obj, context=self.get_serializer_context()).data,
                'created': created,
                'written': {'works_capture': 1 if created else 0},
            },
            status=http.HTTP_201_CREATED if created else http.HTTP_200_OK,
        )

    def destroy(self, request, *args, **kwargs):
        obj = services.uncapture(kwargs['pk'])
        if obj is None:
            return Response({'detail': '这条已经不在了'}, status=http.HTTP_404_NOT_FOUND)
        return Response({
            'detail': '已取消标记',
            'written': {'works_capture': -1},
        })


# ══════════════════════════════════════════════════════════════
# 合成
# ══════════════════════════════════════════════════════════════

class ComposeView(APIView):
    """把若干条待提炼**合成一件作品** —— 「编译」这个动作在界面上的形态。"""

    permission_classes = [AllowAny]

    def post(self, request):
        ser = ComposeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        work = services.compose(**data)
        ctx = _period_context(request)
        return Response(
            {
                'work': WorkSerializer(work, context=ctx).data,
                'written': {'works_work': 1, 'works_capture': len(data['capture_ids'])},
            },
            status=http.HTTP_201_CREATED,
        )


# ══════════════════════════════════════════════════════════════
# 计数 / 枚举 / 出口去向
# ══════════════════════════════════════════════════════════════

class OverviewView(APIView):
    """顶部计数：累计 N 件 · 已发 M 件 · 待提炼 K 条。"""

    permission_classes = [AllowAny]

    def get(self, request):
        data = services.overview()
        data['channels'] = services.list_channels()
        return Response(data)


class WorkMetaView(APIView):
    """界面枚举（**随接口下发，前端零副本**）。

    ⚠️ 键名清单是契约：改了这里必须同时改前端类型 —— 但**漏改不会报错**，
       只会让某个下拉少一项（项目高频硬坑：键名写错看不出来）。
       ⇒ 有一条用例专门钉这份键名清单。
    """

    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            'kinds': [{'value': v, 'label': l} for v, l in WORK_KIND_CHOICES],
            'statuses': [{'value': v, 'label': l} for v, l in WORK_STATUS_CHOICES],
            'sources': [{'value': v, 'label': l} for v, l in CAPTURE_SOURCE_CHOICES],
            'channels': services.list_channels(),
        })


class ChannelsView(APIView):
    """出口去向清单（用户自己维护的短清单）。"""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response({'values': services.list_channels()})

    def put(self, request):
        ser = ChannelsSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        values = services.save_channels(ser.validated_data['values'])
        return Response({'values': values, 'written': {'core_system_preset': 1}})
