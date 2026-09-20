"""工作日志 Excel → 「牛马工作」时间记录的解析层（v3.58.7）

为什么零第三方依赖
------------------
项目 venv 没有 openpyxl，而 xlsx 本质只是 zip + XML。为一个导入功能给项目环境引入新依赖
（还得改 requirements.txt）不划算，所以用标准库 zipfile + ElementTree 直解。实测（2026-09-18，
955 条真实日志）完全够用：共享字符串、内联字符串、日期序列号全覆盖。

为什么只读、无 DB 依赖
----------------------
所有派生规则都是纯函数：单测不需要数据库，也避免「解析口径」和「写入口径」互相污染。

⚠️ 必须按「列位置」而不是「表头名」解析（实测坑，勿凭直觉改）
-------------------------------------------------------------
1. **sheet 名 ≠ 年份**：「每日记录2024」实际从 2023-12-25 开始，每个 sheet 都跨年。
2. **表头多处损坏**：2024 的 A1/B1 是空格串，2025/2026 的 A1 是字母 `y`。
3. **2026 表第 41 行是嵌在数据区中间的「第二套表头」**（月份/日期/工作内容/工作状态/备注/文本）
   → 靠「B 列是不是日期」识别并跳过，不要写死行号。
4. **备注列位置三套**：2023 在 G（F 是「评分」）／2024·2025 在 F／2026 在 E（且 2026 没有
   「加班|请假时长」列，备注就是那一列）。
5. **B 列是日期序列号**：2023 带时间分量（44929.375 = 2023-01-03 09:00），2024 起是纯日期。

两条「已有记录 / 无时段」的补充规则（用户 2026-09-18 二次拍板）
------------------------------------------------------------
- **规则 A（单段碎片回补开始）**：某天只有**一段**「牛马工作」记录、且当天日志状态是**工作日**类
  （正常上班 / 正常工作 / 加班 / 实习期单休 / 补班，即 `not is_restday(status)`）时，
  把这条记录的**开始时刻回补到当日标准上班时刻**，**结束时刻不动**。
  典型：`18:00→22:30`（只记了加班段）→ `09:00→22:30`。
  ⚠️ **只在工作日生效**：周末/法定节假的加班按表内实况记，不往 09:00 拉（用户明确选择）。
  ⚠️ 这一条**在命令层**实现（要读改 DB），不在解析层。
- **规则 B（非工作日族无时段兜底）**：周末 / 法定节假 / 调休的加班，如果日志**没给任何时段信息**，
  按「标准上班 → 标准下班」登记，**不再进「待人工确认」**。实测触发 2 条。
"""
from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from xml.etree import ElementTree as ET

# ─── 工时两段（用户 2026-09-18 给定）──────────────────────────────────────────
MORNING_OLD = time(9, 0)
EVENING_OLD = time(18, 0)
MORNING_NEW = time(8, 0)
EVENING_NEW = time(17, 45)
# 2026-03-02 起切入新工时；中间 2026-02-26 ~ 03-01 是离职空档（日志里也没有记录）
WORKTIME_SWITCH = date(2026, 3, 2)

# ─── 工作状态分类 ────────────────────────────────────────────────────────────
# 用户 2026-09-18 拍板：正常上班/正常工作、加班类（含周末/法定节假/调休）、实习期单休、
# 补班、迟到 → 补成牛马工作记录；年休假/有薪事假/病假/法定节日/放假/请假/三停一休 → 不补。
STATUS_INCLUDE = ('正常上班', '正常工作', '实习期单休', '补班')
STATUS_EXCLUDE = ('年休假', '有薪事假', '病假', '法定节日', '放假', '请假', '三停一休')
# 「加班」优先判定（`加班（法定节假）` 含「加班」→ 要补；光「法定节日」= 放假 → 不补）
OVERTIME_KEYWORD = '加班'
# 非工作日标记：这些天没有「标准下班」可延，起止直接取表内
OFFDAY_MARKERS = ('周末', '法定节假')
# 「非工作日族」= 周末 / 法定节假 / 调休。规则 B（2026-09-18 用户拍板）：
# 这一族的加班如果日志里**没给任何时段信息**（时长列与备注都提不出起止、也没有时长），
# 就按「标准上班 → 标准下班」登记，不再卡在「待人工确认」上。
# 实测触发 2 条：2023-11-18 `加班【周末】`、2023-11-24 `加班调休`（备注都是抒情，没有时刻）。
STD_FALLBACK_MARKERS = OFFDAY_MARKERS + ('调休',)
# 备注里明确写了「提前下班」的日子：结束时刻是**真实的提前下班**，不是记漏，
# 「补满标准工时窗口」必须放过它（用户 2026-09-18 拍板，样板 = 2025-01-25
# 「温馨提示：今天手上如果没有紧急工作的小伙伴们，下午4点可以提前下班了」，
#  实际记到 16:32，补成 18:00 等于篡改真实记录）。
EARLY_LEAVE_MARKERS = ('提前下班', '提早下班', '提前走了', '提前走')

