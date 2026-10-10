"""月度加班台账 → 逐日工作时间记录（反推生成器）

**纯函数层**：给定同样的台账与常量，永远产出同样的安排 —— 不含任何随机、
不读时钟、不碰数据库。落库在 `management/commands/reconstruct_worktime.py`。

产物性质（务必向使用者说清）
---------------------------
- **月度加班总量是真实的**（用户手工台账）；
- **上下班时间、请假记录是真实的**（用户给定）；
- **哪一天加班、加多久是推定的** —— 原始数据里没有这个信息，是按规则摊出来的。

所以每次落库都带批次号，事后可整批筛出、整批回滚。

规则口径（用户 2026-09-29 拍板）
-------------------------------
- 正常上班 `09:00–18:00`（9.0h，不扣午休，与系统内 2023+ 记录一致）；
- 工作日加班 `2.5–3h/天`；周末加班 `10:00` 起、单日上限 9h；
- 半天假记下午 `13:30–18:00`；计时假从下班时刻往前扣；
- **法定节假日不排班、调休补班日按工作日算**（国务院办公厅通知原文）；
- **请假日一律移出加班候选集**，该月加班重新摊到其余工作日
  （做法是「并入生成阶段」，不是「算完再挪走」—— 后者会破坏总量守恒）；
- 时段粒度 **5 分钟**（直接按分钟分摊会产出 20:25/20:24 交替的碎值）。

三情形（设某月台账加班 H 分钟、加班候选日 C 天）
------------------------------------------------
1. `H > C×3h`        → **溢出**：候选日按「一半 3h / 一半 2.5h **交错**」铺满，余量去周末
2. `C×2h ≤ H ≤ C×3h` → 全部候选日加班，每天 `H/C`
3. `H < C×2h`        → `n = round(H/2.5)` 天（至少 1 天）**等间隔散布**，每天 `H/n`

⚠️ 情形 1 的**判定阈值不跟着铺法下调**。曾有一个月（2022-05，53h÷19 天 = 2.79h/天）
仅超 2.75h 共 0.75h，若把阈值降到 `C×2.75h` 会把它卷进溢出分支、产出 **0.5h 的周末加班**
（0.75h 摊到 19 天 = 每天 2.4 分钟，**落不成 5 分钟粒度**）。
判据：**余量小到无法在粒度内均摊时，宁可让它留在情形 2 被平滑吸收，也不强行分组。**

节假日数据源（2026-09-29 核对官方原文）
--------------------------------------
2020 年 国办发明电〔2019〕16号 ｜ 2021 年 国办发明电〔2020〕**27**号
（网上大量资料误写成 18 号）｜ 2022 年 国办发明电〔2021〕11号
"""
from __future__ import annotations

import calendar
import re
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

# ── 常量 ───────────────────────────────────────────────────────────────────
RANGE_START = date(2020, 4, 1)
RANGE_END = date(2022, 12, 31)
WORK_START = (9, 0)             # 上班 09:00
WORK_END = (18, 0)              # 正常下班 18:00
WD_OT_CAP_MIN = 180             # 工作日加班上限 3h（兼作溢出判定与高档）
WD_OT_LOW_MIN = 150             # 工作日加班低档 2.5h（溢出月一半天用）
WE_START = (10, 0)              # 周末加班 10:00 起
WE_CAP_MIN = 540                # 周末单日上限 9h
AFTERNOON_START = (13, 30)      # 半天假：下午上班
GRAN = 5                        # 时段粒度（分钟）
BATCH_DEFAULT = 'overtime_recon_2020_2022'
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'

# ── 法定节假日（放假日，不排班）────────────────────────────────────────────
HOLIDAYS_STR = """
2020-04-04 2020-04-05 2020-04-06
2020-05-01 2020-05-02 2020-05-03 2020-05-04 2020-05-05
2020-06-25 2020-06-26 2020-06-27
2020-10-01 2020-10-02 2020-10-03 2020-10-04 2020-10-05 2020-10-06 2020-10-07 2020-10-08
2021-01-01 2021-01-02 2021-01-03
2021-02-11 2021-02-12 2021-02-13 2021-02-14 2021-02-15 2021-02-16 2021-02-17
2021-04-03 2021-04-04 2021-04-05
2021-05-01 2021-05-02 2021-05-03 2021-05-04 2021-05-05
2021-06-12 2021-06-13 2021-06-14
2021-09-19 2021-09-20 2021-09-21
2021-10-01 2021-10-02 2021-10-03 2021-10-04 2021-10-05 2021-10-06 2021-10-07
2022-01-01 2022-01-02 2022-01-03
2022-01-31 2022-02-01 2022-02-02 2022-02-03 2022-02-04 2022-02-05 2022-02-06
2022-04-03 2022-04-04 2022-04-05
2022-04-30 2022-05-01 2022-05-02 2022-05-03 2022-05-04
2022-06-03 2022-06-04 2022-06-05
2022-09-10 2022-09-11 2022-09-12
2022-10-01 2022-10-02 2022-10-03 2022-10-04 2022-10-05 2022-10-06 2022-10-07
"""
HOLIDAYS = {date.fromisoformat(s) for s in HOLIDAYS_STR.split()}

