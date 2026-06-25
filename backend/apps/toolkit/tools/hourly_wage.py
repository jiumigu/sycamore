from .base import BaseTool


class HourlyWageTool(BaseTool):
    """时薪计算器"""

    tool_key = 'hourly-wage'
    name = '⏱️ 时薪计算器'
    description = '计算真实时薪，看清时间价值'
    icon = '⏱️'
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
            'output_text': '打开时薪计算器',
        }
