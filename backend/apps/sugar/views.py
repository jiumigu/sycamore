import re
from datetime import datetime

from django.db import transaction
from django.db.models import Avg, Count, Q, Sum
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .constants import (
    JOY_TYPE_LEGACY_SUFFIX,
    JOY_TYPE_UNLABELED_LABEL,
    JOY_TYPE_UNLABELED_PARAM,
    SUGAR_HAPPINESS_BANDS,
    SUGAR_HAPPINESS_MAX,
    SUGAR_HAPPINESS_MIN,
    TAG_PARAM,
    TAG_UNTAGGED_LABEL,
    TAG_UNTAGGED_PARAM,
)
from .models import SugarRecord, SugarTemplate
from .serializers import (
    SugarCategoryStatsSerializer,
    SugarRecordSerializer,
    SugarTemplateSerializer,
)
from .services import SugarRecordService


class SugarPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'


def _split_tags(raw: str | None) -> list[str]:
    """把逗号分隔的 `tags` 拆成标签项 —— 「有哪些标签」与「按标签筛」共用这一把尺子。

    前端 `openEdit` 解析同一个字段时也 `map(t => t.trim())`，说明存储里理论上
    可能存在逗号后的空格（早期手工录入）。两处判据必须一致，否则会出现
    「下拉里能看到『成就』，选中却筛不到任何记录」。
    """
    if not raw:
        return []
    return [t.strip() for t in raw.split(',') if t.strip()]


def _tag_item_q(tag: str) -> Q:
    """按**标签项**精确匹配，不是按子串匹配。

    🔴 这是本功能唯一容易做错的地方。库里「成就」「内在成就」「外在成就」三个标签
       互为子串，用 `tags__contains='成就'` 筛「成就」会得到 19 条（实测），
       而真正的「成就」只有 6 条。数字看着合理、不报错、也不会有任何提示，
       是典型的静默错数。

    换成正则锚在逗号边界上：`(^|,)\\s*成就\\s*(,|$)`。
    `\\s*` 不是多余的 —— 见 `_split_tags` 里对带空格历史数据的说明。
    """
    pattern = rf'(^|,)\s*{re.escape(tag.strip())}\s*(,|$)'
    return Q(tags__regex=pattern)


def _apply_record_scope(qs, params):
    """按年份 / 月份 / 分类 / 快乐类型 / 标签过滤 —— 列表与几处统计**共用这一把尺子**。

    为什么必须共用：这几个参数决定「屏幕上哪些记录算数」。如果只给列表加了
    `joy_type`，而顶部「累计奖励」「平均快乐」还按全量算，同一屏就会出现两个
    各自成立、互相矛盾的数 —— 而且没有任何报错。

    `category` 为空串不会被当成筛选（DRF 里 `params.get()` 对「没传」返回 None、
    对 `?category=` 返回 `''`，两者都不做过滤 —— 空串不是一个合法分类，
    这里按「没传」处理，不像 `joy_type` 那样有「未标注」这种真实语义）。
    """
    year = params.get('year')
    if year:
        qs = qs.filter(years=int(year))

    month = params.get('month')
    if month:
        qs = qs.filter(month=int(month))

    category = params.get('category')
    if category:
        qs = qs.filter(category=category)

    joy_type = params.get('joy_type')
    if joy_type == JOY_TYPE_UNLABELED_PARAM:
        # 该列是 NOT NULL DEFAULT ''，理论上不该有 NULL；但早期数据/手工 SQL 可能留下，
        # 漏掉 `isnull` 这几条就会在任何筛选下都看不见（静默漏数）。
        qs = qs.filter(Q(joy_type='') | Q(joy_type__isnull=True))
    elif joy_type:
        qs = qs.filter(joy_type=joy_type)

    tag = params.get('tag')
    if tag == TAG_UNTAGGED_PARAM:
        # 同 `joy_type` 的未标注：NULL 与空串是同一个意思（这条记录没打标签），
        # 分两种状态对用户毫无意义，但 SQL 上是两回事，漏一个就会少几十条。
        qs = qs.filter(Q(tags__isnull=True) | Q(tags=''))
    elif tag:
        qs = qs.filter(_tag_item_q(tag))

    return qs


