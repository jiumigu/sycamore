"""账单 CSV 导入解析器（预演与落库共用，v3.65）

为什么要有这一份
================
旧 `BillImportView` 按**列位置**取值（`row[0]` 类型 / `row[1]` 日期 / `row[7]` 金额…），
并固定跳过前 2 行（`rows[2:]`）。只要导出源换一版模板，整批列就错位 ——
而错位**不会抛异常**：它会把「日期」当「交易类型」写进库，用户看到的是
「导入 0 条」，或者一笔金额莫名其妙的账。

2028 年随手记会员到期后必须换源（或多维表导出），所以判据是：
**换源时只配列名，不改代码。**

三件事在这里定，别处不再判断
============================
1. 列别名表 `BILL_COLUMN_ALIASES` —— 唯一的真源，前端不持有任何列名常量
2. 表头定位 —— 前 5 行里找「命中别名最多、且最靠后」的一行
3. 行级校验 —— 日期 / 金额 / 收支类型，错一个就是 error 行并带 **CSV 物理行号**
   （表头算第 1 行），不做静默跳过

🔴 为什么表头取「最靠后」的那一行：导出文件前面可能有标题行、汇总行、
   甚至是重复的表头（随手记的导出就是两行表头）。最靠后的命中行 =
   最接近数据的那一行。
"""

from __future__ import annotations

import csv
import io
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

# ══════════════════════════════════════════════════════════════
# 列别名表（唯一真源）
#
# 左边是模型字段，右边是**这份文件里可能出现的列名**。
# 加新导出源时只往这里加名字，不允许在视图里另写一份映射。
# ══════════════════════════════════════════════════════════════
BILL_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    'date': ('日期', '交易日期', '时间', '交易时间', 'date'),
    'amount': ('金额', '交易金额', '发生金额', 'amount'),
    'transaction_type': ('交易类型', '收支类型', '类型', '收/支', '收支', 'type'),
    'category': ('分类', '一级分类', '类目', '类别', 'category'),
    'subcategory': ('子分类', '二级分类', '小类', '细类', 'subcategory'),
    'project': ('项目', 'project'),
    'account': ('账户', '账号', '支付方式', 'account'),
    'account_currency': ('币种', '账户币种', 'currency'),
    'member': ('成员', 'member'),
    'merchant': ('商户', '商家', '交易对方', 'merchant'),
    'notes': ('备注', '说明', 'notes'),
}

#: 精确别名都没命中时，按「名字里带这些词」兜底再认一次。
#:
#: 🔴 为什么必须有这一层：换成按列名识别之后，列名对不上就**静默丢列** ——
#:    `消费分类` / `支出分类` / `分类(一级)` 这类同义写法全都不在别名表里，
#:    导进去分类是空的，而接口照旧返回「新增 N 条」。按位置取值的老实现
#:    反而不会出这个问题（列名随便叫，位置是对的），所以这是一次真实的回归。
#:
#: 🔴 顺序有意义：`子分类` 里含 `分类`，必须先判子分类，否则前者永远认不出来。
#:    同理 `交易类型` 不能放进 `分类` 的关键词里（它含「类型」不含「分类」，
#:    但 `类别` 与 `类型` 只差一个字，别顺手把 `类型` 加进分类）。
BILL_FUZZY_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ('subcategory', (
        '子分类', '二级分类', '小类', '细类', '子类目',
        # 导出工具对「第二级」的叫法五花八门，穷举一定漏；但只要是「子/二级/细」
        # 开头或含「二级」，就是它。下面还有一条结构性兜底（见 `_match_header`），
        # 两列分类挤在同义词表外面时也不至于丢。
        '子类别', '细分类', '子级', '二级', '次级', '子类', 'subcategory',
    )),
    ('category', ('分类', '类目', '类别')),
    ('transaction_type', ('交易类型', '收支类型', '收支', '方向')),
    ('account_currency', ('币种', 'currency')),
    ('amount', ('金额', '发生额', 'amount')),
    ('date', ('日期', '交易时间', '记账时间', '时间')),
    ('account', ('账户', '账号', '支付方式')),
    ('merchant', ('商家', '商户', '交易对方')),
    ('notes', ('备注', '说明')),
    ('member', ('成员',)),
    ('project', ('项目',)),
)

#: 缺这两列就没法入库 —— 其余都可以空着
BILL_REQUIRED_FIELDS: tuple[str, ...] = ('date', 'amount')


