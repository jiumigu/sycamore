"""工具箱业务逻辑"""

from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from statistics import median

from django.utils import timezone

from .models import CareerEnergyAudit, ElectricityRecord


def calc_career_decision(data: dict) -> tuple:
    """计算职业能量审计判定

    Returns:
        (total, decision, advice, work_score, env_score, growth_score, body_score)
    """
    # 工作内容本身：7项×5分 = 35分
    work_fields = [
        'task_clarity', 'skill_match', 'autonomy', 'achievement',
        'learning', 'workload', 'visibility',
    ]
    work_score = sum(data.get(f, 0) for f in work_fields)

    # 环境与人：8项×5分 = 40分
    env_fields = [
        'communication', 'transparency', 'respect', 'feedback_quality',
        'process_smooth', 'commute', 'physical_env', 'colleague_relation',
    ]
    env_score = sum(data.get(f, 0) for f in env_fields)

    # 成长与未来：5项×5分 = 25分
    growth_fields = [
        'skill_growth', 'vision_expand', 'resume_value',
        'income_satisfy', 'direction',
    ]
    growth_score = sum(data.get(f, 0) for f in growth_fields)

    # 身体与情绪：将1-5反转为-2~+2，加上身体信号扣分
    body_fields = [
        'morning_feeling', 'sunday_anxiety', 'after_work_state',
        'sleep_quality', 'emotion_stability',
    ]
    body_score = 0
    for f in body_fields:
        body_score -= (data.get(f, 3) - 3)  # 3=正常不扣分
    body_signals = data.get('body_signals', '')
    if body_signals:
        body_score -= len([s for s in body_signals.split(',') if s.strip()])

    total = work_score + env_score + growth_score + body_score

    if total >= 40:
        decision = '🟢 继续'
        advice = '能量正向，这份工作在滋养你。'
    elif total >= 10:
        decision = '🟡 待观察'
        advice = '有好有坏，定期审计关注变化。'
    elif total >= -20:
        decision = '🟠 准备离开'
        advice = '消耗大于补给，开始"为离开攒路费"。'
    else:
        decision = '🔴 该走了'
        advice = '身体已经在报警，设一个离开日期。'

    warnings = []
    if data.get('morning_feeling', 3) >= 4:
        warnings.append('你每天早上都在抗拒这份工作。身体最诚实。')
    if body_signals:
        count = len([s for s in body_signals.split(',') if s.strip()])
        if count >= 4:
            warnings.append(f'身体信号{count}个。身体比大脑更早发现"不适合"。')

    if warnings:
        advice += '\n\n⚠️ ' + '；'.join(warnings)

    return total, decision, advice, work_score, env_score, growth_score, body_score


def update_career_audit_decision(instance: CareerEnergyAudit) -> None:
    """重新计算实例的分数和判定并保存"""
    data = {f.name: getattr(instance, f.name) for f in CareerEnergyAudit._meta.fields}
    total, decision, advice, ws, es, gs, bs = calc_career_decision(data)
    instance.total_score = total
    instance.decision = decision
    instance.advice = advice
    instance.work_score = ws
    instance.env_score = es
    instance.growth_score = gs
    instance.body_score = bs


# ─── 时薪计算 ────────────────────────────────────


def _extra_income_monthly(extra_incomes) -> Decimal:
    """把额外收入统一换算为每月金额（daily*30 / yearly/12 / monthly原值）"""
    total = Decimal('0')
    for source in extra_incomes or []:
        if not isinstance(source, dict):
            continue
        try:
            amount = Decimal(str(source.get('amount') or 0))
        except (ValueError, TypeError):
            amount = Decimal('0')
        period = source.get('period') or 'monthly'
        if period == 'daily':
            total += amount * 30
        elif period == 'yearly':
            total += amount / 12
        else:
            total += amount
    return total