_XLSX_NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
_REL_NS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
_SHEET_NAME_MARKER = '每日记录'   # 只认这一族的 sheet（跳过残留的空白 Sheet1）

# HH:MM 或 HH:MM:SS（中文冒号也认）
_TIME_RE = re.compile(r'(\d{1,2})\s*[:：]\s*(\d{1,2})(?:\s*[:：]\s*(\d{1,2}))?')
# 自然语言「加班到 X 点[多][Y分]」/「加班到 X:Y」
_DAO_DIAN_RE = re.compile(r'加班到\s*(\d{1,2})\s*点\s*(多)?\s*(?:(\d{1,2})\s*分)?')
_DAO_CLOCK_RE = re.compile(r'加班到\s*(\d{1,2})\s*[:：]\s*(\d{2})')
# 纯数字时长：2.5h / 2h / 3 / 3.5
_BARE_HOURS_RE = re.compile(r'^\s*(\d+(?:\.\d+)?)\s*[hH]?\s*$')
# 带单位时长：1小时 / 2.5 小时 / 3h
_UNIT_HOURS_RE = re.compile(r'(\d+(?:\.\d+)?)\s*(?:小时|个?钟头|[hH]\b)')
_NEGATIVE_RE = re.compile(r'没加班|没有加班|未加班')
# 提不出具体值的写法 → 交人工确认，不猜
_NEEDS_MANUAL_RE = re.compile(r'一整天|全天|1\s*天|半天')


# ════════════════════════════════════════════════════════════════════════════
# 数据结构
# ════════════════════════════════════════════════════════════════════════════
@dataclass
class WorkLogRow:
    """日志里的一行原始记录（已做过日期/文本归一，未做工时判定）"""

    sheet: str
    row_no: int
    day: date
    content: str = ''
    status: str = ''
    dur_raw: str = ''    # 「加班|请假时长」列原文（2026 表没有这列 → 空）
    note: str = ''       # 备注列原文（按 sheet 取 G / F / E）


@dataclass
class PlannedDay:
    """一天 → 一条「牛马工作」记录的判定结果（纯数据，不含 DB 动作）"""

    day: date
    status: str
    content: str
    note: str
    action: str            # 'include' | 'skip'
    skip_reason: str = ''
    start: datetime | None = None
    end: datetime | None = None
    duration_hours: float | None = None
    overtime_minutes: int = 0
    overtime_source: str = ''
    needs_review: bool = False
    review_reason: str = ''
    is_offday: bool = False
    source: str = ''       # 'sheet!row'


# ════════════════════════════════════════════════════════════════════════════
# xlsx 低层读取（标准库）
# ════════════════════════════════════════════════════════════════════════════
def _cell_col(ref: str) -> str:
    return ''.join(ch for ch in ref if ch.isalpha())


def _serial_to_datetime(raw: str) -> datetime | None:
    """Excel 日期序列号 → datetime（1900 系统；基准用 1899-12-30 已含闰年 bug 修正）"""
    try:
        n = float(raw)
    except (TypeError, ValueError):
        return None
    if not (1 <= n <= 2958465):      # 1900-01-01 ~ 9999-12-31
        return None
    return datetime(1899, 12, 30) + timedelta(days=n)


def _to_datetime(raw: str | None) -> datetime | None:
    """单元格文本 → datetime：先按序列号，再退回常见日期串"""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    dt = _serial_to_datetime(s)
    if dt is not None:
        return dt
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y/%m/%d %H:%M:%S', '%Y/%m/%d',
                '%Y年%m月%d日'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


