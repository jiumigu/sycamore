import os
import re
import uuid

from datetime import date, datetime

from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from django.db.models import Sum

from .models import OneDayPage, TemporalTask, WeeklyTimeCache
from .serializers import (
    OneDayPageSerializer,
    TemporalTaskSerializer,
)
from .services import CSVImportService, OneDayPageService, TemporalStatsService


class TemporalTaskViewSet(viewsets.ReadOnlyModelViewSet):
    """任务时间记录视图集"""

    queryset = TemporalTask.objects.all()
    permission_classes = [AllowAny]
    serializer_class = TemporalTaskSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['task_name', 'task_description', 'notes']
    ordering_fields = ['start_time', 'duration_hours', 'year', 'mon']
    ordering = ['-start_time']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        year = params.get('year')
        if year:
            qs = qs.filter(year=int(year))

        month = params.get('month')
        if month:
            qs = qs.filter(mon=month)

        category = params.get('category')
        if category:
            qs = qs.filter(category_level1=category)

        task_name = params.get('task_name')
        if task_name:
            qs = qs.filter(task_name=task_name)

        date_from = params.get('date_from')
        if date_from:
            qs = qs.filter(start_time__date__gte=date_from)

        date_to = params.get('date_to')
        if date_to:
            qs = qs.filter(start_time__date__lte=date_to)

        return qs

    @action(detail=False, methods=['get'])
    def task_names(self, request):
        """获取所有不重复的任务名称"""
        names = TemporalTask.objects.values_list('task_name', flat=True).distinct().order_by('task_name')
        return Response(list(names))

    @action(detail=False, methods=['post'])
    def import_csv(self, request):
        """CSV 导入任务记录（使用 Django 原生 multipart 解析，绕过 DRF 限制）"""
        file = request._request.FILES.get('file')
        if not file:
            print(f'[CSV 导入] request.FILES: {dict(request._request.FILES)}')
            return Response({'error': '请上传文件'}, status=status.HTTP_400_BAD_REQUEST)

        print(f'[CSV 导入] 文件: name={file.name}, size={file.size}, content_type={file.content_type}')

        batch_id = f'import_{uuid.uuid4().hex[:12]}'

        service = CSVImportService()
        try:
            result = service.import_from_csv(file, batch_id)
        except Exception as e:
            print(f'[CSV 导入] 处理异常: {type(e).__name__}: {e}')
            import traceback
            traceback.print_exc()
            return Response({'error': f'导入处理异常：{str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if 'error' in result:
            return Response({'error': result['error']}, status=status.HTTP_400_BAD_REQUEST)

        print(f'[CSV 导入] 完成: 新增 {result["inserted"]}, 更新 {result["updated"]}')
        return Response(result, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """统计总览"""
        year = request.query_params.get('year')
        if year:
            year = int(year)
        data = TemporalStatsService.get_overview(year)
        return Response(data)

    @action(detail=False, methods=['get'])
    def trend(self, request):
        """趋势数据"""
        year = request.query_params.get('year')
        group = request.query_params.get('group', 'month')
        if year:
            year = int(year)
        data = TemporalStatsService.get_trend(year, group)
        return Response(data)

    @action(detail=False, methods=['get'])
    def balance(self, request):
        """平衡轮数据"""
        year = request.query_params.get('year')
        if year:
            year = int(year)
        data = TemporalStatsService.get_balance(year)
        return Response(data)

    @action(detail=False, methods=['get'])
    def ranking(self, request):
        """任务排行"""
        year = request.query_params.get('year')
        limit = request.query_params.get('limit', 10)
        if year:
            year = int(year)
        data = TemporalStatsService.get_ranking(year, int(limit))
        return Response(data)

    @action(detail=False, methods=['get'])
    def distribution(self, request):
        """时段分布"""
        year = request.query_params.get('year')
        if year:
            year = int(year)
        data = TemporalStatsService.get_distribution(year)
        return Response(data)

    @action(detail=False, methods=['get'])
    def calendar(self, request):
        """日历热力图"""
        year = request.query_params.get('year')
        if year:
            year = int(year)
        data = TemporalStatsService.get_calendar(year)
        return Response(data)


class WeeklyTimeTrackingView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        """获取多年周度时间追踪数据（从固化表读取）"""
        start_year = int(request.GET.get('start_year', date.today().year - 5))
        end_year = int(request.GET.get('end_year', date.today().year + 4))
        benchmark = float(request.GET.get('benchmark', 30))

        cache_data = WeeklyTimeCache.objects.filter(
            year__gte=start_year,
            year__lte=end_year,
        )

        result = {}
        for item in cache_data:
            if item.year not in result:
                result[item.year] = {}
            result[item.year][item.week] = {
                'hours': item.total_hours,
                'percentage': round(item.total_hours / benchmark * 100, 1) if benchmark > 0 else 0,
                'task_count': item.task_count,
            }

        return Response({
            'start_year': start_year,
            'end_year': end_year,
            'benchmark': benchmark,
            'data': result,
            'weeks_per_year': {year: len(result[year]) for year in result},
        })


class RefreshWeeklyCacheView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        """手动刷新周度缓存"""
        from apps.temporal.management.commands.refresh_weekly_cache import Command
        cmd = Command()
        cmd.handle()
        return Response({'success': True})


class OneDayPageViewSet(viewsets.ModelViewSet):
    """每日记录视图集"""

    queryset = OneDayPage.objects.all()
    permission_classes = [AllowAny]
    serializer_class = OneDayPageSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'remark']
    ordering_fields = ['begin_date', 'update_date', 'total', 'oneday', 'page', 'title']
    ordering = ['-begin_date']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        otype = params.get('otype')
        if otype:
            qs = qs.filter(otype=otype)

        years = params.get('years')
        if years:
            qs = qs.filter(years=years)

        year_from = params.get('year_from')
        if year_from:
            qs = qs.filter(years__gte=year_from)

        year_to = params.get('year_to')
        if year_to:
            qs = qs.filter(years__lte=year_to)

        date_from = params.get('date_from')
        if date_from:
            qs = qs.filter(begin_date__gte=date_from)

        date_to = params.get('date_to')
        if date_to:
            qs = qs.filter(begin_date__lte=date_to)

        total_min = params.get('total_min')
        if total_min:
            try:
                qs = qs.filter(total__gte=int(total_min))
            except ValueError:
                pass

        total_max = params.get('total_max')
        if total_max:
            try:
                qs = qs.filter(total__lte=int(total_max))
            except ValueError:
                pass

        return qs

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """获取统计信息"""
        data = OneDayPageService.get_stats()
        return Response(data)

    @action(detail=False, methods=['delete'])
    def bulk_delete(self, request):
        """批量删除"""
        oid_list = request.data.get('oids', [])
        if not oid_list:
            return Response({'error': '请提供要删除的ID列表'}, status=status.HTTP_400_BAD_REQUEST)

        deleted_count, _ = OneDayPage.objects.filter(oid__in=oid_list).delete()
        return Response({'message': f'成功删除 {deleted_count} 条记录', 'deleted_count': deleted_count})

    @action(detail=False, methods=['get'])
    def yearly_heatmap(self, request):
        """获取指定年份的日记热力图数据"""
        year = request.query_params.get('year', '')
        try:
            year = int(year)
        except (ValueError, TypeError):
            year = timezone.now().year

        logs = OneDayPage.objects.filter(
            begin_date__year=year,
        ).values('begin_date', 'total', 'title')

        return Response({
            'year': year,
            'data': [
                {
                    'date': log['begin_date'].isoformat(),
                    'count': log['total'] or 0,
                    'title': log['title'],
                }
                for log in logs
            ],
        })

    @action(detail=False, methods=['get'])
    def week_count(self, request):
        """获取本周日记篇数"""
        from datetime import timedelta

        today = date.today()
        week_start = today - timedelta(days=today.weekday())

        count = OneDayPage.objects.filter(
            begin_date__gte=week_start,
            begin_date__lte=today,
        ).count()

        return Response({'count': count})


class OpenLogseqView(APIView):
    """打开 Logseq 日记文件，返回 Markdown 内容"""

    permission_classes = [AllowAny]

    def get(self, request):
        filepath = request.GET.get('path', '')

        if not filepath or not os.path.exists(filepath):
            return Response({'error': '文件不存在'}, status=404)

        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        content = re.sub(r'^---\n.*?\n---\n', '', content, flags=re.DOTALL)
        content = re.sub(r'collapsed::\s*true', '', content)

        return Response({
            'filename': os.path.basename(filepath),
            'content': content,
        })
