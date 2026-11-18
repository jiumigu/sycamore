"""综合进度看板 — 模块配置与换算规则"""

# ── 模块标识 ──────────────────────────────────────────────
WEALTH = 'wealth'
HEALTH = 'health'
TIMES = 'times'
WORDS = 'words'
SUGAR = 'sugar'
TRAVEL = 'travel'
BOOK = 'book'

# ── 模块元信息 ──────────────────────────────────────────────
MODULE_META: dict[str, dict] = {
    WEALTH: {'label': '财富', 'color': '#F59E0B', 'order': 1},
    HEALTH: {'label': '健康', 'color': '#10B981', 'order': 2},
    TIMES: {'label': '时间投入', 'color': '#6366F1', 'order': 3},
    WORDS: {'label': '文字记录', 'color': '#EC4899', 'order': 7},
    SUGAR: {'label': '小确幸', 'color': '#F97316', 'order': 5},
    TRAVEL: {'label': '旅行', 'color': '#06B6D4', 'order': 6},
    BOOK: {'label': '阅读', 'color': '#3B82F6', 'order': 4},
}

# ── 换算规则 ──────────────────────────────────────────────
# type: 'aggregate' = SUM + divide, 'count' = COUNT rows, 'net_income' = income-expense
#
# 三个系数各司其职，别混用（§120）：
# - divisor      : raw_value → 进度点（如 30 小时 = 1 点），只管评分
# - display_scale: raw_value → 展示值（如 448067 步 = 44.81 万步），只管显示
#   ⚠️ 两者对「时间/小确幸/旅行/阅读」并不相等，前端绝不能拿 unit 自己折算量级
# - points_floor : 评分下限。净收入为负（亏损）时只表示「本维度没产出」，
#   不倒扣总分 —— 亏损本身仍由 raw_value/display_value 如实展示，不是被抹成 0
CONVERSION_RULES: dict[str, dict] = {
    WEALTH: {'type': 'net_income', 'divisor': 10000, 'display_scale': 10000,
             'unit': '万元', 'points_floor': 0.0},
    HEALTH: {'type': 'aggregate', 'field': 'total', 'divisor': 10000,
             'display_scale': 10000, 'unit': '万步'},
    TIMES: {'type': 'aggregate', 'field': 'duration_hours', 'divisor': 30,
            'display_scale': 1, 'unit': '小时'},
    WORDS: {'type': 'aggregate', 'field': 'total', 'divisor': 10000,
            'display_scale': 10000, 'unit': '万字'},
    SUGAR: {'type': 'aggregate', 'field': 'level_of_happiness', 'divisor': 10,
            'display_scale': 1, 'unit': '级'},
    TRAVEL: {'type': 'count', 'display_scale': 1, 'unit': '次'},
    BOOK: {'type': 'count_completed', 'display_scale': 1, 'unit': '本'},
}

# 取不到 / 按 0 计 的原因码（后端下发，前端只查表，不自己拼文案）
ZERO_REASON_NO_DATA = 'no_data'          # 该区间没有任何原始记录（null ≠ 0）
ZERO_REASON_NET_NEGATIVE = 'net_negative'  # 有数据但净流出，评分按 points_floor 计

# ── 年度目标 ──────────────────────────────────────────────
# 🔴 v3.62.43 起**已从总览口径退役**：总览不再有「总分 / 400 分目标」。
#    它把七个不同量纲直接相加（1 本书 = 1 次旅行 = 1 万字 = 1 万步），
#    而且七轴封顶之和（5+50+120+50+50+20+20 = 315）本来就到不了 400，
#    所以那个百分比既不可解释也不可达。
#    仅「季度决策工作台」仍在用（该模块已从页面撤下、组件与接口保留未删）。
YEARLY_TARGET = 400.0
MONTHLY_TARGET_RATIO = 1 / 12  # 33.33 点/月

