"""三年赎回期 · 视图层"""
from datetime import date, timedelta

from rest_framework import status
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import RedemptionPoolInject, RedemptionAttrRule
from .serializers import (
    RedemptionPeriodSerializer, PoolInjectSerializer, AttrRuleSerializer,
)
from . import services


def _phase_label(period):
    total = (period.end_date - period.start_date).days + 1
    elapsed = (min(date.today(), period.end_date) - period.start_date).days + 1
    elapsed = max(elapsed, 0)
    ratio = elapsed / total if total else 0
    if ratio < 0.25:
        return '一·戒断与试探'
    if ratio < 0.5:
        return '二·深耕'
    if ratio < 0.75:
        return '三·复利'
    return '四·收束'


class RedemptionConfigView(APIView):
    """赎回期配置：GET 读配置+派生；PUT 改起止/本金。"""

    permission_classes = [AllowAny]

    def get(self, request):
        period = services.get_or_create_period()
        data = RedemptionPeriodSerializer(period).data
        data['derived'] = {
            'elapsed_days': services.compute_redemption_stats(period, include_time=False)['window']['elapsed_days'],
            'remaining_days': services.compute_redemption_stats(period, include_time=False)['window']['remaining_days'],
            'phase': _phase_label(period),
        }
        return Response(data)

    def put(self, request):
        period = services.get_or_create_period()
        serializer = RedemptionPeriodSerializer(period, data=request.data, partial=True)
        if serializer.is_valid():
            # 仅允许改起止与本金；暂停状态字段由 pause/resume 控制
            allowed = {'start_date', 'end_date', 'pool_principal'}
            for k in allowed:
                if k in serializer.validated_data:
                    setattr(period, k, serializer.validated_data[k])
            period.save(update_fields=['start_date', 'end_date', 'pool_principal', 'updated_at'])
            return Response(RedemptionPeriodSerializer(period).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RedemptionPauseView(APIView):
    """暂停追踪：停止评价与告警，但保留记录能力。"""

    permission_classes = [AllowAny]

    def post(self, request):
        period = services.get_or_create_period()
        if period.tracking_status == 'paused':
            return Response({'msg': '已在暂停中', 'tracking_status': 'paused'})
        period.tracking_status = 'paused'
        period.paused_since = date.today()
        resume_at = request.data.get('resume_at')
        period.resume_at = (
            date.fromisoformat(resume_at) if resume_at else date.today() + timedelta(days=14)
        )
        period.save(update_fields=['tracking_status', 'paused_since', 'resume_at', 'updated_at'])
        return Response({
            'tracking_status': 'paused',
            'paused_since': period.paused_since.isoformat(),
            'resume_at': period.resume_at.isoformat(),
        })


class RedemptionResumeView(APIView):
    """恢复追踪。"""

    permission_classes = [AllowAny]

    def post(self, request):
        period = services.get_or_create_period()
        period.tracking_status = 'active'
        period.paused_since = None
        period.resume_at = None
        period.save(update_fields=['tracking_status', 'paused_since', 'resume_at', 'updated_at'])
        return Response({'tracking_status': 'active'})


class InjectListCreateView(ListCreateAPIView):
    """现金池注入流水：GET 列表 / POST 新增。

    同 `AttrRuleListCreateView`：关掉全局分页，返回裸数组（前端按数组取用）。
    """

    queryset = RedemptionPoolInject.objects.all()
    serializer_class = PoolInjectSerializer
    permission_classes = [AllowAny]
    pagination_class = None


class AttrRuleListCreateView(ListCreateAPIView):
    """归因规则：GET 列表 / POST 新增。

    🔴 `pagination_class = None`：全局 `StandardPagination` 会把响应包成
    `{count, next, previous, results}`，而前端（`AttrRuleEditor.vue`）与 API 层
    （`request<AttrRule[]>`）都按**裸数组**取用 → 一旦分页生效，页面把对象当数组，
    `length` 得到 undefined，表现为「现有规则 ()」+ 空表格，**规则明明存在却看不见**
    （2026-09-18 发现：库内 3 条真实规则被显示成 0 条）。
    规则量级为个位数，本就不需要分页；与项目其他列表接口的裸数组风格保持一致。
    """

    queryset = RedemptionAttrRule.objects.all()
    serializer_class = AttrRuleSerializer
    permission_classes = [AllowAny]
    pagination_class = None


class AttrRuleDetailView(APIView):
    """归因规则：PUT 更新 / DELETE 删除。"""

    permission_classes = [AllowAny]

    def put(self, request, pk):
        try:
            rule = RedemptionAttrRule.objects.get(pk=pk)
        except RedemptionAttrRule.DoesNotExist:
            return Response({'error': '规则不存在'}, status=status.HTTP_404_NOT_FOUND)
        serializer = AttrRuleSerializer(rule, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        try:
            rule = RedemptionAttrRule.objects.get(pk=pk)
        except RedemptionAttrRule.DoesNotExist:
            return Response({'error': '规则不存在'}, status=status.HTTP_404_NOT_FOUND)
        rule.delete()
        return Response({'deleted': pk})


class RedemptionStatsView(APIView):
    """合体统计：窗口 / 池 / 档位 / 时间归因 / 单位成本。"""

    permission_classes = [AllowAny]

    def get(self, request):
        period = services.get_or_create_period()
        return Response(services.compute_redemption_stats(period, include_time=True))


class RedemptionSyncScenarioView(APIView):
    """同步到资金推演：preview 只返回不写库；apply 写入 WealthCurrentScenario。"""

    permission_classes = [AllowAny]

    def post(self, request):
        mode = request.data.get('mode', 'preview')
        if mode not in {'preview', 'apply'}:
            return Response({'error': "mode 仅支持 preview/apply"}, status=status.HTTP_400_BAD_REQUEST)
        period = services.get_or_create_period()
        return Response(services.sync_to_scenario(period, mode=mode))
