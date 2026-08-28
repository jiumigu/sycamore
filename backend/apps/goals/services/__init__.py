"""goals 服务包（由 services.py 拆分，对外接口不变）"""

from .goal_clone import GoalCloneService
from .goal_progress import GoalProgressService
from .milestone_reward import MilestoneRewardService
from .quick_goal import QuickGoalService
from .streak import calculate_streak

__all__ = [
    'GoalCloneService',
    'GoalProgressService',
    'MilestoneRewardService',
    'QuickGoalService',
    'calculate_streak',
]
