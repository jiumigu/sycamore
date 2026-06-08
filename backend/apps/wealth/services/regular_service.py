"""定期存款 — 利息计算 + CRUD + 状态管理"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from django.db.models import Q, Sum

from ..models import WealthRegularList

FLAG_ONGOING = 0
FLAG_MATURED = 1
FLAG_WITHDRAWN = 2


def _add_year(d: date) -> date:
    """日期加一年（处理闰年边界）"""
    try:
        return d.replace(year=d.year + 1)
    except ValueError:
        # 闰年2月29日 → 平年2月28日
        return d.replace(year=d.year + 1, day=28)


def calculate_interest(
    value: float,
    rate: float,
    begin_date: date,
    end_date: date | None = None,
) -> float:
    """单利计算：本金 × 年利率 × (天数/365)"""
    if end_date is None:
        end_date = date.today()
    days = (end_date - begin_date).days
    if days <= 0:
        return 0.0
    return round(value * (rate / 100) * (days / 365), 2)


def calculate_maturity_amount(
    value: float,
    rate: float,
    begin_date: date,
    end_date: date,
) -> float:
    """到期本息合计"""
    interest = calculate_interest(value, rate, begin_date, end_date)
    return round(value + interest, 2)


def get_stats() -> dict:
    """定期存款统计概览"""
    today = date.today()

    all_qs = WealthRegularList.objects.all()
    active_qs = all_qs.exclude(flag=FLAG_WITHDRAWN)

    # 总额（排除已取出）
    total_value = active_qs.aggregate(s=Sum('value'))['s'] or 0
    total_interest = active_qs.aggregate(s=Sum('interest'))['s'] or 0

    # 按状态分组
    ongoing = all_qs.filter(flag=FLAG_ONGOING).aggregate(s=Sum('value'))['s'] or 0
    matured = all_qs.filter(flag=FLAG_MATURED).aggregate(s=Sum('value'))['s'] or 0
    withdrawn = all_qs.filter(flag=FLAG_WITHDRAWN).aggregate(s=Sum('value'))['s'] or 0

    # 到期提醒
    expiring_soon = all_qs.filter(
        flag=FLAG_ONGOING,
        end_date__gte=today,
        end_date__lte=today + timedelta(days=30),
    ).count()

    expired = all_qs.filter(flag=FLAG_ONGOING, end_date__lt=today).count()

    return {
        'total_value': round(total_value, 2),
        'total_interest': round(total_interest, 2),
        'ongoing_value': round(ongoing, 2),
        'matured_value': round(matured, 2),
        'withdrawn_value': round(withdrawn, 2),
        'ongoing_count': all_qs.filter(flag=FLAG_ONGOING).count(),
        'matured_count': all_qs.filter(flag=FLAG_MATURED).count(),
        'withdrawn_count': all_qs.filter(flag=FLAG_WITHDRAWN).count(),
        'expiring_soon_count': expiring_soon,
        'expired_count': expired,
    }


def get_regular_list(
    bankinfo: str | None = None,
    flag: int | None = None,
    keyword: str | None = None,
    ordering: str = 'end_date',
) -> list[WealthRegularList]:
    """查询定期存款列表（支持筛选）"""
    qs = WealthRegularList.objects.all()

    if bankinfo:
        qs = qs.filter(bankinfo=bankinfo)
    if flag is not None:
        qs = qs.filter(flag=flag)
    if keyword:
        qs = qs.filter(
            Q(bankinfo__icontains=keyword)
            | Q(remark__icontains=keyword)
        )

    return list(qs.order_by(ordering))


def get_regular_detail(pk: int) -> WealthRegularList | None:
    """获取单条定期存款"""
    try:
        return WealthRegularList.objects.get(pk=pk)
    except WealthRegularList.DoesNotExist:
        return None


def create_regular(data: dict) -> WealthRegularList:
    """新增定期存款"""
    obj = WealthRegularList(
        begin_date=data['begin_date'],
        end_date=data['end_date'],
        value=data['value'],
        rate=data.get('rate'),
        bankinfo=data.get('bankinfo', ''),
        remark=data.get('remark', ''),
        flag=data.get('flag', FLAG_ONGOING),
        user_id=data.get('user_id', 1),
    )
    # 自动计算利息
    if obj.rate and obj.value:
        obj.interest = calculate_interest(
            obj.value, obj.rate, obj.begin_date, obj.end_date,
        )
    else:
        obj.interest = data.get('interest', 0.0)
    obj.save()
    return obj


def update_regular(pk: int, data: dict) -> WealthRegularList | None:
    """更新定期存款"""
    obj = get_regular_detail(pk)
    if not obj:
        return None

    for field in ('begin_date', 'end_date', 'value', 'rate', 'bankinfo',
                  'remark', 'flag', 'interest', 'user_id'):
        if field in data:
            setattr(obj, field, data[field])

    # 重算利息
    if obj.rate and obj.value and obj.begin_date and obj.end_date:
        obj.interest = calculate_interest(
            obj.value, obj.rate, obj.begin_date, obj.end_date,
        )
    obj.save()
    return obj


def delete_regular(pk: int) -> bool:
    """删除定期存款"""
    obj = get_regular_detail(pk)
    if not obj:
        return False
    obj.delete()
    return True


def process_mature(pk: int, action: str, new_rate: float | None = None,
                   new_end_date: date | None = None) -> WealthRegularList | None:
    """到期处理

    action:
        withdraw — 取出（标记已取出）
        renew    — 本金续存，利息取出
        renew_all — 本息续存
    """
    obj = get_regular_detail(pk)
    if not obj:
        return None

    if action == 'withdraw':
        obj.flag = FLAG_WITHDRAWN
        obj.save()
        return obj

    if action == 'renew':
        # 利息取出，本金续存
        interest = obj.interest or 0
        principal = obj.value
    elif action == 'renew_all':
        # 本息一起续存
        interest = 0
        principal = (obj.value or 0) + (obj.interest or 0)
    else:
        return obj

    # 原记录标记已取出
    obj.flag = FLAG_WITHDRAWN
    obj.save()

    # 创建新记录
    new_obj = WealthRegularList(
        begin_date=obj.end_date,
        end_date=new_end_date or _add_year(obj.end_date),
        value=principal,
        rate=new_rate or obj.rate,
        bankinfo=obj.bankinfo,
        remark=f'{obj.remark or ""} (续存)',
        flag=FLAG_ONGOING,
        user_id=obj.user_id,
    )
    if new_obj.rate and new_obj.value:
        new_obj.interest = calculate_interest(
            new_obj.value, new_obj.rate, new_obj.begin_date, new_obj.end_date,
        )
    new_obj.save()
    return new_obj


def get_expiring_regulars(days: int = 30) -> list[WealthRegularList]:
    """获取即将到期的定期存款（指定天数内）"""
    today = date.today()
    end = today + timedelta(days=days)
    return list(
        WealthRegularList.objects.filter(
            flag=FLAG_ONGOING,
            end_date__gte=today,
            end_date__lte=end,
        ).order_by('end_date')
    )


def get_expired_regulars() -> list[WealthRegularList]:
    """获取已过期但未处理的定期存款"""
    return list(
        WealthRegularList.objects.filter(
            flag=FLAG_ONGOING,
            end_date__lt=date.today(),
        ).order_by('end_date')
    )


def update_all_status() -> int:
    """批量更新所有到期存款状态（未到期→已到期）"""
    today = date.today()
    updated = WealthRegularList.objects.filter(
        flag=FLAG_ONGOING,
        end_date__lt=today,
    ).update(flag=FLAG_MATURED)
    return updated


def get_available_banks() -> list[str]:
    """获取所有银行列表"""
    return list(
        WealthRegularList.objects.values_list('bankinfo', flat=True)
        .distinct()
        .order_by('bankinfo')
    )