def bill_field_options() -> list[dict]:
    """列映射下拉的候选项。

    字段名与中文标签**只来自上面的别名表**（`aliases[0]` 就是它的正式名字），
    前端不持有一份字段常量 —— 否则加一个字段要改两处，漏一处的表现是
    「下拉里选不到」，而不是报错。
    """
    return [
        {
            'value': field_name,
            'label': aliases[0],
            'required': field_name in BILL_REQUIRED_FIELDS,
        }
        for field_name, aliases in BILL_COLUMN_ALIASES.items()
    ]

# 日期格式：由严到宽。秒级排前面，避免 `2025-01-07 12:00:00` 被 `%Y-%m-%d` 截断。
BILL_DATE_FORMATS: tuple[str, ...] = (
    '%Y-%m-%d %H:%M:%S',
    '%Y-%m-%dT%H:%M:%S',
    '%Y-%m-%d %H:%M',
    '%Y-%m-%d',
    '%Y/%m/%d %H:%M:%S',
    '%Y/%m/%d %H:%M',
    '%Y/%m/%d',
)

#: 收支类型：列里的值先归一，不认识的一律 error（不做兜底猜测）
#:
#: 🔴 除「收入 / 支出」外，**原样放行**三个随手记真实存在的值：`转入` / `转出` /
#:    `余额变更`（开发库现有 67 / 67 / 3 条）。它们不是收支，不参与收支统计，
#:    但它们是代付、账户互转的凭据 —— 判成 error 就等于以后再也导不进这批账。
#:    放行的是「已知的枚举值」，不是「任何字符串」：`转账`、`借` 这类仍会报错，
#:    因为那意味着导出方换了口径，猜方向等于替用户决定钱的流向。
BILL_TYPE_VALUES: dict[str, str] = {
    '支出': '支出', '支': '支出', 'out': '支出', 'expense': '支出',
    '收入': '收入', '收': '收入', 'in': '收入', 'income': '收入',
    '转入': '转入', '转出': '转出', '余额变更': '余额变更',
}

#: 表头只在文件前几行里找 —— 扫全表没有意义，只会把某个备注行当表头
BILL_HEADER_SCAN_ROWS = 5

#: 预演里最多回多少行给人看（其余只给计数）
BILL_PREVIEW_ROW_LIMIT = 50

#: 预演里回的前几条「正常行」，用来让人确认列对上了
BILL_PREVIEW_SAMPLE_ROWS = 3


class BillCsvFormatError(Exception):
    """整份文件不可用（不是某一行的问题）—— 视图层直接 400。

    `missing_required` / `columns` 是给用户看的「哪一列没对上」，
    不能只回一句「文件格式不正确」—— 那样用户只能瞎试。
    """

    def __init__(
        self,
        message: str,
        *,
        code: str = 'format',
        missing_required: list[str] | None = None,
        columns: list[dict] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.missing_required = missing_required or []
        self.columns = columns or []


@dataclass
class BillRecord:
    """一行解析成功的账单。字段名与模型一致，落库时逐个对应。"""

    row_no: int
    date: datetime
    amount: Decimal
    transaction_type: str
    category: str = ''
    subcategory: str = ''
    project: str = ''
    account: str = ''
    account_currency: str = ''
    member: str = ''
    merchant: str = ''
    notes: str = ''
    #: 人话提示（例如「金额为负，已按绝对值处理」），不是错误
    note: str = ''

    def amount_key(self) -> str:
        """金额归一成两位小数的字符串 —— 浮点 `==` 比不出「30 还是 30.0」。"""
        return str(self.amount.quantize(Decimal('0.01')))

    def dedupe_key(self) -> tuple:
        """判重键：同一天 + 同金额 + 同类型。"""
        return (self.date.date(), self.amount_key(), self.transaction_type)


@dataclass
class BillRowError:
    row_no: int
    reason: str
    content: str = ''


@dataclass
class BillParseResult:
    header_row: int = 0                       # 1-based，给前端显示
    columns: list[dict] = field(default_factory=list)   # [{raw, mapped, sample}]
    #: 没认出来、但**确实有值**的列：[{raw, sample, filled}]
    #: 🔴 这份清单存在的唯一目的：不让「列名没对上」变成静默丢数据
    ignored_columns: list[dict] = field(default_factory=list)
    needs_default_type: bool = False
    records: list[BillRecord] = field(default_factory=list)
    errors: list[BillRowError] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.records) + len(self.errors)


