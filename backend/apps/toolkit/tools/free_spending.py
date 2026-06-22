from .base import BaseTool


class FreeSpendingTool(BaseTool):
    """自由支配额度计算器"""

    tool_key = 'free-spending'
    name = '💰 自由支配额度'
    description = '计算每次消费无需纠结的自由额度，减少日常消费内耗'
    icon = '💰'
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
            'output_text': '打开自由支配额度计算器',
        }
