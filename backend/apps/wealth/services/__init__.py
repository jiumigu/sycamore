from .calendar_init import init_week_calendar_for_user, update_lived_status
from .week_aggregator import aggregate_weekly_net_income, get_net_level, current_age_week
from .coverage_calculator import calculate_coverage, calculate_daily_budget
from .monthly_aggregator import aggregate_monthly_days, get_daily_detail, calculate_monthly_summary
from .review_service import get_monthly_review, get_trend_data, get_category_ranking, get_monthly_list, get_compare_data, generate_balance_info
from .cashflow_service import get_cashflow_overview, get_asset_trend, get_snapshot_list, create_or_update_snapshot, copy_last_month, get_cashflow_by_yearmon, sum_liquid_accounts
from .debt_service import (
    aging_bucket,
    get_liability_list, get_liability_summary,
    get_receivable_list, get_receivable_summary,
)
from .asset_service import (
    rollup_items,
    get_account_list, get_account_summary,
    create_account, update_account, delete_account, seed_asset_accounts,
    list_snapshots, get_snapshot_detail, get_snapshot_by_yearmon,
    save_snapshot, delete_snapshot,
    backfill_from_legacy,
)
from .classify_service import (
    match_classify_rule, classify_bill,
    get_rule_list, get_rule_summary,
    create_rule, update_rule, delete_rule, seed_classify_rules,
    preview_rule_impact,
    classify_summary, classify_dimension_totals, get_unclassified_candidates,
    monthly_classified_totals,
    available_periods,
)
from .expense_estimate import (
    estimate_from_buckets, get_monthly_expense_estimate, window_ym_keys,
)
from .ratio_grade import grade_ratio, ratio_meta, all_ratio_meta
from .ratio_service import (
    resolve_asset_source, resolve_asset_series, resolve_asset_position,
    get_ratio_overview, get_ratio_trend, available_anchor_months,
)
# 生存资源盘点（v3.59.0，P3-A 一期）—— 物资侧的算法唯一真源在 survival_calc
from . import survival_calc
from .survival_service import (
    get_category_list, create_category, update_category, delete_category,
    get_unit_list, create_unit, update_unit, delete_unit,
    get_item_list, create_item, update_item, delete_item,
    get_recipe_list, create_recipe, update_recipe, delete_recipe,
    get_analysis as get_survival_analysis,
    seed_survival_defaults, get_meta as get_survival_meta,
)
# 盘点快照（v3.59.0 二期）—— ⚠️ 必须加别名：
# `list_snapshots` / `delete_snapshot` 已被上面的 asset_service（资产快照）占用，
# 不加别名会静默覆盖掉它，而那种错误只有别的模块调错函数时才会暴露。
from .survival_snapshot import (
    take_snapshot as take_survival_snapshot,
    list_snapshots as list_survival_snapshots,
    delete_snapshot as delete_survival_snapshot,
    get_trend as get_survival_trend,
    get_snapshot as get_survival_snapshot,
)
# 实盘盘点（v3.59.3）—— 与上面的「快照」是**两件事**，别当成一回事：
#   快照存**系统算出来的结论**（我以为能撑多久），不需要人动手；
#   盘点存**人填进去的实盘**（实际还剩多少件），必须人动手。
# 这五个函数名与既有服务都不重名（全仓 grep 过），但仍然**一律加限定**：
# `services/__init__` 是一个**扁平命名空间**，`get_worksheet` 这种通用词
# 放在那里早晚会撞（二期 `list_snapshots` 就是这么被 asset_service 占掉的）。
# 模块内部仍用短名 —— 那里有模块名限定，不会歧义。
from .survival_stocktake import (
    get_worksheet as get_survival_worksheet,
    create_stocktake as create_survival_stocktake,
    list_stocktakes as list_survival_stocktakes,
    get_stocktake as get_survival_stocktake,
    delete_stocktake as delete_survival_stocktake,
)
# 库存流水（v3.60.18 · P0）—— 库存**怎么变的**。
# 🔴 **改库存的唯一写口就在这一篇**（见 services/survival_flow.py 头顶三条铁律），
#    `survival_service` 与 `survival_stocktake` 都已改成经由它写数量。
# 四个名字一律加限定：本文件是**扁平命名空间**，`list_flows` / `summarize_flows`
# 这类通用词放在这里早晚会被别的模块占掉（二期 `list_snapshots` 就是这么丢的）。
from .survival_flow import (
    record_flow as record_survival_flow,
    record_batch as record_survival_flow_batch,
    reverse_flow as reverse_survival_flow,
    list_flows as list_survival_flows,
    summarize_flows as summarize_survival_flows,
)
# 必需品基准清单（v3.59.7）—— 回答「我漏了什么」，与「盘点」不是一回事：
#   对账核的是「该有的东西在不在」，盘点核的是「已有的东西数量对不对」。
# 六个名字一律加限定：`get_reconcile` 这种通用词放在这个扁平命名空间里
# 早晚会被别的模块占掉（二期 `list_snapshots` 就是这么丢的）。
from .survival_essential_service import (
    get_essential_list as get_survival_essential_list,
    get_reconcile as get_survival_reconcile,
    create_essential as create_survival_essential,
    update_essential as update_survival_essential,
    delete_essential as delete_survival_essential,
    seed_essentials as seed_survival_essentials,
)
# 组合（v3.59.13）—— 「分开登记、一起下锅」：把几件物品声明成一个可复用的搭配。
# 与基准项挂多件的区别是：**可复用**（任何配方都能引用）、**带每件用量**。
# 三个名字一律加限定（本文件是扁平命名空间，`get_combo_list` 这类词早晚会撞）。
from .survival_combo_service import (
    get_combo_list as get_survival_combo_list,
    create_combo as create_survival_combo,
    update_combo as update_survival_combo,
    delete_combo as delete_survival_combo,
)
# 物件资产（v3.60.0）—— 耐用品台账：会折旧会报废，答案是「年」与「元」。
# 算法唯一真源在 property_calc（与 survival_calc 同地位）。
# ⚠️ `get_category_list` / `create_category` / `update_category` / `delete_category`
#    这几个词已被上面的 survival_service 占用 —— 本文件是**扁平命名空间**，
#    不加限定会**静默覆盖**掉它，而那种错误只有别的模块调错函数时才会暴露
#    （二期 `list_snapshots` 就是这么丢的）。
from . import property_calc
from .property_service import (
    get_category_list as get_property_category_list,
    create_category as create_property_category,
    update_category as update_property_category,
    delete_category as delete_property_category,
    seed_property_categories,
    get_item_list as get_property_item_list,
    get_item as get_property_item,
    create_item as create_property_item,
    update_item as update_property_item,
    delete_item as delete_property_item,
    preview_item as preview_property_item,
    get_summary as get_property_summary,
    get_meta as get_property_meta,
)
__all__ = [
    'init_week_calendar_for_user',
    'update_lived_status',
    'aggregate_weekly_net_income',
    'current_age_week',
    'get_net_level',
    'calculate_coverage',
    'calculate_daily_budget',
    'aggregate_monthly_days',
    'get_daily_detail',
    'calculate_monthly_summary',
    'get_monthly_review',
    'get_trend_data',
    'get_category_ranking',
    'get_monthly_list',
    'get_compare_data',
    'generate_balance_info',
    'get_cashflow_overview',
    'get_asset_trend',
    'get_snapshot_list',
    'create_or_update_snapshot',
    'copy_last_month',
    'get_cashflow_by_yearmon',
    'sum_liquid_accounts',
    'aging_bucket',
    'get_liability_list',
    'get_liability_summary',
    'get_receivable_list',
    'get_receivable_summary',
    'rollup_items',
    'get_account_list',
    'get_account_summary',
    'create_account',
    'update_account',
    'delete_account',
    'seed_asset_accounts',
    'list_snapshots',
    'get_snapshot_detail',
    'get_snapshot_by_yearmon',
    'save_snapshot',
    'delete_snapshot',
    'backfill_from_legacy',
    'match_classify_rule',
    'classify_bill',
    'get_rule_list',
    'get_rule_summary',
    'create_rule',
    'update_rule',
    'delete_rule',
    'seed_classify_rules',
    'preview_rule_impact',
    'classify_summary',
    'classify_dimension_totals',
    'get_unclassified_candidates',
    'monthly_classified_totals',
    'available_periods',
    'grade_ratio',
    'ratio_meta',
    'all_ratio_meta',
    'get_monthly_expense_estimate',
    'estimate_from_buckets',
    'window_ym_keys',
    'resolve_asset_source',
    'resolve_asset_series',
    'resolve_asset_position',
    'get_ratio_overview',
    'get_ratio_trend',
    'available_anchor_months',
    'get_category_list',
    'create_category',
    'update_category',
    'delete_category',
    'get_unit_list',
    'create_unit',
    'update_unit',
    'delete_unit',
    'get_item_list',
    'create_item',
    'update_item',
    'delete_item',
    'get_recipe_list',
    'create_recipe',
    'update_recipe',
    'delete_recipe',
    'get_survival_analysis',
    'seed_survival_defaults',
    'get_survival_meta',
    'take_survival_snapshot',
    'list_survival_snapshots',
    'delete_survival_snapshot',
    'get_survival_trend',
    'get_survival_snapshot',
    'get_survival_worksheet',
    'create_survival_stocktake',
    'list_survival_stocktakes',
    'get_survival_stocktake',
    'delete_survival_stocktake',
    'record_survival_flow',
    'record_survival_flow_batch',
    'reverse_survival_flow',
    'list_survival_flows',
    'summarize_survival_flows',
    'get_survival_essential_list',
    'get_survival_reconcile',
    'create_survival_essential',
    'update_survival_essential',
    'delete_survival_essential',
    'seed_survival_essentials',
    'get_survival_combo_list',
    'create_survival_combo',
    'update_survival_combo',
    'delete_survival_combo',
]
