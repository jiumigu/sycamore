"""生成系统通知（关系静默 / 目标落后 / 文件堆积）。

用法：

    python manage.py generate_notifications
    python manage.py generate_notifications --force     # 忽略 30 分钟节流
    python manage.py generate_notifications --cleanup   # 顺手清理 30 天前已读

为什么要有它：接口侧的 `POST /api/core/notifications/generate/` 依赖前端打开
通知中心才会触发 —— 如果几天没开页面，通知就不会更新。命令给它一个
**不依赖前端**的入口，可以挂 cron（例如每天 08:00）。

🔴 `--cleanup` 是**显式**才删：默认一次都不删。删除范围仅限
   「已读 + 30 天前」，未读通知永远不动。
"""
from django.core.management.base import BaseCommand

from apps.core.notification_service import NotificationService


class Command(BaseCommand):
    help = '生成系统通知（幂等：同一来源只保留一条）'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='忽略节流窗口')
        parser.add_argument('--cleanup', action='store_true', help='清理 30 天前的已读通知')

    def handle(self, *args, **options):
        payload = NotificationService.generate_if_due(force=options['force'])
        if not payload['ran']:
            self.stdout.write(self.style.WARNING(
                '跳过：30 分钟节流窗口内已跑过。加 --force 可强制。'
            ))
            return
        result = payload['result'] or {}
        for item in result.get('checks', []):
            self.stdout.write(
                f"  · {item['check']:<10} {item.get('state')}"
                + (f"  hit={item['hit']}" if 'hit' in item else '')
                + (f"  resolved={item['resolved']}" if item.get('resolved') else '')
            )
        for bad in result.get('failed', []):
            self.stderr.write(self.style.ERROR(f"  ! {bad['check']}: {bad['error']}"))
        if options['cleanup']:
            deleted = NotificationService.cleanup_old(30)
            self.stdout.write(f'清理已读通知 {deleted} 条')
        self.stdout.write(self.style.SUCCESS(
            f"完成：{len(result.get('checks', []))} 项检查，"
            f"{len(result.get('failed', []))} 项失败"
        ))
