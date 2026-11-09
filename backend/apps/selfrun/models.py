"""自我运转 · 数据模型（**7 张 managed 表**）

> 走 `sycamore-managed-table-feature` 流水线。设计依据：`docs/自我运转-功能设计-v0.3-20261013.md` §7。
> ⚠️ **新增 managed 表 ⇒ `backend/conftest.py` 必须同步补镜像 DDL**（`--reuse-db` 下
> Django 跳过建库 ⇒ 新表不出，报错长相是「列不存在」，看着像代码错）。

🔴 建表三条铁律（本项目踩实过的）：
1. **派生值一律不落库** —— `Stage` 不缓存「已进行 N 天」；`Metric` 不缓存任何读数。
   全稿唯一允许落库的派生值是**快照**（`Period.readings` / `Stage.summary_snapshot`），
   判据是「**以后重算得出同样结果吗？**」——不能 ⇒ 才落。
   ⚠️ **目标值不在此列** —— 它是**输入**不是派生，所以必须落库
   （`Metric.goal_value` 是阶段默认，`MetricPlan` 是按期的设定）。
2. **FK 一律 `PROTECT`**（禁级联删除）—— 删一条 KPI 定义若连带删掉历史读数，
   等于让往期复盘凭空变化。
   ⚠️ **模板刻意不用 FK**：`Metric.template_key` 只是字符标记 ⇒ **删模板不影响已建阶段**。
3. **`SelfRunPeriod.status` 空串 = 未归档** —— 与 `closed_at IS NULL` 同义，
   但显式留一列是为了让「归档那刻的判定」**定格**（重算不出来，故必须落库）。
"""
from django.core.exceptions import ValidationError
from django.db import models

from . import constants as C


class SelfRunTemplate(models.Model):
    """KPI 模板库 —— 「制定配置」页**上区**维护的就是它（可自定义增删改）。

    🔴 与 `SelfRunMetric` 的关系是**拷贝不是引用**（`templates.py` 铁律 1）：
       建阶段时把模板值**抄进** `SelfRunMetric`；此后改模板**不影响已建阶段**
       —— 否则「改模板」会**回溯改写历史口径**，而往期结论是冻结快照。
    🔴 与阶段的关联只是 `SelfRunMetric.template_key` 这个**字符标记**（不是 FK）
       ⇒ **删掉一条模板不会牵连任何已建阶段**（不会触发 `PROTECT` 报 400），
         代价只是那条 KPI 的「来源」失去指向 —— 这是可接受的，因为来源只用于展示。

    ⚠️ 本表由迁移 `0002` 用 `templates.KPI_TEMPLATES` **seed 一次**；
       此后一切增删改只落库。**不要再写成「表空就补」**——
       那会把你删掉的内置模板在下次启动时**悄悄放回来**。
    """

    # 稳定标识：内置 9 条沿用 `templates.py` 的 key；用户自建由后端生成 `custom_<8位>`
    key = models.CharField(max_length=40, unique=True, verbose_name='模板标识')
    name = models.CharField(max_length=100, verbose_name='名称')
    period_type = models.CharField(
        max_length=10, choices=C.PERIOD_TYPE_CHOICES, verbose_name='周期',
    )
    unit = models.CharField(max_length=20, verbose_name='单位')
    direction = models.CharField(
        max_length=10, choices=C.DIRECTION_CHOICES, default='at_least', verbose_name='判定方向',
    )
    # ⚠️ 两个都允许 None：「只有目标没有底线」是合理状态；`None` ≠ 0
    goal_value = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='目标线',
    )
    floor_value = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='底线',
    )
    goal_why = models.CharField(max_length=200, blank=True, default='', verbose_name='目标依据')
    floor_why = models.CharField(max_length=200, blank=True, default='', verbose_name='底线依据')
    agg = models.CharField(max_length=20, choices=C.AGG_CHOICES, verbose_name='聚合方式')
    source_kind = models.CharField(
        max_length=20, choices=C.SOURCE_KIND_CHOICES, verbose_name='取数来源',
    )
    source_config = models.JSONField(default=dict, verbose_name='取数参数')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        managed = True
        db_table = 'selfrun_template'
        db_table_comment = 'KPI 模板库：「制定配置」页上区维护的候选清单；新建阶段时从这里拷进 KPI 定义'
        verbose_name = '自我运转·KPI 模板'
        verbose_name_plural = '自我运转·KPI 模板'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f'{self.name}（{self.period_type}）'



