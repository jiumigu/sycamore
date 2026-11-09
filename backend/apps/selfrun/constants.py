"""自我运转 · 枚举 / 阈值 / 白名单（**单一真源**）

🔴 读之前先知道三件事：

1. **本文件是唯一真源。** 前端 `modules/selfrun/types/selfrunTypes.ts` 是**副本**，
   漏改**不会报错**（要么落 `|| 兜底` 变灰、要么少一个下拉选项）。
2. **判定阈值（`PERIOD_VERDICT_BANDS`）只此一份**，前端 **0 个阈值数字**，只上色不判。
3. **`Metric.status` 里刻意没有 `paused`** —— 三种「暂停」作用域不同（一条·一周 /
   整个阶段 / 一条·永久），混进一个字段**必成兜底桶**（项目铁律）。
4. **`SelfRunTemplate`（模板库）与 `SelfRunMetric`（阶段里的那条）是「拷贝」不是「引用」** ——
   模板只是**起点**；改模板**不影响任何已建阶段**。详见 `templates.py`。
"""

# ══════════════════════════════════════════════════════════════
# 一、枚举（7 张表的取值）
# ══════════════════════════════════════════════════════════════

# ① 阶段状态机：draft → active ⇄ paused → closed ──[复制]──> 新 draft
STAGE_STATUS_CHOICES = [
    ('draft', '草稿'),
    ('active', '进行中'),
    ('paused', '暂停中'),
    ('closed', '已收尾'),
]

# 暂停原因 —— **拆轴不加 key**：四种原因同一把尺子（「为什么停下」），
# 不合并进 status（否则 `paused` 会变成兜底桶）。
PAUSE_REASON_CHOICES = [
    ('trip', '旅途'),
    ('sick', '生病'),
    ('fallow', '休耕'),
    ('other', '其他'),
]

# ② 周期类型（两把**正交**的尺子：周量「有没有在动」、月量「动出结果没有」）
PERIOD_TYPE_CHOICES = [
    ('weekly', '周'),
    ('monthly', '月'),
]

# ③ 周期状态（四档 + 休耕）
# 🔴 `fallow` 不是失败（V4）；`no_record` 是「这期没有记录」，与 `slid` 不同。
#
# 🔴 v3.62.45：标签**只放档位本名，不带「本周 / 本月」前缀**。
#    前缀由页面按 `period_type` 拼（`periodStatusLabel(v, periodType)`）——
#    之前写死「本周合格」，于是「本月状态」页也在说「本周」，读起来像走错了页。
PERIOD_STATUS_CHOICES = [
    ('great', '我超棒'),
    ('on_track', '合格'),
    ('slipping', '及格'),
    ('slid', '活着'),
    ('no_record', '这期没有记录'),
    ('fallow', '休耕中'),
]

# 档位本名（🔴 唯一一份；`choices` 与接口下发都用它，别在别处再写一遍）
PERIOD_STATUS_LABEL = dict(PERIOD_STATUS_CHOICES)

# 页面按周期类型拼前缀：`PERIOD_PREFIX['weekly'] + '合格'` ⇒ 本周合格
PERIOD_TYPE_PREFIX = {
    'weekly': '本周',
    'monthly': '本月',
}

# ④ KPI 状态 —— 刻意只有两个值（见模块 docstring 第 3 条）
METRIC_STATUS_CHOICES = [
    ('active', '生效中'),
    ('retired', '已退役'),
]

# ⑤ 单条 KPI 的本期判定
# 🔴 `empty` 与 `unknown` 必须分开：前者是「真的没做」，后者是「系统不知道」（V1）。
VERDICT_CHOICES = [
    ('goal', '达目标'),
    ('floor', '达底线'),
    ('miss', '未达底线'),
    ('empty', '本期无数据'),
    ('unknown', '取不到'),
]

# ⑥ 取数来源（决定 `final_value` 怎么合并，见 readers.py）
SOURCE_KIND_CHOICES = [
    ('auto', '自动取数'),
    ('manual', '手工登记'),
    ('auto_plus_manual', '自动 + 手工补记'),
]

# ⑦ 聚合方式
# ⚠️ 「宣纸 6 张」是**计数**不是时长 ⇒ `manual_sum` 与 `sum_hours` **不共用路径**。
AGG_CHOICES = [
    ('sum_hours', '时长求和'),
    ('sum_value', '数值求和'),
    ('distinct_days', '有记录天数'),
    ('count', '计数'),
    ('boolean', '有无'),
    ('manual_sum', '手工求和'),
]

