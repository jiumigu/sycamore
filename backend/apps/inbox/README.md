# Inbox — 收件箱

## Models
| Model | Table | 用途 |
|-------|-------|------|
| InboxItem | inbox_item | 收件箱条目（6 种类别含"工作" + 3 级优先级 + 6 种状态（pending 待处理/hesitating 犹豫中/processed 已处理/done 已完成/archived 已归档/abandoned 已废弃）+ 目标关联 + 完成备注 + 犹豫/废弃原因） |
| InboxProcessLog | inbox_process_log | 处理日志（记录转为目标/里程碑/能量等操作） |

## Services
- `ConverterService`：统一转换入口，支持转为 Goal / Milestone / Sugar(EnergyTemplate) / Complete / Archive
- `InboxImportService`：批量导入（parse_csv / parse_markdown_tasks / parse_plain_text + import_items），中文标签自动归一化为合法 code，导入项 `source='import'`
- 标记完成时可联动创建小确幸记录和快乐银行奖励（前端处理，非 `ConverterService` 职责）

## API Endpoints

前缀 `/api/inbox/`

| 方法 | 端点 | 用途 |
|------|------|------|
| GET/POST | /items/ | 列表（分页 PageNumberPagination，?page=&page_size=&status=&category=&priority=&search= 筛选，status 支持 pending/hesitating/processed/done/archived/abandoned，默认 pending）/ 创建 |
| GET/PUT/DELETE | /items/&lt;id&gt;/ | 详情（含处理日志）/ 更新 / 删除 |
| POST | /items/&lt;id&gt;/complete/ | 标记完成（可选 completion_note 备注）。前端联动：可同时创建小确幸记录 (`POST /sugar/`) 和奖励流水 (`POST /reward/transactions/` with `source_type=inbox_complete`) |
| POST | /items/&lt;id&gt;/convert/ | 转为其他模块（action=convert_to_goal/convert_to_milestone/convert_to_sugar，milestone 需传 goal_id/milestone_name/target_date） |
| POST | /items/batch/ | 批量操作（complete/archive/delete/convert） |
| POST | /items/import/ | 批量导入（multipart 文件上传，按扩展名 .csv/.md/纯文本 自动识别解析，返回 success/created/failed/total/success_count/failed_count） |
| POST | /items/convert_to_goal/ | 批量转为目标（创建 Goal + 多条 Milestone） |
| GET | /items/today_pending/ | 今日待处理（pending，按优先级排序） |
| GET | /items/stats/ | 统计（总数/待处理/犹豫中/已完成/已处理/已废弃/分类统计/优先级统计） |
