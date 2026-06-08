from django.db import migrations


class Migration(migrations.Migration):
    """为 relationship_interaction 表添加 my_action 字段"""

    dependencies = [
        ('relation', '0003_readerinteraction_interaction_date_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE relationship_interaction ADD COLUMN my_action longtext NOT NULL;",
            reverse_sql="ALTER TABLE relationship_interaction DROP COLUMN my_action;",
        ),
    ]
