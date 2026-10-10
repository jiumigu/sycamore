"""账单项分类服务 — 一张规则表服务三个维度（v3.58.22，P1-C）

背景
    wealth_bill_list 只记「这笔钱归在哪个分类」（category / subcategory /
    merchant），不记「这笔钱是什么性质」。于是三类财务规划指标算不出来：
        · 被动收入覆盖率  ← 要「主动 / 被动 / 一次性」
        · 刚性支出覆盖率  ← 要「固定 / 可变」
        · 现金流量表五类  ← 要「现金流类别」
    三者机制同构（按特征给账单项打标签），故合并为一张规则表。

三条口径（即验收标准）
    1. **分类结果不落库、实时算**。账单表是 managed=False 外部表（加不了列），
       且「金额是历史事实、分类是当前视角」—— 改规则本就应当回溯地改变
       往期报表。这与 P1-B 资产快照「头部不缓存派生合计」是同一条原则。
       代价是改规则有历史影响，故必须提供 `preview_rule_impact` 让改动前
       看得见会动多少。
    2. **转入 / 转出 / 余额变更不计入**。前两者是账户间搬运（实测成对出现、
       金额恒等，如 2026-04 各 21 笔 48310），计进去会让收支总额双双虚增；
       后者是对账修正行，不对应任何真实经济行为。
    3. **未归类必须显式报出**，不静默吞掉。每个维度各有一个覆盖率，
       另给 `get_unclassified_candidates` 列出「补哪条规则最划算」。

匹配的单一真源
    `match_classify_rule` 是全项目唯一的分类匹配实现。加一个匹配字段必须
    **同时改三处**：constants.CLASSIFY_RULE_FIELDS + 本函数的取值分支 +
    前端下拉。漏前端 = 选不到，漏后端 = 静默不生效。
    ⚠️ 与 redemption 的归因外挂不同：那三个字段里 `activity_type` 住在
    另一张表（temporal_task_meta），须按 task_name 反查后传入；本表的
    category / subcategory / merchant **都在 wealth_bill_list 本行上**，
    直接取即可，不需要间接步骤、也不会 N+1。
"""

from django.db.models import Count, Q

from apps.wealth.constants import (
    CASHFLOW_CLASSES,
    CASHFLOW_EXPENSE_CLASSES,
    CASHFLOW_INCOME_CLASSES,
    CLASSIFY_CANDIDATE_LIMIT,
    CLASSIFY_COUNTED_TYPES,
    CLASSIFY_DEFAULT_PRIORITY,
    CLASSIFY_EXCLUDED_TYPES,
    CLASSIFY_RULE_FIELD_KEYS,
    CLASSIFY_RULE_FIELD_SPECIFICITY,
    CLASSIFY_SEED_RULES,
    EXPENSE_NATURES,
    INCOME_TYPES,
    NECESSITY_VALUES,
)
from apps.wealth.models import WealthBillList, WealthClassifyRule


# ══════════════════════════════════════════════════════════════
# 内部工具
# ══════════════════════════════════════════════════════════════


def _round(value, digits: int = 2) -> float:
    return round(float(value or 0), digits)


def _norm(value):
    """空串 / 空白 → None。三个标签列都是「可空且语义上等价于不设」。"""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _get(bill, field):
    """同时支持 dict 与模型实例取值 —— 预览用的是 dict，汇总用的是 QuerySet 行。"""
    if isinstance(bill, dict):
        return bill.get(field)
    return getattr(bill, field, None)


def _parse_yearmon(yearmon):
    """'YYYY-MM' → (year, month)。非法返回 (None, None)。

    ⚠️ 月份过滤走 wealth_bill_list 的 **year / month 整型列**
    （全表 6588 行 0 空值），不走 date 区间：既绕开 USE_TZ 与
    无时区外部表的换算坑，也与 review_service 的既有写法一致。
    """
    if not yearmon or not isinstance(yearmon, str) or len(yearmon) < 7:
        return None, None
    try:
        year = int(yearmon[:4])
        month = int(yearmon[5:7])
    except (TypeError, ValueError):
        return None, None
    if not (1 <= month <= 12):
        return None, None
    return year, month