# ── 覆盖率口径（v3.62.43）──────────────────────────────────
#
# 每个维度从「一个总量」拆成两个正交的量（§123）：
#   coverage  = 有记录的期数 ÷ 该有的期数   —— 回答「有没有断」
#   intensity = 总量 ÷ 有记录的期数         —— 回答「记的时候做了多少」
#
# 期粒度必须是该维度**天然记账的节奏**，不能一律按天：
# 月度收支按月落、读完一本书按月落，按天算会把正常情况误报成断档。
#
# counts_empty：日记页每天会自动建一条空占位（total=0，标题固定），
#   把它算成「有记录」会让文字维度的覆盖率凭空变成 100%。
COVERAGE_SPEC: dict[str, dict] = {
    WEALTH: {
        'period': 'month', 'period_word': '月', 'label': '记账覆盖',
        'intensity_label': '记录月均', 'intensity_unit': '元/月',
    },
    HEALTH: {
        'period': 'day', 'period_word': '天', 'label': '记录覆盖',
        'intensity_label': '记录日均', 'intensity_unit': '步/天',
    },
    TIMES: {
        'period': 'day', 'period_word': '天', 'label': '记录覆盖',
        'intensity_label': '记录日均', 'intensity_unit': '小时/天',
    },
    WORDS: {
        'period': 'day', 'period_word': '天', 'label': '记录覆盖',
        'intensity_label': '记录日均', 'intensity_unit': '字/天',
        'counts_empty': False,   # 空占位不算
    },
    SUGAR: {
        'period': 'day', 'period_word': '天', 'label': '记录覆盖',
        'intensity_label': '记录日均', 'intensity_unit': '级/天',
    },
    TRAVEL: {
        'period': 'month', 'period_word': '月', 'label': '出行覆盖',
        'intensity_label': '出行月均', 'intensity_unit': '次/月',
    },
    BOOK: {
        'period': 'month', 'period_word': '月', 'label': '阅读覆盖',
        'intensity_label': '阅读月均', 'intensity_unit': '本/月',
    },
}

# 「最近 N 天」——用于判断覆盖率是「一直低」还是「最近才断」
RECENT_DAYS = 30

# ── 雷达图最大参考值 ──────────────────────────────────────
RADAR_MAX: dict[str, float] = {
    WEALTH: 10.0,    # 财富封顶 10 万元（不设 100，让"财富满分"可实现）
    HEALTH: 80.0,    # 万步/年
    TIMES: 80.0,     # 千小时级/年
    BOOK: 20.0,      # 阅读封顶 20 本/年（好书要细嚼慢咽）
    SUGAR: 50.0,     # 幸福等级
    TRAVEL: 20.0,    # 旅行次数
    WORDS: 20.0,     # 万字/年
}

MODULE_LIST = [WEALTH, HEALTH, TIMES, WORDS, SUGAR, TRAVEL, BOOK]

# ── 跨维度相关性（v3.64.62）─────────────────────────────────
#
# 🔴 这里**不是**「任意两个维度都能配对」。任意组合会批量制造伪相关：
#    80 个月里总有一些碰巧同涨同跌，n 越大越容易撞出 |r|>0.3。
#    清单是**预先论证过语义**的有限几组 —— 加一组前先回答
#    「这两个量为什么可能互相解释」，答不出来就别加。
#
# 粒度固定按月：日粒度下「今天没记」与「今天真的是 0」分不开，
# 两次缺失就能把相关系数带偏；月粒度下两边各自有记账节奏，缺口更好判。
CORRELATION_MONTH = 'month'

# 少于这么多个共同月份就不算相关系数。
# n=5 时 |r|=0.9 也可能纯属随机 —— 那时该说「样本不足」，不是「强相关」。
CORRELATION_MIN_N = 12

# 强度分档：只看 |rho|（Spearman），不看 r（Pearson）——
# 支出这类量有极端月（单月 4.5 万 vs 常态 5 千），Pearson 会被一两个点绑架。
# 档位标签只在这里定义，前端只查表。
CORRELATION_BANDS: list[tuple[float, str, str]] = [
    (0.5, 'strong', '明显'),
    (0.3, 'weak', '弱'),
    (0.0, 'none', '无明显关系'),
]

# 去掉最高最低各一个月后，|rho| 跌破这个值 ⇒ 标「不稳健」。
# 含义：结论是靠一两个极端月撑起来的，换个月份看就散了。
CORRELATION_ROBUST_MIN = 0.3
# 至少这么多个共同月份才做去极值复核（太少的样本，去掉两个就没意义了）
CORRELATION_ROBUST_MIN_N = 10

