"""数据库注释（`TABLE_COMMENT` / `COLUMN_COMMENT`）—— 派生规则的**唯一实现**。

## 为什么需要这个模块

Django 建表时**只**把两个属性送进 MySQL：

    · `Field.db_comment`      → 列的 `COMMENT`
    · `Meta.db_table_comment` → 表的 `COMMENT`

本项目此前 **0 处**用过它们。于是 2026-10-16 审计出来的结果是：

    109 张 managed 表 —— **表注释全空**（109/109）
    616 个字段        —— 没有列注释

而 `verbose_name` 写得再全也**不会**进库。这就是「打开 Navicat 看不懂这张表
是干什么的」的根因 —— 不是谁忘了写，是**这段通路压根没接上**。

## 列注释为什么不逐字段手写 `db_comment=`

2026-10-16 取证：库里存量注释里 **773 / 815（98.1%）与 `verbose_name` 逐字相同**，
剩下 15 条全在 `wealth_bill_list`（且是库里那条更好）。也就是说
**「列注释 = verbose_name」本就是本项目的既有口径**，不是这里新立的规矩。

再手写 616 遍，就是把同一事实存成两份：`verbose_name` 改了，手写的
`db_comment` 不会跟着改 —— 必然静默漂移。故：

    **默认从 verbose_name 派生**（本模块 do）+ **例外集中声明**
    （`COLUMN_COMMENT_OVERRIDES`，且由测试保证没有死条目）。

## 🔴 文案只写「不随业务变化的稳定事实」

**写**：单位、格式、「空」的含义（`null` ≠ `0`）、互斥 / 唯一 / 幂等等结构约束、
真源指针（「取值见 constants.XXX_CHOICES」）。

**不写**：枚举取值清单、派生公式、阈值 —— 那些的真源在 `constants.py` /
`services.py`，抄进库里就是**第三把尺子**，改了不会同步。

指针 ≠ 副本：指到真源不会漂移，把取值抄一份才会。

## 自动中间表是个例外

Django 的 autodetector **完全忽略** `auto_created` 的 M2M 中间表
（2026-10-16 实测：给它的字段设 `db_comment`、给 `_meta` 设
`db_table_comment`，检出的操作数 **0**）⇒ 这类表登记在
`RUNSQL_ONLY_TABLES`，注释只能由迁移里的 `RunSQL` 补。
"""

from django.apps import apps

# ──────────────────────────────────────────────────────────────
# 覆盖范围
# ──────────────────────────────────────────────────────────────

# 🔴 **已接管**的 app —— 分批推进。
#
# 为什么要有这个白名单，而不是「全项目一起生效」：
#   派生一旦生效，`makemigrations` 就会为该 app 的**每个**字段生成
#   `AlterField(db_comment=...)`。全项目一次生效 = 一步生成 600 多个
#   列变更的迁移 —— 那不是「分批试点」，是「一把梭」。
#   未列出的 app 保持原状（不派生 ⇒ 不产生迁移），等轮到它再往里加。
#
# 批次记录：批 1 = wealth（2026-10-16）；批 2 = 中间那 6 个；批 3 = 其余全部（同日）。
# 批 3 是**收尾批** ⇒ 本白名单已等于「全项目我们自己管的 app」，
# 之后新增 app 时**必须**在这里补一行，否则派生对它静默不生效
# （判据：`test_db_comments` 里那条「接管范围内的表都要有中文表注释」会变红）。
DOCUMENTED_APPS = frozenset({
    # ── 批 1 ──
    'wealth',
    # ── 批 2 ──
    'selfrun',      # 自我运转
    'toolkit',      # 工具箱
    'redemption',   # 赎回期
    'lifesample',   # 人生样本
    'temporal',     # 时间统计
    'relation',     # 关系
    # ── 批 3（收尾）──
    'travel',       # 旅行
    'core',         # 核心配置
    'works',        # 作品库
    'summary',      # 总结 / 七维
    'health',       # 健康
    'goals',        # 目标
    'book',         # 阅读
    'treasure',     # 双面档案
    'sugar',        # 小确幸 / 能量
    'reward',       # 奖励
    'dams',         # 文件资源
    'inbox',        # 收件箱
    'food',         # 美食
})

# Django 自带的 app（auth / admin / contenttypes / sessions）永远不进
# `DOCUMENTED_APPS`：它们是框架表，名字自解释，且没有任何一处是我们
# 能（也不该）通过迁移去改的。所以这里不需要再单列一份排除名单。

# AutoField 的 verbose_name 默认就是 `'ID'` —— 直接拿来当注释等于没写。
DEFAULT_PK_COMMENT = '主键'

# 自动中间表：autodetector 管不到（见模块 docstring 末节），
# 只能由迁移里的 RunSQL 补注释。新增 M2M 时「必须」在这里登记，
# 否则 `test_db_comments` 会报出来。
RUNSQL_ONLY_TABLES = {
    'wealth_survival_essential_items': 'SurvivalEssential.items 的 M2M 自动中间表',
}


