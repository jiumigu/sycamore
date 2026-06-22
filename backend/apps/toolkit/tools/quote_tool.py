from .base import BaseTool


class QuoteTool(BaseTool):
    """摘录馆"""

    tool_key = 'quote-tool'
    name = '📖 摘录馆'
    description = '收录名言、典故、故事、好段，区分语言，支持随机回顾'
    icon = '📖'
    category = 'other'
    output_type = 'text'
    is_async = False

    def get_input_schema(self):
        return {
            'type': 'object',
            'properties': {},
            'required': [],
        }

    def execute(self, params, progress_callback=None):
        return {
            'success': True,
            'redirect': '/toolkit/quotes',
        }
