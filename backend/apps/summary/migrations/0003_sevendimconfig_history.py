from django.db import migrations, models


class Migration(migrations.Migration):
    """七维封顶配置 → 版本化历史：加备注/生效状态/配置时间，去 updated_at"""

    dependencies = [
        ('summary', '0002_sevendimconfig'),
    ]

    operations = [
        migrations.AddField(
            model_name='sevendimconfig',
            name='note',
            field=models.CharField(blank=True, default='', max_length=200, verbose_name='备注'),
        ),
        migrations.AddField(
            model_name='sevendimconfig',
            name='is_active',
            field=models.BooleanField(default=True, verbose_name='是否生效'),
        ),
        migrations.AddField(
            model_name='sevendimconfig',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, verbose_name='配置时间'),
            preserve_default=False,
        ),
        migrations.RemoveField(
            model_name='sevendimconfig',
            name='updated_at',
        ),
    ]