def _period_label(yearmon) -> str:
    return yearmon if yearmon else '全周期'


def _bill_queryset(user_id: int = 1, yearmon: str | None = None, counted_only: bool = False):
    """账单基础查询集。

    ⚠️ 不上 `.order_by()`：外部表 `Meta.ordering = ['-date']` 会被注入
       SELECT，而本函数后续要做 `values().annotate()` 聚合 —— 注入的排序会
       混进 GROUP BY 而把聚合拆碎（项目硬坑②）。故显式清序。
    """
    qs = WealthBillList.objects.filter(user_id=user_id).order_by()
    year, month = _parse_yearmon(yearmon)
    if year is not None:
        qs = qs.filter(year=year, month=month)
    if counted_only:
        qs = qs.filter(transaction_type__in=CLASSIFY_COUNTED_TYPES)
    return qs


# ══════════════════════════════════════════════════════════════
# 匹配 —— 全项目唯一实现
# ══════════════════════════════════════════════════════════════


def match_classify_rule(bill, rules):
    """按优先级匹配分类规则，返回**命中的规则对象**或 None。

    🔴 **单一真源**：汇总、预览、未归类清单全部走本函数，不许各写一份。

    胜负规则（两级，都可解释）：
        ① `priority` 数值大者胜；
        ② 优先级相同时**更具体的字段胜**（merchant > subcategory > category）。
    为什么不靠 id 决胜：那会让结果随「谁先建的规则」而变，同样两条规则
    换个创建顺序结论就不同 —— 不可预测的规则比错的规则更难查。

    `bill` 可以是 dict（预览）或模型实例（汇总）。
    """
    best = None
    best_key = None
    for rule in rules:
        field = rule.rule_field
        if field not in CLASSIFY_RULE_FIELD_KEYS:
            continue  # 已废弃 / 未来字段：一律不匹配，不静默按别的维度算
        val = _get(bill, field)
        if val is None or str(val) != rule.match_value:
            continue
        key = (rule.priority or 0, CLASSIFY_RULE_FIELD_SPECIFICITY.get(field, 0))
        if best_key is None or key > best_key:
            best, best_key = rule, key
    return best


def classify_bill(bill, rules) -> dict:
    """给一条账单项打上三个维度的标签。

    ⚠️ **收支方向隔离**：一条 merchant 规则可能同时命中收入行与支出行
    （如商户「支付宝」），此时收入行只认收入侧标签、支出行只认支出侧标签，
    另一侧标签自动忽略。否则会出现「支出行带了收入性质」这种脏数据。
    ⚠️ 非计入类型（转入/转出/余额变更）即使命中规则也**不出标签** ——
    它们不是收支，贴任何收支标签都是错的。`rule_id` 仍返回，便于排查
    「为什么这笔没归类」。

    返回的 `matched_*` 三个键是「命中来源」，前端可据此显示
    「这条标签来自哪条规则」（与归因外挂的 rule_field 提示同款用途）。
    """
    result = {
        'rule_id': None,
        'matched_field': None,
        'matched_value': None,
        'income_type': None,
        'expense_nature': None,
        'cashflow_class': None,
    }
    rule = match_classify_rule(bill, rules)
    if rule is None:
        return result

    result['rule_id'] = rule.id
    result['matched_field'] = rule.rule_field
    result['matched_value'] = rule.match_value

    transaction_type = _get(bill, 'transaction_type')
    if transaction_type == '收入':
        result['income_type'] = _norm(rule.income_type)
        if rule.cashflow_class in CASHFLOW_INCOME_CLASSES:
            result['cashflow_class'] = rule.cashflow_class
    elif transaction_type == '支出':
        result['expense_nature'] = _norm(rule.expense_nature)
        if rule.cashflow_class in CASHFLOW_EXPENSE_CLASSES:
            result['cashflow_class'] = rule.cashflow_class
    return result


def _load_active_rules(user_id: int = 1) -> list:
    """启用中的规则，排序固定为 `-priority, id`。

    排序固定是**正确性要求**而非美观：`match_classify_rule` 的平局决胜
    依赖遍历顺序确定性，乱序会让同样的数据两次汇总结果不同。
    """
    return list(
        WealthClassifyRule.objects
        .filter(user_id=user_id, is_active=True)
        .order_by('-priority', 'id')
    )


