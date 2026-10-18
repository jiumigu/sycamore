# Temporal — 时间感知

## Management Commands

| 命令 | 用途 |
|------|------|
| `migrate_atracker` | 旧表数据迁移（逐条；**判重 = 同任务名 + 时段重叠**，见下「导入判重」） |
| `migrate_oneday` | 旧日记表迁移 |
| `migrate_temporal_categories` | 按 v0.3 新映射重跑历史 L2 类型 |
| `generate_daily_log` | 每日自动生成默认日记 |
| `refresh_weekly_cache` | 刷新周度固化表 |
| `**import_worklog**` | **工作日志 Excel → 「牛马工作」时间记录（v3.58.7）** |
| `**reconstruct_worktime**` | **月度加班台账 → 逐日时间记录（反推，v3.60.8）** |
| `**check_meta_consistency**` | **只读报告「常量表种子 vs 库真源」的三类差异（v3.60.37）** |

### `check_meta_consistency`（v3.60.37）——「种子 vs 真源」漂移报告

⚠️ 先读判据：`TASK_TO_L2` **不是真源，是「初始种子」**（详见「三层分类模型」小节）。

```bash
python manage.py check_meta_consistency            # 人类可读
python manage.py check_meta_consistency --json     # 便于脚本消费
python manage.py check_meta_consistency --strict   # 有差异则退出码 1（可挂 CI / 提交前）
```

| 类 | 症状 | 动作 |
|---|---|---|
| **A 僵尸** | 种子表里的任务名，库里没有 | 从种子表删掉 |
| **B 漂移** | 两边都有、值不同 | **人工判哪个对**，再决定改哪边 |
| **C 未收录** | 库里有、种子表没有 | 补录进种子表（否则将来重建库会落「未归类」） |

🔴 只读：不写库、不改常量。用例 `tests/test_meta_consistency.py`（16 条）。

### `import_worklog`（v3.58.7；**v3.60.28 起认第二族表**）

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
> ⚠️ **写库前必备份** `temporal_time_atracker_tasks_list` + `temporal_task_meta`。**回滚分两类**：`DELETE ... WHERE import_batch='worklog'` **只能撤掉新增记录**，⚠️ **但该批次已累计多轮导入 —— 再按批次整批删会把前几轮的一起带走**，单次回滚务必**按日期**限定（如 `AND DATE(start_time) >= '2026-09-18'`）；规则 A 改写过的原始记录（原批次号保留）**删不掉也回不到原起止**，只能**整表恢复备份**（**按项目铁律由用户本人执行**）。

解析层 `worklog_parser.py` 是**纯函数、不碰 DB**：`read_worklog_rows(path)` 读表、`build_plan(rows)` 判定。xlsx 用**标准库** `zipfile + ElementTree` 直解（venv 无 openpyxl，也不打算加）。**一律按列位置解析、绝不按表头名**——sheet 名与年份不符、表头多处损坏、2026 中间嵌第二套表头、备注列**四套**位置，详见模块头。
> 🔴 **v3.60.28 新增第四套**：「每日任务日志记录」族（单 sheet、**不含年份**）——E 列是**心情指数** ⇒ **备注在 F、且没有时长列**。⚠️ 新表族必须**同时改 `_SHEET_NAME_MARKERS` 与 `_layout_for`**：漏了会落到默认布局 `('F','E')`，把 1~5 的**心情指数当成加班 1~5 小时** —— 而链路上**没有任何一步会报错**（「裸数字 = 小时」本就是 2024 那代的合法写法）。两族名**不是包含关系**，只改原先那个字符串会漏掉一族。

### `reconstruct_worktime`（v3.60.8）

```bash
python manage.py reconstruct_worktime <xlsx 路径>            # 干跑，只读不写（默认）
python manage.py reconstruct_worktime <xlsx 路径> --apply    # 落库
```

用于**只有每月加班总时长、没有逐日明细**的台账（Sheet1 = `YYYY-M` → 加班小时）：把月度总量按规则摊回每一天。
纯函数层在 `overtime_recon.py`（含 3 条硬断言：逐月总量守恒 / 请假日无加班 / 全天假无记录）。

| 参数 | 说明 |
|------|------|
| `--apply` | 真正写入（默认只干跑） |
| `--task-name` | 目标任务名，默认 `牛马工作` |
| `--batch` | `import_batch` 批次号，默认 `overtime_recon_2020_2022` |
| `--date-from` / `--date-to` | 只处理某区间（默认 `2020-04-01` ~ `2022-12-31`） |
| `--limit N` | 只新增前 N 条（冒烟） |
| `--report out.csv` | 明细导出（UTF-8 BOM） |

