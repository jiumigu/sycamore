"""展厅的口径单一真源。

技能熟练度三级是唯一的枚举；案例时间标签是自由文本、作品/案例/技能
都是策展清单，没有其它需要下发的枚举。
"""

SKILL_LEVEL_CHOICES = [
    ('expert', '精通'),
    ('proficient', '熟练'),
    ('familiar', '了解'),
]

# 界面选项与模型 choices 同源 —— 前端下拉直接用，不自己拼文案。
SKILL_LEVEL_OPTIONS = [
    {'value': value, 'label': label} for value, label in SKILL_LEVEL_CHOICES
]
