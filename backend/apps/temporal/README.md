# Temporal — 时间感知

## Management Commands

| 命令 | 用途 |
|------|------|
| `migrate_atracker` | 旧表数据迁移（逐条，去重键 `(task_name, start_time)`） |
| `migrate_temporal_categories` | 按 v0.3 新映射重跑历史 L2 类型 |
| `generate_daily_log` | 每日自动生成默认日记 |
| `refresh_weekly_cache` | 刷新周度固化表 |
| `**import_worklog**` | **工作日志 Excel → 「牛马工作」时间记录（v3.58.7）** |

### `import_worklog`（v3.58.7）

```bash
python manage.py import_worklog <xlsx 路径>            # 干跑，只读不写（默认）
python manage.py import_worklog <xlsx 路径> --apply    # 落库
```

**默认干跑是硬闸门**：不带 `--apply` 时只打印报表（将新增 / 将追加 / 将补缺口 / 已导过跳过 / 待人工确认），一句都不写库。

| 参数 | 说明 |
|------|------|
| `--apply` | 真正写入（默认只干跑） |
| `--task-name` | 目标任务名，默认 `牛马工作` |
| `--date-from` / `--date-to` | 只处理某区间（`YYYY-MM-DD`） |
| `--limit N` | 只新增前 N 条（冒烟） |
| `--include-review` | 待人工确认的行也按兜底值（= 标准下班）写入 |
| `--fill-gaps` | 多段／已覆盖日若没盖满标准工时，补一条缺口记录（**默认关**；单段碎片日走规则 A，见下） |
| `--report out.csv` | 明细导出（UTF-8 BOM） |

**口径**（用户 2026-09-18 拍板，完整规则见 `worklog_parser.py` 模块头）：

- **工时两段、不扣午休**：`≤ 2026-02-27` → `09:00–18:00`；`≥ 2026-03-02` → `08:00–17:45`。正常上班日记单条。
- **加班时长表内优先**（四代写法）：2023 取方括号里的「止」而不是时长列的块时长／2024 裸数字 = 标准下班 + 时长／2025 取起止的「止」／2026 备注自然语言正则；非工作日（周末、法定节假）起止直接取表内。
- **当天已有该任务名记录 → 不新增，只追加文本**：内容 → `task_description`、备注 → `notes`；追加带 `[YYYY-MM-DD]` 前缀，该前缀**同时是幂等键**。
- **规则 A（v3.58.8 起，v3.58.9 升级）— 单段碎片补满标准工时窗口**：当天只有**一段**记录且状态是**工作日类**（`not is_restday`）时，把区间补成 `[min(原开始, 标准上班), max(原结束, 标准下班)]`：只缺开始 → `18:00→22:30` ⇒ `09:00→22:30`；只缺结束 → `12:17→12:47` ⇒ `08:00→17:45`；两端都缺就两端都补。**已达标的日子一律不动**（这就是幂等键，v3.58.9 起不再看附注标记——否则第一次只补了开始的日子会被自己的标记挡住、静默补不上结束）。**会改写已有记录的时间字段**，但**不写 `import_batch`**（保留原批次号，否则按批次回滚会误删原始记录）。**两条豁免**：① 多段 ／ 周末·法定节假·调休；② **备注明确写了「提前下班」**（`is_early_leave`，结束是实况不是记漏，样板 `2025-01-25`）。
- **规则 B（v3.58.8）— 非工作日族无时段兜底**：周末／法定节假／调休的加班若日志**没给时段**，按标准上下班窗口登记，**不进待确认**。普通「加班」无时段仍走人工确认。
- **提不出具体值的写法不猜**（`一整天` / `半天` / 备注空白 / `8点多`）→ 进「待人工确认」，默认不写。
- 每条**新增**记录带 `import_batch='worklog'`；`_ensure_task_meta` 幂等建映射、**不覆盖**已有归类。
- **不动 schema**（`managed=False` 外部表，绝不加列）、**无迁移**。

> ⚠️ **`--fill-gaps` 与规则 A 互斥**：规则 A 已改写过时间的日子会跳过 `--fill-gaps`，否则同一天既改起止时刻又补缺口记录会**重复计时**。
>
> ⚠️ **`--fill-gaps` 为什么默认关**：用户规则是「有记录就不新增」，它只在「当天有多段记录、或只有一段但两端都已达标」时才有意义（多段场景实测很少）。
>
> ⚠️ **写库前必备份** `temporal_time_atracker_tasks_list` + `temporal_task_meta`。**回滚分两类**：`DELETE ... WHERE import_batch='worklog'` **只能撤掉新增记录**；规则 A 改写过的原始记录（原批次号保留）**删不掉也回不到原起止**，只能**整表恢复备份**（**按项目铁律由用户本人执行**）。

