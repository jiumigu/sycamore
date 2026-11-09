"""小确幸快乐程度档位 —— 唯一真源。

5~20 分制，划五档。**档位边界与显示词只在这里出现一次**，三个消费方都读它：

1. `serializers._reward_label()` —— 每条记录下发的 `reward_label`
2. `serializers.get_reward_color()` —— 每条记录下发的 `reward_color`
3. 接口 `GET /api/sugar/records/happiness_bands/` —— 前端录入弹窗的实时预览

为什么要有这个文件：在此之前，同一套档位在四处各写了一遍 ——
后端 `serializers._reward_label`、前端卡片里的 `happinessColor` / `happinessEmoji`、
前端录入弹窗里的 `happinessTexts`、还有一个没人用的 `REWARD_LABELS`。
四份里已经有两份对不上（弹窗说「非常开心」、列表说「很高兴」是同一件事的两种说法）。
**同一个分数只能说一个词** —— 所以边界与词表收到这里一份，前端零副本。
"""

# 快乐程度取值范围（表单与校验共用；前端范围也由 happiness_bands 接口下发）
SUGAR_HAPPINESS_MIN = 5
SUGAR_HAPPINESS_MAX = 20

# 五档：`max_level` 是这一档的上界（含），按升序排列。
# `color` 随档位下发 —— 它不是装饰，而是「一眼扫过去分得出来」的唯一手段：
# 卡片上的进度条去掉之后，档位颜色只剩分数文字这一处承载。
SUGAR_HAPPINESS_BANDS = (
    {'max_level': 7, 'label': '小开心', 'color': '#9CA3AF'},
    {'max_level': 10, 'label': '开心', 'color': '#60A5FA'},
    {'max_level': 13, 'label': '很高兴', 'color': '#34D399'},
    {'max_level': 16, 'label': '超开心', 'color': '#FBBF24'},
    {'max_level': 20, 'label': '幸福爆炸', 'color': '#F97316'},
)

# 派生字典：给「只想要词 / 只想要色」的调用方，避免它们各自遍历一遍
SUGAR_HAPPINESS_LABELS = {b['max_level']: b['label'] for b in SUGAR_HAPPINESS_BANDS}
SUGAR_HAPPINESS_COLORS = {b['max_level']: b['color'] for b in SUGAR_HAPPINESS_BANDS}


# ─── 快乐类型筛选 ───
#
# 🔴「未标注」必须用一个**非空**的值来表达，不能直接传空串。
#    `?joy_type=` 与「压根没传 joy_type」在 query string 里长得一样，
#    `params.get('joy_type')` 两种情况都返回 `''` ⇒ 清空筛选和「只看未标注」
#    会变成同一件事，而失效的那一边**不会报错**（只是少了个筛选条件）。
#    同理前端 `el-select` 的 `clearable` 清空也回 `''` / `undefined`。
JOY_TYPE_UNLABELED_PARAM = '__unlabeled__'

# 「未标注」下拉项的显示词。它**不是**一种快乐类型，是这个字段还没填 ——
# 所以不放进 model 的 choices 里（那会让「未标注」变成一个可选类型）。
JOY_TYPE_UNLABELED_LABEL = '未标注'

# 库里出现、但不在 choices 里的值（早期词表残留）。它们必须能被筛出来，
# 否则下拉里没有、列表里却有 ⇒ 用户永远看不到也清不掉。
JOY_TYPE_LEGACY_SUFFIX = '（旧词表）'


def resolve_happiness_band(level):
    """返回该分数所在的档位 dict（含 max_level / label / color）。

    ⚠️ **不抛异常、也不返回 None**：超出 5~20 时夹取到最近的一档。
    历史数据里有 3.0 / 4.0（早于这条校验上线）与 20.0，若这里报错或留空，
    那几条记录在列表上就会「有分数、没有词」—— 比夹取更难解释。
    低于最低档的落进第一档，高于最高档的落进最后一档。
    """
    value = float(level)
    for band in SUGAR_HAPPINESS_BANDS:
        if value <= band['max_level']:
            return band
    return SUGAR_HAPPINESS_BANDS[-1]