# ── 调休补班日（周末上班，按工作日算）──────────────────────────────────────
MAKEUP_STR = """
2020-04-26 2020-05-09 2020-06-28 2020-09-27 2020-10-10
2021-02-07 2021-02-20 2021-04-25 2021-05-08 2021-09-18 2021-09-26 2021-10-09
2022-01-29 2022-01-30 2022-04-02 2022-04-24 2022-05-07 2022-10-08 2022-10-09
"""
MAKEUP = {date.fromisoformat(s) for s in MAKEUP_STR.split()}

# ── 请假台账（用户 2026-09-29 提供）────────────────────────────────────────
# 全天假 → 不出记录；半天假 → 下午上班 13:30–18:00；计时假 → 09:00 起，下班往前扣
FULL_LEAVE = {
    date(2022, 1, 28): '提前回家过年',
    date(2022, 9, 9): '中秋',
}
HALF_LEAVE = {
    date(2022, 3, 11): '急性呼吸道感染·省立同德医院看病',
    date(2022, 5, 16): '例假',
    date(2022, 6, 10): '上班路上打滑',
    date(2022, 7, 7): '例假',
    date(2022, 7, 21): '早退',
    date(2022, 9, 13): '中秋',
}
HOURS_LEAVE = {
    date(2022, 9, 22): (150, '例假·调休'),      # 请假 2.5h = 150 分钟
}
ALL_LEAVE = set(FULL_LEAVE) | set(HALF_LEAVE) | set(HOURS_LEAVE)

KIND_LABEL = {
    'work': '正常上班',
    'work_ot': '工作日加班',
    'weekend_ot': '周末加班',
    'half_leave': '半天假',
    'hours_leave': '计时假',
}


# ── 数据结构 ───────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Entry:
    """一条待写入的时间记录（当天一段）"""

    day: date
    kind: str                   # KIND_LABEL 的键
    ot: int                     # 加班分钟数（正常上班 / 请假为 0）

    def times(self) -> tuple[datetime, datetime]:
        """当日 naive 起止时刻（由调用方 make_aware）"""
        base = datetime(self.day.year, self.day.month, self.day.day)
        end_1800 = base.replace(hour=WORK_END[0], minute=WORK_END[1])
        if self.kind == 'weekend_ot':
            st = base.replace(hour=WE_START[0], minute=WE_START[1])
            return st, st + timedelta(minutes=self.ot)
        if self.kind == 'half_leave':
            return base.replace(hour=AFTERNOON_START[0], minute=AFTERNOON_START[1]), end_1800
        if self.kind == 'hours_leave':
            return base.replace(hour=WORK_START[0], minute=WORK_START[1]), \
                end_1800 - timedelta(minutes=HOURS_LEAVE[self.day][0])
        st = base.replace(hour=WORK_START[0], minute=WORK_START[1])
        return st, end_1800 + timedelta(minutes=self.ot)

    @property
    def hours(self) -> float:
        st, en = self.times()
        return round((en - st).total_seconds() / 3600, 2)

    def description(self) -> str:
        d = self.day.isoformat()
        if self.kind == 'weekend_ot':
            return f'[{d}] 周末加班 +{_fmt_h(self.ot)}h（月度台账反推）'
        if self.kind == 'work_ot':
            return f'[{d}] 加班 +{_fmt_h(self.ot)}h（月度台账反推）'
        if self.kind == 'half_leave':
            return f'[{d}] 半天假·下午上班（月度台账反推）'
        if self.kind == 'hours_leave':
            return f'[{d}] 请假 {_fmt_h(HOURS_LEAVE[self.day][0])}h（月度台账反推）'
        return f'[{d}] 正常上班（月度台账反推）'


