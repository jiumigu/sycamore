from django.core.management.base import BaseCommand

from apps.core.models import SystemPreset

DEFAULT_PRESETS = {
    'tags': ['励志', '人生感悟', '写作', '成长', '情感', '职场', '哲思', '幽默', '治愈', '自律'],
    'quick_phrases': [
        '辛苦了，这段时间不容易',
        '做得不错，继续保持',
        '比想象中难，但坚持下来了',
        '下次可以提前准备',
        '这件事让我学到了...',
        '完成了！下一个目标是什么？',
    ],
    'sugar_tags': ['美食', '旅行', '人际关系', '学习成长', '工作成就', '自然', '音乐', '阅读', '运动', '意外惊喜'],
    'diary_tags': [
        '美食', '旅行', '人际关系', '学习成长', '工作成就',
        '自然', '音乐', '阅读', '运动', '意外惊喜', '日常', '思考', '复盘',
    ],
}


class Command(BaseCommand):
    help = '初始化系统预设（标签 / 快捷短语），幂等：已存在的类型保持用户自定义值不覆盖'

    def handle(self, *args, **options):
        created, kept = 0, 0
        for preset_type, values in DEFAULT_PRESETS.items():
            obj, was_created = SystemPreset.objects.update_or_create(
                preset_type=preset_type,
                defaults={'values': values},
            )
            if was_created:
                created += 1
                self.stdout.write(f'创建 [{preset_type}] ({len(values)} 项)')
            else:
                kept += 1
                self.stdout.write(f'已存在 [{preset_type}]，跳过（{len(obj.values)} 项）')

        self.stdout.write(self.style.SUCCESS(f'完成：新建 {created} 个，保留 {kept} 个'))
