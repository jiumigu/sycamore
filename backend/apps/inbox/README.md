# Inbox — 收件箱

> 文档对齐 v3.64.82 ｜ 最后核对 2026-11-18

## Models
| Model | Table | 用途 |
|-------|-------|------|
| InboxItem | inbox_item | 收件箱条目（6 种类别含"工作" + 3 级优先级 + 6 种状态（pending 待处理/hesitating 犹豫中/processed 已处理/done 已完成/archived 已归档/abandoned 已废弃）+ 目标关联 + 完成备注 + 犹豫/废弃原因） |
| InboxProcessLog | inbox_process_log | 处理日志（记录转为目标/里程碑等操作；`convert_to_sugar` 仅存于历史行） |

## Services
- `ConverterService`：统一转换入口，支持转为 Goal / Milestone / Complete / Archive（转能量已随 sugar 能量清单退役，见 `apps/sugar/README.md`）
- `InboxImportService`：批量导入（parse_csv / parse_markdown_tasks / parse_plain_text + import_items），导入项 `source='import'`
  - 三个解析器签名统一：返回 `{'items': [...], 'skipped': [{row, content, reason}]}`（v3.64.39）
  - CSV 列名双兼容：`content`/`title`、`due_date`/`target_date`、`tags`/`标签`、`阶段`/`stage` 及中文别名（内容/事项、类别/分类、截止日期、状态、优先级、备注/描述）
  - **类别读行内 `category`**（code 或中文标签都认），不再写死 `study`；空值落 `other`（v3.64.39）
  - **旧模板兼容**：`category` 列的值既不是 code 也不是类别标签（如「基础期」）⇒ 视作阶段名进 `tags`，类别落 `other`
  - `阶段`/`stage` 列 → `tags` + 备注 `[阶段: 基础期]`
  - 优先级显式且非「中」→ 备注 `[优先级: 高/低]`（同时写入 priority 字段）；中优先级只写字段不写备注
  - 日期多格式解析：`2026-08-25` / `2026/8/25` / `2026年8月25日` / `2026.8.25` / `20260825`，失败回退 dateutil 模糊解析；**解析失败进 `skipped`，不再静默存 `None`**
  - 缺标题列的行进 `skipped`（带物理行号），不再 `continue` 吃掉
  - 状态归一化：已完成/完成/已办/done → done，其余中文标签 → 对应 code
- 标记完成时可联动创建小确幸记录和快乐银行奖励（前端处理，非 `ConverterService` 职责）

## API Endpoints

前缀 `/api/inbox/`

| 方法 | 端点 | 用途 |
|------|------|------|
| GET/POST | /items/ | 列表（分页 PageNumberPagination，?page=&page_size=&status=&category=&priority=&search= 筛选，status 支持 pending/hesitating/processed/done/archived/abandoned，默认 pending）/ 创建 |
| GET/PUT/DELETE | /items/&lt;id&gt;/ | 详情（含处理日志）/ 更新 / 删除 |
| POST | /items/&lt;id&gt;/complete/ | 标记完成（可选 completion_note 备注）。前端联动：可同时创建小确幸记录 (`POST /sugar/records/`) 和奖励流水 (`POST /reward/transactions/` with `source_type=inbox_complete`) |
| POST | /items/&lt;id&gt;/convert/ | 转为其他模块（action=convert_to_goal/convert_to_milestone，milestone 需传 goal_id/milestone_name/target_date） |
| POST | /items/batch/ | 批量操作（complete/archive/delete/convert） |
| POST | /items/import/ | 批量导入（multipart 文件上传，按扩展名 .csv/.md/纯文本 自动识别解析。返回 success/created/failed/total/success_count/failed_count；**`failed[]` 每项带 `row` 行号 + `reason`（解析跳过）或 `error`（入库失败）**，两种失败合成一条链，前端只读 `failed`） |
| POST | /items/convert_to_goal/ | 批量转为目标（创建 Goal + 多条 Milestone） |
| GET | /items/today_pending/ | 今日待处理（pending，按优先级排序） |
| GET | /items/stats/ | 统计（总数/待处理/犹豫中/已完成/已处理/已废弃/分类统计/优先级统计） |
| GET | /items/calendar/ | 按日的收件箱日历（?year=&month=） |
| POST | /items/convert-to-milestone/ | 批量转为里程碑 |

## 排序与「完成时间」（v3.64.82）

### 列表默认排序按「这件事发生的时间」

| 看哪个列表 | 排序键 | 为什么 |
|---|---|---|
| `status=done` 已完成 | `-Coalesce(processed_at, created_at)`，次级 `-id` | 这一页问的是「我最近**完成**了什么」；按创建时间排，会把 9 月记下、昨天才做完的那条埋在中间 |
| 其它状态（含 `processed` 已处理） | `-created_at` | 问的是「我最近**记**了什么」 |
| 显式 `?ordering=` | 听调用方 | 排序控件/调试不能被默认值挡回去 |

🔴 `processed`（已转出）**故意不**按 `processed_at` 排：87 条里 61 条是历史空值
（早期转出时不记时间）。按它排会让那 61 条整体沉底、内部又按 id 排，比现在更糟。
要改先补历史数据。

🔴 排序键与显示键必须是同一个：前端 `InboxItem.vue` 对已完成行印的是
「完成于 …」（`processed_at ?? created_at`，与这里的 `Coalesce` 同一句兜底）。
两把尺子的话，列表看起来就是乱序。

### `processed_at` 只有一个写入口

`InboxItem.sync_processed_at()`。六种状态按「时间该不该有」分三组：

| 组 | 状态 | 处理 |
|---|---|---|
| `STATUS_CLOSED` | `done` / `processed` | 记下这一刻（**已有值不覆盖**：完成是既成事实） |
| `STATUS_OPEN` | `pending` / `hesitating` | 清空（一条待办不该带完成时间） |
| 收尾态 | `archived` / `abandoned` | 不碰（归档掉一条已完成的不该抹掉完成时刻） |

调用方两处，都必须过它：`ConverterService.process()`（`complete` / `convert_*` / `archive`）
与 `InboxViewSet.perform_update()`（编辑表单能直接把状态改成「已完成」，走 PATCH）。
`tests/test_order_and_time.py::test_status_groups_partition_choices` 钉住三组正好铺满六种状态 ——
将来加状态却忘了想「`processed_at` 该不该有」，它会当场红。
