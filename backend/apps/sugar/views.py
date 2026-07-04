from datetime import datetime

from django.db.models import Avg, Count, Sum
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .energy_service import EnergyService
from .models import EnergyLog, EnergyTemplate, SugarRecord, SugarTemplate
from .serializers import (
    EnergyCompleteSerializer,
    EnergyLogSerializer,
    EnergyTemplateSerializer,
    SugarCategoryStatsSerializer,
    SugarRecordSerializer,
    SugarTemplateSerializer,
)
from .services import SugarRecordService


class SugarPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'


class SugarRecordViewSet(viewsets.ModelViewSet):
    """小确幸记录视图集"""

    queryset = SugarRecord.objects.all()
    serializer_class = SugarRecordSerializer
    permission_classes = [AllowAny]
    pagination_class = SugarPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'notes', 'tags']
    ordering_fields = ['time', 'level_of_happiness', 'created_at', 'reward_amount']
    ordering = ['-time', '-s_id']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        year = params.get('year')
        if year:
            qs = qs.filter(years=int(year))

        month = params.get('month')
        if month:
            qs = qs.filter(month=int(month))

        category = params.get('category')
        if category:
            qs = qs.filter(category=category)

        min_happiness = params.get('min_happiness')
        if min_happiness:
            qs = qs.filter(level_of_happiness__gte=float(min_happiness))

        return qs

    def perform_create(self, serializer):
        level = serializer.validated_data['level_of_happiness']
        time = serializer.validated_data['time']
        record = serializer.save(
            reward_amount=level,
            reward_synced=True,
            years=time.year,
            month=time.month,
        )
        # 同步奖励池
        from apps.reward.services import RewardPoolService
        RewardPoolService().add_reward(
            source_id=record.s_id,
            source_type='sugar',
            amount=level,
            transaction_type='sugar_create',
            description=f'新增小确幸：{record.title}，获得{level}元奖励',
        )

    def perform_update(self, serializer):
        instance = self.get_object()
        old_amount = instance.reward_amount or 0
        new_amount = serializer.validated_data.get('level_of_happiness', old_amount)

        from django.db import transaction
        with transaction.atomic():
            serializer.save(reward_amount=new_amount)

            if old_amount != new_amount:
                from apps.reward.models import RewardPool, RewardTransaction

                pool = RewardPool.objects.select_for_update().first()
                if pool:
                    delta = new_amount - old_amount
                    pool.balance += delta
                    if delta > 0:
                        pool.total_earned += delta
                    pool.save()

                    RewardTransaction.objects.create(
                        source_id=instance.s_id,
                        source_type='sugar',
                        amount=delta,
                        transaction_type='sugar_update',
                        balance_before=pool.balance - delta,
                        balance_after=pool.balance,
                        description=f'小确幸快乐程度变化：{instance.title}，奖励 {old_amount}→{new_amount}',
                    )

        if 'time' in serializer.validated_data:
            new_time = serializer.validated_data['time']
            if new_time:
                instance.years = new_time.year
                instance.month = new_time.month
                instance.save(update_fields=['years', 'month'])

    def perform_destroy(self, instance):
        service = SugarRecordService()
        service.delete(s_id=instance.s_id)

    @action(detail=False, methods=['get'])
    def joy_type_stats(self, request):
        """获取快乐类型分布统计"""
        qs = SugarRecord.objects.exclude(joy_type='')

        params = self.request.query_params
        year = params.get('year')
        if year:
            qs = qs.filter(years=int(year))
        month = params.get('month')
        if month:
            qs = qs.filter(month=int(month))

        stats = (
            qs.values('joy_type')
            .annotate(
                count=Count('s_id'),
                total_happiness=Sum('level_of_happiness'),
                avg_happiness=Avg('level_of_happiness'),
            )
            .order_by('-count')
        )

        total = sum(s['count'] for s in stats)
        result = []
        for s in stats:
            result.append({
                'joy_type': s['joy_type'],
                'count': s['count'],
                'percentage': round(s['count'] / total * 100, 1) if total else 0,
                'total_happiness': float(s['total_happiness'] or 0),
                'avg_happiness': round(float(s['avg_happiness'] or 0), 1),
            })

        return Response({'joy_types': result, 'total': total})

    @action(detail=False, methods=['get'])
    def categories(self, request):
        """获取分类统计及整体汇总"""
        qs = SugarRecord.objects

        params = self.request.query_params
        year = params.get('year')
        if year:
            qs = qs.filter(years=int(year))
        month = params.get('month')
        if month:
            qs = qs.filter(month=int(month))
        category = params.get('category')
        if category:
            qs = qs.filter(category=category)

        stats = (
            qs.values('category')
            .annotate(
                count=Count('s_id'),
                total_reward=Sum('reward_amount'),
            )
            .order_by('-count')
        )
        for s in stats:
            s['category'] = s['category'] or 'other'
            s['total_reward'] = float(s['total_reward'] or 0)

        overall = qs.aggregate(
            total_count=Count('s_id'),
            total_reward=Sum('reward_amount'),
            avg_happiness=Avg('level_of_happiness'),
        )

        serializer = SugarCategoryStatsSerializer(stats, many=True)
        return Response({
            'categories': serializer.data,
            'summary': {
                'total_count': overall['total_count'] or 0,
                'total_reward': float(overall['total_reward'] or 0),
                'avg_happiness': round(float(overall['avg_happiness'] or 0), 1),
            },
        })