# ── 小工具 ────────────────────────────────────────────────────

def _norm(cell: str) -> str:
    """列名归一：去 BOM、全角空格、首尾空白，转小写。

    「账户 」与「账户」是同一列 —— 这种差异不该让用户手动去指。
    """
    return (cell or '').replace('\ufeff', '').replace('\u3000', '').strip().lower()


#: 括号里的单位/注释：`金额（元）`、`分类[必填]`、`日期(YYYY-MM-DD)`
_BRACKET_RE = re.compile(r'[（(\[{【][^）)\]】]*[）)\]】]')


def _clean_name(cell: str) -> str:
    """在 `_norm` 之上再去掉括号注释、星号与空格 —— `*金额（元）` 就是「金额」。

    导出工具很喜欢给列名加装饰：必填星号、单位括号、全角空格。
    这些都和「这一列是什么」无关，加进来只会让精确匹配落空。
    """
    text = _BRACKET_RE.sub('', _norm(cell))
    return text.replace('*', '').replace(' ', '').replace('\u200b', '').strip()


#: 预先拍平的别名，避免每次比对都遍历字典（表头不超过 20 列，但这个更直观）
_ALIAS_INDEX: dict[str, str] = {
    _clean_name(alias): field_name
    for field_name, aliases in BILL_COLUMN_ALIASES.items()
    for alias in aliases
}


def decode_csv_bytes(raw: bytes) -> str:
    """按 BOM → UTF-8 → GB18030 的顺序解码。

    Excel「另存为 CSV」在中文 Windows 上默认是 GBK，随手记导出的却常是带 BOM 的
    UTF-8。只认一种的后果是整份文件读成乱码，然后「一列都没认出来」。
    """
    for encoding in ('utf-8-sig', 'utf-8', 'gb18030'):
        try:
            return raw.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    raise BillCsvFormatError('文件编码认不出来，请另存为 UTF-8 或 GBK 再试')


def _fuzzy_fields(name: str) -> list[str]:
    """名字里带哪些关键词 ⇒ 可能是什么字段（按别名表顺序，先到先用）。"""
    return [
        field_name
        for field_name, keywords in BILL_FUZZY_KEYWORDS
        if any(kw in name for kw in keywords)
    ]


def _match_header(row: list[str]) -> dict[str, int]:
    """一行里能认出哪些字段，返回 {字段: 列下标}。

    认不出的列不在这里报 —— `_build_columns` 会把它们以 `mapped=''` 列出来，
    同一件事只说一遍。

    🔴 分两轮：**先所有列走精确匹配，再用同义词兜底**。
       一轮内边认边兜底的话，`创建时间` 排在前面的文件会把 `日期` 抢走 ——
       兜底只能捡精确匹配剩下的，不能抢。
    """
    cleaned = [_clean_name(cell) for cell in row]
    mapping: dict[str, int] = {}

    for idx, name in enumerate(cleaned):
        field_name = _ALIAS_INDEX.get(name)
        if field_name and field_name not in mapping:
            mapping[field_name] = idx

    for idx, name in enumerate(cleaned):
        if not name or idx in mapping.values():
            continue
        candidates = _fuzzy_fields(name)
        for field_name in candidates:
            if field_name not in mapping:
                mapping[field_name] = idx
                break
        else:
            # 结构性兜底：两列分类挤在同义词表外面（`分类` + `分类2` /
            # `分类(二级)` / `二级类别` …），第二列本来会被整列丢掉，
            # 而接口照旧回「新增 N 条」—— 子分类全空且不报错。
            # 判据：这一列最像分类、一级分类已被占、子分类还空着。
            if candidates and candidates[0] == 'category' and 'subcategory' not in mapping:
                mapping['subcategory'] = idx

    return mapping