class SelfRunStage(models.Model):
    """阶段 —— 生命周期容器。

    状态机：`draft → active ⇄ paused → closed ──[复制]──> 新 draft`

    🔴 约束（v3.65.0 起分两层）：
    1. **最多两层**：长阶段（`parent IS NULL`）挂小阶段，小阶段不能再挂。
    2. **同一 `parent` 下只允许一个 `active`/`paused`** —— 不是全局唯一
       （否则长阶段一开，小阶段就开不了）。
    3. **KPI 只挂叶子**：长阶段零 `Metric` ⇒ 天然不产生 `SelfRunPeriod`。

    ⚠️ 为什么要 3：`Period` 的唯一键是 `(stage, period_type, period_key)`。
       长阶段若也配 KPI，**同一周会同时属于长阶段和小阶段两个 Period**，
       判定打两遍，而「本周活着 0/5」到底算谁的就说不清了 ——
       又一把「同一事实两把尺子」。所以长阶段只做**账本 + 汇总**。
    """

    name = models.CharField(max_length=100, verbose_name='阶段名称')
    # 🔴 长阶段（parent 为空）只汇总；小阶段才是真正跑 KPI 的那一层。
    #    `PROTECT`：删长阶段不许连带删小阶段（与全模块 FK 纪律一致）。
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.PROTECT,
        related_name='children', verbose_name='上级阶段',
    )
    start_date = models.DateField(verbose_name='起点')
    # 🔴 生效后 `start_date` **不可改**（改它会让已完成周期「掉出」阶段）⇒ 序列化器只读。
    end_date = models.DateField(null=True, blank=True, verbose_name='终点')
    status = models.CharField(
        max_length=10, choices=C.STAGE_STATUS_CHOICES, default='draft', verbose_name='状态',
    )
    # 四种原因同一把尺子（「为什么停下」）—— 不折进 status，否则 paused 变兜底桶。
    pause_reason = models.CharField(
        max_length=20, choices=C.PAUSE_REASON_CHOICES, null=True, blank=True, verbose_name='暂停原因',
    )
    # 字段命名对齐 redemption.RedemptionPeriod 的既有先例（同一套语义，不另创一套）
    paused_since = models.DateField(null=True, blank=True, verbose_name='暂停自')
    resume_at = models.DateField(null=True, blank=True, verbose_name='预计恢复')
    # 心跳：**不判好坏、不改任何 KPI**（V3：不追着你跑）
    last_seen_at = models.DateTimeField(null=True, blank=True, verbose_name='最近回访')
    summary = models.TextField(blank=True, default='', verbose_name='阶段总结')
    # 🔴 冻结「你写这段话时看到的数」—— 将来口径变了重算会不同，
    #    不冻结的话你留下的文字会与旁边的数字对不上，且你不知道是哪个变了。
    summary_snapshot = models.JSONField(null=True, blank=True, verbose_name='总结时的数字')
    summary_at = models.DateTimeField(null=True, blank=True, verbose_name='总结写于')
    note = models.CharField(max_length=200, blank=True, default='', verbose_name='备注')
    # 账本参数（目前只有 `pool_principal`）。**只长阶段用**，小阶段留空 dict。
    # 🔴 刻意不做成 FK、不单开一张表：它是一段配置不是流水
    #    （流水在 `redemption_pool_inject`，一行一笔，那个才需要表）。
    ledger_config = models.JSONField(default=dict, blank=True, verbose_name='账本参数')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        managed = True
        db_table = 'selfrun_stage'
        db_table_comment = '阶段：生命周期容器；每条 KPI 定义都必须挂在某个阶段下'
        verbose_name = '自我运转·阶段'
        verbose_name_plural = '自我运转·阶段'
        ordering = ['-start_date', '-id']

    def __str__(self):
        return f'{self.name}（{self.get_status_display()}）'

    def clean(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError({'end_date': '终点不能早于起点。'})
        # 🔴 两层封顶。⚠️ `clean()` 挡不住 `objects.create()` ——
        #    服务层 `create_stage()` 里必须**再判一次**，两处都判才有意义。
        if self.parent_id and self.parent.parent_id:
            raise ValidationError({'parent': '只支持两层：上级阶段不能再有上级。'})


class SelfRunMetric(models.Model):
    """阶段下的一条 KPI 定义。

    🔴 `metric_id` **必须稳定** —— `Period.readings` 里的 `metric_id` 引用它。
    所以「改目标值」是 **UPDATE 本行 + 写一条 `MetricLog`**，**不新建行**
    （v0.2 用 `is_active` 做版本化会让引用失效，v0.3 已改掉）。
    """

    stage = models.ForeignKey(
        SelfRunStage, on_delete=models.PROTECT, related_name='metrics', verbose_name='阶段',
    )
    # 只记来源，**不参与取数**（模板后来改了不影响已建阶段）
    template_key = models.CharField(max_length=40, blank=True, default='', verbose_name='来源模板')
    name = models.CharField(max_length=100, verbose_name='名称')
    period_type = models.CharField(
        max_length=10, choices=C.PERIOD_TYPE_CHOICES, verbose_name='周期',
    )
    unit = models.CharField(max_length=20, verbose_name='单位')
    direction = models.CharField(
        max_length=10, choices=C.DIRECTION_CHOICES, default='at_least', verbose_name='判定方向',
    )
    # ⚠️ 两个都允许 None：「只有目标没有底线」是合理状态；两条都空 ⇒ unconfigured。
    #    `None` ≠ 0，界面显示「—」。
    goal_value = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='目标线',
    )
    floor_value = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='底线',
    )
    # 「为什么是这个数」—— V2：让你看见尺子（存的是**你设的那一刻**的依据）
    goal_why = models.CharField(max_length=200, blank=True, default='', verbose_name='目标依据')
    floor_why = models.CharField(max_length=200, blank=True, default='', verbose_name='底线依据')
    agg = models.CharField(max_length=20, choices=C.AGG_CHOICES, verbose_name='聚合方式')
    source_kind = models.CharField(
        max_length=20, choices=C.SOURCE_KIND_CHOICES, verbose_name='取数来源',
    )
    # 取数参数（含 `kind` + `where`）—— **不含 `agg`**（那是上面那个列，两处都存就是第二份真源）
    source_config = models.JSONField(default=dict, verbose_name='取数参数')
    # 🔴 刻意只有 active/retired：三种「暂停」作用域不同，混进来必成兜底桶
    status = models.CharField(
        max_length=10, choices=C.METRIC_STATUS_CHOICES, default='active', verbose_name='状态',
    )
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        managed = True
        db_table = 'selfrun_metric'
        db_table_comment = 'KPI 定义：某阶段下的一条指标（周期 / 目标线 / 底线 / 取数来源）'
        verbose_name = '自我运转·KPI 定义'
        verbose_name_plural = '自我运转·KPI 定义'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f'{self.name}（{self.period_type}）'


