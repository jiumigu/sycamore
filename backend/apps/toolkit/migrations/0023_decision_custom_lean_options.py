"""决策追踪器支持自定义倾向选项

- DecisionTracker 加 lean_options（JSON 字符串数组，留空用默认三项）
- DecisionRecord.tendency varchar(10)→varchar(50)，去掉固定 choices
（自定义选项的追踪直接把选项文字存进 tendency）

纯 additive：加列 + 加宽，无任何删除，可安全反向。
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('toolkit', '0022_remove_decision_log'),
    ]

    operations = [
        migrations.AddField(
            model_name='decisiontracker',
            name='lean_options',
            field=models.JSONField(
                blank=True, null=True,
                help_text='字符串数组（2–6 项），如 ["想现在买","再等等","不买"]；留空用默认三项（想继续/不想继续/不确定）',
                verbose_name='自定义倾向选项',
            ),
        ),
        migrations.AlterField(
            model_name='decisionrecord',
            name='tendency',
            field=models.CharField(
                help_text='默认追踪存 continue/quit/uncertain；自定义倾向选项的追踪直接存选项文字',
                max_length=50,
                verbose_name='倾向',
            ),
        ),
    ]