# 原因码（后端下发，前端只查表）
CORR_REASON_NO_DATA = 'no_data'            # 该组一个共同月份都没有
CORR_REASON_NOT_ENOUGH = 'not_enough'      # 共同月份 < CORRELATION_MIN_N
CORR_REASON_CONSTANT = 'constant'          # 某一侧常年不变，相关系数无定义

# 配对清单。`left` / `right` 是 metric key，取值见 correlation_service.METRICS。
# `why` 是「这两个量为什么可能相关」—— 答不出来的一律不收。
CORRELATION_PAIRS: list[dict] = [
    {
        'key': 'times_expense',
        'left': 'times', 'right': 'expense',
        'left_label': '投入时间', 'right_label': '支出',
        'unit_left': '小时', 'unit_right': '元',
        'why': '时间投在哪儿，往往也跟着花在哪儿（学习/出行/爱好都要买单）',
    },
    {
        'key': 'times_income',
        'left': 'times', 'right': 'income',
        'left_label': '投入时间', 'right_label': '收入',
        'unit_left': '小时', 'unit_right': '元',
        'why': '谋生期里投入的时间应当换来收入；离职后这条链会断',
    },
    {
        'key': 'expense_sugar',
        'left': 'expense', 'right': 'sugar_level',
        'left_label': '支出', 'right_label': '快乐程度',
        'unit_left': '元', 'unit_right': '级',
        'why': '花得多的月份是不是也过得更开心（或只是记账更勤）',
    },
    {
        'key': 'steps_expense',
        'left': 'steps', 'right': 'expense',
        'left_label': '步数', 'right_label': '支出',
        'unit_left': '步', 'unit_right': '元',
        'why': '出门多→走路多也花钱多；宅着省钱又省步',
    },
    {
        'key': 'steps_sugar',
        'left': 'steps', 'right': 'sugar_level',
        'left_label': '步数', 'right_label': '快乐程度',
        'unit_left': '步', 'unit_right': '级',
        'why': '活动量是否能解释心情 —— 这是「运动改善情绪」的日拱一卒版',
    },
]

# ── 年度回顾（叙事版，v3.64.63）──────────────────────────────
#
# 🔴 这一块**只产出「有时间锚点的事实」**，不产出评价、不建议、不打分。
#    审计报告的原话：「需要先定叙事取自哪里，否则会变成又一张表。」
#    所以这里的判据是：**一条叙事必须能指到时间轴上的某一处**，
#    并且必须引用至少一条真实记录作为证据。指不到时间的（今年读了几本书）
#    留给「年度明细」那张表，不往这里塞。

# 叙事段的类型。加一种之前先回答：它的时间锚点是什么？
RETRO_FIRST = 'first'          # 今年第一条记录
RETRO_GAP = 'gap'              # 最长的一段没有记录（整年缺席也走这里）
RETRO_STAGE = 'stage'          # 人生阶段切换
RETRO_DENSEST = 'densest'      # 连续有记录的最长一段
RETRO_LAST = 'last'            # 今年最后一条记录

# 最多讲几段。超过就按时间轴截断 —— 回顾不是台账，讲不完的年份不需要讲完。
RETRO_MAX_SEGMENTS = 8

# 空档最多讲几段（按长度降序取）。
# 为什么限 3：七个维度各自都有断档，全讲出来就变成「七段抱怨」，
# 真正长的那些反而被淹没。
RETRO_MAX_GAPS = 3

# 日粒度维度的空档阈值：少于这么多天不算「断了」。
# 30 天 = 整整一个自然月。日粒度维度（步数/小确幸/日记/时间）本来就该天天或隔天记，
# 一个月没有记录就是真的停了，不是「这个月没做这件事」。
RETRO_GAP_MIN_DAYS = 30

# 月粒度维度（记账 / 出行 / 阅读）的阈值，单位是「月」。
# 2 个月 ≈ 隔了一个整月没落账；按天算这边天然不适用。
RETRO_GAP_MIN_MONTHS = 2

# 「连续有记录」这一段至少要这么多天才值得讲。
# 太短的连续段是常态，讲出来等于没说。
RETRO_DENSEST_MIN_DAYS = 30

# 阶段切换最多讲几段。一年里正常也就一两次，多的多半是阶段录得太碎。
RETRO_MAX_STAGES = 2

# 少于这么多段就明说「这一年可讲的不多」，而不是硬凑。
RETRO_THIN_SEGMENTS = 3
