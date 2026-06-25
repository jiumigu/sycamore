"""工具箱业务逻辑"""

from .models import CareerEnergyAudit


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
):
    """计算实际时薪（含通勤时间）"""
    if calc_mode == 'freelance':
        return _calc_freelance(
            monthly_salary=monthly_salary,
            time_mode=freelance_time_mode,
            days=freelance_days,
            hours_per_day=freelance_hours_per_day,
            weekly_hours=weekly_hours or [],
            weeks=freelance_weeks,
            commute_minutes=commute_minutes,
        )

    # 正式职业：原有逻辑
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

    # 时薪 = 月薪 / 总投入小时
    hourly_wage = round(float(monthly_salary) / total_hours, 2) if total_hours > 0 else 0

    return {
        'work_days_per_month': round(work_days, 1),
        'work_hours_per_day': round(work_hours, 1),
        'total_hours_per_month': round(total_hours, 1),
        'hourly_wage': hourly_wage,
    }


def _calc_freelance(monthly_salary, time_mode, days, hours_per_day, weekly_hours, weeks, commute_minutes):
    """自由职业时薪计算"""
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

    hourly_wage = round(float(monthly_salary) / total_hours, 2) if total_hours > 0 else 0

    return {
        'work_days_per_month': round(work_days, 1),
        'work_hours_per_day': round(work_hours_per_day, 1),
        'total_hours_per_month': round(total_hours, 1),
        'hourly_wage': hourly_wage,
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
