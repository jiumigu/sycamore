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
