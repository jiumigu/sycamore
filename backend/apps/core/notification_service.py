"""统一通知生成服务 —— 各模块提供数据，此处集中管理通知的生成与清理。

🔴 2026-10-18 之前，本服务是**死代码**：全仓 0 个调用方、表 0 行，
   而且三条检查里有两条本身就是坏的（见下）。现在它被真正接线了。

## 修掉的三个静默失败

| 检查 | 原来的写法 | 问题 |
|---|---|---|
| 关系 | `Interaction.created_at` | 字段是**录入时间**，不是互动时间；语义应是 `happened_at` |
| 目标 | `GoalProgressService.recalculate(goal)` | 它内部 `goal.save()` —— **在只读路径上写库**，而且会把用户手填的进度覆盖成里程碑比例 |
| 文件 | `organize_status='pending'` | 该字段**不存在**（真字段是 `is_organized` 布尔）⇒ 必然抛异常 |

三处又都包在 `try: ... except Exception: pass` 里 ⇒ 抛了也看不见。
现在：**异常不再吞掉**，逐条记录到返回值的 `failed` 里，同时 `logger.exception`。

## 调用方式

1. `POST /api/core/notifications/generate/` —— 前端打开通知中心时调用，30 分钟内只跑一次；
2. `python manage.py generate_notifications` —— 需要手动/定时跑时用（可配 cron）。

两条都幂等：同一个 `(source_module, source_object_id)` 只会有一行，
`update_or_create` 保证重复执行不产生重复通知。
"""
import logging
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone

from .models import Notification

logger = logging.getLogger(__name__)

# ── 阈值（只在这里一份，前端 0 个数字）──────────────────────────
RELATION_QUIET_DAYS = 90      # 关系互动静默超过这么多天 → 提醒
GOAL_STALL_PROGRESS = 40      # 进度低于这个数
GOAL_STALL_ELAPSED = 0.5      # 且时间已过这个比例 → 报警
DAMS_UNORGANIZED = 50         # 待整理文件超过这个数 → 提醒
GENERATE_THROTTLE_SECONDS = 30 * 60

THROTTLE_KEY = 'core.notification.generate.last'


def _today():
    """🔴 一律走 `timezone.localdate()`：`date.today()` 在 `USE_TZ=True` 下
    取的是服务器本地日期，与项目时区（Asia/Shanghai）未必一致。"""
    return timezone.localdate()


def _upsert(source_module, source_object_id, category, title, body, action_url):
    """同一来源只保留一条通知；返回 (obj, created)。"""
    obj, created = Notification.objects.update_or_create(
        source_module=source_module,
        source_object_id=source_object_id,
        defaults={
            'category': category,
            'title': title,
            'body': body,
            'action_url': action_url,
        },
    )
    return obj, created


def _resolve(source_module, alive_ids):
    """条件已解除的通知要撤下 —— 否则「修好了也还在报警」。

    `alive_ids` 是本轮仍然成立的对象 id 集合；只在这个范围内比对，
    不碰别的模块、也不碰用户可能手动创建的同类通知（`source_object_id IS NULL`）。
    """
    stale = Notification.objects.filter(
        source_module=source_module,
        source_object_id__isnull=False,
    ).exclude(source_object_id__in=alive_ids)
    removed, _ = stale.delete()
    return removed


