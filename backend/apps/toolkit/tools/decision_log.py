from .base import BaseTool


class DecisionLogTool(BaseTool):
    """决策日志工具"""

    tool_key = 'decision-log'
    name = '📋 决策日志'
    description = '记录重大决策，分析决策偏误，定期回顾复盘'
    icon = '📋'
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
            'output_text': '打开决策日志工具',
        }
