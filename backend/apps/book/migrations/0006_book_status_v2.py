"""书籍状态：8 个混维度值 → 6 个生命周期值（v3.64.79）

旧值把「阶段」和「读法」混在一个字段里（精读 / 通读 / 消遣 是读法），
新枚举只留生命周期，读法仍由 `reading_depth` 表达（**一个字节都不动**）。

🔴 这是**多对一**迁移，不可逆：
   `精读 → reading`，`通读 / 消遣 / 已完成 → finished`。
   反向只能回到「最大公约数」（见 BACKWARD），迁过去之后
   「哪些是通读、哪些是消遣」就只剩在 `reading_depth` 与 `readDate` 里了。
   执行前先备份：`db_backups/`。

🔴 映射表**写死在这个文件里**，不从 `models` 或 `constants` import：
   迁移要能独立重放，将来有人改了业务常量，这个文件必须还是当年那份。
   测试 `test_status_migration.py` 读的就是下面这张表 —— 它才是唯一依据。
"""
from django.db import migrations, models

# 旧值 → 新值（8 个旧值，每一个都必须有归宿；漏一个就会静默留在库里，
# 而 MySQL 不会因为 choices 变了就拒绝旧字符串）
FORWARD = {
    '计划阅读': 'to_read',
    '在读': 'reading',
    '精读': 'reading',      # 「正在精读」= 在读的一种
    '通读': 'finished',     # 75 本全部有 readDate，是「读完了」的记录
    '消遣': 'finished',     # 12 本全部有 readDate（2013–2025）、9 本有读后感
    '弃读': 'abandoned',
    '已完成': 'finished',
    '待重读': 'to_read',    # 「待」= 还没开始；rereading 留给「正在二刷」
}

# 反向：多对一只能给最大公约数。`shelved` 历史上没有对应记法，回 to_read。
BACKWARD = {
    'to_read': '计划阅读',
    'reading': '在读',
    'rereading': '待重读',
    'finished': '已完成',
    'shelved': '计划阅读',
    'abandoned': '弃读',
}


def forwards(apps, schema_editor):
    Book = apps.get_model('book', 'Book')
    for old, new in FORWARD.items():
        Book.objects.filter(status=old).update(status=new)


def backwards(apps, schema_editor):
    Book = apps.get_model('book', 'Book')
    for new, old in BACKWARD.items():
        Book.objects.filter(status=new).update(status=old)


class Migration(migrations.Migration):

    dependencies = [
        ('book', '0005_readingfocus'),
    ]

    operations = [
        # 先把数据搬过去，再改枚举 —— 反过来也不影响（choices 只是应用层校验），
        # 但顺序写成「先数据后契约」，读的人不必再想一遍。
        migrations.RunPython(forwards, backwards),
        migrations.AlterModelTableComment(
            name='book',
            table_comment='书籍阅读记录：一张表承载待读 / 在读 / 读完 / 搁置 / 弃读；读法看 reading_depth；列名多为旧式命名（bid / btype / openop / closedop）',
        ),
        migrations.AlterField(
            model_name='book',
            name='status',
            field=models.CharField(blank=True, choices=[('to_read', '待读'), ('reading', '在读'), ('rereading', '在读二刷'), ('finished', '已读完'), ('shelved', '搁置'), ('abandoned', '弃读')], db_comment='状态', max_length=25, null=True, verbose_name='状态'),
        ),
    ]
