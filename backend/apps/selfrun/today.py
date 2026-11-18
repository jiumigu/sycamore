"""「今天」四格 · 取数与候选（**纯只读**）

🔴 这个模块一条 `save()` 都没有。原因不是懒，是这个功能的全部价值就在于此：

   它只回答「今天走哪一格、那一格里有哪三件」，不持有任何数据。
   候选、计数、理由一律**现算** —— 一旦落库，它就成了第二份真源，
   而第二份真源迟早和 milestones / inbox / works 漂移。

🔴 与其它模块的边界（防止后人误接）：
   · 与 temporal L1 六词**无关**：四格是当天主调，六词是事后归因，不互为输入。
   · 与 selfrun KPI **无关**：不读 KPI、不被 KPI 读、不进 `PERIOD_VERDICT_BANDS`。
   · 与 goals / inbox / works **只读**，完成动作由前端调那些模块**现有**接口
     （`done` 字段给的就是真实路径，本页不新增任何写端点）。
   · 与 `Book.status` **两件事**：`status` 说这本书走到哪一步，
     `ReadingFocus` 说现在读哪本。不互相推导。

⚠️ 各模块模型一律**函数内导入**：`apps/works/views.py` 已经 import 了
   `apps.selfrun.readers`，模块级反向 import 会绕成环（加载顺序依赖，
   本机起得来、换台机器可能就 `AppRegistryNotReady`）。
"""
from __future__ import annotations

import datetime as dt

from django.db.models import Case, IntegerField, When
from django.utils import timezone

from .constants import (
    DAY_CELL_BACKFILL_DAYS,
    DAY_CELL_CANDIDATE_LIMIT,
    DAY_EMPTY_ALL,
    DAY_EMPTY_NO_CANDIDATES,
    DAY_EMPTY_NO_FOCUS,
    DAY_QUADRANT_CHOICES,
    DAY_QUADRANT_COLORS,
    DAY_QUADRANT_LABEL,
    DAY_WEEK_DAYS,
    DAY_WEEKDAY_LABELS,
)

# 目标到了这两个状态，它下面的里程碑就不再是「今天该做的活」。
# 与 `goals` 的 `STATUS_CHOICES` 同源取值（那边没有可供 import 的元组常量，
# 所以这里列两个字面值 —— 改 goals 状态机时**这里也要看一眼**）。
_DEAD_GOAL_STATUSES = ('abandoned', 'archived')

_REST = 'rest'


# ══════════════════════════════════════════════════════════════
# 候选行
# ══════════════════════════════════════════════════════════════

def _row(*, kind, obj_id, title, subtitle, reason, open_route, done=None):
    """一行候选。

    🔴 `done.path` **不含 `/api` 前缀** —— 前端 `request` 的 `baseURL` 就是
       `/api`，直接 `request({url: done.path})` 即可。
       曾经想过给完整 `/api/...`（更像浏览器里看到的地址），但那要求前端做
       一次字符串裁剪，裁剪写错不报错、只是请求打到 `/api/api/...` 得到 404。
       宁可让「完整路径」由 `open_route` 承担（那是给人点的），
       `done.path` 只服务代码。

    🔴 `milestone` 的 `done.body` **不是一个完整请求**：它只带状态，
       而后端要求完成必须附一句 `self_review`（`goals/services/completion_review.py`）。
       那句话只能由用户在当场写，所以由前端收集后合并进去
       （见 `TodayPanel.finish()` 与 `selfrunApi.completeCandidate` 的 `extra`）。
       别把这里改成「body 里塞一句默认批阅」—— 那等于替用户编一句他没说过的话。
    """
    return {
        'kind': kind,
        'id': obj_id,
        'title': title,
        'subtitle': subtitle,
        'reason': reason,
        'open_route': open_route,
        'done': done,
    }


# ══════════════════════════════════════════════════════════════
# 四格各自的一个池子
#
# 每个函数返回 `(candidates, total)`，**同一份 queryset** 既数总数又取前 N 条 ——
# 两处各写一遍过滤条件，就是「格子上写 16 件、点进去 0 件」这种共盲区的来源。
# `total` 是这一类**总共有多少件**（不打 limit），格子上显示的是它。
# ══════════════════════════════════════════════════════════════