def calculate_hourly_wage(
    monthly_salary,
    rest_type='双休',
    work_start='09:00',
    work_end='18:00',
    lunch_break=60,
    commute_minutes=0,
    calc_mode='formal',
    freelance_time_mode='fixed',
    freelance_days=None,
    freelance_hours_per_day=None,
    weekly_hours=None,
    freelance_weeks=4,
    extra_incomes=None,
):
    """计算实际时薪（含通勤时间与额外收入，时薪按总收入/总投入小时）"""
    total_salary = Decimal(str(monthly_salary))
    total_extra = _extra_income_monthly(extra_incomes)
    total_income = total_salary + total_extra

    if calc_mode == 'freelance':
        stats = _freelance_stats(
            time_mode=freelance_time_mode,
            days=freelance_days,
            hours_per_day=freelance_hours_per_day,
            weekly_hours=weekly_hours or [],
            weeks=freelance_weeks,
            commute_minutes=commute_minutes,
        )
    else:
        stats = _formal_stats(
            rest_type=rest_type,
            work_start=work_start,
            work_end=work_end,
            lunch_break=lunch_break,
            commute_minutes=commute_minutes,
        )

    total_hours = stats['total_hours_per_month']
    hourly_wage = round(float(total_income) / total_hours, 2) if total_hours > 0 else 0
    stats['hourly_wage'] = hourly_wage
    return stats


def _formal_stats(rest_type, work_start, work_end, lunch_break, commute_minutes):
    """正式职业：月工作天数/日工作小时/月总投入小时"""
    # 月工作天数
    if rest_type == '双休':
        work_days = 21.75
    elif rest_type == '单休':
        work_days = 26
    elif rest_type == '大小周':
        work_days = 24
    else:  # 不休
        work_days = 30

    # 日工作小时（扣除午休）
    start_h, start_m = map(int, work_start.split(':'))
    end_h, end_m = map(int, work_end.split(':'))
    work_minutes = (end_h * 60 + end_m) - (start_h * 60 + start_m) - lunch_break
    work_hours = work_minutes / 60

    # 日通勤时间（往返）
    commute_hours = commute_minutes * 2 / 60

    # 月总投入小时 = 工作小时 + 通勤小时
    total_hours = work_days * (work_hours + commute_hours)

    return {
        'work_days_per_month': round(work_days, 1),
        'work_hours_per_day': round(work_hours, 1),
        'total_hours_per_month': round(total_hours, 1),
    }


def _freelance_stats(time_mode, days, hours_per_day, weekly_hours, weeks, commute_minutes):
    """自由职业：月工作天数/日工作小时/月总投入小时"""
    commute_hours_per_day = commute_minutes * 2 / 60

    if time_mode == 'flexible':
        # 弹性工时：每周各天工作时长 × 每月周数
        week_total = sum(h for h in weekly_hours if h)
        active_days = sum(1 for h in weekly_hours if h)  # 有工作的天数
        work_days = active_days * weeks
        work_hours_per_day = week_total / active_days if active_days > 0 else 0
        total_hours = week_total * weeks + commute_hours_per_day * work_days
    else:
        # 固定时长：月工作天数 × 日均工作时长
        d = days or 22
        h = float(hours_per_day or 8)
        work_days = d
        work_hours_per_day = h
        total_hours = d * h + commute_hours_per_day * d

    return {
        'work_days_per_month': round(work_days, 1),
        'work_hours_per_day': round(work_hours_per_day, 1),
        'total_hours_per_month': round(total_hours, 1),
    }


# ─── 身体健康自查评分 ──────────────────────────────