# ══════════════════════════════════════════════════════════════
# 规则 CRUD
# ══════════════════════════════════════════════════════════════


def _rule_row(rule: WealthClassifyRule) -> dict:
    return {
        'id': rule.id,
        'rule_field': rule.rule_field,
        'match_value': rule.match_value,
        'income_type': _norm(rule.income_type),
        'expense_nature': _norm(rule.expense_nature),
        'cashflow_class': _norm(rule.cashflow_class),
        'priority': rule.priority,
        'is_active': rule.is_active,
        'note': rule.note or '',
        'updated_at': rule.updated_at,
    }


def get_rule_list(user_id: int = 1, include_inactive: bool = False) -> list[dict]:
    """规则台账（裸数组，量小、前端整表渲染）。"""
    qs = WealthClassifyRule.objects.filter(user_id=user_id)
    if not include_inactive:
        qs = qs.filter(is_active=True)
    return [_rule_row(r) for r in qs.order_by('-priority', 'rule_field', 'id')]


def get_rule_summary(user_id: int = 1) -> dict:
    """规则结构汇总：各匹配字段的规则数、各维度的覆盖条数。"""
    rows = list(WealthClassifyRule.objects.filter(user_id=user_id))
    active = [r for r in rows if r.is_active]

    by_field = {key: 0 for key in CLASSIFY_RULE_FIELD_KEYS}
    for r in active:
        if r.rule_field in by_field:
            by_field[r.rule_field] += 1

    def _filled(field):
        return sum(1 for r in active if _norm(getattr(r, field)) is not None)

    return {
        'total': len(rows),
        'active': len(active),
        'inactive': len(rows) - len(active),
        'by_field': by_field,
        'by_dimension': {
            'income_type': _filled('income_type'),
            'expense_nature': _filled('expense_nature'),
            'cashflow_class': _filled('cashflow_class'),
        },
        'default_priority': dict(CLASSIFY_DEFAULT_PRIORITY),
        'field_specificity': dict(CLASSIFY_RULE_FIELD_SPECIFICITY),
    }


def create_rule(data: dict, user_id: int = 1) -> dict:
    """新建规则。`priority` 未给时按匹配字段的具体度自动取默认值。"""
    payload = _rule_payload(data, partial=False)
    obj = WealthClassifyRule.objects.create(user_id=user_id, **payload)
    return _rule_row(obj)


def update_rule(rule_id: int, data: dict, user_id: int = 1) -> dict:
    """更新规则。`match_value` 留空表示不改（避免前端只传部分字段时被清空）。"""
    obj = WealthClassifyRule.objects.filter(id=rule_id, user_id=user_id).first()
    if not obj:
        raise ValueError('规则不存在')
    payload = _rule_payload(data, partial=True, instance=obj)
    for key, value in payload.items():
        setattr(obj, key, value)
    obj.save()
    return _rule_row(obj)


def delete_rule(rule_id: int, user_id: int = 1) -> int:
    """删除规则。**没有保护约束**：分类结果不落库，删规则只是改变当前视角。

    ⚠️ 但仍会改变往期报表 —— 这是本表「分类是当前视角」口径的直接后果。
       若要保留历史口径，应把规则**停用**而不是删除（停用同样能追溯原因）。
    """
    deleted, _ = WealthClassifyRule.objects.filter(id=rule_id, user_id=user_id).delete()
    if not deleted:
        raise ValueError('规则不存在')
    return rule_id


