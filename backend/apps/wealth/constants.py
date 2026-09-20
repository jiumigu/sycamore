"""人生现金流热力图系统常量定义"""

# ──────────────────────────────────────────────────────────────
# 数据层：周历表覆盖范围（wealth_life_week_calendar，61年 × 52周 = 3172 行）
# START_AGE 同时是 global_week_index 的**索引原点**，
# 改动会让全表索引与既有数据整体错位 —— 勿动。
# ──────────────────────────────────────────────────────────────
START_AGE = 18
END_AGE = 78
TOTAL_YEARS = END_AGE - START_AGE + 1  # 61
WEEKS_PER_YEAR = 52
TOTAL_WEEKS = TOTAL_YEARS * WEEKS_PER_YEAR  # 3172

# ──────────────────────────────────────────────────────────────
# 计量窗口：这套人生现金流系统的有效观测范围（2026-09-17 用户定）
# 展示（热力图行）、统计（已度过周数/收支）、推演（可支撑上限）统一按此窗口，
# 前端 HeatmapGrid.vue 的 DISPLAY_START_AGE / DISPLAY_END_AGE 与此保持一致。
#   19 岁起：18 岁那一年无账单记录，整行零值，显示无意义；
#   60 岁止：此后不再维护这套体系，跨度铺太长反而干扰当下。
# 注意：窗口只影响「看哪些、算到哪」，**不删任何数据**。
# ──────────────────────────────────────────────────────────────
WINDOW_START_AGE = 19
WINDOW_END_AGE = 60
WINDOW_YEARS = WINDOW_END_AGE - WINDOW_START_AGE + 1  # 42
WINDOW_WEEKS = WINDOW_YEARS * WEEKS_PER_YEAR  # 2184
WINDOW_START_INDEX = (WINDOW_START_AGE - START_AGE) * WEEKS_PER_YEAR  # 52
WINDOW_END_INDEX = WINDOW_START_INDEX + WINDOW_WEEKS - 1  # 2235


def age_week_to_global_index(age: int, week: int) -> int:
    """年龄(18-78) + 周数(1-52) → 全局索引(0-3171)"""
    return (age - START_AGE) * WEEKS_PER_YEAR + (week - 1)


def global_index_to_age_week(global_index: int) -> tuple[int, int]:
    """全局索引 → (年龄, 周数)"""
    age_offset = global_index // WEEKS_PER_YEAR
    week = global_index % WEEKS_PER_YEAR + 1
    age = START_AGE + age_offset
    return age, week


# ──────────────────────────────────────────────────────────────
# 资产健康指标口径（v3.58.19，财务规划口径纠偏）
# 两条规则：
#   ① 比率类指标必须与**总资产**同分母（含应收借出）—— 分母漏计 lend
#      会让负债率被系统性高估；
#   ② 应急金必须用「月数」而非绝对金额判定 —— 绝对阈值与支出水平脱钩，
#      月支出 1 万与 3 万的人共用一把尺子。
#
#   总资产    = 活期账户 + 公积金 + 应收借出
#   金融资产  = 活期账户 + 公积金（wealth_cash_flow.total 的既有口径，数值不变）
#   净资产    = 总资产 − 负债 = 金融资产 + 借出 − 负债
#   应急金月数 = 现金类资产 ÷ 近 EXPENSE_LOOKBACK_MONTHS 月平均月支出
# ──────────────────────────────────────────────────────────────

# 活期类账户 = 应急金分子：T+0 可取的账户合计。
# 公积金不计入（不可随时支取）；定期存款在 wealth_regular_list 另表管理，同样不计入。
LIQUID_ACCOUNT_FIELDS = (
    'zplay', 'wechat', 'cash',
    'jianbank', 'gongbank', 'zhongbank', 'nongbank',
)

# 月均支出的回看月数
EXPENSE_LOOKBACK_MONTHS = 3

# 应急金判定：目标月数（充足线）与警戒月数
EMERGENCY_MONTHS_TARGET = 6
EMERGENCY_MONTHS_WARN = 3