def locate_header(rows: list[list[str]]) -> tuple[int, dict[str, int]]:
    """在前几行里找表头。返回 (0-based 行下标, 字段→列下标)。

    🔴 命中数相同时取**更靠后**的那一行：随手记的导出是「汇总行 + 列名行」，
    多行标题的文件也一样 —— 越靠后越接近数据。
    """
    best: tuple[int, dict[str, int]] | None = None
    for idx, row in enumerate(rows[:BILL_HEADER_SCAN_ROWS]):
        mapping = _match_header(row)
        if len(mapping) < 2:
            continue
        if best is None or len(mapping) >= len(best[1]):
            best = (idx, mapping)

    if best is not None:
        return best

    # 一个别名都没命中（导出源换了列名）⇒ 退回「第一行非空行当表头」，
    # 让后面的 400 能带上 `columns`，用户在界面上手动指认。
    # 只回一句「没找到表头」的话，那份文件就永远导不进来了。
    for idx, row in enumerate(rows[:BILL_HEADER_SCAN_ROWS]):
        if any((cell or '').strip() for cell in row):
            return idx, {}
    raise BillCsvFormatError('文件是空的，没有任何内容')


def _parse_date(raw: str) -> datetime:
    text = (raw or '').strip()
    if not text:
        raise ValueError('日期为空')
    # 截掉毫秒与时区尾巴：`2025-01-07 12:00:00.123456+08:00`
    for candidate in (text, text[:19]):
        for fmt in BILL_DATE_FORMATS:
            try:
                return datetime.strptime(candidate, fmt)
            except ValueError:
                continue
    raise ValueError(f'日期「{raw}」认不出格式（支持 2025-01-07 / 2025-01-07 12:00:00）')


def _parse_amount(raw: str) -> Decimal:
    text = (raw or '').strip().replace(',', '').replace('¥', '').replace('￥', '')
    if not text:
        raise ValueError('金额为空')
    try:
        return abs(Decimal(text))
    except (InvalidOperation, ValueError):
        raise ValueError(f'金额「{raw}」不是数字')


def normalize_type(raw: str) -> str:
    key = _norm(raw)
    if not key:
        return ''
    return BILL_TYPE_VALUES.get(key, '')


def _apply_user_mapping(
    header: list[str],
    user_mapping: dict[str, str],
) -> dict[str, int]:
    """把「源列名 → 字段」换成「字段 → 列下标」。

    用户改过的映射**整份覆盖**自动识别结果，不与推断结果合并 ——
    合并的后果是「界面上明明清空了，导进去却还有值」。

    先按**原始列名**精确对位，再退回清洗后的名字：前端回传的就是表头原文，
    原文对得上就不该再走归一化（同名两列时归一化会一律指到第一列）。
    """
    raw_header = [(cell or '').strip() for cell in header]
    cleaned_header = [_clean_name(cell) for cell in header]

    result: dict[str, int] = {}
    for raw_name, field_name in user_mapping.items():
        if not field_name:
            continue
        key = (raw_name or '').strip()
        if key in raw_header:
            idx = raw_header.index(key)
        else:
            cleaned = _clean_name(raw_name)
            if cleaned not in cleaned_header:
                continue
            idx = cleaned_header.index(cleaned)
        if field_name not in result:
            result[field_name] = idx
    return result


