"""清理驼峰列名：wealth_balance_list.wageIncome→wageincome、otherIncome→otherincome（外部表需 ALTER）"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('wealth', '0011_remove_fundschedule_reserve_items'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE wealth_balance_list
                    RENAME COLUMN wageIncome TO wageincome,
                    RENAME COLUMN otherIncome TO otherincome;
            """,
            reverse_sql="""
                ALTER TABLE wealth_balance_list
                    RENAME COLUMN wageincome TO wageIncome,
                    RENAME COLUMN otherincome TO otherIncome;
            """,
        ),
    ]