_SCORE_MAP = {
    'headache': {'无': 0, '轻度': 1, '中度': 2, '重度': 3},
    'dizzy': {'无': 0, '偶尔': 1, '频繁': 3},
    'hairloss': {'正常': 0, '偏多': 1, '成片脱落': 3},
    'memory': {'无变化': 0, '轻微减退': 1, '明显减退': 3},
    'vision': {'无': 0, '偶尔': 1, '持续': 2},
    'ear': {'无': 0, '偶尔': 1, '持续': 2},
    'ulcer': {'无': 0, '1-2次/月': 1, '≥3次/月': 2},
    'gum': {'无': 0, '偶尔': 1, '经常': 2},
    'allergy': {'无': 0, '季节性': 1, '常年': 2},
    'spots': {'无': 0, '有': 2},
    'rash': {'无': 0, '局部': 1, '全身': 3},
    'wound_healing': {'正常': 0, '变慢': 2},
    'joint': {'无': 0, '晨起僵硬': 1, '活动后加重': 2},
    'numbness': {'无': 0, '偶尔': 1, '频繁': 3},
    'muscle': {'无': 0, '轻微': 1, '影响活动': 2},
    'finger_flex': {'正常': 0, '晨起僵硬': 1, '持续僵硬': 2},
    'appetite': {'正常': 0, '增加': 1, '减退': 2},
    'bloating': {'无': 0, '偶尔': 1, '经常': 2},
    'abdominal_pain': {'无': 0, '隐痛': 1, '绞痛': 2, '烧灼感': 2},
    'reflux': {'无': 0, '偶尔': 1, '经常': 2},
    'stool_type': {'正常': 0, '干结': 1, '稀水': 1, '带血': 3},
    'urination_pain': {'无': 0, '有': 2},
    'morning_energy': {'恢复感好': 0, '一般': 1, '疲惫': 2},
    'snoring': {'无': 0, '轻微': 1, '响亮且不规律': 2},
    'fatigue': {'无': 0, '轻度': 1, '严重影响生活': 3},
    'mood': {'无': 0, '偶尔': 1, '持续>2周': 3},
    'afternoon_fatigue': {'无': 0, '偶尔': 1, '每天': 2},
    'interest_change': {'正常': 0, '对事物失去兴趣': 3},
}

_NUMERIC_RULES = {
    'sleep_latency': [(30, 0), (60, 1), (float('inf'), 2)],
    'awakenings': [(1, 0), (3, 1), (float('inf'), 2)],
    'nocturia': [(1, 0), (2, 1), (float('inf'), 2)],
    'stool_count': [(float('inf'), 0)],
}

_SYSTEM_GROUPS = {
    '头部': ['headache', 'dizzy', 'hairloss', 'memory'],
    '五官': ['vision', 'ear', 'ulcer', 'gum', 'allergy'],
    '皮肤': ['spots', 'rash', 'wound_healing'],
    '四肢/肌肉': ['joint', 'numbness', 'muscle', 'finger_flex'],
    '消化系统': ['appetite', 'bloating', 'abdominal_pain', 'reflux', 'stool_count', 'stool_type'],
    '泌尿系统': ['urination_pain', 'nocturia'],
    '睡眠': ['sleep_latency', 'awakenings', 'morning_energy', 'snoring'],
    '精力/情绪': ['fatigue', 'mood', 'afternoon_fatigue', 'interest_change'],
}

_FIELD_LABELS = {
    'headache': '头痛/偏头痛', 'dizzy': '头晕/眩晕', 'hairloss': '脱发', 'memory': '记忆力变化',
    'vision': '视力模糊/眼干', 'ear': '耳鸣/听力', 'ulcer': '口腔溃疡', 'gum': '牙龈出血',
    'allergy': '鼻塞/过敏', 'spots': '新发痣/斑', 'rash': '皮疹/瘙痒', 'wound_healing': '伤口愈合速度',
    'joint': '关节疼痛/僵硬', 'numbness': '手脚发麻', 'muscle': '肌肉酸痛', 'finger_flex': '手指灵活性',
    'appetite': '食欲', 'bloating': '腹胀/打嗝', 'abdominal_pain': '腹痛', 'reflux': '胃酸反流',
    'stool_count': '大便次数', 'stool_type': '大便性状',
    'urination_pain': '尿频/尿急/尿痛', 'nocturia': '夜尿次数',
    'sleep_latency': '入睡时间', 'awakenings': '夜间醒来次数', 'morning_energy': '晨起精力',
    'snoring': '打鼾', 'fatigue': '疲劳感', 'mood': '情绪低落/焦虑',
    'afternoon_fatigue': '午后犯困', 'interest_change': '兴趣变化',
}

_ALERT_THRESHOLD = 2