# ⑧ 方向（判定比较符）
DIRECTION_CHOICES = [
    ('at_least', '至少（≥）'),
    ('at_most', '至多（≤）'),
]

# ⑨ 配置变更留痕的动作
# 「创建」只是**第一种 action** —— 它和「改动」是同一种事实（配置变更）。
METRIC_ACTION_CHOICES = [
    ('created', '创建'),
    ('goal_changed', '目标变更'),
    ('floor_changed', '底线变更'),
    ('config_changed', '口径变更'),
    # 「按期设定」与「改默认值」是**两种事实**（作用域不同、影响面不同）⇒ 分开记，
    # 否则时间轴上分不清「哪一期换过尺子」和「往后都换了尺子」。
    ('plan_changed', '按期设定'),
    ('retired', '退役'),
    ('revived', '恢复'),
]

# ⑩ 变更原因（**系统不判断对错，只记录** —— 三个月后在时间轴上自己看出来）
CHANGE_REASON_CHOICES = [
    ('template_use', '套用模板'),
    ('calibrate', '校准：之前的预期不现实'),
    ('mood', '状态：最近状态不好，想先松一点'),
    ('other', '其他'),
]

# ⑪ 按期目标的**作用域** —— 「两种都要」，但它们是**两种事实**，不合并成一个布尔：
#    · `single` = **只**这一期（下一期回落默认值）；
#    · `from`   = **从**这一期起一直用（直到出现更晚的 `from`）。
#    ⚠️ 同一期两条都在时 **`single` 压过 `from`**（特例优先于长期）。
PLAN_SCOPE_CHOICES = [
    ('single', '只这一期'),
    ('from', '从这一期起'),
]

# 目标值**从哪来**（读数里下发，前端只显示不判）——
# ⚠️ 这三者必须能分辨：`metric` 是「阶段默认」、`single` 是「本期特例」、
#    `from` 是「从某期起改过」。全都显示成同一个数的话，
#    「我这周的目标怎么变了」就永远说不清（而界面两处都「看着正常」）。
TARGET_SOURCE_METRIC = 'metric'
TARGET_SOURCE_SINGLE = 'single'
TARGET_SOURCE_FROM = 'from'
TARGET_SOURCE_LABELS = {
    TARGET_SOURCE_METRIC: '阶段默认',
    TARGET_SOURCE_SINGLE: '本期设定',
    TARGET_SOURCE_FROM: '按期设定',
}


# ══════════════════════════════════════════════════════════════
# 二、判定阈值（🔴 全项目只此一份）
# ══════════════════════════════════════════════════════════════

# 周判定：达标条数 / 生效条数 ≥ 下限即命中该档（**从高到低**匹配，先中先得）
#
# v3.62.45 由两档扩到三档（另有 `<0.4` 兜底档 `slid`）：
#   ≥80% 我超棒 · ≥60% 合格 · ≥40% 及格 · <40% 活着
# 🔴 加档只改这张表：`compute_period_status` 与前端文案都是遍历它，
#    前端 0 个阈值数字（写死 = 哪天调线界面还在说旧线）。
PERIOD_VERDICT_BANDS = [
    ('great', 0.8),
    ('on_track', 0.6),
    ('slipping', 0.4),
]

# 月判定：三问里答「是」的个数 ÷ **3**（三问总数）。
# 🔴 分母恒为 3，不按「已答数」——「未答」不当作否、也不当作是（V1 同源），
#    但这不代表可以拿它去放大比例：答了 1 个「是」就是 1/3，不是 1/1。
#
# 🔴 v3.64.6 起：月度**只有这一把尺子**。全部未答（一个都没点）⇒ 空串，
#    界面显示「待答三问」，**不再落回月度 KPI 档位** —— 旧行为会让同一期
#    在归档前一秒判「我超棒」(4/4=100%)、答完三问立刻掉成「合格」(2/3=67%)：
#    数字没变、尺子换了，用户看到的就是「归档把我降档了」。
#    KPI 达标率仍下发（`ok` / `counted`），但只作参考，不参与判定。
MONTHLY_QUESTION_COUNT = 3

# 三问的键（🔴 顺序 = 页面顺序 = 判定顺序；`monthly_answer_stats` 唯一遍历它）
MONTHLY_QUESTION_KEYS = ('q1_income', 'q2_output', 'q3_runway')

# 补归档阈值：周期结束超过这么多天再归档 ⇒ 必须显式标注「此数事后补算」
BACKFILL_WARN_DAYS = 7

# 心跳节流：同一天最多写一次 `last_seen_at`
HEARTBEAT_MIN_INTERVAL_DAYS = 1


