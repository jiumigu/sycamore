from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import HealthRecord, MenstrualRecord, WeightGoal, WeightGoalAdjustment, WeightMilestone, WeightRecord, UserBodyInfo
from .serializers import (
    HealthRecordSerializer,
    MenstrualRecordSerializer,
    UserBodyInfoSerializer,
    WeightGoalAdjustmentSerializer,
    WeightGoalSerializer,
    WeightMilestoneSerializer,
    WeightRecordSerializer,
)
from .services import HealthStatsService, WeightService


class HealthRecordViewSet(viewsets.ModelViewSet):
    """运动记录视图集"""

    queryset = HealthRecord.objects.all()
    permission_classes = [AllowAny]
    serializer_class = HealthRecordSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['remark']
    ordering_fields = ['time', 'total']
    ordering = ['-time']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        year = params.get('year')
        if year:
            qs = qs.filter(time__year=int(year))

        month = params.get('month')
        if month:
            qs = qs.filter(time__month=int(month))

        htype = params.get('htype')
        if htype:
            qs = qs.filter(htype=int(htype))

        return qs

    # ─── 统计接口 ───

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """目标总览（总步数/进度/里程碑/预测）"""
        data = HealthStatsService.get_summary()
        return Response(data)

    @action(detail=False, methods=['get'])
    def milestones(self, request):
        """里程碑列表（50个里程碑状态）"""
        data = HealthStatsService.get_milestones()
        return Response(data)

    @action(detail=False, methods=['get'])
    def daily_trend(self, request):
        """每日步数趋势"""
        days = request.query_params.get('days', 30)
        data = HealthStatsService.get_daily_trend(int(days))
        return Response(data)

    @action(detail=False, methods=['get'])
    def calendar(self, request):
        """日历热力图数据"""
        year = request.query_params.get('year')
        month = request.query_params.get('month')
        data = HealthStatsService.get_calendar(
            int(year) if year else None,
            int(month) if month else None,
        )
        return Response(data)

    @action(detail=False, methods=['get'])
    def milestone_timeline(self, request):
        """里程碑达成时间线"""
        data = HealthStatsService.get_milestone_timeline()
        return Response(data)

    @action(detail=False, methods=['get'])
    def type_stats(self, request):
        """运动类型占比"""
        data = HealthStatsService.get_type_stats()
        return Response(data)

    @action(detail=False, methods=['get'])
    def yearly_comparison(self, request):
        """年度步数对比"""
        data = HealthStatsService.get_yearly_comparison()
        return Response(data)


