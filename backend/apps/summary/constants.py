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
CONVERSION_RULES: dict[str, dict] = {
    WEALTH: {'type': 'net_income', 'divisor': 10000, 'unit': '万元'},
    HEALTH: {'type': 'aggregate', 'field': 'total', 'divisor': 10000, 'unit': '万步'},
    TIMES: {'type': 'aggregate', 'field': 'duration_hours', 'divisor': 30, 'unit': '小时'},
    WORDS: {'type': 'aggregate', 'field': 'total', 'divisor': 10000, 'unit': '万字'},
    SUGAR: {'type': 'aggregate', 'field': 'level_of_happiness', 'divisor': 10, 'unit': '级'},
    TRAVEL: {'type': 'count', 'unit': '次'},
    BOOK: {'type': 'count_completed', 'unit': '本'},
}

# ── 年度目标 ──────────────────────────────────────────────
YEARLY_TARGET = 400.0
MONTHLY_TARGET_RATIO = 1 / 12  # 33.33 点/月

# ── 雷达图最大参考值 ──────────────────────────────────────
RADAR_MAX: dict[str, float] = {
    WEALTH: 100.0,
    HEALTH: 80.0,
    TIMES: 80.0,
    BOOK: 60.0,
    SUGAR: 50.0,
    TRAVEL: 20.0,
    WORDS: 20.0,
}

MODULE_LIST = [WEALTH, HEALTH, TIMES, WORDS, SUGAR, TRAVEL, BOOK]
