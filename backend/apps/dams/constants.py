from django.db import models

# ─── 文件分类 ───
FILE_CATEGORY_CHOICES = [
    ('document', '文档'),
    ('image', '图片'),
    ('video', '视频'),
    ('audio', '音频'),
    ('archive', '压缩包'),
    ('code', '代码'),
    ('executable', '可执行文件'),
    ('other', '其他'),
]
FILE_CATEGORY_LABELS = dict(FILE_CATEGORY_CHOICES)

# ─── 注意力分区 ───
ATTENTION_ZONE_COLORS = {
    'red': '#EF4444',
    'blue': '#3B82F6',
    'green': '#10B981',
    'gray': '#9CA3AF',
}

ATTENTION_ZONE_LABELS = {
    'red': '高频混乱 — 需整理',
    'blue': '低频有序 — 可归档',
    'green': '正常有序 — 健康态',
    'gray': '未访问/未分类',
}
