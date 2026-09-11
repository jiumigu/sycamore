"""移除三个「死透」模块：复盘工具箱 / 语言训练 / 环境校准

背景（第六轮审计发现）：这三个工具近 30 天与近 7 天写入均为 0，复盘工具箱全表 0 条，
语言训练自 2026-07-06 后无新增，环境校准自 2026-08-04 后无新增，已确认不再使用。

移除内容：
  - ReviewRecord      → toolkit_review_record      （0 行）
  - LanguageTraining  → toolkit_language_training  （1 行，2026-07-06）
  - EnvironmentAudit  → toolkit_environment_audit  （3 行，2026-06-03 / 06-16 / 08-04）

注意：本迁移会 DROP 这三张表，数据不可恢复——执行前请先备份
（db_backups/three_modules_before_removal_20260910.sql）。反向迁移只重建空的表结构。
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('toolkit', '0020_decisionrecord_intensity_numeric'),
    ]

    operations = [
        migrations.DeleteModel(
            name='ReviewRecord',
        ),
        migrations.DeleteModel(
            name='LanguageTraining',
        ),
        migrations.DeleteModel(
            name='EnvironmentAudit',
        ),
    ]
