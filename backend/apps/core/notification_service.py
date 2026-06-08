"""统一通知生成服务——各模块提供数据，此处集中管理通知的生成和清理"""

from datetime import date, timedelta

from django.utils import timezone

from .models import Notification


class NotificationService:
    """统一通知生成服务"""

    @staticmethod
    def generate_all():
        """生成所有模块的待处理通知"""
        NotificationService.check_relations()
        NotificationService.check_goals()
        NotificationService.check_dams()

    @staticmethod
    def check_relations():
        """检查关系模块：90天无审计提醒"""
        try:
            from apps.relation.models import Interaction

            latest = Interaction.objects.order_by('-created_at').first()
            if not latest:
                return

            if latest.created_at.date() < date.today() - timedelta(days=90):
                Notification.objects.update_or_create(
                    source_module='relation',
                    category='reminder',
                    defaults={
                        'title': '关系审计周期到了',
                        'body': '建议本周内完成一次关系审计',
                        'action_url': '/relation',
                    },
                )
        except Exception:
            pass

    @staticmethod
    def check_goals():
        """检查目标模块：进度落后提醒"""
        try:
            from apps.goals.models import Goal
            from apps.goals.services import GoalProgressService

            for goal in Goal.objects.filter(status='in-progress'):
                progress = GoalProgressService.recalculate(goal)
                if goal.deadline and progress < 40:
                    elapsed_days = (date.today() - goal.start_date).days if goal.start_date else 0
                    total_days = (goal.deadline - goal.start_date).days if goal.start_date else 1
                    if total_days > 0 and elapsed_days / total_days > 0.5:
                        Notification.objects.update_or_create(
                            source_module='goals',
                            source_object_id=goal.id,
                            category='alert',
                            defaults={
                                'title': f'目标「{goal.title}」进度落后',
                                'body': f'时间过半，进度仅 {progress:.0f}%',
                                'action_url': '/goals',
                            },
                        )
        except Exception:
            pass

    @staticmethod
    def check_dams():
        """检查数字资产模块：文件整理提醒"""
        try:
            from apps.dams.models import DamsFileResource

            unorganized = DamsFileResource.objects.filter(organize_status='pending').count()
            if unorganized > 50:
                Notification.objects.update_or_create(
                    source_module='dams',
                    category='reminder',
                    defaults={
                        'title': f'有 {unorganized} 个文件待整理',
                        'body': '数字资产中有大量文件尚未整理，建议尽快处理',
                        'action_url': '/dams',
                    },
                )
        except Exception:
            pass

    @staticmethod
    def cleanup_old(days=30):
        """清理超过指定天数的已读通知"""
        cutoff = timezone.now() - timedelta(days=days)
        Notification.objects.filter(is_read=True, created_at__lt=cutoff).delete()
