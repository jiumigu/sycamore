# Inbox — 收件箱

## Models
| Model | Table | 用途 |
|-------|-------|------|
| InboxItem | inbox_item | 收件箱条目（6 种类别含"工作" + 3 级优先级 + 5 种状态（pending/processed/completed/archived/deleted）+ 目标关联 + 完成备注） |
| InboxProcessLog | inbox_process_log | 处理日志（记录转为目标/里程碑/能量等操作） |

## Services
- `ConverterService`：统一转换入口，支持转为 Goal / Milestone / Sugar(EnergyTemplate) / Complete / Archive

## API Endpoints

前缀 `/api/inbox/`

| 方法 | 端点 | 用途 |
|------|------|------|
| GET/POST | /items/ | 列表（分页 PageNumberPagination，?page=&page_size=&status=&category=&priority=&search= 筛选，status 支持 pending/processed/completed/archived，默认 pending）/ 创建 |
| GET/PUT/DELETE | /items/&lt;id&gt;/ | 详情（含处理日志）/ 更新 / 删除 |
| POST | /items/&lt;id&gt;/complete/ | 标记完成（可选 completion_note 备注） |
| POST | /items/&lt;id&gt;/convert/ | 转为其他模块（action=convert_to_goal/convert_to_milestone/convert_to_sugar，milestone 需传 goal_id/milestone_name/target_date） |
| POST | /items/batch/ | 批量操作（complete/archive/delete/convert） |
| POST | /items/convert_to_goal/ | 批量转为目标（创建 Goal + 多条 Milestone） |
| GET | /items/today_pending/ | 今日待处理（pending，按优先级排序） |
| GET | /items/stats/ | 统计（总数/待处理/本周完成/逾期/分类统计/优先级统计） |
