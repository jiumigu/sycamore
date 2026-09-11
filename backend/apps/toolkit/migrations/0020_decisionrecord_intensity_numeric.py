"""决策记录强度：varchar 枚举「低/中/高」→ PositiveSmallIntegerField(1–5)

旧枚举与新数值的对应关系（按强度位置映射，保留 1/5 两端留给「很弱/很强」）：
    低 → 2    中 → 3    高 → 4
反向迁移按同一区间回退，1/2 → 低、3 → 中、4/5 → 高。
"""
import django.core.validators
from django.db import migrations, models

# 旧字符串 → 新数值（写成字符串，因为执行顺序上此刻该列还是 varchar）
OLD_TO_NEW = {'低': '2', '中': '3', '高': '4'}
# 新数值 → 旧字符串区间（反向迁移用）
NEW_TO_OLD = {'1': '低', '2': '低', '3': '中', '4': '高', '5': '高'}


def forwards(apps, schema_editor):
    """把「低/中/高」就地改写为 '2'/'3'/'4'，为随后的 ALTER 转数值列铺路"""
    DecisionRecord = apps.get_model('toolkit', 'DecisionRecord')
    for old, new in OLD_TO_NEW.items():
        DecisionRecord.objects.filter(intensity=old).update(intensity=new)
    # 兜底：非「低/中/高」的历史脏值统一归到「中」(3)
    DecisionRecord.objects.exclude(intensity__in=list(OLD_TO_NEW.values())).update(intensity='3')


def backwards(apps, schema_editor):
    """列已回退为 varchar，把 1–5 按区间折回旧枚举"""
    DecisionRecord = apps.get_model('toolkit', 'DecisionRecord')
    for new, old in NEW_TO_OLD.items():
        DecisionRecord.objects.filter(intensity=new).update(intensity=old)


class Migration(migrations.Migration):

    dependencies = [
        ('toolkit', '0019_ask_scene_followups'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
        migrations.AlterField(
            model_name='decisionrecord',
            name='intensity',
            field=models.PositiveSmallIntegerField(
                choices=[(1, '很弱'), (2, '弱'), (3, '中'), (4, '强'), (5, '很强')],
                default=3,
                help_text='1–5，数值越大越强烈（旧版「低/中/高」已分别映射为 2/3/4）',
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(5),
                ],
                verbose_name='情绪强度',
            ),
        ),
    ]
