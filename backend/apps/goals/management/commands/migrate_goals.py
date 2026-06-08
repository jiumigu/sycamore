"""
从旧数据库 sycamore_db 迁移 Goal 和 Milestone 数据到新数据库 sycamore。

执行: python manage.py migrate_goals
"""

from django.db import connections, transaction

from django.core.management.base import BaseCommand
from apps.goals.models import Goal, Milestone


# 字段映射：旧 → 新
CATEGORY_MAP = {
    'year': 'year',
    'quarter': 'quarter',
    'month': 'month',
    'long-term': 'long-term',
    'career': 'year',
    'learning': 'year',
    'health': 'year',
    'finance': 'year',
    'relationship': 'year',
    'hobby': 'year',
}

PRIORITY_MAP = {
    'high': 'p1',
    'medium': 'p2',
    'low': 'p3',
}

STATUS_MAP = {
    'not-started': 'planning',
    'in-progress': 'in-progress',
    'completed': 'completed',
    'paused': 'paused',
    'overdue': 'in-progress',
}

MILESTONE_STATUS_MAP = {
    0: 'pending',
    1: 'completed',
}


class Command(BaseCommand):
    help = '从 sycamore_db 迁移 Goal 和 Milestone 数据'

    def handle(self, *args, **options):
        old_db = 'old_db'

        if old_db not in connections:
            self.stderr.write('错误: old_db 未配置')
            return

        conn = connections[old_db]

        # 1. 清空新表已有数据（清除测试数据）
        self.stdout.write('清除新表已有数据...')
        Milestone.objects.all().delete()
        Goal.objects.all().delete()
        self.stdout.write('  已清空')

        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM o_goals_info")
            old_goal_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM o_goals_milestones")
            old_milestone_count = cursor.fetchone()[0]
            self.stdout.write(f'旧数据: {old_goal_count} 个目标, {old_milestone_count} 个里程碑')

            # 读取所有旧目标
            cursor.execute("""
                SELECT id, title, description, category, tags, priority, status,
                       progress, start_date, deadline, year, notes,
                       created_at, updated_at, user_id, reward_value,
                       decision_quality, mental_models_used,
                       inversion_check, first_principles,
                       circle_check, happiness_impact, peace_impact
                FROM o_goals_info
                ORDER BY id
            """)
            old_goals = cursor.fetchall()

        # 迁移 Goal
        id_map = {}
        goal_created = 0

        for row in old_goals:
            (
                old_id, title, description, category, tags, priority, status,
                progress, start_date, deadline, year, notes,
                created_at, updated_at, user_id, reward_value,
                decision_quality, mental_models_used,
                inversion_check, first_principles,
                circle_check, happiness_impact, peace_impact,
            ) = row

            new_category = CATEGORY_MAP.get(category, 'year')
            new_priority = PRIORITY_MAP.get(priority, 'p2')
            new_status = STATUS_MAP.get(status, 'planning')

            if old_id in (9, 13):
                self.stdout.write(f'  DEBUG: old_id={old_id} old_status="{status}" → new_status="{new_status}"')

            with transaction.atomic():
                goal = Goal.objects.create(
                    title=title or '',
                    description=description or '',
                    category=new_category,
                    tags=tags if tags else None,
                    priority=new_priority,
                    status=new_status,
                    progress_percentage=progress or 0,
                    start_date=start_date,
                    deadline=deadline,
                    year=year,
                    notes=notes or '',
                    user_id=user_id,
                    reward_value=reward_value or 0,
                    decision_quality=decision_quality or None,
                    mental_models_used=mental_models_used or '',
                    inversion_check=inversion_check or '',
                    first_principles=first_principles or '',
                    circle_check=circle_check or None,
                    happiness_impact=happiness_impact or None,
                    peace_impact=peace_impact or None,
                    created_at=created_at,
                    updated_at=updated_at,
                )
                id_map[old_id] = goal.id
                goal_created += 1

        self.stdout.write(f'已迁移 Goal: {goal_created} 条')

        # 读取旧里程碑
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, goal_id, title, completed, completed_note, order_num,
                       created_at, updated_at
                FROM o_goals_milestones
                ORDER BY goal_id, order_num
            """)
            old_milestones = cursor.fetchall()

        # 迁移 Milestone
        ms_created = 0
        for row in old_milestones:
            (old_id, old_goal_id, title, completed, completed_note, order_num,
             created_at, updated_at) = row

            new_goal_id = id_map.get(old_goal_id)
            if new_goal_id is None:
                self.stderr.write(f'  警告: 里程碑 {old_id} 关联的目标 {old_goal_id} 未迁移，跳过')
                continue

            new_status = MILESTONE_STATUS_MAP.get(completed, 'pending')

            with transaction.atomic():
                Milestone.objects.create(
                    goal_id=new_goal_id,
                    title=title or '',
                    status=new_status,
                    completed_note=completed_note or '',
                    order_num=order_num or 0,
                    created_at=created_at,
                    updated_at=updated_at,
                )
                ms_created += 1

        self.stdout.write(f'已迁移 Milestone: {ms_created} 条')
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'迁移完成: {goal_created} 个目标, {ms_created} 个里程碑'
        ))
        self.stdout.write(f'旧 ID 映射范围: {min(id_map.keys())}~{max(id_map.keys())} → '
                          f'{min(id_map.values())}~{max(id_map.values())}')