class NotificationService:
    """统一通知生成服务。"""

    @staticmethod
    def check_relations():
        """关系模块：连续 90 天没有互动记录 → 提醒做一次关系审计。"""
        from apps.relation.models import Interaction

        latest = Interaction.objects.order_by('-happened_at').first()
        if latest is None:
            return {'check': 'relations', 'state': 'no_data'}
        quiet_days = (_today() - latest.happened_at.date()).days
        if quiet_days <= RELATION_QUIET_DAYS:
            return {'check': 'relations', 'state': 'ok', 'quiet_days': quiet_days}
        _, created = _upsert(
            'relation', None, 'reminder',
            '关系审计周期到了',
            f'已经 {quiet_days} 天没有记录过任何互动（阈值 {RELATION_QUIET_DAYS} 天）',
            '/relation',
        )
        return {'check': 'relations', 'state': 'alerted', 'quiet_days': quiet_days,
                'created': created}

    @staticmethod
    def check_goals():
        """目标模块：时间过半而进度落后 → 报警；条件解除了就撤下。"""
        from apps.goals.models import Goal
        from apps.goals.services import GoalProgressService

        today = _today()
        alive = []
        hit = 0
        for goal in Goal.objects.filter(status='in-progress'):
            if not goal.deadline or not goal.start_date:
                continue
            total_days = (goal.deadline - goal.start_date).days
            if total_days <= 0:
                continue
            elapsed = (today - goal.start_date).days / total_days
            if elapsed <= GOAL_STALL_ELAPSED:
                continue
            # 🔴 用 goals 服务的**唯一实现**算账本进度（本文件不再自己算一遍）；
            #    返回 None = 既没有子目标也没有里程碑 ⇒ 无账本，**不报警**（不是 0%）。
            progress = GoalProgressService.ledger_progress(goal)
            if progress is None or progress >= GOAL_STALL_PROGRESS:
                continue
            alive.append(goal.id)
            hit += 1
            _upsert(
                'goals', goal.id, 'alert',
                f'目标「{goal.title}」进度落后',
                f'时间已过 {elapsed * 100:.0f}%，进度仅 {progress}%（账本口径）',
                '/goals',
            )
        removed = _resolve('goals', alive)
        return {'check': 'goals', 'state': 'alerted' if hit else 'ok',
                'hit': hit, 'resolved': removed}

    @staticmethod
    def check_dams():
        """数字资产：待整理文件过多 → 提醒。"""
        from apps.dams.models import DamsFileResource

        unorganized = DamsFileResource.objects.filter(is_organized=False).count()
        if unorganized <= DAMS_UNORGANIZED:
            return {'check': 'dams', 'state': 'ok', 'unorganized': unorganized}
        _, created = _upsert(
            'dams', None, 'reminder',
            f'有 {unorganized} 个文件待整理',
            f'数字资产中有 {unorganized} 个文件尚未标记为已整理（阈值 {DAMS_UNORGANIZED}）',
            '/dams',
        )
        return {'check': 'dams', 'state': 'alerted', 'unorganized': unorganized,
                'created': created}

    @staticmethod
    def generate_all():
        """跑一遍全部检查。

        🔴 每一条**单独**捕获异常，但**不吞**：写进 `failed` 并 `logger.exception`。
           「一条坏了不影响其余两条，但坏了必须能被看见」——
           这正是原来 `except: pass` 缺的那半句。
        """
        checks = []
        failed = []
        for name, fn in (
            ('relations', NotificationService.check_relations),
            ('goals', NotificationService.check_goals),
            ('dams', NotificationService.check_dams),
        ):
            try:
                checks.append(fn())
            except Exception as exc:                       # noqa: BLE001
                logger.exception('通知检查失败：%s', name)
                failed.append({'check': name, 'error': f'{type(exc).__name__}: {exc}'})
        return {'checks': checks, 'failed': failed}

    # ── 节流 ────────────────────────────────────────────────
    @staticmethod
    def due():
        """距上次生成是否已超过节流窗口。"""
        return cache.get(THROTTLE_KEY) is None

    @staticmethod
    def generate_if_due(force=False):
        """按节流窗口生成；`force=True` 时忽略节流。

        返回 `{'ran': bool, 'result': {...} | None, 'next_in': int}`
        """
        if not force and not NotificationService.due():
            ttl = cache.ttl(THROTTLE_KEY) if hasattr(cache, 'ttl') else None
            return {'ran': False, 'result': None, 'next_in': ttl}
        result = NotificationService.generate_all()
        cache.set(THROTTLE_KEY, timezone.now().isoformat(), GENERATE_THROTTLE_SECONDS)
        return {'ran': True, 'result': result, 'next_in': GENERATE_THROTTLE_SECONDS}

    @staticmethod
    def cleanup_old(days=30):
        """清理超过指定天数的**已读**通知（默认不自动调用，见管理命令 `--cleanup`）。"""
        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = Notification.objects.filter(is_read=True, created_at__lt=cutoff).delete()
        return deleted