def parse_bill_csv(
    text: str,
    default_type: str = '',
    user_mapping: dict[str, str] | None = None,
) -> BillParseResult:
    """把 CSV 文本解析成「可入库的记录 + 逐行错误」。

    这里**不碰数据库** —— 判重与写入在 `split_records` / `commit_records` 里做。
    预演与落库共用本函数，所以「预演说新增 110」与「落库写 110」
    不会因为两套解析而分叉。

    `user_mapping`：用户在界面上手工指定过的列（`{"源列名": "字段名"}`）。
    传了就**整份取代**自动识别，让预览与实际落库用的是同一份列映射。
    """
    reader = csv.reader(io.StringIO(text))
    rows = [row for row in reader]
    if len(rows) < 2:
        raise BillCsvFormatError('文件里没有数据行（只看到表头）')

    header_idx, mapping = locate_header(rows)
    if user_mapping is not None:
        mapping = _apply_user_mapping(rows[header_idx], user_mapping)

    result = BillParseResult(header_row=header_idx + 1)
    missing_required = [f for f in BILL_REQUIRED_FIELDS if f not in mapping]
    if missing_required:
        # 决不能「导 0 条还说成功」—— 400 里带清是哪一列没认出来
        raise BillCsvFormatError(
            '缺少必需列：' + '、'.join(BILL_COLUMN_ALIASES[f][0] for f in missing_required),
            code='missing_required',
            missing_required=missing_required,
            columns=_build_columns(rows, header_idx, mapping),
        )

    result.needs_default_type = 'transaction_type' not in mapping
    fallback_type = normalize_type(default_type)

    data_rows = rows[header_idx + 1:]
    if not data_rows:
        raise BillCsvFormatError('文件里没有数据行（表头后面是空的）')

    # 表头行后面的重复表头（多行标题的文件）→ 当表头跳过，不当错误。
    # 🔴 必须同时命中「日期」或「金额」才算重复表头：否则某行的备注写着
    #    「分类」「类型」也会被误吞，那是丢数据。
    while data_rows:
        probe = _match_header(data_rows[0])
        if len(probe) >= 2 and ('date' in probe or 'amount' in probe):
            data_rows = data_rows[1:]
            continue
        break

    for offset, row in enumerate(data_rows):
        row_no = header_idx + 2 + offset         # 表头是第 1 行
        if not any((cell or '').strip() for cell in row):
            continue                             # 全空行不算错，直接跳过

        def cell_of(field_name: str) -> str:
            idx = mapping.get(field_name)
            if idx is None or idx >= len(row):
                return ''
            return (row[idx] or '').strip()

        content = ','.join((c or '').strip() for c in row[:4])

        try:
            date_value = _parse_date(cell_of('date'))
            amount = _parse_amount(cell_of('amount'))

            raw_type = cell_of('transaction_type')
            type_value = normalize_type(raw_type) if raw_type else ''
            if not type_value:
                type_value = fallback_type
            if not type_value:
                if raw_type:
                    raise ValueError(f'交易类型「{raw_type}」不认识（只认 收入 / 支出）')
                if 'transaction_type' in mapping:
                    raise ValueError('这一行没有交易类型')
                # 整列缺失、又没给默认值 ⇒ 先留空：预演要让用户先看见数据，
                # 「必须定方向」由落库那一步强制（`needs_default_type`）

            note = ''
            amount_raw = cell_of('amount')
            if amount_raw.startswith('-') or amount_raw.startswith('−'):
                note = '金额为负，已按绝对值处理'

            result.records.append(BillRecord(
                row_no=row_no,
                date=date_value,
                amount=amount,
                transaction_type=type_value,
                category=cell_of('category'),
                subcategory=cell_of('subcategory'),
                project=cell_of('project'),
                account=cell_of('account'),
                account_currency=cell_of('account_currency'),
                member=cell_of('member'),
                merchant=cell_of('merchant'),
                notes=cell_of('notes'),
                note=note,
            ))
        except ValueError as exc:
            result.errors.append(BillRowError(row_no=row_no, reason=str(exc), content=content))

    result.columns = _build_columns(rows, header_idx, mapping)
    result.ignored_columns = _ignored_columns(rows, header_idx, mapping, data_rows)
    return result


def _ignored_columns(
    rows: list[list[str]],
    header_idx: int,
    mapping: dict[str, int],
    data_rows: list[list[str]],
) -> list[dict]:
    """没被认领、但**有值**的列。

    🔴 这是「按列名识别」带来的一种新型静默失败：列名对不上就不再取值，
    而接口照旧回「新增 N 条」—— 用户只会在月底对账时发现分类全空。
    凡是这种列，一律摆到预演界面上，让用户在落库前看见。
    """
    used = set(mapping.values())
    header = rows[header_idx]
    out: list[dict] = []

    for idx, raw_name in enumerate(header):
        name = (raw_name or '').strip()
        if not name or idx in used:
            continue
        values = [(row[idx] or '').strip() for row in data_rows if idx < len(row)]
        filled = [v for v in values if v]
        if not filled:
            continue
        out.append({'raw': name, 'sample': filled[0][:40], 'filled': len(filled)})
    return out


def _build_columns(
    rows: list[list[str]],
    header_idx: int,
    mapping: dict[str, int],
) -> list[dict]:
    """给前端看的「源列名 → 识别成什么」（含一个样例值）。

    表头里每一列都列出来（`mapped` 为空的就是没认出来），
    这样用户能看到「我这份文件的第 3 列没对上」，而不是只看到一个总数。
    """
    header = rows[header_idx]
    sample_row = rows[header_idx + 1] if header_idx + 1 < len(rows) else []
    idx_to_field = {v: k for k, v in mapping.items()}

    columns: list[dict] = []
    for idx, raw_name in enumerate(header):
        if not (raw_name or '').strip():
            continue
        columns.append({
            'raw': raw_name.strip(),
            'mapped': idx_to_field.get(idx, ''),
            'sample': (sample_row[idx] if idx < len(sample_row) else '').strip(),
        })
    return columns


