"""生存资源盘点 · 视图

视图只做协议转换：校验入参、调服务层、把服务层的异常转成 400 / 404。
**一个除法都不在这里做** —— 口径真源在 `services/survival_calc.py`，
分散到视图层就会出现「两个地方各判一次」，而且不一致是静默的。

四个列表端点全部显式 `pagination_class = None`：被 DRF 全局分页包成
`{count, results}` 时，前端按数组消费会**静默显示为空**（项目硬坑③）。
"""

from datetime import date, datetime

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import (
    SurvivalCategory,
    SurvivalCombo,
    SurvivalEssential,
    SurvivalItem,
    SurvivalRecipe,
    SurvivalSnapshot,
    SurvivalStocktake,
    SurvivalUnit,
)
# ⚠️ 直接导入模块而不是 `from ..services import list_snapshots`：
# 那个名字已被 asset_service（资产快照）占用，走包级导出容易拿到别人家的函数。
from ..services.survival_snapshot import (
    delete_snapshot as delete_survival_snapshot,
    get_snapshot as get_survival_snapshot,
    get_trend as get_survival_trend,
    list_snapshots as list_survival_snapshots,
    take_snapshot as take_survival_snapshot,
)
# 实盘盘点（v3.59.3）—— 与快照是**两件事**：快照存系统算出的结论，
# 盘点存人填进去的实盘。同样直接导入模块：模块内这五个名字不重名，
# 但包级导出要经过扁平的 `services/__init__`，那里的名字将来可能被占掉。
from ..services.survival_stocktake import (
    create_stocktake,
    delete_stocktake,
    get_stocktake,
    get_worksheet,
    list_stocktakes,
)
# 必需品基准清单（v3.59.7）—— 回答「我漏了什么」，与前两件都不同：
#   快照存「系统算出的结论」、盘点存「人填的实盘」，对账存「该有什么」这把尺子。
# 同样直接导入模块：`get_reconcile` 这种通用词经扁平命名空间中转时早晚被占掉。
from ..services.survival_essential_service import (
    create_essential,
    delete_essential,
    get_essential_list,
    get_reconcile as get_essential_reconcile,
    seed_essentials as seed_survival_essentials,
    update_essential,
)
# 组合（v3.59.13）—— 「分开登记、一起下锅」。同样直接导入模块：
# `get_combo_list` 这种通用词经扁平命名空间中转时早晚被别人占掉。
from ..services.survival_combo_service import (
    create_combo,
    delete_combo,
    get_combo_list,
    update_combo,
)
# 库存流水（v3.60.18 · P0）—— 库存**怎么变的**。
# ⚠️ 它同时是**改库存的唯一写口**（`record_flow`）：本模块不直接写 quantity，
#    别的模块也不许 —— 绕过它就等于造出一次「账变了但没记录」。
from ..services.survival_flow import (
    list_flows,
    record_batch,
    record_flow,
    reverse_flow,
    summarize_flows,
)
from ..serializers import (
    SurvivalAnalysisSerializer,
    SurvivalCategoryFormSerializer,
    SurvivalCategorySerializer,
    SurvivalComboFormSerializer,
    SurvivalComboSerializer,
    SurvivalEssentialFormSerializer,
    SurvivalEssentialReconcileSerializer,
    SurvivalEssentialSeedResultSerializer,
    SurvivalEssentialSerializer,
    SurvivalFlowBatchWriteSerializer,
    SurvivalFlowSerializer,
    SurvivalFlowSummarySerializer,
    SurvivalFlowWriteSerializer,
    SurvivalItemFormSerializer,
    SurvivalItemPreviewSerializer,
    SurvivalItemSerializer,
    SurvivalMetaSerializer,
    SurvivalMetricMetaSerializer,
    SurvivalRecipeFormSerializer,
    SurvivalRecipeSerializer,
    SurvivalSeedResultSerializer,
    SurvivalSnapshotCreateSerializer,
    SurvivalSnapshotSerializer,
    SurvivalStocktakeCreateSerializer,
    SurvivalStocktakeSerializer,
    SurvivalTrendSerializer,
    SurvivalWorksheetRowSerializer,
    SurvivalUnitFormSerializer,
    SurvivalUnitSerializer,
)
from ..services import survival_service as svc