# ──────────────────────────────────────────────────────────────
# 列注释的「例外」集中的地方
#
# 判定标准：**这一列光看 verbose_name 会读错或读不懂**。
# 不要在这里重复 verbose_name —— 那由派生负责。
#
# key 一律是 `表名.列名`（真源是库里那张表，不是 model 名）。
# 拼错的 key 不会静默失效：`test_db_comments` 会逐条回查。
# ──────────────────────────────────────────────────────────────
COLUMN_COMMENT_OVERRIDES = {
    # ── 资产科目 / 快照（v3.58.21，P1-B）──────────────────────
    'wealth_asset_account.code': '映射码 —— 只记录「对应旧表 wealth_cash_flow 的哪一列」；手工新增的科目留空即可',
    'wealth_asset_account.category': '资产类别；取值见 constants.ASSET_CATEGORIES',
    'wealth_asset_account.account_kind': '账户形态；同一形态可以有多条（如两个公积金账户）',
    'wealth_asset_account.is_liquid': '是否 T+0 可取 —— 公积金等当天取不出来的为 False',
    'wealth_asset_snapshot.yearmon': '年月（YYYY-MM），每月一期',
    'wealth_asset_snapshot.borrow': '负债合计（元）',
    'wealth_asset_snapshot.lend': '应收借出合计（元）',
    'wealth_asset_snapshot_item.amount': '该科目本期余额（元）',
    'wealth_asset_snapshot_item.account_id': '资产科目；被任何历史快照引用后「不可删除」（PROTECT），只能停用',

    # ── 生存资源 · 单位（换算错会给出「看着合理」的错误天数）──
    'wealth_survival_unit.base_unit': '基准单位 —— 同类别内所有单位都必须能换算到它，否则跨单位求和是错的',
    'wealth_survival_unit.to_base_rate': '换算率 = 1 个本单位等于多少基准单位',
    'wealth_survival_unit.is_serving_unit': '能否作为「一餐 / 一次」的计量单位',

    # ── 生存资源 · 物品：三档估算的输入 ────────────────────
    'wealth_survival_item.quantity': '当前数量（按本行单位计）',
    'wealth_survival_item.satiety': '饱腹角色；取值见 constants.SURVIVAL_SATIETY_CHOICES',
    'wealth_survival_item.grade': '等级；取值见 constants.SURVIVAL_GRADE_CHOICES',
    'wealth_survival_item.status': '状态；取值见 constants.SURVIVAL_STATUS_CHOICES',
    'wealth_survival_item.days_per_unit': '单件可用天数 —— 三档估算输入之一，与「一份可用次数」二选一',
    'wealth_survival_item.uses_per_unit': '一份可用次数 —— 三档估算输入之一，与「单件可用天数」二选一',
    'wealth_survival_item.use_cycle_num': '每几个使用周期一次（与下面两列配套，是一个整体的三元组）',
    'wealth_survival_item.use_cycle_unit': '使用周期单位；取值见 constants.SURVIVAL_USE_CYCLE_CHOICES',
    'wealth_survival_item.stocktake_cycle_days': '建议盘点间隔（天）',
    'wealth_survival_item.restock_threshold': '补货提醒阈值（数量）',
    'wealth_survival_item.purchase_cost': '购入成本（元）',

    # ── 生存资源 · 配餐：餐位语义就是聚合口径 ───────────────
    'wealth_survival_category.consume_mode': '消耗模式；取值见 constants.SURVIVAL_CONSUME_MODES',
    'wealth_survival_category.aggregate_mode': '聚合口径；取值见 constants.SURVIVAL_AGGREGATE_MODES',
    'wealth_survival_recipe.meals_per_day': '每天吃几顿',
    'wealth_survival_recipe_line.role': '餐位；取值见 constants.SURVIVAL_ROLE_CHOICES（同 staple 位求和、跨 required 位取最小）',
    'wealth_survival_recipe_line.quantity_per_serving': '每餐用量（按本行单位计）',
    'wealth_survival_recipe_combo_line.role': '餐位；取值见 constants.SURVIVAL_ROLE_CHOICES',
    'wealth_survival_combo_item.quantity_per_serving': '每餐用量（按本行单位计）',
    'wealth_survival_essential.scope': '性质；取值见 constants.SURVIVAL_ESSENTIAL_SCOPES',
    'wealth_survival_essential.unit_name': '建议单位 —— 只是录入时的提示，不参与任何计算',

    # ── 生存资源 · 快照：算不出是 NULL，不是 0 ──────────────
    'wealth_survival_snapshot.days_optimistic': '乐观天数；算不出为 NULL，不是 0',
    'wealth_survival_snapshot.days_likely': '最可能天数；算不出为 NULL，不是 0',
    'wealth_survival_snapshot.days_pessimistic': '悲观天数；算不出为 NULL，不是 0',
    'wealth_survival_snapshot.days_expected': '三点估算期望天数；算不出为 NULL，不是 0',
    'wealth_survival_snapshot.spread': '离散度 —— 三档估算的离差；三档任一算不出时为 NULL',
    'wealth_survival_snapshot.trustworthy': '结论是否可信；有未解决的问题条数时为 False',
    'wealth_survival_snapshot.issue_count': '落库那一刻的问题条数；> 0 时结论打折',
    'wealth_survival_snapshot_category.days_optimistic': '乐观天数；算不出为 NULL，不是 0',
    'wealth_survival_snapshot_category.days_likely': '最可能天数；算不出为 NULL，不是 0',
    'wealth_survival_snapshot_category.days_pessimistic': '悲观天数；算不出为 NULL，不是 0',
    'wealth_survival_snapshot_category.days_expected': '期望天数；算不出为 NULL，不是 0',
    'wealth_survival_snapshot_category.aggregate_mode_effective': '当时生效的聚合口径 —— 快照要能自证，故冗余留存',
    'wealth_survival_snapshot_category.category_name': '当时的类别名 —— 冗余留存，不靠外键取回（类别改名后旧快照仍读得懂）',

    # ── 生存资源 · 实盘 / 流水 ───────────────────────────
    'wealth_survival_stocktake_line.book_quantity': '账面数量 —— 「必须落库」：盘点那一刻账上有多少，事后重算不出来',
    'wealth_survival_stocktake_line.actual_quantity': '实盘数量 —— 数出来的那个数',
    'wealth_survival_flow.delta': '变化量 —— 正数入库、负数出库（同一件物品只记增量，不记结存）',
    'wealth_survival_flow.reverses_id': '冲销对象 —— 撤销一条流水 = 新增一条反向流水，「不是删除」',
    'wealth_survival_flow.channel': '渠道；取值见 constants.SURVIVAL_FLOW_CHANNELS',
    'wealth_survival_flow.reason': '原因；取值见 constants.SURVIVAL_FLOW_REASONS',

    # ── 物件资产 ────────────────────────────────────────
    'wealth_property.purchase_amount': '购买金额（元）；空 = 未填，「不是 0」',
    'wealth_property.lifespan_months': '计划使用年限（月）；空 = 未填',
    'wealth_property.status': '状态；取值见 constants.PROPERTY_STATUS_CHOICES',
    'wealth_property.condition': '状况；取值见 constants.PROPERTY_CONDITION_CHOICES（broken 时净值按 0 计）',
    'wealth_property.scrapped_date': '报废日期；填了它净值就定格在这一刻',
    'wealth_property_category.default_lifespan_months': '默认使用年限（月）—— 新建物件时的预填值，不回溯改已有物件',

    # ── 身上之物 ────────────────────────────────────────
    'wealth_body_need.find_status': '进度；取值见 constants.BODY_FIND_STATUS_CHOICES',
    'wealth_body_need.satisfaction': '满意程度；空 = 未评 —— 「未评」与「不满意」是两件事',
    'wealth_body_need.property_id': '关联的物件资产；与 survival_item_id 「最多一个非空」（两把不同的尺子）',
    'wealth_body_need.survival_item_id': '关联的库存物品；与 property_id 「最多一个非空」（两把不同的尺子）',

    # ── 账单项分类规则 ──────────────────────────────────
    'wealth_classify_rule.rule_field': '匹配字段；取值见 constants.CLASSIFY_RULE_FIELDS',
    'wealth_classify_rule.income_type': '收入性质；取值见 constants.INCOME_TYPES',
    'wealth_classify_rule.expense_nature': '支出刚性；取值见 constants.EXPENSE_NATURES',
    'wealth_classify_rule.cashflow_class': '现金流类别；取值见 constants.CASHFLOW_CLASSES',
    'wealth_classify_rule.match_value': '匹配值 —— 与 rule_field 合起来是这条规则的身份',

    # ══════════════════════════════════════════════════════════
    # 批 2（2026-10-16）：自我运转 / 工具箱 / 赎回期 / 人生样本 / 时间 / 关系
    # ══════════════════════════════════════════════════════════

    # ── 自我运转 · 模板库 ────────────────────────────────
    'selfrun_template.key': '模板标识 —— 唯一；代码里按它播种，改它等于换一个模板',
    'selfrun_template.period_type': '周期类型；取值见 constants.PERIOD_TYPE_CHOICES',
    'selfrun_template.direction': '判定方向；取值见 constants.DIRECTION_CHOICES',
    'selfrun_template.agg': '聚合方式；取值见 constants.AGG_CHOICES',
    'selfrun_template.source_kind': '取数来源；取值见 constants.SOURCE_KIND_CHOICES',
    'selfrun_template.goal_value': '目标线；空 = 未设目标',
    'selfrun_template.floor_value': '底线；空 = 未设底线',
    'selfrun_template.source_config': '取数参数（JSON）—— 结构由「取数来源」决定',

    # ── 自我运转 · 阶段 ─────────────────────────────────
    'selfrun_stage.status': '状态；取值见 constants.STAGE_STATUS_CHOICES',
    'selfrun_stage.pause_reason': '暂停原因；取值见 constants.PAUSE_REASON_CHOICES',
    'selfrun_stage.last_seen_at': '最近一次回访 —— 用来判断这个阶段还活不活',
    'selfrun_stage.summary_snapshot': '写总结那一刻的读数（JSON）—— 事后重算不出来',

    # ── 自我运转 · KPI 定义 ─────────────────────────────
    'selfrun_metric.template_key': '来源模板的标识 —— 是字符标记、不是外键；删模板不会动这条 KPI',
    'selfrun_metric.period_type': '周期类型；取值见 constants.PERIOD_TYPE_CHOICES',
    'selfrun_metric.direction': '判定方向；取值见 constants.DIRECTION_CHOICES',
    'selfrun_metric.agg': '聚合方式；取值见 constants.AGG_CHOICES',
    'selfrun_metric.source_kind': '取数来源；取值见 constants.SOURCE_KIND_CHOICES',
    'selfrun_metric.status': '状态；取值见 constants.METRIC_STATUS_CHOICES',
    'selfrun_metric.goal_value': '目标线（默认值）—— 某一期真正生效的目标在「按期目标」表里',
    'selfrun_metric.floor_value': '底线（默认值）；空 = 未设',
    'selfrun_metric.stage_id': '所属阶段 —— 下面挂着 KPI 时不可删除',

    # ── 自我运转 · 按期目标 ─────────────────────────────
    'selfrun_metric_plan.metric_id': '所属 KPI —— 不可删除',
    'selfrun_metric_plan.period_key': '生效期（ISO 周 2026-W43 / 自然月 2026-10）—— 字符串序即时间序',
    'selfrun_metric_plan.scope': '作用域；取值见 constants.PLAN_SCOPE_CHOICES',
    'selfrun_metric_plan.goal_value': '目标线（按期输入）—— 改目标是「新开一期」，不回改历史',
    'selfrun_metric_plan.floor_value': '底线（按期输入）',
    'selfrun_metric_plan.note': '这一期为什么这么定',

    # ── 自我运转 · 配置变更留痕 ─────────────────────────
    'selfrun_metric_log.metric_id': '所属 KPI —— 不可删除',
    'selfrun_metric_log.action': '动作；取值见 constants.METRIC_ACTION_CHOICES',
    'selfrun_metric_log.reason': '原因；取值见 constants.CHANGE_REASON_CHOICES',

    # ── 自我运转 · 周期快照 ─────────────────────────────
    'selfrun_period.period_type': '周期类型；取值见 constants.PERIOD_TYPE_CHOICES',
    'selfrun_period.period_key': '周期标识（ISO 周 / 自然月）—— 与阶段、周期类型合起来唯一',
    'selfrun_period.period_start': '起点（含）—— 与终点构成半开区间 [起, 止)',
    'selfrun_period.period_end': '终点（不含）',
    'selfrun_period.is_partial': '残缺周期 —— 起止没盖满一个完整周 / 月',
    'selfrun_period.status': '判定；取值见 constants.PERIOD_STATUS_CHOICES',
    'selfrun_period.readings': '冻结读数（JSON）—— 归档那一刻各指标的值，事后重算不出来',
    'selfrun_period.config_fingerprint': '配置指纹 —— 判断「两期能不能比」的依据；不同说明尺子变了',
    'selfrun_period.skipped_metric_ids': '本期暂停的条目 —— 不进分母',
    'selfrun_period.answer_sheet': '问卷答案（JSON）',
    'selfrun_period.closed_at': '归档时间 —— 一归档就定格：此后补记 / 冲销 / 改本期目标一律拒绝',

    # ── 自我运转 · 手工登记 ─────────────────────────────
    'selfrun_checkin.metric_id': '所属 KPI —— 不可删除',
    'selfrun_checkin.checkin_date': '登记日期 —— 默认今天，允许改（用来补记）',
    'selfrun_checkin.value': '数值 —— 正数记一笔、负数冲销；只追加，不改历史',

    # ── 工具箱 · 时薪（输入与「算出来的」别混）──────────
    'toolkit_hourly_wage.work_days_per_month': '月工作天数（后端算出）—— 不是输入',
    'toolkit_hourly_wage.work_hours_per_day': '日工作小时（后端算出）',
    'toolkit_hourly_wage.total_hours_per_month': '月总投入小时（后端算出）—— 含通勤时间',
    'toolkit_hourly_wage.hourly_wage': '时薪（元/时，后端算出）—— 这个工具最终要的答案',
    'toolkit_hourly_wage.weekly_hours': '每周各天工作时长（JSON）—— 弹性工时模式下用',
    'toolkit_hourly_wage.extra_incomes': '额外收入来源（JSON）—— 每项含名称 / 金额 / 周期',
    'toolkit_hourly_wage.user_id': '用户标识 —— 单用户系统，恒为默认值 1',

    # ── 工具箱 · 其它 ───────────────────────────────────
    'toolkit_fixed_expense.items': '开销项目列表（JSON）—— 每项含名称与金额',
    'toolkit_free_spending.free_amount': '计算结果（元/次）—— 后端算出',
    'toolkit_decision_tracker.lean_options': '自定义倾向选项（JSON）—— 留空则用默认倾向',
    'toolkit_decision_record.tendency': '倾向 —— 可选取值来自所属追踪的自定义选项',
    'toolkit_ask_answer.parent_id': '追问自哪条回答 —— 首轮为空',
    'toolkit_ask_topic.scene_id': '所属业务场景 —— 空 = 未归类',

    # ── 赎回期 ──────────────────────────────────────────
    'redemption_period.pool_principal': '启动现金池本金（元）',
    'redemption_period.baseline_toward_ratio': '阶段一基线·成长占比 —— 锁定后不再变',
    'redemption_pool_inject.amount': '注入金额（元）—— 正数为注入池',
    'redemption_attr_rule.match_field': '匹配字段 —— 与「匹配值」合起来算一条规则',
    'redemption_attr_rule.match_value': '匹配值 —— 与「匹配字段」合起来算一条规则',
    'redemption_attr_rule.attribution': '归因类别 —— 真源是 temporal/constants.py 的 ATTRIBUTION_CHOICES',
    'redemption_attr_rule.priority': '优先级 —— 多条同时命中时取高者',
    'redemption_week_snapshot.coverage_rate': '覆盖率 = 已记录小时 ÷ 理论小时',
    'redemption_week_snapshot.unit_cost': '单位赎回成本 —— 空 = 算不出（不是 0）',

    # ── 人生样本 ────────────────────────────────────────
    'life_sample.obsidian_path': '相对于 Obsidian 仓库根目录 —— 唯一，一行对一个笔记',
    'life_sample.status': '状态 —— 推进时会自动补上核实 / 审阅时间',
    'life_sample.summary': '一句话简介 —— 列表页显示的就是它',
    'life_sample.my_note': '我自己的笔记（Sycamore 侧）—— 与 Obsidian 正文是两回事',

    # ── 时间 ────────────────────────────────────────────
    'temporal_task_meta.task_name': '任务名（L3）—— 唯一',
    'temporal_task_meta.activity_type': '活动类型（L2）',
    'temporal_task_meta.default_attribution': '默认归因 —— 真源是 temporal/constants.py 的 ATTRIBUTION_CHOICES',
    'temporal_task_meta.group_id': '旧「聚合分组」遗留列（v3.57.0 起不再读写）—— 保留只为不丢历史',
    'temporal_weekly_time_cache.year': '年份 —— 与周次合起来唯一',
    'temporal_weekly_time_cache.week': '周次 —— 与年份合起来唯一',

    # ── 关系 ────────────────────────────────────────────
    'relation_reader_monthly_summary.reader_group_id': '所属群体 —— 与年份、月份合起来唯一',

    # ══════════════════════════════════════════════════════════
    # 批 3（2026-10-16，收尾）：旅行 / 核心 / 作品 / 结 / 健康 / 目标 /
    #                           阅读 / 双面档案 / 小确幸 / 奖励 / 文件 / 收件箱 / 美食
    # ══════════════════════════════════════════════════════════

    # ── 旅行 ────────────────────────────────────────────
    'travel_wish.visit_record_id': '已沉淀成的足迹（travel_list_info 的 tid）—— 空 = 这天还没沉淀；沉淀时按「已打卡 + 同一天 + 尚未沉淀」挑待合并的心愿',
    'travel_wish.status': '状态：想去 → 已列入计划 → 已打卡；只有「已打卡」才有打卡字段，也才有沉淀资格',
    'travel_plan_item.item_type': '类型：美食 / 景点 / 交通 / 住宿 —— 决定子项显示哪些字段',

    # ── 核心配置 ────────────────────────────────────────
    'core_user_profile.privacy_mode': '脱敏模式 —— 展示层是否掩码的唯一开关；状态源在这里，前端不另存一份',
    'core_user_profile.logseq_path': 'Logseq 日记目录 —— 时间统计按 YYYY_MM_DD.md 在此目录下找 oneday 文件；留空 = 「打开日记」不可用',
    'core_user_profile.quote_pool_max_len': '金句池长度上限（字）—— 默认值的唯一真源是模型 default；可填区间见 core/models.py 的 QUOTE_POOL_LEN_RANGE',
    'core_system_preset.preset_type': '预设类型 —— 一类一行（唯一），取值见 core/models.py 内联的 PRESET_TYPE_CHOICES',
    'core_menu_preference.menu_key': '菜单标识 —— 与前端 menuConfig.ts 里的 key 逐字对应，改名等于换一项菜单',
    'core_notification.source_object_id': '来源对象 ID —— 与「来源模块」合起来指向那条业务记录；业务记录删了通知仍在',

    # ── 作品库 ──────────────────────────────────────────
    'works_work.channel': '出口去向 —— 空串 = 还没决定发到哪，与「出口状态 = 只给自己」是两件事；候选值来自 core_system_preset 的 work_channels',
    'works_work.status': '出口状态 —— 只记状态，不逼你填日期或链接；取值见 constants.WORK_STATUS_CHOICES',
    'works_work.kind': '类型 —— 取值见 constants.WORK_KIND_CHOICES',
    'works_capture.source_type': '来自哪种入口 —— 取值见 constants.CAPTURE_SOURCE_CHOICES（七个入口共用同一个勾）',
    'works_capture.source_id': '来源 ID —— 跨七张源表的裸 id，单看会撞号；身份键必须是 (source_type, source_id) 复合',
    'works_capture.status': '状态 —— 取值见 constants.CAPTURE_STATUS_CHOICES',
    'works_capture.title': '当时勾的那条源记录的标题（快照）—— 源记录改名或被删后仍要读得懂',
    'works_capture.work_id': '收进哪件作品 —— 空 = 还在待提炼；删掉作品会把它放回待提炼（不是删除）',

    # ── 总结 / 七维 ─────────────────────────────────────
    'summary_quarterly_answer.question_key': '问题标识 —— 与年份、季度合起来唯一（同一问题一年只问一次）',
    'summary_quarterly_answer.related_module': '关联模块 —— 空 = 通用问题，不指向任何具体模块',
    'summary_seven_dim_config.is_active': '是否生效 —— 同一时刻只应有一条；改配置 = 新增一条 + 把旧的置为历史',
    'summary_seven_dim_config.note': '这一版为什么这么定 —— 历史配置靠它可追溯',

    # ── 健康 ────────────────────────────────────────────
    'health_weight_record.record_date': '记录日期 —— 与用户 ID 合起来唯一（一天一条）',
    'health_weight_record.body_fat': '体脂率（%）—— 空 = 这次没测，不是 0',
    'health_weight_goal.current_month': '当前第几个月 —— 从 1 起算；随里程碑推进回写',
    'health_menstrual_record.month': '月份 —— 文本列，形如「10月」（历史遗留）；做统计请用开始日期，别按它排',
    'health_menstrual_record.offset': '偏移量（天）= 本次周期跨度 − 上次周期跨度；正数 = 比上个周期推迟',
    'health_menstrual_record.cycle_days': '周期跨度（天）= 距上一次开始的天数；录入时前端自动算、可手改',
    'health_weight_goal_adjustment.before_value': '变更前目标（斤）—— ⚠️ 本表三个金额列都用「斤」，而体重目标表用「公斤」，换算别搞错',

    # ── 目标 · 奖励四件套（同名不同义，必须逐列说清）────
    'goals_goal.reward_value': '旧版「每个里程碑奖励」—— 已被 default_reward_amount 取代，仅作回退保留',
    'goals_goal.default_reward_amount': '每项里程碑默认奖励（元）—— 启用奖励且它 > 0 时生效，优先于 reward_value',
    'goals_goal.goal_completion_bonus': '目标完成奖励金（元）—— 全部里程碑完成后只发一次，靠流水判重',
    'goals_goal.total_reward_issued': '本目标累计已发放（元）—— 发放时累加、撤销完成时扣回',
    'goals_goal.enable_reward': '是否启用里程碑奖励 —— 关闭时上面那几个金额一律不参与发放',
    'goals_goal.progress_percentage': '进度百分比 —— 由里程碑完成情况算出（只读，不可直接编辑）',
    'goals_goal.circle_check': '是否在能力圈内 —— 用整数存的「是 / 否」；历史字段，前端已不展示',
    'goals_milestone.reward_transaction_id': '关联的奖励流水 ID —— 指向 reward_transaction 的裸 id，用来回溯这一笔',
    'goals_milestone.reward_synced': '奖励是否已同步 —— 幂等标记：True 时不再重复发放',
    'goals_output_record.quality': '质量判定 —— 良品率的分母按它算',

    # ── 阅读 ────────────────────────────────────────────
    'book_read_list.created_at': '创建日期（只到天）—— 本表用 DateField 而非 DateTimeField，与本项目其它表不同',
    'book_read_list.updated_at': '更新日期（只到天）—— 同为 DateField，写入时自动',
    'book_read_list.readDate': '阅读日期 —— 列名是驼峰（历史遗留），与 bid / btype 同属旧式命名',
    'book_read_list.closedop': '读后感 —— 合上书时的观点；与 openop 成一对，用来看「读完之后我变了没有」',
    'book_read_list.openop': '打开书时的观点和期待 —— 与 closedop 成一对',
    'book_read_list.abandon_reason': '弃读原因 —— 状态是「弃读」时才填',
    'book_read_list.recommend': '推荐指数 —— 0 = 禁止阅读（比「不推荐」更低一档）；取值见 models.RECOMMEND_CHOICES',

    # ── 双面档案 ────────────────────────────────────────
    'treasure_good_thing.subject_kind': '记录对象：实物 / 方法 —— 决定下面显示哪些字段；取值见 constants.SUBJECT_KIND_CHOICES',
    'treasure_good_thing.record_type': '类型：好 = 好物、歹 = 歹物（双面档案的两面）',
    'treasure_good_thing.category': '类别 —— 只有实物才有；取值见 constants.CATEGORY_CHOICES（界面文案按好 / 歹分流，走 constants.category_label）',
    'treasure_good_thing.method_group': '方法归类 —— 只有方法才有，可留空；取值见 constants.METHOD_GROUP_CHOICES',
    'treasure_good_thing.property_id': '关联物件资产 —— 与「关联物品清单」最多一个非空；一件实物最多一条评价（唯一约束）',
    'treasure_good_thing.survival_item_id': '关联物品清单 —— 与「关联物件资产」最多一个非空',
    'treasure_good_thing.still_available': '还能找到吗 —— 实物专属；False = 绝版 / 买不到了',
    'treasure_good_thing.rating': '评分 —— 前端已撤下（零信息量，与好 / 歹 + 理由重复）；列留着只为不动存量',

    # ── 小确幸 / 能量 ───────────────────────────────────
    'sugar_energy_log.template_id': '关联模板 —— 空 = 当时是自定义内容（模板被删也留空，不连坐）',
    'sugar_energy_log.is_custom': '是否自定义内容 —— True 时「关联模板」为空',
    'sugar_energy_log.reward_processed': '是否已处理奖励池 —— 幂等标记：True 时不再重复发奖',
    'sugar_record.reward_synced': '奖励是否已同步 —— 幂等标记：True 时不再重复发奖',
    'sugar_record.reward_amount': '本记录产生的奖励金额（元）—— 落库是为了撤销时知道该退多少',
    'sugar_record.years': '年份 —— 与「发生日期」同源的冗余列（录入时一并写入，应始终一致）；按年月聚合走它，避免对日期做函数运算',
    'sugar_record.month': '月份 —— 与「发生日期」同源的冗余列，同「年份」',
    'sugar_energy_template.user_id': '用户 ID —— is_system 为 False 时记录是谁自建的',

    # ── 奖励 ────────────────────────────────────────────
    'reward_pool.balance': '当前余额（元）—— 与流水对照：余额 ≈ 累计获得 − 累计提取',
    'reward_pool.total_earned': '累计获得（元）—— 只增不减的累计口径',
    'reward_pool.total_withdrawn': '累计提取（元）',
    'reward_transaction.source_type': '来源类型 —— milestone / sugar 等，用裸字符串不是外键',
    'reward_transaction.source_id': '来源 ID —— 与「来源类型」合起来指向业务记录；裸 id 跨表会撞号',
    'reward_transaction.balance_before': '交易前余额（元）—— 落库快照，用来逐笔对账',
    'reward_transaction.balance_after': '交易后余额（元）—— 落库快照',

    # ── 文件资源 ────────────────────────────────────────
    'dams_file_resource.path': '完整路径 —— 绝对路径；本表只是索引，不搬动也不删除文件',
    'dams_file_resource.file_category': '文件分类 —— 取值见 constants.FILE_CATEGORY_CHOICES',
    'dams_file_resource.access_count': '访问次数 —— 由访问日志累计得出',
    'dams_file_resource.folder_depth': '文件夹深度 —— 由路径算出的层级数',
    'dams_file_resource.parent_folder': '父文件夹 —— 由路径截取，便于按目录筛',
    'dams_file_resource.is_duplicate': '是否重复 —— 只是标记，不代表会被删除或合并',

    # ── 收件箱 ──────────────────────────────────────────
    'inbox_item.target_type': '目标模块类型 —— 与「目标模块 ID」合起来指向转过的那条记录；空 = 还没处理',
    'inbox_item.completion_note': '完成备注 —— 状态是「已完成」时才填',
    'inbox_item.hesitate_reason': '犹豫原因 —— 状态是「犹豫中」时才填',
    'inbox_item.abandon_reason': '废弃原因 —— 状态是「已废弃」时才填',
    'inbox_process_log.action': '操作 —— 转成目标 / 里程碑 / 能量、完成、归档；取值见 models.ACTION_CHOICES',

    # ── 美食 ────────────────────────────────────────────
    'food_record.province': '省份 —— 必填；列表与地图按省 / 市筛',
    'food_record.city': '城市 —— 必填；与省份合成 (province, city) 索引',
    'food_record.want_visit_again': '是否还想再去 —— 与「美味等级」是两件事（好吃 ≠ 想再去）',
    'food_record.eat_time': '时段 —— 早餐 / 午餐 / 晚餐 / 小吃',
}


