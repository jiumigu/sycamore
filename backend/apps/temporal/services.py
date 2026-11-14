import calendar
import csv
import io
import uuid
from collections import defaultdict
from datetime import datetime, date, timedelta

from django.db import models, transaction
from django.db.models import Avg, Count, Max, Min, Sum
from django.utils import timezone

from .constants import (
    ACTIVITY_TYPE_COLORS,
    ATTRIBUTION_COLORS,
    ATTRIBUTION_ORDER,
    CONTRIB_EXCLUDED_TASK_NAMES,
    DAILY_GUARD_LINES,
    DAILY_GUARD_STATUS_TEXT,
    DEFAULT_FALLBACK_ATTR,
    LEGACY_FOUR_TO_L2,
    SOURCE_BATCH_EXACT,
    SOURCE_BATCH_PREFIXES,
    SOURCE_KIND_HINTS,
    SOURCE_KIND_LABELS,
    SOURCE_KIND_VALUES,
    TASK_CATEGORY_MAPPING,
    TASK_TO_L2,
)
from .models import OneDayPage, TaskMeta, TemporalTask, TimerSession


def resolve_task_meta(task_names: list[str]) -> dict:
    """task_name(L3) → {activity_type(L2), is_unclassified}

    注：v0.3 语义订正后，L1 = 归因（见 resolve_attribution），不再有「自建聚合分组」层。
    """
    if not task_names:
        return {}
    rows = TaskMeta.objects.filter(task_name__in=task_names)
    out = {}
    for r in rows:
        out[r.task_name] = {
            'activity_type': r.activity_type,
            'is_unclassified': r.activity_type == '未归类',
        }
    return out


def resolve_attribution_detail(task_names: list[str]) -> dict:
    """task_name(L3) → {'attribution': 有效归因, 'source': 来源}

    优先级：temporal_task_meta.default_attribution > 兜底 DEFAULT_FALLBACK_ATTR
    source ∈ {'default' 映射表那列的默认值, 'fallback' 兜底}

    🔴 v3.64.16：这里曾是**三层**（redemption_attr_rule > default > fallback）。
       那条「外挂规则」已整条退役，原因不是重复而是**漏数**：
       它只是映射表 L1 列的影子副本（改值时顺带写一条 priority=100 的 task_name 规则），
       却只覆盖被改过的那几个任务名；赎回期页面拿「命中规则」当口径，
       未覆盖的记录**静默不计** —— 实测 2 天窗口 33.96h 只算了 20h，
       「成长」1.99h 而真实 12.39h，「谋生」恒为 0，且全程不报错。
       现在全站只有这一把尺子：映射表那一列。
    """
    if not task_names:
        return {}
    meta_map = {m.task_name: m for m in TaskMeta.objects.filter(task_name__in=task_names)}
    out = {}
    for tn in task_names:
        m = meta_map.get(tn)
        if m and m.default_attribution:
            out[tn] = {'attribution': m.default_attribution, 'source': 'default'}
        else:
            out[tn] = {'attribution': DEFAULT_FALLBACK_ATTR, 'source': 'fallback'}
    return out


def resolve_attribution(task_names: list[str]) -> dict:
    """task_name(L3) → 价值归因（L1：见 constants.ATTRIBUTION_ORDER）

    优先级：temporal_task_meta.default_attribution > 兜底 DEFAULT_FALLBACK_ATTR
    仅取有效值；需要知道「来源」时用 resolve_attribution_detail。
    """
    return {tn: d['attribution'] for tn, d in resolve_attribution_detail(task_names).items()}


def build_time_fields(start_dt: datetime, end_dt: datetime | None = None) -> dict:
    """由起止时间派生记录的日历字段（可选派生时长）。

    v3.58.6 抽出：CSV 导入与「任务清单手工新增/编辑」共用同一套派生规则，避免两处漂移。

    - `year / mon / day / week / quarter` 一律取自**开始时刻**；`mon` 为两位字符串（`'09'`），
      与历史数据、`?month=` 筛选口径一致。
    - **传了 `end_dt` 才附 `duration_hours`**（= 结束 − 开始，小时，保留 2 位）：手工录入靠它
      自动算时长；**CSV 导入不要传**——ATracker 自带时长（含计时器暂停等）不应被覆盖。
    """
    d = start_dt.date() if isinstance(start_dt, datetime) else start_dt
    fields = {
        'year': d.year,
        'mon': f'{d.month:02d}',
        'day': d.day,
        'week': d.isocalendar()[1],
        'quarter': (d.month - 1) // 3 + 1,
    }
    if end_dt is not None:
        fields['duration_hours'] = round((end_dt - start_dt).total_seconds() / 3600, 2)
    return fields


# ── 重复判定（单一真源，v3.60.29） ─────────────────────────────────────────
# 🔴 为什么不能用 `(task_name, start_time)` 精确相等判重：
# `import_worklog` 规则 A 会**改写已有记录的 start_time**（08:05 → 08:00，附注留
# 「原 08:05–18:00」）⇒ 那条记录的原始时刻在精确匹配下**"消失"**了 ⇒ 再导入一次 CSV
# 或迁移旧库时被判为新记录、**静默插入一条重复**（2026-09-17 就是这么多出 9.92h 一条，
# 推导见 TECH-NOTES §64）。实测「被改写过的日子」有 50 天，全是雷区。
# ⚠️ 别退回精确匹配：它是**容错余量为零**的键 —— 只要有一个流程会改这个字段，
#    它就会在某次导入时静默失效，而链路上没有任何一步会报错。
DUP_OVERLAP_RATIO = 0.8      # 重叠时长 ÷ 较短一方时长 ≥ 此值 ⇒ 判为同一条
DUP_SEARCH_WINDOW_DAYS = 1   # 在开始时刻前后各搜 1 天（容忍跨天的长记录）

# ── 时段重叠（手工新增/编辑的**提示**口径，v3.63.6）──────────────────────
# 🔴 与上面的「重复判定」是**两件事**，别合并：
#   · `find_duplicate_task`：同任务名 + 比值 ≥0.8 ⇒ **删除/跳过**（导入去重）
#   · `find_overlaps`：任意任务名 + 绝对交集 ⇒ **只提示、不阻断**（下面这份）
# 本库实测（2026-08~10 共 339 条记录）里有 19 对记录时段相交，其中「牛马工作 07:46-18:00」
# 内再细分「代码编程」是最常见形态 —— 重叠在本项目里**是合法记录**，
# 所以这里绝不能拿来做「禁止保存」的闸门，只能是给用户看的提醒。
OVERLAP_MIN_SECONDS = 60      # 交集 < 1 分钟视为 ATracker 分段的秒级抖动，不提示
OVERLAP_SEARCH_WINDOW_DAYS = 2  # 候选下界：只跳过 2 天以前的开始时刻（单条记录不会更长）

# ── 重叠的**语义**分类（导入预演用，v3.64.32）────────────────────────────
# 🔴 「重叠」不是一件事，是四件事：合法细分、跨整点摩擦、同一件事记两遍、真要人判。
#    本库实测（2026-11-07，5457 条 / 262 对重叠）：
#      contained 214 对（82%）、edge 36 对、review 7 对、likely_dup 5 对。
#    把一个「禁止重叠」的闸门装上去，会把那 214 对合法的细分记录一起堵死；
#    什么都不做，则 12 对真问题永远埋在月度统计里 —— 都错，所以先分类再谈处理。
CONFLICT_CONTAINED = 'contained'    # 短的完全落在长的里面 ⇒ 合法细分（上班时段里记代码）
CONFLICT_EDGE = 'edge'              # 只相交 ≤10 分钟 ⇒ 跨整点 / 两端精度差，无害
CONFLICT_LIKELY_DUP = 'likely_dup'  # 长度接近且几乎完全重合 ⇒ 同一件事记了两遍
CONFLICT_REVIEW = 'review'          # 其余交叉 ⇒ 摊开给人看
# 严重度：数字越大越需要人看（预演时一行只报最严重的那条关系）
CONFLICT_SEVERITY = {
    CONFLICT_CONTAINED: 0,
    CONFLICT_EDGE: 1,
    CONFLICT_REVIEW: 2,
    CONFLICT_LIKELY_DUP: 3,
}
CONFLICT_KEYS = tuple(CONFLICT_SEVERITY)      # 预演汇总的固定键序（前端只查表，不自造）
EDGE_MAX_SECONDS = 10 * 60                    # 「边缘摩擦」的交集上限
EDGE_MAX_RATIO = 0.3                          # 且占较短一方不足 30%
DUP_MIN_LENGTH_RATIO = 0.8                    # 包含关系里，长度比 ≥ 此值才算「疑似同一条」


def _to_aware(dt: datetime | None) -> datetime | None:
    """库里读出的 datetime 恒为 aware（`USE_TZ=True`），外部传入的可能是 naive ⇒ 统一。"""
    if dt is None:
        return None
    return timezone.make_aware(dt) if timezone.is_naive(dt) else dt