@dataclass(frozen=True)
class MonthStat:
    """某月的生成统计（用于逐月核对）"""

    year: int
    month: int
    target_hours: float
    workdays: int
    candidates: int
    ot_days: int
    weekend_ot_days: int
    weekday_avg: float
    generated_hours: float
    branch: str                 # overfull / all_cand / partial

    @property
    def ok(self) -> bool:
        return abs(self.generated_hours - self.target_hours) < 1e-6


def _fmt_h(minutes: int) -> str:
    return f'{minutes / 60:.2f}'.rstrip('0').rstrip('.')


# ── 读台账 ─────────────────────────────────────────────────────────────────
def read_monthly(path: str | Path) -> list[tuple[date, float]]:
    """从 Sheet1 读「YYYY-M → 加班小时」台账（直接解析 xml，不依赖 openpyxl）"""
    with zipfile.ZipFile(path) as z:
        ss: list[str] = []
        if 'xl/sharedStrings.xml' in z.namelist():
            root = ET.fromstring(z.read('xl/sharedStrings.xml'))
            for si in root.findall(f'{NS}si'):
                ss.append(''.join(t.text or '' for t in si.iter(f'{NS}t')))
        root = ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
        out: list[tuple[date, float]] = []
        for row in root.iter(f'{NS}row'):
            cells: dict[str, str] = {}
            for c in row.findall(f'{NS}c'):
                col = re.match(r'[A-Z]+', c.get('r')).group()
                t, v = c.get('t'), c.find(f'{NS}v')
                isn = c.find(f'{NS}is')
                # 三种单元格写法都要认：inlineStr / sharedStrings 索引 / 直接值
                # （真实 xlsx 走 sharedStrings，测试里手写的走 inlineStr）
                if t == 'inlineStr' and isn is not None:
                    cells[col] = ''.join(x.text or '' for x in isn.iter(f'{NS}t'))
                elif t == 's' and v is not None and v.text is not None:
                    cells[col] = ss[int(v.text)]
                elif v is not None and v.text is not None:
                    cells[col] = v.text
            a, b = cells.get('A'), cells.get('B')
            if a and b and re.match(r'^\d{4}-\d{1,2}$', a.strip()):
                y, m = a.strip().split('-')
                out.append((date(int(y), int(m), 1), float(b)))
    return out


# ── 工作日 / 休息日 ────────────────────────────────────────────────────────
def month_days(y: int, m: int) -> list[date]:
    return [date(y, m, d) for d in range(1, calendar.monthrange(y, m)[1] + 1)]


def workdays_of(y: int, m: int) -> list[date]:
    """周一~周五且非法定节假日，**加调休补班日**，**再剔除全天请假日**"""
    out = []
    for d in month_days(y, m):
        if d in HOLIDAYS or d in FULL_LEAVE:
            continue
        if d.weekday() < 5 or d in MAKEUP:
            out.append(d)
    return out


def restdays_of(y: int, m: int) -> list[date]:
    """当月休息日（周末，排除补班日与法定节假日）"""
    return [d for d in month_days(y, m)
            if d.weekday() >= 5 and d not in MAKEUP and d not in HOLIDAYS]


def candidates_of(y: int, m: int) -> list[date]:
    """加班候选日 = 工作日 − 一切请假日"""
    return [d for d in workdays_of(y, m) if d not in ALL_LEAVE]


# ── 分摊工具 ───────────────────────────────────────────────────────────────
def spread(n_total: int, n_pick: int) -> list[int]:
    """在 n_total 个位置里等间隔挑出 n_pick 个下标（不集中在头尾）"""
    if n_pick <= 0:
        return []
    if n_pick >= n_total:
        return list(range(n_total))
    return [int((2 * i + 1) * n_total / (2 * n_pick)) for i in range(n_pick)]


def split_minutes(total: int, n: int) -> list[int]:
    """切成 n 份，总和精确、每份都是 GRAN 的倍数（最大余数法）"""
    assert n > 0, '份数必须为正'
    assert total % GRAN == 0, f'{total} 分钟不是 {GRAN} 的倍数'
    units = total // GRAN
    per, rem = divmod(units, n)
    return [(per + (1 if i < rem else 0)) * GRAN for i in range(n)]


