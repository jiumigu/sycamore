import json
import os
import time
import uuid

from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db import models
from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone

from rest_framework import status, views, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import AskAnswer, AskScene, AskTopic, CareerEnergyAudit, CityCoordinate, DecisionRecord, DecisionTracker, ElectricityRecord, FixedExpense, FreeSpendingCalculator, HealthSelfCheck, HourlyWageRecord, Quote, ToolkitDefinition, ToolkitExecution, TravelRoutePreset

from apps.sugar.models import SugarRecord
from apps.treasure.models import GoodThing
from .registry import ToolRegistry
from .serializers import (
    AskAnswerSerializer,
    AskSceneSerializer,
    AskTopicSerializer,
    CareerEnergyAuditSerializer,
    CityCoordinateSerializer,
    DecisionRecordSerializer,
    DecisionTrackerSerializer,
    ElectricityRecordSerializer,
    ExecutionSerializer,
    ExecuteToolSerializer,
    FixedExpenseSerializer,
    FreeSpendingCalculatorSerializer,
    HealthSelfCheckSerializer,
    HourlyWageRecordSerializer,
    QuoteSerializer,
    ToolInfoSerializer,
    TravelRoutePresetSerializer,
)
from .services import ElectricityService, calculate_health_score, collect_health_alerts, update_career_audit_decision

# 周期 → 天数换算：daily=1天、monthly=30天、yearly=365天
PERIOD_DAYS = {'daily': 1, 'monthly': 30, 'yearly': 365}


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


from django.http import FileResponse, Http404


class FileDownloadView(views.APIView):
    """工具产物文件下载——仅允许 MEDIA_ROOT 内文件（防路径穿越）"""

    permission_classes = [AllowAny]

    def get(self, request, filepath):
        media_root = os.path.abspath(settings.MEDIA_ROOT)
        target = os.path.abspath(os.path.join(media_root, filepath))
        if not target.startswith(media_root + os.sep) or not os.path.isfile(target):
            raise Http404
        return FileResponse(open(target, 'rb'), as_attachment=True,
                            filename=os.path.basename(target))


_TOOL_ALLOWED_EXTS = {
    'trad2simp': {'.txt'},
    'gif-compressor': {'.gif'},
}


def _build_tool_params(form_data) -> dict:
    """将 multipart 表单字段转为工具参数，数值字符串自动转换类型"""
    params = {}
    for key, value in form_data.items():
        if key in ('tool_key', 'file', 'files'):
            continue
        if isinstance(value, str):
            try:
                params[key] = int(value)
            except ValueError:
                try:
                    params[key] = float(value)
                except ValueError:
                    params[key] = value
        else:
            params[key] = value
    return params