def _pool_sow(today: dt.date, limit: int):
    """播种：当前这本（1 条）＋ 无硬期限的长期里程碑（按 `order_num`）。

    「从哪本书开始」在这里被消掉：这一格只放**当前那一本**，其余 94 本不出现。
    不是系统帮你挑，是系统不给你看。
    """
    from apps.book.services import ReadingFocusService
    from apps.goals.models import Milestone

    focus = ReadingFocusService.get_focus()
    book = focus.book if focus and focus.book_id else None

    qs = (
        Milestone.objects
        .filter(status='pending', target_date__isnull=True)
        .exclude(goal__status__in=_DEAD_GOAL_STATUSES)
        .select_related('goal')
        .order_by('order_num', 'id')
    )
    total = qs.count() + (1 if book else 0)

    rows = []
    if book:
        # 「第 N 天」的唯一算法在 `ReadingFocusService.days_on` —— 书页横条与这里
        # 必须是同一个数，否则同一天两个页面写着不同的天数。
        days = ReadingFocusService.days_on(book, focus.started_on, today=today)
        rows.append(_row(
            kind='book',
            obj_id=book.pk,
            title=book.btitle,
            subtitle=book.author or '当前这本',
            # 算不出天数就说「当前这本」，不写「第 0 天」（0 会被读成今天刚开始）。
            reason=f'当前这本，第 {days} 天' if days else '当前这本',
            open_route='/books',
            # 🔴 书**没有** done：读完由换书动作触发（书页），不在候选行里做。
            done=None,
        ))

    rest = max(limit - len(rows), 0)
    for idx, m in enumerate(qs[:rest], start=len(rows) + 1):
        rows.append(_row(
            kind='milestone',
            obj_id=m.pk,
            title=m.title,
            subtitle=_milestone_subtitle(m),
            # K 是**本格里的排位**（第 2、第 3 条），不是 `order_num` 的镜像。
            reason=f'没有日期，排在第 {idx}',
            open_route='/goals',
            done={
                'method': 'PATCH',
                'path': f'/goals/milestones/{m.pk}/',
                'body': {'status': 'completed'},
            },
        ))

    # 第三个返回值：这一格有没有「当前这本」。
    # 🔴 它必须**单独**给，不能只靠 `empty_reason` ——
    #    有里程碑、没书时 `empty_reason` 是 `None`（格子不为空），
    #    于是「还没指定当前这本」这条提示永远不会出现，
    #    而播种格的第一条本该就是那本书（第 1 步书闸门的全部意义）。
    return rows, total, book is not None


def _pool_reap(today: dt.date, limit: int):
    """收割：逾期/今天到期的里程碑在前，准备发的作品补足。"""
    from apps.goals.models import Milestone
    from apps.works.models import Work

    due = (
        Milestone.objects
        .filter(status__in=('pending', 'in-progress'), target_date__lte=today)
        .exclude(goal__status__in=_DEAD_GOAL_STATUSES)
        .select_related('goal')
        .order_by('target_date', 'id')
    )
    works = Work.objects.filter(status='ready').order_by('id')
    total = due.count() + works.count()

    rows = []
    for m in due[:limit]:
        late_days = (today - m.target_date).days
        rows.append(_row(
            kind='milestone',
            obj_id=m.pk,
            title=m.title,
            subtitle=_milestone_subtitle(m),
            reason=f'逾期 {late_days} 天' if late_days > 0 else '今天到期',
            open_route='/goals',
            done={
                'method': 'PATCH',
                'path': f'/goals/milestones/{m.pk}/',
                'body': {'status': 'completed'},
            },
        ))

    rest = max(limit - len(rows), 0)
    for w in works[:rest]:
        rows.append(_row(
            kind='work',
            obj_id=w.pk,
            title=w.name,
            subtitle=w.summary or '准备发',
            reason='准备发，还没发',
            open_route='/works',
            done={
                'method': 'PATCH',
                'path': f'/works/items/{w.pk}/',
                'body': {'status': 'published'},
            },
        ))

    return rows, total


