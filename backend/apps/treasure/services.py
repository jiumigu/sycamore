"""档案 ↔ 实物的关联检索（v3.60.32 入口 3）

🔴 **只做「输入即搜 + 用户显式点选」，绝不按名称自动写入。**
   名称模糊匹配后自动关联是静默错值的经典来源：物件叫「小米扫地机」、
   档案里写「扫地机器人」—— 自动匹配会把两条不相干的东西绑在一起，
   而界面上看起来完全正常（同项目「靠字符串偶然对上」的历史教训）。
"""

from .constants import suggest_category_for_property

LINK_CANDIDATE_LIMIT = 20


def search_link_candidates(search: str, limit: int = LINK_CANDIDATE_LIMIT) -> dict:
    """在两个实物池里按名称搜候选。

    返回 **`{rows, total, limit}` 而不是裸数组**：
    ⚠️ 这里**存在取数上限**，而「只给了前 N 条」必须被说出来 ——
       否则用户搜「空气」看到 20 条会以为总共就这么多。
       （项目硬坑②：有意的 `{rows,total}` 与「被分页包住的裸数组」是两回事，
       后者是假 0。）
    ⚠️ 空搜索词**不给候选**：那只会把两个池子全倒出来，而那不是「搜索」。
    """
    keyword = (search or '').strip()
    if not keyword:
        return {'rows': [], 'total': 0, 'limit': limit}

    # 函数内 import：避免 app registry 未就绪时被模块级 import 拖住
    from apps.wealth.models import SurvivalItem, WealthProperty

    rows: list[dict] = []

    props = (
        WealthProperty.objects.select_related('category')
        .filter(user_id=1, name__icontains=keyword)
        .order_by('name')
    )
    for prop in props:
        category_name = prop.category.name if prop.category_id else ''
        rows.append({
            'kind': 'property',
            'id': prop.id,
            'name': prop.name,
            'source_label': '📦 物件资产',
            'category_name': category_name,
            # 「记录类型建议」的判据：物件状况坏了 ⇒ 前端提示「要不要记成歹物？」
            # ⚠️ 只是**提示**，绝不自动改 record_type（好坏是用户的判断，不是系统推的）。
            'condition': prop.condition,
            'suggest_category': suggest_category_for_property(category_name),
        })

    items = (
        SurvivalItem.objects.select_related('category', 'unit')
        .filter(user_id=1, name__icontains=keyword)
        .order_by('name')
    )
    for item in items:
        rows.append({
            'kind': 'survival_item',
            'id': item.id,
            'name': item.name,
            'source_label': '🛒 物品清单',
            'category_name': item.category.name if item.category_id else '',
            'condition': '',        # 物品清单没有「状况」这把尺子
            'suggest_category': suggest_category_for_property(
                item.category.name if item.category_id else '',
            ),
        })

    total = len(rows)
    return {'rows': rows[:limit], 'total': total, 'limit': limit}
