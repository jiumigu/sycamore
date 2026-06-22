from .base import BaseTool


class HealthSelfCheckTool(BaseTool):
    """身体健康自查工具"""

    tool_key = 'health-self-check'
    name = '🩺 身体健康自查'
    description = '8大系统31项指标，自动评分+趋势对比+异常汇总'
    icon = '🩺'
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
            'output_text': '打开身体健康自查页面进行评估',
        }
