"""移除决策日志模块（DecisionLog 模型 + toolkit_decision_log 表）

对应「工具箱瘦身」：决策日志（记录重大决策 / 分析决策偏误）与「决策追踪器」
（DecisionTracker，长期观察型）是两套独立功能，本次只移除前者。

注意：迁移只负责 DROP TABLE。toolkit_definition 中 tool_key='decision-log' 的
登记行、以及个人画像里的决策质量卡片属另一侧清理，不随本迁移自动消失。
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('toolkit', '0021_remove_review_language_environment'),
    ]

    operations = [
        migrations.DeleteModel(
            name='DecisionLog',
        ),
    ]