def _score_field(field: str, value) -> int:
    if value is None or value == '':
        return 0
    if field in _NUMERIC_RULES:
        for threshold, score in _NUMERIC_RULES[field]:
            try:
                if int(value) <= threshold:
                    return score
            except (ValueError, TypeError):
                return 0
        return _NUMERIC_RULES[field][-1][1]
    if field in _SCORE_MAP:
        return _SCORE_MAP[field].get(str(value), 0)
    return 0


def calculate_health_score(data: dict) -> int:
    """计算健康总分"""
    total = 0
    for fields in _SYSTEM_GROUPS.values():
        for field in fields:
            total += _score_field(field, data.get(field))
    return total


def collect_health_alerts(data: dict) -> list[str]:
    """汇总异常项，按身体区域归类"""
    alerts_by_system: dict[str, list[str]] = {}
    for system, fields in _SYSTEM_GROUPS.items():
        items = []
        for field in fields:
            if _score_field(field, data.get(field)) >= _ALERT_THRESHOLD:
                items.append(_FIELD_LABELS.get(field, field))
        if items:
            alerts_by_system[system] = items

    result = []
    for system, items in alerts_by_system.items():
        if len(items) <= 3:
            result.append(f'{system}（{"、".join(items)}）')
        else:
            result.append(f'{system}（{items[0]}等{len(items)}项）')
    return result


# ─── 用电记录 ────────────────────────────────────

MONTHS_WINDOW = 12          # 月度卡片窗口：最近 N 个自然月
PERT_MIN_SAMPLES = 3        # PERT 三点估算的最少样本月数（低于此不给数值）
_Q1 = Decimal('0.1')
_Q2 = Decimal('0.01')


def _q(value: Decimal, exp: Decimal) -> float:
    """量化成 float（派生值直接下发，前端按数字消费）"""
    return float(value.quantize(exp, rounding=ROUND_HALF_UP))


def _shift_month(key: tuple[int, int], delta: int) -> tuple[int, int]:
    """(year, month) 平移 delta 个月（delta 可负）"""
    idx = key[0] * 12 + (key[1] - 1) + delta
    return idx // 12, idx % 12 + 1


def build_monthly_usage(records) -> dict:
    """按自然月聚合，算每月的用电量（纯函数，不碰库）

    口径：**本月最后一条读数 − 上月最后一条读数**（电表读数法的标准做法，与电费单一致）。
    首月没有上月基准，退化为「本月初条读数」，并标记 `base_source='own_first'` 让人看得见。

    ⚠️ 不复用记录上的 `month_usage` 字段：那个字段在本月没有上月记录时会拿本月首条
    当基准，月初不是 1 号就会低估；两者语义不同，不能互相顶替。

    Returns:
        {(year, month): {usage, days, daily_avg, records,
                         base_date, base_source, end_date, single}}
        `usage=None` 表示**算不出**（该月只有一条记录，起止同点），不是 0。
    """
    by_month: dict[tuple[int, int], list] = defaultdict(list)
    for r in sorted(records, key=lambda x: (x.record_date, x.id or 0)):
        by_month[(r.record_date.year, r.record_date.month)].append(r)

    out: dict[tuple[int, int], dict] = {}
    prev_last = None
    for key in sorted(by_month):
        items = by_month[key]
        last = items[-1]
        if prev_last is None:
            base, base_source = items[0], 'own_first'
        else:
            base, base_source = prev_last, 'prev_month'

        entry = {
            'records': len(items),
            'base_date': base.record_date,
            'base_source': base_source,
            'end_date': last.record_date,
            'usage': None,
            'days': None,
            'daily_avg': None,
            'single': False,
        }
        if base.pk != last.pk:      # 起止同点 ⇒ 只有读数、没有用电量
            usage = Decimal(str(last.meter_reading)) - Decimal(str(base.meter_reading))
            days = (last.record_date - base.record_date).days
            entry['usage'] = _q(usage, _Q1)
            entry['days'] = days
            entry['daily_avg'] = _q(usage / days, _Q2) if days else None
        else:
            entry['single'] = True
        out[key] = entry
        prev_last = last
    return out


