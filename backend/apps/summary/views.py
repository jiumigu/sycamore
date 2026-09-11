"""综合进度看板 — API 视图"""

from datetime import datetime

from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncDate

from rest_framework import status, views, viewsets
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
        """年度明细：每年一行（总进度/目标/7 模块/达成率）"""
        years = ProgressAggregator.get_available_years()
        rows = []
        for y in years:
            data = ProgressAggregator.get_yearly_overview(y)
            mod_map = {m['module']: m['points'] for m in data['modules']}
            rows.append({
                'year': data['year'],
                'total_points': data['total_points'],
                'yearly_target': data['yearly_target'],
                'progress_percent': data['progress_percent'],
                'wealth': mod_map.get('wealth', 0),
                'health': mod_map.get('health', 0),
                'times': mod_map.get('times', 0),
                'book': mod_map.get('book', 0),
                'sugar': mod_map.get('sugar', 0),
                'travel': mod_map.get('travel', 0),
                'words': mod_map.get('words', 0),
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


class PersonalProfileView(views.APIView):
    """个人画像仪表盘"""

    permission_classes = [AllowAny]

    def get(self, request):
        year = request.query_params.get('year')
        if year:
            year = int(year)
        else:
            year = datetime.now().year

        return Response({
            'health': self._health_profile(year),
            'energy': self._energy_profile(year),
            'mood': self._mood_profile(year),
            'relation': self._relation_profile(year),
            'output': self._output_profile(year),
            'inbox': self._inbox_profile(),
            'decision': self._decision_profile(year),
        })

    def _health_profile(self, year: int) -> dict:
        """健康画像：最新自查分 + 体重趋势"""
        from apps.toolkit.models import HealthSelfCheck
        from apps.health.models import WeightRecord

        latest_check = HealthSelfCheck.objects.filter(
            check_date__year=year, user_id=1,
        ).order_by('-check_date').first()

        checks = list(HealthSelfCheck.objects.filter(
            check_date__year=year, user_id=1,
        ).values('check_date', 'health_score').order_by('check_date'))

        weight_qs = WeightRecord.objects.filter(
            record_date__year=year,
        ).order_by('-record_date')

        latest_weight = weight_qs.first()
        all_weights = list(weight_qs.order_by('record_date').values('record_date', 'weight_kg'))

        return {
            'latest_score': latest_check.health_score if latest_check else None,
            'score_trend': [{'date': c['check_date'], 'value': c['health_score']} for c in checks],
            'latest_weight': float(latest_weight.weight_kg) if latest_weight else None,
            'weight_trend': [{'date': w['record_date'], 'value': float(w['weight_kg'])} for w in all_weights],
            'check_count': len(checks),
        }

    def _energy_profile(self, year: int) -> dict:
        """职业能量画像"""
        from apps.toolkit.models import CareerEnergyAudit

        latest = CareerEnergyAudit.objects.filter(
            audit_date__year=year, user_id=1,
        ).order_by('-audit_date').first()

        all_audits = list(CareerEnergyAudit.objects.filter(
            audit_date__year=year, user_id=1,
        ).values('audit_date', 'total_score', 'work_score', 'env_score', 'growth_score', 'body_score').order_by('audit_date'))

        return {
            'latest': {
                'total_score': latest.total_score if latest else None,
                'work_score': latest.work_score if latest else None,
                'env_score': latest.env_score if latest else None,
                'growth_score': latest.growth_score if latest else None,
                'body_score': latest.body_score if latest else None,
                'decision': latest.decision if latest else None,
            } if latest else None,
            'trend': [{
                'date': a['audit_date'],
                'total': a['total_score'],
                'work': a['work_score'],
                'env': a['env_score'],
                'growth': a['growth_score'],
                'body': a['body_score'],
            } for a in all_audits],
            'audit_count': len(all_audits),
        }

    def _mood_profile(self, year: int) -> dict:
        """情绪画像：小确幸数据"""
        from apps.sugar.models import SugarRecord

        qs = SugarRecord.objects.filter(years=year)
        total = qs.count()

        if total == 0:
            return {'total_records': 0, 'avg_happiness': None, 'happiness_trend': [], 'active_days': 0}

        agg = qs.aggregate(avg=Avg('level_of_happiness'))
        trend = list(qs.values('time', 'level_of_happiness').order_by('time'))

        return {
            'total_records': total,
            'avg_happiness': round(float(agg['avg'] or 0), 2),
            'happiness_trend': [{'date': t['time'], 'value': float(t['level_of_happiness'])} for t in trend],
            'active_days': qs.dates('time', 'day').count(),
        }

    def _relation_profile(self, year: int) -> dict:
        """关系画像"""
        from apps.relation.models import Relationship, Interaction

        total_relations = Relationship.objects.count()
        active_relations = Interaction.objects.filter(
            happened_at__year=year,
        ).values('relationship_id').distinct().count()

        interaction_count = Interaction.objects.filter(happened_at__year=year).count()

        return {
            'total_relations': total_relations,
            'active_relations': active_relations,
            'interactions_this_year': interaction_count,
        }

    def _output_profile(self, year: int) -> dict:
        """良品率画像"""
        from apps.goals.models import OutputRecord

        qs = OutputRecord.objects.filter(created_at__year=year)
        total = qs.count()
        if total == 0:
            return {'total_records': 0, 'good_rate': None, 'by_category': []}

        good = qs.filter(quality='good').count()
        by_cat = list(qs.values('category').annotate(
            total=Count('id'),
            good=Count('id', filter=Q(quality='good')),
        ))

        return {
            'total_records': total,
            'good_rate': round(good / total * 100, 1) if total > 0 else 0,
            'by_category': [{
                'category': c['category'],
                'total': c['total'],
                'good': c['good'],
                'rate': round(c['good'] / c['total'] * 100, 1) if c['total'] > 0 else 0,
            } for c in by_cat],
        }

    def _inbox_profile(self) -> dict:
        """收件箱画像"""
        from apps.inbox.models import InboxItem

        pending = InboxItem.objects.filter(status='pending').count()
        hesitating = InboxItem.objects.filter(status='hesitating').count()
        done_this_year = InboxItem.objects.filter(
            status='done', updated_at__year=datetime.now().year,
        ).count()
        total = InboxItem.objects.count()

        by_category = list(InboxItem.objects.values('category').annotate(
            count=Count('id'),
        ))

        return {
            'pending': pending,
            'hesitating': hesitating,
            'done_this_year': done_this_year,
            'total': total,
            'by_category': by_category,
        }
