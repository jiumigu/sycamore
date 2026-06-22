from .base import BaseTool


class ReviewToolboxTool(BaseTool):
    """复盘工具箱"""

    tool_key = 'review-toolbox'
    name = '📋 复盘工具箱'
    description = '每日/周/月/季度/人生复盘模板，让反思有迹可循'
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
            'output_text': '打开复盘工具箱',
        }