# ⚠️ `priority` 存的是 'high'/'medium'/'low' **字符串**。直接 `order_by('priority')`
#    会按字典序排成 high → low → medium —— 静默排错，页面上完全看不出原因。
#    所以排的是映射出来的整数，不是字段本身。
_PRIORITY_RANK = Case(
    When(priority='high', then=0),
    When(priority='medium', then=1),
    default=2,                       # low 以及历史脏值（脏值排最后，不报错也不抢占）
    output_field=IntegerField(),
)


def _pool_tend(today: dt.date, limit: int):
    """疏苗：收件箱里还压着的（含「犹豫中」）。"""
    from apps.inbox.models import InboxItem

    qs = (
        InboxItem.objects
        .filter(status__in=('pending', 'hesitating'))
        .annotate(_pr=_PRIORITY_RANK)
        .order_by('_pr', 'created_at')
    )
    total = qs.count()

    rows = []
    for item in qs[:limit]:
        # `created_at` 是 UTC 存的（`USE_TZ=True`）⇒ 先转本地再取日期，
        # 否则凌晨记的条目会算成「压了 1 天」。
        created = timezone.localtime(item.created_at).date()
        waited = (today - created).days
        reason = '今天记的' if waited <= 0 else f'压了 {waited} 天'
        if item.status == 'hesitating':
            reason = f'{reason}，一直在犹豫'
        rows.append(_row(
            kind='inbox',
            obj_id=item.pk,
            title=item.content,
            subtitle=(item.description or '').strip()[:40],
            reason=reason,
            open_route='/inbox',
            done={
                'method': 'POST',
                'path': f'/inbox/items/{item.pk}/complete/',
                'body': {},
            },
        ))

    return rows, total


# ══════════════════════════════════════════════════════════════
# 对外
# ══════════════════════════════════════════════════════════════

def _milestone_subtitle(m) -> str:
    """`目标 · 第 N 个里程碑`。

    ⚠️ `order_num` 默认是 0，而且允许重复 —— 所以只在 `> 0` 时才写序号，
       否则页面上会出现一排「第 0 个里程碑」。
    """
    goal_title = m.goal.title if m.goal_id else ''
    if m.order_num and m.order_num > 0:
        return f'{goal_title} · 第 {m.order_num} 个里程碑' if goal_title else f'第 {m.order_num} 个里程碑'
    return goal_title


def quadrant_pool(quadrant: str, *, today: dt.date, limit: int = DAY_CELL_CANDIDATE_LIMIT):
    """某一格的 `(candidates, total, empty_reason, has_focus)`。

    `empty_reason` 只描述**这一格**为什么**没有候选**：
      · `no_focus`       播种格：还没指定当前这本（去指定一本就有活了）
      · `no_candidates`  这一类今天真的没有活
      · `None`           有候选，或风干（风干本来就没有清单）

    `has_focus` 与 `empty_reason` **正交**：播种格有里程碑、没书时，
    `empty_reason` 是 `None`（不为空）而 `has_focus` 是 `False`。
    两个都真、都要说 —— 前端在列表下方补一句「还没指定当前这本」。
    其余三格恒为 `True`（这一格不涉及书）。
    """
    if quadrant == _REST:
        # 🔴 风干的空**不是**「没有活」，是「这一格本来就没有清单」。
        #    给 `no_candidates` 会让前端显示「这一类没有排着的活」——
        #    对着一格叫「今天不排活」的卡说这句话，等于自相矛盾。
        return [], 0, None, True

    if quadrant == 'sow':
        rows, total, has_focus = _pool_sow(today, limit)
        if not rows:
            return [], total, DAY_EMPTY_NO_FOCUS, has_focus
        # 🔴 只有书、没有可用里程碑时，不算「有缺口」：
        #    返回 1 条就是 1 条，不补位、不凑数。
        return rows, total, None, has_focus

    if quadrant == 'reap':
        rows, total = _pool_reap(today, limit)
    else:
        rows, total = _pool_tend(today, limit)

    return rows, total, (None if rows else DAY_EMPTY_NO_CANDIDATES), True