def pert_estimate(samples: list[float]) -> dict:
    """PERT 三点估算（纯函数）

    O/M/P 取历史样本的 **最小 / 中位数 / 最大**；
    期望值 `E = (O + 4M + P) / 6`，标准差 `σ = (P − O) / 6`。

    ⚠️ 这里算出的是**期望值**（加权平均），不是「最可能值」（那是 M 本身）——
    卡片上要标清楚，否则日后会被读成两种意思。

    样本不足 `PERT_MIN_SAMPLES` 时**一个数都不给**，只回进度与 issues：
    2 个点算出来的区间看着很窄，实际只是样本不够，给人「模型很自信」的错觉。
    """
    n = len(samples)
    res = {
        'samples': n, 'required': PERT_MIN_SAMPLES, 'ready': False,
        'optimistic': None, 'most_likely': None, 'pessimistic': None,
        'expected': None, 'sigma': None, 'low': None, 'high': None,
        'mean': None, 'issues': [],
    }
    if n:
        total = sum(Decimal(str(s)) for s in samples)
        res['mean'] = _q(total / n, _Q2)

    if n < PERT_MIN_SAMPLES:
        res['issues'].append(
            f'样本仅 {n} 个完整月，PERT 三点估算需 ≥{PERT_MIN_SAMPLES} 个')
        return res

    o, p = min(samples), max(samples)
    m = float(median(samples))
    e = (o + 4 * m + p) / 6
    sigma = (p - o) / 6
    res.update({
        'ready': True,
        'optimistic': _q(Decimal(str(o)), _Q1),
        'most_likely': _q(Decimal(str(m)), _Q1),
        'pessimistic': _q(Decimal(str(p)), _Q1),
        'expected': _q(Decimal(str(e)), _Q1),
        'sigma': _q(Decimal(str(sigma)), _Q2),
        'low': _q(Decimal(str(e - sigma)), _Q1),
        'high': _q(Decimal(str(e + sigma)), _Q1),
    })
    if o == p:
        res['issues'].append('样本各月用电量完全相同，区间宽度为 0 —— 这是样本无差异，不是真实波动小')
    return res