class SugarRecordViewSet(viewsets.ModelViewSet):
    """小确幸记录视图集"""

    queryset = SugarRecord.objects.all()
    serializer_class = SugarRecordSerializer
    permission_classes = [AllowAny]
    pagination_class = SugarPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'notes', 'tags']
    ordering_fields = ['time', 'level_of_happiness', 'created_at', 'reward_amount']
    ordering = ['-time', '-s_id']

    def get_queryset(self):
        qs = _apply_record_scope(super().get_queryset(), self.request.query_params)

        min_happiness = self.request.query_params.get('min_happiness')
        if min_happiness:
            qs = qs.filter(level_of_happiness__gte=float(min_happiness))

        return qs

    @transaction.atomic
    def perform_create(self, serializer):
        """建档 + 发奖必须同生共死。

        🔴 2026-10-23 实案：`serializer.save()` 在 autocommit 下已提交，紧接着
        `add_reward()` 抛异常 ⇒ 小确幸记录进了库、奖励池没加、前端只看到「操作失败」，
        用户重试还会再留一条（s_id 77/78 就是这么来的）。
        包一层 atomic：失败则整体回滚，宁可什么都没写，也别写一半。
        """
        level = serializer.validated_data['level_of_happiness']
        time = serializer.validated_data['time']
        frontend_reward = serializer.validated_data.get('reward_amount')
        # 前端明确传了 reward_amount 则优先使用，否则默认 = 快乐程度
        reward_amount = frontend_reward if frontend_reward is not None and frontend_reward > 0 else level
        record = serializer.save(
            reward_amount=reward_amount,
            reward_synced=True,
            years=time.year,
            month=time.month,
        )
        # 同步奖励池
        from apps.reward.services import RewardPoolService
        RewardPoolService().add_reward(
            source_id=record.s_id,
            source_type='sugar',
            # 用**落库后**的 `record.reward_amount`（已是 Decimal），不用原始入参：
            # 入参类型由 serializer 决定，改一次字段类型就会牵动这里（类型不该跨层传）。
            amount=record.reward_amount,
            transaction_type='sugar_create',
            # 🔴 文案必须说**实际入账**的金额，不是 `level`（快乐程度分）。
            #    2026-10-26 实案：收件箱完成弹窗按「3 星 × 4」送 12 分给程度、
            #    金额另填 5 —— 这里写 `level` ⇒ 流水上写「获得 12.0 元奖励」，
            #    右侧却是 `+¥5.00`，两个数字同屏且都像真的。
            description=f'新增小确幸：{record.title}，获得{record.reward_amount}元奖励',
        )

    def perform_update(self, serializer):
        instance = self.get_object()
        old_amount = instance.reward_amount or 0
        old_level = instance.level_of_happiness
        new_level = serializer.validated_data.get('level_of_happiness', old_level)
        frontend_reward = serializer.validated_data.get('reward_amount')

        # 🔴 三级判断，顺序不能换（2026-10-26）：
        #   1. 前端显式传了 >0 的金额 ⇒ 听前端的（与 perform_create 同一优先级）；
        #   2. 否则**程度真的变了**才按现行口径「金额 = 分数」重算；
        #   3. 程度没变 ⇒ **金额原地不动**。
        # 为什么必须有第 3 级：历史记录里「程度 12 / 金额 5」是真实填过的，
        # 若照旧一律取 `level_of_happiness`，用户只改个标题（PUT 会带上 level）
        # 就会把金额从 5 改成 12，还顺手记一笔 +7 的调整流水 —— 等于**悄悄改写账本**。
        if frontend_reward is not None and frontend_reward > 0:
            new_amount = frontend_reward
        elif new_level != old_level:
            new_amount = new_level
        else:
            new_amount = old_amount

        from django.db import transaction
        with transaction.atomic():
            serializer.save(reward_amount=new_amount)

            if old_amount != new_amount:
                from apps.reward.models import RewardPool, RewardTransaction

                pool = RewardPool.objects.select_for_update().first()
                if pool:
                    delta = new_amount - old_amount
                    pool.balance += delta
                    if delta > 0:
                        pool.total_earned += delta
                    pool.save()

                    RewardTransaction.objects.create(
                        source_id=instance.s_id,
                        source_type='sugar',
                        amount=delta,
                        transaction_type='sugar_update',
                        balance_before=pool.balance - delta,
                        balance_after=pool.balance,
                        description=f'小确幸快乐程度变化：{instance.title}，奖励 {old_amount}→{new_amount}',
                    )

        if 'time' in serializer.validated_data:
            new_time = serializer.validated_data['time']
            if new_time:
                instance.years = new_time.year
                instance.month = new_time.month
                instance.save(update_fields=['years', 'month'])

    def perform_destroy(self, instance):
        service = SugarRecordService()
        service.delete(s_id=instance.s_id)

    @action(detail=False, methods=['get'])
    def happiness_bands(self, request):
        """快乐程度档位表 —— 前端录入预览用的唯一来源（前端零副本）。

        `reward_label` / `reward_color` 是本表按行算出来的结果下发；
        这里是整张表本身，供「还没保存、正在拖滑块」时使用 ——
        两个出口同源，所以不会出现「弹窗说非常开心、列表说很高兴」。
        """
        return Response({
            'min': SUGAR_HAPPINESS_MIN,
            'max': SUGAR_HAPPINESS_MAX,
            'bands': [
                {
                    'max_level': band['max_level'],
                    'label': band['label'],
                    'color': band['color'],
                }
                for band in SUGAR_HAPPINESS_BANDS
            ],
        })

    @action(detail=False, methods=['get'])
    def joy_type_stats(self, request):
        """获取快乐类型分布统计"""
        # 未标注的不进分布图 —— 图的横轴是「类型的构成」，空值不是一种类型。
        # 但注意：它并没有消失，在 `joy_types` 接口里以「未标注 N 条」出现。
        qs = _apply_record_scope(
            SugarRecord.objects.exclude(joy_type=''), request.query_params,
        )
        stats = (
            qs.values('joy_type')
            .annotate(
                count=Count('s_id'),
                total_happiness=Sum('level_of_happiness'),
                avg_happiness=Avg('level_of_happiness'),
            )
            .order_by('-count')
        )

        total = sum(s['count'] for s in stats)
        result = []
        for s in stats:
            result.append({
                'joy_type': s['joy_type'],
                'count': s['count'],
                'percentage': round(s['count'] / total * 100, 1) if total else 0,
                'total_happiness': float(s['total_happiness'] or 0),
                'avg_happiness': round(float(s['avg_happiness'] or 0), 1),
            })

        return Response({'joy_types': result, 'total': total})

    @action(detail=False, methods=['get'])
    def joy_types(self, request):
        """快乐类型筛选项 —— 列表页下拉框的唯一来源。

        三类选项必须拼在一起，缺任何一类都会「静默漏数」：

        1. 模型 `choices` 的 5 个标准型 —— **即便本期 0 条也列出**。
           否则会出现「录入弹窗里能选联结型、筛选下拉里却没有联结型」，
           只因为库里恰好一条都没有（2026-11-08 实况：联结型 0 条）。
        2. 库里出现、但不在 `choices` 里的值（早期词表残留：社交/其他/创造）。
           下拉里没有它们 ⇒ 这几条记录永远筛不出来、也没法找出来清理。
        3. 「未标注」（`joy_type=''`）—— 空串不是一种类型，但必须能单独筛出来，
           否则那 36 条补标时只能一页页翻。

        `count` 只按 year/month/category 统计，**不含 `joy_type` 自身**：
        选了某个类型之后，别的类型还得显示各自有多少条；若把自己也算进去，
        选完就只剩被选中那一项有数字，等于把「换一个类型看看」的路堵死。
        """
        params = self.request.query_params
        scope = params.copy()
        scope.pop('joy_type', None)
        counts = {
            row[0]: row[1]
            for row in _apply_record_scope(
                SugarRecord.objects, scope,
            ).values_list('joy_type').annotate(n=Count('s_id'))
        }

        choices = SugarRecord._meta.get_field('joy_type').choices
        standard = [(value, label) for value, label in choices if value]
        options = [
            {'value': value, 'label': label, 'count': counts.get(value, 0), 'kind': 'standard'}
            for value, label in standard
        ]

        # 选项集合取**全库**，不随当前筛选变化 —— 若按当期取，某个值的最后一条
        # 记录落在别的月份时，选项会忽隐忽现（下拉框自己会变，比缺选项更难察觉）。
        known = {value for value, _ in standard}
        legacy = set(SugarRecord.objects.values_list('joy_type', flat=True).distinct())
        for value in sorted(legacy - known - {''}, key=lambda v: (-counts.get(v, 0), v)):
            options.append({
                'value': value,
                'label': f'{value}{JOY_TYPE_LEGACY_SUFFIX}',
                'count': counts.get(value, 0),
                'kind': 'legacy',
            })

        options.append({
            'value': JOY_TYPE_UNLABELED_PARAM,
            'label': JOY_TYPE_UNLABELED_LABEL,
            # 列出 NULL 只是为了跟 `_apply_record_scope` 的判据对齐；该列 NOT NULL，正常为 0
            'count': counts.get('', 0) + counts.get(None, 0),
            'kind': 'unlabeled',
        })
        return Response({'unlabeled_value': JOY_TYPE_UNLABELED_PARAM, 'options': options})

    @action(detail=False, methods=['get'])
    def tags(self, request):
        """标签筛选项 —— 列表页标签下拉框的唯一来源。

        `tags` 是逗号分隔字符串，没有独立的标签表，所以「有哪些标签」只能从数据里
        现算。三类都要出现，缺任何一类都会让用户「看得见、筛不到」：

        1. 库里出现过的每一个标签项 —— 包括只在旧记录里出现过的自定义标签
           （你手打的「内在成就」这类不在预设里的词）。
        2. 「无标签」哨兵 —— 库里现在 30/74 条没打标签（NULL）。不给这个选项，
           那批记录既不能通过标签筛到，也没法与「清空筛选」区分开。
        3. 条数为 0 的标签**仍然保留**（选项集合取全库）：某个标签的最后一条记录
           落在别的月份时，选项不该忽隐忽现 —— 下拉框自己会变比缺选项更难察觉。

        `count` 只按 year/month/category/joy_type 统计，**不含 `tag` 自身**：
        选了「成就」之后再拿它去统计，别的标签会全部变成 0，等于堵死换一个看看的路。
        """
        params = self.request.query_params
        scope = params.copy()
        scope.pop(TAG_PARAM, None)

        counts: dict[str, int] = {}
        for raw in _apply_record_scope(SugarRecord.objects, scope).values_list('tags', flat=True):
            # `set()` 是口径不是优化：一条记录上同一个标签写两遍也只算一条。
            for tag in set(_split_tags(raw)):
                counts[tag] = counts.get(tag, 0) + 1

        # 选项集合取全库（不随当期筛选增减），与 `joy_types` 同一判据
        known: set[str] = set()
        for raw in SugarRecord.objects.values_list('tags', flat=True):
            known.update(_split_tags(raw))

        options = [
            {'value': tag, 'label': tag, 'count': counts.get(tag, 0), 'kind': 'tag'}
            for tag in sorted(known, key=lambda t: (-counts.get(t, 0), t))
        ]
        options.append({
            'value': TAG_UNTAGGED_PARAM,
            'label': TAG_UNTAGGED_LABEL,
            'count': _apply_record_scope(SugarRecord.objects, scope).filter(
                Q(tags__isnull=True) | Q(tags=''),
            ).count(),
            'kind': 'untagged',
        })
        return Response({'untagged_value': TAG_UNTAGGED_PARAM, 'options': options})

    @action(detail=False, methods=['get'])
    def categories(self, request):
        """获取分类统计及整体汇总"""
        # 与列表同一套筛选（含 joy_type）—— 顶部「累计获得 / 平均快乐」必须
        # 跟下面列出来的那几条是同一批记录，否则筛选后两个数会互相打脸。
        qs = _apply_record_scope(SugarRecord.objects, request.query_params)

        stats = (
            qs.values('category')
            .annotate(
                count=Count('s_id'),
                total_reward=Sum('reward_amount'),
            )
            .order_by('-count')
        )
        for s in stats:
            s['category'] = s['category'] or 'other'
            s['total_reward'] = float(s['total_reward'] or 0)

        overall = qs.aggregate(
            total_count=Count('s_id'),
            total_reward=Sum('reward_amount'),
            avg_happiness=Avg('level_of_happiness'),
        )

        serializer = SugarCategoryStatsSerializer(stats, many=True)
        return Response({
            'categories': serializer.data,
            'summary': {
                'total_count': overall['total_count'] or 0,
                'total_reward': float(overall['total_reward'] or 0),
                'avg_happiness': round(float(overall['avg_happiness'] or 0), 1),
            },
        })


class SugarTemplateViewSet(viewsets.ModelViewSet):
    """小确幸模板 CRUD"""

    queryset = SugarTemplate.objects.filter(is_active=True)
    serializer_class = SugarTemplateSerializer
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
        serializer.save(user_id=1)