def build_cell_payload(cell, *, today: dt.date):
    """一条日结 → 首屏的 `cell`。

    🔴 候选**现算**，不从表里读 —— 表里只有「走了哪一格」，
       候选是那一刻池子的样子；存下来就会跟 milestones / inbox / works 漂移。
       于是同一条日结，昨天点开和今天点开看到的候选可以不同，这是**正确**的：
       它说的是「这一格现在有什么」，不是「当时摆了什么」。
    """
    rows, total, empty_reason, has_focus = quadrant_pool(cell.quadrant, today=today)
    return {
        'id': cell.pk,
        'cell_date': cell.cell_date.isoformat(),
        'quadrant': cell.quadrant,
        'quadrant_label': DAY_QUADRANT_LABEL[cell.quadrant],
        # `''` = 还没结算（**不是**「没成」）。前端按空串分流。
        'outcome': cell.outcome,
        'note': cell.note,
        'is_backfilled': cell.is_backfilled,
        'candidates': rows,
        'total': total,
        'empty_reason': empty_reason,
        'no_focus': cell.quadrant == 'sow' and not has_focus,
    }


def build_week(end: dt.date):
    """以 `end` 为**最后一天**（含）的 7 格色带 + 汇总。

    `end` 不是「今天」的别名：本周状态页翻到历史周时，色带要画的是
    **那一周**，而不是「最近 7 天」（见 `urls.py` 的 `day-cells/week/`）。

    🔴 `outcome=None` 有两种来源，**不许合并**：
       那天没定档（`quadrant is None`）与定了没结算（`quadrant` 有值、
       原始 `outcome` 是空串）。前者是「空」，后者是「待结算」。
    """
    from .models import SelfRunDayCell

    start = end - dt.timedelta(days=DAY_WEEK_DAYS - 1)
    cells = {
        c.cell_date: c
        for c in SelfRunDayCell.objects.filter(cell_date__gte=start, cell_date__lte=end)
    }

    days = []
    for offset in range(DAY_WEEK_DAYS - 1, -1, -1):
        day = end - dt.timedelta(days=offset)
        cell = cells.get(day)
        days.append({
            'date': day.isoformat(),
            'quadrant': cell.quadrant if cell else None,
            'outcome': (cell.outcome or None) if cell else None,
            'is_backfilled': bool(cell and cell.is_backfilled),
        })

    values = list(cells.values())
    summary = {
        'marked_days': len(values),
        'settled_days': sum(1 for c in values if c.outcome),
        'missed_days': sum(1 for c in values if c.outcome == 'missed'),
        # 🔴 风干不进「未结算」：它本来就不结算。算进去的话，
        #    只要休息过一天，色带就永远显示「还差一天没结」，而那一天永远补不上。
        'unsettled_days': sum(1 for c in values if c.quadrant != _REST and not c.outcome),
    }
    return {'days': days, 'summary': summary}


def build_week_payload(end: dt.date):
    """`GET /selfrun/day-cells/week/?end=` 的响应体。

    比今日页内嵌的 `week` 多两样：

    · `end`  —— 前端要标「这一格是终点」，不能自己拿 `days[-1]` 猜
    · `legend` —— 四格的 `label` + `color`

    🔴 为什么带 `legend`：色带在**两个页面**出现（今日页 / 本周状态页），
       而本周状态页拿不到 `quadrants` 卡片。少了这份，前端只能自己写一份
       四格词表与配色 —— 那就是第二份口径，改一处漏一处，且不报错。
    """
    return {
        **build_week(end),
        'end': end.isoformat(),
        'legend': [
            {'quadrant': quadrant, 'label': label, 'color': DAY_QUADRANT_COLORS[quadrant]}
            for quadrant, label in DAY_QUADRANT_CHOICES
        ],
    }