class WeightViewSet(viewsets.ModelViewSet):
    """体重管理视图集"""

    permission_classes = [AllowAny]

    def get_serializer_class(self):
        if self.action == 'list':
            return WeightRecordSerializer
        return WeightRecordSerializer

    def get_queryset(self):
        return WeightRecord.objects.filter(user_id=self.request.query_params.get('user_id', 1))

    def perform_create(self, serializer):
        instance = serializer.save(user_id=int(self.request.data.get('user_id', 1)))
        goal = WeightGoal.objects.filter(
            user_id=instance.user_id, is_active=True, status='in_progress'
        ).first()
        if goal:
            WeightService.check_weight_goal_status(goal)

    # ─── 统计 ───

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """统计概览"""
        data = WeightService.get_stats(user_id=int(request.query_params.get('user_id', 1)))
        return Response(data)

    @action(detail=False, methods=['get'])
    def trend(self, request):
        """体重趋势数据"""
        data = WeightService.get_trend(user_id=int(request.query_params.get('user_id', 1)))
        return Response(data)

    # ─── 目标 ───

    @action(detail=False, methods=['get', 'post'])
    def goal(self, request):
        """获取/创建活跃目标"""
        user_id = int(request.data.get('user_id', 1) if request.method == 'POST'
                      else request.query_params.get('user_id', 1))
        if request.method == 'GET':
            goal = WeightGoal.objects.filter(user_id=user_id, is_active=True).first()
            if not goal:
                return Response(None)
            WeightService.check_weight_goal_status(goal)
            serializer = WeightGoalSerializer(goal)
            return Response(serializer.data)

        # POST
        data = dict(request.data.items())
        data.pop('user_id', None)
        if data.get('start_date') and isinstance(data['start_date'], str):
            from datetime import datetime
            data['start_date'] = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
        goal = WeightService.create_goal(user_id=user_id, **data)
        serializer = WeightGoalSerializer(goal)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    # ─── 里程碑 ───

    @action(detail=False, methods=['get'])
    def milestones(self, request):
        """获取月度里程碑"""
        user_id = int(request.query_params.get('user_id', 1))
        goal = WeightGoal.objects.filter(user_id=user_id, is_active=True).first()
        if not goal:
            return Response([])
        qs = WeightMilestone.objects.filter(goal=goal).order_by('month_number')
        serializer = WeightMilestoneSerializer(qs, many=True)
        return Response(serializer.data)

    # ─── 目标调整记录 ───

    @action(detail=False, methods=['get'])
    def adjustments(self, request):
        """获取当前活跃目标的调整记录"""
        user_id = int(request.query_params.get('user_id', 1))
        goal = WeightGoal.objects.filter(user_id=user_id, is_active=True).first()
        if not goal:
            return Response([])
        qs = WeightGoalAdjustment.objects.filter(goal=goal).order_by('-adjusted_at')
        serializer = WeightGoalAdjustmentSerializer(qs, many=True)
        return Response(serializer.data)

    # ─── 身体信息 ───

    @action(detail=False, methods=['get', 'put'])
    def body_info(self, request):
        """获取/更新身体信息"""
        user_id = int(request.data.get('user_id', 1) if request.method == 'PUT'
                      else request.query_params.get('user_id', 1))
        if request.method == 'GET':
            info = UserBodyInfo.objects.filter(user_id=user_id).first()
            if not info:
                return Response(None)
            serializer = UserBodyInfoSerializer(info)
            return Response(serializer.data)

        # PUT
        data = dict(request.data.items())
        data.pop('id', None)
        info, created = UserBodyInfo.objects.update_or_create(
            user_id=user_id,
            defaults=data,
        )
        serializer = UserBodyInfoSerializer(info)
        return Response(serializer.data)


class MenstrualViewSet(viewsets.ModelViewSet):
    """好朋友跟踪视图集"""

    permission_classes = [AllowAny]
    serializer_class = MenstrualRecordSerializer

    def get_queryset(self):
        qs = MenstrualRecord.objects.filter(user_id=1)
        year = self.request.query_params.get('year')
        if year:
            qs = qs.filter(year=int(year))
        return qs

    def perform_create(self, serializer):
        serializer.save(user_id=1)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """统计：平均周期、平均偏移、下次预测"""
        records = MenstrualRecord.objects.filter(user_id=1).order_by('-start_date')
        total = records.count()
        if total == 0:
            return Response({
                'total_records': 0, 'avg_cycle': 0, 'avg_offset': 0,
                'predicted_next': None, 'min_cycle': 0, 'max_cycle': 0,
            })

        cycles = [r.cycle_days for r in records if r.cycle_days > 0]
        offsets = [r.offset for r in records]

        avg_cycle = round(sum(cycles) / len(cycles)) if cycles else 0
        avg_offset = round(sum(offsets) / len(offsets)) if offsets else 0
        min_cycle = min(cycles) if cycles else 0
        max_cycle = max(cycles) if cycles else 0

        latest = records.first()
        from datetime import timedelta
        predicted_next = (latest.start_date + timedelta(days=avg_cycle)).isoformat() if avg_cycle else None

        return Response({
            'total_records': total,
            'avg_cycle': avg_cycle,
            'avg_offset': avg_offset,
            'predicted_next': predicted_next,
            'min_cycle': min_cycle,
            'max_cycle': max_cycle,
        })

    @action(detail=False, methods=['get'])
    def trend(self, request):
        """周期跨度趋势（全部记录正序）"""
        records = MenstrualRecord.objects.filter(
            user_id=1, cycle_days__gt=0
        ).order_by('start_date')

        return Response([{
            'date': r.start_date.isoformat(),
            'cycle_days': r.cycle_days,
        } for r in records])
