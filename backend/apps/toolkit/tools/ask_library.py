from .base import BaseTool


class AskLibraryTool(BaseTool):
    """AI 问答库——完整存档 AI 问答（问题/回答/AI 对象/会话背景），多 AI 对照与重复询问追溯"""

    tool_key = 'ask-library'
    name = '🤖 AI 问答库'
    description = '完整记录 AI 问答：问题原文 + 各 AI 回答 + 会话背景，可检索/打标/导出 md'
    icon = '🤖'
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
            'output_text': '打开 AI 问答库工具',
        }