def _rule_payload(data: dict, partial: bool, instance=None) -> dict:
    """序列化器校验之后的载荷 → 模型字段。

    ⚠️ 空串归一为 None：三个标签列「空串」与「NULL」语义相同（都是不设），
       但只有 NULL 能通过 `_norm` 的一致性判断，混着存会让
       「这个维度覆盖了几条规则」统计出两个口径。
    ⚠️ `instance` 只用于 partial 更新时回退取 `rule_field` ——
       否则「只改 priority」的请求会因载荷里没有 rule_field 而算不出默认值。
    """
    payload = {}
    if not partial or 'rule_field' in data:
        payload['rule_field'] = data.get('rule_field')
    if not partial or 'match_value' in data:
        payload['match_value'] = str(data.get('match_value') or '').strip()
    for field in ('income_type', 'expense_nature', 'cashflow_class'):
        if not partial or field in data:
            payload[field] = _norm(data.get(field))
    if not partial or 'priority' in data:
        priority = data.get('priority')
        if priority in (None, ''):
            field = payload.get('rule_field') or getattr(instance, 'rule_field', None)
            priority = CLASSIFY_DEFAULT_PRIORITY.get(field, 0)
        payload['priority'] = int(priority)
    if not partial or 'is_active' in data:
        payload['is_active'] = bool(data.get('is_active', True))
    if not partial or 'note' in data:
        payload['note'] = _norm(data.get('note')) or ''
    return payload


def seed_classify_rules(user_id: int = 1, overwrite: bool = False) -> dict:
    """按 `CLASSIFY_SEED_RULES` 初始化规则（幂等）。

    `(user_id, rule_field, match_value)` 是唯一键，故重复执行只会命中已有行：
        overwrite=False（默认）→ 只补缺失的，**不动用户改过的规则**；
        overwrite=True          → 把种子值重新盖上去（会丢掉用户改动，慎用）。
    手工新增的规则（不在种子里）两种情况都不受影响。
    """
    created, updated, skipped = 0, 0, 0
    for field, value, income, nature, cashflow, priority, note in CLASSIFY_SEED_RULES:
        defaults = {
            'income_type': _norm(income),
            'expense_nature': _norm(nature),
            'cashflow_class': _norm(cashflow),
            'priority': priority,
            'note': note,
            'is_active': True,
        }
        existing = WealthClassifyRule.objects.filter(
            user_id=user_id, rule_field=field, match_value=value,
        ).first()
        if existing is None:
            WealthClassifyRule.objects.create(
                user_id=user_id, rule_field=field, match_value=value, **defaults,
            )
            created += 1
        elif overwrite:
            for key, val in defaults.items():
                setattr(existing, key, val)
            existing.save()
            updated += 1
        else:
            skipped += 1
    return {
        'created': created,
        'updated': updated,
        'skipped': skipped,
        'total': len(CLASSIFY_SEED_RULES),
        'overwrite': overwrite,
    }


# ══════════════════════════════════════════════════════════════
# 影响预览 —— 改规则前先看会动多少
# ══════════════════════════════════════════════════════════════


class _CandidateRule:
    """未落库的候选规则，只为复用 `match_classify_rule` 的匹配逻辑。

    刻意不复用 `WealthClassifyRule` 实例：那需要先写库再删，
    预览失败会留下半条规则。这里只要同名属性即可参与匹配。
    """

    id = None

    def __init__(self, rule_field, match_value, priority, income_type,
                 expense_nature, cashflow_class):
        self.rule_field = rule_field
        self.match_value = match_value
        self.priority = priority
        self.income_type = income_type
        self.expense_nature = expense_nature
        self.cashflow_class = cashflow_class