def override_comment(table: str, column: str) -> str:
    """例外声明的查表入口。取不到返回空串（由派生兜底）。"""
    return COLUMN_COMMENT_OVERRIDES.get(f'{table}.{column}', '')


def normalize_comment(text: str) -> str:
    """注释落库前的安全化：`%` → 全角 `％`。

    🔴 **不是洁癖，是炸弹拆除**（2026-10-16 实测）。

    Django 生成 `ALTER TABLE ... MODIFY COLUMN` 时，把注释**内联**进 SQL
    之后还要再走一次 `sql % params`（`BaseDatabaseSchemaEditor.execute`，
    注释那一路 `params` 是空列表）。于是注释里任何一个 `%` 都会被当成
    格式化占位符：

        cursor.execute("... COMMENT '年利率(%)'", [])
        → ProgrammingError: not enough arguments for format string

    后果不是「注释不好看」，是**整条迁移半路崩掉** —— 而且崩在 294 条
    `MODIFY` 中间的某一条，前面已经执行的那部分不会自动回滚
    （MySQL 的 DDL 不可回滚），排障成本很高。

    为什么归一化在**机制层**、而不是只改当前那几个字段：
    只修当下，等于给下一次埋雷 —— 将来谁写了带 `%` 的 verbose_name，
    `makemigrations` 生成得好好的，`migrate` 才崩，且没人知道为什么。
    `test_db_comments` 里有一条断言守着这个不变量（db_comment 与
    db_table_comment 都不得出现半角 `%`）。

    ⚠️ 为什么不写成 `%%` 转义：那只是**赌**这条 SQL 恰好会被替换一次。
    哪天 Django 改了转义策略，库里就会留下字面的 `%%`，同样是静默的。
    全角字符在任何路径下都稳定，代价仅是视觉上略宽。
    """
    return (text or '').replace('%', '％')