class _Workbook:
    """把用得到的那几部分 XML 读进来：共享字符串 + sheet 名 → 文件路径"""

    def __init__(self, path: str):
        self.zip = zipfile.ZipFile(path)
        self.shared = self._load_shared()
        self.sheets = self._load_sheet_map()

    def _load_shared(self) -> list[str]:
        try:
            root = ET.fromstring(self.zip.read('xl/sharedStrings.xml'))
        except KeyError:
            return []
        return [''.join(t.text or '' for t in si.iter(_XLSX_NS + 't'))
                for si in root.iter(_XLSX_NS + 'si')]

    def _load_sheet_map(self) -> list[tuple[str, str]]:
        rels = {}
        for r in ET.fromstring(self.zip.read('xl/_rels/workbook.xml.rels')):
            rels[r.get('Id')] = r.get('Target')
        wb = ET.fromstring(self.zip.read('xl/workbook.xml'))
        out = []
        for s in wb.iter(_XLSX_NS + 'sheet'):
            target = rels.get(s.get(_REL_NS + 'id'), '')
            if not target:
                continue
            if target.startswith('/'):
                target = target[1:]
            elif not target.startswith('xl/'):
                target = 'xl/' + target
            out.append((s.get('name') or '', target))
        return out

    def rows(self, sheet_path: str):
        """逐行产出 {列字母: 文本}，跳过没有 <v>/<is> 的空单元格"""
        root = ET.fromstring(self.zip.read(sheet_path))
        for row in root.iter(_XLSX_NS + 'row'):
            try:
                row_no = int(row.get('r'))
            except (TypeError, ValueError):
                continue
            cells: dict[str, str] = {}
            for c in row.iter(_XLSX_NS + 'c'):
                ref = c.get('r') or ''
                ctype = c.get('t')
                vnode = c.find(_XLSX_NS + 'v')
                inode = c.find(_XLSX_NS + 'is')
                if ctype == 's' and vnode is not None:
                    try:
                        val = self.shared[int(vnode.text)]
                    except (ValueError, IndexError):
                        val = ''
                elif ctype == 'inlineStr' and inode is not None:
                    val = ''.join(t.text or '' for t in inode.iter(_XLSX_NS + 't'))
                elif vnode is not None:
                    val = vnode.text or ''
                else:
                    continue
                cells[_cell_col(ref)] = val
            yield row_no, cells


# ════════════════════════════════════════════════════════════════════════════
# 读表
# ════════════════════════════════════════════════════════════════════════════
def _layout_for(sheet_name: str) -> tuple[str, str | None]:
    """→ (备注列, 「加班|请假时长」列)。坑 4：三套列布局，按 sheet 名分流。"""
    if '2023' in sheet_name:
        return 'G', 'E'          # 2023 多一列「评分」F → 备注落到 G
    if '2026' in sheet_name:
        return 'E', None         # 2026 无时长列，备注就是 E
    return 'F', 'E'


def read_worklog_rows(path: str) -> list[WorkLogRow]:
    """读工作日志 Excel → 归一后的行列表（按日期升序）。只读，不改文件。"""
    wb = _Workbook(path)
    out: list[WorkLogRow] = []
    for sheet_name, sheet_path in wb.sheets:
        if _SHEET_NAME_MARKER not in sheet_name:
            continue                       # 跳过残留的空白 Sheet1
        note_col, dur_col = _layout_for(sheet_name)
        for row_no, cells in wb.rows(sheet_path):
            if row_no < 2:
                continue
            # 坑 2/3：表头损坏 + 2026 中段第二套表头 —— 一律靠「B 列是不是日期」判记录行
            dt = _to_datetime(cells.get('B'))
            if dt is None:
                continue
            status = (cells.get('D') or '').strip()
            if not status or status == '工作状态':
                continue                   # 空状态 / 表头残留
            out.append(WorkLogRow(
                sheet=sheet_name,
                row_no=row_no,
                day=dt.date(),
                content=(cells.get('C') or '').strip(),
                status=status,
                dur_raw=(cells.get(dur_col) or '').strip() if dur_col else '',
                note=(cells.get(note_col) or '').strip(),
            ))
    out.sort(key=lambda r: (r.day, r.sheet, r.row_no))
    return out


