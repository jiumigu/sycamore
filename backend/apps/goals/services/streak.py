"""连续打卡计算（由 services.py 拆分）"""

from datetime import date, datetime, timedelta

def calculate_streak(completion_log: dict) -> dict:
    """计算打卡连续天数

    返回: {'current': int, 'longest': int, 'total': int}
    """
    from datetime import date, timedelta

    checked_dates = sorted(
        d for d, v in completion_log.items() if v
    )
    if not checked_dates:
        return {'current': 0, 'longest': 0, 'total': 0}

    # Current streak: count backward from today
    today = date.today()
    check = today
    current = 0
    while check.isoformat() in completion_log:
        current += 1
        check -= timedelta(days=1)
    # If today not checked, try from yesterday
    if current == 0:
        check = today - timedelta(days=1)
        while check.isoformat() in completion_log:
            current += 1
            check -= timedelta(days=1)

    # Longest streak
    longest = 0
    run = 1
    for i in range(1, len(checked_dates)):
        curr = date.fromisoformat(checked_dates[i])
        prev = date.fromisoformat(checked_dates[i - 1])
        if (curr - prev).days == 1:
            run += 1
        else:
            longest = max(longest, run)
            run = 1
    longest = max(longest, run)

    return {
        'current': current,
        'longest': longest,
        'total': len(checked_dates),
    }