**口径**（完整规则见 `overtime_recon.py` 模块头）：正常上班 `09:00–18:00`（9.0h，不扣午休）；
工作日加班 `2.5–3h/天`；周末加班 `10:00` 起、单日上限 9h；半天假记 `13:30–18:00`；时段粒度 5 分钟。
法定节假日与调休补班日按国务院办公厅通知原文内置；**请假日一律移出加班候选集**、该月加班重新摊。

**三情形**（设某月台账加班 H 分钟、加班候选日 C 天 = 工作日 − 请假日）：

| 情形 | 触发 | 做法 |
|---|---|---|
| 溢出去周末 | `H > C×3h` | 候选日按「一半 3h / 一半 2.5h **交错**」铺满，余量去周末 |
| 全部候选日加班 | `C×2h ≤ H ≤ C×3h` | 每天 `H/C` |
| 部分候选日加班 | `H < C×2h` | `n = round(H/2.5)` 天等间隔散布，每天 `H/n` |

> ⚠️ **判定阈值不跟着铺法下调**：把溢出阈值降到 `C×2.75h` 会把「仅微超」的月份也卷进来，
> 产出**小到落不成 5 分钟粒度**的周末余量。余量摊不开时，宁可让它留在第二情形被平滑吸收。

> ⚠️ **产物是推定值**：月度总量、上下班时间、请假记录是真实的；**哪一天加班、加多久是摊出来的**
> （原始数据里没有这个信息）。生成规则**确定性**（同样输入永远同样输出），整批带批次号。
> **幂等键带 `import_batch`** —— 区间内已有别的来源记录（如 `worklog` 导入的）不影响本批次生成。

> ⚠️ **写库前必备份**；回滚 `DELETE ... WHERE import_batch='<批次号>'`（**按项目铁律由用户本人执行**）。


## Models
| Model | Table | 用途 |
|-------|-------|------|
| TemporalTask | temporal_time_atracker_tasks_list | 活动追踪任务（**managed=False 外部表，绝不加列**） |
| OneDayPage | temporal_oneday_page_list | 日记记录（managed=False） |
| WeeklyTimeCache | temporal_weekly_time_cache | 周度固化表，由 `refresh_weekly_cache` 重建。⚠️ **当前无消费方** —— 168h 周结构走 `get_168h_structure()` **实时聚合源表**、不读它；消费它的 `weekly-tracking` 接口与前端页面**均已退役**（见「周度追踪」节） |
| TaskMeta | temporal_task_meta | 任务元数据（`activity_type` = v0.3 的 **L2 类型**，9 类预设 + 未归类） |
| ActivityGroup | temporal_activity_group | ⚠️ **已废弃** —— v0.3 起取消该层，表与 `TaskMeta.group` 列**保留不删**，代码不再读写 |

## Services
- TemporalStatsService：分类统计 / 平衡轮 / 排名
- CSVImportService：CSV 导入
- OneDayPageService：日记统计服务
- DailyLogAutoService：每日自动生成默认日记（当天无任何日记时创建"幸福未被发现，就叫做普通的一天"），兜底入口在 OneDayPageViewSet.list()，管理命令为 `generate_daily_log`
- **`find_duplicate_task()`：导入判重的单一真源**（CSV 导入与 `migrate_atracker` 共用）

### 导入判重（v3.60.29，改判重前必读）

🔴 **判重 = 「同任务名 + 时段重叠」，不是 `(task_name, start_time)` 精确相等。**
旧口径（秒级半开区间精确匹配）会被 `import_worklog` **规则 A（时段补全）**打穿 ——
规则 A 会把已有记录的 `start_time` 改写成标准上班时刻（08:05→08:00），
那条记录在精确匹配下**"消失"**，于是再导一次 CSV / 重跑迁移就会**静默多插一条重复**
（2026-09-17 实案：多出 9.92h；被改写过的「雷区日」共 50 天）。

- 判据 = **重叠时长 ÷ 较短一方时长 ≥ `DUP_OVERLAP_RATIO`（0.8）**。
  ⚠️ 用比值而不是「有重叠就算」：**相接分段会重叠几秒**（合法记录，不能吞）。
- ⚠️ 命中后若**开始时刻与源数据不同** ⇒ 视为「起止已被工作日志校准」，
  **跳过覆盖**并计入 `protected`（否则重导会把补全后的工时**静默打回**原值）。
- ⚠️ `reconstruct_worktime` **有意不走**此判重：它按 `import_batch` 隔离，
  且**故意允许**与 ATracker 记录并存（见 `test_overtime_recon.py`）。
- 用例：`apps/temporal/tests/test_dedup.py`（11 条）。推导：`TECH-NOTES §64`。

## 三层分类模型（v0.3，勿改回颠倒层级）

