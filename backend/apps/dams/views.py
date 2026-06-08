from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from django.db.models import Count, Max, Q

from .constants import ATTENTION_ZONE_COLORS, ATTENTION_ZONE_LABELS
from .models import DamsAccessLog, DamsFileResource
from .serializers import (
    DamsAccessLogSerializer,
    DamsFileResourceListSerializer,
    DamsFileResourceSerializer,
)


class DamsFileResourceViewSet(viewsets.ModelViewSet):
    """文件资源视图集"""

    queryset = DamsFileResource.objects.all()
    permission_classes = [AllowAny]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'path', 'parent_folder']
    ordering_fields = ['name', 'file_size_mb', 'access_count', 'updated_at', 'created_at']
    ordering = ['-updated_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return DamsFileResourceListSerializer
        return DamsFileResourceSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        category = params.get('category')
        if category:
            qs = qs.filter(file_category=category)

        dup = params.get('is_duplicate')
        if dup is not None:
            qs = qs.filter(is_duplicate=dup.lower() == 'true')

        organized = params.get('is_organized')
        if organized is not None:
            qs = qs.filter(is_organized=organized.lower() == 'true')

        search = params.get('search')
        if search:
            qs = qs.filter(
                Q(name__icontains=search) | Q(path__icontains=search)
            )

        return qs

    def perform_create(self, serializer):
        serializer.save(user_id=1)

    @action(detail=False, methods=['get'])
    def attention_map(self, request):
        """按注意力分区返回文件统计"""
        threshold_freq = int(request.query_params.get('freq_threshold', 10))

        files = self.get_queryset()
        total = files.count()
        zones = {'red': [], 'blue': [], 'green': [], 'gray': []}

        for f in files:
            if f.access_count is None or f.access_count == 0:
                zones['gray'].append(f.id)
            elif f.access_count >= threshold_freq and not f.is_organized:
                zones['red'].append(f.id)
            elif f.access_count < threshold_freq and f.is_organized:
                zones['blue'].append(f.id)
            else:
                zones['green'].append(f.id)

        result = {
            config_key: {
                'label': ATTENTION_ZONE_LABELS[zone_key],
                'color': ATTENTION_ZONE_COLORS[zone_key],
                'count': len(ids),
                'file_ids': ids,
            }
            for zone_key, ids in zones.items()
            for config_key in [zone_key]
        }
        result['total'] = total

        return Response(result)

    @action(detail=True, methods=['post'])
    def mark_organized(self, request, pk=None):
        """标记文件为已整理"""
        obj = self.get_object()
        obj.is_organized = True
        obj.save(update_fields=['is_organized'])
        return Response({'status': 'ok'})


class DamsAccessLogViewSet(viewsets.ModelViewSet):
    """访问日志视图集"""

    queryset = DamsAccessLog.objects.all()
    permission_classes = [AllowAny]
    serializer_class = DamsAccessLogSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ['accessed_at']
    ordering = ['-accessed_at']

    def get_queryset(self):
        qs = super().get_queryset()
        file_id = self.request.query_params.get('file')
        if file_id:
            qs = qs.filter(file_id=int(file_id))
        return qs.select_related('file')

    def perform_create(self, serializer):
        serializer.save(user_id=1)
