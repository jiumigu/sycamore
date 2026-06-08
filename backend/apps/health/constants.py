HEALTH_TARGET_STEPS = 100_000_000  # 1亿步
HEALTH_MILESTONE_SIZE = 2_000_000  # 200万步
HEALTH_TOTAL_MILESTONES = 50

HTYPE_CHOICES = [
    (1, '步数'),
    (2, '跳绳'),
    (3, '跑步'),
    (4, '骑行'),
]

HTYPE_LABELS = {1: '步数', 2: '跳绳', 3: '跑步', 4: '骑行'}

# 每单位 → 步数 转换系数
CONVERSION_RATES = {
    2: 0.5,    # 跳绳: 1个 → 0.5步
    3: 1300,   # 跑步: 1公里 → 1300步
    4: 400,    # 骑行: 1公里 → 400步
}
