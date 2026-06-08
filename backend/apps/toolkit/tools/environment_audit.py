from .base import BaseTool


class EnvironmentAuditTool(BaseTool):
    """环境校准工具"""

    tool_key = 'environment-audit'
    name = '🧭 环境校准'
    description = '用六条特征给当前环境打分，判断是否在增值'
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
            'output_text': '打开环境校准页面进行评测',
        }
