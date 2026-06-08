import importlib
from pathlib import Path


class ToolRegistry:
    """工具注册中心——自动发现并管理所有工具"""

    _tools = {}

    @classmethod
    def register(cls, tool_class):
        instance = tool_class()
        cls._tools[instance.tool_key] = instance
        return tool_class

    @classmethod
    def get_tool(cls, tool_key):
        return cls._tools.get(tool_key)

    @classmethod
    def get_all_tools(cls, category=None):
        tools = list(cls._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        return tools

    @classmethod
    def get_categories(cls):
        categories = {}
        for tool in cls._tools.values():
            cat = tool.category
            if cat not in categories:
                categories[cat] = {
                    'key': cat,
                    'label': _CATEGORY_LABELS.get(cat, '其他'),
                    'count': 0,
                }
            categories[cat]['count'] += 1
        return list(categories.values())

    @classmethod
    def auto_discover(cls):
        tools_dir = Path(__file__).parent / 'tools'
        for py_file in sorted(tools_dir.glob('*.py')):
            if py_file.name.startswith('_'):
                continue
            module_name = f'apps.toolkit.tools.{py_file.stem}'
            try:
                module = importlib.import_module(module_name)
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type)
                            and attr.__name__ != 'BaseTool'
                            and issubclass(attr, object)
                            and any(base.__name__ == 'BaseTool' for base in attr.__mro__)):
                        cls.register(attr)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning('Failed to load tool %s: %s', module_name, e)


_CATEGORY_LABELS = {
    'image': '图片处理',
    'text': '文本处理',
    'file': '文件转换',
    'convert': '格式转换',
    'other': '其他',
}
