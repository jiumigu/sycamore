from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from django.db.models import Avg, Count, Max, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce, ExtractMonth

from .models import ConflictEvent, Interaction, ReaderGroup, ReaderInteraction, ReaderMonthlySummary, Relationship
from .serializers import (
    ConflictEventSerializer, InteractionSerializer, ReaderGroupSerializer,
    ReaderInteractionSerializer, ReaderMonthlySummarySerializer,
    RelationshipListSerializer, RelationshipSerializer,
)
from .services.stats_service import StatsService


class RelationshipPagination(PageNumberPagination):
    """关系档案分页"""
    page_size = 12
    page_size_query_param = 'page_size'


class RelationshipViewSet(viewsets.ModelViewSet):
    """关系档案视图集"""

    queryset = Relationship.objects.all()
    permission_classes = [AllowAny]
    pagination_class = RelationshipPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'alias', 'notes', 'tags']
    ordering_fields = ['name', 'updated_at', 'created_at']
    ordering = ['-updated_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return RelationshipListSerializer
        return RelationshipSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        quality = params.get('quality')
        if quality:
            qs = qs.filter(current_quality=quality)

        status_val = params.get('status')
        if status_val:
            qs = qs.filter(current_status=status_val)

        tag = params.get('tag')
        if tag:
            qs = qs.filter(tags__icontains=tag)

        location = params.get('location')
        if location:
            qs = qs.filter(met_place__icontains=location)

        year = params.get('year')
        if year:
            qs = qs.filter(met_date__year=year)

        # 预计算统计值
        latest = Interaction.objects.filter(
            relationship=OuterRef('pk'),
        ).order_by('-happened_at').values('happened_at')[:1]

        qs = qs.annotate(
            interaction_count=Count('interactions'),
            total_energy=Sum('interactions__energy_score'),
            avg_energy=Avg('interactions__energy_score'),
            last_interaction=Subquery(latest),
        )

        type_param = params.get('type')
        if type_param:
            type_filters = {
                'nourishing': Q(avg_energy__gte=3),
                'neutral': Q(avg_energy__gte=0, avg_energy__lt=3),
                'draining': Q(avg_energy__gte=-3, avg_energy__lt=0),
                'toxic': Q(avg_energy__lt=-3),
            }
            f = type_filters.get(type_param)
            if f:
                qs = qs.filter(f)

        return qs

    def perform_create(self, serializer):
        serializer.save(user_id=1)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        data = StatsService.get_overview(user_id=1)
        return Response(data)

    @action(detail=False, methods=['get'])
    def met_places(self, request):
        """获取所有认识地点（去重）"""
        places = Relationship.objects.filter(
            user_id=1,
        ).exclude(
            Q(met_place__isnull=True) | Q(met_place=''),
        ).values_list('met_place', flat=True).distinct().order_by('met_place')
        return Response(list(places))


class InteractionViewSet(viewsets.ModelViewSet):
    """互动记录视图集"""

    queryset = Interaction.objects.all()
    permission_classes = [AllowAny]
    serializer_class = InteractionSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['happened_at']
    ordering = ['-happened_at']

    def get_queryset(self):
        qs = super().get_queryset()
        rel_id = self.request.query_params.get('relationship')
        if rel_id:
            qs = qs.filter(relationship_id=int(rel_id))
        return qs.select_related('relationship')

    def perform_create(self, serializer):
        serializer.save(user_id=1)


class StatsViewSet(viewsets.ViewSet):
    """统计视图集"""

    permission_classes = [AllowAny]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        return Response(StatsService.get_overview(user_id=1))

    @action(detail=False, methods=['get'])
    def quality_distribution(self, request):
        return Response(StatsService.get_quality_distribution(user_id=1))

    @action(detail=False, methods=['get'])
    def energy_trend(self, request):
        rel_id = request.query_params.get('relationship')
        return Response(StatsService.get_energy_trend(
            relationship_id=int(rel_id) if rel_id else None, user_id=1,
        ))

    @action(detail=False, methods=['get'])
    def interaction_frequency(self, request):
        return Response(StatsService.get_interaction_frequency(user_id=1))

    @action(detail=False, methods=['get'])
    def due_reminders(self, request):
        return Response(StatsService.get_due_reminders(user_id=1))

    @action(detail=False, methods=['get'])
    def location_stats(self, request):
        """按认识地点统计关系分布"""
        qs = Relationship.objects.filter(
            user_id=1,
        ).exclude(
            Q(met_place__isnull=True) | Q(met_place=''),
        ).values('met_place').annotate(
            total=Count('id'),
            nourishing=Count('id', filter=Q(current_quality='nourishing')),
            neutral=Count('id', filter=Q(current_quality='neutral')),
            draining=Count('id', filter=Q(current_quality='draining')),
            toxic=Count('id', filter=Q(current_quality='toxic')),
        ).order_by('-total')

        locations = []
        for loc in qs:
            total = loc['total']
            nourishing_rate = round(loc['nourishing'] / total * 100, 1) if total else 0
            locations.append({
                'name': loc['met_place'],
                'total': total,
                'nourishing': loc['nourishing'],
                'neutral': loc['neutral'],
                'draining': loc['draining'],
                'toxic': loc['toxic'],
                'nourishing_rate': nourishing_rate,
            })

        best = max(locations, key=lambda x: x['nourishing_rate']) if locations else None

        return Response({
            'locations': locations,
            'summary': {
                'total_locations': len(locations),
                'total_people': sum(l['total'] for l in locations),
                'best_location': best['name'] if best else None,
                'best_nourishing_rate': best['nourishing_rate'] if best else 0,
            },
        })


class ReaderGroupViewSet(viewsets.ModelViewSet):
    """读者群体视图集"""
    queryset = ReaderGroup.objects.all().order_by('-created_at')
    permission_classes = [AllowAny]
    serializer_class = ReaderGroupSerializer

    def perform_create(self, serializer):
        serializer.save(user_id=1)


class ReaderInteractionViewSet(viewsets.ModelViewSet):
    """读者互动视图集"""
    queryset = ReaderInteraction.objects.all()
    permission_classes = [AllowAny]
    serializer_class = ReaderInteractionSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        group_id = self.request.query_params.get('group_id')
        if group_id:
            qs = qs.filter(reader_group_id=group_id)
        return qs.order_by('-energy_score', '-created_at')

    @action(detail=False, methods=['get'])
    def resonance_points(self, request):
        """获取认知共振点（能量分 >= 3 的互动）"""
        qs = self.get_queryset().filter(energy_score__gte=3)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        serializer.save(user_id=1)
        self._update_group_energy(serializer.instance.reader_group)

    @action(detail=False, methods=['post'])
    def quick_record(self, request):
        """一键记录读者互动（零思考负担：只需填内容）"""
        content = request.data.get('content', '').strip()
        if not content:
            return Response({'error': '请填写互动内容'}, status=status.HTTP_400_BAD_REQUEST)

        default_group, _ = ReaderGroup.objects.get_or_create(
            name='读者',
            defaults={'user_id': 1, 'description': '默认读者群体'},
        )

        interaction = ReaderInteraction.objects.create(
            user_id=1,
            reader_group=default_group,
            reader_name=request.data.get('reader_name', '匿名读者'),
            interaction_type=request.data.get('interaction_type', 'comment'),
            content=content,
            article_title=request.data.get('article_title', ''),
            energy_score=int(request.data.get('energy_score', 1)),
        )

        self._update_group_energy(default_group)

        serializer = self.get_serializer(interaction)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def recent(self, request):
        """最近 5 条读者互动"""
        qs = self.get_queryset()[:5]
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @staticmethod
    def _update_group_energy(group):
        group.total_energy = ReaderInteraction.objects.filter(
            reader_group=group,
        ).aggregate(total=Sum('energy_score'))['total'] or 0
        group.save()


class ConflictEventViewSet(viewsets.ModelViewSet):
    """冲突事件视图集"""
    queryset = ConflictEvent.objects.all()
    permission_classes = [AllowAny]
    serializer_class = ConflictEventSerializer

    def get_queryset(self):
        qs = super().get_queryset().filter(user_id=1)
        contact_id = self.request.query_params.get('contact_id')
        event_type = self.request.query_params.get('type')

        if contact_id:
            qs = qs.filter(contact_id=contact_id)
        if event_type:
            qs = qs.filter(event_type=event_type)

        return qs.order_by('-event_date')

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """冲突统计"""
        qs = self.get_queryset()

        return Response({
            'total_count': qs.count(),
            'total_loss': qs.aggregate(total=Sum('loss_amount'))['total'] or 0,
            'avg_emotion': qs.aggregate(avg=Avg('emotion_level'))['avg'] or 0,
            'by_type': qs.values('event_type').annotate(count=Count('id')),
            'by_month': qs.annotate(month=ExtractMonth('event_date')).values('month').annotate(count=Count('id')),
        })

    def perform_create(self, serializer):
        serializer.save(user_id=1)


class ReaderMonthlySummaryViewSet(viewsets.ModelViewSet):
    """读者月末盘点视图集"""
    queryset = ReaderMonthlySummary.objects.all()
    permission_classes = [AllowAny]
    serializer_class = ReaderMonthlySummarySerializer

    def get_queryset(self):
        qs = super().get_queryset().filter(user_id=1)
        group_id = self.request.query_params.get('group_id')
        year = self.request.query_params.get('year')
        if group_id:
            qs = qs.filter(reader_group_id=group_id)
        if year:
            qs = qs.filter(year=int(year))
        return qs

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """年度统计"""
        year = request.query_params.get('year')
        qs = self.get_queryset()
        if year:
            qs = qs.filter(year=int(year))

        if not qs.exists():
            return Response({
                'year': year,
                'total_new_followers': 0,
                'total_new_unfollowers': 0,
                'net_growth': 0,
                'avg_monthly_interactions': 0,
                'best_month': None,
                'total_summaries': 0,
            })

        agg = qs.aggregate(
            total_new_followers=models.Sum('new_followers'),
            total_new_unfollowers=models.Sum('new_unfollowers'),
            total_interactions=models.Sum('total_interactions'),
            total_high_energy=models.Sum('high_energy_count'),
        )
        total_new_followers = agg['total_new_followers'] or 0
        total_new_unfollowers = agg['total_new_unfollowers'] or 0
        total_interactions = agg['total_interactions'] or 0
        count = qs.count()

        best = qs.order_by('-total_interactions').first()

        return Response({
            'year': year,
            'total_new_followers': total_new_followers,
            'total_new_unfollowers': total_new_unfollowers,
            'net_growth': total_new_followers - total_new_unfollowers,
            'avg_monthly_interactions': round(total_interactions / count, 1) if count else 0,
            'total_interactions': total_interactions,
            'best_month': {
                'month': best.month,
                'total_interactions': best.total_interactions,
                'top_article': best.top_article,
            } if best else None,
            'total_summaries': count,
        })

    def perform_create(self, serializer):
        serializer.save(user_id=1)