def preview_rule_impact(data: dict, user_id: int = 1,
                        yearmon: str | None = None, sample_limit: int = 5) -> dict:
    """预览一条候选规则会命中什么、会改变什么（**不写库**）。

    两层信息：
        matched_*  —— 这条规则命中多少笔、多少钱（「值不值得建」）；
        changed_*  —— 命中行里，现有标签会被它**改掉**多少（「会不会误伤」）。
                     计算方式是把候选规则插进现有规则集重新跑一遍比对，
                     而不是只数命中数：优先级低的候选规则可能命中一大片
                     却一条都改不动，只报命中数会让人误判影响面。
    """
    field = data.get('rule_field')
    value = str(data.get('match_value') or '').strip()
    if field not in CLASSIFY_RULE_FIELD_KEYS or not value:
        raise ValueError('匹配字段或匹配值不合法')

    priority = data.get('priority')
    if priority in (None, ''):
        priority = CLASSIFY_DEFAULT_PRIORITY.get(field, 0)
    candidate = _CandidateRule(
        rule_field=field,
        match_value=value,
        priority=int(priority),
        income_type=_norm(data.get('income_type')),
        expense_nature=_norm(data.get('expense_nature')),
        cashflow_class=_norm(data.get('cashflow_class')),
    )

    current_rules = _load_active_rules(user_id)
    simulated_rules = current_rules + [candidate]

    matched_count, matched_amount = 0, 0.0
    changed_count, changed_amount = 0, 0.0
    by_type: dict[str, int] = {}
    samples: list[dict] = []

    for bill in _bill_queryset(user_id, yearmon):
        if _get(bill, field) is None or str(_get(bill, field)) != value:
            continue
        if bill.transaction_type not in CLASSIFY_COUNTED_TYPES:
            continue
        matched_count += 1
        matched_amount += float(bill.amount or 0)
        by_type[bill.transaction_type] = by_type.get(bill.transaction_type, 0) + 1

        before = classify_bill(bill, current_rules)
        after = classify_bill(bill, simulated_rules)
        labels = ('income_type', 'expense_nature', 'cashflow_class')
        if any(before[key] != after[key] for key in labels):
            changed_count += 1
            changed_amount += float(bill.amount or 0)
            if len(samples) < sample_limit:
                samples.append({
                    'date': bill.date,
                    'category': bill.category or '',
                    'subcategory': bill.subcategory or '',
                    'merchant': bill.merchant or '',
                    'transaction_type': bill.transaction_type,
                    'amount': _round(bill.amount),
                    'before': {key: before[key] for key in labels},
                    'after': {key: after[key] for key in labels},
                })

    return {
        'rule_field': field,
        'match_value': value,
        'priority': candidate.priority,
        'matched_count': matched_count,
        'matched_amount': _round(matched_amount),
        'changed_count': changed_count,
        'changed_amount': _round(changed_amount),
        'by_transaction_type': by_type,
        'samples': samples,
        'period_label': _period_label(yearmon),
    }


# ══════════════════════════════════════════════════════════════
# 归类汇总
# ══════════════════════════════════════════════════════════════


