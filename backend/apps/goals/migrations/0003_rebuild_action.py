from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """重建 Action 表：从旧打卡模型切换到纯记录模型"""

    dependencies = [
        ('goals', '0002_alter_action_options_remove_action_completed_date_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS goals_action",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.CreateModel(
            name='Action',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False, verbose_name='行为ID')),
                ('name', models.CharField(max_length=200, verbose_name='行为名称')),
                ('note', models.TextField(blank=True, null=True, verbose_name='备注说明')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('goal', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='actions', to='goals.goal', verbose_name='所属目标')),
                ('milestone', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='actions', to='goals.milestone', verbose_name='关联里程碑')),
            ],
            options={
                'verbose_name': '行为记录',
                'verbose_name_plural': '行为记录',
                'db_table': 'goals_action',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='action',
            index=models.Index(fields=['goal', 'created_at'], name='goals_acti_goal_id_43c5d6_idx'),
        ),
        migrations.AddIndex(
            model_name='action',
            index=models.Index(fields=['goal', 'milestone'], name='goals_acti_goal_id_cd3ede_idx'),
        ),
    ]