class FileToolUploadView(views.APIView):
    """文件上传工具执行——接收文件 + 工具参数，用于文件处理类工具"""

    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [AllowAny]

    def post(self, request):
        tool_key = request.data.get('tool_key')
        uploaded_file = request.FILES.get('file')

        if not tool_key:
            return Response({'error': '缺少 tool_key'}, status=status.HTTP_400_BAD_REQUEST)
        if not uploaded_file:
            return Response({'error': '请上传文件'}, status=status.HTTP_400_BAD_REQUEST)

        tool = ToolRegistry.get_tool(tool_key)
        if not tool:
            return Response({'error': '工具不存在'}, status=status.HTTP_404_NOT_FOUND)

        ext = os.path.splitext(uploaded_file.name)[1].lower()
        allowed = _TOOL_ALLOWED_EXTS.get(tool_key)
        if allowed is None:
            return Response({'error': '该工具不支持文件上传'}, status=status.HTTP_400_BAD_REQUEST)
        if ext not in allowed:
            return Response({
                'error': f'仅支持 {", ".join(sorted(allowed))} 文件',
            }, status=status.HTTP_400_BAD_REQUEST)

        temp_dir = os.path.join(settings.MEDIA_ROOT, 'toolkit_uploads')
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, f'{uuid.uuid4().hex}{ext}')
        with open(temp_path, 'wb') as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)

        params = _build_tool_params(request.data)
        params['file'] = temp_path

        definition = ToolkitDefinition.objects.filter(
            tool_key=tool_key, is_enabled=True,
        ).first()

        execution = ToolkitExecution.objects.create(
            tool=definition,
            input_params={'original_name': uploaded_file.name, **params},
            status='running',
            user_id=1,
        ) if definition else None

        try:
            start = time.time()
            result = tool.execute(
                params,
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


class FixedExpenseViewSet(viewsets.ModelViewSet):
    """固定开销计算 CRUD"""

    permission_classes = [AllowAny]
    queryset = FixedExpense.objects.all()
    serializer_class = FixedExpenseSerializer

    def get_queryset(self):
        return FixedExpense.objects.filter(user_id=1)

    def _compute_totals(self, items):
        total_daily = Decimal('0')
        for item in items:
            if not isinstance(item, dict):
                continue
            amount = Decimal(str(item.get('amount') or 0))
            days = PERIOD_DAYS.get(item.get('period') or 'monthly', 30)
            total_daily += (amount / days).quantize(Decimal('0.01'))
        return {
            'total_daily': total_daily,
            'total_monthly': (total_daily * 30).quantize(Decimal('0.01')),
            'total_yearly': (total_daily * 365).quantize(Decimal('0.01')),
        }

    def perform_create(self, serializer):
        items = serializer.validated_data.get('items') or []
        serializer.save(user_id=1, **self._compute_totals(items))

    def perform_update(self, serializer):
        items = serializer.validated_data.get('items')
        kwargs = {}
        if items is not None:
            kwargs.update(self._compute_totals(items))
        serializer.save(**kwargs)


class HourlyWageViewSet(viewsets.ModelViewSet):
    """时薪计算 CRUD"""

    permission_classes = [AllowAny]
    queryset = HourlyWageRecord.objects.all()
    serializer_class = HourlyWageRecordSerializer

    def get_queryset(self):
        return HourlyWageRecord.objects.filter(user_id=1)

    def _compute_wage(self, data):
        from .services import calculate_hourly_wage
        return calculate_hourly_wage(
            monthly_salary=float(data['monthly_salary']),
            rest_type=data.get('rest_type', '双休'),
            work_start=data.get('work_start', '09:00'),
            work_end=data.get('work_end', '18:00'),
            lunch_break=data.get('lunch_break', 60),
            commute_minutes=data.get('commute_minutes', 0),
            calc_mode=data.get('calc_mode', 'formal'),
            freelance_time_mode=data.get('freelance_time_mode', 'fixed'),
            freelance_days=data.get('freelance_days'),
            freelance_hours_per_day=data.get('freelance_hours_per_day'),
            weekly_hours=data.get('weekly_hours', []),
            freelance_weeks=data.get('freelance_weeks', 4),
            extra_incomes=data.get('extra_incomes', []),
        )

    def perform_create(self, serializer):
        result = self._compute_wage(serializer.validated_data)
        serializer.save(user_id=1, **result)

    def perform_update(self, serializer):
        result = self._compute_wage(serializer.validated_data)
        serializer.save(**result)


class ElectricityRecordViewSet(viewsets.ModelViewSet):
    """用电记录 CRUD"""

    permission_classes = [AllowAny]
    queryset = ElectricityRecord.objects.all()
    serializer_class = ElectricityRecordSerializer

    def get_queryset(self):
        return ElectricityRecord.objects.filter(user_id=1)

    def perform_create(self, serializer):
        record = serializer.save(user_id=1)
        ElectricityService.calculate_on_create(record)

    def perform_destroy(self, instance):
        instance.delete()
        ElectricityService.recalculate_all(user_id=1)


TENDENCY_LABELS = {
    'continue': '想继续',
    'quit': '不想继续',
    'uncertain': '不确定',
}
TENDENCY_ORDER = ['continue', 'quit', 'uncertain']
LEAN_LABELS = {'continue': '倾向留下', 'quit': '倾向离开', 'uncertain': '暂不明朗'}
INTENSITY_LABELS = {1: '很弱', 2: '弱', 3: '中', 4: '强', 5: '很强'}
# 强度 ≥ 4（强/很强）计为「高强度」
INTENSITY_HIGH_LEVEL = 4
# 连续多少天没有新记录就提醒（观察期容易断记）
STALE_REMINDER_DAYS = 3


def _lean_option_pairs(tracker) -> list[tuple[str, str]]:
    """追踪可用的倾向选项 [(key, label)]，key 即记录存的 tendency 值"""
    return tracker.tendency_options()


def _option_payload(tracker) -> list[dict]:
    return [{'key': k, 'label': l} for k, l in _lean_option_pairs(tracker)]


def _build_preview(tracker, today):
    """单条决策的倾向预览——占比 + 强度加权分数 + 连续断记天数

    强度即权重（1–5）：
      weighted[t]      该倾向下所有记录的强度之和
      默认三选项追踪   weighted_score = (quit 加权 − continue 加权) / 两者加权和 × 100，正=偏离开
      自定义选项追踪   weighted_score = (主导加权 − 次主导加权) / 加权和 × 100，即主导优势
    """
    records = list(tracker.records.all())
    total = len(records)

    options = _lean_option_pairs(tracker)
    labels = dict(options)
    custom = bool(tracker.lean_options)

    by_tendency: dict[str, list] = defaultdict(list)
    for rec in records:
        by_tendency[rec.tendency].append(rec)
    # 统计口径 = 定义的选项 + 历史记录里出现过但已不在选项中的（兜底显示原文）
    stat_keys = [k for k, _ in options] + [t for t in by_tendency if t not in labels]

    weighted = {t: sum(r.intensity for r in by_tendency.get(t, [])) for t in stat_keys}
    weighted_total = sum(weighted.values())

    tendency_stats = []
    for t in stat_keys:
        items = by_tendency.get(t, [])
        count = len(items)
        high = sum(1 for r in items if r.intensity >= INTENSITY_HIGH_LEVEL)
        tendency_stats.append({
            'tendency': t,
            'label': labels.get(t, t),
            'count': count,
            'percent': round(count / total * 100, 1) if total else 0.0,
            'weighted': weighted[t],
            'weighted_percent': round(weighted[t] / weighted_total * 100, 1) if weighted_total else 0.0,
            'avg_intensity': round(weighted[t] / count, 1) if count else 0.0,
            'high_count': high,
            'high_ratio': round(high / count * 100, 1) if count else 0.0,
        })

    # 主导倾向：先比条数，再比加权分，最后按选项定义顺序收敛
    lean_tendency = None
    if total:
        lean_tendency = min(
            stat_keys,
            key=lambda t: (-len(by_tendency.get(t, [])), -weighted[t], stat_keys.index(t)),
        )
    lean_stat = next((s for s in tendency_stats if s['tendency'] == lean_tendency), None)

    # 加权分：默认三项沿用「离开−留下」双向分；自定义选项改用「主导 − 次主导」优势分（恒 ≥ 0）
    ranked = sorted(stat_keys, key=lambda t: -weighted[t])
    if custom:
        weighted_score = (
            round((weighted[ranked[0]] - weighted[ranked[1]]) / weighted_total * 100, 1)
            if weighted_total and len(ranked) > 1 else 0.0
        )
        weighted_lean_percent = (
            round(weighted[ranked[0]] / weighted_total * 100, 1) if weighted_total else 0.0
        )
    else:
        quit_continue_weight = weighted['quit'] + weighted['continue']
        weighted_score = (
            round((weighted['quit'] - weighted['continue']) / quit_continue_weight * 100, 1)
            if quit_continue_weight else 0.0
        )
        weighted_lean_percent = (
            round(weighted['quit'] / quit_continue_weight * 100, 1) if quit_continue_weight else 0.0
        )

    last_record_date = max((r.record_date for r in records), default=None)
    # 无记录时以观察开始日为准——建了追踪却一直没记，同样算断记
    stale_days = max((today - (last_record_date or tracker.start_date)).days, 0)

    if not total:
        conclusion = '还没有任何记录，先记一条看看'
    elif lean_stat:
        if custom:
            conclusion = (
                f"目前 {lean_stat['percent']}% 倾向「{lean_stat['label']}」，"
                f"其中高强度占 {lean_stat['high_count']}/{lean_stat['count']}"
            )
        else:
            conclusion = (
                f"目前 {lean_stat['percent']}% {LEAN_LABELS[lean_tendency]}，"
                f"其中高强度占 {lean_stat['high_count']}/{lean_stat['count']}"
            )
    else:
        conclusion = ''

    return {
        'tracker_id': tracker.id,
        'topic': tracker.topic,
        'status': tracker.status,
        'total_records': total,
        'record_days': len({r.record_date for r in records}),
        'last_record_date': last_record_date.strftime('%Y-%m-%d') if last_record_date else None,
        'stale_days': stale_days,
        'needs_reminder': tracker.status == '观察中' and stale_days >= STALE_REMINDER_DAYS,
        'options': _option_payload(tracker),
        'lean_tendency': lean_tendency,
        'lean_label': (
            lean_stat['label'] if (custom and lean_stat)
            else LEAN_LABELS.get(lean_tendency, '') if lean_tendency else ''
        ),
        'lean_percent': lean_stat['percent'] if lean_stat else 0.0,
        'weighted_total': weighted_total,
        'weighted_score': weighted_score,
        'weighted_lean_percent': weighted_lean_percent,
        'high_count': sum(1 for r in records if r.intensity >= INTENSITY_HIGH_LEVEL),
        'conclusion': conclusion,
        'tendency_stats': tendency_stats,
    }


class DecisionTrackerViewSet(viewsets.ModelViewSet):
    """决策追踪器 CRUD + 到期状态流转 + 汇总报告"""

    permission_classes = [AllowAny]
    queryset = DecisionTracker.objects.all()
    serializer_class = DecisionTrackerSerializer

    def get_queryset(self):
        # 到期自动流转：观察中且已过 end_date → 已到期（幂等）
        DecisionTracker.objects.filter(
            status='观察中', end_date__lt=date.today(),
        ).update(status='已到期')
        qs = super().get_queryset()
        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    @action(detail=True, methods=['get'])
    def records(self, request, pk=None):
        """该决策的全部日常记录（日期倒序）"""
        tracker = self.get_object()
        records = tracker.records.all()
        serializer = DecisionRecordSerializer(records, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def report(self, request, pk=None):
        """到期汇总报告——倾向统计 / 月度趋势 / 理由明细（本地聚合，选项随追踪自定义）"""
        tracker = self.get_object()
        records = list(tracker.records.all())

        options = _lean_option_pairs(tracker)
        labels = dict(options)
        total = len(records)
        by_tendency: dict[str, list] = defaultdict(list)
        monthly: dict[str, dict[str, int]] = defaultdict(dict)
        for rec in records:
            by_tendency[rec.tendency].append(rec)
            month_key = rec.record_date.strftime('%Y-%m')
            monthly[month_key][rec.tendency] = monthly[month_key].get(rec.tendency, 0) + 1

        # 统计口径 = 定义的选项 + 历史记录里出现过但已不在选项中的（兜底显示原文）
        stat_keys = [k for k, _ in options] + [t for t in by_tendency if t not in labels]

        tendency_stats = []
        for t in stat_keys:
            items = by_tendency.get(t, [])
            tendency_stats.append({
                'tendency': t,
                'label': labels.get(t, t),
                'count': len(items),
                'percent': round(len(items) / total * 100, 1) if total else 0,
            })

        monthly_trend = [
            {'month': k, **{t: monthly[k].get(t, 0) for t in stat_keys}}
            for k in sorted(monthly.keys())
        ]

        reasons = {
            t: [
                {
                    'record_date': rec.record_date.strftime('%Y-%m-%d'),
                    'intensity': rec.intensity,
                    'intensity_label': INTENSITY_LABELS.get(rec.intensity, str(rec.intensity)),
                    'reason': rec.reason,
                }
                for rec in sorted(by_tendency.get(t, []), key=lambda r: r.record_date, reverse=True)
                if rec.reason
            ]
            for t in stat_keys
        }

        return Response({
            'tracker': {
                'id': tracker.id,
                'topic': tracker.topic,
                'background': tracker.background,
                'start_date': tracker.start_date,
                'end_date': tracker.end_date,
                'status': tracker.status,
            },
            'options': _option_payload(tracker),
            'total_records': total,
            'record_days': len({r.record_date for r in records}),
            'tendency_stats': tendency_stats,
            'monthly_trend': monthly_trend,
            'reasons': reasons,
        })

    @action(detail=False, methods=['get'])
    def preview(self, request):
        """随时可看的倾向汇总——占比 + 强度加权分数 + 连续断记天数（不必等到期）

        查询参数：?tracker=<id> 只看某条决策；?status=观察中 只看某状态（同列表口径）
        """
        today = timezone.localdate()
        qs = self.get_queryset()  # 含到期自动流转 + ?status= 过滤
        tracker_id = request.query_params.get('tracker')
        if tracker_id:
            qs = qs.filter(id=tracker_id)

        items = [_build_preview(t, today) for t in qs]
        stale_trackers = [
            {
                'tracker_id': i['tracker_id'],
                'topic': i['topic'],
                'stale_days': i['stale_days'],
                'last_record_date': i['last_record_date'],
            }
            for i in items if i['needs_reminder']
        ]
        reminder_text = ''
        if stale_trackers:
            first = stale_trackers[0]
            more = f"，另有 {len(stale_trackers) - 1} 个决策同样断记" if len(stale_trackers) > 1 else ''
            reminder_text = (
                f"「{first['topic']}」已连续 {first['stale_days']} 天没有记录{more}，"
                f"观察期容易就此中断，记得补一条。"
            )

        return Response({
            'generated_at': timezone.now().isoformat(),
            'stale_threshold_days': STALE_REMINDER_DAYS,
            'tracker_count': len(items),
            'total_records': sum(i['total_records'] for i in items),
            'has_reminder': bool(stale_trackers),
            'reminder_text': reminder_text,
            'stale_trackers': stale_trackers,
            'items': items,
        })

    @action(detail=True, methods=['post'])
    def decide(self, request, pk=None):
        """做出决定：填最终决定 + 决定日期 → 状态置为已决策"""
        tracker = self.get_object()
        final_decision = (request.data.get('final_decision') or '').strip()
        if not final_decision:
            return Response({'error': '请填写最终决定'}, status=status.HTTP_400_BAD_REQUEST)
        decision_date = request.data.get('decision_date') or date.today().isoformat()
        tracker.final_decision = final_decision
        tracker.decision_date = decision_date
        tracker.status = '已决策'
        tracker.save(update_fields=['final_decision', 'decision_date', 'status', 'updated_at'])
        return Response(DecisionTrackerSerializer(tracker).data)

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """归档：附事后回看（可选，30 天后补填）→ 状态置为已归档"""
        tracker = self.get_object()
        review_note = request.data.get('review_note')
        if review_note is not None:
            tracker.review_note = str(review_note).strip()
        tracker.status = '已归档'
        tracker.save(update_fields=['review_note', 'status', 'updated_at'])
        return Response(DecisionTrackerSerializer(tracker).data)


class DecisionRecordViewSet(viewsets.ModelViewSet):
    """决策日常记录 CRUD（创建/删除为主，列表可按 tracker 过滤）"""

    permission_classes = [AllowAny]
    queryset = DecisionRecord.objects.all()
    serializer_class = DecisionRecordSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        tracker_id = self.request.query_params.get('tracker')
        if tracker_id:
            qs = qs.filter(tracker_id=tracker_id)
        return qs


class AskTopicViewSet(viewsets.ModelViewSet):
    """AI 问答库·主题：全文检索（问题/追问/背景/回答/会话/AI）+ 场景/标签/AI/日期过滤"""

    permission_classes = [AllowAny]
    queryset = AskTopic.objects.all()
    serializer_class = AskTopicSerializer

    def get_queryset(self):
        qs = AskTopic.objects.annotate(answer_count=Count('answers'))
        params = self.request.query_params
        keyword = (params.get('search') or '').strip()
        if keyword:
            qs = qs.filter(
                Q(title__icontains=keyword)
                | Q(question__icontains=keyword)
                | Q(background__icontains=keyword)
                | Q(answers__answer__icontains=keyword)
                | Q(answers__question__icontains=keyword)
                | Q(answers__session__icontains=keyword)
                | Q(answers__ai__icontains=keyword)
            ).distinct()
        scene = (params.get('scene') or '').strip()
        if scene:
            qs = qs.filter(scene_id=scene) if scene != 'none' else qs.filter(scene__isnull=True)
        tag = (params.get('tag') or '').strip()
        if tag:
            qs = qs.filter(tags__contains=[tag])
        ai = (params.get('ai') or '').strip()
        if ai:
            qs = qs.filter(answers__ai__icontains=ai).distinct()
        has_accepted = (params.get('has_accepted') or '').strip()
        if has_accepted and has_accepted.lower() in ('1', 'true', 'yes'):
            qs = qs.filter(answers__verdict='采纳').distinct()
        date_from = (params.get('date_from') or '').strip()
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        date_to = (params.get('date_to') or '').strip()
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        # distinct()/filter 后会丢 Meta ordering，统一按创建时间倒序
        return qs.order_by('-created_at')

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """采纳结论汇总：某范围（?scene=<id>|none|空=全部）内所有 ✅采纳 回答清单，供导出回顾。

        返回结构 { topics: [{id, title, question, scene_name, created_at,
        accepted: [{ai, session, question, asked_at, answer, note}]}] } —— 仅含采纳节点；
        追问节点若被采纳则 question 为该轮追问文本，便于还原上下文。
        """
        scene = (request.query_params.get('scene') or '').strip()
        qs = AskTopic.objects.filter(answers__verdict='采纳').distinct()
        if scene == 'none':
            qs = qs.filter(scene__isnull=True)
        elif scene:
            qs = qs.filter(scene_id=scene)
        topics = (
            qs.select_related('scene')
            .prefetch_related('answers')
            .order_by('-created_at')
        )
        result = []
        for t in topics:
            accepted = [a for a in t.answers.all() if a.verdict == '采纳']
            if not accepted:
                continue
            result.append({
                'id': t.id,
                'title': t.title,
                'question': t.question,
                'scene_name': t.scene.name if t.scene_id else '',
                'created_at': t.created_at,
                'accepted': [{
                    'ai': a.ai,
                    'session': a.session,
                    'question': a.question,
                    'asked_at': a.asked_at,
                    'answer': a.answer,
                    'note': a.note,
                } for a in sorted(accepted, key=lambda x: x.asked_at)],
            })
        return Response({'topics': result})


class AskSceneViewSet(viewsets.ModelViewSet):
    """AI 问答库·业务场景容器 CRUD（list 带 topic_count 注解）"""

    permission_classes = [AllowAny]
    queryset = AskScene.objects.all()
    serializer_class = AskSceneSerializer

    def get_queryset(self):
        return AskScene.objects.annotate(topic_count=Count('topics')).order_by('sort', 'id')


class AskAnswerViewSet(viewsets.ModelViewSet):
    """AI 问答库·回答：按 topic 过滤；verdict 采纳标记行内可改"""

    permission_classes = [AllowAny]
    queryset = AskAnswer.objects.all()
    serializer_class = AskAnswerSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        topic_id = self.request.query_params.get('topic')
        if topic_id:
            qs = qs.filter(topic_id=topic_id)
        return qs
