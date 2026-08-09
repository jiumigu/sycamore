from .base import BaseTool


class FixedExpenseTool(BaseTool):
    """固定开销计算器"""

    tool_key = 'fixed-expense'
    name = '💰 固定开销计算器'
    description = '自定义开销项目，计算每月/每日固定开销'
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
            'output_text': '打开固定开销计算器',
        }
