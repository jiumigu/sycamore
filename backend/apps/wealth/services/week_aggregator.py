"""账单按周聚合服务"""
from collections import defaultdict
from datetime import date

from django.db.models import Sum, Q
from django.utils.timezone import make_aware

from apps.wealth.constants import (
    START_AGE, END_AGE, WEEKS_PER_YEAR, TOTAL_WEEKS,
    WINDOW_START_INDEX, WINDOW_END_INDEX,
    age_week_to_global_index,
)
from apps.wealth.models import WealthLifeWeekCalendar


def get_user_birth_date(user_id: int) -> date:
    """获取用户出生日期。目前从周历表反推。"""
    first_week = WealthLifeWeekCalendar.objects.filter(
        user_id=user_id, global_week_index=0
    ).first()
    if first_week:
        # 18岁第1周的起始日期减18年 ≈ 出生日期
        birth_date_approx = date(
            first_week.week_start_date.year - 18,
            first_week.week_start_date.month,
            first_week.week_start_date.day,
        )
        return birth_date_approx
    from django.conf import settings
    birth_str = getattr(settings, 'WEALTH_BIRTH_DATE', '1995-01-01')
    return date.fromisoformat(birth_str)  # 从 settings 读取


def date_to_week_index(tx_date: date, birth_date: date) -> int | None:
    """
    将具体日期映射到 18-78 岁范围内的全局周索引。
    如果日期对应年龄 < 18 或 > 78，返回 None。
    """
    age = tx_date.year - birth_date.year
    # 调整：如果今年生日还没到，age - 1
    birthday_this_year = date(tx_date.year, birth_date.month, birth_date.day)
    if tx_date < birthday_this_year:
        age -= 1

    if age < START_AGE or age > END_AGE:
        return None

    # 计算是该年龄的第几周
    year_start = date(tx_date.year, 1, 1)
    # 对齐到周一
    monday = tx_date - __import__('datetime').timedelta(days=tx_date.weekday())
    days_since_year_start = (monday - year_start).days
    week_num = days_since_year_start // 7 + 1
    if week_num > WEEKS_PER_YEAR:
        week_num = WEEKS_PER_YEAR

    return age_week_to_global_index(age, week_num)


# ──────────────────────────────────────────────────────────────
# 「现在处在第几岁第几周」—— 全项目唯一真源是**周历表**
#
# 🔴 为什么必须读表、不能按出生日期现算（v3.60.15 修的 31/32 岁断层）：
#   周历表是这套体系的**索引真源**：`global_week_index` 由它定义，
#   账单按周聚合、热力图着色、推演起点全都按它对位。而它有两处写法
#   与「生日现算」**天然不同**：
#     ① `age_year = 日历年份 − 出生年`（`week=出生年+age`，见 calendar_init），
#        即「那一年里你几岁」是按**年**编的，不随生日当天翻页；
#     ② `week_number` 以**当年第一个周一**为第 1 周，而 `date.isocalendar()[1]`
#        是 ISO 周 —— 只要 1 月 1 日不是周一，两者就差 1 周。
#   于是「生日 + ISO 周」现算出来的位置会与表错开，最坏整整一年。
#   2026-10-09 的现场：表说今天在 (31,40)=索引 715（最后一格彩色），
#   现算说在 (32,41)=索引 768 ⇒ 中间 52 周既非「已度过」也不在推演
#   覆盖范围内，热力图在 31/32 岁之间撕出一条 52 周的对角缺口。
#
#   ⇒ 判据：**「现在」是一个事实，不是一个可以各自推算的派生值。**
#     凡「按出生日期现算当前位置」的写法一律不得进入渲染链路。
# ──────────────────────────────────────────────────────────────

# 「现在」的来源标识 —— 界面据此说明这个位置是怎么来的（回落必须显式告知）
CURRENT_AGE_WEEK_SOURCE_CALENDAR = 'calendar'
CURRENT_AGE_WEEK_SOURCE_BIRTHDATE = 'birthdate'
CURRENT_AGE_WEEK_SOURCE_LABELS = {
    CURRENT_AGE_WEEK_SOURCE_CALENDAR: '周历表（含今天的那一周）',
    CURRENT_AGE_WEEK_SOURCE_BIRTHDATE: '按出生日期估算（周历尚未初始化）',
}