def derive_column_comment(field) -> str:
    """算出一列该写什么注释 —— 例外优先，否则用 verbose_name。

    🔴 这里是**唯一**的判定处。别在别处再写一份「取 verbose_name」的兜底，
       那种第二实现一旦口径不同就是静默偏差。
    """
    if field.db_comment:
        return field.db_comment            # 模型里就地声明的最优先
    vn = str(field.verbose_name or '').strip()
    if not vn:
        return ''
    if vn.lower() == 'id':
        return DEFAULT_PK_COMMENT          # AutoField 的默认 verbose_name 是 'ID'
    return vn


def documented_models():
    """本机制负责的模型 = **已接管 app**（`DOCUMENTED_APPS`）里我们自己管的表。

    `auto_created` 的 M2M 中间表**不在**其中 —— autodetector 忽略它们，
    给它们设 `db_comment` 只会让运行时模型「自称有注释」而库里没有。
    那类表由 `RUNSQL_ONLY_TABLES` 登记、走迁移里的 RunSQL。
    """
    for model in apps.get_models(include_auto_created=True):
        meta = model._meta
        if not meta.managed:
            continue
        if meta.app_label not in DOCUMENTED_APPS:
            continue
        if meta.auto_created:
            continue
        yield model


def apply_column_comments():
    """把派生的 / 声明的列注释写到 `field.db_comment` 上。

    由 `CoreConfig.ready()` 调用。**必须在 ready() 里做**：那时所有 app 的模型
    都已注册完，一次遍历覆盖全项目，且 `makemigrations` 能据此生成 `AlterField`。

    幂等：值没变就不赋值。
    """
    for model in documented_models():
        table = model._meta.db_table
        for field in model._meta.concrete_fields:
            comment = normalize_comment(
                override_comment(table, field.column) or derive_column_comment(field)
            )
            if comment and field.db_comment != comment:
                field.db_comment = comment