class SelfRunMetricPlan(models.Model):
    """某一条 KPI 在**某一期**的目标设定 —— 「每周/每月修订下一周、月」的唯一落点。

    🔴 为什么要单独一张表，而不是直接改 `SelfRunMetric.goal_value`：
       目标是**输入**不是派生 ⇒ 必须落库；而「本周还没结束，先把下周的目标定下来」
       是真实诉求 —— 直接改 `Metric` 会**把当期一起改掉**（当期还没归档，
       冻结快照保护不到它），于是「我这周的目标是什么时候变的」就永远说不清，
       而且**界面上两处都看着正常**。

    🔴 两种作用域是**两种事实**，不合并成一个布尔（拆轴不加 key）：
       - `single`：**只**这一期（下一期回落 `Metric` 的默认值）；
       - `from`  ：**从**这一期起一直用（直到出现更晚的 `from`）。
       同一期两条都在 ⇒ **`single` 压过 `from`**（特例优先于长期）。

    🔴 解析规则见 `services.resolve_targets` —— **只有一份实现**，前端不重算、不兜底。
    ⚠️ 落在**已归档周期**里的设定一律 **409**（归档 = 定格，见 `services._assert_period_open`）。
    """

    metric = models.ForeignKey(
        SelfRunMetric, on_delete=models.PROTECT, related_name='plans', verbose_name='KPI',
    )
    # ISO 周 `2026-W43` / 自然月 `2026-10`；**字符串序即时间序**（零填充是同一年内可比的前提）
    period_key = models.CharField(max_length=20, verbose_name='生效期')
    scope = models.CharField(
        max_length=10, choices=C.PLAN_SCOPE_CHOICES, verbose_name='作用域',
    )
    goal_value = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='目标线',
    )
    floor_value = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, verbose_name='底线',
    )
    goal_why = models.CharField(max_length=200, blank=True, default='', verbose_name='目标依据')
    floor_why = models.CharField(max_length=200, blank=True, default='', verbose_name='底线依据')
    note = models.CharField(max_length=200, blank=True, default='', verbose_name='为什么改')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='设定于')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        managed = True
        db_table = 'selfrun_metric_plan'
        db_table_comment = '按期目标：某条 KPI 在某一期的目标设定；改目标是「新开一期」而非改历史'
        verbose_name = '自我运转·按期目标'
        verbose_name_plural = '自我运转·按期目标'
        ordering = ['period_key', 'scope']
        constraints = [
            models.UniqueConstraint(
                fields=['metric', 'period_key', 'scope'],
                name='uniq_selfrun_plan_metric_key_scope',
            ),
        ]

    def __str__(self):
        return f'{self.metric_id} {self.period_key} {self.scope} {self.goal_value}'


