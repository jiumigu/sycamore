from django.db import models

# ─── 关系质量 ───
QUALITY_CHOICES = [
    ('nourishing', '滋养型'),
    ('neutral', '中性'),
    ('draining', '消耗型'),
    ('toxic', '有害型'),
]

QUALITY_LABELS = dict(QUALITY_CHOICES)
QUALITY_COLORS = {
    'nourishing': '#10B981',
    'neutral': '#9CA3AF',
    'draining': '#F59E0B',
    'toxic': '#EF4444',
}
QUALITY_ICONS = {
    'nourishing': '🌱',
    'neutral': '⚪',
    'draining': '⚡',
    'toxic': '⚠️',
}

# ─── 关系状态 ───
STATUS_CHOICES = [
    ('active', '保持联系'),
    ('distant', '已疏远'),
    ('paused', '暂停联系'),
    ('ended', '已结束'),
]
STATUS_LABELS = dict(STATUS_CHOICES)

# ─── 互动方式 ───
METHOD_CHOICES = [
    ('meet', '☕ 见面'),
    ('call', '📞 电话'),
    ('wechat', '💬 微信'),
    ('other', '📧 其他'),
]
METHOD_LABELS = dict(METHOD_CHOICES)

# ─── 质量变化 ───
SHIFT_CHOICES = [
    ('improved', '感觉变好了'),
    ('declined', '感觉变差了'),
    ('same', '差不多'),
]
SHIFT_LABELS = dict(SHIFT_CHOICES)

# ─── 能量分阈值 ───
ENERGY_THRESHOLDS = {
    'nourishing': 5,     # avg >= 5 → nourishing
    'neutral': 1,        # avg >= 1 → neutral
    'draining': -3,      # avg >= -3 → draining
    # else → toxic
}

ENERGY_LABELS = [
    (-10, -8, '极度痛苦'),
    (-7, -5, '很消耗'),
    (-4, -1, '有点累'),
    (0, 0, '一般般'),
    (1, 4, '还不错'),
    (5, 7, '很开心'),
    (8, 10, '太棒了！'),
]

ENERGY_REVIEW_DAYS = 20    # 取最近 N 条计算平均能量分
DUE_REMINDER_DAYS = 30     # 超过 N 天未互动视为待提醒
