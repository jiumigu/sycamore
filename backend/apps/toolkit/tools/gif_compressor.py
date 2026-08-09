import os

from django.conf import settings
from PIL import Image, ImageSequence

from .base import BaseTool


class GifCompressorTool(BaseTool):
    """GIF压缩工具——通过抽帧、缩放、减色、质量参数压缩GIF"""

    tool_key = 'gif-compressor'
    name = 'GIF压缩'
    description = '通过抽帧、压缩等级、调整尺寸来压缩GIF文件'
    icon = '🎞️'
    category = 'image'
    output_type = 'file'

    def get_input_schema(self):
        return {
            'type': 'object',
            'properties': {
                'file': {
                    'type': 'file',
                    'description': 'GIF文件',
                },
                'frame_skip': {
                    'type': 'integer',
                    'default': 1,
                    'minimum': 1,
                    'maximum': 10,
                    'description': '抽帧间隔（每隔N帧保留1帧）',
                },
                'quality': {
                    'type': 'integer',
                    'default': 75,
                    'minimum': 10,
                    'maximum': 100,
                    'description': '压缩质量',
                },
                'scale': {
                    'type': 'number',
                    'default': 1.0,
                    'minimum': 0.1,
                    'maximum': 1.0,
                    'description': '缩放比例',
                },
                'width': {
                    'type': 'integer',
                    'default': 0,
                    'minimum': 0,
                    'maximum': 1920,
                    'description': '指定宽度（px，0=不限制）',
                },
                'height': {
                    'type': 'integer',
                    'default': 0,
                    'minimum': 0,
                    'maximum': 1920,
                    'description': '指定高度（px，0=不限制）',
                },
                'colors': {
                    'type': 'integer',
                    'default': 256,
                    'minimum': 2,
                    'maximum': 256,
                    'description': '颜色数',
                },
            },
            'required': ['file'],
        }

    def execute(self, params, progress_callback=None):
        file_path = params['file']
        frame_skip = max(1, int(params.get('frame_skip', 1)))
        quality = int(params.get('quality', 75))
        scale = float(params.get('scale', 1.0))
        width = max(0, int(params.get('width', 0)))
        height = max(0, int(params.get('height', 0)))
        colors = max(2, min(256, int(params.get('colors', 256))))

        img = Image.open(file_path)

        # 抽帧 + 缩放 + 减色
        frames = []
        durations = []
        for i, frame in enumerate(ImageSequence.Iterator(img)):
            if i % frame_skip != 0:
                continue

            if width > 0 or height > 0:
                new_w = width if width > 0 else frame.width
                new_h = height if height > 0 else frame.height
                frame = frame.resize((new_w, new_h), Image.LANCZOS)
            elif scale < 1.0:
                new_w = int(frame.width * scale)
                new_h = int(frame.height * scale)
                frame = frame.resize((new_w, new_h), Image.LANCZOS)

            if frame.mode != 'P':
                frame = frame.convert('P', palette=Image.ADAPTIVE, colors=colors)

            frames.append(frame.copy())
            durations.append(frame.info.get('duration', 100))

        if not frames:
            raise ValueError('抽帧后无可用帧')

        original_name = os.path.splitext(os.path.basename(file_path))[0]
        output_path = self.get_temp_path('gif')

        frames[0].save(
            output_path,
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=0,
            optimize=True,
            quality=quality,
        )

        if progress_callback:
            progress_callback(100)

        original_size = os.path.getsize(file_path)
        compressed_size = os.path.getsize(output_path)
        rel = os.path.relpath(output_path, settings.MEDIA_ROOT)
        download_url = settings.MEDIA_URL + rel.replace(os.sep, '/')

        return {
            'success': True,
            'output_file': download_url,
            'filename': f'{original_name}_compressed.gif',
            'stats': {
                'original_size': f'{original_size / 1024:.1f}KB',
                'compressed_size': f'{compressed_size / 1024:.1f}KB',
                'ratio': f'{(1 - compressed_size / original_size) * 100:.1f}%' if original_size else '0%',
                'frames_before': img.n_frames,
                'frames_after': len(frames),
            },
        }