class SelfRunMetricLog(models.Model):
    """配置变更留痕 —— **append-only**，T4「尺子断点」的**唯一真源**。

    为什么把「创建」也放进来：它和「改动」**是同一种事实**（配置变更），
    v0.2 用两张表分开记（`Metric` 版本化 + `TemplateUse`）反而让「这段时期的尺子怎么变的」
    要拼两处才看得全。⇒ 合并成一张，`created` 只是第一种 action。
    """

    metric = models.ForeignKey(
        SelfRunMetric, on_delete=models.PROTECT, related_name='logs', verbose_name='KPI',
    )
    action = models.CharField(max_length=20, choices=C.METRIC_ACTION_CHOICES, verbose_name='动作')
    field_name = models.CharField(max_length=30, null=True, blank=True, verbose_name='变更字段')
    from_value = models.JSONField(null=True, blank=True, verbose_name='原值')
    to_value = models.JSONField(null=True, blank=True, verbose_name='新值')
    # 原因：系统**不判断对错、只记录** ——「校准」与「逃避」在当下无法区分，
    # 但在 T4 的时间轴上可以（连续三次「状态」+ 达标率持续下降 = 一种模式）。
    reason = models.CharField(
        max_length=20, choices=C.CHANGE_REASON_CHOICES, null=True, blank=True, verbose_name='原因',
    )
    reason_note = models.CharField(max_length=200, blank=True, default='', verbose_name='原因备注')
    at = models.DateTimeField(auto_now_add=True, verbose_name='发生时间')

    class Meta:
        managed = True
        db_table = 'selfrun_metric_log'
        db_table_comment = '配置变更留痕：append-only，不修改不删除'
        verbose_name = '自我运转·配置变更'
        verbose_name_plural = '自我运转·配置变更'
        ordering = ['-at', '-id']

    def __str__(self):
        return f'{self.metric_id} {self.action} @ {self.at:%Y-%m-%d %H:%M}'


class SelfRunPeriod(models.Model):
    """周期快照与结论。

    🔴 **归档前 `readings` 是空的，归档后它永不改变。**
    ⇒「这周成长多少」在 T2（进行中）和 T3（已归档）是两个**不同的问题**，答案可以不同，
    而且**两个都对**：前者答「此刻跑到哪了」，后者答「结束时定格成什么」。
    """

    stage = models.ForeignKey(
        SelfRunStage, on_delete=models.PROTECT, related_name='periods', verbose_name='阶段',
    )
    period_type = models.CharField(
        max_length=10, choices=C.PERIOD_TYPE_CHOICES, verbose_name='周期',
    )
    period_key = models.CharField(max_length=20, verbose_name='周期标识')   # 2026-W42 / 2026-10
    # 🔴 **半开区间** `[period_start, period_end)` —— 边界日不重复计入。
    period_start = models.DateField(verbose_name='起（含）')
    period_end = models.DateField(verbose_name='止（不含）')
    # 阶段起于周中 ⇒ 第一个周期是残缺周：**参与展示、不进阶段达标率**
    is_partial = models.BooleanField(default=False, verbose_name='残缺周期')
    # 空串 = 未归档（与 `closed_at IS NULL` 同义）
    status = models.CharField(
        max_length=20, choices=C.PERIOD_STATUS_CHOICES, blank=True, default='', verbose_name='判定',
    )
    # 🔴 冻结读数：每条含 `auto_value` / `manual_value` / `final_value` **三个数**。
    #    只存 `final` 的话，三个月后你看到「社交 1 天」没法回答「这 1 天是自动取的还是你补的」。
    readings = models.JSONField(null=True, blank=True, verbose_name='冻结读数')
    # 当时的尺子（改 goal/floor/source_config/agg 都会变 ⇒ 此后周期不可直接比）
    config_fingerprint = models.CharField(max_length=64, blank=True, default='', verbose_name='配置指纹')
    skipped_metric_ids = models.JSONField(default=list, blank=True, verbose_name='本周暂停的条目')
    # 周 = 一句话；月 = 三问（按 `period_type` 分派）
    answer_sheet = models.JSONField(null=True, blank=True, verbose_name='问卷答案')
    # 🔴 **归档后仍可写** —— 记忆型 ≠ 数据型；但每次补写留 `at`（见 `review_edits`）
    review_text = models.TextField(blank=True, default='', verbose_name='你写的话')
    review_edits = models.JSONField(default=list, blank=True, verbose_name='补写留痕')
    # 🔴 这一列一旦有值，`readings` 立即只读（序列化器 `read_only` ⇒ PUT/PATCH 405）
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name='归档于')
    # 🔴 补归档必须诚实：> 7 天 ⇒ 界面显式标注「此数事后补算」，不等价于当天归档
    is_backfilled = models.BooleanField(default=False, verbose_name='事后补归档')
    backfilled_at = models.DateTimeField(null=True, blank=True, verbose_name='补归档于')
    # 重开（改历史判定的唯一出口，且留痕）
    reopened_at = models.DateTimeField(null=True, blank=True, verbose_name='最近重开于')
    reopen_count = models.IntegerField(default=0, verbose_name='重开次数')
    reopen_reason = models.CharField(max_length=200, blank=True, default='', verbose_name='重开原因')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        managed = True
        db_table = 'selfrun_period'
        db_table_comment = '周期快照：某一期算完的结论；归档即定格，此后写入门全关'
        verbose_name = '自我运转·周期'
        verbose_name_plural = '自我运转·周期'
        ordering = ['-period_start', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['stage', 'period_type', 'period_key'],
                name='uniq_selfrun_period_stage_type_key',
            ),
        ]

    def __str__(self):
        return f'{self.period_key}（{self.status or "进行中"}）'

    @property
    def is_closed(self) -> bool:
        return self.closed_at is not None


