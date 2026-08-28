"""为外部表 temporal_oneday_page_list 补充业务查询索引（managed=False，需 RunSQL 直建）"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('temporal', '0002_weeklytimecache'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE INDEX idx_oneday_date ON temporal_oneday_page_list (beginDate);
                CREATE INDEX idx_oneday_type_date ON temporal_oneday_page_list (otype, beginDate);
                CREATE INDEX idx_oneday_year_date ON temporal_oneday_page_list (years, beginDate);
            """,
            reverse_sql="""
                DROP INDEX idx_oneday_date ON temporal_oneday_page_list;
                DROP INDEX idx_oneday_type_date ON temporal_oneday_page_list;
                DROP INDEX idx_oneday_year_date ON temporal_oneday_page_list;
            """,
        ),
    ]
