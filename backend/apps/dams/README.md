# DAMS — 数字资产管理

## Models
| Model | Table | 用途 |
|-------|-------|------|
| DamsFileResource | dams_file_resource | 文件资源（含分类/大小/重复标记/整理状态） |
| DamsAccessLog | dams_access_log | 文件访问日志 |

## Constants
- FILE_CATEGORY_CHOICES：文件分类（文档/图片/视频/代码/压缩包/其他）
- ATTENTION_ZONE_LABELS / ATTENTION_ZONE_COLORS：注意力四分区（red/blue/green/gray）

## API Endpoints

前缀 `/api/dams/`

| 方法 | 端点 | 用途 |
|------|------|------|
| GET/POST | /files/ | 列表（?category=&is_duplicate=&is_organized=&search=）/ 创建 |
| GET/PUT/DELETE | /files/&lt;pk&gt;/ | 详情/更新/删除 |
| GET | /files/attention_map/ | 注意力四分区统计（?freq_threshold=，默认 10） |
| POST | /files/&lt;pk&gt;/mark_organized/ | 标记为已整理 |
| GET/POST | /access-logs/ | 访问日志列表（?file=）/ 创建 |
| GET/PUT/DELETE | /access-logs/&lt;pk&gt;/ | 日志详情/更新/删除 |

## 注意力分区口径

按「访问次数 × 是否已整理」判定，**后端算、前端只渲染**：

| 分区 | 条件 | 含义 |
|---|---|---|
| gray | `access_count` 为空或 0 | 从未访问 / 未分类 |
| red | `access_count >= freq_threshold` 且未整理 | 高频但混乱，需整理 |
| blue | `access_count < freq_threshold` 且已整理 | 低频且整齐，冷存储候选 |
| green | 其余 | 健康状态 |

## 边界

- ⚠️ **本 app 只有 CRUD + 注意力分区 + 人工标记，没有文件扫描 / 自动分类 / 去重任务**。
  项目**未引入 Celery**，`apps/dams/automation/` 子包**不存在**（历史上曾如此规划，从未实现）——
  若要加后台任务，需先引入任务队列。
- 表均为 `managed=True`，`user_id` 由视图固定写入 `1`（单用户系统）。
- 侧边栏已归档（`menuConfig` 的 `defaultArchived`），页面与接口均可用。