def _parse_date(raw: str | None) -> date | None:
    """解析 ?date=YYYY-MM-DD —— 解析不了就当没传，而不是报错

    「参考日期」是个可选的视角切换参数，写错格式时回落到今天
    比甩一个 400 更符合使用直觉。
    """
    if not raw:
        return None
    try:
        return datetime.strptime(raw[:10], '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


class SurvivalCategoryViewSet(viewsets.ModelViewSet):
    """物资类别：CRUD + 初始化默认类别"""

    queryset = SurvivalCategory.objects.all()
    serializer_class = SurvivalCategoryFormSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        return SurvivalCategory.objects.filter(user_id=1)

    def list(self, request, *args, **kwargs):
        include_units = str(request.query_params.get('include_units', '')).lower() in (
            '1', 'true', 'yes',
        )
        rows = svc.get_category_list(include_units=include_units)
        return Response(SurvivalCategorySerializer(rows, many=True).data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = svc.create_category(dict(serializer.validated_data))
        return Response(SurvivalCategorySerializer(row).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=kwargs.pop('partial', False),
        )
        serializer.is_valid(raise_exception=True)
        row = svc.update_category(instance.id, dict(serializer.validated_data))
        return Response(SurvivalCategorySerializer(row).data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            pk = svc.delete_category(instance.id)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'deleted': pk})

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        row = next(
            (r for r in svc.get_category_list(include_units=True) if r['id'] == instance.id),
            None,
        )
        return Response(SurvivalCategorySerializer(row).data)

    @action(detail=False, methods=['post'])
    def seed(self, request):
        """初始化默认类别与单位（幂等，不预设任何物品与库存）"""
        overwrite = str(request.data.get('overwrite', '')).lower() in ('1', 'true', 'yes')
        result = svc.seed_survival_defaults(overwrite=overwrite)
        return Response(SurvivalSeedResultSerializer(result).data)


class SurvivalUnitViewSet(viewsets.ModelViewSet):
    """消耗单位：CRUD"""

    queryset = SurvivalUnit.objects.all()
    serializer_class = SurvivalUnitFormSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        return SurvivalUnit.objects.filter(user_id=1)

    def list(self, request, *args, **kwargs):
        raw = request.query_params.get('category_id')
        category_id = int(raw) if raw and str(raw).isdigit() else None
        return Response(SurvivalUnitSerializer(svc.get_unit_list(category_id), many=True).data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = svc.create_unit(dict(serializer.validated_data))
        return Response(SurvivalUnitSerializer(row).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=kwargs.pop('partial', False),
        )
        serializer.is_valid(raise_exception=True)
        row = svc.update_unit(instance.id, dict(serializer.validated_data))
        return Response(SurvivalUnitSerializer(row).data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            pk = svc.delete_unit(instance.id)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'deleted': pk})


class SurvivalItemViewSet(viewsets.ModelViewSet):
    """物资物品：CRUD"""

    queryset = SurvivalItem.objects.all()
    serializer_class = SurvivalItemFormSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        return SurvivalItem.objects.filter(user_id=1)

    def list(self, request, *args, **kwargs):
        raw = request.query_params.get('category_id')
        category_id = int(raw) if raw and str(raw).isdigit() else None
        rows = svc.get_item_list(
            category_id=category_id,
            satiety=request.query_params.get('satiety') or None,
            status=request.query_params.get('status') or None,
        )
        return Response(SurvivalItemSerializer(rows, many=True).data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        row = svc.create_item(dict(serializer.validated_data))
        return Response(SurvivalItemSerializer(row).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='preview')
    def preview(self, request, *args, **kwargs):
        """保存前试算（v3.59.11）—— 与 `create` 同一套校验，但**不写库**

        🔴 校验刻意复用**同一个**表单序列化器：试算的放行条件与保存的必须一模一样，
           否则会出现「试算给出 150 天、一按保存报 400」这种事 ——
           那比没有试算更误导，因为它先把人哄住了。

           它放在 `items` 下面而不是另开一个路径：试算与保存是同一件事的
           前半步与后半步，分开放会让人以为它算的是别的东西。
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            row = svc.preview_item_life(dict(serializer.validated_data))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SurvivalItemPreviewSerializer(row).data)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=kwargs.pop('partial', False),
        )
        serializer.is_valid(raise_exception=True)
        row = svc.update_item(instance.id, dict(serializer.validated_data))
        return Response(SurvivalItemSerializer(row).data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            pk = svc.delete_item(instance.id)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'deleted': pk})


class SurvivalEssentialViewSet(viewsets.ModelViewSet):
    """必需品基准清单：CRUD + 缺口对账 + 初始化

    ⚠️ 与物品、快照、实盘盘点是**四件不同的事**，端点刻意分开：

        基准项（本端点）= 一个人生活**本该**有什么（用户视角，可增删改，无数量）
        物品            = 我**实际**有多少（库存事实）
        快照            = 系统**算出来的结论**（不需要人动手）
        实盘盘点        = 人**填进去的实盘**（必须人动手）

    合并任意两个都会让「我核对过」「系统算过」「我本该有」这三件事互相冒充 ——
    而它们要采取的行动完全不同。

    列表端点显式 `pagination_class = None`：被 DRF 全局分页包成 `{count, results}`
    时，前端按数组消费会**静默显示为空**（项目硬坑③）。
    """

    queryset = SurvivalEssential.objects.all()
    serializer_class = SurvivalEssentialFormSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        return SurvivalEssential.objects.filter(user_id=1)

    def list(self, request, *args, **kwargs):
        raw = request.query_params.get('category_id')
        category_id = int(raw) if raw and str(raw).isdigit() else None
        # 默认按**紧迫度**排（该先处理的在前）；管理界面要看录入顺序时传 sort=order。
        sort_by_urgency = (request.query_params.get('sort') or 'urgency') != 'order'
        rows = get_essential_list(
            category_id=category_id,
            scope=request.query_params.get('scope') or None,
            sort_by_urgency=sort_by_urgency,
        )
        return Response(SurvivalEssentialSerializer(rows, many=True).data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            row = create_essential(dict(serializer.validated_data))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            SurvivalEssentialSerializer(row).data, status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=kwargs.pop('partial', False),
        )
        serializer.is_valid(raise_exception=True)
        try:
            row = update_essential(instance.id, dict(serializer.validated_data))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SurvivalEssentialSerializer(row).data)

    def destroy(self, request, *args, **kwargs):
        """删除一件基准项 —— 只影响这把尺子，不碰任何库存

        与 `delete_item` 刻意不同：那边要求先解除配方引用，因为删物品会动到
        计算的分母；这边删的是一条认知，关联物品是用户的资产，不该跟着消失。
        """
        instance = self.get_object()
        pk = delete_essential(instance.id)
        return Response({'deleted': pk})

    @action(detail=False, methods=['get'])
    def reconcile(self, request):
        """缺口对账的汇总与最短的一件（明细走列表端点，不在这里重复下发）"""
        return Response(
            SurvivalEssentialReconcileSerializer(get_essential_reconcile()).data,
        )

    @action(detail=False, methods=['post'])
    def seed(self, request):
        """写入必需品基准清单（幂等，**不预设任何库存数量**）"""
        overwrite = str(request.data.get('overwrite', '')).lower() in ('1', 'true', 'yes')
        result = seed_survival_essentials(overwrite=overwrite)
        return Response(SurvivalEssentialSeedResultSerializer(result).data)


class SurvivalRecipeViewSet(viewsets.ModelViewSet):
    """配餐配方：CRUD（配方行整体替换）"""

    queryset = SurvivalRecipe.objects.all()
    serializer_class = SurvivalRecipeFormSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        return SurvivalRecipe.objects.filter(user_id=1)

    def list(self, request, *args, **kwargs):
        raw = request.query_params.get('category_id')
        category_id = int(raw) if raw and str(raw).isdigit() else None
        with_lines = str(request.query_params.get('with_lines', '1')).lower() not in (
            '0', 'false', 'no',
        )
        rows = svc.get_recipe_list(category_id=category_id, with_lines=with_lines)
        return Response(SurvivalRecipeSerializer(rows, many=True).data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            row = svc.create_recipe(_payload(serializer.validated_data))
        except ValueError as exc:
            # 跨类别组合那类问题：序列化器已经挡了一层，这里是服务层的第二道
            # （脚本 / 别的调用方绕过 HTTP 时只剩它）。转 400，别让它变 500。
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SurvivalRecipeSerializer(row).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=kwargs.pop('partial', False),
        )
        serializer.is_valid(raise_exception=True)
        try:
            row = svc.update_recipe(instance.id, _payload(serializer.validated_data))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SurvivalRecipeSerializer(row).data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        pk = svc.delete_recipe(instance.id)
        return Response({'deleted': pk})


class SurvivalComboViewSet(viewsets.ModelViewSet):
    """组合：把几件物品声明成「一起用」（v3.59.13）

    ⚠️ 与「基准项挂多件」不是一回事，端点也因此分开：

        基准项挂多件 = 一把**尺子**上的一项（「我本该有牙膏」），问「缺了什么」
        组合         = 一份**可复用的搭配**（「杂粮粥 = 燕麦米+绿豆+薏仁+紫米」），
                       带每件用量，供**配方**引用，问「这一顿还能吃几顿」

    两者组内口径同源（并列缺一不可 → 取最小），但生命周期与用途都不同，
    合并会让「没录入」与「没配够」互相冒充。

    列表端点显式 `pagination_class = None`：被全局分页包成 `{count, results}`
    时前端按数组消费会**静默显示为空**（项目硬坑③）。
    """

    queryset = SurvivalCombo.objects.all()
    serializer_class = SurvivalComboFormSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        return SurvivalCombo.objects.filter(user_id=1)

    def list(self, request, *args, **kwargs):
        raw = request.query_params.get('category_id')
        category_id = int(raw) if raw and str(raw).isdigit() else None
        rows = get_combo_list(category_id=category_id)
        return Response(SurvivalComboSerializer(rows, many=True).data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            row = create_combo(_payload(serializer.validated_data))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SurvivalComboSerializer(row).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=kwargs.pop('partial', False),
        )
        serializer.is_valid(raise_exception=True)
        try:
            row = update_combo(instance.id, _payload(serializer.validated_data))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SurvivalComboSerializer(row).data)

    def destroy(self, request, *args, **kwargs):
        """删除组合 —— 被配方引用时拒绝（先摘引用），不级联

        与「删基准项」刻意不同：那边删的是一条认知、不碰任何分母；
        这边删的是一行的**计量来源**，删了那道菜就算不出来或算得更耐吃。
        """
        instance = self.get_object()
        try:
            pk = delete_combo(instance.id)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'deleted': pk})


def _payload(validated: dict) -> dict:
    """把 validated_data 转成服务层要的纯 dict（配方行 / 组合行保持原样）

    ⚠️ 两条行**各自判断「在不在」**：只传食材行时不带 `combo_lines` 这个键，
       服务层才会「这次不动组合行」。统一填成 [] 会让「懒得传」
       变成「静默清空组合」（`update_recipe` 的注释里写着这条判据）。
    """
    data = dict(validated)
    for key in ('lines', 'combo_lines', 'members'):
        if key in data and data[key] is not None:
            data[key] = [dict(row) for row in data[key]]
    return data


class SurvivalAnalysisView(APIView):
    """GET /survival/analysis/?date=YYYY-MM-DD —— 首屏一次取全

    只读、实时算、无主键：挂成 ModelViewSet 会误导人以为结果可以「保存」。
    """

    permission_classes = [AllowAny]

    def get(self, request):
        return Response(
            SurvivalAnalysisSerializer(svc.get_analysis(_parse_date(request.query_params.get('date')))).data,
        )


class SurvivalMetaView(APIView):
    """GET /survival/meta/ —— 枚举与口径的单一出口

    口径文案只从 `constants.SURVIVAL_METRIC_NOTES` 来；前端据此画气泡提示，
    **不另写一份** —— 两处文案迟早不一致，而且没人会发现。
    """

    permission_classes = [AllowAny]

    def get(self, request):
        return Response(SurvivalMetaSerializer(svc.get_meta()).data)


class SurvivalMetricMetaView(APIView):
    """GET /survival/metrics/meta/ —— 只要口径元信息（裸数组）

    与 `/wealth/ratios/meta/` 一致：裸数组，被全局分页包成
    `{count, results}` 时前端按数组消费会**静默变空**。
    """

    permission_classes = [AllowAny]

    def get(self, request):
        return Response(SurvivalMetricMetaSerializer(svc.get_meta()['metric_meta'], many=True).data)


class SurvivalSnapshotViewSet(viewsets.ModelViewSet):
    """盘点快照：列表 / 盘点（落一份）/ 删除 / 趋势

    ⚠️ **刻意不提供修改**。可编辑的历史等于伪造的历史 ——
       把上个月那个不好看的数改掉，曲线就永远只升不降了。
       要改只能删掉重盘，留下「删过一次」这个动作本身。

    列表端点 `pagination_class = None`：被全局分页包成 `{count, results}`
    时前端按数组消费会静默变空（项目硬坑③）。趋势不在这里分页 ——
    折线的点数由 `limit` 控制，月度数据上分页器只是噪声。
    """

    queryset = SurvivalSnapshot.objects.all()
    serializer_class = SurvivalSnapshotSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        return SurvivalSnapshot.objects.filter(user_id=1)

    def list(self, request, *args, **kwargs):
        """历史列表 —— **最近的在前**（表格用）"""
        rows = list_survival_snapshots(request.query_params.get('limit'))
        return Response(SurvivalSnapshotSerializer(rows, many=True).data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        return Response(SurvivalSnapshotSerializer(get_survival_snapshot(instance.id)).data)

    def create(self, request, *args, **kwargs):
        """盘点：把此刻算出来的结论落成一份快照

        同一天重复盘点**默认拒绝**（400 + 可照做的提示）；
        `overwrite=true` 才是显式的「我知道，替换掉它」。
        """
        serializer = SurvivalSnapshotCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            row = take_survival_snapshot(
                snapshot_date=data.get('date'),
                note=data.get('note') or '',
                overwrite=bool(data.get('overwrite')),
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except SurvivalSnapshot.DoesNotExist:
            return Response({'detail': '快照不存在'}, status=status.HTTP_404_NOT_FOUND)
        return Response(SurvivalSnapshotSerializer(row).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        pk = delete_survival_snapshot(instance.id)
        return Response({'deleted': pk})

    def update(self, request, *args, **kwargs):
        return Response(
            {'detail': '盘点快照不可修改 —— 历史一旦可编辑就不再是历史。如需重盘，请删掉这一期再盘一次。'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    @action(detail=False, methods=['get'])
    def trend(self, request):
        """趋势序列（按日期升序）+ 与上一期的对比

        `comparison.comparable=False` 时界面必须显示 `reason`：
        两次之间改过类别或消耗模式的话，天数的差里混着「换了算法」这一项，
        照常显示差值等于把配置变更说成了物资变化。
        """
        return Response(
            SurvivalTrendSerializer(get_survival_trend(request.query_params.get('limit'))).data,
        )


def _parse_int_list(raw) -> list[int] | None:
    """把 `1,2,3` 解析成 [1, 2, 3]

    ⚠️ 解析不出东西时返回 **None 而不是空列表**：空列表会被服务层理解为
       「一件都不选」，于是返回空清单 —— 用户看到的是「表里什么都没有」，
       而真实原因是参数写错了。这两种情况必须分开，否则错误会被伪装成空数据。
    """
    if not raw:
        return None
    out: list[int] = []
    for piece in str(raw).split(','):
        piece = piece.strip()
        if not piece:
            continue
        try:
            out.append(int(piece))
        except ValueError:
            continue
    return out or None


class SurvivalStocktakeViewSet(viewsets.ModelViewSet):
    """实盘盘点：工作表 / 提交 / 历史 / 删除

    与 `SurvivalSnapshotViewSet` 并列但**不是一回事**，不要合并：
        快照 = 系统算出来的结论（我以为能撑多久），点一下就落一份；
        盘点 = 人填进去的实盘（实际还剩多少件），得一件件数出来。

    ⚠️ **刻意不提供修改**，理由与快照相同：可编辑的盘点记录等于伪造的核对结果。
       要更正只能删掉重盘 —— 并留下「删过一次」这个动作本身。

    ⚠️ 删除**不回滚库存**（服务层铁律三）：库存是已经被核实过的事实，
       删记录只是删掉凭据。若删一条历史能把库存改回去，「删记录」就成了
       一个能改现状的按钮 —— 而它在界面上看起来只影响历史。
    """

    queryset = SurvivalStocktake.objects.all()
    serializer_class = SurvivalStocktakeSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        return SurvivalStocktake.objects.filter(user_id=1)

    def list(self, request, *args, **kwargs):
        """盘点历史 —— **最近一次在最上面**（表格用）"""
        rows = list_stocktakes(request.query_params.get('limit'))
        return Response(SurvivalStocktakeSerializer(rows, many=True).data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            row = get_stocktake(instance.id)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response(SurvivalStocktakeSerializer(row).data)

    def create(self, request, *args, **kwargs):
        """提交一次实盘盘点

        请求体里**不需要**（也不接受）账面数量：服务端在提交那一刻重新读。
        这不是防篡改，是防一个必然发生的过期读 —— 盘点页可能开着很久。
        """
        serializer = SurvivalStocktakeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            row = create_stocktake(
                stocktake_date=data.get('date'),
                note=data.get('note') or '',
                lines=[dict(line) for line in data['lines']],
                source=data.get('source') or 'manual',
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SurvivalStocktakeSerializer(row).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            pk = delete_stocktake(instance.id)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response({'deleted': pk})

    def update(self, request, *args, **kwargs):
        return Response(
            {'detail': '盘点记录不可修改 —— 可编辑的核对结果等于伪造的核对结果。如需更正，请删掉这一条重新盘一次。'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def partial_update(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    @action(detail=False, methods=['get'])
    def worksheet(self, request):
        """盘点工作表：要盘哪些物品、系统记的是多少、上次盘是什么时候

        三个参数都可选、可组合：`category_id` 按类别圈定、
        `item_ids` 指定几件（逗号分隔）、`keyword` 按名称搜。
        """
        raw_category = request.query_params.get('category_id')
        try:
            category_id = int(raw_category) if raw_category else None
        except (TypeError, ValueError):
            category_id = None
        rows = get_worksheet(
            category_id=category_id,
            item_ids=_parse_int_list(request.query_params.get('item_ids')),
            keyword=(request.query_params.get('keyword') or '').strip() or None,
        )
        return Response(SurvivalWorksheetRowSerializer(rows, many=True).data)


class SurvivalFlowViewSet(viewsets.ViewSet):
    """库存流水：列表 / 记一笔 / 撤销 / 按月汇总（v3.60.18 · P0）

    🔴 **登记入口在物品上、查看入口在这里** —— 两个地方，别混。
       本端点（生存资源页第 5 个页签）**刻意不放登记按钮**：那会把「查流水」
       变成「又要先选一次物品」，而用户想「我吃了一罐」时，眼睛盯的是那件物品。

    ⚠️ 列表**返回裸数组**：ViewSet 不走 `pagination_class`，「最近 N 条」
       由服务层的 `limit` 控制 —— 绕回分页会把数组包成 `{count, results}`，
       前端按数组消费就是「假 0」。
    """

    permission_classes = [AllowAny]

    def list(self, request):
        raw_limit = request.query_params.get('limit')
        raw_item = request.query_params.get('item_id')
        try:
            limit = int(raw_limit) if raw_limit else None
        except (TypeError, ValueError):
            limit = None
        try:
            item_id = int(raw_item) if raw_item else None
        except (TypeError, ValueError):
            item_id = None

        rows = list_flows(
            item_id=item_id,
            category_name=(request.query_params.get('category_name') or '').strip() or None,
            channel=(request.query_params.get('channel') or '').strip() or None,
            reason=(request.query_params.get('reason') or '').strip() or None,
            date_from=_parse_date(request.query_params.get('date_from')),
            date_to=_parse_date(request.query_params.get('date_to')),
            keyword=(request.query_params.get('keyword') or '').strip() or None,
            limit=limit,
        )
        return Response(SurvivalFlowSerializer(rows, many=True).data)

    def create(self, request):
        """记一笔；请求体里带 `rows` 时按**批量**处理。

        🔴 批量的时间与原因是**整批一个** —— 绝不把单件表单复制 N 份。
        """
        if isinstance(request.data, dict) and 'rows' in request.data:
            batch = SurvivalFlowBatchWriteSerializer(data=request.data)
            batch.is_valid(raise_exception=True)
            data = batch.validated_data
            rows = [dict(r) for r in data['rows']]
            batch_at = data.get('occurred_at')
            if batch_at is not None:
                for row in rows:
                    row['occurred_at'] = batch_at
            try:
                out = record_batch(rows)
            except ValueError as exc:
                return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
            return Response(
                SurvivalFlowSerializer(out, many=True).data, status=status.HTTP_201_CREATED,
            )

        serializer = SurvivalFlowWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        try:
            row = record_flow(
                item_id=data['item_id'],
                delta=data['delta'],
                channel=data.get('channel') or 'manual',
                reason=data.get('reason') or '',
                note=data.get('note') or '',
                occurred_at=data.get('occurred_at'),
            )
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SurvivalFlowSerializer(row).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def reverse(self, request, pk=None):
        """撤销 = 补一条反向流水（**不做物理删除**，历史全留）"""
        try:
            row = reverse_flow(int(pk))
        except (ValueError, TypeError) as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SurvivalFlowSerializer(row).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """按月汇总 —— 回答「这个月吃掉多少」

        ⚠️ 这是**静态段**：DRF 把 `detail=False` 的 action 路由排在 `{pk}/`
           之前，不会像手写 `path()` 那样被主键抢掉（配一条用例钉住，
           因为「被抢」的症状是 404，看起来像路由没注册）。
        """
        try:
            row = summarize_flows(month=(request.query_params.get('month') or '').strip() or None)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(SurvivalFlowSummarySerializer(row).data)
