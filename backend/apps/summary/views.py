"""综合进度看板 — API 视图"""

from datetime import datetime

from django.db.models import Q

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .constants import MODULE_LIST
from .models import SevenDimConfig
from .serializers import SevenDimConfigSerializer
from .services import BodyMindCorrelationService, ProgressAggregator, QuarterlyWorkbenchService


class SummaryViewSet(viewsets.ViewSet):
    """综合进度看板 — 只读聚合 API"""

    permission_classes = [AllowAny]

    def dispatch(self, request, *args, **kwargs):
        """给整个请求开一个取数作用域

        🔴 只在这里开：一次请求内「同一份事实」被反复取（年视图 + 月视图 +
           强度），作用域内记一次就够。出作用域即销毁 —— **不做跨请求缓存**，
           否则用户改完归因规则再刷新，页面还会显示旧口径。
        """
        with ProgressAggregator.request_scope():
            return super().dispatch(request, *args, **kwargs)

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

    CONFIG_MAX_FIELDS = [
        'wealth_max', 'health_max', 'times_max',
        'words_max', 'sugar_max', 'travel_max', 'book_max',
    ]

    @action(detail=False, methods=['get'])
    def yearly_detail(self, request):
        """年度明细：每年一行（各维度**覆盖率** + 当年最短板）

        🔴 v3.62.43 起不再有「总进度 / 目标 / 达成率」三列 —— 总分解散后
        这些年行没有可加的量，硬凑一个合计就是又把不同量纲加回去。
        """
        years = ProgressAggregator.get_available_years()
        rows = []
        for y in years:
            data = ProgressAggregator.get_yearly_overview(y)
            mod_map = {m['module']: m['coverage']['pct'] for m in data['modules']}
            weakest = data.get('weakest') or {}
            rows.append({
                'year': data['year'],
                'weakest': weakest.get('label'),
                'weakest_pct': weakest.get('coverage_pct'),
                'wealth': mod_map.get('wealth'),
                'health': mod_map.get('health'),
                'times': mod_map.get('times'),
                'book': mod_map.get('book'),
                'sugar': mod_map.get('sugar'),
                'travel': mod_map.get('travel'),
                'words': mod_map.get('words'),
            })
        return Response({'years': rows})

    @action(detail=False, methods=['get'])
    def radar_config(self, request):
        """七维平衡封顶配置：当前生效的一条"""
        cfg = SevenDimConfig.get_active()
        return Response(SevenDimConfigSerializer(cfg).data)

    @action(detail=False, methods=['get'])
    def radar_config_history(self, request):
        """七维平衡封顶配置：历史版本列表（倒序）"""
        qs = SevenDimConfig.objects.all()[:30]
        return Response(SevenDimConfigSerializer(qs, many=True).data)

    @radar_config.mapping.post
    @radar_config.mapping.put
    @radar_config.mapping.patch
    def update_radar_config(self, request):
        """七维平衡封顶配置：新增一个版本并生效（未传字段沿用当前值，旧版本自动失效）"""
        current = SevenDimConfig.get_active()
        data = {
            f: request.data.get(f, getattr(current, f))
            for f in self.CONFIG_MAX_FIELDS
        }
        ser = SevenDimConfigSerializer(data=data)
        if not ser.is_valid():
            return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
        note = request.data.get('note', '')
        new = SevenDimConfig.apply_config(
            {f: ser.validated_data[f] for f in self.CONFIG_MAX_FIELDS},
            note,
        )
        return Response(SevenDimConfigSerializer(new).data)

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
            diary = OneDayPage.objects.exclude(title='').exclude(title__icontains='幸福未被发现').order_by('?').values('title', 'begin_date').first()
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

        # 随机摘录
        try:
            from apps.toolkit.models import Quote
            quote = Quote.objects.exclude(
                content__icontains='幸福未被发现，就叫做普通的一天'
            ).exclude(
                short_title__icontains='幸福未被发现，就叫做普通的一天'
            ).order_by('?').first()
            if quote:
                text = quote.short_title or quote.content[:200]
                if quote.author:
                    text += f' —— {quote.author}'
                items.append({
                    'type': '📖 摘录',
                    'content': text,
                    'date': quote.created_at.isoformat() if quote.created_at else '',
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

    # ── 身体-状态关联 ─────────────────────────────────────

    @action(detail=False, methods=['get'])
    def body_mind(self, request):
        """身体-状态关联：睡眠、良品率、情绪趋势"""
        weeks = int(request.query_params.get('weeks', 12))
        user_id = int(request.query_params.get('user_id', 1))
        data = BodyMindCorrelationService.get_correlation_data(user_id=user_id, weeks=weeks)
        return Response(data)
