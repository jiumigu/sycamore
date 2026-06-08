import os

from django.conf import settings

from zhconv import convert

from .base import BaseTool

_MODE_MAP = {
    't2s': 'zh-cn',
    's2t': 'zh-tw',
}
_MODE_LABELS = {
    't2s': '繁体→简体',
    's2t': '简体→繁体',
}
_OUTPUT_SUFFIX = {
    't2s': '_简体',
    's2t': '_繁体',
}


class Trad2SimpTool(BaseTool):
    """繁简转换工具——上传文件，转换后下载"""

    tool_key = 'trad2simp'
    name = '繁简转换'
    description = '上传 .txt 文件，将繁体与简体互相转换后下载'
    icon = '📝'
    category = 'text'
    output_type = 'file'

    def get_input_schema(self):
        return {
            'type': 'object',
            'properties': {
                'file': {
                    'type': 'string',
                    'description': '上传的txt文件路径',
                },
                'mode': {
                    'type': 'string',
                    'enum': ['t2s', 's2t'],
                    'default': 't2s',
                    'description': '转换方向：t2s=繁体→简体，s2t=简体→繁体',
                },
            },
            'required': ['file'],
        }

    def execute(self, params, progress_callback=None):
        file_path = params.get('file', '')
        mode = params.get('mode', 't2s')
        zhconv_mode = _MODE_MAP.get(mode, 'zh-cn')
        suffix = _OUTPUT_SUFFIX.get(mode, '_converted')

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        converted = convert(content, zhconv_mode)

        original_name = os.path.splitext(os.path.basename(file_path))[0]
        new_filename = f'{original_name}{suffix}.txt'

        output_dir = os.path.join(settings.MEDIA_ROOT, 'converted')
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, new_filename)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(converted)

        changed_count = sum(1 for a, b in zip(content, converted) if a != b)
        download_url = f'{settings.MEDIA_URL}converted/{new_filename}'

        if progress_callback:
            progress_callback(100)

        return {
            'success': True,
            'output_file': download_url,
            'filename': new_filename,
            'stats': {
                'original_size': len(content),
                'converted_size': len(converted),
                'changed_chars': changed_count,
                'mode': mode,
                'mode_label': _MODE_LABELS.get(mode, ''),
            },
            'preview': converted[:500] + ('...' if len(converted) > 500 else ''),
        }
