import json
import os
import time
import uuid

from django.db import models
from django.conf import settings
from django.utils import timezone

from rest_framework import status, views, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import CareerEnergyAudit, CityCoordinate, DecisionLog, EnvironmentAudit, FreeSpendingCalculator, HealthSelfCheck, Quote, ReviewRecord, ToolkitDefinition, ToolkitExecution, TravelRoutePreset
from .registry import ToolRegistry
from .serializers import (
    CareerEnergyAuditSerializer,
    CityCoordinateSerializer,
    DecisionLogSerializer,
    EnvironmentAuditSerializer,
    ExecutionSerializer,
    ExecuteToolSerializer,
    FreeSpendingCalculatorSerializer,
    HealthSelfCheckSerializer,
    QuoteSerializer,
    ReviewRecordSerializer,
    ToolInfoSerializer,
    TravelRoutePresetSerializer,
)
from .services import calculate_health_score, collect_health_alerts, update_career_audit_decision


class CityCoordinateViewSet(viewsets.ReadOnlyModelViewSet):
    """城市坐标查询"""

    permission_classes = [AllowAny]
    queryset = CityCoordinate.objects.all()
    serializer_class = CityCoordinateSerializer
    pagination_class = None

    @action(detail=False, methods=['get'])
    def search(self, request):
        q = request.query_params.get('q', '').strip()
        if not q:
            return Response([])
        qs = CityCoordinate.objects.filter(name__icontains=q)[:20]
        return Response(CityCoordinateSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'])
    def provinces(self, request):
        """获取所有省份"""
        provinces = CityCoordinate.objects.filter(province__gt='').values_list('province', flat=True).distinct().order_by('province')
        return Response(list(provinces))

    @action(detail=False, methods=['get'])
    def cities(self, request):
        """获取指定省份下的地级市"""
        province = request.query_params.get('province', '')
        cities = CityCoordinate.objects.filter(province=province, city_type='地级市').values_list('name', flat=True).order_by('name')
        return Response(list(cities))

    @action(detail=False, methods=['get'])
    def districts(self, request):
        """获取指定地级市下的区县"""
        city = request.query_params.get('city', '')
        districts = CityCoordinate.objects.filter(
            full_name__icontains=city,
        ).exclude(city_type='地级市').values_list('name', flat=True).order_by('name')
        return Response(list(districts))


class ToolListView(views.APIView):
    """工具列表"""

    permission_classes = [AllowAny]

    def get(self, request):
        category = request.query_params.get('category')
        tools = ToolRegistry.get_all_tools(category)

        definitions = []
        for t in tools:
            try:
                obj = ToolkitDefinition.objects.filter(
                    tool_key=t.tool_key, is_enabled=True,
                ).first()
                if obj:
                    definitions.append(obj)
            except Exception:
                pass

        if not definitions:
            serializer = ToolInfoSerializer(
                [{
                    **t.get_definition_data(),
                    'tool_key': t.tool_key,
                    'input_schema': t.get_input_schema(),
                } for t in tools],
                many=True,
            )
            return Response({
                'tools': serializer.data,
                'categories': ToolRegistry.get_categories(),
            })
        return Response({
            'tools': ToolInfoSerializer(definitions, many=True).data,
            'categories': ToolRegistry.get_categories(),
        })


class ToolDetailView(views.APIView):
    """工具详情"""

    permission_classes = [AllowAny]

    def get(self, request, tool_key):
        tool = ToolRegistry.get_tool(tool_key)
        if not tool:
            return Response({'error': '工具不存在'}, status=status.HTTP_404_NOT_FOUND)
        return Response(ToolInfoSerializer({
            **tool.get_definition_data(),
            'tool_key': tool_key,
            'input_schema': tool.get_input_schema(),
        }).data)


class ExecuteToolView(views.APIView):
    """执行工具（JSON 参数）"""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ExecuteToolSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        tool_key = serializer.validated_data['tool_key']
        params = serializer.validated_data['params']

        tool = ToolRegistry.get_tool(tool_key)
        if not tool:
            return Response({'error': '工具不存在'}, status=status.HTTP_404_NOT_FOUND)

        definition = ToolkitDefinition.objects.filter(
            tool_key=tool_key, is_enabled=True,
        ).first()
        if not definition:
            return Response({'error': '工具未注册'}, status=status.HTTP_400_BAD_REQUEST)

        execution = ToolkitExecution.objects.create(
            tool=definition,
            input_params=params,
            status='running',
            user_id=1,
        )

        try:
            start = time.time()
            result = tool.execute(params, progress_callback=execution.update_progress)
            elapsed = int((time.time() - start) * 1000)

            execution.status = 'success'
            execution.progress = 100
            execution.output_result = json.dumps(result, ensure_ascii=False)
            if result.get('output_file'):
                execution.output_file = result['output_file']
            execution.execution_time_ms = elapsed
            execution.completed_at = timezone.now()
            execution.save()

            return Response({
                'execution_id': execution.id,
                'status': 'success',
                'result': result,
            })

        except Exception as e:
            execution.status = 'failed'
            execution.error_message = str(e)
            execution.completed_at = timezone.now()
            execution.save()
            return Response({
                'execution_id': execution.id,
                'status': 'failed',
                'error': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FileToolUploadView(views.APIView):
    """文件上传工具执行——接收文件 + 工具参数，用于文本转换类工具"""

    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [AllowAny]

    def post(self, request):
        tool_key = request.data.get('tool_key')
        mode = request.data.get('mode', 't2s')
        uploaded_file = request.FILES.get('file')

        if not tool_key:
            return Response({'error': '缺少 tool_key'}, status=status.HTTP_400_BAD_REQUEST)
        if not uploaded_file:
            return Response({'error': '请上传文件'}, status=status.HTTP_400_BAD_REQUEST)

        tool = ToolRegistry.get_tool(tool_key)
        if not tool:
            return Response({'error': '工具不存在'}, status=status.HTTP_404_NOT_FOUND)

        ext = os.path.splitext(uploaded_file.name)[1].lower()
        if ext != '.txt':
            return Response({'error': '仅支持 .txt 文件'}, status=status.HTTP_400_BAD_REQUEST)

        temp_dir = os.path.join(settings.MEDIA_ROOT, 'toolkit_uploads')
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, f'{uuid.uuid4().hex}{ext}')
        with open(temp_path, 'wb') as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)

        definition = ToolkitDefinition.objects.filter(
            tool_key=tool_key, is_enabled=True,
        ).first()

        execution = ToolkitExecution.objects.create(
            tool=definition,
            input_params={'original_name': uploaded_file.name, 'mode': mode},
            status='running',
            user_id=1,
        ) if definition else None

        try:
            start = time.time()
            result = tool.execute(
                {'file': temp_path, 'mode': mode},
                progress_callback=execution.update_progress if execution else None,
            )
            elapsed = int((time.time() - start) * 1000)

            if execution:
                execution.status = 'success'
                execution.progress = 100
                execution.output_result = json.dumps(result, ensure_ascii=False)
                if result.get('output_file'):
                    execution.output_file = result['output_file']
                execution.execution_time_ms = elapsed
                execution.completed_at = timezone.now()
                execution.save()

            try:
                os.remove(temp_path)
            except OSError:
                pass

            return Response({
                'status': 'success',
                'result': result,
            })

        except Exception as e:
            if execution:
                execution.status = 'failed'
                execution.error_message = str(e)
                execution.completed_at = timezone.now()
                execution.save()
            try:
                os.remove(temp_path)
            except OSError:
                pass
            return Response({
                'status': 'failed',
                'error': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TaskStatusView(views.APIView):
    """任务状态查询"""

    permission_classes = [AllowAny]

    def get(self, request, execution_id):
        try:
            execution = ToolkitExecution.objects.get(id=execution_id)
        except ToolkitExecution.DoesNotExist:
            return Response({'error': '任务不存在'}, status=status.HTTP_404_NOT_FOUND)

        result = None
        if execution.output_result and execution.status == 'success':
            try:
                result = json.loads(execution.output_result)
            except (json.JSONDecodeError, TypeError):
                result = execution.output_result

        return Response({
            'id': execution.id,
            'tool_id': execution.tool_id,
            'status': execution.status,
            'progress': execution.progress,
            'error_message': execution.error_message,
            'execution_time_ms': execution.execution_time_ms,
            'result': result,
            'output_file': execution.output_file if execution.status == 'success' else None,
            'created_at': execution.created_at,
            'completed_at': execution.completed_at,
        })


class HistoryListView(views.APIView):
    """执行历史"""

    permission_classes = [AllowAny]

    def get(self, request):
        tool_key = request.query_params.get('tool_key')
        status_filter = request.query_params.get('status')

        qs = ToolkitExecution.objects.select_related('tool').filter(user_id=1)
        if tool_key:
            qs = qs.filter(tool__tool_key=tool_key)
        if status_filter:
            qs = qs.filter(status=status_filter)

        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        total = qs.count()
        qs = qs[(page - 1) * page_size:page * page_size]

        return Response({
            'results': ExecutionSerializer(qs, many=True).data,
            'total': total,
            'page': page,
            'page_size': page_size,
        })


class RegisterToolsView(views.APIView):
    """注册工具到数据库"""

    permission_classes = [AllowAny]

    def post(self, request):
        tools = ToolRegistry.get_all_tools()
        count = 0
        for t in tools:
            _, created = ToolkitDefinition.objects.update_or_create(
                tool_key=t.tool_key,
                defaults={
                    'name': t.name,
                    'description': t.description or '',
                    'icon': t.icon,
                    'category': t.category,
                    'input_schema': t.get_input_schema(),
                    'output_type': getattr(t, 'output_type', 'file'),
                    'is_async': t.is_async,
                    'timeout_seconds': getattr(t, 'timeout_seconds', 300),
                    'is_enabled': True,
                    'user_id': 1,
                },
            )
            if created:
                count += 1
        return Response({
            'message': f'注册完成，新增 {count} 个工具',
            'total': len(tools),
        })


class TravelRoutePresetViewSet(viewsets.ModelViewSet):
    """旅行路线预设 CRUD"""

    permission_classes = [AllowAny]
    queryset = TravelRoutePreset.objects.all()
    serializer_class = TravelRoutePresetSerializer


def _calculate_verdict(total_score: int) -> tuple:
    """根据总分返回 (判定文字, 建议)"""
    if total_score >= 24:
        return '增值环境', '这里让你变得更好，值得深耕。'
    elif total_score >= 18:
        return '可维持', '不差，但也别待太久。找找哪些特征拖后腿。'
    elif total_score >= 12:
        return '消耗环境', '待一天就少一天能量。开始准备离开。'
    return '立即离开', '这里在透支你。身体已经告诉你了。'


class EnvironmentAuditViewSet(viewsets.ModelViewSet):
    """环境校准 CRUD"""

    permission_classes = [AllowAny]
    queryset = EnvironmentAudit.objects.all()
    serializer_class = EnvironmentAuditSerializer

    def perform_create(self, serializer):
        total = sum([
            serializer.validated_data.get('allow_learning', 0),
            serializer.validated_data.get('system_valued', 0),
            serializer.validated_data.get('signal_over_noise', 0),
            serializer.validated_data.get('body_heard', 0),
            serializer.validated_data.get('people_share', 0),
            serializer.validated_data.get('output_echoes', 0),
        ])
        verdict, _ = _calculate_verdict(total)
        serializer.save(user_id=1, total_score=total, verdict=verdict)

    def perform_update(self, serializer):
        total = sum([
            serializer.validated_data.get('allow_learning', 0),
            serializer.validated_data.get('system_valued', 0),
            serializer.validated_data.get('signal_over_noise', 0),
            serializer.validated_data.get('body_heard', 0),
            serializer.validated_data.get('people_share', 0),
            serializer.validated_data.get('output_echoes', 0),
        ])
        verdict, _ = _calculate_verdict(total)
        serializer.save(total_score=total, verdict=verdict)


class CareerEnergyAuditViewSet(viewsets.ModelViewSet):
    """职业能量审计 CRUD"""

    permission_classes = [AllowAny]
    queryset = CareerEnergyAudit.objects.all()
    serializer_class = CareerEnergyAuditSerializer

    def perform_create(self, serializer):
        instance = serializer.save(user_id=1)
        update_career_audit_decision(instance)
        instance.save(update_fields=[
            'total_score', 'decision', 'advice',
            'work_score', 'env_score', 'growth_score', 'body_score',
        ])

    def perform_update(self, serializer):
        instance = serializer.save()
        update_career_audit_decision(instance)
        instance.save(update_fields=[
            'total_score', 'decision', 'advice',
            'work_score', 'env_score', 'growth_score', 'body_score',
        ])


class QuoteViewSet(viewsets.ModelViewSet):
    """摘录馆"""
    queryset = Quote.objects.all()
    permission_classes = [AllowAny]
    serializer_class = QuoteSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        tags = self.request.query_params.get('tags', '').strip()
        if tags:
            qs = qs.filter(tags__contains=tags)
        lang = self.request.query_params.get('language', '').strip()
        if lang:
            qs = qs.filter(language=lang)
        para = self.request.query_params.get('is_paragraph')
        if para is not None and para != '':
            qs = qs.filter(is_paragraph=para.lower() in ('true', '1'))
        return qs

    @action(detail=False, methods=['get'])
    def stats(self, request):
        qs = self.get_queryset()
        total = qs.count()
        paragraphs = qs.filter(is_paragraph=True).count()
        total_reviews = qs.aggregate(total=models.Sum('review_count'))['total'] or 0
        return Response({
            'total': total,
            'paragraphs': paragraphs,
            'shorts': total - paragraphs,
            'total_reviews': total_reviews,
        })

    @action(detail=False, methods=['get'])
    def random(self, request):
        """随机返回一条摘录（排除默认日记标题）"""
        quote = Quote.objects.exclude(
            content__icontains='幸福未被发现，就叫做普通的一天'
        ).exclude(
            short_title__icontains='幸福未被发现，就叫做普通的一天'
        ).order_by('?').first()
        if not quote:
            return Response(None, status=204)
        # 每次随机查看增加回顾次数
        Quote.objects.filter(id=quote.id).update(review_count=models.F('review_count') + 1)
        quote.refresh_from_db()
        return Response(QuoteSerializer(quote).data)


class DecisionLogViewSet(viewsets.ModelViewSet):
    """决策日志 CRUD"""

    permission_classes = [AllowAny]
    queryset = DecisionLog.objects.all()
    serializer_class = DecisionLogSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        year = self.request.query_params.get('year')
        category = self.request.query_params.get('category')
        if year:
            qs = qs.filter(decision_date__year=int(year))
        if category:
            qs = qs.filter(category=category)
        return qs


class HealthSelfCheckViewSet(viewsets.ModelViewSet):
    """身体健康自查 CRUD"""

    permission_classes = [AllowAny]
    queryset = HealthSelfCheck.objects.all()
    serializer_class = HealthSelfCheckSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        year = self.request.query_params.get('year')
        if year:
            qs = qs.filter(check_date__year=int(year))
        return qs

    def perform_create(self, serializer):
        instance = serializer.save(user_id=1)
        self._recalc(instance)

    def perform_update(self, serializer):
        instance = serializer.save()
        self._recalc(instance)

    def _recalc(self, instance):
        data = {f.name: getattr(instance, f.name) for f in HealthSelfCheck._meta.fields}
        instance.health_score = calculate_health_score(data)
        instance.alert_items = '；'.join(collect_health_alerts(data))

        prev = (HealthSelfCheck.objects
                .filter(check_date__lt=instance.check_date, user_id=1)
                .order_by('-check_date').first())
        if prev:
            instance.last_score = prev.health_score
            instance.score_change = instance.health_score - prev.health_score

        instance.save(update_fields=['health_score', 'last_score', 'score_change', 'alert_items'])


class FreeSpendingCalculatorViewSet(viewsets.ModelViewSet):
    """自由支配额度计算 CRUD"""

    permission_classes = [AllowAny]
    queryset = FreeSpendingCalculator.objects.all()
    serializer_class = FreeSpendingCalculatorSerializer

    def get_queryset(self):
        return FreeSpendingCalculator.objects.filter(user_id=1)

    def perform_create(self, serializer):
        serializer.save(user_id=1)


class ReviewRecordViewSet(viewsets.ModelViewSet):
    """复盘记录 CRUD"""

    permission_classes = [AllowAny]
    serializer_class = ReviewRecordSerializer

    def get_queryset(self):
        qs = ReviewRecord.objects.filter(user_id=1)
        rtype = self.request.query_params.get('review_type', '').strip()
        if rtype:
            qs = qs.filter(review_type=rtype)
        year = self.request.query_params.get('year')
        if year:
            qs = qs.filter(review_date__year=int(year))
        return qs

    def perform_create(self, serializer):
        serializer.save(user_id=1)