# ════════════════════════════════════════════════════════════════════════════
# 工时 / 加班判定（纯函数）
# ════════════════════════════════════════════════════════════════════════════
def work_window(day: date) -> tuple[time, time]:
    """该日适用的 (标准上班, 标准下班)"""
    if day >= WORKTIME_SWITCH:
        return MORNING_NEW, EVENING_NEW
    return MORNING_OLD, EVENING_OLD


def classify_status(status: str) -> tuple[str, str]:
    """→ ('include'|'skip', 原因)。加班优先于排除词（`加班（法定节假）` 要补）。"""
    s = (status or '').strip()
    if not s:
        return 'skip', '状态为空'
    if OVERTIME_KEYWORD in s:
        return 'include', '加班'
    for kw in STATUS_INCLUDE:
        if kw in s:
            return 'include', kw
    for kw in STATUS_EXCLUDE:
        if kw in s:
            return 'skip', kw
    return 'skip', f'未登记状态「{s}」'


def is_overtime(status: str) -> bool:
    """是不是加班类（含【周末】【法定节假】调休）。**只有这类才需要解加班时长**——
    正常上班的日子就是「标准上班 → 标准下班」，不该进加班解析，
    否则会被无意义地标成「解析不出加班时刻」而污染待确认清单。"""
    return OVERTIME_KEYWORD in (status or '')


def is_offday(status: str) -> bool:
    """周末 / 法定节假日的加班：没有「标准下班」可延，起止直接取表内"""
    s = status or ''
    return any(m in s for m in OFFDAY_MARKERS)


def is_restday(status: str) -> bool:
    """非工作日族（周末 / 法定节假 / 调休）。

    用途有两处，都只认这一族：
    - 规则 B：这一族**没给时段**时按标准窗口登记（见 `plan_day`）；
    - 规则 A 的排除项：「单段碎片回补标准窗口」**只对工作日生效**——
      周末加班本来就该按表内实况记（用户 2026-09-18 拍板），不往 09:00 拉。
    """
    s = status or ''
    return any(m in s for m in STD_FALLBACK_MARKERS)


def is_early_leave(note: str) -> bool:
    """备注是否明确说明当天提前下班。

    → 当天的结束时刻是**实况**而非记漏，不参与「补满标准窗口」
    （2025-01-25 就是这种：备注发了提前下班通知，实际记到 16:32）。
    """
    s = note or ''
    return any(m in s for m in EARLY_LEAVE_MARKERS)


def _find_times(text: str) -> list[time]:
    """抠出文本里所有 HH:MM[:SS] 时刻（按出现顺序）"""
    out = []
    for m in _TIME_RE.finditer(text or ''):
        h, mi = int(m.group(1)), int(m.group(2))
        sec = int(m.group(3) or 0)
        if 0 <= h <= 23 and 0 <= mi <= 59 and 0 <= sec <= 59:
            out.append(time(h, mi, sec))
    return out


def _extract_hours(text: str) -> float | None:
    """从文本里抠「时长（小时）」：2.5h / 3 / 1小时 / 半小时"""
    s = (text or '').strip()
    if not s:
        return None
    m = _BARE_HOURS_RE.match(s)
    if m:
        return float(m.group(1))
    if '半小时' in s:
        return 0.5
    m = _UNIT_HOURS_RE.search(s)
    if m:
        return float(m.group(1))
    return None


def _to_evening_clock(hour: int, minute: int) -> time:
    """「加班到 7 点」这类 12 小时制写法 → 24 小时制。

    加班的「到点」一律理解为傍晚之后：1~11 点补 +12（7点→19点，10点→22点）。
    12 点原样保留（可能是笔误，调用方会标 needs_review）。
    """
    h = hour + 12 if 1 <= hour <= 11 else hour
    return time(h % 24, minute)