解析层 `worklog_parser.py` 是**纯函数、不碰 DB**：`read_worklog_rows(path)` 读表、`build_plan(rows)` 判定。xlsx 用**标准库** `zipfile + ElementTree` 直解（venv 无 openpyxl，也不打算加）。**一律按列位置解析、绝不按表头名**——sheet 名与年份不符、表头多处损坏、2026 中间嵌第二套表头、备注列三套位置，详见模块头。

## Models
| Model | Table | 用途 |
|-------|-------|------|
| TemporalTask | temporal_time_atracker_tasks_list | 活动追踪任务（managed=False） |
| OneDayPage | temporal_oneday_page_list | 日记记录（managed=False） |

## Services
- TemporalStatsService：分类统计 / 平衡轮 / 排名
- CSVImportService：CSV 导入
- OneDayPageService：日记统计服务
- DailyLogAutoService：每日自动生成默认日记（当天无任何日记时创建"幸福未被发现，就叫做普通的一天"），兜底入口在 OneDayPageViewSet.list()，管理命令为 `generate_daily_log`

## Constants
4 类任务分类：生产与创造 / 维护与秩序 / 滋养与成长 / 连接与记录，含颜色和图标

## API Endpoints

前缀 `/api/temporal/`

### Tasks
| 方法 | 端点 | 用途 |
|------|------|------|
| GET/POST | /tasks/ | 任务列表 / 手工新增（v3.58.6） |
| GET/PATCH/DELETE | /tasks/&lt;id&gt;/ | 详情 / 编辑 / 删除 |
| GET | /tasks/task_names/ | 所有任务名称 |
| GET | /tasks/stats/ | 统计总览 |
| GET | /tasks/trend/ | 趋势数据 |
| GET | /tasks/balance/ | 平衡轮 |
| GET | /tasks/ranking/ | 任务排行 |
| GET | /tasks/calendar/ | 日历热力图 |
| GET | /tasks/contrib/ | 贡献图（`?metric=record_count\|hours\|toward\|deepwork\|work\|dominant_attr`；`work`=按 L3 任务名「牛马工作」聚合，v3.58.14 起替代原 `sleep`） |
| POST | /tasks/import_csv/ | CSV 导入 |

**写入口径（v3.58.6，手工新增 / 编辑）**：**不要传 `duration_hours`** —— 起止时间都给时，
后端按「结束 − 开始」算出时长，并派生 `year/mon/day/week/quarter`（这几列是 `read_only`，
手工写入若不在后端补就会落 `NULL`，年份筛选 / 月度趋势 / 完整度分母会静默漏掉该行）；
`end <= start` 返回 **400** 且错误挂在 `end_time` 上。派生统一走 `services.build_time_fields()`——
CSV 导入复用同一函数但**不传 `end`**（保留 ATracker 自带时长，含计时器暂停）。新出现的
`task_name` 会自动进 `TaskMeta`（未命中映射表则进「未归类」桶），改名的旧名字**不自动删**。

`contrib` 的两种响应形态：
- **量值模式**（`mode: "value"`，默认 `hours`）：`data: [{date, value}]`，value 是该 metric 的当日聚合值。
- **主导归因模式**（`metric=dominant_attr`，`mode: "attribution"`）：`data: [{date, value, attr, breakdown}]`——
  `attr` 是当天**五个** L1 归因中时长最多者（并列按 `成长 > 关系 > 维持 > 谋生 > 流失` 价值序取靠前者，比较前先四舍五入到 2 位小数，保证与 `breakdown` 展示一致）；
  当天无任何已归因时长（L2 类型为「未归类」）时 `attr = null`，前端画灰格；`value` 仍是当天总时长（供「峰值」展示）。

### OneDay
| 方法 | 端点 | 用途 |
|------|------|------|
| GET/POST | /oneday/ | 日记列表/创建 |
| GET/PUT/DELETE | /oneday/&lt;id&gt;/ | 详情/更新/删除 |
| GET | /oneday/stats/ | 统计信息 |
| GET | /oneday/yearly_heatmap/ | 年度热力图 |
| GET | /oneday/week_count/ | 本周日记篇数 |
| DELETE | /oneday/bulk_delete/ | 批量删除 |

### Logseq
| 方法 | 端点 | 用途 |
|------|------|------|
| GET | /open-logseq/?path= | 读取 Logseq md 文件，返回 `{filename, content}` |

### OneDayPageSerializer 扩展字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `logseq_file` | string\|null | 按 `begin_date` 拼接 Logseq 文件名，检测文件是否存在后返回绝对路径（需配置 `UserProfile.logseq_path`） |
