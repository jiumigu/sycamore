import csv
import re
from datetime import datetime
from io import StringIO

from django.db import models, transaction
from django.utils import timezone

from .models import InboxItem


class ConverterService:
    """收件箱条目转换服务——将条目转为其他模块的数据"""

    @staticmethod
    def convert_to_goal(inbox_item, **extra):
        """转为目标，返回 (target_type, target_id)"""
        from apps.goals.models import Goal

        goal = Goal.objects.create(
            title=inbox_item.content,
            description=inbox_item.description or '',
            category='month',
            status='planning',
            priority=extra.get('priority', 'p2'),
            user_id=inbox_item.user_id,
        )
        return 'goal', goal.id

    @staticmethod
    def convert_to_milestone(inbox_item, **extra):
        """转为里程碑，返回 (target_type, target_id)"""
        from apps.goals.models import Goal, Milestone
        from apps.goals.services import GoalProgressService

        goal_id = extra.get('goal_id')
        if not goal_id:
            raise ValueError('转为里程碑需要指定目标ID')

        goal = Goal.objects.get(id=goal_id)
        milestone_name = extra.get('milestone_name', '') or inbox_item.content

        max_order = goal.milestones.aggregate(
            max_order=models.Max('order_num')
        )['max_order'] or 0

        milestone = Milestone.objects.create(
            goal=goal,
            title=milestone_name,
            # 详细描述兜底链：前端显式传的 > 待办详细描述 > 待办内容
            description=extra.get('description') or inbox_item.description or inbox_item.content,
            status='pending',
            order_num=max_order + 1,
            # 截止日期兜底链：前端显式传的 > 待办截止日期
            target_date=extra.get('target_date') or inbox_item.due_date or None,
        )

        GoalProgressService.recalculate(goal)
        return 'milestone', milestone.id

    @staticmethod
    def convert_to_sugar(inbox_item, **extra):
        """转为能量清单模板，返回 (target_type, target_id)"""
        from apps.sugar.models import EnergyTemplate

        template = EnergyTemplate.objects.create(
            content=inbox_item.content,
            default_energy=extra.get('energy', 2),
            category=extra.get('category', 'daily'),
            is_system=False,
            user_id=inbox_item.user_id,
        )
        return 'sugar', template.id

    @classmethod
    def process(cls, inbox_item, action, **extra):
        """统一处理入口——执行转换并记录日志"""
        from .models import InboxProcessLog

        target_type = None
        target_id = None

        if action == 'complete':
            inbox_item.status = 'done'
            inbox_item.processed_at = timezone.now()

        elif action == 'convert_to_goal':
            target_type, target_id = cls.convert_to_goal(inbox_item, **extra)
            inbox_item.target_type = target_type
            inbox_item.target_id = target_id
            inbox_item.status = 'processed'
            inbox_item.processed_at = timezone.now()

        elif action == 'convert_to_milestone':
            target_type, target_id = cls.convert_to_milestone(inbox_item, **extra)
            inbox_item.target_type = target_type
            inbox_item.target_id = target_id
            inbox_item.status = 'processed'
            inbox_item.processed_at = timezone.now()

        elif action == 'convert_to_sugar':
            target_type, target_id = cls.convert_to_sugar(inbox_item, **extra)
            inbox_item.target_type = target_type
            inbox_item.target_id = target_id
            inbox_item.status = 'processed'
            inbox_item.processed_at = timezone.now()

        elif action == 'archive':
            inbox_item.status = 'archived'

        inbox_item.save()

        InboxProcessLog.objects.create(
            inbox=inbox_item,
            action=action,
            target_type=target_type,
            target_id=target_id,
            notes=extra.get('notes', ''),
            user_id=inbox_item.user_id,
        )

        return inbox_item