def _span(start_dt, end_dt, duration_hours) -> tuple[datetime, datetime] | None:
    """把「开始 + (结束时刻 | 时长)」归一成一个 `(起, 止)` 区间。

    结束时刻缺失时用时长推算（ATracker 导出的「结束时间」列常为空，但「持续时间」必有）。
    两侧都缺 ⇒ 退化成零宽区间（止 = 起），由 `_overlap_ratio` 的零宽分支处理。
    """
    start = _to_aware(start_dt)
    if start is None:
        return None
    end = _to_aware(end_dt)
    if end is None and duration_hours:
        end = start + timedelta(hours=float(duration_hours))
    if end is None or end < start:
        end = start
    return start, end


def _dedup_key(name: str, start_dt) -> tuple:
    """**同一个 CSV 内部**判重的键（同任务名 + 同一开始时刻）。

    ⚠️ 与 `find_duplicate_task`（与**库里**比，容错到「时段重叠」）不是一回事：
       这里可以要求精确，因为两行来自同一次导出、中间没有任何流程改写它们；
       而库里那条可能被 `import_worklog` 规则 A 补全过开始时刻，精确匹配会失效。
       预演与落库共用本函数，别各写一份（否则「预演说重复 2 条、实际去重 1 条」）。
    """
    return (name, start_dt)


def _overlap_ratio(a: tuple, b: tuple) -> float:
    """重叠时长 ÷ **较短一方**时长。

    🔴 用比值而不是「有重叠就算」：ATracker 允许同时做两件事，**相接分段也会重叠几秒**
    （2026-01-10「日常家务」两段只重叠 30 秒 ⇒ 比值 2%，是合法记录）。
    按「有重叠就算重复」会把它们吞掉，且**界面上看不出来少了什么**。
    """
    a_start, a_end = a
    b_start, b_end = b
    a_secs = (a_end - a_start).total_seconds()
    b_secs = (b_end - b_start).total_seconds()
    if a_secs <= 0 or b_secs <= 0:
        # 零宽（只有开始时刻）：退化为「点是否落在对方区间内」
        if a_secs <= 0:
            return 1.0 if b_start <= a_start <= b_end else 0.0
        return 1.0 if a_start <= b_start <= a_end else 0.0
    overlap = (min(a_end, b_end) - max(a_start, b_start)).total_seconds()
    return max(overlap, 0.0) / min(a_secs, b_secs)


def classify_overlap(a: tuple, b: tuple) -> str:
    """两条时段「怎么重叠的」—— 四类之一，供导入预演分拣（不是判重）。

    与 `find_duplicate_task`（同任务名 + 比值 ≥0.8 ⇒ 跳过/更新）的分工：
    那条回答「这是不是同一条」，本条回答「这两条摆在一起像什么」，**不看任务名**
    （异名重叠恰恰是最需要人看的那一类）。

    🔴 判据顺序不能换：**先判包含，再看比值**。
       `_overlap_ratio` 的分母是「较短一方」，所以「A 完全包住 B」的比值恒为 1.0 ——
       一旦先看比值，本库 214 对合法细分（`牛马工作 09:00-18:00` 里记
       `代码编程 10:00-11:00`）会全部被判成「疑似重复」，而那正是 82% 的重叠。

    四类的不变量（写测试时按这个钉）：
    - `contained`：短的完全落在长的里面，且 `短/长 < 0.8`
    - `likely_dup`：长度接近（`短/长 ≥ 0.8`）**且**重合 ≥ `DUP_OVERLAP_RATIO`
    - `edge`：非包含，且交集 ≤ 10 分钟、占较短一方 < 30%
    - `review`：其余一切交叉（含零宽退化）
    """
    a_start, a_end = a
    b_start, b_end = b
    a_len = (a_end - a_start).total_seconds()
    b_len = (b_end - b_start).total_seconds()
    if a_len <= 0 or b_len <= 0:
        # 零宽（只记了开始时刻）：表达不了「占了哪一段」，交给人和上面那条单条提示，
        # 不在这里猜 —— 猜成 edge 会把它从清单里折叠掉。
        return CONFLICT_REVIEW

    overlap = (min(a_end, b_end) - max(a_start, b_start)).total_seconds()
    if overlap <= 0:
        return CONFLICT_REVIEW

    short, long_ = (a_len, b_len) if a_len <= b_len else (b_len, a_len)
    ratio = overlap / short
    length_ratio = short / long_
    contained = (
        (a_start <= b_start and b_end <= a_end)
        or (b_start <= a_start and a_end <= b_end)
    )

    if contained:
        return (CONFLICT_LIKELY_DUP if length_ratio >= DUP_MIN_LENGTH_RATIO
                else CONFLICT_CONTAINED)
    if ratio >= DUP_OVERLAP_RATIO:
        return CONFLICT_LIKELY_DUP
    if overlap <= EDGE_MAX_SECONDS and ratio < EDGE_MAX_RATIO:
        return CONFLICT_EDGE
    return CONFLICT_REVIEW


def find_duplicate_task(task_name: str, start_dt, end_dt=None, duration_hours=None):
    """按「同任务名 + 时段重叠」找已有记录；找不到（或都没到阈值）返回 None。

    调用方：`CSVImportService.import_from_csv`（前端 CSV 导入）与
    `migrate_atracker` 命令（旧库 `o_atracker_tasks_list` 迁移）——**两处共用这一份实现**，
    别再各写一份精确匹配（理由见上方 `DUP_OVERLAP_RATIO` 的注释）。

    ⚠️ **`reconstruct_worktime` 有意不走这里**：它按 `import_batch` 隔离，
    并且**故意允许**与已有 ATracker 记录并存（台账推定的加班时段本就可能与原始记录同期，
    见 `test_overtime_recon.py` 的「当天两条并存」用例）。改走这里会破坏那个语义。
    """
    span = _span(start_dt, end_dt, duration_hours)
    if not task_name or span is None:
        return None
    a_start, a_end = span
    lo = a_start - timedelta(days=DUP_SEARCH_WINDOW_DAYS)
    hi = a_start + timedelta(days=DUP_SEARCH_WINDOW_DAYS) + (a_end - a_start)

    best, best_ratio = None, 0.0
    for cand in TemporalTask.objects.filter(
        task_name=task_name, start_time__gte=lo, start_time__lt=hi,
    ):
        c_start = cand.start_time
        c_end = _to_aware(cand.end_time)
        if c_end is None and cand.duration_hours:
            c_end = c_start + timedelta(hours=float(cand.duration_hours))
        if c_end is None or c_end < c_start:
            c_end = c_start
        ratio = _overlap_ratio(span, (c_start, c_end))
        if ratio > best_ratio:
            best, best_ratio = cand, ratio
    return best if best_ratio >= DUP_OVERLAP_RATIO else None


def find_overlaps(start_dt, end_dt=None, duration_hours=None,
                  exclude_id=None, task_name: str | None = None,
                  limit: int = 5) -> list[dict]:
    """找与 `[start, end)` 时段相交的已有记录（**不限任务名**），供新增/编辑时提示。

    与 `find_duplicate_task` 的分工见上方 `OVERLAP_MIN_SECONDS` 的注释。

    - 交集必须 ≥ `OVERLAP_MIN_SECONDS`（默认 60s）才算一条，避免把
      「上一段 10:00 结束、下一段 10:00:03 开始」这种**相接分段**报成重复。
    - `exclude_id`：编辑时排除自己（否则一条记录永远与自己重叠）。
    - `task_name`：只用来标 `same_name`，**不参与筛选** —— 异名重叠同样要提示。
    - 返回值按交集时长倒序，最多 `limit` 条；`same_name` 供前端决定文案
      （同名重叠 = 极可能重复新增；异名重叠 = 合法并行，需用户自己判断）。
    - 结束时刻缺失时用 `duration_hours` 推算（与 `_span` 同一规则，单一日历口径）。
    """
    span = _span(start_dt, end_dt, duration_hours)
    if span is None:
        return []
    s, e = span
    # 零宽区间（只有开始时刻、也没有时长）：无法表达"占了哪一段"，不参与提示
    if e <= s:
        return []

    lo = s - timedelta(days=OVERLAP_SEARCH_WINDOW_DAYS)
    qs = TemporalTask.objects.filter(start_time__gte=lo, start_time__lt=e)
    if exclude_id:
        qs = qs.exclude(id=exclude_id)

    hits = []
    for cand in qs:
        c = _span(cand.start_time, cand.end_time, cand.duration_hours)
        if c is None:
            continue
        overlap = (min(e, c[1]) - max(s, c[0])).total_seconds()
        if overlap >= OVERLAP_MIN_SECONDS:
            hits.append({
                'id': cand.id,
                'task_name': cand.task_name,
                'start_time': timezone.localtime(c[0]).strftime('%Y-%m-%d %H:%M'),
                'end_time': timezone.localtime(c[1]).strftime('%Y-%m-%d %H:%M'),
                'overlap_minutes': round(overlap / 60),
                'same_name': bool(task_name) and cand.task_name == task_name,
                # 四类语义（`classify_overlap` 是唯一实现）——单条录入时前端不用它，
                # 导入预演用它决定「这条要不要摊开给人看」。
                'relation': classify_overlap((s, e), (c[0], c[1])),
            })
    hits.sort(key=lambda x: (-x['overlap_minutes'], x['start_time']))
    return hits[:limit]