def classify_summary(yearmon: str | None = None, user_id: int = 1) -> dict:
    """按三个维度汇总某期（或全周期）的归类结果 + 各维度覆盖率。

    ⚠️ 覆盖率的分母是**各维度自己的适用金额**，不是全表金额：
       收入性质的分母 = 收入总额（支出行本来就没有收入性质）；
       支出刚性的分母 = 支出总额；
       现金流类别的分母 = 收入 + 支出总额（两向都要有类）。
       用一个统一分母会让「收入维度覆盖率」被庞大的支出额稀释成接近 0，
       看着像规则没生效 —— 数字会骗人，分母要说清楚。

    ⚠️ 未归类金额**必须显式报出**（`unclassified` + 覆盖率），
       不静默并入某一类。这与时间统计「未归类计总时长但不参与完整度」
       是同一处理原则。
    """
    rules = _load_active_rules(user_id)
    qs = _bill_queryset(user_id, yearmon)

    income = {'total': 0.0, 'by_type': {k: 0.0 for k in INCOME_TYPES},
              'unclassified': 0.0, 'count': 0}
    expense = {'total': 0.0, 'by_nature': {k: 0.0 for k in EXPENSE_NATURES},
               'unclassified': 0.0, 'count': 0}
    cashflow = {k: 0.0 for k in CASHFLOW_CLASSES}
    cashflow['unclassified'] = 0.0
    excluded = {k: {'transaction_type': k, 'count': 0, 'amount': 0.0}
                for k in CLASSIFY_EXCLUDED_TYPES}
    counted_count = 0
    counted_total = 0.0

    for bill in qs:
        ttype = bill.transaction_type
        amount = float(bill.amount or 0)
        if ttype not in CLASSIFY_COUNTED_TYPES:
            bucket = excluded.get(ttype)
            if bucket is not None:
                bucket['count'] += 1
                bucket['amount'] += amount
            continue

        counted_count += 1
        counted_total += amount
        labels = classify_bill(bill, rules)

        if ttype == '收入':
            income['count'] += 1
            income['total'] += amount
            if labels['income_type']:
                income['by_type'][labels['income_type']] = (
                    income['by_type'].get(labels['income_type'], 0.0) + amount
                )
            else:
                income['unclassified'] += amount
        else:
            expense['count'] += 1
            expense['total'] += amount
            if labels['expense_nature']:
                expense['by_nature'][labels['expense_nature']] = (
                    expense['by_nature'].get(labels['expense_nature'], 0.0) + amount
                )
            else:
                expense['unclassified'] += amount

        if labels['cashflow_class']:
            cashflow[labels['cashflow_class']] = (
                cashflow.get(labels['cashflow_class'], 0.0) + amount
            )
        else:
            cashflow['unclassified'] += amount

    def _rate(classified, total):
        return round(classified / total, 4) if total else 0.0

    income_classified = income['total'] - income['unclassified']
    expense_classified = expense['total'] - expense['unclassified']
    cashflow_classified = counted_total - cashflow['unclassified']

    return {
        'yearmon': yearmon,
        'period_label': _period_label(yearmon),
        'bill_count': counted_count,
        'bill_amount': _round(counted_total),
        'income': {
            'total': _round(income['total']),
            'count': income['count'],
            'by_type': {k: _round(v) for k, v in income['by_type'].items()},
            'unclassified': _round(income['unclassified']),
        },
        'expense': {
            'total': _round(expense['total']),
            'count': expense['count'],
            'by_nature': {k: _round(v) for k, v in expense['by_nature'].items()},
            'unclassified': _round(expense['unclassified']),
        },
        'cashflow': {k: _round(v) for k, v in cashflow.items()},
        'coverage': {
            'income_type': _rate(income_classified, income['total']),
            'expense_nature': _rate(expense_classified, expense['total']),
            'cashflow_class': _rate(cashflow_classified, counted_total),
        },
        'excluded': [excluded[k] for k in CLASSIFY_EXCLUDED_TYPES],
    }


def get_unclassified_candidates(yearmon: str | None = None, user_id: int = 1,
                                limit: int = CLASSIFY_CANDIDATE_LIMIT) -> dict:
    """未归类候选清单 —— 按 `(category, subcategory)` 聚合，金额降序。

    这张清单回答的是「**下一条规则该建在哪儿**」：
    与其让人对着 6588 行流水发呆，不如直接说「食品酒水 / 早午晚餐
    还有 105007 元没归类，在这里建一条规则最划算」。

    分组粒度选 `(category, subcategory)` 而不是更细的商户：
    商户有 5000+ 个取值，按商户聚合会列出一屏长尾，
    而同一子分类下的商户性质通常一致 —— 一条子分类规则即可解决。
    `merchant_samples` 给出组内金额最高的几个商户，供想更精确时参考。
    """
    rules = _load_active_rules(user_id)
    groups: dict[tuple, dict] = {}

    for bill in _bill_queryset(user_id, yearmon, counted_only=True):
        ttype = bill.transaction_type
        labels = classify_bill(bill, rules)

        if ttype == '收入':
            needed = ('income_type', 'cashflow_class')
        else:
            needed = ('expense_nature', 'cashflow_class')
        missing = [key for key in needed if not labels[key]]
        if not missing:
            continue

        key = (bill.category or '', bill.subcategory or '')
        group = groups.setdefault(key, {
            'category': key[0],
            'subcategory': key[1],
            'count': 0,
            'amount': 0.0,
            'missing_dimensions': set(),
            'transaction_types': set(),
            'merchants': {},
        })
        group['count'] += 1
        group['amount'] += float(bill.amount or 0)
        group['missing_dimensions'].update(missing)
        group['transaction_types'].add(ttype)
        merchant = (bill.merchant or '').strip()
        if merchant:
            group['merchants'][merchant] = group['merchants'].get(merchant, 0.0) + float(bill.amount or 0)

    rows = []
    for group in groups.values():
        # 建议规则建在**最窄的可用字段**上：有子分类就用子分类，否则退回分类。
        # 这与默认优先级（具体度派生）方向一致 —— 建议的就是能起作用的。
        if group['subcategory']:
            suggested_field, suggested_value = 'subcategory', group['subcategory']
        else:
            suggested_field, suggested_value = 'category', group['category']
        merchants = sorted(group['merchants'].items(), key=lambda kv: kv[1], reverse=True)[:3]
        rows.append({
            'category': group['category'],
            'subcategory': group['subcategory'],
            'count': group['count'],
            'amount': _round(group['amount']),
            'transaction_types': sorted(group['transaction_types']),
            'missing_dimensions': sorted(group['missing_dimensions']),
            'suggested_field': suggested_field,
            'suggested_value': suggested_value,
            'merchant_samples': [m for m, _ in merchants],
        })

    rows.sort(key=lambda r: r['amount'], reverse=True)
    return {
        'yearmon': yearmon,
        'period_label': _period_label(yearmon),
        'total_count': sum(r['count'] for r in rows),
        'total_amount': _round(sum(r['amount'] for r in rows)),
        'items': rows[:limit],
    }


