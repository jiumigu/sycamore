# LifeSample — 人生样本

轻量索引人生参照样本，深度内容存放在 Obsidian。Sycamore 侧只存索引（姓名/别名/类型/标签/一句话简介/Obsidian 路径/我的笔记），Obsidian 仓库按 `frontmatter` 扫描自动关联。

## Models

| Model | Table | 用途 |
|-------|-------|------|
| LifeSample | life_sample | 人生样本索引（name/alias/sample_type/tags JSON/summary/obsidian_path/my_note/related_goals/related_diary JSON + status/verified_at/reviewed_at/relevance/relevance_reason） |
| ObsidianConfig | obsidian_config | Obsidian 集成配置（单例 id=1：enabled/vault_path/samples_folder） |

> **状态管理**：`status` ∈ 已收集/已核实/已审阅；`relevance` ∈ 高度借鉴/参考/了解。`verified_at`/`reviewed_at` 为只读，由 `save()` 在状态推进时自动补齐（模型属性 `status_label`/`relevance_label` 输出中文标签）。

`LifeSample.obsidian_full_path` 为属性，惰性调用 `ObsidianService.get_full_path`（集成未启用或无路径时返回空串）。

## Services

`services/obsidian_service.py` — `ObsidianService` 全静态方法：

| 方法 | 职责 |
|------|------|
| `get_config()` | 取单例配置（get_or_create id=1） |
| `get_full_path(rel_path)` | 相对路径 → 仓库绝对路径（未启用/无 vault 返回 ''） |
| `get_samples_folder_path()` | 样本文件夹绝对路径（`Optional[Path]`） |
| `parse_frontmatter(content)` | 解析 frontmatter：name/alias/era/region/birth_year/death_year/type/tags/summary |
| `scan_samples()` | 扫描样本文件夹，解析 frontmatter，按 mtime 倒序返回 `[{name, alias, era, region, birth_year, death_year, type, tags, summary, path, filename, modified_at, exists}]` |
| `sync_samples()` | **双向同步核心（防重复）**：匹配顺序 ① `obsidian_path` 精确匹配 → 字段变更则更新；② 文件名（不含扩展名）在已关联记录路径里包含匹配（重命名时 frontmatter name 也可能变，如 `李白.md` → 旧路径 `诗人_李白.md`）→ 迁移路径 + 更新内容；③ `name` 匹配（重命名后路径已变，或手动索引未关联）→ 迁移/补齐路径 + 更新内容，**保留 status/relevance**；④ 都找不到 → 新建；`transaction.atomic` 包裹，返回 `{success, message, created, updated, migrated, skipped, total}`；跳过 `SYNC_SKIP_FILENAMES`（`待采集名单.md`） |
| `_normalize_type(value)` | frontmatter type 归一化为合法 code（支持中文标签，非法回退 historical） |
| `get_obsidian_uri(relative_path)` | 生成 `obsidian://open?path=<绝对路径>` URI（`path` 参数需绝对路径 Obsidian 才能解析，拼上仓库路径；集成未启用/无仓库路径返回 `''`） |
| `get_obsidian_vault_uri()` | 生成仓库根目录打开 URI |

## API Endpoints

前缀 `/api/lifesample/`

| 方法 | 端点 | 用途 |
|------|------|------|
| GET/POST | /samples/ | 样本列表（**不分页**，?search=&type=&status=&relevance=&tag= 筛选）/ 创建 |
| GET/PATCH/DELETE | /samples/&lt;pk&gt;/ | 详情 / 更新 / 删除 |
| GET | /samples/tags/ | 去重标签列表（排序） |
| GET | /samples/stats/ | 统计 `{total, synced, pending, obsidian_files, status, relevance}`（状态/评级分布 dict） |
| POST | /samples/sync-from-obsidian/ | **同步**：扫描并自动创建/更新/迁移索引，返回 `{success, message, created, updated, migrated, skipped, total}`（无文件时 404 + 提示信息） |
| GET/POST | /obsidian/config/ | 集成配置（单例：GET 取 / POST 局部更新） |
| GET | /obsidian/scan/ | 扫描样本文件夹（预览），返回扩展字段数组 |
| GET | /obsidian/open/&lt;path&gt;/ | 打开 Obsidian 文件，返回 `{uri}`（绝对路径，Obsidian 可直接解析） |

> `LifeSampleViewSet` 设 `pagination_class = None`（轻量索引，前端直接读数组）；`open/<path>` 用 DefaultRouter 正则捕获路径，含 `/` 与中文原样保留。
