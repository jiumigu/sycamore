import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from django.db import transaction

from ..models import LifeSample, ObsidianConfig

# 该文件是「待采集」名单，不是样本本体，同步时跳过，避免被索引成样本
SYNC_SKIP_FILENAMES = ('待采集名单.md',)


class ObsidianService:
    """Obsidian 集成服务"""

    @staticmethod
    def get_config() -> ObsidianConfig:
        return ObsidianConfig.get_config()

    @staticmethod
    def get_full_path(relative_path: str) -> str:
        """获取完整文件路径

        Args:
            relative_path: 相对 Obsidian 仓库根目录的路径

        Returns:
            完整文件路径；未启用或无仓库路径时返回空字符串
        """
        config = ObsidianService.get_config()
        if not config.enabled or not config.vault_path:
            return ''
        return str(Path(config.vault_path) / relative_path)

    @staticmethod
    def get_samples_folder_path() -> Optional[Path]:
        """获取样本文件夹完整路径

        防御误配置：当仓库路径本身已包含样本文件夹名时（vault 尾部与
        samples_folder 同名），避免重复拼接导致路径不存在。

        Returns:
            样本文件夹 Path；未启用或无仓库路径时返回 None
        """
        config = ObsidianService.get_config()
        if not config.enabled or not config.vault_path:
            return None
        vault = Path(config.vault_path.rstrip('/'))
        folder = config.samples_folder.strip('/')
        if folder and vault.name == folder:
            return vault
        return vault / folder if folder else vault

    @staticmethod
    def parse_frontmatter(content: str) -> Dict:
        """解析 Markdown frontmatter

        Args:
            content: Markdown 文件全文

        Returns:
            {name, alias, era, region, birth_year, death_year, type, tags, summary}
        """
        result = {
            'name': '',
            'alias': '',
            'era': '',
            'region': '',
            'birth_year': None,
            'death_year': None,
            'type': 'historical',
            'tags': [],
            'summary': '',
        }

        if not content.startswith('---'):
            return result

        parts = content.split('---', 2)
        if len(parts) < 3:
            return result

        for line in parts[1].split('\n'):
            line = line.strip()
            if ':' not in line:
                continue

            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip().strip('"\'')

            if key == 'name':
                result['name'] = value
            elif key == 'alias':
                result['alias'] = value
            elif key == 'era':
                result['era'] = value
            elif key == 'region':
                result['region'] = value
            elif key in ('birth_year', 'death_year'):
                if value and value != 'null':
                    try:
                        result[key] = int(value)
                    except (TypeError, ValueError):
                        result[key] = None
            elif key == 'type':
                result['type'] = value
            elif key == 'tags':
                if value.startswith('[') and value.endswith(']'):
                    tags_str = value[1:-1]
                    result['tags'] = [t.strip().strip('"\'') for t in tags_str.split(',') if t.strip()]
                elif value:
                    result['tags'] = [value]
            elif key == 'summary':
                result['summary'] = value

        return result

    @staticmethod
    def scan_samples() -> List[Dict]:
        """扫描 Obsidian 样本文件夹中的 Markdown 文件

        Returns:
            扫描结果列表，按修改时间倒序，含 frontmatter 扩展字段 + modified_at/exists
        """
        config = ObsidianService.get_config()
        folder = ObsidianService.get_samples_folder_path()
        if not folder or not folder.exists():
            return []

        results = []
        for md_file in sorted(folder.glob('*.md'), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                content = md_file.read_text(encoding='utf-8')
                frontmatter = ObsidianService.parse_frontmatter(content)

                # 无 name 时回退到文件名
                if not frontmatter['name']:
                    frontmatter['name'] = md_file.stem

                mtime = md_file.stat().st_mtime

                results.append({
                    'name': frontmatter['name'],
                    'alias': frontmatter.get('alias', ''),
                    'era': frontmatter.get('era', ''),
                    'region': frontmatter.get('region', ''),
                    'birth_year': frontmatter.get('birth_year'),
                    'death_year': frontmatter.get('death_year'),
                    'type': frontmatter.get('type', 'historical'),
                    'tags': frontmatter.get('tags', []),
                    'summary': frontmatter.get('summary', ''),
                    'path': str(md_file.relative_to(config.vault_path)),
                    'filename': md_file.name,
                    'modified_at': datetime.fromtimestamp(mtime).isoformat(),
                    'exists': True,
                })
            except Exception:
                continue

        return results

    @staticmethod
    def _normalize_type(value: str) -> str:
        """将 frontmatter type 归一化为合法 code，非法/中文标签回退 historical"""
        code = (value or '').strip()
        if code in dict(LifeSample.TYPE_CHOICES):
            return code
        label_to_code = {label: c for c, label in LifeSample.TYPE_CHOICES}
        return label_to_code.get(code, 'historical')

    @staticmethod
    def sync_samples() -> Dict:
        """从 Obsidian 同步样本：扫描文件夹，自动创建/更新索引

        匹配顺序（防重命名后重复创建）：
        1. 按 obsidian_path 精确匹配（路径未变）→ 更新内容
        2. 按文件名（不含扩展名）在已关联记录路径里包含匹配（重命名时 frontmatter name 也可能变）→ 迁移路径 + 更新内容
        3. 按 name 匹配（重命名后路径已变，或手动索引未关联）→ 迁移/补齐路径 + 更新内容，保留 status/relevance
        4. 都找不到 → 新建

        Returns:
            {success, message, created, updated, migrated, skipped, total}
        """
        files = [
            f for f in ObsidianService.scan_samples()
            if f.get('filename') not in SYNC_SKIP_FILENAMES
        ]

        if not files:
            config = ObsidianConfig.get_config()
            return {
                'success': False,
                'message': (
                    f'未找到样本文件，请检查 Obsidian 配置\n'
                    f'当前配置路径: {config.vault_path}/{config.samples_folder}'
                ),
                'created': [],
                'updated': [],
                'migrated': [],
                'skipped': [],
                'total': 0,
            }

        created = []
        updated = []
        migrated = []
        skipped = []

        def update_content(instance: LifeSample, file_data: Dict) -> bool:
            """比对文件内容并写回实例，返回是否有字段变化"""
            changed = False
            for field, value in (
                ('name', file_data.get('name', '')),
                ('alias', file_data.get('alias', '')),
                ('tags', file_data.get('tags', [])),
                ('summary', file_data.get('summary', '')),
            ):
                if getattr(instance, field) != value:
                    setattr(instance, field, value)
                    changed = True
            return changed

        with transaction.atomic():
            for file_data in files:
                path = file_data['path']

                # 1. 按 obsidian_path 精确匹配（路径未变）
                existing = LifeSample.objects.filter(obsidian_path=path).first()
                if existing:
                    if update_content(existing, file_data):
                        existing.save()
                        updated.append(file_data['name'])
                    else:
                        skipped.append(file_data['name'])
                    continue

                # 2. 按文件名（不含扩展名）在已关联记录的路径里包含匹配：
                #    重命名时 frontmatter name 也可能一并变化，此时按姓名匹配不到，
                #    用新文件名片段在旧路径里找回原索引并迁移（如 `李白.md` → 旧路径 `诗人_李白.md`）。
                file_stem = Path(path).stem
                stem_match = None
                if file_stem:
                    stem_match = (
                        LifeSample.objects.exclude(obsidian_path='')
                        .filter(obsidian_path__icontains=file_stem)
                        .first()
                    )
                if stem_match:
                    old_path = stem_match.obsidian_path
                    stem_match.obsidian_path = path
                    update_content(stem_match, file_data)
                    stem_match.save()
                    migrated.append({'name': file_data['name'], 'old_path': old_path, 'new_path': path})
                    continue

                # 3. 按 name 匹配：文件重命名后路径已变，按姓名找回原索引并迁移路径。
                #    未关联的手动索引则补齐路径。两种情况都不触碰 status/relevance。
                name_match = LifeSample.objects.filter(name=file_data['name']).first()
                if name_match and name_match.obsidian_path != path:
                    old_path = name_match.obsidian_path
                    name_match.obsidian_path = path
                    update_content(name_match, file_data)
                    name_match.save()
                    if old_path:
                        migrated.append({'name': file_data['name'], 'old_path': old_path, 'new_path': path})
                    else:
                        updated.append(file_data['name'])
                    continue

                # 4. 创建新记录
                LifeSample.objects.create(
                    name=file_data.get('name', ''),
                    alias=file_data.get('alias', ''),
                    sample_type=ObsidianService._normalize_type(file_data.get('type', 'historical')),
                    tags=file_data.get('tags', []),
                    summary=file_data.get('summary', ''),
                    obsidian_path=path,
                )
                created.append(file_data['name'])

        parts = []
        if created:
            parts.append(f'新增 {len(created)} 个')
        if updated:
            parts.append(f'更新 {len(updated)} 个')
        if migrated:
            parts.append(f'迁移 {len(migrated)} 个（路径变更）')
        if skipped:
            parts.append(f'跳过 {len(skipped)} 个（无变化）')

        return {
            'success': True,
            'message': '同步完成：' + '，'.join(parts),
            'created': created,
            'updated': updated,
            'migrated': migrated,
            'skipped': skipped,
            'total': len(files),
        }

    @staticmethod
    def get_obsidian_uri(relative_path: str) -> str:
        """生成 Obsidian 打开文件的 URI

        Obsidian 的 path 参数需为绝对路径（相对路径无法解析），故拼上仓库绝对路径。

        Args:
            relative_path: 相对 Obsidian 仓库根目录的路径

        Returns:
            obsidian://open?path=<绝对路径>；集成未启用或无仓库路径时返回空串
        """
        config = ObsidianService.get_config()
        if not config.enabled or not config.vault_path:
            return ''
        abs_path = Path(config.vault_path) / relative_path
        return f"obsidian://open?path={urllib.parse.quote(str(abs_path))}"

    @staticmethod
    def get_obsidian_vault_uri() -> str:
        """打开 Obsidian 仓库"""
        return "obsidian://open"
