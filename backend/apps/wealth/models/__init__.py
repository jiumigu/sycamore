from .wealth_models import (
    WealthLifeWeekCalendar,
    WealthCurrentScenario,
    WealthScenarioHistory,
    WealthCashFlow,
    WealthBalanceList,
    WealthRegularList,
    WealthBillList,
    WealthLiabilityDetail,
    WealthReceivableDetail,
    WealthAssetAccount,
    WealthAssetSnapshot,
    WealthAssetSnapshotItem,
    WealthClassifyRule,
)
# 生存资源盘点（v3.59.0，P3-A 一期）—— 物资侧，与上面的金融资产体系刻意分开命名
from .survival_models import (
    SurvivalCategory,
    SurvivalUnit,
    SurvivalItem,
    SurvivalEssential,
    SurvivalRecipe,
    SurvivalRecipeLine,
    SurvivalCombo,
    SurvivalComboItem,
    SurvivalRecipeComboLine,
    SurvivalSnapshot,
    SurvivalSnapshotCategory,
    SurvivalStocktake,
    SurvivalStocktakeLine,
    SurvivalFlow,
)
# 物件资产（v3.60.0）—— 耐用品台账：会折旧会报废，答案是「年」与「元」
from .property_models import (
    WealthPropertyCategory,
    WealthProperty,
)
# 身上之物（v3.62.4）—— 「我该有什么、找到了没有」：不靠任何数量，只记结论。
# ⚠️ 必须排在上面两个之后：body_models 的 FK 分别指向 wealth_property 与
#    wealth_survival_item，两者都得先被 import。
from .body_models import (
    WealthBodyPart,
    WealthBodyNeed,
)
__all__ = [
    'WealthLifeWeekCalendar',
    'WealthCurrentScenario',
    'WealthScenarioHistory',
    'WealthCashFlow',
    'WealthBalanceList',
    'WealthRegularList',
    'WealthBillList',
    'WealthLiabilityDetail',
    'WealthReceivableDetail',
    'WealthAssetAccount',
    'WealthAssetSnapshot',
    'WealthAssetSnapshotItem',
    'WealthClassifyRule',
    'SurvivalCategory',
    'SurvivalUnit',
    'SurvivalItem',
    'SurvivalEssential',
    'SurvivalRecipe',
    'SurvivalRecipeLine',
    'SurvivalCombo',
    'SurvivalComboItem',
    'SurvivalRecipeComboLine',
    'SurvivalSnapshot',
    'SurvivalSnapshotCategory',
    'SurvivalStocktake',
    'SurvivalStocktakeLine',
    'SurvivalFlow',
    'WealthPropertyCategory',
    'WealthProperty',
    'WealthBodyPart',
    'WealthBodyNeed',
]
