from .base import BaseTool


class CareerEnergyAuditTool(BaseTool):
    """职业能量审计工具"""

    tool_key = 'career-energy-audit'
    name = '⚡ 职业能量审计'
    description = '26项细化指标，定期审计工作能量，用数据替代反复纠结'
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
            'output_text': '打开职业能量审计页面进行评估',
        }