# 供视图层复用的汇总/聚合入口别名（避免视图里散落 Q/Sum 聚合）
def classify_dimension_totals(yearmon: str | None = None, user_id: int = 1) -> dict:
    """轻量版归类合计 —— 只回三个维度的字典，供比率类指标（P2-A）取数。

    与 `classify_summary` 的区别：不做覆盖率、不做排除项、不出明细，
    只把「主动/被动/一次性」「固定/可变」「五类」的金额直接给出。
    比率类指标需要的是干净的分子分母，多给的东西反而容易误用。
    """
    qs = _bill_queryset(user_id, yearmon, counted_only=True)
    rows = list(qs.values('transaction_type', 'category', 'subcategory', 'merchant', 'amount'))

    rules = _load_active_rules(user_id)
    income = {k: 0.0 for k in INCOME_TYPES}
    expense = {k: 0.0 for k in EXPENSE_NATURES}
    cashflow = {k: 0.0 for k in CASHFLOW_CLASSES}
    income_total = expense_total = 0.0

    for row in rows:
        labels = classify_bill(row, rules)
        amount = float(row['amount'] or 0)
        if row['transaction_type'] == '收入':
            income_total += amount
            if labels['income_type']:
                income[labels['income_type']] = income.get(labels['income_type'], 0.0) + amount
        else:
            expense_total += amount
            if labels['expense_nature']:
                expense[labels['expense_nature']] = expense.get(labels['expense_nature'], 0.0) + amount
        if labels['cashflow_class']:
            cashflow[labels['cashflow_class']] = cashflow.get(labels['cashflow_class'], 0.0) + amount

    return {
        'income_total': _round(income_total),
        'expense_total': _round(expense_total),
        'income_type': {k: _round(v) for k, v in income.items()},
        'expense_nature': {k: _round(v) for k, v in expense.items()},
        'cashflow_class': {k: _round(v) for k, v in cashflow.items()},
    }