def apply_table_comments():
    """把 `Meta.db_table_comment` 也归一化（`%` → 全角 `％`）。

    🔴 **和列注释是同一颗炸弹**：2026-10-16 用真实驱动实测
    `cursor.execute("ALTER TABLE x COMMENT = '测试 100% 覆盖'", ())`
    → `ProgrammingError: not enough arguments for format string`。
    表注释的 SQL 虽然先走 `sql_alter_table_comment % {dict}`（值不被二次
    解释），但最后仍落到 `cursor.execute(sql, ())`，`args` 不是 None ⇒
    驱动还会做一次 `sql % ()`。一样是**整条迁移半路崩**。

    🔴 **为什么必须同时改 `_meta.original_attrs`**（这一步很反直觉，实测出来的）：
    `ModelState.from_model()` 读表注释读的是 `model._meta.original_attrs`
    —— 类定义时记下的**原始 kwargs** —— 而**不是** `model._meta.db_table_comment`。
    2026-10-16 实测：

        只改 _meta.db_table_comment    → ProjectState.from_apps() 读到的仍是旧值（静默失效）
        同时改 original_attrs          → 读到新值 ✅

    也就是说：只改 `_meta` 的话 `makemigrations` 会**当作什么都没发生**，
    代码看着生效、迁移里却仍是带 `%` 的原文 —— 又是一次静默失败。
    （字段层不存在这个问题：`field.db_comment` 是字段自身的属性，
     `from_model` 里 `field.clone()` 会原样带上。）

    ⚠️ 副作用是有意接受的：运行时状态与**源码字面量**可能不同（源码写 `%`、
    内存里是 `％`）。因为迁移文件记的是归一化后的值，下一次
    `makemigrations` 两边一致 ⇒ **不会**产生无谓的新迁移。
    """
    for model in documented_models():
        raw = model._meta.db_table_comment
        if not raw:
            continue
        safe = normalize_comment(raw)
        if safe == raw:
            continue
        model._meta.db_table_comment = safe
        model._meta.original_attrs['db_table_comment'] = safe