# ══════════════════════════════════════════════════════════════
# 三、取数器注册表（收敛：不做任意查询构建器）
# ══════════════════════════════════════════════════════════════

# 🔴 **不做任意查询构建器**的理由：任意查询 = 口径可以静默配错，且没有测试能钉住它。
# 这里只列**允许**的 reader key；`source_config.kind` 必须命中其一。
READER_KEYS = (
    'temporal_hours',      # 按 L1/L2/L3 过滤 → 时长求和
    'growth_hours',        # 映射编辑器勾了「成长计时」的任务名 → 时长求和（口径固定，无 where）
    'temporal_days',       # 有记录的天数（社交连接）
    'diary_migu_count',    # 日记流 otype='MIGU' 的条数 / 字数（输出）
    'step_days',           # health 步数 → 有步数的天数（出门）
    'bill_income',         # wealth 收入明细求和（收入验证）
    'module_value',        # 白名单单值：redemption.runway / wealth.snapshot_fresh
    'manual_sum',          # 手工打卡求和（宣纸 / 画）
    'works_count',         # 作品库的件数（留下件数，v3.62.0 起取代 diary_migu_count 的输出口径）
)

# `module_value` 的**白名单**（键必须完全命中，不做前缀匹配）
MODULE_VALUE_WHITELIST = (
    'wealth.snapshot_fresh',    # 本月有无新的资产快照（→ 资产盘点）
    'redemption.runway',        # 可支撑月数（当前算不出来 ⇒ None + reason）
)

# 模板编辑界面用：每个取数器在 `source_config.where` 里需要哪一个键。
#
# 🔴 这是**界面元信息，不参与取数** —— 取数只看 `readers.py` 的实现。
#    放在这里是为了让前端**不抄第三份**取数器枚举（抄了就会漏改、且静默）：
#    模板接口直接把这份连同 `READER_KEYS` 一起下发。
# `None` = 该取数器**不需要**附加条件（它自带固定口径），界面不开放编辑：
#     · `diary_migu_count` 固定 `otype_eq='MIGU'`（reader 自带默认值）；
#     · `step_days`      无过滤；
#     · `bill_income`    固定 `transaction_type='收入'`（category 由 seed 的模板带）；
#     · `manual_sum`     手工登记，本就没有配置。
READER_WHERE_KEYS = {
    'temporal_hours': 'l2',
    # 🔴 成长计时**没有**可配条件：唯一依据是映射编辑器里那个开关，
    #    再给一个 l2 过滤器就等于同一个量有两处定义（v3.64.11 收口）
    'growth_hours': None,
    'temporal_days': 'l2',
    'diary_migu_count': None,
    'step_days': None,
    'bill_income': None,
    'module_value': 'key',
    'manual_sum': None,
    # 作品库：v3.64.30 起可按**类型**过滤（「这月画了几张」= works_count + work_kind=drawing）。
    # 🔴 留空 = 数全部类型（「留下件数」那条就是这么用的）；**不是**「默认只数文章」——
    #    默认值一变，所有既有阶段的历史读数会跟着变。
    'works_count': 'work_kind',
}

# 每个取数器**默认**的聚合方式（换取数器 ⇒ 聚合方式跟着走，不让人再填一遍）。
#
# 🔴 `agg` 不参与取数，只出现在「口径」那一栏（`自动 + 手工补记 · manual_sum`）
#    与配置指纹里。正因为**不影响数**，漏改它不会有任何报错 —— 只会让界面
#    理直气壮地说错话（「从作品库取数、按手工求和」）。所以不让它单独可填，
#    由 `source_config.kind` 推导：一个事实一把尺子。
READER_AGG = {
    'temporal_hours': 'sum_hours',
    'growth_hours': 'sum_hours',
    'temporal_days': 'distinct_days',
    'diary_migu_count': 'count',
    'step_days': 'distinct_days',
    'bill_income': 'sum_value',
    'module_value': 'boolean',
    'manual_sum': 'manual_sum',
    'works_count': 'count',
}

# 漏一个就早点炸，别等线上（与 `readers.py` 的注册表断言同一个精神）
assert set(READER_AGG) == set(READER_KEYS), \
    'READER_AGG 与 READER_KEYS 不一致'
assert set(READER_WHERE_KEYS) == set(READER_KEYS), \
    'READER_WHERE_KEYS 与 READER_KEYS 不一致'


# ══════════════════════════════════════════════════════════════
# 四、数据源新鲜度（→ `state='stale'`）
# ══════════════════════════════════════════════════════════════