# ── 记录来源（v3.64.33）───────────────────────────────────────────────────
# 口径全在 `constants.SOURCE_*`；这里只有「怎么读批次号」和「怎么汇总」两件事。


def make_batch_id(now=None) -> str:
    """新导入批次的编号：`import_20261107_1832_ab12`。

    🔴 为什么要带日期：旧格式 `import_3c3fff90846d` 是纯哈希，界面上既读不懂
       「这是哪天导的」，两个批次也没法按时间排。带 `YYYYmmdd_HHMM` 后，
       用户在批次清单里一眼能对上「那天我导了手机上的记录」。
    🔴 前缀仍是 `import_` —— 分类（`SOURCE_BATCH_PREFIXES`）、按批次回滚的命令
       都按前缀认，换前缀会把它们一起打穿。
    ⚠️ 尾巴留 4 位随机：同一分钟连导两次也不会撞号（撞号 = 两批合并、事后无法区分）。
    """
    stamp = (now or timezone.localtime()).strftime('%Y%m%d_%H%M')
    return f'import_{stamp}_{uuid.uuid4().hex[:4]}'


def classify_source(import_batch: str | None) -> dict:
    """批次号 → `{kind, label, batch, hint}`（**唯一实现**，纯字符串判断、不查库）。

    调用方：序列化器（每行都要，所以**绝不能**在这里查库）、来源筛选、批次清单。
    """
    batch = (import_batch or '').strip()
    if not batch:
        kind = 'unlabeled'
    elif batch in SOURCE_BATCH_EXACT:
        kind = SOURCE_BATCH_EXACT[batch]
    else:
        kind = 'other'
        for prefix, k in SOURCE_BATCH_PREFIXES:
            if batch.startswith(prefix):
                kind = k
                break
    return {
        'kind': kind,
        'label': SOURCE_KIND_LABELS.get(kind, SOURCE_KIND_LABELS['other']),
        'batch': batch or None,
        'hint': SOURCE_KIND_HINTS.get(kind, ''),
    }


def batches_of_kind(kind: str) -> list[str | None]:
    """该来源名下出现过的批次号（含 None）。

    来源筛选时用它把「kind」翻成「一批 import_batch 值」——
    `TemporalTask` 上没有 kind 列（外部表加不了列），分类只能事后做。
    """
    raw = (TemporalTask.objects.order_by()
           .values_list('import_batch', flat=True).distinct())
    return [b for b in raw if classify_source(b)['kind'] == kind]


def list_record_sources() -> dict:
    """全库按来源聚合：批次明细 + 按 kind 汇总（供「来源可见」弹窗）。

    🔴 `.order_by()` 必须清序：模型 Meta 是 `ordering = ['-start_time']`，
       不清序 Django 会把 start_time 注入 GROUP BY，一个批次会被拆成许多行
       —— 本项目反复踩过的坑，且**不报错**，只是数字看起来变小。
    """
    rows = (TemporalTask.objects.order_by()
            .values('import_batch')
            .annotate(
                n=Count('id'),
                name_kinds=Count('task_name', distinct=True),
                first_start=Min('start_time'),
                last_start=Max('start_time'),
                last_touch=Max('updated_at'),
            ))

    def _fmt(dt):
        return timezone.localtime(dt).strftime('%Y-%m-%d %H:%M') if dt else None

    items = []
    by_kind = {}
    total = 0
    for r in rows:
        info = classify_source(r['import_batch'])
        n = r['n']
        total += n
        items.append({
            'batch': info['batch'],
            'kind': info['kind'],
            'label': info['label'],
            'count': n,
            'name_kinds': r['name_kinds'],
            'first_start': _fmt(r['first_start']),
            'last_start': _fmt(r['last_start']),
            'last_touch': _fmt(r['last_touch']),
        })
        agg = by_kind.setdefault(info['kind'], {
            'kind': info['kind'], 'label': info['label'], 'hint': info['hint'],
            'count': 0, 'batches': 0,
        })
        agg['count'] += n
        agg['batches'] += 1

    # 批次明细按条数倒序（未标注同样参与排序，不特殊照顾 —— 它的条数本身就是信息）
    items.sort(key=lambda x: (-x['count'], x['label']))

    # 汇总按枚举固定顺序下发：同一页面每次打开顺序一致，不随数据量跳动
    kinds = [by_kind[k] for k in SOURCE_KIND_VALUES if k in by_kind]

    return {
        'total_records': total,
        'total_batches': len(items),
        'items': items,
        'kinds': kinds,
        'unlabeled_count': by_kind.get('unlabeled', {}).get('count', 0),
    }


def label_unlabeled_source(target: str = 'manual', *, ids=None, dry_run: bool = True) -> dict:
    """把「没有来源标记」的历史记录补上来源（**数据修复**，不是分类）。

    只动 `import_batch` 为空（NULL 或空串）的行；**已有任何来源的一律不碰**
    —— 修历史不该顺手改写已知来源。

    🔴 为什么不能按时间/任务名自动猜：这些行的写入路径当年没留任何痕迹
       （`updated_at` 被后续改写刷过、`task_description` 也可能是被 `import_worklog`
       规则 A 回填的），从库里推不出来源。猜出来的来源就是伪造数据。
       所以这里只接受**已核实过的结论**（`target` 由调用方给），并把将改动的
       每一行摊开回报，让人能逐行否决（用 `ids` 收窄）。

    `dry_run=True`（默认）只回报、不写库。返回 `{target, label, total, updated, dry_run, rows}`。
    """
    if target not in SOURCE_KIND_VALUES:
        raise ValueError(f'未知来源 kind: {target!r}')
    if target in ('unlabeled', 'other'):
        raise ValueError(f'{target!r} 不是可写入的来源，别拿它打补丁')

    qs = TemporalTask.objects.filter(
        models.Q(import_batch__isnull=True) | models.Q(import_batch='')
    )
    if ids is not None:
        qs = qs.filter(id__in=list(ids))

    rows = [
        {
            'id': r['id'],
            'start': timezone.localtime(r['start_time']).strftime('%Y-%m-%d %H:%M'),
            'task_name': r['task_name'],
            # 有描述的行要人看一眼：`import_worklog` 规则 A 会回填描述，
            # 光凭描述分不清「这段是敲进去的」还是「被脚本改写过的」
            'has_description': bool((r['task_description'] or '').strip()),
        }
        for r in qs.order_by('start_time').values(
            'id', 'start_time', 'task_name', 'task_description')
    ]

    updated = 0
    if not dry_run and rows:
        # ⚠️ 用 `update()` 而不是逐条 `save()`：`updated_at` 是 auto_now，只在 `save()` 时刷。
        # 这里改的是**来源标签**、不是记录内容，不该把「最后改动」一起抹成今天
        # —— 那是这批记录唯一还能说明「什么时候被编辑过」的痕迹。
        updated = qs.update(import_batch=target)

    return {
        'target': target,
        'label': SOURCE_KIND_LABELS.get(target, target),
        'total': len(rows),
        'updated': updated,
        'dry_run': dry_run,
        'rows': rows,
    }


def _ensure_task_meta(task_names: list[str]) -> int:
    """为新出现的 task_name 建 TaskMeta；命中 TASK_TO_L2 则带活动类型+归因，否则进未归类桶。幂等。

    返回本次新建的「未归类」task_name 数（提示用户前往映射编辑器完善）。
    """
    created_unclassified = 0
    for tn in task_names:
        if TaskMeta.objects.filter(task_name=tn).exists():
            continue
        if tn in TASK_TO_L2:
            at, attr = TASK_TO_L2[tn]
        elif tn in TASK_CATEGORY_MAPPING:
            at, attr = LEGACY_FOUR_TO_L2[TASK_CATEGORY_MAPPING[tn]]
        else:
            at, attr = '未归类', None
            created_unclassified += 1
        TaskMeta.objects.create(task_name=tn, activity_type=at, default_attribution=attr, is_system=False)
    return created_unclassified


class TaskNameError(ValueError):
    """任务名改名 / 删除被拒绝 —— 视图转 400 并把原话给用户，不静默兜底。"""


def task_name_usage(task_name: str) -> dict:
    """一个任务名背后的真实用量：记录数 / 小时 / 有没有未结束的计时会话。

    🔴 台账显示「0 条 0.0h」不代表这个名字是空的：可能有一段**正在跑**的计时，
       它一停止就会写回这个名字。删除前必须看这一项，否则删完立刻复活。
    """
    agg = TemporalTask.objects.filter(task_name=task_name).aggregate(
        n=Count('id'), h=Sum('duration_hours'),
    )
    return {
        'records': int(agg['n'] or 0),
        'hours': round(float(agg['h'] or 0), 2),
        'running': TimerSession.objects.filter(task_name=task_name, status='running').exists(),
    }


def _meta_attrs(m: TaskMeta) -> dict:
    """台账里那四列属性 —— 合并时用来比「谁覆盖谁」。"""
    return {
        'activity_type': m.activity_type,
        'default_attribution': m.default_attribution,
        'counts_growth': bool(m.counts_growth),
        'daily_role': m.daily_role or '',
    }


