"""健康服务 — 体重管理（由 services.py 拆分）"""

import calendar
import math
from datetime import date, timedelta

from django.utils import timezone

from ..models import (
    UserBodyInfo,
    WeightGoal,
    WeightGoalAdjustment,
    WeightMilestone,
    WeightRecord,
)

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

