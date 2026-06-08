from .base import BaseTool


class TravelRouteTool(BaseTool):
    """旅行路线推演工具"""

    tool_key = 'travel-route'
    name = '🚂 旅行路线推演'
    description = '输入出发地和多个目的地，生成小火车沿路线逐个抵达的动画'
    icon = '🚂'
    category = 'other'
    output_type = 'text'

    def get_input_schema(self):
        return {
            'type': 'object',
            'properties': {
                'origin': {
                    'type': 'string',
                    'description': '出发地',
                },
                'destinations': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': '目的地列表（按顺序）',
                },
            },
            'required': ['origin', 'destinations'],
        }

    def execute(self, params, progress_callback=None):
        origin = params.get('origin', '')
        destinations = params.get('destinations', [])
        stops = [origin] + destinations
        return {
            'success': True,
            'output_text': f"出发地：{origin}\n目的地：{' → '.join(destinations)}\n共 {len(destinations)} 站",
            'stats': {
                'total_stops': len(destinations),
            },
        }