# ── 核心：单月计划 ─────────────────────────────────────────────────────────
def plan_month(y: int, m: int, hours: float) -> tuple[list[Entry], MonthStat]:
    """把某月的台账加班小时摊到具体日子上"""
    wd, rd = workdays_of(y, m), restdays_of(y, m)
    cand = [d for d in wd if d not in ALL_LEAVE]
    target = round(hours * 60)
    assert cand, f'{y}-{m} 无加班候选日'
    entries: list[Entry] = []

    if target > len(cand) * WD_OT_CAP_MIN:
        # 情形 1 溢出：候选日按「一半 3h / 一半 2.5h 交错」铺满，余量去周末。
        # 交错（i 偶→3h、i 奇→2.5h）而非前半 3h 后半 2.5h，避免月中出现台阶。
        mins_list = [WD_OT_CAP_MIN if i % 2 == 0 else WD_OT_LOW_MIN
                     for i in range(len(cand))]
        assert sum(1 for v in mins_list if v == WD_OT_CAP_MIN) == (len(cand) + 1) // 2
        work_total = sum(mins_list)
        assert work_total < target, f'{y}-{m} 溢出月工作日量应小于目标'
        entries += [Entry(d, 'work_ot', v) for d, v in zip(cand, mins_list)]
        rest = target - work_total
        nw = -(-rest // WE_CAP_MIN)
        assert nw <= len(rd), f'{y}-{m} 周末日不足：需 {nw} 天，仅 {len(rd)} 天'
        for idx, mins in zip(spread(len(rd), nw), split_minutes(rest, nw)):
            entries.append(Entry(rd[idx], 'weekend_ot', mins))
        branch = 'overfull'
    elif target >= len(cand) * 120:
        # 情形 2 全部候选日加班，每天 target/候选数 ∈ [2h, 3h]
        entries += [Entry(d, 'work_ot', v)
                    for d, v in zip(cand, split_minutes(target, len(cand)))]
        branch = 'all_cand'
    else:
        # 情形 3 部分候选日加班：天数由 2.5h/天 反推，等间隔散布
        n = max(1, min(len(cand), round(hours / 2.5)))
        for idx, mins in zip(spread(len(cand), n), split_minutes(target, n)):
            entries.append(Entry(cand[idx], 'work_ot', mins))
        branch = 'partial'

    # 余下的工作日：加班日已有条目，全天假不出记录，其余按「正常 / 半天假 / 计时假」补
    ot_days = {e.day for e in entries}
    for d in wd:
        if d in ot_days or d in FULL_LEAVE:
            continue
        if d in HALF_LEAVE:
            entries.append(Entry(d, 'half_leave', 0))
        elif d in HOURS_LEAVE:
            entries.append(Entry(d, 'hours_leave', 0))
        else:
            entries.append(Entry(d, 'work', 0))

    entries.sort(key=lambda e: (e.day, e.kind != 'work'))   # 同日只可能有一条
    assert sum(e.ot for e in entries) == target, f'{y}-{m} 加班量不符'

    ot_days_n = sum(1 for e in entries if e.kind == 'work_ot')
    we_days_n = sum(1 for e in entries if e.kind == 'weekend_ot')
    stat = MonthStat(
        year=y, month=m, target_hours=hours,
        workdays=len(wd), candidates=len(cand),
        ot_days=ot_days_n, weekend_ot_days=we_days_n,
        weekday_avg=(work_total / ot_days_n / 60) if branch == 'overfull'
        else (sum(e.ot for e in entries if e.kind == 'work_ot') / 60 / ot_days_n
              if ot_days_n else 0.0),
        generated_hours=sum(e.ot for e in entries) / 60,
        branch=branch,
    )
    return entries, stat


# ── 全量计划 ───────────────────────────────────────────────────────────────
def build_plan(path: str | Path,
               date_from: date = RANGE_START,
               date_to: date = RANGE_END,
               ) -> tuple[list[Entry], list[MonthStat]]:
    """读台账 → 逐月摊开。返回（全部条目, 逐月统计）。

    末尾做三项硬断言（不通过就抛，绝不放行）：
      ① 每个月加班总量 == 台账；
      ② 请假日绝不出现加班；
      ③ 全天请假日绝不出记录。
    """
    monthly = [(d, h) for d, h in read_monthly(path) if date_from <= d <= date_to]
    assert monthly, '台账为空或区间不匹配'
    entries: list[Entry] = []
    stats: list[MonthStat] = []
    for d, h in monthly:
        e, s = plan_month(d.year, d.month, h)
        entries += e
        stats.append(s)
    entries.sort(key=lambda e: e.day)

    bad = [e for e in entries if e.day in ALL_LEAVE and e.ot > 0]
    assert not bad, f'请假日仍排了加班：{bad}'
    assert not [e for e in entries if e.day in FULL_LEAVE], '全天假仍出记录'
    assert all(s.ok for s in stats), \
        '存在月度核对不通过的月份：' + ', '.join(f'{s.year}-{s.month}' for s in stats if not s.ok)
    return entries, stats