# 属性差异的中文名（后端算、前端只打印 —— 免得两边各写一份对照表必然漂）
_ATTR_LABELS = (
    ('activity_type', 'L2 类型'),
    ('default_attribution', 'L1 归因'),
    ('counts_growth', '成长计时'),
    ('daily_role', '护栏角色'),
)


def rename_task_name(task_name: str, new_name: str, dry_run: bool = False) -> dict:
    """把 `task_name` 改名成 `new_name`；**新名已存在时即为「合并」**。

    为什么合成一个操作：改名和合并是同一件事的两种结局 ——
    目标名不存在就是改名，存在就是并过去。拆成两个按钮，用户得先自己判断
    「这个名字有没有人用过」，而那个列表就在他眼前（同一个表里）。

    合并时**以目标那行为准**（L1/L2/成长计时/护栏角色全取目标的），
    并在返回里给出 `changed_attrs`，让界面在点「确定」之前就把「会丢什么」说清。

    🔴 记录必须跟着改：只改 `temporal_task_meta` 而不动 `temporal_task`
       会让这个名字变成 0h、旧名的时长全部从台账消失 —— 且不报错。
    🔴 `TemporalTask` 是 `managed=False` 的外部表，但 `.update()` 是合法写入
       （手工新增 / CSV 导入 / 计时停止本来就在写它），这里只改 `task_name` 一列。

    `dry_run=True` 只算不写 —— 弹窗的「影响预览」与真执行走**同一份判据**。
    """
    new_name = (new_name or '').strip()
    if not new_name:
        raise TaskNameError('新任务名不能为空')
    if len(new_name) > 255:
        raise TaskNameError('新任务名最长 255 个字')
    if new_name == task_name:
        raise TaskNameError('新旧名字相同，什么都不会变')

    src = TaskMeta.objects.filter(task_name=task_name).first()
    if src is None:
        raise TaskNameError(f'任务名「{task_name}」不在映射表里')

    # ⚠️ 必须按主键排掉自己：MySQL 的 `utf8mb4_general_ci` 不区分大小写，
    #    `filter(task_name='abc')` 会把 'Abc' 这一行（也就是 src 自己）也捞出来，
    #    于是「只改大小写」会被误判成「并到自己身上」，合并分支一删就把这行干掉。
    target = TaskMeta.objects.filter(task_name=new_name).exclude(pk=src.pk).first()

    usage = task_name_usage(task_name)
    payload = {
        'task_name': task_name,
        'new_name': new_name,
        'merged': target is not None,
        'moved_records': usage['records'],
        'moved_hours': usage['hours'],
        'dry_run': dry_run,
        'kept': _meta_attrs(target) if target is not None else None,
        'dropped': None,
        'changed_attrs': [],
    }

    if target is not None:
        before, after = _meta_attrs(src), _meta_attrs(target)
        payload['dropped'] = before
        payload['changed_attrs'] = [
            label for key, label in _ATTR_LABELS if before[key] != after[key]
        ]
    else:
        # 改名：属性跟着名字一起走，所以「丢掉的」就是没有
        payload['dropped'] = None

    if dry_run:
        return payload

    with transaction.atomic():
        # 记录先改名：万一后面出错，事务回滚，不会留下「字典改了、记录没改」
        TemporalTask.objects.filter(task_name=task_name).update(
            task_name=new_name, updated_at=timezone.now(),
        )
        # 正在跑的计时也要改：否则它一停止就写回旧名，旧名立刻复活
        TimerSession.objects.filter(task_name=task_name, status='running').update(task_name=new_name)
        if target is not None:
            # 合并：保留目标行，删掉源行。源行的备注不丢 —— 并进目标备注里
            if (src.note or '').strip():
                sep = '' if not (target.note or '').strip() else '\n'
                target.note = f'{target.note or ""}{sep}合并自「{task_name}」：{src.note}'
                target.save(update_fields=['note', 'updated_at'])
            src.delete()
        else:
            src.task_name = new_name
            src.save(update_fields=['task_name', 'updated_at'])
    return payload


def delete_task_name(task_name: str) -> dict:
    """删掉一行台账 —— **只有名下一条记录都没有时才允许**。

    🔴 有记录时拒绝，而不是「连记录一起删」或「只删字典」：
       · 连记录删 = 抹掉真实发生过的时长，不可逆；
       · 只删字典 = 这些记录从台账里消失、按兜底归因计入，**不报错**，
         从此没人知道那 N 小时去哪了（`meta_ledger` 是遍历 TaskMeta 的）。
       所以名字下有量时，正确的出口是「合并到别处」，不是删除。
    """
    src = TaskMeta.objects.filter(task_name=task_name).first()
    if src is None:
        raise TaskNameError(f'任务名「{task_name}」不在映射表里')

    usage = task_name_usage(task_name)
    if usage['records']:
        raise TaskNameError(
            f'「{task_name}」名下还有 {usage["records"]} 条记录（{usage["hours"]}h），不能删除：'
            f'删掉不会删记录，只会让它从台账消失、按兜底归因计入。'
            f'如果你是想把它并到别处，用「改名 / 合并」。'
        )
    if usage['running']:
        raise TaskNameError(f'「{task_name}」有一段正在计时，停止后会重新写回这个名字，先停掉再删')

    src.delete()
    return {'task_name': task_name}