def _age_week_from_birth_date(today: date | None = None) -> tuple[int, int]:
    """按出生日期现算「几岁第几周」—— **仅为回落路径**，不是真源。

    只在周历表没有已度过行时使用（例如刚装好还没跑 `init_week_calendar`）。
    返回值一律夹到合法区间，避免界面拿到 0 岁或第 53 周这类越界值 ——
    越界值会让推演索引算到窗口之外，且**不报错**。
    """
    from django.conf import settings

    birth_str = getattr(settings, 'WEALTH_BIRTH_DATE', '1995-01-01')
    birth = date.fromisoformat(birth_str)
    today = today or date.today()

    age = today.year - birth.year
    if (today.month, today.day) < (birth.month, birth.day):
        age -= 1
    age = min(max(age, START_AGE), END_AGE)
    week = min(max(today.isocalendar()[1], 1), WEEKS_PER_YEAR)
    return age, week


def current_age_week(user_id: int = 1) -> dict:
    """「现在处在第几岁第几周」—— 读周历表，不按出生日期现算（理由见上）。

    口径与 `/wealth/summary/` 的 `lived_weeks` **同源**：都数窗口内 `is_lived`
    的行，**含本周**（本周是你正在度过的一周，热力图也把它着色）。
    同页这两个数字必须相等，否则推演面板的进度条与页头会各说各话。

    返回:
        current_age / current_week   —— 含今天那一行的 (age_year, week_number)
        global_week_index            —— 同一行的全局索引，供调用方直接对位
        lived_weeks                  —— 窗口（19–60 岁）内已度过周数
        source                       —— 'calendar' / 'birthdate'（回落）
        birth_date                   —— 表反推出的出生日期（回落时取 settings）
    """
    from apps.wealth.services.calendar_init import update_lived_status

    # 先把今天及之前的周标记为已度过：本函数可能在 /calendar/ 之前被调用
    # （推演面板 onMounted 就调它），不刷新会拿到上一次的边界。
    update_lived_status()

    row = (
        WealthLifeWeekCalendar.objects
        .filter(user_id=user_id, is_lived=True)
        .order_by('-global_week_index')
        .first()
    )

    if row is None:
        age, week = _age_week_from_birth_date()
        from django.conf import settings
        return {
            'current_age': age,
            'current_week': week,
            'global_week_index': age_week_to_global_index(age, week),
            'lived_weeks': 0,
            'source': CURRENT_AGE_WEEK_SOURCE_BIRTHDATE,
            'birth_date': getattr(settings, 'WEALTH_BIRTH_DATE', ''),
        }

    lived_weeks = WealthLifeWeekCalendar.objects.filter(
        user_id=user_id,
        is_lived=True,
        global_week_index__gte=WINDOW_START_INDEX,
        global_week_index__lte=WINDOW_END_INDEX,
    ).count()

    return {
        'current_age': row.age_year,
        'current_week': row.week_number,
        'global_week_index': row.global_week_index,
        'lived_weeks': lived_weeks,
        'source': CURRENT_AGE_WEEK_SOURCE_CALENDAR,
        'birth_date': get_user_birth_date(user_id).isoformat(),
    }


def aggregate_weekly_net_income(user_id: int) -> dict[int, dict]:
    """
    将 wealth_bill_list 中的交易记录按周聚合。
    返回: { global_week_index: { 'income': float, 'expense': float, 'net': float } }
    """
    from apps.wealth.models import WealthLifeWeekCalendar

    # 获取已度过的周
    lived_weeks = WealthLifeWeekCalendar.objects.filter(
        user_id=user_id, is_lived=True
    ).values('global_week_index', 'week_start_date', 'week_end_date')

    # 从 bill_list 按周聚合
    from django.db import connection

    result = {}

    for week in lived_weeks:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    COALESCE(SUM(CASE WHEN transaction_type = '收入' THEN amount ELSE 0 END), 0) as income,
                    COALESCE(SUM(CASE WHEN transaction_type = '支出' THEN amount ELSE 0 END), 0) as expense
                FROM wealth_bill_list
                WHERE user_id = %s
                  AND date >= %s AND date < %s
            """, [user_id, week['week_start_date'], week['week_end_date'] + __import__('datetime').timedelta(days=1)])

            row = cursor.fetchone()
            income = float(row[0])
            expense = float(row[1])
            net = income - expense

            result[week['global_week_index']] = {
                'income': round(income, 2),
                'expense': round(expense, 2),
                'net': round(net, 2),
            }

    return result


def get_net_level(net: float) -> str:
    """净收入 → 颜色分级标识"""
    if net > 1500:
        return 'surplus_high'
    elif net > 500:
        return 'surplus_mid'
    elif net > 0:
        return 'surplus_low'
    elif net == 0:
        return 'zero'
    elif net >= -500:
        return 'deficit_low'
    elif net >= -1500:
        return 'deficit_mid'
    else:
        return 'deficit_high'
