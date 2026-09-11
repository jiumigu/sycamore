"""图书预设标签：SystemPreset 新增 book_tags 类型并播种默认值"""
from django.db import migrations, models


def seed_book_tags(apps, schema_editor):
    SystemPreset = apps.get_model('core', 'SystemPreset')
    SystemPreset.objects.get_or_create(
        preset_type='book_tags',
        defaults={'values': ['经典必读', '强烈推荐', '值得重读', '思维启发']},
    )


def unseed_book_tags(apps, schema_editor):
    SystemPreset = apps.get_model('core', 'SystemPreset')
    SystemPreset.objects.filter(preset_type='book_tags').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_menugroup_menupreference'),
    ]

    operations = [
        migrations.AlterField(
            model_name='systempreset',
            name='preset_type',
            field=models.CharField(choices=[
                ('tags', '标签预设'),
                ('quick_phrases', '快捷短语（里程碑完成感悟）'),
                ('sugar_tags', '小确幸预设标签'),
                ('diary_tags', '日记流预设标签'),
                ('ask_tags', 'AI 问答库标签'),
                ('book_tags', '图书预设标签'),
            ], max_length=50, unique=True, verbose_name='预设类型'),
        ),
        migrations.RunPython(seed_book_tags, unseed_book_tags),
    ]