def build_backfill(today: dt.date):
    """最近 `DAY_CELL_BACKFILL_DAYS` 天里**还没定档**的那几天（不含今天）。

    🔴 这个列表只回答「哪几天还能补」，**不回答「那天该是哪一格」**：
       那天走了哪一格是你记得的事，系统不猜。所以这里**不带任何候选计数** ——
       格子上的 `count` 是「**今天**这一格给几件」，把它摆进「补 3 天前」的
       对话框里，就是拿今天的池子冒充那天的池子，而且看起来完全正常。

    ⚠️ 为什么不用 `build_week(today)` 反推：色带是 `[今-6, 今]`，
       补记窗口是 `[今-7, 昨]` —— 错开一天且方向不同。用色带去推，
       「第 7 天」会永远补不了，而它恰好在窗口里。

    ⚠️ 今天不在列表里：今天没定档时，今日页那四格**就是**入口。
       同一件事给两个入口，早晚出现「在补记里定了今天」这种记法。
    """
    from .models import SelfRunDayCell

    start = today - dt.timedelta(days=DAY_CELL_BACKFILL_DAYS)
    end = today - dt.timedelta(days=1)
    taken = set(
        SelfRunDayCell.objects
        .filter(cell_date__gte=start, cell_date__lte=end)
        .values_list('cell_date', flat=True)
    )

    days = []
    for offset in range(1, DAY_CELL_BACKFILL_DAYS + 1):
        day = today - dt.timedelta(days=offset)
        if day in taken:
            continue
        days.append({
            'date': day.isoformat(),
            # 周几由后端给：前端算就要 `new Date()`，那会差 8 小时且合法不可见
            'weekday': DAY_WEEKDAY_LABELS[day.weekday()],
        })
    return {'days': days, 'limit': DAY_CELL_BACKFILL_DAYS}


def _settle_prompt(today: dt.date):
    """「还有一格没结算」—— 最多一条，指向最近的那天。

    昨天的格子昨天定、今天结，是这个功能的主循环；隔天不打开就会积压，
    所以这里取**最近一条**未结算，而不是死看昨天（见 `latest_unsettled_cell`）。
    """
    from . import services

    cell = services.latest_unsettled_cell(today)
    if cell is None:
        return None
    return {
        'cell_id': cell.pk,
        'date': cell.cell_date.isoformat(),
        'quadrant': cell.quadrant,
        'quadrant_label': DAY_QUADRANT_LABEL[cell.quadrant],
        'days_ago': (today - cell.cell_date).days,
    }


def build_today(*, today: dt.date | None = None):
    """`GET /selfrun/today/` 的响应体（**只读，不写库**）。

    `cell` 有值 = 今天已经定档，并带上那一格的候选；`null` = 还没定。
    """
    from . import services

    today = today or timezone.localdate()
    cell = services.get_day_cell(today)
    week = build_week(today)

    quadrants = []
    any_candidate = False
    for quadrant, label in DAY_QUADRANT_CHOICES:
        # `total` 这一层不用（格子上不报池子总量），但两个数必须来自**同一次**
        # `quadrant_pool` 调用 —— 分开算就等于两份过滤条件。
        rows, _total, _reason, _has_focus = quadrant_pool(quadrant, today=today)
        has = bool(rows)
        any_candidate = any_candidate or has
        quadrants.append({
            'quadrant': quadrant,
            'label': label,
            'color': DAY_QUADRANT_COLORS[quadrant],
            # 🔴 `count` 是**这一格今天给几件**（≤ 3），**不是**池子总量。
            #    设计稿原以为「无期限里程碑」只有两三条，真实数据是 262 条 ——
            #    格子上写 262，等于把「426 件待办」的焦虑原封不动搬回首屏，
            #    而这一页存在的唯一理由就是**别让你面对那个数**。
            #    池子总量在 `cell.total` 里，点开才看得到。
            'count': len(rows),
            # 风干恒为 False：它没有候选，但它**可点**（见下面的 selectable）。
            'has_candidates': has,
            # 🔴 `selectable` 由后端给，前端只看这一个字段决定能否点。
            #    前端若按 `count == 0` 统一置灰，风干会永远点不了 ——
            #    而风干恰恰是最该随时可点的一格。
            'selectable': quadrant == _REST or has,
        })

    return {
        'date': today.isoformat(),
        'weekday': DAY_WEEKDAY_LABELS[today.weekday()],
        'cell': build_cell_payload(cell, today=today) if cell else None,
        'quadrants': quadrants,
        # 四格全空时给一个总口径 —— 有候选时不给（有候选的格子自己说自己的事）。
        'empty_reason': None if any_candidate else DAY_EMPTY_ALL,
        'settle_prompt': _settle_prompt(today),
        'week': week['days'],
        'week_summary': week['summary'],
        # 补记入口：最近 7 天里还空着的那几天（今天除外 —— 今天那四格就是入口）
        'backfill': build_backfill(today),
    }
