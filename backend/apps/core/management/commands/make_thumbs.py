"""为已落盘的图片补生成列表缩略图（v3.64.72）。

🔴 **只新增 `*_thumb.jpg`，不动原图、不改库**：
   缩略图是原图的派生物，`media` JSON 里不存它（URL 由 `thumb_url_for()` 推出来）。
   所以这个命令可以随便重复跑 —— 已生成的会跳过，跑坏了删掉重跑即可。

⚠️ 历史数据必须跑一次，否则列表仍回退原图（新上传的会自动生成）。
"""
from django.apps import apps
from django.core.management.base import BaseCommand

from apps.core.media import has_thumb, make_thumb, thumb_url_for

# 目前带 `media` JSONField 的模型（新增媒体表时往这里加一行）
TARGETS = (
    ('works', 'Work'),
    ('showroom', 'ShowroomCase'),
    ('showroom', 'ShowroomWork'),
)


class Command(BaseCommand):
    help = '为已落盘的图片生成列表缩略图（幂等；只新增 *_thumb.jpg）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='只统计与列出将生成的文件，不写盘',
        )

    def handle(self, *args, **options):
        refs = 0
        urls = []
        for app_label, model_name in TARGETS:
            model = apps.get_model(app_label, model_name)
            for media in model.objects.values_list('media', flat=True).iterator():
                for m in media or []:
                    if not isinstance(m, dict):
                        continue
                    if m.get('type') != 'image' or not m.get('url'):
                        continue
                    refs += 1
                    urls.append(m['url'])

        # 展厅与作品可能引用同一张图 ⇒ 先去重，否则同一文件会被判两次
        unique = list(dict.fromkeys(urls))
        pending = [u for u in unique if not has_thumb(u)]
        self.stdout.write(
            f'媒体引用 {refs} 处 / 去重 {len(unique)} 张图片：'
            f'已生成 {len(unique) - len(pending)}，待生成 {len(pending)}',
        )

        if options['dry_run']:
            for u in pending:
                self.stdout.write(f'  待生成 {thumb_url_for(u)}')
            self.stdout.write(self.style.WARNING('（--dry-run：未写入任何文件）'))
            return

        made = failed = 0
        for u in pending:
            if make_thumb(u):
                made += 1
            else:
                failed += 1

        self.stdout.write(self.style.SUCCESS(f'生成 {made} 张缩略图，失败 {failed} 张'))
        if failed:
            self.stdout.write(self.style.WARNING(
                '失败的会在下次运行重试（原图未动，列表会回退原图）',
            ))