```
L1 归因  六词：成长 / 体验 / 关系 / 维持 / 谋生 / 流失   （真源 temporal/constants.py）
L2 类型  TaskMeta.activity_type，10 类预设 + 未归类
L3 任务  ATracker 原始 task_name（managed=False 外部表，不改）
```

- ⚠️ **ActivityGroup 层已取消**，不要再引入中间层。叠加归因覆盖靠 `attr_rule`，不靠 group。
- 🔴 `TASK_TO_L2` 是**初始种子、不是真源**（v3.60.37 拍板）：真源 = `temporal_task_meta`，
  运行时所有统计（贡献图 / 时间统计 / 台账）都读库里的值。种子表**只在「库里还没有该 task_name」
  时生效**（`_ensure_task_meta` 建档 / `migrate_temporal_categories` 回填），建完即永久退出运算
  ⇒ 两边**允许**不一致，那不是 bug；但这不一致必须**看得见**。
  - 想改一个**已经在用**的任务归类 ⇒ 改库里那行（前端「映射编辑器」），**改种子表没用**。
  - ⚠️ `default_attribution` 是**落库值**：改种子表不会回头改已存在的行，须另跑数据迁移。
    先例三条：`0010`（社交→关系）、`0011`（旅游观景→主动经历/体验）、
    `0013`（运动健身 维持→成长 —— 这一条是**改库以对齐种子**，方向与前两条相反）。
  - **新增 L1 词或改某个 task_name 的挂靠时，常量与迁移必须成对做** —— 只改常量是静默的部分修复。
  - 漂移凭据：`manage.py check_meta_consistency`（只读，报 A/B/C 三类，见上）。
- ⚠️ `ATTRIBUTION_ORDER`（价值序）**只许纯增量插入，不许挪动已有词次序**：并列时靠前者胜，挪位会让历史数据「并列取谁」的结果静默改变。钉在 `test_temporal_v03.py::test_relation_slot_and_order_invariance`。

## Constants
- 旧四分类（`CATEGORY_COLORS` / `TASK_CATEGORY_MAPPING` 的值域）：**工作 / 学习 / 生活 / 兴趣记录**（含颜色与图标）。
  ⚠️ 更早的名字「生产与创造 / 维护与秩序 / 滋养与成长 / 连接与记录」**已废弃** —— 值域只能是现在这四个，
  因为它要被 `LEGACY_FOUR_TO_L2` 二次查表（塞第五个值进去会 KeyError）。
- L1 归因**六词**与顺序见 `temporal/constants.py` 的 `ATTRIBUTION_CHOICES` / `ATTRIBUTION_ORDER` / `ATTRIBUTION_COUNTED`。
- L2 类型 10 类预设见 `ACTIVITY_TYPE_PRESETS`；`TASK_TO_L2` 是 task_name 级**种子**（见上「三层分类模型」）。

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
| GET | /tasks/contrib/ | 贡献图（`?metric=record_count\|hours\|toward\|deepwork\|work\|dominant_attr`；`work`=按 L3 任务名「牛马工作」聚合，v3.58.14 起替代原 `sleep`）。**睡眠类不计入**（见下「不计入贡献图的任务」） |
| POST | /tasks/import_csv/ | CSV 导入 |
| GET | /tasks/daily_detail/ | 单日任务明细（`?date=`；`&scope=contrib` = 按**贡献图口径**取，即排除不计入贡献图的任务） |
| GET | /tasks/distribution/ | 时长分布 |
| GET | /tasks/meta/ | 任务元数据（**分类台账**主体，非「未归类池」） |
| GET | /tasks/meta_ledger/ | 分类台账（编辑 / 撤销覆盖的入口） |
| GET | /tasks/unclassified/ | 未归类任务（**只是 meta 的筛选态**） |
| POST | /tasks/batch_set_meta/ | 批量设置 L2 类型 |
| GET | /tasks/sunburst/ | 结构图（三层同心 pie 数据） |
| GET | /tasks/completeness/ | 记录完整度（分母默认 16h/天） |

**写入口径（v3.58.6，手工新增 / 编辑）**：**不要传 `duration_hours`** —— 起止时间都给时，
后端按「结束 − 开始」算出时长，并派生 `year/mon/day/week/quarter`（这几列是 `read_only`，
手工写入若不在后端补就会落 `NULL`，年份筛选 / 月度趋势 / 完整度分母会静默漏掉该行）；
`end <= start` 返回 **400** 且错误挂在 `end_time` 上。派生统一走 `services.build_time_fields()`——
CSV 导入复用同一函数但**不传 `end`**（保留 ATracker 自带时长，含计时器暂停）。新出现的
`task_name` 会自动进 `TaskMeta`（未命中映射表则进「未归类」桶），改名的旧名字**不自动删**。

