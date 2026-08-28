"""为外部表 health_step_info 补充业务查询索引（managed=False，需 RunSQL 直建）"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('health', '0004_alter_menstrualrecord_options_weightgoaladjustment'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE INDEX idx_health_time ON health_step_info (time);
            """,
            reverse_sql="""
                DROP INDEX idx_health_time ON health_step_info;
            """,
        ),
    ]
