# DAMS — 数字资产管理

## Models
| Model | Table | 用途 |
|-------|-------|------|
| DamsFileResource | dams_file_resource | 文件资源（含分类/大小/重复标记/整理状态） |
| DamsAccessLog | dams_access_log | 文件访问日志 |

## Constants
- FILE_CATEGORY_CHOICES：文件分类（文档/图片/视频/代码/压缩包/其他）

## API Endpoints

前缀 `/api/dams/`

| 方法 | 端点 | 用途 |
|------|------|------|
| GET/POST | /files/ | 列表/创建 |
| GET/PUT/DELETE | /files/&lt;pk&gt;/ | 详情/更新/删除 |
| GET | /files/stats/ | 文件统计 |
| GET | /files/duplicates/ | 重复文件列表 |
| POST | /files/organize/ | 自动整理脚本触发 |

## Automation (Celery)
- `apps/dams/automation/` 子包：文件扫描/分类/去重等后台任务