class SelfRunPoolInject(models.Model):
    """账单上的**「中途注入」标记**（v3.64.26 起改为标记，不再自己记金额）。

    为什么从「自记金额」改成「标账单」：
    - 这笔钱在财富账单里**本来就录过一次**。再自记一份金额 = 同一笔钱两个入口，
      迟早出现「账单改了、注入没改」的分叉，而且分叉是静默的（余额看着合理）。
    - `wealth_bill_list` 是 `managed=False` 外部表，**禁止加列**（项目铁律），
      所以标记只能落在 selfrun 自己的表里，靠 `bill_id` 指向那笔账单。

    🔴 **不带 `stage` 外键**（v3.64.26 特意去掉）：标记是**账单的属性**，
       金额与日期都从账单来；注入额按阶段区间夹窗口算，与本金、消耗**同一把尺子**。
       若再挂一个 stage FK，就会出现「stage 说属于 A、账单日期落在 B」的双源。

    🔴 **只允许标收入**（`transaction_type='收入'`）：注入是钱进来。
       标了注入的收入会从「为自己净消耗」里排除，只算进注入 —— 否则同一笔钱
       既加进注入、又减少净消耗，余额凭空多出一倍。

    ⚠️ 标记本身不含金额，所以**撤销 = 删标记**（不像流水要写负值冲销：
       那条铁律针对的是「账目」，标记只是一个标签）。
    """

    bill_id = models.IntegerField(unique=True, verbose_name='账单ID')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='标记时间')

    class Meta:
        managed = True
        db_table = 'selfrun_pool_inject'
        db_table_comment = '池注入标记：被标为「中途注入」的账单 id（金额从账单读）'
        verbose_name = '自我运转·池注入标记'
        verbose_name_plural = '自我运转·池注入标记'
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'注入标记 bill={self.bill_id}'


class SelfRunCheckin(models.Model):
    """手工登记明细（唯一的手工数据）。

    撤销 = **补一条负值**，原记录保留（项目铁律「撤销 ≠ 删除」）——
    否则 `Period` 快照冻结后，历史读数与明细账实不符。
    """

    metric = models.ForeignKey(
        SelfRunMetric, on_delete=models.PROTECT, related_name='checkins', verbose_name='KPI',
    )
    # 默认今天但**允许改**（补昨天的）—— 不许改日期会逼你在「不记」和「记假日期」之间选
    checkin_date = models.DateField(verbose_name='登记日期')
    value = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name='数值（负数=冲销）',
    )
    note = models.CharField(max_length=200, blank=True, default='', verbose_name='备注')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='登记于')

    class Meta:
        managed = True
        db_table = 'selfrun_checkin'
        db_table_comment = '手工登记：唯一的手工数据入口，一条登记就是一次数量变化'
        verbose_name = '自我运转·手工登记'
        verbose_name_plural = '自我运转·手工登记'
        ordering = ['-checkin_date', '-id']

    def __str__(self):
        return f'{self.metric_id} {self.checkin_date} {self.value}'