# 每个 reader 的「多久没更新算 stale」与**用来判新鲜度的字段**，
# 以及给用户的兜底提示（指向哪个模块去补）。
# 🔴 `field` 是**文档性标注**（真正参与计算的是 reader 返回的 `freshness_at`），
#    但它必须写对 —— 后来人会照着它去改实现。**它必须指向「取数那张表」**：
#    取账单明细的 reader 就该写 `MAX(date)`，写成月结表的 `MAX(yearmon)`
#    会把一份新鲜的数据判成过期（2026-10-18：「收入验证」明明取到 6,012.64 元
#    却显示「取不到」，因为月结表一月一行、天生滞后）。
# ⚠️ `manual_sum` 没有新鲜度概念（手工登记本来就是你想记才记）⇒ None。
STALE_RULES = {
    'temporal_hours': {'days': 3, 'field': 'MAX(start_time)', 'hint': '时间统计'},
    'growth_hours': {'days': 3, 'field': 'MAX(start_time)', 'hint': '时间统计'},
    'temporal_days': {'days': 3, 'field': 'MAX(start_time)', 'hint': '时间统计'},
    'diary_migu_count': {'days': 7, 'field': 'MAX(begin_date)', 'hint': '日记流'},
    'step_days': {'days': 7, 'field': 'MAX(time)', 'hint': '健康管理'},
    # 取数走 `wealth_bill_list`（逐笔账单），新鲜度也必须是它的 `MAX(date)`。
    # `days=40` 不动：它表达的是「记账断了一个多月才算源过期」，与取哪张表无关。
    'bill_income': {'days': 40, 'field': 'MAX(date)', 'hint': '财务管理'},
    'module_value': {'days': 40, 'field': '(白名单各自判定)', 'hint': '财务管理'},
    'manual_sum': None,
    # 作品库：**不给新鲜度**。
    # 🔴 「这周一件都没留」不是数据源过期，是**事实** ——
    #    给它一条 stale 规则等于把「没留东西」说成「系统不知道」，
    #    与 `state='empty'` 的语义直接打架。
    'works_count': None,
}


# ══════════════════════════════════════════════════════════════
# 五、配色（跟语义走，**不套涨红跌绿**）
# ══════════════════════════════════════════════════════════════

# 🔴 这里量的是**自我状态**，不是财富增减 ⇒ 不套「涨红跌绿」。
# 🔴 `miss` 刻意用**灰蓝不用红**：红是「报警」，「这周没做到」是**正常波动**（V3）。
VERDICT_COLORS = {
    'goal': '#10B981',      # 绿 ——「做到了」
    'floor': '#F59E0B',     # 琥珀 ——「保住了」
    'miss': '#94A3B8',      # 灰蓝 —— 刻意不用红
    'empty': '#CBD5E1',     # 中灰 ——「真的没做」
    'unknown': '#CBD5E1',   # 中灰 ——「系统不知道，不是你的错」
}

PERIOD_STATUS_COLORS = {
    'great': '#059669',     # 深绿 —— 比「合格」更实，不用新色相（绿=好，红=差的口径不动）
    'on_track': '#10B981',
    'slipping': '#F59E0B',
    'slid': '#94A3B8',
    'no_record': '#CBD5E1',
    'fallow': '#E5E7EB',    # 中性 —— 休耕不是失败（V4）
}

# KPI 状态
METRIC_STATUS_COLORS = {
    'active': '#10B981',
    'retired': '#CBD5E1',
}


# ══════════════════════════════════════════════════════════════
# 六、其它约定
# ══════════════════════════════════════════════════════════════

# 阶段未配置时的标记：`goal_value` 与 `floor_value` **都为空** ⇒ 该条只展示不判定。
STATE_UNCONFIGURED = 'unconfigured'
STATE_STALE = 'stale'
STATE_OK = 'ok'
STATE_EMPTY = 'empty'

# 周期读数的状态取值（`state` 列，与 `verdict` 正交）
STATE_CHOICES = [
    (STATE_OK, '正常'),
    (STATE_STALE, '数据源过期'),
    (STATE_UNCONFIGURED, '未配置目标'),
    (STATE_EMPTY, '本期无数据'),
]

# 一个阶段同一时间只允许一个 `active` 或 `paused`
OPEN_STAGE_STATUSES = ('active', 'paused')

# 归档后**只读**的 Period 字段（序列化器用同一份，避免两处清单漂移）
PERIOD_FROZEN_FIELDS = (
    'readings',
    'status',
    'config_fingerprint',
    'period_type',
    'period_key',
    'period_start',
    'period_end',
    'is_partial',
    'closed_at',
    'skipped_metric_ids',
    'stage',
)
