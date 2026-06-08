import os

import os

from PIL import Image

from .base import BaseTool


class Img2GifTool(BaseTool):
    """图片转GIF工具"""

    tool_key = 'img2gif'
    name = '图片转GIF'
    description = '将多张图片合成为GIF动图，可调整帧率和循环次数'
    icon = '🖼️'
    category = 'image'
    output_type = 'file'

    def get_input_schema(self):
        return {
            'type': 'object',
            'properties': {
                'images': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': '图片文件路径列表',
                },
                'fps': {
                    'type': 'integer',
                    'default': 10,
                    'minimum': 1,
                    'maximum': 60,
                    'description': '帧率（每秒帧数）',
                },
                'loop': {
                    'type': 'integer',
                    'default': 1,
                    'minimum': 0,
                    'description': '循环次数（0=无限循环）',
                },
                'max_width': {
                    'type': 'integer',
                    'default': 800,
                    'minimum': 100,
                    'maximum': 3840,
                    'description': '最大宽度（像素）',
                },
                'quality': {
                    'type': 'integer',
                    'default': 80,
                    'minimum': 1,
                    'maximum': 100,
                    'description': '输出质量',
                },
            },
            'required': ['images'],
        }

    def execute(self, params, progress_callback=None):
        images = []
        file_paths = params['images']
        total = len(file_paths)
        max_w = params.get('max_width', 800)
        fps = params.get('fps', 10)
        duration = int(1000 / fps)

        for idx, img_path in enumerate(file_paths):
            img = Image.open(img_path)

            # 保持宽高比缩小
            w, h = img.size
            if w > max_w:
                ratio = max_w / w
                img = img.resize((max_w, int(h * ratio)), Image.LANCZOS)

            # GIF 需要 RGB 或 P 模式
            if img.mode not in ('RGB', 'P'):
                img = img.convert('RGB')

            images.append(img)

            if progress_callback:
                progress_callback(int((idx + 1) / total * 50))

        output_path = self.get_temp_path('gif')

        images[0].save(
            output_path,
            save_all=True,
            append_images=images[1:],
            duration=duration,
            loop=params.get('loop', 1),
            quality=params.get('quality', 80),
        )

        file_size = os.path.getsize(output_path)

        if progress_callback:
            progress_callback(100)

        return {
            'success': True,
            'output_file': output_path,
            'stats': {
                'frame_count': len(images),
                'duration_ms': duration * len(images),
                'file_size': file_size,
                'dimensions': f'{images[0].width}x{images[0].height}',
            },
        }
