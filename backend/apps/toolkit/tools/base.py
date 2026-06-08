from pathlib import Path

from django.conf import settings


class BaseTool:
    """工具基类——所有工具需继承此类"""

    tool_key = None
    name = None
    description = None
    icon = '🔧'
    category = 'other'
    is_async = True

    def get_input_schema(self):
        """返回输入参数的 JSON Schema"""
        raise NotImplementedError

    def execute(self, params, progress_callback=None):
        """执行工具逻辑"""
        raise NotImplementedError

    def get_temp_path(self, ext):
        """获取临时文件路径"""
        import os
        import uuid

        temp_dir = Path(settings.MEDIA_ROOT) / 'toolkit_temp'
        temp_dir.mkdir(parents=True, exist_ok=True)
        return str(temp_dir / f'{uuid.uuid4().hex}.{ext}')

    def get_definition_data(self):
        return {
            'tool_key': self.tool_key,
            'name': self.name,
            'description': self.description,
            'icon': self.icon,
            'category': self.category,
            'input_schema': self.get_input_schema(),
            'output_type': getattr(self, 'output_type', 'file'),
            'is_async': self.is_async,
            'timeout_seconds': getattr(self, 'timeout_seconds', 300),
        }