`contrib` 的两种响应形态：
- **量值模式**（`mode: "value"`，默认 `hours`）：`data: [{date, value}]`，value 是该 metric 的当日聚合值。
- **主导归因模式**（`metric=dominant_attr`，`mode: "attribution"`）：`data: [{date, value, attr, breakdown}]`——
  `attr` 是当天**六个** L1 归因中时长最多者（并列按 `成长 > 体验 > 关系 > 维持 > 谋生 > 流失` 价值序取靠前者，比较前先四舍五入到 2 位小数，保证与 `breakdown` 展示一致）；
  当天无任何已归因时长（L2 类型为「未归类」）时 `attr = null`，前端画灰格；`value` 仍是当天总时长（供「峰值」展示）。

**不计入贡献图的任务**（v3.60.27 · 单一真源 = `constants.CONTRIB_EXCLUDED_TASK_NAMES`）

- 目前名单：`休息睡眠`、`午睡`。**为什么**：它们的 L2 = 主动休息 ⇒ 归因 = 维持；
  一天 8h 会长期成为当天**最大**归因，热力图（默认口径就是「主导归因」）于是几乎
  天天一片「维持」，真正想看的成长 / 谋生 / 关系全被压掉。
- **为什么按 `task_name` 而不是 L2**：同一个 L2「主动休息」里还有 **运动健身 / 心灵冥想**
  （归因「成长」）—— 按 L2 剔会把它们一起误伤。
- **过滤只有一处**：`contrib` 取数的那个 queryset ⇒ **6 个口径一起生效**
  （逐口径各改一处的话，漏掉的那个不报错，而这类图是扫一眼看的，根本看不出来）。
- **只作用于贡献图**：时间统计页的总时长 / 记录数 / 完整度 / 旭日图 / 趋势 / 168h 结构
  **照旧包含**睡眠 —— 那页回答的是「一天到底怎么花的」。两页回答不同的问题，不共用一把尺子。
  有一条**边界钉子**用例钉住这条：将来别把过滤顺手提到公共取数里。
- **副作用（既定行为，不是 bug）**：只有睡眠记录的那天会**整格消失**（前端 `v === 0`
  ⇒ 画空白格、不可点），语义是「那天没有可分析的活动」。
- ⚠️ 任务改名 / 新增同类睡眠任务 ⇒ **必须同步那张名单**（`test_exclusion_list_is_pinned`
  钉住名单内容，改名时它会失败提醒）。

### OneDay
| 方法 | 端点 | 用途 |
|------|------|------|
| GET/POST | /oneday/ | 日记列表/创建 |
| GET/PUT/DELETE | /oneday/&lt;id&gt;/ | 详情/更新/删除 |
| GET | /oneday/stats/ | 统计信息 |
| GET | /oneday/yearly_heatmap/ | 年度热力图 |
| GET | /oneday/week_count/ | 本周日记篇数 |
| GET | /oneday/daily_detail/ | 单日日记明细（?date=） |
| GET | /oneday/contrib/ | 日记贡献图 |
| GET | /oneday/week_stats/ | 周统计 |
| DELETE | /oneday/bulk_delete/ | 批量删除 |

### 周度追踪（⚠️ 已退役，接口按设计稿保留）

原功能：每周总投入 vs **30h/周基准** ⇒ 达标率 / 达标周数。
v0.2 设计稿**决策 4 彻底移除 30h benchmark**（全记录后周总时长逼近 168h 硬上限，
30h 从「及格线」跌成「地板」），替代品 = **「168h 周结构」**（回答「我的一周由什么组成」，
可切 L1/L2 堆叠）。

| 方法 | 端点 | 用途 |
|------|------|------|
| GET | /weekly-tracking/ | 周度追踪（读固化表）—— ⚠️ **前端已无调用方**，按 v0.3 设计稿刻意保留（避免 404），别再接回前端 |
| POST | /weekly-tracking/refresh/ | 重建周度固化表 —— 同上；另有管理命令 `refresh_weekly_cache`（支持 `--dry-run`） |
| GET | /weekly-structure/ | ✅ **在用**：168h 周结构（替代 `weekly-tracking`），消费方 = 时间统计首页 `TimeStatsView.vue` |

> 前端侧对应清理见 v3.60.34：孤儿页面 `WeeklyTrackingView.vue` 与两个 API 封装已移除。

### Logseq
| 方法 | 端点 | 用途 |
|------|------|------|
| GET | /open-logseq/?path= | 读取 Logseq md 文件，返回 `{filename, content}` |

### OneDayPageSerializer 扩展字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `logseq_file` | string\|null | 按 `begin_date` 拼接 Logseq 文件名，检测文件是否存在后返回绝对路径（需配置 `UserProfile.logseq_path`） |