def resolve_overtime_end(e_raw: str, content: str, note: str,
                         standard_end: time) -> tuple[time | None, int, str, bool, str]:
    """解出「加班结束时刻」。

    → (end_clock, 加班分钟数, 来源, 是否需人工确认, 原因)

    口径（2026-09-18 用户拍板「表内优先」，并按实测细化）：
      1. **优先取表内「止」**——实测 2023 的 `【加班：17:30~20:00】` 配 `E=2.5h`，
         2.5h 是**加班块的时长**、`20:00` 才是**真实下班时刻**；2025 的 E 列写的直接就是
         全天起止（`9:00~22:10`）。所以「止」比「时长」更接近事实。
      2. 取不到「止」→ 退回「标准下班 + 时长」（2024 只有 `3`/`3.5` 这种裸数字）。
      3. 都没有 → 记 0 加班并标 needs_review（`一整天`/空白/`7点` 这种提不出具体值的）。
    """
    # ① 表内起止：E 列（2023/2024/2025）→ 再退到 C 列方括号
    candidates: list[tuple[str, str]] = []
    if e_raw:
        candidates.append((e_raw, '时长列起止'))
    if content:
        for seg in re.findall(r'【([^】]*)】', content):
            if '加班' in seg:
                candidates.append((seg, '工作内容方括号'))
    for text, src in candidates:
        times = _find_times(text)
        if len(times) >= 2:
            end_clock = times[-1]
            return end_clock, _minutes_between(standard_end, end_clock), src, False, ''

    # ② 自然语言「加班到 X 点」
    for text, src in ((note, '备注'), (e_raw, '时长列')):
        if not text:
            continue
        m = _DAO_CLOCK_RE.search(text)
        if m:
            clock = time(int(m.group(1)), int(m.group(2)))
            return clock, _minutes_between(standard_end, clock), f'{src}「加班到」', False, ''
        m = _DAO_DIAN_RE.search(text)
        if m:
            clock = _to_evening_clock(int(m.group(1)), int(m.group(3) or 0))
            approx = bool(m.group(2))          # 「8点多」→ 取 8 点，标待确认
            return (clock, _minutes_between(standard_end, clock),
                    f'{src}「加班到…点」', approx, '备注写「X点多」，只能取整点' if approx else '')

    # ③ 只有时长：标准下班 + 时长
    for text, src in ((e_raw, '时长列'), (note, '备注')):
        hours = _extract_hours(text)
        if hours is not None:
            return (None, int(round(hours * 60)), f'{src}时长 {hours:g}h', False, '')

    # ④ 明确否定
    if _NEGATIVE_RE.search(f'{note or ""}{e_raw or ""}'):
        return None, 0, '备注明确「没加班」', False, ''

    # ⑤ 提不出：不猜，交人工确认
    reason = '备注/时长里没有可解析的加班结束时刻或时长'
    if _NEEDS_MANUAL_RE.search(f'{note or ""}{e_raw or ""}'):
        reason = '「一整天/全天/半天」这类写法没有具体结束时刻'
    elif not (note or e_raw):
        reason = '状态是加班，但时长与备注都为空'
    return None, 0, '', True, reason


def _minutes_between(start: time, end: time) -> int:
    """从 start 到 end 的分钟数，可为负（= 提前下班）。

    跨零点只在「end 明显早于 start」时认定：差值超过 12 小时才 +24h。
    否则 `18:00 → 17:30` 会被误算成「加班到次日 17:30」（+23.5h）——这是真踩过的坑。
    """
    a = start.hour * 60 + start.minute + start.second / 60
    b = end.hour * 60 + end.minute + end.second / 60
    diff = b - a
    if diff < -12 * 60:
        diff += 24 * 60
    return int(round(diff))


def _brackets(text: str) -> str:
    """把正文里的【…】片段拼起来（2023 的加班起止写在 `【加班：17:30~20:00】` 里）"""
    return ' '.join(re.findall(r'【([^】]*)】', text or ''))


