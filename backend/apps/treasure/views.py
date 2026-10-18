from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from . import services
from .constants import (
    METHOD_GROUP_OPTIONS,
    SUBJECT_KIND_OPTIONS,
    categories_for,
)
from .models import GoodThing
from .serializers import GoodThingSerializer, TreasureMetaSerializer


class GoodThingViewSet(viewsets.ModelViewSet):
    """好恶物档案馆视图集

    ⚠️ `pagination_class = None`（裸数组）：DRF 全局分页会把它包成
       `{count, results}`，前端按数组消费即**静默显示为空**（项目硬坑②）。
       档案是几十条的量级，不需要分页。
    """

    queryset = GoodThing.objects.all()
    permission_classes = [AllowAny]
    serializer_class = GoodThingSerializer
    pagination_class = None

    def get_queryset(self):
        # `select_related` 一次带出关联实物：列表要显示「🔗 物件资产 · 空气炸锅」，
        # 不预取就是每条一次查询（N+1，小数据量下看不出来）。
        qs = GoodThing.objects.select_related('property', 'survival_item')
        params = self.request.query_params

        record_type = params.get('record_type')
        if record_type:
            qs = qs.filter(record_type=record_type)

        subject_kind = params.get('subject_kind')
        if subject_kind:
            qs = qs.filter(subject_kind=subject_kind)

        category = params.get('category')
        if category:
            qs = qs.filter(category=category)

        # 「待补理由」出口（入口 4）：答案留空是允许的，但**留空这件事必须看得见**
        # —— 否则「允许留空」会退化成「永远空着」。
        if params.get('pending_reason'):
            qs = qs.filter(
                Q(record_type='好', why_good='') | Q(record_type='歹', avoid_reason=''),
            )

        return qs

    def get_serializer_context(self):
        context = super().get_serializer_context()
        # ⚠️ 关联实物的事实（折旧、净值）只在**详情**时算：
        #    列表对每条档案各算一次是 N+1，而列表上并不需要这些数。
        context['with_linked_facts'] = self.action == 'retrieve'
        return context

    @action(detail=False, methods=['get'])
    def meta(self, request):
        """口径与枚举的单一出口。

        ⚠️ 类别文案**按侧各一套**（好物侧「🏪 好店」/ 歹物侧「🏪 坑店」），
           所以下发的是 `categories_by_type` 而不是一个扁平列表 ——
           前端按当前 `record_type` 取，不自己拼文案。
        """
        payload = {
            'subject_kind_options': SUBJECT_KIND_OPTIONS,
            'method_group_options': METHOD_GROUP_OPTIONS,
            'categories_by_type': {
                '好': categories_for('好'),
                '歹': categories_for('歹'),
            },
            'record_type_options': [
                {'value': value, 'label': label}
                for value, label in GoodThing.RECORD_TYPE_CHOICES
            ],
        }
        return Response(TreasureMetaSerializer(payload).data)

    @action(detail=False, methods=['get'], url_path='link_candidates')
    def link_candidates(self, request):
        """档案侧「输入即搜实物」（入口 3）。

        返回 `{rows, total, limit}` —— **不是裸数组**，因为这里存在取数上限，
        而「只给了前 N 条」必须被说出来（项目硬坑② 的有意变体）。
        """
        raw_limit = request.query_params.get('limit')
        limit = services.LINK_CANDIDATE_LIMIT
        if raw_limit and str(raw_limit).isdigit():
            limit = max(1, min(int(raw_limit), 50))
        payload = services.search_link_candidates(
            request.query_params.get('search') or '', limit=limit,
        )
        return Response(payload)