# ══════════════════════════════════════════════════════════════
# 判重与预览汇总
# ══════════════════════════════════════════════════════════════

def existing_counts(records: list[BillRecord]) -> Counter:
    """把「库里这几天已有的账」读成 Counter，键与 `BillRecord.dedupe_key` 一致。

    只查本次文件覆盖的日期区间 —— 全表扫描 6,700 行没必要，而且文件越大越慢。
    """
    from django.db import connection

    if not records:
        return Counter()

    lo = min(r.date for r in records).date()
    hi = max(r.date for r in records).date() + timedelta(days=1)
    counter: Counter = Counter()
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT DATE(date), amount, transaction_type '
            'FROM wealth_bill_list WHERE date >= %s AND date < %s',
            [lo, hi],
        )
        for day, amount, ttype in cursor.fetchall():
            counter[(day, str(Decimal(str(amount)).quantize(Decimal('0.01'))), ttype)] += 1
    return counter


@dataclass
class BillPreview:
    """预演结论（结构即接口响应，视图层不再加工）。"""

    header_row: int
    columns: list[dict]
    ignored_columns: list[dict]
    needs_default_type: bool
    total: int
    new: int
    duplicate: int
    error: int
    inner_duplicate: int
    rows: list[dict]


@dataclass
class BillSplit:
    """预演与落库共用的判重结论。"""

    new: list[BillRecord]
    duplicates: list[dict]
    inner_duplicate: int


def split_records(parse: BillParseResult) -> BillSplit:
    """按「库里已有 ⇒ 重复；文件内第 2 次出现 ⇒ 仍算新增」结账。

    🔴 文件内完全相同的两行**不判重**：同一天两杯 15 元咖啡是真的两笔。
       旧口径（Counter 计重数）就是这么定的，这里逐字沿用 —— 一旦改成
       「文件内重复就丢」，真实消费会被静默吞掉。`inner_duplicate` 只是提示。

    🔴 预演与落库**都调这一个函数**：两处各写一遍，就会出现
       「预览说新增 110、实际写入 105」这种查不出来的差。
    """
    remaining = existing_counts(parse.records)

    new_records: list[BillRecord] = []
    duplicate_rows: list[dict] = []
    seen: Counter = Counter()
    inner_duplicate = 0

    for rec in parse.records:
        key = rec.dedupe_key()
        if remaining[key] > 0:
            remaining[key] -= 1
            duplicate_rows.append({
                'row_no': rec.row_no,
                'date': rec.date.strftime('%Y-%m-%d %H:%M:%S'),
                'type': rec.transaction_type,
                'amount': float(rec.amount),
                'category': rec.category,
                'subcategory': rec.subcategory,
                'verdict': 'duplicate',
                'reason': '库中已有同一笔（同一天、同金额、同类型）',
            })
            continue
        if seen[key] > 0:
            inner_duplicate += 1
        seen[key] += 1
        new_records.append(rec)

    return BillSplit(new=new_records, duplicates=duplicate_rows, inner_duplicate=inner_duplicate)


def build_preview(parse: BillParseResult) -> BillPreview:
    """预演：只读，判重口径与落库完全一致。"""
    split = split_records(parse)

    error_rows = [{
        'row_no': e.row_no,
        'date': '',
        'type': '',
        'amount': None,
        'category': '',
        'subcategory': '',
        'verdict': 'error',
        'reason': e.reason,
    } for e in parse.errors]

    # 前几条正常行 + 全部问题行，供人扫一眼；其余只给计数
    sample_rows = [{
        'row_no': r.row_no,
        'date': r.date.strftime('%Y-%m-%d %H:%M:%S'),
        'type': r.transaction_type,
        'amount': float(r.amount),
        'category': r.category,
        'subcategory': r.subcategory,
        'verdict': 'new',
        'reason': r.note,
    } for r in split.new[:BILL_PREVIEW_SAMPLE_ROWS]]

    rows = (sample_rows + split.duplicates + error_rows)[:BILL_PREVIEW_ROW_LIMIT]

    return BillPreview(
        header_row=parse.header_row,
        columns=parse.columns,
        ignored_columns=parse.ignored_columns,
        needs_default_type=parse.needs_default_type,
        total=parse.total,
        new=len(split.new),
        duplicate=len(split.duplicates),
        error=len(error_rows),
        inner_duplicate=split.inner_duplicate,
        rows=rows,
    )


