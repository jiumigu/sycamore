"""作品类型加「绘画作品 / 刺绣作品」，并把「实物」改名「其他手作」（v3.64.30）

⚠️ 这条迁移**不改列类型**（仍是 `varchar(20)`），改的是 `choices` 元数据 ——
   也就是说 `--fake` 也不会留下任何结构差异。它存在的意义是：
   让 Django 的迁移状态与 `constants.WORK_KIND_CHOICES` 对齐，否则
   `makemigrations --check` 永远报一条待生成迁移，把真正的遗漏淹掉。

🔴 为什么「实物」要改名（不是措辞偏好）：
   月度 KPI 现在能按作品类型自动数（`selfrun.readers.works_count` +
   `where.work_kind`）。只要「画」还能被填进「实物」这个桶，
   那条自动数就会**少算一件**，而页面上只显示少一件、不报错。

⚠️ 已有行不会因为本迁移改值：库里 `craft` 一条都没有（2026-11-06 实测），
   所以改名对存量数据零影响。将来若真有 `craft` 行，它只是换了个显示名，
   `kind='craft'` 本身不变。
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('works', '0005_work_media'),
    ]

    operations = [
        migrations.AlterField(
            model_name='work',
            name='kind',
            field=models.CharField(
                choices=[
                    ('article', '文章'),
                    ('model', '模型'),
                    ('template', '模板'),
                    ('checklist', '清单'),
                    ('craft', '其他手作'),
                    ('drawing', '绘画作品'),
                    ('embroidery', '刺绣作品'),
                    ('tutorial', '教程'),
                    ('other', '其他'),
                ],
                db_comment='类型 —— 取值见 constants.WORK_KIND_CHOICES',
                default='other', max_length=20, verbose_name='类型',
            ),
        ),
    ]
