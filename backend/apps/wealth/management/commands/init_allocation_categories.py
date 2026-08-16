"""初始化分配类别管理命令"""
from django.core.management.base import BaseCommand

from apps.wealth.models.allocation_plan import AllocationCategory


class Command(BaseCommand):
    help = '初始化默认分配类别（幂等）'

    def handle(self, *args, **options):
        categories = [
            {'name': '投资', 'icon': '📈', 'color': '#409EFF', 'priority': 2, 'default_amount': 0},
            {'name': '日常生活', 'icon': '🛡️', 'color': '#67C23A', 'priority': 1, 'default_amount': 0},
            {'name': '精神愉悦-旅游/美食', 'icon': '🌴', 'color': '#E6A23C', 'priority': 3, 'default_amount': 0},
            {'name': '家居装修', 'icon': '🏠', 'color': '#909399', 'priority': 4, 'default_amount': 0},
            {'name': '风险预估-留底钱', 'icon': '🚨', 'color': '#F56C6C', 'priority': 0, 'default_amount': 0},
        ]

        created = 0
        for data in categories:
            _, was_created = AllocationCategory.objects.get_or_create(
                name=data['name'],
                defaults=data
            )
            if was_created:
                created += 1

        self.stdout.write(self.style.SUCCESS(f'✅ 分配类别初始化完成（新增 {created} 条）'))
