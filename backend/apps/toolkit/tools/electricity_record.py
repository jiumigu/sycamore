from .base import BaseTool


class ElectricityTool(BaseTool):
    """用电记录"""

    tool_key = 'electricity-record'
    name = '⚡ 用电记录'
    description = '记录电表读数，自动计算间隔/日均/本月累计用电'
    icon = '⚡'
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
            'output_text': '打开用电记录',
        }