class CSVImportService:
    """CSV 导入服务：按 ATracker 原始记录逐条落库（v3.58.5 起不再按「任务名 + 日期」合并）"""

    REQUIRED_COLUMNS = ['任务名称', '开始时间', '持续时间（小时）']

    @staticmethod
    def _parse_datetime(s: str) -> datetime | None:
        """解析日期时间，支持 ISO 和中文字段格式"""
        if not s:
            return None
        s = s.strip()
        # ISO 格式：2026-06-03 23:29:36
        try:
            return datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            pass
        # 中文格式：2026年6月3日 23:29:36
        import re
        m = re.match(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日\s+(\d{1,2}):(\d{2}):(\d{2})', s)
        if m:
            return datetime(*map(int, m.groups()))
        return None

    # ── 唯一解析实现（预演与落库共用，🔴 别各写一份）────────────────────
    def _read_rows(self, file) -> tuple[list[dict], dict, str]:
        """把上传的 CSV 解成标准行列表；第三个返回值是给人看的错因（`''` = 没出错）。

        🔴 **预演与落库必须共用这一份**：预演按 `row_no` 告诉用户「第 7 行不要」，
           落库若用另一份解析、哪怕只差一行，就会**跳错记录** ——
           表现是「该跳的没跳、该留的被吞」，两边都不报错。
        🔴 `row_no` 是 **CSV 物理行号（表头占第 1 行）**，不是 rows 的下标：
           解析失败的行会占掉一个行号，用下标当行号就会整体错位。
        """
        raw = file.read()
        print(f'[CSV 导入] 收到文件: {file.name!r}, 大小: {len(raw)} 字节')

        # 尝试解码（UTF-8 → GBK → 自动检测）
        content = None
        for enc in ('utf-8-sig', 'utf-8', 'gbk', 'gb2312', 'latin-1'):
            try:
                content = raw.decode(enc)
                if enc != 'utf-8':
                    print(f'[CSV 导入] 使用编码: {enc}')
                break
            except (UnicodeDecodeError, LookupError):
                continue
        if content is None:
            return [], {}, '无法解码文件，请确认编码为 UTF-8 或 GBK'

        # ── 解析 CSV ──
        reader = csv.DictReader(io.StringIO(content))
        print(f'[CSV 导入] CSV 列名: {reader.fieldnames}')

        missing = [c for c in self.REQUIRED_COLUMNS if c not in reader.fieldnames]
        if missing:
            print(f'[CSV 导入] 缺少必要列: {missing}')
            return [], {}, f'缺少必要列：{", ".join(missing)}'

        rows = []
        parse_errors = {'no_name': 0, 'no_time': 0, 'bad_duration': 0, 'bad_date': 0}
        for i, row in enumerate(reader, start=2):  # 行号从 2 开始（header 占第 1 行）
            name = (row.get('任务名称') or '').strip()
            start = row.get('开始时间', '').strip()
            dur_str = row.get('持续时间（小时）', '').strip()

            if not name:
                parse_errors['no_name'] += 1
                continue
            if not start:
                parse_errors['no_time'] += 1
                continue
            try:
                dur = float(dur_str) if dur_str else 0
            except ValueError:
                parse_errors['bad_duration'] += 1
                dur = 0
            if dur <= 0:
                parse_errors['bad_duration'] += 1
                continue
            try:
                start_dt = self._parse_datetime(start)
            except (ValueError, TypeError):
                start_dt = None
            if start_dt is None:
                parse_errors['bad_date'] += 1
                if i <= 5:
                    print(f'[CSV 导入] 第{i}行 日期解析失败: start={start!r}')
                continue

            rows.append({
                'row_no': i,
                'name': name,
                'start_dt': start_dt,
                'date': start_dt.date(),
                'duration': dur,
                'description': (row.get('任务说明') or '').strip(),
                'end_time_str': (row.get('结束时间') or '').strip(),
                'notes': (row.get('附注') or '').strip(),
                'tags': (row.get('标签') or '').strip(),
            })

        print(f'[CSV 导入] 解析结果: 有效 {len(rows)} 行, 跳过详情: {parse_errors}')
        return rows, parse_errors, ''

    def preview_from_csv(self, file) -> dict:
        """只读预演：解析 + 与库对账，**一个字都不写库**（不建 TaskMeta、不刷周缓存）。

        回答一个问题：**这份 CSV 落进去，会和库里已有什么东西撞上？**
        两个维度正交，别混：

        - **出路**（`already_exists`）：库里已有同一条 ⇒ 落库时跳过或更新。这是
          `find_duplicate_task` 的事（同任务名 + 比值 ≥0.8），预演只数不判。
        - **关系**（`contained/edge/review/likely_dup`）：与库里**其它**记录的时段
          关系（不限任务名），由 `classify_overlap` 分四类。

        一条 CSV 行只归一类，所以 `total = already_exists + clean + Σ四类`。
        只把**需要人看**的行放进 `rows`（clean 只有计数）——
        100 行里 96 行干净，不该占满屏幕。
        """
        from collections import Counter

        rows, parse_errors, error = self._read_rows(file)
        if error:
            return {'error': error}

        # CSV 内部重复（同一次导出里同任务名 + 同开始时刻）—— 与落库同一个键
        seen = Counter(_dedup_key(r['name'], r['start_dt']) for r in rows)
        inner_dup = sum(n - 1 for n in seen.values() if n > 1)

        verdict_counts = {k: 0 for k in CONFLICT_KEYS}
        already_exists = 0
        detail_rows = []
        seen_once = set()
        for r in rows:
            key = _dedup_key(r['name'], r['start_dt'])
            if seen_once.__contains__(key):
                continue          # CSV 内重复行：落库时会被丢弃，不让它二次占位
            seen_once.add(key)

            start_aware = timezone.make_aware(r['start_dt'])
            end_dt = self._parse_datetime(r['end_time_str'])
            end_aware = timezone.make_aware(end_dt) if end_dt else None
            duration = float(r['duration'])

            if find_duplicate_task(r['name'], start_aware, end_aware, duration):
                already_exists += 1
                continue

            conflicts = find_overlaps(
                start_aware, end_aware, duration, task_name=r['name'],
            )
            if not conflicts:
                continue
            verdict = max(
                (c.get('relation') or CONFLICT_REVIEW for c in conflicts),
                key=lambda k: CONFLICT_SEVERITY.get(k, 0),
            )
            verdict_counts[verdict] += 1
            if verdict not in (CONFLICT_REVIEW, CONFLICT_LIKELY_DUP):
                # `contained` / `edge` 只计数、不进清单：本库 214 对包含关系是常态，
                # 列出来就是噪音，而**「有没有列出来」和「要不要人看」必须是同一件事** ——
                # 否则前端写着「下面 3 行需要你判断」，表格里却混着 3 行合法的细分。
                continue
            detail_rows.append({
                'row_no': r['row_no'],
                'task_name': r['name'],
                'start_time': timezone.localtime(start_aware).strftime('%Y-%m-%d %H:%M'),
                'end_time': (timezone.localtime(end_aware).strftime('%H:%M')
                             if end_aware else ''),
                'hours': round(duration, 2),
                'verdict': verdict,
                'conflict_total': len(conflicts),
                # 只带最严重的两条：清单是让人「认出来」，不是全文比对
                'conflicts': [
                    {k: c[k] for k in ('id', 'task_name', 'start_time', 'end_time',
                                       'overlap_minutes', 'relation')}
                    for c in sorted(
                        conflicts,
                        key=lambda c: -CONFLICT_SEVERITY.get(c.get('relation'), 0),
                    )[:2]
                ],
            })

        counted = already_exists + sum(verdict_counts.values())
        return {
            'total_parsed': len(rows),
            'parse_errors': parse_errors,
            'inner_duplicate': inner_dup,
            'summary': {
                'total': len(rows),
                'already_exists': already_exists,
                'clean': len(rows) - inner_dup - counted,
                'contained': verdict_counts[CONFLICT_CONTAINED],
                'edge': verdict_counts[CONFLICT_EDGE],
                'review': verdict_counts[CONFLICT_REVIEW],
                'likely_dup': verdict_counts[CONFLICT_LIKELY_DUP],
                'needs_review': (verdict_counts[CONFLICT_REVIEW]
                                 + verdict_counts[CONFLICT_LIKELY_DUP]),
            },
            'rows': detail_rows,
        }

    @transaction.atomic
    def import_from_csv(self, file, batch_id: str, skip_rows=None) -> dict:
        """落库。`skip_rows` = 预演里被勾掉的 CSV 行号集合（物理行号，同 `row_no`）。

        🔴 行号对不上就**报错不写库**，不静默忽略：`skip_rows` 传成 0-based、
           或文件被换过，否则会「跳了不该跳的行」而界面显示成功。
        """
        rows, parse_errors, error = self._read_rows(file)
        if error:
            return {'error': error, 'inserted': 0, 'updated': 0, 'skipped': 0}

        parsed_total = len(rows)      # 解析成功总数（在扣掉用户勾掉的那些**之前**）
        skipped_by_user = 0
        if skip_rows:
            try:
                skip = {int(n) for n in skip_rows}
            except (TypeError, ValueError):
                return {'error': 'skip_rows 必须是行号列表', 'inserted': 0,
                        'updated': 0, 'skipped': 0}
            unknown = sorted(skip - {r['row_no'] for r in rows})
            if unknown:
                return {
                    'error': (f'第 {",".join(map(str, unknown))} 行不在本次解析结果里，'
                              '可能文件换了 —— 请重新检查一次再导入'),
                    'inserted': 0, 'updated': 0, 'skipped': 0,
                }
            kept = [r for r in rows if r['row_no'] not in skip]
            skipped_by_user = len(rows) - len(kept)
            rows = kept

        # ── v3.58.5：按 ATracker 原始记录逐条导入（不再按「任务名称 + 日期」合并）──
        # 一条 CSV 记录 → 一行 DB：start_time = 该条开始时刻、end_time = 该条结束时刻、
        # duration_hours = 该条时长。这样「时长 == 结束 − 开始」自然成立，count 类指标
        # 也回到真实记录数（旧的合并口径会把同一天同名任务压成一行并把时长累加）。
        # CSV 内若出现完全重复行（同「任务名 + 开始时刻」），按 key 去重并计数（不静默丢弃）。
        deduped: dict[tuple[str, datetime], dict] = {}
        duplicated = 0
        for r in rows:
            key = _dedup_key(r['name'], r['start_dt'])
            if key in deduped:
                duplicated += 1
                continue
            deduped[key] = r

        print(f'[CSV 导入] 原始 {len(rows)} 条 → 去重后 {len(deduped)} 条（CSV 内重复 {duplicated} 条）')

        # ── 覆盖模式写入（去重键 = task_name + start_time） ──
        # 注意：v0.3 起不再写入 category_level1/category_color（旧四大类字段停用），
        # 分类改走独立 managed 表 temporal_task_meta（由 migrate_temporal_categories 或下方自动建）。
        # protected = 命中但「起止被工作日志校准过」⇒ 保留校准值、不用源数据覆盖的条数
        stats = {'inserted': 0, 'updated': 0, 'skipped': 0, 'protected': 0,
                 'deduplicated': duplicated, 'total_parsed': parsed_total,
                 # 用户在预演里自己勾掉的，与「库已有故跳过」分开报：
                 # 合成一个数就说不清「这 5 条是我不要的，还是系统吞的」。
                 'skipped_by_user': skipped_by_user}
        for (name, start_dt), r in deduped.items():
            duration = float(r['duration'])
            start_aware = timezone.make_aware(start_dt)
            end_dt = self._parse_datetime(r['end_time_str'])
            end_aware = timezone.make_aware(end_dt) if end_dt else None

            task_defaults = {
                'task_name': name,
                'task_description': r['description'],
                'start_time': start_aware,
                'end_time': end_aware,
                'duration_hours': duration,
                'notes': r['notes'],
                'tags': r['tags'],
                'task_type': name,
                'import_batch': batch_id,
            }
            # 日历字段（year/mon/day/week/quarter）走公共派生函数；不传 end_dt——
            # 导入的时长以 ATracker 自带的为准（可能含计时器暂停），不用「结束−开始」覆盖。
            task_defaults.update(build_time_fields(start_dt))

            # 判重 = 「同任务名 + 时段重叠」（单一真源 `find_duplicate_task`）。
            # v3.60.29 之前这里是 (task_name, start_time) 的**秒级精确匹配**，会被
            # `import_worklog` 规则 A 的「时段补全」（改写 start_time 08:05→08:00）打穿
            # ⇒ 重复导入时静默多插一条。推导见 TECH-NOTES §64。
            existing = find_duplicate_task(name, start_aware, end_aware, duration)

            if existing:
                # 🔴 v3.60.29 保护：命中、但**开始时刻与源数据不同** ⇒ 库里这条的起止被别的
                # 流程改写过（`import_worklog` 规则 A 的「时段补全」：08:05→08:00，附注留了
                # 原时刻）。源数据带的是**改写之前**的旧值 ⇒ 不许用它覆盖回去，否则每次重导
                # CSV 都会**静默撤销**那次日志校准（把 10h 打回 9.92h）。
                # ⚠️ 旧判重命中不了这条（它直接 create 出一条重复）—— 「多一条」与
                # 「改回旧值」两种错都错，但后者在界面上看不出来，所以单列一个计数键。
                if (existing.start_time.replace(microsecond=0)
                        != start_aware.replace(microsecond=0)):
                    stats['protected'] += 1
                    continue
                # 时长 / 结束时刻 / 附注（CSV 有值时）全同 → 跳过，保证重复导入幂等
                same_hours = abs(float(existing.duration_hours or 0) - duration) < 0.01
                same_end = end_aware is None or existing.end_time == end_aware
                same_notes = not r['notes'] or (existing.notes or '') == r['notes']
                if same_hours and same_end and same_notes:
                    stats['skipped'] += 1
                    continue
                fields = {
                    'duration_hours': duration,
                    'notes': r['notes'] or (existing.notes or ''),
                    'import_batch': batch_id,
                    'updated_at': timezone.now(),
                }
                if end_aware is not None:
                    fields['end_time'] = end_aware
                TemporalTask.objects.filter(id=existing.id).update(**fields)
                stats['updated'] += 1
            else:
                TemporalTask.objects.create(**task_defaults)
                stats['inserted'] += 1

        # ── 自动为新出现的 task_name 建 L2 映射（命中 TASK_TO_L2 才建，否则进未归类桶）──
        stats['unclassified'] = _ensure_task_meta(sorted({name for name, _ in deduped}))

        # ── 自动刷新周度缓存 ──
        from apps.temporal.management.commands.refresh_weekly_cache import Command
        try:
            Command().handle()
            print('[CSV 导入] 周度缓存已刷新')
        except Exception as e:
            print(f'[CSV 导入] 缓存刷新失败: {e}')

        return stats


class TemporalStatsService:
    """时间统计服务（v0.3：聚合维度从 category_level1 改为 L1/L2）"""

    @staticmethod
    def get_overview(year: int | None = None) -> dict:
        qs = TemporalTask.objects.all()
        if year:
            qs = qs.filter(year=year)

        total_hours = qs.aggregate(s=models.Sum('duration_hours'))['s'] or 0
        total_records = qs.count()
        # order_by() 清序：避免 Django 把 start_time 注入 DISTINCT 列致去重失效
        active_days = qs.order_by().values('year', 'mon', 'day').distinct().count()

        rows = qs.values('task_name').annotate(h=models.Sum('duration_hours'))
        names = [r['task_name'] for r in rows]
        meta = resolve_task_meta(names)
        attr = resolve_attribution(names)

        attribution_breakdown = defaultdict(float)   # L1 归因
        activity_breakdown = defaultdict(float)      # L2 活动类型
        for r in rows:
            tn = r['task_name']
            h = float(r['h'] or 0)
            m = meta.get(tn)
            at = m['activity_type'] if m else '未归类'
            a = attr.get(tn, DEFAULT_FALLBACK_ATTR)
            activity_breakdown[at] += h
            attribution_breakdown[a] += h

        return {
            'total_hours': round(float(total_hours), 2),
            'total_records': total_records,
            'active_days': active_days,
            'attribution_breakdown': {k: round(v, 2) for k, v in attribution_breakdown.items()},
            'activity_breakdown': {k: round(v, 2) for k, v in activity_breakdown.items()},
            'completeness': TemporalStatsService.get_completeness(year),
        }

    @staticmethod
    def get_trend(year: int | None = None, group: str = 'month', level: str = 'l1') -> list:
        """趋势数据：level=l1(归因) / l2(活动类型) / l3(task_name)"""
        qs = TemporalTask.objects.all()
        if year:
            qs = qs.filter(year=year)

        tasks = qs.values('task_name', 'start_time', 'duration_hours')
        names = [t['task_name'] for t in tasks]
        meta = resolve_task_meta(names)
        attr = resolve_attribution(names)

        period_data = defaultdict(lambda: defaultdict(float))
        for t in tasks:
            st = t['start_time']
            if not st:
                continue
            tn = t['task_name']
            m = meta.get(tn)
            if level == 'l3':
                key2 = tn
            elif level == 'l2':
                key2 = (m['activity_type'] if m else '未归类')
            else:  # l1 = 价值归因
                key2 = attr.get(tn, DEFAULT_FALLBACK_ATTR)
            hours = float(t['duration_hours'] or 0)
            if group == 'month':
                p = st.strftime('%Y-%m')
            elif group == 'week':
                p = f"{st.year}-W{st.isocalendar()[1]:02d}"
            else:
                p = st.strftime('%Y-%m-%d')
            period_data[p][key2] += hours

        all_keys = set()
        for d in period_data.values():
            all_keys.update(d.keys())
        result = []
        for p in sorted(period_data.keys()):
            item = {'period': p}
            for k in sorted(all_keys):
                item[k] = round(period_data[p].get(k, 0.0), 2)
            result.append(item)
        return result

    @staticmethod
    def get_balance(year: int | None = None) -> dict:
        """平衡轮数据：按 L2 活动类型聚合（v0.3 改自 category_level1）"""
        qs = TemporalTask.objects.all()
        if year:
            qs = qs.filter(year=year)

        total_hours = float(qs.aggregate(s=models.Sum('duration_hours'))['s'] or 0)
        rows = qs.values('task_name').annotate(h=models.Sum('duration_hours'))
        meta = resolve_task_meta([r['task_name'] for r in rows])

        at_map = defaultdict(float)
        for r in rows:
            m = meta.get(r['task_name'])
            at = m['activity_type'] if m else '未归类'
            at_map[at] += float(r['h'] or 0)

        categories = []
        for at in sorted(at_map.keys()):
            h = round(at_map[at], 2)
            pct = round(h / total_hours * 100, 1) if total_hours > 0 else 0
            categories.append({
                'name': at,
                'hours': h,
                'percentage': pct,
                'color': ACTIVITY_TYPE_COLORS.get(at, '#9CA3AF'),
            })
        return {'total_hours': round(total_hours, 2), 'categories': categories}

    @staticmethod
    def get_sunburst(year: int | None = None) -> dict:
        """旭日/嵌套饼图数据（3 环）：L1 归因 → L2 活动类型 → L3 task_name"""
        qs = TemporalTask.objects.all()
        if year:
            qs = qs.filter(year=year)

        rows = qs.values('task_name').annotate(h=models.Sum('duration_hours'))
        names = [r['task_name'] for r in rows]
        meta = resolve_task_meta(names)
        attr = resolve_attribution(names)

        tree: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
        for r in rows:
            tn = r['task_name']
            h = float(r['h'] or 0)
            m = meta.get(tn)
            at = m['activity_type'] if m else '未归类'
            a = attr.get(tn, DEFAULT_FALLBACK_ATTR)
            tree[a][at][tn] += h

        def _ordered(keys, order):
            return sorted(keys, key=lambda n: (order.index(n) if n in order else 99, str(n)))

        groups = []
        for a in _ordered(tree.keys(), ATTRIBUTION_ORDER):
            l2_map = tree[a]
            l1_hours = sum(sum(l3.values()) for l3 in l2_map.values())
            children = []
            for at in _ordered(l2_map.keys(), []):
                l3_map = l2_map[at]
                children.append({
                    'name': at,
                    'hours': round(sum(l3_map.values()), 2),
                    'color': ACTIVITY_TYPE_COLORS.get(at, '#CBD5E1'),
                    'children': [
                        {'name': tn, 'hours': round(hv, 2)}
                        for tn, hv in sorted(l3_map.items(), key=lambda x: -x[1])
                    ],
                })
            groups.append({
                'name': a,
                'hours': round(l1_hours, 2),
                'color': ATTRIBUTION_COLORS.get(a, '#94A3B8'),
                'children': children,
            })
        return {'groups': groups}

    @staticmethod
    def get_168h_structure(year: int | None = None, weeks: int = 12) -> dict:
        """近 N 周 168h 结构：by_l1=归因 / by_l2=类型 / by_l3=task_name + 完整度"""
        qs = TemporalTask.objects.all()
        if year:
            qs = qs.filter(year=year)

        rows = qs.values('task_name', 'year', 'week').annotate(h=models.Sum('duration_hours'))
        names = [r['task_name'] for r in rows]
        meta = resolve_task_meta(names)
        attr = resolve_attribution(names)

        day_map = defaultdict(set)
        for d in qs.order_by().values('year', 'week', 'mon', 'day').distinct():
            day_map[(d['year'], d['week'])].add((d['mon'], d['day']))

        by_week = defaultdict(lambda: {
            'by_l1': defaultdict(float), 'by_l2': defaultdict(float), 'by_l3': defaultdict(float),
            'classified': 0.0,
        })
        for r in rows:
            tn = r['task_name']
            h = float(r['h'] or 0)
            yw = (r['year'], r['week'])
            m = meta.get(tn)
            at = (m['activity_type'] if m else '未归类')
            a = attr.get(tn, DEFAULT_FALLBACK_ATTR)
            by_week[yw]['by_l1'][a] += h
            by_week[yw]['by_l2'][at] += h
            by_week[yw]['by_l3'][tn] += h
            if m and m['activity_type'] != '未归类':
                by_week[yw]['classified'] += h

        result = []
        for yw in sorted(by_week.keys()):
            d = by_week[yw]
            days = len(day_map.get(yw, set()))
            denom = days * 16
            by_l1 = {k: round(v, 2) for k, v in d['by_l1'].items()}
            result.append({
                'year': yw[0],
                'week': yw[1],
                'by_l1': by_l1,
                'by_l2': {k: round(v, 2) for k, v in d['by_l2'].items()},
                'by_l3': {k: round(v, 2) for k, v in d['by_l3'].items()},
                'completeness': round(d['classified'] / denom, 4) if denom else 0,
            })
        if weeks:
            result = result[-weeks:]
        return {'weeks': result}

    @staticmethod
    def get_completeness(year: int | None = None) -> dict:
        """记录完整度：已归类小时 / (16h/天 × 有记录天数)

        v0.2 决策 3：未归类参与总时长（灰显）但不参与完整度分母/分子。
        """
        qs = TemporalTask.objects.all()
        if year:
            qs = qs.filter(year=year)

        total = qs.aggregate(s=models.Sum('duration_hours'))['s'] or 0
        classified_names = list(
            TaskMeta.objects.exclude(activity_type='未归类').values_list('task_name', flat=True)
        )
        covered = qs.filter(task_name__in=classified_names).aggregate(s=models.Sum('duration_hours'))['s'] or 0
        days = qs.order_by().values('year', 'mon', 'day').distinct().count()
        hours_per_day = 16  # 完整度分母基数：按「清醒时段 16h/天」计
        denom = days * hours_per_day
        return {
            'total_hours': round(float(total), 2),
            'classified_hours': round(float(covered), 2),
            'completeness': round(covered / denom, 4) if denom else 0,
            'days_recorded': days,
            'denominator_hours_per_day': hours_per_day,
            # 总时间（小时）= 基数 × 有记录天数，供前端展示「已记录 / 总时间」
            'denominator_hours': round(float(denom), 2),
        }

    @staticmethod
    def get_ranking(year: int | None = None, limit: int = 10) -> list:
        """任务排行（L3 task_name），附 L2 活动类型与 L1 归因"""
        qs = TemporalTask.objects.all()
        if year:
            qs = qs.filter(year=year)

        rankings = list(
            qs.values('task_name').annotate(
                total_hours=models.Sum('duration_hours'),
                record_count=models.Count('id'),
            ).order_by('-total_hours')[:limit]
        )
        names = [r['task_name'] for r in rankings]
        meta = resolve_task_meta(names)
        attr = resolve_attribution(names)

        out = []
        for r in rankings:
            tn = r['task_name']
            at = (meta.get(tn) or {}).get('activity_type', '未归类')
            out.append({
                'task_name': tn,
                'activity_type': at,
                'attribution': attr.get(tn, DEFAULT_FALLBACK_ATTR),
                # 兼容旧键名
                'category': at,
                'color': ACTIVITY_TYPE_COLORS.get(at, '#9CA3AF'),
                'total_hours': round(float(r['total_hours'] or 0), 2),
                'record_count': r['record_count'],
            })
        return out

    @staticmethod
    def get_frequent_names(months: int = 3, limit: int = 10) -> dict:
        """最近 N 个月最频繁的任务名（手工新增记录的快捷候选）

        口径**只在这一处**（前端不判、不复刻）：

        - 窗口：`[今天往前 N 个自然月, 现在)` 半开区间。
          用自然月而不是「N×30 天」——「最近 3 个月」按日历月理解更贴近直觉。
          月末对齐照 `apps/health/views.py` 的既有写法（1/31 往前 1 月 → 2/28 或 2/29）。
        - 排序：记录次数 ↓ → 累计时长 ↓ → 最近使用 ↓ → 任务名 ↑（末位兜底保证稳定）。
          **「频繁」按次数算**；时长只用来给同频次的任务分先后（做了 5 次 4 小时
          比做了 5 次 5 分钟更该排在前面）。
        - 排除空任务名：历史数据里可能有空串，它不是可选的任务。

        🔴 外部表 `Meta.ordering = ['-start_time']`：末尾必须给**显式排序** ——
           它同时覆盖默认排序，`start_time` 不会进聚合的 GROUP BY。
           若换成 `values_list().distinct()` 那类写法、又不显式清序，同一任务名会被
           按开始时刻拆成多行、`record_count` 恒为 1，排行变成「哪个时刻最忙」而不是
           「哪个任务最常做」，而且**不报错**（`test_meta_ledger` 里踩过同款）。
        """
        now = timezone.localtime()
        y, m = now.year, now.month - months
        while m <= 0:
            m += 12
            y -= 1
        window_start = now.replace(
            year=y, month=m, day=min(now.day, calendar.monthrange(y, m)[1]),
        )

        rows = list(
            TemporalTask.objects
            .filter(start_time__gte=window_start, start_time__lt=now)
            .exclude(task_name='')
            .values('task_name')
            .annotate(
                record_count=Count('id'),
                total_hours=Sum('duration_hours'),
                last_used=Max('start_time'),
            )
            .order_by('-record_count', '-total_hours', '-last_used', 'task_name')[:limit]
        )
        return {
            'months': months,
            'limit': limit,
            'window_start': window_start.date().isoformat(),
            'items': [
                {
                    'task_name': r['task_name'],
                    'record_count': int(r['record_count']),
                    'total_hours': round(float(r['total_hours'] or 0), 2),
                }
                for r in rows
            ],
        }

    @staticmethod
    def get_distribution(year: int | None = None) -> dict:
        qs = TemporalTask.objects.all()
        if year:
            qs = qs.filter(year=year)

        tasks = qs.values('start_time', 'duration_hours')
        slots = {'morning': 0.0, 'afternoon': 0.0, 'evening': 0.0}

        for t in tasks:
            st = t['start_time']
            if not st:
                continue
            hours = float(t['duration_hours'] or 0)
            h = st.hour
            if 6 <= h < 12:
                slots['morning'] += hours
            elif 12 <= h < 18:
                slots['afternoon'] += hours
            else:
                slots['evening'] += hours

        total = sum(slots.values())
        return {
            'morning': round(slots['morning'], 2),
            'afternoon': round(slots['afternoon'], 2),
            'evening': round(slots['evening'], 2),
            'morning_pct': round((slots['morning'] / total) * 100, 1) if total > 0 else 0,
            'afternoon_pct': round((slots['afternoon'] / total) * 100, 1) if total > 0 else 0,
            'evening_pct': round((slots['evening'] / total) * 100, 1) if total > 0 else 0,
        }

    @staticmethod
    def get_calendar(year: int | None = None) -> list:
        qs = TemporalTask.objects.all()
        if year:
            qs = qs.filter(year=year)

        days = qs.values('year', 'mon', 'day').annotate(
            total_hours=models.Sum('duration_hours'),
            record_count=models.Count('id'),
        ).order_by('year', 'mon', 'day')

        return [
            {
                'date': f"{d['year']}-{d['mon']}-{str(d['day']).zfill(2)}",
                'hours': round(float(d['total_hours'] or 0), 2),
                'count': d['record_count'],
            }
            for d in days
        ]


class OneDayPageService:
    """每日记录统计服务"""

    @staticmethod
    def get_stats():
        """获取全量统计信息"""
        total_count = OneDayPage.objects.count()

        type_stats = list(OneDayPage.objects.values('otype').annotate(
            count=Count('oid'),
            total_oneday=Sum('oneday'),
            total_page=Sum('page'),
            total_words=Sum('total'),
            avg_words=Avg('total'),
        ))

        year_stats = list(OneDayPage.objects.values('years').annotate(
            count=Count('oid'),
            total_oneday=Sum('oneday'),
            total_page=Sum('page'),
            total_words=Sum('total'),
            avg_words=Avg('total'),
        ).order_by('-years'))

        month_stats = list(OneDayPage.objects.extra(
            select={'month': "DATE_FORMAT(begin_date, '%%Y-%%m')"},
        ).values('month').annotate(
            count=Count('oid'),
            total_oneday=Sum('oneday'),
            total_page=Sum('page'),
            total_words=Sum('total'),
        ).order_by('-month')[:12])

        now = timezone.now()
        month_start = datetime(now.year, now.month, 1)
        month_count = OneDayPage.objects.filter(begin_date__gte=month_start).count()

        total_oneday = OneDayPage.objects.aggregate(total=Sum('oneday'))['total'] or 0
        total_page = OneDayPage.objects.aggregate(total=Sum('page'))['total'] or 0
        total_words = OneDayPage.objects.aggregate(total=Sum('total'))['total'] or 0
        avg_words = OneDayPage.objects.aggregate(avg=Avg('total'))['avg'] or 0

        return {
            'total_count': total_count,
            'month_count': month_count,
            'total_oneday': total_oneday,
            'total_page': total_page,
            'total_words': total_words,
            'avg_words': round(avg_words, 2),
            'type_stats': type_stats,
            'year_stats': year_stats,
            'month_stats': month_stats,
        }


class DailyLogAutoService:
    """每日默认日记自动生成服务"""

    @staticmethod
    def generate_default_log(user_id: int = 1) -> OneDayPage | None:
        """为今天生成默认日记（如果今天还没有任何日记）"""
        today = date.today()

        # 使用日期字段比较，兼容 DateField
        if OneDayPage.objects.filter(
            user_id=user_id,
            begin_date__year=today.year,
            begin_date__month=today.month,
            begin_date__day=today.day,
        ).exists():
            return None

        log = OneDayPage.objects.create(
            user_id=user_id,
            title='幸福未被发现，就叫做普通的一天',
            begin_date=today,
            otype='ONEDAY',
            oneday=0,
            page=0,
            total=0,
            years=str(today.year),
        )
        return log


# ══════════════════════════════════════════════════════════════
# 日常护栏：「今天的三条线」（v3.64.12）
# ══════════════════════════════════════════════════════════════

def contrib_excluded_names() -> set[str]:
    """贡献图要排除的任务名 = 常量名单 ∪ 角色为睡眠类的任务名。

    🔴 取**并集**而不是替换：库里的角色是异步补上的（要人跑 migrate、要人在编辑器里点），
       只认库会让「还没标」的那几天贡献图口径突然变宽（睡眠重新变成主导归因）。
       并集保证：老名字永远排除，新标的睡眠分类也能跟着进。
    """
    sleep_names = set(
        TaskMeta.objects.filter(daily_role__in=('sleep_night', 'nap'))
        .values_list('task_name', flat=True),
    )
    return set(CONTRIB_EXCLUDED_TASK_NAMES) | sleep_names


def _local_day_bounds(target_date: date):
    """本地日 [00:00, 次日 00:00) 半开区间（USE_TZ 下不碰 `__date`）。"""
    tz = timezone.get_current_timezone()
    start = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=tz)
    return start, start + timedelta(days=1)


