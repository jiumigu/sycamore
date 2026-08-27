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
            description=extra.get('description', '') or inbox_item.content,
            status='pending',
            order_num=max_order + 1,
            target_date=extra.get('target_date') or None,
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

    # CSV 列名（含别名）→ 模型字段
    _CSV_FIELD_ALIASES = {
        'content': ('content', 'title', '内容', '事项'),
        'category': ('category', '类别'),
        'due_date': ('due_date', 'target_date', '截止日期', '日期'),
        'status': ('status', '状态'),
        'priority': ('priority', '优先级'),
        'description': ('description', 'note', '备注', '描述'),
    }

    @staticmethod
    def _normalize_category(value):
        """中文标签/合法 code → 合法 code，非法回退 other"""
        label_map = {
            '待办': 'todo', '想法': 'idea', '痛点': 'pain',
            '提醒': 'reminder', '工作': 'work', '其他': 'other',
        }
        value = (value or '').strip()
        if value in label_map:
            return label_map[value]
        valid = {code for code, _ in InboxItem.CATEGORY_CHOICES}
        return value if value in valid else 'other'

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
        """解析 YYYY-MM-DD，非法返回 None"""
        if not value:
            return None
        try:
            return datetime.strptime(str(value).strip(), '%Y-%m-%d').date()
        except ValueError:
            return None

    @staticmethod
    def parse_csv(content: str) -> list:
        """解析 CSV 内容

        Args:
            content: CSV 全文（首行为列名）

        Returns:
            [{content, category, due_date, status, priority, description}]
        """
        reader = csv.DictReader(StringIO(content))
        items = []
        for row in reader:
            item = {}
            for field, aliases in InboxImportService._CSV_FIELD_ALIASES.items():
                for alias in aliases:
                    raw = row.get(alias)
                    if raw is not None:
                        item[field] = str(raw).strip()
                        break
            content_val = item.get('content', '')
            if content_val:
                items.append({
                    'content': content_val,
                    'category': InboxImportService._normalize_category(item.get('category', '其他')),
                    'due_date': InboxImportService._parse_date(item.get('due_date')),
                    'status': InboxImportService._normalize_status(item.get('status', '待处理')),
                    'priority': InboxImportService._normalize_priority(item.get('priority', '中')),
                    'description': item.get('description', ''),
                })
        return items

    @staticmethod
    def parse_markdown_tasks(content: str) -> list:
        """解析 Markdown 任务列表（- [ ] / - [x]），行尾 (YYYY-MM-DD) 识别为截止日期"""
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
        return items

    @staticmethod
    def parse_plain_text(content: str) -> list:
        """解析纯文本：每行一个任务，跳过标题/分隔线"""
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
        """批量创建收件箱条目

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
                    content=item_data['content'],
                    description=item_data.get('description', ''),
                    category=item_data.get('category', 'other'),
                    due_date=item_data.get('due_date'),
                    status=item_data.get('status', 'pending'),
                    priority=item_data.get('priority', 'medium'),
                    source='import',
                )
                created.append({'id': inbox_item.id, 'content': inbox_item.content})
            except Exception as e:
                failed.append({
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
