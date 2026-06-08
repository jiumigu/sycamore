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
