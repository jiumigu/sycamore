"""通知服务：三条检查 + 幂等 + **只读**（不写目标进度）

🔴 这组测试守的是第八轮审计的 P0-2：`NotificationService` 之前全仓 0 调用方、
   表 0 行，而且三条检查里两条本身是坏的（`Interaction.created_at` 用错字段、
   `organize_status` 字段不存在）。三处又都包在 `except: pass` 里，坏了也看不见。
"""
import datetime as dt

import pytest
from django.utils import timezone

from apps.core.models import Notification
from apps.core.notification_service import NotificationService


def _today():
    return timezone.localdate()


# ══════════════════════════════════════════════════════════
# 关系：90 天静默
# ══════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_relations_quiet_creates_notification():
    from apps.relation.models import Interaction, Relationship

    rel = Relationship.objects.create(user_id=1, name='老同学')
    Interaction.objects.create(
        relationship=rel, user_id=1,
        happened_at=timezone.now() - dt.timedelta(days=120), energy_score=5,
    )

    out = NotificationService.check_relations()
    assert out['state'] == 'alerted'
    assert Notification.objects.filter(source_module='relation').count() == 1


@pytest.mark.django_db
def test_relations_recent_interaction_stays_quiet():
    from apps.relation.models import Interaction, Relationship

    rel = Relationship.objects.create(user_id=1, name='同事')
    Interaction.objects.create(
        relationship=rel, user_id=1,
        happened_at=timezone.now() - dt.timedelta(days=3), energy_score=5,
    )

    out = NotificationService.check_relations()
    assert out['state'] == 'ok'
    assert Notification.objects.count() == 0


@pytest.mark.django_db
def test_relations_uses_happened_at_not_created_at():
    """🔴 守字段选择：一条**很久以前发生**、但**今天才补录**的互动。

    旧实现读 `created_at` ⇒ 会认为「刚刚互动过」而不提醒；
    正确口径是 `happened_at` ⇒ 应当提醒。
    """
    from apps.relation.models import Interaction, Relationship

    rel = Relationship.objects.create(user_id=1, name='旧友')
    Interaction.objects.create(
        relationship=rel, user_id=1,
        happened_at=timezone.now() - dt.timedelta(days=200), energy_score=3,
    )

    out = NotificationService.check_relations()
    assert out['state'] == 'alerted', '应按 happened_at 判静默，不是录入时间'


# ══════════════════════════════════════════════════════════
# 目标：只读 + 条件解除要撤下
# ══════════════════════════════════════════════════════════

def _stalled_goal():
    """时间过半（>50%）、里程碑 1/4 完成（25% < 40%）的目标。"""
    from apps.goals.models import Goal, Milestone

    today = _today()
    goal = Goal.objects.create(
        title='测试目标', user_id=1, status='in-progress',
        start_date=today - dt.timedelta(days=80),
        deadline=today + dt.timedelta(days=20),
    )
    Milestone.objects.create(goal=goal, title='m1', status='completed', target_date=today)
    for i in range(3):
        Milestone.objects.create(goal=goal, title=f'm{i + 2}', status='pending',
                                 target_date=today + dt.timedelta(days=i + 1))
    return goal


@pytest.mark.django_db
def test_goals_stalled_creates_alert():
    goal = _stalled_goal()

    out = NotificationService.check_goals()
    assert out['state'] == 'alerted'
    assert Notification.objects.filter(
        source_module='goals', source_object_id=goal.id,
    ).count() == 1


@pytest.mark.django_db
def test_goals_check_does_not_write_progress():
    """🔴 核心：生成通知**不能**顺手改目标进度（旧实现调 `recalculate()` 会 save）。"""
    goal = _stalled_goal()
    before = goal.progress_percentage

    NotificationService.check_goals()

    goal.refresh_from_db()
    assert goal.progress_percentage == before, '只读路径写库了'


@pytest.mark.django_db
def test_goals_resolved_condition_removes_notification():
    """条件解除 ⇒ 通知要撤下，否则「修好了也还在报警」。"""
    from apps.goals.models import Milestone

    goal = _stalled_goal()
    NotificationService.check_goals()
    assert Notification.objects.count() == 1

    # 把剩下的里程碑全完成 ⇒ 进度 100% ⇒ 不再落后
    Milestone.objects.filter(goal=goal).update(status='completed')
    out = NotificationService.check_goals()

    assert out['resolved'] >= 1
    assert Notification.objects.filter(source_module='goals').count() == 0


@pytest.mark.django_db
def test_goals_without_ledger_are_skipped():
    """既没有子目标也没有里程碑 ⇒ 无账本 ⇒ 不报警（不是 0%）。"""
    from apps.goals.models import Goal

    today = _today()
    Goal.objects.create(
        title='无里程碑目标', user_id=1, status='in-progress',
        start_date=today - dt.timedelta(days=90),
        deadline=today + dt.timedelta(days=10),
    )

    out = NotificationService.check_goals()
    assert out['state'] == 'ok'
    assert Notification.objects.count() == 0


# ══════════════════════════════════════════════════════════
# 数字资产：字段名（is_organized 而不是 organize_status）
# ══════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_dams_check_uses_real_field():
    """旧实现在 `organize_status='pending'` 上炸，被 `except: pass` 吞掉。

    这条测试只要不抛异常、且能按 `is_organized` 计数就说明字段对了。
    """
    from apps.dams.models import DamsFileResource

    for i in range(3):
        DamsFileResource.objects.create(name=f'f{i}', path=f'/tmp/f{i}', user_id=1)

    out = NotificationService.check_dams()
    assert out['check'] == 'dams'
    assert out['state'] == 'ok'
    assert out['unorganized'] == 3


# ══════════════════════════════════════════════════════════
# generate_all：失败要能被看见
# ══════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_generate_all_reports_failures_instead_of_swallowing(monkeypatch):
    """一条检查坏了 ⇒ 进 `failed`，其余照跑，**不许静默**。"""
    def boom():
        raise RuntimeError('模拟数据源坏了')

    monkeypatch.setattr(NotificationService, 'check_relations', staticmethod(boom))

    out = NotificationService.generate_all()

    assert len(out['failed']) == 1
    assert '模拟数据源坏了' in out['failed'][0]['error']
    assert len(out['checks']) == 2, '其余两条必须照跑'


@pytest.mark.django_db
def test_generate_all_is_idempotent():
    """同一条件跑两遍 ⇒ 通知仍只有一条（update_or_create）。"""
    _stalled_goal()
    NotificationService.generate_all()
    NotificationService.generate_all()

    assert Notification.objects.filter(source_module='goals').count() == 1