class SugarTemplateViewSet(viewsets.ModelViewSet):
    """小确幸模板 CRUD"""

    queryset = SugarTemplate.objects.filter(is_active=True)
    serializer_class = SugarTemplateSerializer
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
        serializer.save(user_id=1)


class EnergyViewSet(viewsets.ViewSet):
    """能量清单视图集"""

    permission_classes = [AllowAny]

    @action(detail=False, methods=['get', 'post'])
    def templates(self, request):
        """获取/创建能量清单模板"""
        if request.method == 'GET':
            service = EnergyService()
            qs = service.get_templates(user_id=1)
            serializer = EnergyTemplateSerializer(qs, many=True)
            return Response(serializer.data)

        ser = EnergyTemplateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        service = EnergyService()
        template = service.create_custom_template(
            content=ser.validated_data['content'],
            default_energy=ser.validated_data.get('default_energy', 1),
            category=ser.validated_data.get('category', 'daily'),
            icon=ser.validated_data.get('icon', '✨'),
            estimated_seconds=ser.validated_data.get('estimated_seconds', 60),
            user_id=1,
        )
        return Response(EnergyTemplateSerializer(template).data, status=201)

    @action(detail=False, methods=['post'])
    def complete(self, request):
        """完成一个能量任务"""
        ser = EnergyCompleteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        service = EnergyService()
        result = service.complete_task(
            template_id=ser.validated_data.get('template_id'),
            content=ser.validated_data['content'],
            energy_gained=ser.validated_data.get('energy_gained', 1),
            is_custom=ser.validated_data.get('is_custom', False),
            completed_at=ser.validated_data.get('completed_at') or datetime.now(),
            user_id=1,
        )
        return Response(result, status=201)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """获取能量统计"""
        service = EnergyService()
        return Response(service.get_stats(user_id=1))

    @action(detail=False, methods=['get'])
    def history(self, request):
        """获取能量历史记录"""
        qs = EnergyLog.objects.filter(user_id=1).select_related('template')
        day = request.query_params.get('date')
        if day:
            qs = qs.filter(completed_at__date=day)
        page = int(request.query_params.get('page', 1))
        size = int(request.query_params.get('size', 20))
        start = (page - 1) * size
        total = qs.count()
        items = qs.order_by('-completed_at')[start:start + size]
        serializer = EnergyLogSerializer(items, many=True)
        return Response({'results': serializer.data, 'count': total, 'page': page})

    @action(detail=False, methods=['get'])
    def daily(self, request):
        """获取每日已完成列表"""
        service = EnergyService()
        day_str = request.query_params.get('date')
        if day_str:
            from datetime import date as date_cls
            stat_date = date_cls.fromisoformat(day_str)
        else:
            stat_date = datetime.now().date()
        logs = service.get_daily_completed(stat_date=stat_date, user_id=1)
        serializer = EnergyLogSerializer(logs, many=True)
        return Response({'date': stat_date.isoformat(), 'items': serializer.data})

    @action(detail=False, methods=['get'])
    def trend(self, request):
        """获取能量趋势"""
        days = int(request.query_params.get('days', 30))
        service = EnergyService()
        return Response(service.get_energy_trend(days=days, user_id=1))