class ElectricityService:
    """用电记录计算"""

    @staticmethod
    def calculate_on_create(record: ElectricityRecord) -> None:
        """计算单条记录的间隔用电量/日均用电量/本月累计

        - 间隔用电量 = 本次读数 - 最近一次更早日期的读数（首条为 None）
        - 日均用电量 = 间隔用电量 ÷ 间隔天数（首条为 None）
        - 本月累计 = 本次读数 - 月初基准（优先取上月最后一条，无则取本月首条；本月首条为 0）
        """
        qs = ElectricityRecord.objects.filter(user_id=record.user_id)
        prev = qs.filter(record_date__lt=record.record_date).order_by('-record_date').first()

        month_start = record.record_date.replace(day=1)
        month_base = qs.filter(record_date__lt=month_start).order_by('-record_date').first()
        if month_base is None:
            month_base = qs.filter(record_date__gte=month_start).order_by('record_date').first()

        reading = Decimal(str(record.meter_reading))
        quantize_1dp = Decimal('0.1')

        if prev:
            prev_reading = Decimal(str(prev.meter_reading))
            interval_usage = (reading - prev_reading).quantize(quantize_1dp, rounding=ROUND_HALF_UP)
            interval_days = (record.record_date - prev.record_date).days
            daily_avg = (
                (interval_usage / interval_days).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                if interval_days > 0
                else Decimal('0.00')
            )
            record.interval_usage = interval_usage
            record.interval_days = interval_days
            record.daily_avg = daily_avg
        else:
            record.interval_usage = None
            record.interval_days = None
            record.daily_avg = None

        if month_base:
            record.month_usage = (reading - Decimal(str(month_base.meter_reading))).quantize(
                quantize_1dp, rounding=ROUND_HALF_UP
            )
        else:
            record.month_usage = Decimal('0')

        record.save()

    @staticmethod
    def recalculate_all(user_id: int = 1) -> None:
        """按日期顺序重算全部记录（删除记录后保证后续记录联动）"""
        for record in ElectricityRecord.objects.filter(user_id=user_id).order_by('record_date'):
            ElectricityService.calculate_on_create(record)

    @staticmethod
    def overview(user_id: int = 1, months: int = MONTHS_WINDOW, today=None) -> dict:
        """月度用电量序列 + PERT 估算 + 统计卡数据（**全部实时算，不落库**）

        - 窗口：最近 `months` 个自然月（含当月）；**无记录的月 `usage=None`，不是 0**
        - PERT 样本：窗口内**已结束**的月（排除进行中的当月）且用电量可算
        - `latest`：给统计卡用（最新读数 / 本月累计 / 日均 / 总记录数），
          与分页解耦 —— 历史表分页后前端拿不到全量，统计卡不能再从列表取

        判据：月度电量与 PERT 都是「以后重算得出同样结果」的派生值 ⇒ **不落库**。
        """
        today = today or timezone.localdate()
        cur = (today.year, today.month)
        records = list(ElectricityRecord.objects.filter(user_id=user_id))
        computed = build_monthly_usage(records)

        series, samples, excluded = [], [], []
        for i in range(months - 1, -1, -1):
            key = _shift_month(cur, -i)
            item = computed.get(key)
            row = {
                'month': f'{key[0]:04d}-{key[1]:02d}',
                'usage': None, 'days': None, 'daily_avg': None, 'records': 0,
                'base_date': None, 'base_source': None, 'end_date': None,
                'partial': key == cur, 'in_pert_sample': False,
            }
            if item:
                row.update({
                    'usage': item['usage'], 'days': item['days'],
                    'daily_avg': item['daily_avg'], 'records': item['records'],
                    'base_date': item['base_date'].isoformat(),
                    'base_source': item['base_source'],
                    'end_date': item['end_date'].isoformat(),
                })
            if item and item['usage'] is not None:
                if key < cur:
                    row['in_pert_sample'] = True
                    samples.append(item['usage'])
                else:
                    excluded.append(row['month'])
            series.append(row)

        pert = pert_estimate(samples)
        if excluded:
            pert['issues'].append(f'{excluded[-1]} 尚未结束，不计入样本')

        latest = None
        if records:
            rec = max(records, key=lambda r: (r.record_date, r.id or 0))
            latest = {
                'id': rec.id,
                'record_date': rec.record_date.isoformat(),
                'meter_reading': float(rec.meter_reading),
                'interval_usage': float(rec.interval_usage) if rec.interval_usage is not None else None,
                'interval_days': rec.interval_days,
                'daily_avg': float(rec.daily_avg) if rec.daily_avg is not None else None,
                'month_usage': float(rec.month_usage) if rec.month_usage is not None else None,
            }

        return {
            'months': series,
            'pert': pert,
            'latest': latest,
            'total_records': len(records),
        }


def resolve_quote_pool_max_len() -> int:
    """「每日金句」池的长度上限（读取用户在「系统设置」里的配置）。

    v3.60.12 之前这是 `QuoteViewSet` 上的一个硬编码常量（200），用户既看不见也改不了；
    现在改为 `UserProfile.quote_pool_max_len`，在系统设置里可调。

    ⚠️ 默认值**不在这里写第二份** —— 回落到 `UserProfile` 字段的 `default`，
    保证「模型定义」是唯一真源（改默认值只需改一处）。
    ⚠️ 用 `filter().first()` 而不是 `get_or_create`：本函数服务于**只读**接口，
    不该因为「读一次配置」就往库里插一行。
    ⚠️ 配到超大值时不做二次夹取：区间校验在序列化器那一层（`QUOTE_POOL_LEN_RANGE`），
    这里只负责把「当前生效值」取出来。
    """
    # 函数内导入：core 是上游 app，模块级导入会让 toolkit 的加载顺序变敏感
    from apps.core.models import UserProfile

    profile = UserProfile.objects.filter(user_id=1).only('quote_pool_max_len').first()
    if profile is not None:
        return profile.quote_pool_max_len
    return UserProfile._meta.get_field('quote_pool_max_len').default