def _attribution_hours_and_count(target_date: date, attribution_value: str):
    """按 L1 归因取当日时长：`(小时数, 记录条数)`；当天没有命中归因的记录 ⇒ `(None, 0)`。

    🔴 用 `resolve_attribution`，**跟贡献图 / 时间统计页同一把尺子**
       （规则覆盖 > TaskMeta 默认 > 兜底）。若另写一套「直接读 default_attribution」，
       图上说流失 4.8h、护栏说 2.3h —— 同一屏两个数，且两边都「看着合理」。
    🔴 归因是**按任务名**解析的，所以取全天任务名一次解析，不逐条查库。
    """
    day_start, day_end = _local_day_bounds(target_date)
    rows = list(TemporalTask.objects.filter(
        start_time__gte=day_start, start_time__lt=day_end,
    ).values_list('task_name', 'duration_hours'))
    if not rows:
        return None, 0

    attr = resolve_attribution(sorted({tn for tn, _ in rows}))
    total, count = 0.0, 0
    for task_name, hours in rows:
        if not hours or attr.get(task_name) != attribution_value:
            continue
        total += float(hours)
        count += 1
    return (round(total, 2) if count else None), count


def _guard_value_and_count(spec: dict, names: list[str], target_date: date):
    """返回 `(小时数, 记录条数)`。没记录 ⇒ `(None, 0)` —— 与「0 小时」严格区分。"""
    # 归因口径的线（流失）不看角色：没有角色可漏标，也就不存在「没标」这一态
    if spec.get('role') is None:
        return _attribution_hours_and_count(target_date, spec['attribution_value'])

    if not names:
        return None, 0

    if spec['day_bucket'] == 'wakeup_day':
        # 夜间睡眠：按**醒来那一刻**归属。23:40 睡 8h ⇒ 归到次日。
        # 🔴 这是全链路最容易做错的一处：若按 start_time 的日期归属，
        #    上午打开页面会永远显示「今天还没有睡眠记录」—— 且不报错。
        # 取数窗口往前放宽 36h：跨零点前入睡的那一觉也要捞到。
        day_start, _ = _local_day_bounds(target_date)
        qs = TemporalTask.objects.filter(
            task_name__in=names,
            start_time__gte=day_start - timedelta(hours=36),
            start_time__lt=day_start + timedelta(hours=36),
        ).values_list('start_time', 'duration_hours')
        total, count = 0.0, 0
        tz = timezone.get_current_timezone()
        for start_time, hours in qs:
            if not start_time or not hours:
                continue
            wake = start_time + timedelta(hours=float(hours))
            # 外部表理论上都带时区；万一读出 naive（历史导入数据），按本地时区补上，
            # 不能让 `astimezone` 去猜系统时区 —— 那会得到差 8 小时的「合法结果」。
            if timezone.is_naive(wake):
                wake = timezone.make_aware(wake, tz)
            if wake.astimezone(tz).date() != target_date:
                continue
            total += float(hours)
            count += 1
        return (round(total, 2) if count else None), count

    # 午睡：按开始时刻归属（不跨日，用当日半开区间就够）
    day_start, day_end = _local_day_bounds(target_date)
    agg = TemporalTask.objects.filter(
        task_name__in=names,
        start_time__gte=day_start,
        start_time__lt=day_end,
    ).aggregate(total=Sum('duration_hours'), n=Count('id'))
    count = int(agg['n'] or 0)
    if not count:
        return None, 0
    return round(float(agg['total'] or 0), 2), count


