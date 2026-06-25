import calendar
import math
from datetime import date, datetime, timedelta

from django.db import connection, models
from django.db.models.functions import Cast
from django.utils import timezone

from .constants import (
    CONVERSION_RATES,
    HEALTH_MILESTONE_SIZE,
    HEALTH_TARGET_STEPS,
    HEALTH_TOTAL_MILESTONES,
    HTYPE_LABELS,
)
from .models import HealthRecord, WeightGoal, WeightGoalAdjustment, WeightMilestone, WeightRecord, UserBodyInfo


class HealthStatsService:
    """健康统计服务（1亿步目标）"""

    @staticmethod
    def get_summary() -> dict:
        qs = HealthRecord.objects.all()
        total_steps = qs.aggregate(s=models.Sum('total'))['s'] or 0

        if total_steps == 0:
            return {
                'total_steps': 0, 'target_steps': HEALTH_TARGET_STEPS,
                'progress_percent': 0, 'completed_milestones': 0,
                'total_milestones': HEALTH_TOTAL_MILESTONES,
                'next_milestone_distance': HEALTH_MILESTONE_SIZE,
                'daily_avg': 0, 'days_active': 0, 'max_daily': 0,
                'longest_streak': 0, 'this_month_steps': 0,
                'prediction': None,
                'current_milestone': {
                    'number': 1, 'start': 0, 'end': HEALTH_MILESTONE_SIZE,
                    'current': 0, 'remaining': HEALTH_MILESTONE_SIZE,
                    'progress_in_milestone': 0,
                },
            }

        total_steps = float(total_steps)
        progress_percent = round(total_steps / HEALTH_TARGET_STEPS * 100, 2)

        completed = int(total_steps // HEALTH_MILESTONE_SIZE)
        current_milestone_num = min(completed + 1, HEALTH_TOTAL_MILESTONES)
        in_milestone = float(total_steps % HEALTH_MILESTONE_SIZE)
        next_remaining = HEALTH_MILESTONE_SIZE - in_milestone

        days_active = HealthStatsService._count_active_days()
        max_daily = float(qs.aggregate(m=models.Max('total'))['m'] or 0)

        # 日均步数
        if days_active > 0:
            daily_avg = round(total_steps / days_active, 0)
        else:
            daily_avg = 0

        # 最长连续运动天数
        longest_streak = HealthStatsService._calc_longest_streak()

        # 本月步数
        now = timezone.now()
        this_month_steps = HealthStatsService._get_month_steps(now.year, now.month)

        prediction = HealthStatsService._calc_prediction(total_steps, daily_avg)

        return {
            'total_steps': total_steps,
            'target_steps': HEALTH_TARGET_STEPS,
            'progress_percent': progress_percent,
            'completed_milestones': completed,
            'total_milestones': HEALTH_TOTAL_MILESTONES,
            'next_milestone_distance': next_remaining,
            'daily_avg': daily_avg,
            'days_active': days_active,
            'max_daily': max_daily,
            'longest_streak': longest_streak,
            'this_month_steps': this_month_steps,
            'current_milestone': {
                'number': current_milestone_num,
                'start': completed * HEALTH_MILESTONE_SIZE,
                'end': current_milestone_num * HEALTH_MILESTONE_SIZE,
                'current': total_steps,
                'remaining': next_remaining,
                'progress_in_milestone': round(
                    in_milestone / HEALTH_MILESTONE_SIZE * 100, 2
                ),
            },
            'prediction': prediction,
        }

    @staticmethod
    def get_milestones() -> list:
        """获取50个里程碑完成状态"""
        total_steps = float(
            HealthRecord.objects.all().aggregate(s=models.Sum('total'))['s'] or 0
        )
        completed = int(total_steps // HEALTH_MILESTONE_SIZE)

        # 获取里程碑达成日期（每天累计步数 ≥ milestone 阈值的最小日期）
        milestone_dates = HealthStatsService._calc_milestone_dates(completed)

        result = []
        for i in range(1, HEALTH_TOTAL_MILESTONES + 1):
            start = (i - 1) * HEALTH_MILESTONE_SIZE
            end = i * HEALTH_MILESTONE_SIZE
            is_completed = i <= completed
            is_current = i == completed + 1 or (i == completed and completed == HEALTH_TOTAL_MILESTONES)

            entry = {
                'number': i,
                'start': start,
                'end': end,
                'is_completed': is_completed,
                'is_current': is_current,
            }

            if is_completed and i in milestone_dates:
                entry['completed_date'] = milestone_dates[i]['date']
                entry['days_taken'] = milestone_dates[i]['days_taken']

            if is_current and not is_completed:
                entry['current_progress'] = float(total_steps % HEALTH_MILESTONE_SIZE)
                entry['progress_percent'] = round(
                    (total_steps - start) / HEALTH_MILESTONE_SIZE * 100, 2
                )

            result.append(entry)

        return {'milestones': result, 'total_steps': total_steps}

    @staticmethod
    def get_daily_trend(days: int = 30) -> list:
        """获取每日步数趋势"""
        cursor = connection.cursor()
        cursor.execute("""
            SELECT DATE(time) as date, SUM(total) as total_steps, COUNT(hid) as record_count
            FROM health_step_info
            GROUP BY DATE(time)
            ORDER BY date ASC
        """)
        rows = cursor.fetchall()

        data = {r[0]: {'total_steps': float(r[1] or 0), 'record_count': r[2]} for r in rows}

        end = timezone.now()
        start = end - timedelta(days=days)
        result = []
        for i in range(days + 1):
            day = (start + timedelta(days=i)).date()
            entry = data.get(day, {'total_steps': 0, 'record_count': 0})
            result.append({
                'date': day.isoformat(),
                'total_steps': entry['total_steps'],
                'record_count': entry['record_count'],
            })

        return result

    @staticmethod
    def get_calendar(year: int | None = None, month: int | None = None) -> list:
        """获取日历热力图数据"""
        cursor = connection.cursor()
        sql = "SELECT DATE(time) as date, SUM(total) as total_steps, COUNT(hid) as record_count FROM health_step_info"
        params: list = []
        conditions = []
        if year:
            conditions.append("YEAR(time) = %s")
            params.append(year)
        if month:
            conditions.append("MONTH(time) = %s")
            params.append(month)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " GROUP BY DATE(time) ORDER BY date ASC"

        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return [
            {
                'date': r[0].isoformat() if hasattr(r[0], 'isoformat') else str(r[0]),
                'total_steps': float(r[1] or 0),
                'record_count': r[2],
            }
            for r in rows
        ]

    @staticmethod
    def get_milestone_timeline() -> list:
        """获取里程碑达成时间线"""
        total_steps = float(
            HealthRecord.objects.all().aggregate(s=models.Sum('total'))['s'] or 0
        )
        completed = int(total_steps // HEALTH_MILESTONE_SIZE)
        milestone_dates = HealthStatsService._calc_milestone_dates(completed)

        result = []
        for i in range(1, completed + 1):
            info = milestone_dates.get(i, {})
            prev_date = milestone_dates.get(i - 1, {}).get('date')
            prev_date_obj = datetime.strptime(prev_date, '%Y-%m-%d').date() if prev_date else None

            entry = {
                'number': i,
                'start': (i - 1) * HEALTH_MILESTONE_SIZE,
                'end': i * HEALTH_MILESTONE_SIZE,
                'completed_date': info.get('date', ''),
                'days_taken': info.get('days_taken', 0),
            }

            if prev_date_obj and info.get('date'):
                cur = datetime.strptime(info['date'], '%Y-%m-%d').date()
                entry['days_since_previous'] = (cur - prev_date_obj).days
            else:
                entry['days_since_previous'] = None

            result.append(entry)

        return result

    @staticmethod
    def get_type_stats() -> list:
        """获取运动类型占比统计"""
        qs = HealthRecord.objects.values('htype').annotate(
            total_steps=models.Sum('total'),
            count=models.Count('hid'),
        ).order_by('-total_steps')

        grand_total = float(
            HealthRecord.objects.all().aggregate(s=models.Sum('total'))['s'] or 1
        )

        return [
            {
                'htype': t['htype'],
                'label': HTYPE_LABELS.get(t['htype'], '未知'),
                'total_steps': float(t['total_steps'] or 0),
                'count': t['count'],
                'percentage': round(float(t['total_steps'] or 0) / grand_total * 100, 2),
            }
            for t in qs if t['htype']
        ]

    @staticmethod
    def get_yearly_comparison() -> list:
        """获取年度步数对比"""
        qs = HealthRecord.objects.values('years').annotate(
            total_steps=models.Sum('total'),
            count=models.Count('hid'),
            avg_daily=models.Avg('total'),
        ).order_by('-years')

        return [
            {
                'year': t['years'],
                'total_steps': float(t['total_steps'] or 0),
                'count': t['count'],
                'avg_daily': round(float(t['avg_daily'] or 0), 0),
            }
            for t in qs if t['years']
        ]

    # ─── 内部辅助方法 ───

    @staticmethod
    def _count_active_days() -> int:
        """统计有运动记录的天数"""
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(DISTINCT DATE(time)) FROM health_step_info")
        return cursor.fetchone()[0] or 0

    @staticmethod
    def _get_month_steps(year: int, month: int) -> float:
        """获取指定月份的总步数"""
        cursor = connection.cursor()
        cursor.execute(
            "SELECT COALESCE(SUM(total), 0) FROM health_step_info WHERE YEAR(time) = %s AND MONTH(time) = %s",
            [year, month],
        )
        return float(cursor.fetchone()[0])

    @staticmethod
    def _calc_longest_streak() -> int:
        """计算最长连续运动天数"""
        cursor = connection.cursor()
        cursor.execute("SELECT DISTINCT DATE(time) FROM health_step_info ORDER BY DATE(time) ASC")
        dates = [r[0] for r in cursor.fetchall()]

        if not dates:
            return 0

        max_streak = 1
        current_streak = 1
        prev = dates[0]

        for d in dates[1:]:
            if (d - prev).days == 1:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            elif (d - prev).days > 1:
                current_streak = 1
            prev = d

        return max_streak

    @staticmethod
    def _calc_prediction(total_steps: float, daily_avg: float) -> dict | None:
        """计算目标预测"""
        if daily_avg <= 0:
            return None

        remaining = HEALTH_TARGET_STEPS - total_steps
        days_needed = remaining / daily_avg
        target_date = timezone.now() + timedelta(days=int(days_needed))

        return {
            'target_date': target_date.strftime('%Y-%m-%d'),
            'days_remaining': int(days_needed),
            'daily_needed': round(daily_avg, 0),
        }

    @staticmethod
    def _calc_milestone_dates(completed: int) -> dict:
        """计算各里程碑达成日期"""
        cursor = connection.cursor()
        cursor.execute("""
            SELECT DATE(time) as date, SUM(total) as daily
            FROM health_step_info
            GROUP BY DATE(time)
            ORDER BY date ASC
        """)
        rows = cursor.fetchall()

        milestone_dates = {}
        cumulative = 0.0
        prev_milestone = 0
        first_date = None

        for date, daily_total in rows:
            daily = float(daily_total or 0)
            if first_date is None:
                first_date = date

            cumulative += daily

            current_milestone = int(cumulative // HEALTH_MILESTONE_SIZE)
            for m in range(prev_milestone + 1, current_milestone + 1):
                if m > completed:
                    break
                milestone_dates[m] = {
                    'date': date.isoformat(),
                    'days_taken': (date - first_date).days if first_date else 0,
                }
            prev_milestone = current_milestone

        return milestone_dates

    @staticmethod
    def _calc_total_steps_years() -> dict:
        """计算每年的总步数（按月统计结果）"""
        qs = HealthRecord.objects.values('years').annotate(
            total_steps=models.Sum('total'),
            count=models.Count('hid'),
        ).order_by('years')

        result = {}
        for entry in qs:
            if entry['years']:
                result[entry['years']] = {
                    'total_steps': float(entry['total_steps'] or 0),
                    'count': entry['count'],
                }
        return result


class WeightService:
    """体重管理业务逻辑"""

    @staticmethod
    def get_stats(user_id: int = 1) -> dict:
        """获取体重统计概览"""
        latest = WeightRecord.objects.filter(user_id=user_id).order_by('-record_date').first()
        goal = WeightGoal.objects.filter(user_id=user_id, is_active=True).first()
        body_info = UserBodyInfo.objects.filter(user_id=user_id).first()

        result = {
            'current_weight_kg': None,
            'current_weight_jin': None,
            'target_weight_kg': None,
            'target_weight_jin': None,
            'total_lost_kg': None,
            'total_lost_jin': None,
            'remaining_kg': None,
            'remaining_jin': None,
            'overall_progress': 0,
            'monthly_lost_kg': None,
            'monthly_lost_jin': None,
            'monthly_target_kg': None,
            'monthly_progress': 0,
            'bmi': None,
            'bmi_status': None,
            'remaining_days': 0,
        }

        if latest:
            current_kg = float(latest.weight_kg)
            result['current_weight_kg'] = current_kg
            result['current_weight_jin'] = round(current_kg * 2, 1)

        if body_info:
            if latest:
                hm = float(body_info.height_m)
                if hm > 0:
                    bmi = round(current_kg / (hm ** 2), 2)
                    result['bmi'] = bmi
                    if bmi < 18.5:
                        result['bmi_status'] = '偏瘦'
                    elif bmi < 24:
                        result['bmi_status'] = '正常'
                    elif bmi < 28:
                        result['bmi_status'] = '超重'
                    else:
                        result['bmi_status'] = '肥胖'

        if goal:
            start = float(goal.start_weight_kg)
            target = float(goal.target_weight_kg)
            total_to_lose = start - target

            result['target_weight_kg'] = target
            result['target_weight_jin'] = round(target * 2, 1)

            if latest:
                current_kg = float(latest.weight_kg)
                lost = start - current_kg
                remaining = current_kg - target
                result['total_lost_kg'] = round(lost, 2)
                result['total_lost_jin'] = round(lost * 2, 1)
                result['remaining_kg'] = round(remaining, 2)
                result['remaining_jin'] = round(remaining * 2, 1)
                if total_to_lose > 0:
                    result['overall_progress'] = round(min(lost / total_to_lose * 100, 100), 1)

            # 月度进度
            month_start = goal.current_month_start_weight
            monthly_target = goal.monthly_target_kg
            if month_start and monthly_target and latest:
                month_start_kg = float(month_start)
                monthly_target_kg = float(monthly_target)
                monthly_lost = month_start_kg - float(latest.weight_kg)
                result['monthly_lost_kg'] = round(monthly_lost, 2)
                result['monthly_lost_jin'] = round(monthly_lost * 2, 1)
                result['monthly_target_kg'] = monthly_target_kg
                if monthly_target_kg > 0:
                    result['monthly_progress'] = round(min(monthly_lost / monthly_target_kg * 100, 100), 1)

            # 本月剩余天数
            today = date.today()
            _, last_day = calendar.monthrange(today.year, today.month)
            result['remaining_days'] = last_day - today.day

        return result

    @staticmethod
    def get_trend(user_id: int = 1) -> dict:
        """获取体重趋势数据"""
        records = WeightRecord.objects.filter(user_id=user_id).order_by('record_date')
        goal = WeightGoal.objects.filter(user_id=user_id, is_active=True).first()

        record_data = [
            {
                'date': r.record_date.isoformat(),
                'weight_kg': float(r.weight_kg),
                'weight_jin': r.weight_jin,
                'body_fat': float(r.body_fat) if r.body_fat else None,
            }
            for r in records
        ]

        milestone_data = []
        if goal:
            milestones = WeightMilestone.objects.filter(goal=goal).order_by('month_number')
            milestone_data = [
                {
                    'month': m.month_number,
                    'target_weight_kg': float(m.target_weight_kg),
                    'start_weight_kg': float(m.start_weight_kg),
                    'end_weight_kg': float(m.end_weight_kg) if m.end_weight_kg else None,
                    'is_achieved': m.is_achieved,
                }
                for m in milestones
            ]

        return {
            'records': record_data,
            'milestones': milestone_data,
            'target_weight_kg': float(goal.target_weight_kg) if goal else None,
        }

    @staticmethod
    def get_or_create_body_info(user_id: int = 1, **kwargs) -> tuple:
        """获取或创建身体信息"""
        return UserBodyInfo.objects.get_or_create(
            user_id=user_id,
            defaults=kwargs,
        )

    @staticmethod
    def create_goal(user_id: int = 1, **data) -> WeightGoal:
        """创建减重目标并生成月度里程碑，检测目标变更并记录调整"""
        # 读取旧目标（用于调整记录）
        old_goal = WeightGoal.objects.filter(user_id=user_id, is_active=True).first()
        old_target_jin = round(float(old_goal.target_weight_kg) * 2, 1) if old_goal else None

        # 清理旧的活跃目标
        WeightGoal.objects.filter(user_id=user_id, is_active=True).update(is_active=False)

        start_kg = float(data['start_weight_kg'])
        target_kg = float(data['target_weight_kg'])
        monthly_kg = float(data.get('monthly_target_kg', 1.5))
        start_date = data.get('start_date', date.today())

        import math
        total_to_lose = start_kg - target_kg
        total_months = max(1, math.ceil(total_to_lose / monthly_kg))

        # 最后一个月自动调整
        remaining = total_to_lose - (total_months - 1) * monthly_kg

        # 预计达成日期
        end_month = start_date.month + total_months
        end_year = start_date.year + (end_month - 1) // 12
        end_month = ((end_month - 1) % 12) + 1
        _, last_day = calendar.monthrange(end_year, end_month)
        try:
            expected_end = date(end_year, end_month, min(last_day, 28))
        except ValueError:
            expected_end = start_date + timedelta(days=total_months * 30)

        goal = WeightGoal.objects.create(
            user_id=user_id,
            target_weight_kg=target_kg,
            start_weight_kg=start_kg,
            monthly_target_kg=monthly_kg,
            start_date=start_date,
            expected_end_date=expected_end,
            current_month=1,
            current_month_start_weight=start_kg,
            current_month_target=round(start_kg - monthly_kg, 2),
            is_active=True,
        )

        # 创建月度里程碑
        current_start = start_kg
        for m in range(1, total_months + 1):
            month_target = remaining if m == total_months else monthly_kg
            target = round(current_start - month_target, 2)
            WeightMilestone.objects.create(
                goal=goal,
                month_number=m,
                start_weight_kg=round(current_start, 2),
                target_weight_kg=target,
            )
            current_start = target

        # 记录目标调整（如果有旧目标且值不同）
        new_target_jin = round(target_kg * 2, 1)
        if old_target_jin is not None and old_target_jin != new_target_jin:
            WeightGoalAdjustment.objects.create(
                user_id=user_id,
                goal=goal,
                before_value=old_target_jin,
                after_value=new_target_jin,
                change_amount=round(new_target_jin - old_target_jin, 1),
                reason=data.get('adjust_reason', ''),
            )

        return goal

    @staticmethod
    def check_weight_goal_status(goal) -> str:
        """检查体重目标是否达成，自动更新里程碑和总目标状态。"""
        if goal.status != 'in_progress':
            return goal.status

        latest = WeightRecord.objects.filter(user_id=goal.user_id).order_by('-record_date').first()
        if not latest:
            return goal.status

        current = latest.weight_kg
        target = goal.target_weight_kg
        start = goal.start_weight_kg

        # 0. 如果当前里程碑已达成但 current_month 未推进（旧数据修复），自动推进到下一个未达成的月份
        current_ms = WeightMilestone.objects.filter(
            goal=goal, month_number=goal.current_month,
        ).first()
        if current_ms and current_ms.is_achieved:
            next_unachieved = WeightMilestone.objects.filter(
                goal=goal, month_number__gt=goal.current_month, is_achieved=False,
            ).order_by('month_number').first()
            if next_unachieved:
                goal.current_month = next_unachieved.month_number
                goal.current_month_start_weight = next_unachieved.start_weight_kg
                goal.current_month_target = next_unachieved.target_weight_kg
                goal.save(update_fields=['current_month', 'current_month_start_weight', 'current_month_target'])

        # 1. 检查当月里程碑
        month_milestone = WeightMilestone.objects.filter(
            goal=goal, month_number=goal.current_month, is_achieved=False,
        ).first()
        if month_milestone:
            achieved = False
            if start > target and current <= month_milestone.target_weight_kg:
                achieved = True
            elif start < target and current >= month_milestone.target_weight_kg:
                achieved = True
            if achieved:
                month_milestone.is_achieved = True
                month_milestone.end_weight_kg = current
                month_milestone.achieved_at = latest.record_date
                month_milestone.save()

                # 推进到下一个月
                next_start = month_milestone.target_weight_kg
                monthly_kg = float(goal.monthly_target_kg)
                goal.current_month += 1
                goal.current_month_start_weight = next_start
                goal.current_month_target = round(next_start - monthly_kg, 2)
                goal.save(update_fields=['current_month', 'current_month_start_weight', 'current_month_target'])

                # 月度达成后检查总目标
                if (start > target and current <= target) or (start < target and current >= target):
                    goal.status = 'completed'
                    goal.completed_at = timezone.now()
                    goal.save()
                    return 'completed'

        return goal.status