# ════════════════════════════════════════════════════════════════════════════
# 一天 → 一条记录
# ════════════════════════════════════════════════════════════════════════════
def plan_day(row: WorkLogRow) -> PlannedDay:
    """把一行日志判定成「要不要建记录 / 建哪一段」"""
    src = f'{row.sheet}!{row.row_no}'
    action, reason = classify_status(row.status)
    pd = PlannedDay(day=row.day, status=row.status, content=row.content, note=row.note,
                    action=action, skip_reason='' if action == 'include' else reason,
                    source=src)
    if action == 'skip':
        return pd

    std_start, std_end = work_window(row.day)
    offday = is_offday(row.status)
    overtime = is_overtime(row.status)
    pd.is_offday = offday
    review = False
    review_reason = ''

    if not overtime:
        # 非加班日：标准工时一条，不碰加班解析
        pd.start = datetime.combine(row.day, std_start)
        pd.end = datetime.combine(row.day, std_end)
        pd.duration_hours = round(float(_minutes_between(std_start, std_end)) / 60, 2)
        pd.overtime_source = '标准工时'
        # 状态不是加班、备注却写了加班（实测 1 条：实习期单休 +「补班，加班到10点50分」）
        # → 严格按用户规则「只有状态=加班才延长」，但标出来交人工，不擅自改时长。
        blob = f'{row.note}{row.dur_raw}'
        if '加班' in blob and not _NEGATIVE_RE.search(blob):
            pd.needs_review = True
            pd.review_reason = f'状态是「{row.status}」但备注提到加班，未按加班延长'
        return pd

    if offday:
        # 非工作日（周末/法定节假）：当天根本没有「标准工时」，所以起止直接取表内实况
        times = _find_times(row.dur_raw) or _find_times(_brackets(row.content))
        if len(times) >= 2:
            start_dt = datetime.combine(row.day, times[0])
            end_dt = datetime.combine(row.day, times[-1])
            if end_dt <= start_dt:
                end_dt += timedelta(days=1)
            pd.overtime_source = '表内起止（非工作日，全天口径）'
        else:
            # 只有时长（如 2023「法定节日」的 E=`8h`）→ 上班时刻 + 时长
            hours = _extract_hours(row.dur_raw) or _extract_hours(row.note)
            if hours:
                start_dt = datetime.combine(row.day, std_start)
                end_dt = start_dt + timedelta(hours=hours)
                pd.overtime_source = f'非工作日，上班时刻+时长 {hours:g}h'
            else:
                # 规则 B：非工作日加班但日志没给时段 → 按标准窗口登记（用户 2026-09-18 拍板）
                start_dt = datetime.combine(row.day, std_start)
                end_dt = datetime.combine(row.day, std_end)
                pd.overtime_source = '非工作日无时段，按标准工时登记'
    else:
        start_dt = datetime.combine(row.day, std_start)
        end_clock, ot_minutes, ot_source, review, review_reason = resolve_overtime_end(
            row.dur_raw, row.content, row.note, std_end)
        pd.overtime_source = ot_source
        if end_clock is not None:
            # 表内给了「加班到几点」→ 直接用它当收工时刻
            end_dt = datetime.combine(row.day, end_clock)
            if end_dt <= start_dt:
                end_dt += timedelta(days=1)
                review = True
                review_reason = review_reason or '加班结束时刻落在次日凌晨，已按跨零点处理'
            elif ot_minutes < 0:
                review = True
                review_reason = review_reason or (
                    f'表内结束时刻（{end_clock.strftime("%H:%M")}）早于标准下班'
                    f'（{std_end.strftime("%H:%M")}），当天可能提前走了')
        elif ot_minutes:
            # 只有时长（2024 的裸数字 3 / 3.5）→ 标准下班往后推
            end_dt = datetime.combine(row.day, std_end) + timedelta(minutes=ot_minutes)
            if end_dt.date() != row.day:
                review = True
                review_reason = review_reason or '加班跨零点，结束时间落在次日'
        else:
            end_dt = datetime.combine(row.day, std_end)
            if is_restday(row.status):
                # 规则 B（「调休」这一支）：非工作日族、日志没给时段 → 按标准窗口登记，不卡待确认。
                # ⚠️ 必须显式清掉 resolve_overtime_end 返回的 review=True，否则仍会被判成待确认。
                review = False
                review_reason = ''
                pd.overtime_source = '调休日无时段，按标准工时登记'
            # 「没加班，因为…」是明确回答，不算解析失败、不进待确认
            elif not pd.overtime_source.startswith('备注明确'):
                review = True
                review_reason = review_reason or '加班结束时刻未能解析，暂按标准下班收口'

    if end_dt <= start_dt:
        review = True
        review_reason = review_reason or '结束不晚于开始，已按跨零点 +1 天处理'
        end_dt += timedelta(days=1)

    pd.start = start_dt
    pd.end = end_dt
    pd.duration_hours = round((end_dt - start_dt).total_seconds() / 3600, 2)
    pd.needs_review = review
    pd.review_reason = review_reason
    return pd


def build_plan(rows: list[WorkLogRow]) -> list[PlannedDay]:
    """全部日志行 → 判定结果；同一天出现多行时只保留第一条（保留顺序：表内先后）"""
    seen: set[date] = set()
    out: list[PlannedDay] = []
    for row in rows:
        if row.day in seen:
            continue
        seen.add(row.day)
        out.append(plan_day(row))
    return out
