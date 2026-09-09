from .base import BaseTool


class DecisionTrackerTool(BaseTool):
    """决策追踪器——长期观察型决策的日常记录与到期汇总"""

    tool_key = 'decision-tracker'
    name = '🧭 决策追踪器'
    description = '决策前长期观察：日常记录倾向与理由，到期自动汇总分析'
    icon = '🧭'
    category = 'other'
    output_type = 'text'

    def get_input_schema(self):
        return {
            'type': 'object',
            'properties': {},
        }

    def execute(self, params, progress_callback=None):
        return {
            'success': True,
            'output_text': '打开决策追踪器工具',
        }
