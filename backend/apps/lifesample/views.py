from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import LifeSample, ObsidianConfig
from .serializers import (
    LifeSampleSerializer,
    ObsidianConfigSerializer,
    ScanResultSerializer,
)
from .services.obsidian_service import ObsidianService


class LifeSampleViewSet(viewsets.ModelViewSet):
    """人生样本 CRUD + 搜索/筛选 + 标签/统计"""

    queryset = LifeSample.objects.all()
    serializer_class = LifeSampleSerializer
    pagination_class = None  # 轻量索引，不启用全局分页

    def get_queryset(self):
        qs = super().get_queryset()

        search = self.request.query_params.get('search', '')
        if search:
            qs = qs.filter(name__icontains=search)

        sample_type = self.request.query_params.get('type', '')
        if sample_type:
            qs = qs.filter(sample_type=sample_type)

        status = self.request.query_params.get('status', '')
        if status:
            qs = qs.filter(status=status)

        relevance = self.request.query_params.get('relevance', '')
        if relevance:
            qs = qs.filter(relevance=relevance)

        tag = self.request.query_params.get('tag', '')
        if tag:
            qs = qs.filter(tags__contains=[tag])

        return qs

    @action(detail=False, methods=['get'], url_path='tags')
    def get_tags(self, _request):
        """获取所有已使用的标签"""
        all_tags = set()
        for sample in LifeSample.objects.all():
            all_tags.update(sample.tags)
        return Response(sorted(all_tags))

    @action(detail=False, methods=['get'], url_path='stats')
    def get_stats(self, _request):
        """获取统计信息（含状态/评级分布）"""
        total = LifeSample.objects.count()
        synced = LifeSample.objects.exclude(obsidian_path='').count()
        scanned = ObsidianService.scan_samples()

        return Response({
            'total': total,
            'synced': synced,
            'pending': total - synced,
            'obsidian_files': len(scanned),
            'status': {
                code: LifeSample.objects.filter(status=code).count()
                for code, _label in LifeSample.STATUS_CHOICES
            },
            'relevance': {
                code: LifeSample.objects.filter(relevance=code).count()
                for code, _label in LifeSample.RELEVANCE_CHOICES
            },
        })

    @action(detail=False, methods=['post'], url_path='sync-from-obsidian')
    def sync_from_obsidian(self, _request):
        """从 Obsidian 同步样本：扫描文件夹，自动创建/更新索引"""
        result = ObsidianService.sync_samples()
        if not result['success']:
            return Response(result, status=status.HTTP_404_NOT_FOUND)
        return Response(result)


class ObsidianConfigViewSet(viewsets.GenericViewSet):
    """Obsidian 集成配置 + 扫描 + 打开"""

    @action(detail=False, methods=['get', 'post'], url_path='config')
    def config(self, request):
        """获取或更新 Obsidian 集成配置"""
        config = ObsidianConfig.get_config()
        if request.method == 'GET':
            return Response(ObsidianConfigSerializer(config).data)
        serializer = ObsidianConfigSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='scan')
    def scan(self, _request):
        """扫描 Obsidian 样本文件夹"""
        results = ObsidianService.scan_samples()
        serializer = ScanResultSerializer(results, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path=r'open/(?P<path>.+)')
    def open_file(self, _request, path: str = None):
        """生成 Obsidian URI"""
        if not path:
            return Response({'error': '需要文件路径'}, status=status.HTTP_400_BAD_REQUEST)
        uri = ObsidianService.get_obsidian_uri(path)
        return Response({'uri': uri})
