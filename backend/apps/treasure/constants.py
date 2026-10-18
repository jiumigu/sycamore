"""好恶物档案馆的口径单一真源（v3.60.32）

本文件是「类别文案 / 记录对象 / 方法归类」的**唯一**存放处。
前端不写第二份 label —— 与项目「阈值只在后端一份」同源（MEMORY.md §19–§21）。

## 三条设计判据（照抄会踩坑的地方）

1. 🔴 **类别 key 好 / 歹共用，label 两侧各一套。**
   原因不是省事：存量歹物已有 `吃` / `用` 三个值，若让两侧各存一套 key，
   迁移就变成一次**值重写** —— 而值重写漏掉一条映射就是静默错值（行还在、意思变了）。
   key 共用 + label 分流，达到同样的观感，迁移面却是零。

2. 🔴 **`方法` 不在这里。**
   它回答的是「这东西是实物还是一种做法」，与 `吃 / 穿 / 用` 回答的
   「这东西干嘛用的」**不在同一个维度**。混在一个互斥枚举里，它必然变成兜底桶
   （实测占 74%，里面装着人、公众号、课程、App 价格）。
   它已升格为 `subject_kind`（记录对象），见 §三。

3. ⚠️ **label 自带褒贬，所以必须按侧取。**
   `好店 / 好地方` 配一条 👎 歹物，就是在录入框里当场自相矛盾。
"""

# ──────────────────────────────────────────────────────────────
# 一、类别（好 / 歹 共用 key）
# ──────────────────────────────────────────────────────────────

CATEGORY_KEYS = ('吃', '穿', '用', '店', '地方', '服务')

CATEGORY_LABELS_BY_TYPE = {
    '好': {
        '吃': '🍽️ 好吃好喝',
        '穿': '👔 好穿',
        '用': '🧴 好用',
        '店': '🏪 好店',
        '地方': '📍 好地方',
        '服务': '🔧 好服务',
    },
    '歹': {
        '吃': '🤢 难吃',
        '穿': '👕 难穿',
        '用': '🧻 不好用',
        '店': '🏪 坑店',
        '地方': '📍 别去',
        '服务': '📱 坑人的服务',
    },
}

# 模型 `choices` 用中性文案：它只服务 Django 的校验与 admin 显示。
# 🔴 界面上的 label **一律**走 `CATEGORY_LABELS_BY_TYPE`，不走 `get_category_display()`
#    —— 后者拿不到 `record_type`，永远分不了侧。
CATEGORY_CHOICES = [(key, key) for key in CATEGORY_KEYS]


def category_label(record_type: str, key: str) -> str:
    """按侧取类别文案；取不到就原样返回 key（不返回空串）。

    ⚠️ 返回空串会让前端那一格**静默空着**，看起来像「这条记录没类别」；
       原样返回 key 至少能让人看出是「文案没配」，而不是「数据没有」。
    """
    return CATEGORY_LABELS_BY_TYPE.get(record_type, {}).get(key) or key


def categories_for(record_type: str) -> list[dict]:
    """某一侧的类别选项 —— 前端下拉直接用，不自己拼文案。"""
    labels = CATEGORY_LABELS_BY_TYPE.get(record_type, {})
    return [{'value': key, 'label': labels.get(key, key)} for key in CATEGORY_KEYS]


# ──────────────────────────────────────────────────────────────
# 二、记录对象（subject_kind）—— 它决定显示哪些字段
# ──────────────────────────────────────────────────────────────

SUBJECT_KIND_PHYSICAL = '实物'
SUBJECT_KIND_METHOD = '方法'

# ⚠️ `choices`（模型用）与 `options`（接口下发）必须**同源** ——
#    各写一份的下场是「下拉里有、模型不认」或反过来，两种都是到保存/迁移才现形。
SUBJECT_KIND_CHOICES = [
    (SUBJECT_KIND_PHYSICAL, '📦 实物'),
    (SUBJECT_KIND_METHOD, '💡 方法'),
]

_SUBJECT_KIND_HINTS = {
    SUBJECT_KIND_PHYSICAL: '有实体的东西：吃的、用的、一家店、一个地方',
    SUBJECT_KIND_METHOD: '一种做法、一套流程、一条经验 —— 没有实物样',
}

SUBJECT_KIND_OPTIONS = [
    {'value': value, 'label': label, 'hint': _SUBJECT_KIND_HINTS.get(value, '')}
    for value, label in SUBJECT_KIND_CHOICES
]

# ──────────────────────────────────────────────────────────────
# 三、方法归类（仅方法型使用，可留空）
# ──────────────────────────────────────────────────────────────

METHOD_GROUP_KEYS = ('生活', '工作', '学习', '工具', '人际', '其他')

METHOD_GROUP_CHOICES = [(key, key) for key in METHOD_GROUP_KEYS]

METHOD_GROUP_OPTIONS = [
    {'value': key, 'label': key} for key in METHOD_GROUP_KEYS
]

# ──────────────────────────────────────────────────────────────
# 四、徽标（回流到物件资产 / 物品清单的值）
# ──────────────────────────────────────────────────────────────

BADGE_GOOD = '好'
BADGE_BAD = '歹'


# ──────────────────────────────────────────────────────────────
# 五、关联物件时的类别**预填建议**
# ──────────────────────────────────────────────────────────────

# ⚠️ 这是**猜**，所以只用作表单预填（用户看得见、能改），
#    绝不参与任何校验、也绝不参与写入决策。
#    物件资产的类别是**用户可自定义**的（`wealth_property_category`），
#    所以只能按关键词碰运气 —— 碰不中就返回空串，让用户自己选，
#    而不是硬塞一个「看着合理」的值（那就是假话的源头）。
_PROPERTY_CATEGORY_HINTS = (
    ('家电', '用'), ('家具', '用'), ('数码', '用'), ('厨具', '用'),
    ('工具', '用'), ('日用', '用'), ('电子', '用'),
    ('衣', '穿'), ('服饰', '穿'), ('鞋', '穿'),
    ('食品', '吃'), ('饮料', '吃'),
    ('店', '店'), ('服务', '服务'),
)


def suggest_category_for_property(property_category_name: str) -> str:
    """物件资产类别名 → 档案类别 key 的预填建议；猜不出就返回空串。"""
    name = (property_category_name or '').strip()
    if not name:
        return ''
    for keyword, category in _PROPERTY_CATEGORY_HINTS:
        if keyword in name:
            return category
    return ''