# ══════════════════════════════════════════════════════════════
# 落库
# ══════════════════════════════════════════════════════════════

#: 一次 executemany 写多少条 —— 太大撞 max_allowed_packet，太小往返变多
_COMMIT_BATCH_SIZE = 500

_INSERT_CACHE: dict[str, object] = {}


def _insert_plan() -> tuple[str, list]:
    """INSERT 的列清单**由模型字段生成**，不手写。

    🔴 旧实现手写了 15 列，静默漏掉 `project` / `member` / `account_currency`
       —— 导进去就是空值，不报错、也看不出来。列清单跟着模型走，
       以后加字段不用改这里，也不会再漏。
    """
    if not _INSERT_CACHE:
        from ..models import WealthBillList

        fields = [f for f in WealthBillList._meta.concrete_fields if f.name != 'id']
        _INSERT_CACHE['fields'] = fields
        _INSERT_CACHE['sql'] = (
            'INSERT INTO wealth_bill_list (' +
            ', '.join(f.column for f in fields) +
            ') VALUES (' + ', '.join(['%s'] * len(fields)) + ')'
        )
    return _INSERT_CACHE['sql'], _INSERT_CACHE['fields']


@dataclass
class BillCommitResult:
    created: int = 0
    duplicate: int = 0
    skipped_by_user: int = 0
    error: int = 0
    #: [{row_no, reason}]，落库失败与解析失败都算
    errors: list[dict] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.created + self.duplicate + self.skipped_by_user + self.error


def commit_records(
    parse: BillParseResult,
    *,
    skip_rows: set[int] | list[int] | tuple[int, ...] = (),
    user_id: int = 1,
) -> BillCommitResult:
    """把解析结果按判重结论写库。

    `skip_rows`：用户在预览里勾掉不导的物理行号（表头算第 1 行）。
    这些行单独计数为 `skipped_by_user`，**不混进 error** ——
    混进去的后果是「我明明只勾掉 2 行，为什么说 3 行出错」。

    🔴 直接写 naive datetime：`wealth_bill_list` 存的就是**本地时间**，
       走 ORM 保存 aware 值会被转成 UTC（少 8 小时），这里的账会比真实
       消费时间早 8 小时，而且看不出来。项目既有口径如此，别改成 aware。
    """
    from django.db import connection

    split = split_records(parse)
    skip_set = {int(r) for r in skip_rows}
    now = datetime.now()

    result = BillCommitResult(
        duplicate=len(split.duplicates),
        errors=[{'row_no': e.row_no, 'reason': e.reason} for e in parse.errors],
    )
    result.error = len(result.errors)

    pending: list[BillRecord] = []
    for rec in split.new:
        if rec.row_no in skip_set:
            result.skipped_by_user += 1
            continue
        pending.append(rec)

    if not pending:
        return result

    sql, fields = _insert_plan()

    def row_values(rec: BillRecord) -> list:
        values = {
            'transaction_type': rec.transaction_type,
            'date': rec.date,
            'category': rec.category,
            'subcategory': rec.subcategory,
            'project': rec.project,
            'account': rec.account,
            'account_currency': rec.account_currency or 'CNY',
            'member': rec.member or None,
            'merchant': rec.merchant,
            'notes': rec.notes,
            'amount': rec.amount,
            'related_id': None,
            'year': rec.date.year,
            'month': rec.date.month,
            'day': rec.date.day,
            'created_at': now,
            'updated_at': now,
            'user_id': user_id,
        }
        return [values.get(f.name) for f in fields]

    for start in range(0, len(pending), _COMMIT_BATCH_SIZE):
        batch = pending[start:start + _COMMIT_BATCH_SIZE]
        rows = [row_values(rec) for rec in batch]
        try:
            with connection.cursor() as cursor:
                cursor.executemany(sql, rows)
            result.created += len(rows)
        except Exception:
            # 整批失败就逐条重试：一条坏行不该让 500 条一起丢，
            # 更要把「哪一行坏」指出来，而不是只回一句导入失败。
            for rec, values in zip(batch, rows):
                try:
                    with connection.cursor() as cursor:
                        cursor.execute(sql, values)
                    result.created += 1
                except Exception as exc:
                    result.error += 1
                    result.errors.append({
                        'row_no': rec.row_no,
                        'reason': f'写入失败：{exc}',
                    })

    return result