def monthly_classified_totals(ym_keys: list[int], user_id: int = 1) -> dict:
    """按**自然月**聚合的归类结果 — 供比率类指标（P2-A）算滚动窗口。

    ym_keys: `year*100+month` 列表（如 [202607, 202608, 202609]）。

    与 `classify_dimension_totals` 的区别：后者把整段窗口**合并成一个数**，
    适合「看这三个月合起来怎么样」；本函数**按月保留**，因为比率需要的是
    「近 3 个月的月均」这类滚动量 —— 合并后再除会算错（把三个月合计当一个月）。

    ⚠️ 返回值**包含所有请求的月份**（无记录的月份给全 0 骨架），
       调用方据此可以放心地做 `sum(...) / len(...)` ——
       若只返回有记录的月份，调用方得自己补零，而补错的方向恰恰是危险的：
       把「没有记录」当成「当月支出为零」，会把月均拉低、把「能活几个月」抬高。

    ⚠️ **不计入的类型（转入/转出/余额变更）在这里就已剔除**，
       调用方拿到的 income_total / expense_total 天然互不重复 ——
       不要在调用处再减一次「内部转账」，那会减掉并不存在的量。

    返回结构（键为 ym_key 字符串以适配 JSON；服务层内部用整型键）::

        {
          202607: {
            'year': 2026, 'month': 7, 'ym_key': 202607,
            'income_total': ..., 'expense_total': ...,
            'income_type': {'主动': .., '被动': .., '一次性': ..},
            'expense_nature': {'固定': .., '可变': ..},
            'necessity': {
                'amounts': {'必要': .., '可选': .., '冲动': ..},
                'filled_rows': 62, 'total_rows': 112,
                'filled_amount': ..., 'total_amount': ...,
            },
          },
          ...
        }
    """
    keys = sorted({int(k) for k in (ym_keys or [])})
    buckets: dict[int, dict] = {}
    for key in keys:
        buckets[key] = {
            'year': key // 100, 'month': key % 100, 'ym_key': key,
            'income_total': 0.0, 'expense_total': 0.0,
            'income_type': {k: 0.0 for k in INCOME_TYPES},
            'expense_nature': {k: 0.0 for k in EXPENSE_NATURES},
            'necessity': {
                'amounts': {k: 0.0 for k in NECESSITY_VALUES},
                'filled_rows': 0, 'total_rows': 0,
                'filled_amount': 0.0, 'total_amount': 0.0,
            },
        }
    if not keys:
        return buckets

    cond = Q()
    for key in keys:
        cond |= Q(year=key // 100, month=key % 100)

    qs = _bill_queryset(user_id, counted_only=True).filter(cond)
    rows = list(qs.values('year', 'month', 'transaction_type', 'amount',
                          'category', 'subcategory', 'merchant', 'necessity'))
    rules = _load_active_rules(user_id)

    for row in rows:
        key = int(row['year'] or 0) * 100 + int(row['month'] or 0)
        bucket = buckets.get(key)
        if bucket is None:
            continue
        amount = float(row['amount'] or 0)
        labels = classify_bill(row, rules)

        if row['transaction_type'] == '收入':
            bucket['income_total'] += amount
            if labels['income_type']:
                bucket['income_type'][labels['income_type']] += amount
        else:
            bucket['expense_total'] += amount
            if labels['expense_nature']:
                bucket['expense_nature'][labels['expense_nature']] += amount

            # necessity 只对支出行有意义（它是「这笔消费该不该花」），
            # 收入行没有「冲动收入」这回事，不参与填写率统计。
            necessity = _norm(row.get('necessity'))
            bucket['necessity']['total_rows'] += 1
            bucket['necessity']['total_amount'] += amount
            if necessity:
                bucket['necessity']['filled_rows'] += 1
                bucket['necessity']['filled_amount'] += amount
                if necessity in bucket['necessity']['amounts']:
                    bucket['necessity']['amounts'][necessity] += amount

    for bucket in buckets.values():
        bucket['income_total'] = _round(bucket['income_total'])
        bucket['expense_total'] = _round(bucket['expense_total'])
        bucket['income_type'] = {k: _round(v) for k, v in bucket['income_type'].items()}
        bucket['expense_nature'] = {k: _round(v) for k, v in bucket['expense_nature'].items()}
        bucket['necessity']['amounts'] = {
            k: _round(v) for k, v in bucket['necessity']['amounts'].items()
        }
        bucket['necessity']['filled_amount'] = _round(bucket['necessity']['filled_amount'])
        bucket['necessity']['total_amount'] = _round(bucket['necessity']['total_amount'])
    return buckets


def available_periods(user_id: int = 1, limit: int = 24) -> list[str]:
    """有账单数据的年月列表（倒序）—— 前端下拉选择期用。

    用 `values().annotate()` 聚合，故 `_bill_queryset` 已清序（否则外部表
    ordering 注入会拆碎 GROUP BY，项目硬坑②）。
    """
    rows = (
        _bill_queryset(user_id)
        .filter(transaction_type__in=CLASSIFY_COUNTED_TYPES)
        .values('year', 'month')
        .annotate(c=Count('id'))
        .order_by('-year', '-month')[:limit]
    )
    return [f"{r['year']:04d}-{r['month']:02d}" for r in rows if r['year'] and r['month']]
