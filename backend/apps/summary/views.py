"""综合进度看板 — API 视图"""

from datetime import datetime

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .constants import MODULE_LIST
from .services import ProgressAggregator, QuarterlyWorkbenchService


class SummaryViewSet(viewsets.ViewSet):
    """综合进度看板 — 只读聚合 API"""

    permission_classes = [AllowAny]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        """年度总览：各模块进度 + 目标完成率"""
        year = request.query_params.get('year')
        if year:
            year = int(year)
        data = ProgressAggregator.get_yearly_overview(year)
        return Response(data)

    @action(detail=False, methods=['get'])
    def monthly_detail(self, request):
        """月度详情：指定年月各模块进度"""
        year = request.query_params.get('year')
        month = request.query_params.get('month')
        if year:
            year = int(year)
        if month:
            month = int(month)
        data = ProgressAggregator.get_monthly_detail(year, month)
        return Response(data)

    @action(detail=False, methods=['get'])
    def trend(self, request):
        """月度趋势：12 个月各模块堆叠数据"""
        year = request.query_params.get('year')
        if year:
            year = int(year)
        data = ProgressAggregator.get_trend(year)
        return Response(data)

    @action(detail=False, methods=['get'])
    def radar(self, request):
        """雷达图：7 维度年度达成数据"""
        year = request.query_params.get('year')
        if year:
            year = int(year)
        data = ProgressAggregator.get_radar(year)
        return Response(data)

    @action(detail=False, methods=['get'])
    def years(self, request):
        """有数据的年份列表"""
        data = ProgressAggregator.get_available_years()
        return Response(data)

    @action(detail=False, methods=['get'])
    def module_detail(self, request):
        """模块详情钻取"""
        module = request.query_params.get('module')
        year = request.query_params.get('year')
        month = request.query_params.get('month')

        if module not in MODULE_LIST:
            return Response({'error': f'未知模块: {module}'}, status=400)

        if year:
            year = int(year)
        if month:
            month = int(month)

        data = ProgressAggregator.get_module_detail(module, year, month)
        return Response(data)

    @action(detail=False, methods=['get'])
    def random_retro(self, request):
        """随机返回一条过去的记录（日记、小确幸、读后感）"""
        import random

        items = []

        # 随机日记
        try:
            from apps.temporal.models import OneDayPage
            diary = OneDayPage.objects.exclude(title='').order_by('?').values('title', 'begin_date').first()
            if diary:
                items.append({
                    'type': '📝 日记',
                    'content': diary['title'][:200],
                    'date': diary['begin_date'].isoformat() if diary['begin_date'] else '',
                })
        except Exception:
            pass

        # 随机小确幸
        try:
            from apps.sugar.models import SugarRecord
            sugar = SugarRecord.objects.order_by('?').values('content', 'time').first()
            if sugar:
                items.append({
                    'type': '🍰 小确幸',
                    'content': sugar['content'][:200],
                    'date': sugar['time'].isoformat() if sugar['time'] else '',
                })
        except Exception:
            pass

        # 随机读后感
        try:
            from apps.book.models import Book
            book = Book.objects.exclude(closedop__isnull=True).exclude(closedop='').order_by('?').values('closedop', 'readDate', 'btitle').first()
            if book:
                items.append({
                    'type': '📖 读书感悟',
                    'content': f"《{book['btitle']}」{book['closedop'][:180]}"[:200],
                    'date': book['readDate'].isoformat() if book['readDate'] else '',
                })
        except Exception:
            pass

        if items:
            return Response(random.choice(items))
        return Response({'type': '', 'content': '暂无历史记录', 'date': ''})

    # ── 季度决策工作台 ─────────────────────────────────

    @action(detail=False, methods=['get'])
    def quarterly_report(self, request):
        """季度对比报告"""
        year = request.query_params.get('year')
        quarter = request.query_params.get('quarter')
        if not year or not quarter:
            return Response({'error': '需要 year 和 quarter 参数'}, status=status.HTTP_400_BAD_REQUEST)
        data = QuarterlyWorkbenchService.get_quarterly_report(int(year), int(quarter))
        return Response(data)

    @action(detail=False, methods=['get'])
    def quarterly_questions(self, request):
        """季度追问列表"""
        year = request.query_params.get('year')
        quarter = request.query_params.get('quarter')
        if not year or not quarter:
            return Response({'error': '需要 year 和 quarter 参数'}, status=status.HTTP_400_BAD_REQUEST)
        data = QuarterlyWorkbenchService.generate_questions(int(year), int(quarter))
        return Response(data)

    @action(detail=False, methods=['get', 'post'])
    def quarterly_answers(self, request):
        """获取/保存季度追问的回答"""
        year = request.query_params.get('year')
        quarter = request.query_params.get('quarter')
        if not year or not quarter:
            return Response({'error': '需要 year 和 quarter 参数'}, status=status.HTTP_400_BAD_REQUEST)

        if request.method == 'GET':
            data = QuarterlyWorkbenchService.get_answers(int(year), int(quarter))
            return Response(data)

        # POST: 保存回答
        answers = request.data if isinstance(request.data, list) else [request.data]
        results = []
        for ans in answers:
            result = QuarterlyWorkbenchService.save_answer(
                year=int(year),
                quarter=int(quarter),
                question_key=ans['question_key'],
                answer_text=ans.get('answer_text', ''),
                action_taken=ans.get('action_taken', False),
            )
            results.append(result)
        return Response(results, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def quarterly_insights(self, request):
        """季度洞察摘要"""
        year = request.query_params.get('year')
        quarter = request.query_params.get('quarter')
        if not year or not quarter:
            return Response({'error': '需要 year 和 quarter 参数'}, status=status.HTTP_400_BAD_REQUEST)
        data = QuarterlyWorkbenchService.get_insights(int(year), int(quarter))
        return Response(data)
