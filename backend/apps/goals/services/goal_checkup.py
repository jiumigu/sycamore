"""目标过程检查（PDCA 的「C」）—— 只读体检

回答的问题
    「哪些目标名义上还在进行，实际上已经不动了？」

为什么需要它
    库里 445 条里程碑有 70.8% 停在 pending。这个数字本身不说明问题 ——
    但如果**连续三个月没有任何一条被碰过**，那就不是「还没到时间」，
    而是「已经忘了」。这两种情况在页面上长得一模一样，必须由检查区分。

刻意不做的事
    1. **不写库**：不自动把落后目标改状态，也不自动生成复盘。
       「看过」和「处理过」必须能分开，否则下次检查就无从判断。
    2. **不用 `Goal.updated_at` 当动静**：它是 `auto_now`，任何一次保存
       （包括 `recalculate()` 回写进度）都会刷新它，用它判停滞会永远判不出来。
    3. **不把长期目标算成「落后」**：2069 / 2080 这类截止日期按线性
       折算永远只走过个位数百分比，用它判落后等于没判。这类目标只看停滞。
"""

from django.db.models import Max
from django.utils import timezone

from ..constants import (
    ACTIVE_STATUSES,
    BEHIND_GAP,
    HORIZON_YEARS,
    PROBLEM_VERDICTS,
    STALL_DAYS,
    VERDICT_LABELS,
    VERDICT_SEVERITY,
)
from ..models import Action, Goal, GoalReview, Milestone


def _pct(numerator: float, denominator: float) -> float:
    if not denominator:
        return 0.0
    return round(numerator / denominator * 100, 1)


def _last_activity_map(goal_ids):
    """一次性取三类「动静」，取最大 —— 避免逐目标 N+1 查询。

    动静的定义（任一发生即算动过）：
      里程碑被改动（`updated_at`）· 行为打卡被记录 · 写过复盘
    """
    latest = {}

    def _merge(rows, key):
        for row in rows:
            if row['goal_id'] not in goal_ids or not row[key]:
                continue
            current = latest.get(row['goal_id'])
            if current is None or row[key] > current:
                latest[row['goal_id']] = row[key]

    _merge(
        Milestone.objects.filter(goal_id__in=goal_ids)
        .values('goal_id').annotate(last=Max('updated_at')),
        'last',
    )
    _merge(
        Action.objects.filter(goal_id__in=goal_ids)
        .values('goal_id').annotate(last=Max('updated_at')),
        'last',
    )
    _merge(
        GoalReview.objects.filter(goal_id__in=goal_ids)
        .values('goal_id').annotate(last=Max('created_at')),
        'last',
    )
    return latest


def _row(goal, last_activity, today):
    """单个目标的检查结果。

    口径说明：`progress` 用 `Goal.progress_percentage`（与页面显示同一个数），
    不用 `ledger_progress` —— 检查结果和页面进度不一致，会让人先怀疑检查，
    而不是怀疑目标本身。
    """
    days_since_activity = None
    if last_activity:
        days_since_activity = (today - timezone.localtime(last_activity).date()).days

    # ── 时间进度：起止都齐、跨度可判，才算得出来 ───────────────
    time_progress = None
    time_reason = 'ok'
    if not goal.deadline:
        time_reason = 'no_deadline'
    elif not goal.start_date:
        time_reason = 'no_start'
    elif goal.deadline <= goal.start_date:
        time_reason = 'invalid_span'
    elif (goal.deadline - goal.start_date).days > HORIZON_YEARS * 365:
        time_reason = 'long_horizon'
    else:
        span = (goal.deadline - goal.start_date).days
        elapsed = (today - goal.start_date).days
        time_progress = round(min(max(elapsed / span * 100, 0), 100), 1)

    progress = goal.progress_percentage or 0
    gap = round(time_progress - progress, 1) if time_progress is not None else None

    # ── 判定：逾期 > 停滞 > 落后/领先 ────────────────────────
    if goal.status == 'paused':
        verdict = 'paused'
    elif goal.deadline and goal.deadline < today:
        verdict = 'overdue'
    elif days_since_activity is None or days_since_activity >= STALL_DAYS:
        verdict = 'stalled'
    elif time_progress is None:
        # 时间进度不可判，又没有停滞迹象 ⇒ 只能如实说「在动」，不编结论
        verdict = 'on_track'
    elif gap >= BEHIND_GAP:
        verdict = 'behind'
    elif gap <= -BEHIND_GAP:
        verdict = 'ahead'
    else:
        verdict = 'on_track'

    total = goal.milestones.count()
    done = goal.milestones.filter(status='completed').count()

    return {
        'id': goal.id,
        'title': goal.title,
        'status': goal.status,
        'category': goal.category,
        'priority': goal.priority,
        'life_dimension': goal.life_dimension,
        'progress': progress,
        'time_progress': time_progress,
        'progress_gap': gap,
        'time_progress_reason': time_reason,
        'start_date': goal.start_date,
        'deadline': goal.deadline,
        'days_left': (goal.deadline - today).days if goal.deadline else None,
        'last_activity_at': timezone.localtime(last_activity).date() if last_activity else None,
        'days_since_activity': days_since_activity,
        'milestones_total': total,
        'milestones_done': done,
        'verdict': verdict,
        'verdict_label': VERDICT_LABELS[verdict],
    }


def _sort_key(row):
    """按「该先处理的程度」排序：判定严重度 → 落后点数 → 停滞天数"""
    return (
        VERDICT_SEVERITY.get(row['verdict'], 99),
        -(row['progress_gap'] if row['progress_gap'] is not None else -999),
        -(row['days_since_activity'] if row['days_since_activity'] is not None else 99999),
    )


def build_checkup():
    """返回全部在途目标的检查结果（只读）"""
    today = timezone.localdate()
    goals = list(
        Goal.objects.filter(status__in=ACTIVE_STATUSES)
        .prefetch_related('milestones')
        .order_by('id')
    )
    ids = {g.id for g in goals}
    latest = _last_activity_map(ids)

    rows = [_row(g, latest.get(g.id), today) for g in goals]
    rows.sort(key=_sort_key)

    summary = {
        'checked': len(rows),
        'problem': sum(1 for r in rows if r['verdict'] in PROBLEM_VERDICTS),
        'overdue': sum(1 for r in rows if r['verdict'] == 'overdue'),
        'stalled': sum(1 for r in rows if r['verdict'] == 'stalled'),
        'behind': sum(1 for r in rows if r['verdict'] == 'behind'),
        'paused': sum(1 for r in rows if r['verdict'] == 'paused'),
        'on_track': sum(1 for r in rows if r['verdict'] == 'on_track'),
        'ahead': sum(1 for r in rows if r['verdict'] == 'ahead'),
        # 以下两个是「判据算不出来」的说明，不是问题计数
        'long_horizon': sum(1 for r in rows if r['time_progress_reason'] == 'long_horizon'),
        'never_recorded': sum(1 for r in rows if r['days_since_activity'] is None),
    }

    return {
        'as_of': today,
        'stall_days': STALL_DAYS,
        'behind_gap': BEHIND_GAP,
        'horizon_years': HORIZON_YEARS,
        'summary': summary,
        'rows': rows,
    }