class InboxImportService:
    """收件箱批量导入服务"""

    # 优先级 code → 中文标签（写入备注）
    _PRIORITY_LABEL = {'high': '高', 'medium': '中', 'low': '低'}

    @staticmethod
    def _first_value(row, aliases):
        """取行中第一个非空别名对应的值，无则返回空串"""
        for alias in aliases:
            val = row.get(alias)
            if val and str(val).strip():
                return str(val).strip()
        return ''

    @staticmethod
    def _normalize_status(value):
        """中文标签/合法 code → 合法 code，非法回退 pending"""
        label_map = {
            '待处理': 'pending', '犹豫中': 'hesitating', '已处理': 'processed',
            '已完成': 'done', '已归档': 'archived', '已废弃': 'abandoned',
        }
        value = (value or '').strip()
        if value in label_map:
            return label_map[value]
        valid = {code for code, _ in InboxItem.STATUS_CHOICES}
        return value if value in valid else 'pending'

    @staticmethod
    def _normalize_priority(value):
        """中文标签/合法 code → 合法 code，非法回退 medium"""
        label_map = {'高': 'high', '中': 'medium', '低': 'low'}
        value = (value or '').strip()
        if value in label_map:
            return label_map[value]
        return value if value in ('high', 'medium', 'low') else 'medium'

    @staticmethod
    def _parse_date(value):
        """解析多格式日期，非法返回 None

        支持：2026-08-25 / 2026/8/25 / 2026年8月25日 / 2026.8.25 /
        20260825 / 8/25/2026，最后回退 dateutil 模糊解析
        """
        if not value:
            return None
        raw = str(value).strip()
        if not raw:
            return None
        for fmt in (
            '%Y-%m-%d', '%Y/%m/%d', '%Y年%m月%d日', '%Y.%m.%d',
            '%Y%m%d', '%m/%d/%Y', '%d/%m/%Y',
        ):
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                continue
        try:
            from dateutil import parser as dateutil_parser
            return dateutil_parser.parse(raw, fuzzy=True).date()
        except Exception:
            return None

    @staticmethod
    def _resolve_category(raw):
        """`category` 列 → `(类别 code, 阶段名)`。

        🔴 旧模板把**备考阶段**（基础期/强化期）写在 category 列，真正类别被写死成
           `study`（2026-11-09 修）。一条规则分流，不猜：
           值命中 `CATEGORY_CHOICES` 的 code 或中文标签 ⇒ 当类别；
           不命中 ⇒ 当阶段名（进 tags），类别落 `other`。
        🔴 空值 ⇒ `other`，不是 `study` —— 默认值不该替用户选一个他从没用过的类别。
        """
        value = (raw or '').strip()
        if not value:
            return 'other', ''
        for code, label in InboxItem.CATEGORY_CHOICES:
            if value in (code, label):
                return code, ''
        return 'other', value

    @staticmethod
    def parse_csv(content: str) -> dict:
        """解析 CSV → `{'items': [...], 'skipped': [{row, content, reason}]}`

        🔴 三处硬编码已拆（2026-11-09）：
           1. 类别不再写死 `study`，读行内 `category` / `类别` / `分类`，见 `_resolve_category`；
           2. tags 不再无条件前缀「备考」，读行内 `tags` / `标签`；旧模板的 category 列
              （阶段名）由 `_resolve_category` 归入 tags；
           3. 缺标题、日期解析不了的行**不再 `continue` 静默吃掉** ⇒ 进 `skipped` 带行号。
              「成功 3 失败 2」说不出是哪两行，等于没报。
        `row` 是文件里的物理行号（`DictReader.line_num`，表头算第 1 行）。

        Returns:
            {'items': [{content, category, tags, due_date, status, priority, description, _row}],
             'skipped': [{row, content, reason}]}
        """
        reader = csv.DictReader(StringIO(content))
        items, skipped = [], []
        for row in reader:
            row_no = reader.line_num
            title = InboxImportService._first_value(row, ('content', 'title', '内容', '事项'))
            if not title:
                skipped.append({
                    'row': row_no, 'content': '',
                    'reason': '缺少标题列（content / title / 内容 / 事项）',
                })
                continue

            category, legacy_stage = InboxImportService._resolve_category(
                InboxImportService._first_value(row, ('category', '类别', '分类'))
            )
            stage = InboxImportService._first_value(row, ('阶段', 'stage'))
            date_str = InboxImportService._first_value(row, ('due_date', 'target_date', '截止日期', '日期'))
            status_raw = InboxImportService._first_value(row, ('status', '状态'))
            priority_raw = InboxImportService._first_value(row, ('priority', '优先级'))
            description = InboxImportService._first_value(row, ('description', 'note', '备注', '描述'))
            tags_raw = InboxImportService._first_value(row, ('tags', '标签'))

            due_date = InboxImportService._parse_date(date_str) if date_str else None
            if date_str and due_date is None:
                skipped.append({
                    'row': row_no, 'content': title[:60],
                    'reason': f'截止日期无法解析：{date_str}',
                })
                continue

            status = (
                'done' if status_raw in ('已完成', '完成', '已办', 'done')
                else InboxImportService._normalize_status(status_raw)
            )
            priority = InboxImportService._normalize_priority(priority_raw)

            note_parts = []
            if stage:
                note_parts.append(f'[阶段: {stage}]')
            if priority_raw and priority != 'medium':
                note_parts.append(f'[优先级: {InboxImportService._PRIORITY_LABEL.get(priority, priority)}]')
            if description:
                note_parts.append(description)
            note = ' '.join(note_parts)

            tags = ','.join(t for t in (tags_raw, stage, legacy_stage) if t)

            items.append({
                'content': title,
                'category': category,
                'tags': tags,
                'due_date': due_date,
                'status': status,
                'priority': priority,
                'description': note,
                '_row': row_no,
            })
        return {'items': items, 'skipped': skipped}

    @staticmethod
    def parse_markdown_tasks(content: str) -> dict:
        """解析 Markdown 任务列表（- [ ] / - [x]），行尾 (YYYY-MM-DD) 识别为截止日期。

        返回结构与 `parse_csv` 一致（`{'items', 'skipped'}`）—— 三种解析器签名统一，
        视图层不必按格式分支取数。
        """
        items = []
        for line in content.split('\n'):
            match = re.match(r'^\s*-\s*\[([ xX])\]\s*(.+)$', line)
            if not match:
                continue
            is_done = match.group(1).lower() == 'x'
            title = match.group(2).strip()
            date_match = re.search(r'\((\d{4}-\d{2}-\d{2})\)\s*$', title)
            due_date = date_match.group(1) if date_match else None
            if date_match:
                title = title[:date_match.start()].strip()
            if not title:
                continue
            items.append({
                'content': title,
                'category': 'other',
                'due_date': InboxImportService._parse_date(due_date),
                'status': 'done' if is_done else 'pending',
                'priority': 'medium',
                'description': '',
            })
        return {'items': items, 'skipped': []}

    @staticmethod
    def parse_plain_text(content: str) -> dict:
        """解析纯文本：每行一个任务，跳过标题/分隔线。返回结构同 `parse_csv`。"""
        items = []
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue
            if line.startswith('#') or line.startswith('---'):
                continue
            items.append({
                'content': line,
                'category': 'other',
                'due_date': None,
                'status': 'pending',
                'priority': 'medium',
                'description': '',
            })
        return items

    @staticmethod
    def import_items(user_id: int, items: list) -> dict:
        """批量创建收件箱条目（支持 tags / priority）

        Args:
            user_id: 用户ID
            items: 解析后的条目列表

        Returns:
            {created, failed, total, success_count, failed_count}
        """
        created = []
        failed = []
        for item_data in items:
            try:
                inbox_item = InboxItem.objects.create(
                    user_id=user_id,
                    content=item_data['content'][:500],
                    description=item_data.get('description', ''),
                    category=item_data.get('category', 'other'),
                    tags=item_data.get('tags', '') or None,
                    due_date=item_data.get('due_date'),
                    status=item_data.get('status', 'pending'),
                    priority=item_data.get('priority', 'medium'),
                    source='import',
                )
                created.append({'id': inbox_item.id, 'content': inbox_item.content})
            except Exception as e:
                # 行号一路带到前端：只说「失败 2 条」用户无法定位（2026-11-09）
                failed.append({
                    'row': item_data.get('_row'),
                    'content': item_data.get('content', '未知'),
                    'error': str(e),
                })

        return {
            'created': created,
            'failed': failed,
            'total': len(items),
            'success_count': len(created),
            'failed_count': len(failed),
        }
