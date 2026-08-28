"""清理驼峰列名：temporal_oneday_page_list.beginDate→begin_date、updateDate→update_date（外部表需 ALTER，索引自动跟随）"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('temporal', '0003_oneday_indexes'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE temporal_oneday_page_list
                    RENAME COLUMN beginDate TO begin_date,
                    RENAME COLUMN updateDate TO update_date;
            """,
            reverse_sql="""
                ALTER TABLE temporal_oneday_page_list
                    RENAME COLUMN begin_date TO beginDate,
                    RENAME COLUMN update_date TO updateDate;
            """,
        ),
    ]