def _line_configured(spec: dict, names: list[str]) -> bool:
    """这条线「有没有落地的依据」—— 决定空值那天说「没记录」还是说「还没配」。

    · 角色线：有没有任务名标了这个角色；
    · 归因线（流失）：有没有任务名的**默认归因**是它。
      ⚠️ 没有把赎回期覆盖规则算进来：它只影响个别任务的临时口径，
         若靠规则才凑出走失、且当天又恰好没记录，这里会误说「还没有任务名归到流失」。
         代价仅是文案，不影响数值判定（有记录时根本走不到这个分支）。
    """
    if spec.get('role') is None:
        return TaskMeta.objects.filter(default_attribution=spec['attribution_value']).exists()
    return bool(names)


def compute_daily_guards(target_date: date | None = None) -> dict:
    """「今天的三条线」：每条线给实测值 / 阈值 / 状态（睡眠 / 午睡 / 流失）。

    🔴 三档状态，没有兜底桶：
       · `ok`         在线的内侧
       · `off`        越线（下限是「没睡够」，上限是「超了」）
       · `unrecorded` 没有任何记录 —— **绝不当成 `ok`**（`unrecorded ≠ 达标`）
    🔴 文案与阈值全由后端给，前端只按 `status` 上色。
    """
    target_date = target_date or timezone.localdate()

    roles = defaultdict(list)
    for role, name in TaskMeta.objects.exclude(daily_role='').values_list('daily_role', 'task_name'):
        roles[role].append(name)

    lines = []
    for spec in DAILY_GUARD_LINES:
        names = roles.get(spec['role'], []) if spec.get('role') else []
        configured = _line_configured(spec, names)
        value, count = _guard_value_and_count(spec, names, target_date)
        threshold = float(spec['threshold_hours'])
        at_least = spec['direction'] == 'at_least'

        if value is None:
            status = 'unrecorded'
            gap = None
        else:
            status = 'ok' if ((value >= threshold) if at_least else (value <= threshold)) else 'off'
            gap = abs(round(value - threshold, 1))

        if status == 'unrecorded':
            gap_text = ''
            # 🔴 两种「没有」要分开说：还没配（配置问题）≠ 配了但今天没记（事实）。
            #    混成一句话，用户会去翻记录找「为什么没记」，其实只是没配。
            detail_text = spec['unrecorded_text'] if configured else spec['unconfigured_text']
        elif status == 'ok':
            gap_text = ''
            detail_text = f'线 {threshold:g} 小时'
        else:
            gap_text = f'{"差" if at_least else "超"} {gap:g} 小时'
            detail_text = gap_text

        lines.append({
            'key': spec['key'],
            'label': spec['label'],
            'direction': spec['direction'],
            'configured': configured,
            'threshold_hours': threshold,
            'threshold_text': f'{"≥" if at_least else "≤"} {threshold:g} 小时',
            'value_hours': value,
            'value_text': f'{value:g} 小时' if value is not None else '—',
            'status': status,
            'status_text': DAILY_GUARD_STATUS_TEXT[
                (spec['direction'], status) if status != 'unrecorded' else ('any', 'unrecorded')
            ],
            'gap_text': gap_text,
            'detail_text': detail_text,
            'record_count': count,
        })

    return {
        'date': target_date.isoformat(),
        'lines': lines,
        # 一眼看出「三条线是否都已落地」。按**算出来的** configured 汇总，
        # 不再用 `roles.get(...)` 另算一遍 —— 否则加了归因线之后这里会少算一条。
        'configured_lines': sum(1 for line in lines if line['configured']),
    }
