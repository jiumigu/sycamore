## [2026-09-17] v3.58.0 — 时间结构图重做：三层同心环，L1/L2 恒在环内、L3 全部圆外引线标注（解决标签堆叠看不清）

### 🐛 修复

- **时间结构图标签互相堆叠、看不清**：原实现用 ECharts `sunburst` 把三层（L1 归因 / L2 类型 / L3 task_name）标签**全部画在扇区内部**，小扇区（如「拿起画笔」0.18°、「心灵冥想」0.35%、「流失」1.3%）根本没有放字空间，文字互相压叠、跨环穿到相邻扇区，整图不可读。现改为 **三层同心环形饼图**，标签按层级分流：**L1 归因 / L2 类型恒定在环内**，**L3 任务名全部圆外引线标注**——左右分侧、垂直避让（推挤 + 均匀铺满）、折线引线指向所属扇区，文字取所属 L2 色并加深（浅灰/浅蓝色系也保证可读）。圆心显示总时长，替换原「平衡轮」位置的空洞。
- **环内标签排版（L1 / L2，恒在环内、且不做「放不下就隐藏」的判定）**：文字统一水平排在环带中线，位置由一轮**沿弧长方向的松弛避让**算出——理想锚点即扇区中点，与左右邻居冲突时按「扇区宽裕度」加权分配让步量（**大扇区多让、极窄扇区几乎不动**），于是 2025「流失」4.3°、2024「社交」3.7° 这类 1% 级扇区的文字会**钉在自己那段弧上、只向两侧邻区（投向 / 外部 / 主动休息）的空白处溢出**：既不重叠、不隐藏，也不出圆、不需要引线，且保持「标签中心仍在该扇区」的语义。文字取所属扇区色加深 + 白色光晕描边，压在同色系或异色扇区上都能读清。（旧方案曾按「沿弧线 → 沿半径 → 隐藏」三档降级，把塞不下的扇区列到图下「扇区过小未标注」提示里，本轮弃用。）
- **根因（ECharts 能力边界）**：`sunburst` 系列**不支持 `labelLine`**（无法画引线），也不走 `labelLayout` 流程（`moveOverlap: 'shiftY'` 这类自动避让只对饼图等带引线的系列生效）——所以旭日图的外置标签无法自动避让。改用多个 `pie` 系列同心叠放（各环 `startAngle: 90 / clockwise / sort: false` 保证角度对齐），才拿到引线与避让能力。
- **画布利用率与自适应**：圆外只剩 L3 一列后收窄预留（146 → 92，窄容器 126 → 84），圆半径相应放大（实测卡片 445×400 下 `R3` 92.5 → 138.75，**+50%**，各扇区弧长同比变长，更利于环内标注）；图高 340 → 400；半径按可用空间自适应（横向为圆外标签列预留、纵向留 14px 边距，窄容器自动收紧），卡片宽度变化时**重算 option**（标签位置依赖像素尺寸，只 `chart.resize()` 不够）；顺带修掉窗口 `resize` 监听未解绑的内存泄漏。

### 📦 迁移

- **补齐 3 处既有遗留迁移**（此前 `makemigrations --check` 长期存在 diff，非本版功能引入）：① `redemption/0002_alter_redemptionattrrule_match_field`——归因规则 `match_field` 的 choices 增补 `activity_type`（配合 v0.3 三层分类，归因规则可直接按 L2 活动类型匹配；`max_length=20` 未变，**choices 不落库 → 数据库零变更**）；② `summary/0004_alter_sevendimconfig_options`——七维封顶配置补 `ordering: ['-created_at']` 与 `verbose_name`（**Meta 不落库 → 数据库零变更**）；③ `temporal/0006_rename_temporal_ta_activi_2d3a6f_idx_temporal_ta_activit_b06509_idx_and_more`——`TaskMeta` 两个索引改名：Django 6.0 的自动索引命名规则**去掉了升序 `+` 前缀位**（源码 `db/models/indexes.py:263` 由 `"+%s"` 改为 `"%s"`，字段名切片随之右移一位、hash 亦变），故 `temporal_ta_activi_2d3a6f_idx → temporal_ta_activit_b06509_idx`、`temporal_ta_group_3c4b7e_idx → temporal_ta_group_i_78a288_idx`（**DB 层 2 条 `RENAME INDEX`**）。
- 补齐后 `makemigrations --check` → **No changes detected**，迁移历史与模型定义完全对齐。三份迁移**只写文件、未执行**；其中仅 `temporal/0006` 会动库，手动命令 `manage.py migrate temporal 0006`（`redemption/0002`、`summary/0004` 为纯状态变更，执行与否都不影响表结构）。
- 遗留项（未处理，供后续决定）：`TaskMeta.group` 列已弃用（代码不再读写）但仍挂着索引 `temporal_ta_group_i_78a288_idx`，如要清理可单独 `DROP INDEX`——不影响数据，只是白占写入开销。

### 🧪 测试 / 验证

- 用**开发库真实数据**在卡片 445×400 下逐年复核（2026 / 2025 / 2024，开发页面实截 + 标签坐标几何自检）：L1 归因与 L2 类型**全部落在各自环带内、无跨带**，同环带标签**两两无重叠**（0 异常）；极窄扇区已全部正常标注在环内——2025「流失」4.3°、2026「被动消耗」2.18% / 「流失」2.18%、2024「社交」**1.03%（3.7°）** 均按预期溢出到邻区空白显示，无隐藏、无图下提示、无引线；L3 全部在圆外且引线指向正确；悬浮提示正常（如 `悦己越己 → L3 任务 5.40 h 0.5%`）。
- `vue-tsc --build` **0 错误**、`vite build` 通过。纯前端改动（`SunburstChart.vue` + `TimeStatsView` 图高），**无 schema 变更、无需迁移**。

## [2026-09-15] v3.57.0 — 时间统计模块重构 v0.3 落地：三层分类（L1 归因 / L2 类型 / L3 task_name）· 记录完整度替代达标率 · 168h 结构 · 映射编辑器 · 历史数据迁移

### ✨ 新增

- **时间分类三层结构（v0.3 核心，自顶向下）**：把原来「一个 task 一个 category」的扁平分类拆成三层——**L1 = 归因**（投向/维持/外部/流失，即最顶层的「分组」）、**L2 = 类型**（活动类型）、**L3 = task_name**（原始 ATracker 任务名，最细粒度叶子）。数据流读作 `task_name(L3) → 类型(L2) → 归因(L1)`：新建 `temporal_task_meta`（`TaskMeta`，`task_name → 活动类型 + 默认归因`，唯一键 `task_name`），内置 9 项预设（睡眠/维护性事务/深度工作/浅层工作/主动休息/被动消耗/社交/兴趣记录 + 「未归类」桶），未命中映射的落到「未归类」；L1 归因复用赎回期既有的 `redemption_attr_rule`（`RedemptionAttrRule`，四类：投向/维持/外部/流失），**不新增重复归因表**，解析优先级为 `RedemptionAttrRule`（人工 override）> `TaskMeta.default_attribution`（类型默认）> 兜底「投向」。**外部表 `temporal_time_atracker_tasks_list`（managed=False）绝不加列**——所有新分类落在独立 managed 表，ATracker 原表零改动。※ v0.3 初版曾把层级设为「L1 自建聚合分组 / L3 归因」（颠倒），本版按你的口径订正为上述 L1 归因，取消自建分组层。
- **映射编辑器 `/temporal/mapping`**：分类治理页——「未归类池」列出所有还没映射的 `task_name`（带记录数/时长，按量排序），选中后批量设 **L2 活动类型**与 **L1 价值归因**；保存走 `POST tasks/batch_set_meta/`，同一请求内写 `TaskMeta` 并在填了归因时同步写 `RedemptionAttrRule`，一处操作同时服务时间统计与赎回期。
- **任务清单独立页 `/temporal/tasks`**：L3 task_name / L1 归因 / L2 类型三列并排 + 多维筛选（L1 归因 / L2 类型 / 仅未归类 / 关键词 / 日期区间）+ 行内与批量修改，回答「某个 task_name 到底归到哪一层」的排查需求（此前只能进 DB 或读代码）。
- **旭日图 `SunburstChart`（3 环）**：`L1 归因 › L2 类型 › L3 task_name` 三层占比可视化（内环归因四色、中环类型主色、外环任务名），替换原来被砍掉的「平衡轮」（`get_balance` API 保留，仅暂不展示）。
- **168h 结构图 `Weekly168Chart`**：近 N 周按 L1 归因或 L2 类型堆叠（前端可切 `by_l1`/`by_l2`），叠加每周记录完整度——把「一周 168 小时实际流向哪」摊开看。
- **记录完整度替代达标率**：时间统计第 4 卡由「30h/周达标率」改为**记录完整度**（已归类小时 ÷ 有记录天数 × 16h，未归类不计入分子与分母）；口径与赎回期覆盖率对齐，回答的是「记录记得多全」而非「够不够努力」——配合「刷手机/发呆/焦虑空转也纳入记录」的新时间观。
- **贡献图多指标**：`GET tasks/contrib/?metric=hours|record_count|toward|deepwork|sleep`（默认 `hours`），明细列同步改为 L3 task_name / L1 归因 / L2 类型，可按「记录条数」看频次贡献而非只看时长。
- **新接口**：`tasks/meta/`、`tasks/unclassified/`、`tasks/batch_set_meta/`、`tasks/sunburst/`、`tasks/completeness/`、`weekly-structure/`、`trend/?level=l1|l2|l3`（l1=归因 / l2=类型 / l3=task_name）；`TemporalTaskSerializer` 增补 `activity_type`(L2) / `attribution`(L1) / `is_unclassified` 三个只读字段（旧字段全部保留）。前端新增 `temporalTypes` / `temporalApi` / `temporalStore` 对应定义与 `SunburstChart` / `Weekly168Chart` / `MappingEditor` 组件。

### ♻️ 重构

- **三层语义订正（本次）**：确立 `L1 归因 / L2 类型 / L3 task_name` 自顶向下；**取消「自建聚合分组 ActivityGroup」层**——表 `temporal_activity_group` 与 `TaskMeta.group` 列**保留不删**（历史数据零损失），代码侧不再读写，同时移除 `task-groups/` 路由与 `ActivityGroupViewSet` / `ActivityGroupSerializer`。服务层：`get_overview` 的 `group_breakdown` → **`attribution_breakdown`（L1 归因）**（保留 `activity_breakdown` 为 L2）；`get_trend` 支持 `l1`(归因)/`l2`(类型)/`l3`(task_name)；`get_sunburst` 改 3 环；`get_168h_structure` 输出 `by_l1`(归因)/`by_l2`(类型)/`by_l3`(task_name)；`get_ranking` 由旧 `category_level1` 改按 L2；`resolve_task_meta` 去掉 `group_name`/`group_color`。前端同步：类型/接口/状态去 `ActivityGroup`，`SunburstChart` 3 环，`MappingEditor` 去分组管理，`TaskListView`/贡献图明细改 L1 归因 / L2 类型 / L3 task_name。
- **彻底移除 30h/周达标规则**：`TimeStatsView` 去掉 30h 输入与达标率/周数展示；`WeeklyTrackingView` 改接 `weekly-structure/`（原 30h benchmark 移除）。**但 30h = 1 点换算保留**（`summary` 模块 `divisor=30`），口径收紧为**仅统计归因 ∈ {投向,维持,外部} 的小时**——流失与未归类不再折算贡献点，`progress_aggregator._times_raw` 相应改写。
- **CSV 导入停写旧分类列**：`CSVImportService.import_from_csv` 不再写 `category_level1` / `category_color`（**旧列保留不删，仅停止写入**），导入后自动调 `_ensure_task_meta` 为新出现的 `task_name` 建 `TaskMeta` 并回报 `unclassified` 数。

### 🐛 修复

- **Django `DISTINCT` + `Meta.ordering` 导致去重静默失效**：`TemporalTask.Meta.ordering = ['-start_time']`，使 `.values_list('task_name').distinct()` 被 Django 生成 `SELECT DISTINCT task_name, start_time ...`（排序字段被注入 SELECT 列），DISTINCT 实际按「task_name + start_time」去重——历史迁移命令据此把 **25 个**真实去重 task_name 误报成 **2476 个**（若按此执行会徒增两千余次 `get_or_create` 并输出误导性统计）。统一加 `.order_by()` 清空默认排序修复：迁移命令 + `get_overview`（active_days）/ `get_168h_structure`（day_map）/ `get_completeness`（分母天数）四处。

### 🧪 测试 / 验证

- 后端全量 `pytest apps` → **191 passed**（含 temporal/summary/redemption **38 passed**）；`apps/temporal/tests/test_temporal_v03.py` 覆盖：归因优先级 override > 默认 > 兜底 / 完整度分母与未归类剔除 / **趋势 L1·L2·L3 三档** / **旭日 3 环（归因→类型→task_name）** / 未归类池与批量设 L2 / CSV 停写分类列 / 迁移命令幂等且不删旧数据 / **DISTINCT 去重回归** `test_dedup_not_broken_by_meta_ordering`（断言命令上报的去重计数而非仅行数，否则缺陷会被 `get_or_create` 的兜底去重掩盖）；`apps/summary/tests/test_times_raw_v03.py` 覆盖 30h=1 点换算排除「流失」与「未归类」。层级断言已同步订正为「L1=归因」，不再依赖 ActivityGroup。
- 前端 `vue-tsc --build` **0 错误**、`vite build` 构建成功（注：`npm run build` 的 `run-p` 收尾会报 `spawn EPERM` 副作用，非真实错误，可靠校验用 `vue-tsc` 与 `vite` 分开跑）。
- **开发库迁移执行（本版落地）**：① 先 `mysqldump` 全库备份至 `db_backups/pre_v03_20260915.sql`（3.1 MB）；② `manage.py migrate temporal 0005` 建两张新表（`temporal_activity_group` / `temporal_task_meta`）；③ `manage.py migrate_temporal_categories` 迁移历史分类 → **新增 25 条 `TaskMeta`，未归类 0**（命中率 25/25），旧列 `category_level1/2/color` **完整保留**、外部表 **2478 行零变化**；幂等复跑「新增 0」验证通过。迁移脚本 `backend/apps/temporal/management/commands/migrate_temporal_categories.py` 支持 `--dry-run`，全程只 INSERT 不删改。**本次层级订正不含任何 schema 变更**（`temporal_activity_group` 表与 `TaskMeta.group` 列原样保留，仅代码不再读写），故**无需再次执行迁移**；当时 `makemigrations --check` 剩余 3 处既有遗留迁移（redemption `match_field` choices / summary `SevenDimConfig` Meta / temporal 索引名），**已于 2026-09-17 补齐生成**，详见 `v3.58.0`。

## [2026-09-14] v3.56.0 — 三年赎回期（离职后 10 万买回的 3 年）：账单赎回归属标记 + 赎回仪表盘 · 暂停追踪 · 资金推演打通

### ✨ 新增

- **「三年赎回期」功能上线（离职后 10 万买回的 3 年风险自检）**：以 2026-09-14 提离职、计划干到 9 月底为背景，把"这 3 年钱和时间有没有流到该去的地方"做成一个可监督的子系统——设计稿见 `docs/三年赎回期-功能设计-v0.1/v0.2/v0.3` 与落地命令 `docs/三年赎回期-v0.4-落地命令清单.md`。落地坚持 v0.2 的「先钱后时间」：本版先把账单归属与钱面仪表盘做完，时间归因接口与算法已备齐但需等你重构 ATracker 类目后填规则。
- **账单赎回归属标记（v0.2 决策：单字段 + 日期自动推导 + 人工修正 + 收入要标）**：`WealthBillList` 新增 `period_tag`（为自己 / 过渡 / 外部 / 不计入，展示档"窗口外"由日期自动推算），复用既有 `necessity` 的交互范式——① 列表新增「赎回归属」小结条（各档笔数/金额，收支合计）、筛选下拉、行内归属下拉、新增表单归属单选；② 新增 `batch_period_tag`（**收支都生效**，不照搬 necessity 的"收入行清空"兜底，因为离职尾款与稿费性质完全不同）、`period_tag_stats`（含收入）；③ 窗口外（<start / >end）的账单在统计与展示上自动归为"窗口外"，窗口内按日期预填、允许人工覆盖。
- **赎回期判定层（新建 `redemption` app，4 张 managed 表）**：① `redemption_period`（单例：起止日期可编辑、本金 B2 启动现金池 10 万、暂停状态）——起止改后阶段边界/剩余天数/窗口外判定**自动重算**，支持提前或延后开始；② `redemption_pool_inject`（池注入流水，允许中途注入，余额 = 本金 + 累计注入 − 为自己净消耗）；③ `redemption_attr_rule`（时间归因外挂规则，按 ATracker 的 `task_type`/`task_name` 映射到 投向/维持/外部/流失，**绝不向 managed=False 的 ATracker 表加列**）；④ `redemption_week_snapshot`（周快照，供趋势与覆盖率历史）。
- **赎回仪表盘 `/redemption`**：窗口（起止/已过去天数/剩余天数/四阶段相位）/ 现金池（余额·已注入·为自己净消耗·滚动日均·预计可支撑到哪天）/ 四档分布 / 时间归因（四类小时 + **覆盖率**，分母暂定 12h/天，低于 50% 触发"仅基于已记录部分，谨慎解读"提示——你强调的"第 500 天误读"护栏）/ 单位赎回成本（为自己净消耗 ÷ 净赎回小时，分母暂定 8h/天）。界面刻意不考核、不排名、不断更提醒。
- **暂停追踪机制**：`RedemptionPauseView`/`RedemptionResumeView`——低谷期（离职戒断反应）可一键暂停 2 周，**暂停期不计算/不展示评价指标、不暂停记录、不发提醒、不计入考核**，是功能活过 1096 天的必要条件；恢复即用。
- **打通现有资金推演 `WealthCurrentScenario`**：`RedemptionSyncScenarioView` 把赎回池实算值同步到推演（`sync_to_scenario` 复用既有 `calculate_coverage`）；`mode=preview` 只读返回不写库，`mode=apply` 才写入 `current_cash`/`daily_budget` 并重算 support_weeks 且留 `WealthScenarioHistory`；`start_age`/`start_week` 取推演既有位置、**不覆盖你的长期推演**。
- **覆盖率硬要求落地**：无论你后续如何重构 ATracker 把刷手机/空转也纳入记录，无意识空转仍会漏记——覆盖率指标常驻时间面顶部（<50% 显"仅基于已记录部分，谨慎解读"），独立屏幕时间源列为可选增强不阻塞。

### 🧪 测试 / 验证

- 新增 `apps/wealth/tests/test_period_tag.py`（4 条：标记持久化、收支都统计、收入不被清空、批量两端生效）、`apps/redemption/tests/test_redemption.py`（7 条：配置编辑重算、暂停恢复状态机、池余额含注入、统计成功、低覆盖触发 warn、preview 不写库、归因优先级）；受影响目录（wealth/temporal/redemption）**54 passed、0 failed**，全程 vue-tsc 0 错误。
- **铁律遵守**：开发库 `sycamore` 结构变更（账单加列 + 4 张表）由用户本人执行（见 `docs/三年赎回期-v0.4-落地命令清单.md` 的幂等 SQL），AI 仅对测试库 `test_sycamore` 做了非破坏性 ADD COLUMN / CREATE TABLE IF NOT EXISTS 并跑通测试；迁移文件（wealth 0015 / redemption 0001）**只写不跑**；执行前备份纪律见命令清单第 4 节。

## [2026-09-12] v3.55.0 — 足迹地图：地市名悬停显示 · 省界叠加 · 气泡落点改权威坐标表

### ✨ 新增 / 优化

- **旅行足迹地图三处改进（省界可见 · 标签不糊 · 县市级落点准确）**：① **省界叠加**——地级市底图只有市内边界（白色细线），整片未到访区域是一块灰看不出省的分界；现用 `better-echarts-maps/dist/china.js`（34 个省级单位、约 2600 个点，足够轻）在 `chinaCitiesMap.ts` 新增 `getProvinceBorderRings()`，由 `lines` 系列以 `polyline` 形式画在最上层（`#8CA0BC` / 1.1px / `silent`），形成「省界粗深、市界细白」的层级；② **地市名称改为悬停显示**——此前 `map` 系列与气泡 `label` 默认全显，493 个区域名与气泡名互相压字糊成一片（如「泰顺县」「温州市」叠字）；现两者 `label.show: false` + `emphasis.label.show: true`，鼠标移上才浮出地市名，图例右侧加提示「鼠标移到区域上显示地市名称与到访明细」，实测默认态文字元素 **0 个**、悬停「宁德市」后正确出现该名称；③ **气泡落点改由权威坐标表驱动**——原先气泡坐标取自硬编码 `CITY_COORDS`/`DISTRICT_TO_CITY`（`tname` 未匹配到就退回上级坐标 + 随机偏移），导致「温州」「宁德」「福州」「南京」「嘉兴」「湖州」「漳州」「莆田」这 8 个不写后缀的写法**整个气泡丢失**（28 条记录里有 14 条不上图），「福鼎市」也被画到宁德市中心附近的内陆处，看起来像一块没上色的区域；现新增 `resolve_place()`（`get_coordinates()` 改为其薄封装）：优先查 `toolkit_city_coordinate`——全称 / 去后缀简称精确匹配、带省份时**本省优先**（跨省同名不再撞车）、县级市用**自己的点位**而非上级市中心，硬编码表仅作兜底；并按坐标表**规范名归并**同一地点的不同写法（「温州」+「温州市」= 一个气泡），气泡由 12 个增至 **16 个**、无重复、福鼎市回到真实坐标（120.22/27.32）；④ **热力项新增 `sources` 来源明细**（如宁德市 6 次 = 宁德×3 + 宁德市×1 + 寿宁县×1 + 福鼎市×1），tooltip 悬停即显示「明细：寿宁县×1、福鼎市×1」，直接回答「县级市的到访去哪了」——**县级市/区县并入所属地级市着色是刻意口径**（地级市底图没有县级多边形），明细让归属透明；⑤ 测试新增 7 条（来源明细 / 县级市独立点位 / 简称归一 / 省份感知 / 硬编码兜底 / 同地点气泡归并 / 县级市气泡不塌陷），全量 159 → **166 passed**、vue-tsc 0 错误


## [2026-09-11] v3.54.0 — 决策追踪器自定义倾向 · 旅行流水线打通（心愿→路线→计划→足迹）· 城市坐标类型化

### ✨ 新增

- **旅行足迹热力粒度下沉：省份 → 地级市 + 修复城市气泡从未渲染**：① 原先「省份热力」是整省一个色块（福建一整块深蓝，看不出到底去了福州还是厦门），现下沉到**地级市**——`MapDataService` 新增 `resolve_prefecture(city, parent)` 把每条记录归到地级市：`tname` 本身是地级市（「温州市」/简称「温州」）直接采用；`tname` 是县级市/区县（「福鼎市」「泰顺县」）则归到 `parentnode`（宁德市 / 温州市）；直辖市（parent=北京市）保留区名以匹配地图「按区渲染」的口径；无从判定则跳过。索引由 `toolkit_city_coordinate` 的地级市/自治州/地区/盟构建（全称 + 去后缀简称），进程内缓存并提供 `reset_prefecture_index()` 主动失效。实测 27 条记录 **27/27 归属正确**（义乌市 ← 金华市、泰顺县 ← 温州市），热力由 3 个省份细化为 **12 个地级市**；② 新增档位口径 `heat_level()`：1 次 = 偶尔 / 2 次 = 多次 / 3-4 次 = 频繁 / ≥5 次 = 深度游，与页面图例一一对应；`heatmap` 项由 `{province, intensity}` 改为 `{name, count, level}`，并新增 `heat_max` 供图例显示「最高 N 次」；③ **前端底图换成地级市**：`better-echarts-maps` 的 `china.js` 只有省级边界，但其 `china-provinces.js` 实为按省打包的地级市 GeoJSON（38 份，含 `-contour` 描边副本）——新增 `modules/travel/utils/chinaCitiesMap.ts` 把各省要素合并为一张全国地级市地图（**493 个可着色区域**，全国区域名唯一：地级市 + 自治州/地区/盟 + 直辖市下辖区县 + 省直辖县级市），并提供 `resolveRegionName()` 容错对齐（精确 → 去后缀再补各种后缀，解决「毕节市」↔ 地图「毕节地区」、「日喀则市」↔「日喀则地区」、「桃园市」↔「桃园县」等撤地设市旧称差异，另加别名表兜底），对齐失败会 `console.warn` 提示；④ `visualMap` 由连续渐变改为**分段**（4 档配色与图例一致）+ `show: false` 沿用页面图例，未去过区域统一 `#E9EDF3`；⑤ **顺带修复一个潜伏 bug**：`scatter` 声明了 `coordinateSystem: 'geo'` 但 option 里**从未定义 `geo` 组件**，ECharts 直接丢弃该系列——**城市气泡此前一直没有渲染**（截图上确实看不到）；现改为显式 `geo` 组件 + 热力层 `map` 系列 `geoIndex: 0` 绑定，气泡恢复正常且漫游/缩放与底图同步；同时 `visualMap` 未限定 `seriesIndex` 会把气泡一起染色（使气泡自身的满意度配色失效），已限定为 `seriesIndex: 0`；⑥ 用 ECharts SSR 渲染实测：493 个区域中 12 个已到访各按档位着色（44 个多边形环全部落位）、11 个气泡渲染成功；新增 15 条 pytest（归属解析四种情形 / 档位映射 / 按地级市聚合 / 倒序与字段 / 年份过滤 / 空数据 / 接口），全量 144 → **159 passed**、vue-tsc 0 错误
- **心愿清单第三批导入：早市 / 夜市 / 书店 200 条 + 新增「早市」分类（迁移 travel 0007）**：① 分类口径新增 `早市`（🌅 早市），`CATEGORY_CHOICES` 11 → 12 类，前端 `CATEGORY_LABELS` 与「值得反复」文案同步（美食 · 早市 · 夜市 = 反复吃，其余 = 反复去），筛选下拉因遍历 `CATEGORY_LABELS` 自动出现新分类；② 导入用户整理的「早市、夜市和书店」地域清单 **200 条**（福建 27 / 浙江 32 / 广东 27 / 江西 25 / 其他地区精选 89），按 **(城市, 名称)** 去重——**刻意不做全局同名去重**：「晓风书屋」在福州/杭州/漳州、「愈欣书店」在惠州/赣州、「方所」在广州/成都，都是真实并存的独立条目，按名去重会误杀；③ 另显式别名跳过 5 条**同址异名**（北京·单向空间 ↔ 存量「单向街」、杭州·河坊街夜市 ↔「河坊街」、泉州·西街夜市 ↔「西街」、西安·回民街夜市 ↔「回民街」、西双版纳·告庄星光夜市 ↔「告庄西双景」），避免同一地点在地图上重复打点；④ 合计跳过 13 条存量已有，**实插 187 条**（早市 21 / 夜市 70 / 书店 96），心愿单 708 → **895 条**；⑤ 坐标解析直接复用 `views.resolve_wish_coords`（省份感知三级解析）保证与页面手工新增同源，187/187 全部解析、**省份零错配**（POI 级名称为城市级定位，与存量美食口径一致）；district 复用最近邻（≤60km）口径回填 187 条，省/市/区县筛选自动收敛；⑥ 脚本沉淀 `backend/travel_import_markets.py`（dry-run / APPLY=1，`ALIAS_SKIP` 集中维护同址异名），迁移 0007 仅 choices 变更（无表结构 DDL），执行前备份 `db_backups/travel_wish_before_markets_20260911.sql`；全量 144 passed、vue-tsc 0 错误
- **旅行流水线打通：心愿打卡 → 行程日志 → 沉淀足迹（迁移 travel 0006）**：此前「心愿单打卡」只在心里记一笔、从不落到「旅行足迹」，四个模块各管一段。本次把打卡结果沉淀为可读、可统计的行程日志——① `TravelWish` 新增 `visit_plan`（归属行程，可空外键）与 `visit_record_id`（已沉淀的足迹 ID）两列，迁移 pure additive；② 新增只读接口 `GET /travel/trip-log/`：把 **status=已打卡且 `visited_at` 非空** 的心愿按「日期 + 地点」聚合为一天一张卡（`days[].items[]` 含名称/分类/评分/评价/是否值得反复/是否已沉淀），地点键做行政后缀归一（「南京」与「南京市」合并为同一天，且不剥离单字「州」以免误伤「杭州」），支持 `from`/`to`/`plan`/`city` 过滤，返回 `total_days`/`total_items`/`pending_days`；③ 新增 `POST /travel/trip-log/consolidate/`：把某天某地的打卡清单**显式沉淀**为一条 `travel_list_info` 足迹（评分默认取当日均分、摘要默认拼接打卡名、坐标取打卡点均值，并回写 `visit_record_id`），**只新增不改存量**；④ **为何不做「打卡即自动写表」**：`travel_list_info` 是 `managed=False` 历史表，一趟多城行程会被拆成十几条足迹、污染地图热力与年份趋势，且与手工记录混在一起无法区分——改为「日志自动聚合 + 沉淀手动确认」；⑤ 足迹页（`/travel`）新增「🗺️ 足迹地图 / 📔 行程日志」双视图：日志按日期倒序渲染，一天一张卡（虚线边框=临时日志，实线=已沉淀并显示花费/满意度/同行），卡内列出当日打卡点（美食/景点图标、星级、「值得反复」标签、评价摘要），并提供「沉淀为足迹」弹窗（花费/停留天数/满意度/同行伙伴/摘要，满意度默认取当日均分）与日期区间筛选；⑥ 心愿打卡弹窗新增「本次行程」下拉（把打卡归属到某趟计划），打卡成功提示改为「已进入行程日志」；⑦ 计划内勾选子项时，若该子项关联心愿则弹出轻量打卡录入（可点「只打卡」跳过），保证计划打卡与心愿打卡在日志里字段一致；测试库同步 ALTER + conftest 镜像，新增 11 条 pytest（聚合分组/后缀归一/未打卡排除/日期过滤/沉淀与回写/重复沉淀拦截/评分校验/路线预检/带心愿成计划/无心愿占位/参数校验），全量 133 → **144 passed**
- **路线推演 ↔ 旅行计划双向打通 + 路线推演主入口迁入旅行模块**：① **路线 → 计划**：新增 `POST /travel/plans/route-preview/`（按站返回该城「想去」心愿，地点键同样做后缀归一）与 `POST /travel/plans/from-route/`（由「出发地 → 多目的地」生成计划：计划名/出发日期可填，默认名「南京等 2 站」，备注记「由路线推演生成：福州 → 南京 → 杭州」；**勾选心愿则按分类映射 food/scenic 子项并挂 `wish` 外键、心愿转「已列入计划」**，未勾选则每站生成一条「待细化」占位项）；路线页页头新增「生成旅行计划」按钮 + 弹窗（路线预览 + 出发日期 + 逐站心愿勾选，默认全选）；② **计划 → 路线**：计划卡新增「🚂 路线」按钮，从计划备注解析出完整站点序列后跳 `/travel/route?origin=&destinations=` 自动推演（无备注则回落到 destination）；③ **归属迁移**：「🚂 旅行路线推演」本质是旅行计划的编排器，与 `TravelPlan` 强耦合、与心愿地图共用同一张坐标表，放在 `category=other` 的通用工具箱里与决策追踪器/报价/电价并列，会让用户在编排行程时根本想不起来去工具箱找——前端 `TravelRoute.vue` 迁至 `modules/travel/views/TravelRouteView.vue`，新增 `/travel/route` 路由与侧边栏「路线推演」菜单项（旅行四件套 旅行记录 → 心愿单 → 计划 → 路线推演 归入「连接与足迹」分组，计划页同时取消默认归档）；工具箱侧保留一张跳转卡片（进入 `/toolkit/travel-route` 提示「已迁入旅行模块」并给跳转按钮），**后端表 `toolkit_travel_route_preset` 与 `/api/toolkit/travel-routes/` 接口原封不动**，零表迁移风险；vue-tsc 0 错误
- **（顺带修复）`TravelWishSerializer` 缺 `timezone` 导入**：`update()` 内 `timezone.localdate()` 未导入模块，一旦通过 PATCH 修改心愿状态即 `NameError`（此前测试与页面都未覆盖该路径），已补 `from django.utils import timezone`
- **旅行心愿单（新表 travel_wish + 地图点亮 + 一键进计划，迁移 travel 0003）**：把「想去的地方/想吃的东西」从脑内清单变成可管理、可打卡、可进预算的库——① 后端新增 `TravelWish`（`travel_wish` 表：名称/分类/省市/经纬度/状态/打卡日期/备注，分类 11 类含景点·美食·古镇·寺庙·自然·大学·书店·街区·夜市·路线·其他，状态 想去 → 已列入计划 → 已打卡），`TravelPlanItem` 新增 `wish` 外键打通计划；② 接口：`/wishes/` CRUD（不分页，支持分类/状态/省份/城市/搜索筛选，创建时自动解析坐标）、`/wishes/<id>/mark_visited/`（打卡/取消打卡）、`/wishes/<id>/add_to_plan/`（指定已有计划或自动新建「XX之旅」，按分类映射 food/scenic 子项，重复加入被拒）、`/wishes/stats/`；③ **打卡闭环**：计划子项勾选完成 → 关联心愿自动转「已打卡」并记日期，取消勾选回「已列入计划」；计划编辑整体替换明细时按「类型|名称」复原心愿关联，被移除的心愿回退「想去」；④ 前端新增 `/travel/wishes`「旅行心愿单」页（侧边栏连接与足迹分组）：统计 chips（总数/想去/已列入计划/已打卡/已定位）+ ECharts 中国地图按状态三色点亮（想去橙 / 已列入计划蓝 / 已打卡绿）+ 分类·状态·省份·搜索四重筛选 + 按省份分组卡片（点击编辑、一键打卡、加入计划、删除）+ 新建/编辑弹窗；⑤ **导入能力**：脚本 `backend/travel_import_wishes.py` 把私人清单（300 景点 + 262 美食目的地）归一化导入——城市前缀归一（延吉→延边、建水/蒙自→红河、敦煌→酒泉等）、跨清单去重（鸡鸣寺/先锋书店/南京大学/老门东/中央大街等 12+ 处）、坐标三级解析（名称精确 → 景区模糊 → 城市定位，解析率 98.7%，仅“潮汕”7 条无坐标回退省份），实际入库 **526 条**；同时给 `toolkit_city_coordinate` 补 **50 条高置信度 POI 坐标**（南京及周边 30 条：紫金山/明孝陵/鸡鸣寺/玄武湖/夫子庙/老门东/栖霞山/牛首山/南京博物院/总统府/高淳老街/先锋书店等 + 西塘/同里/南浔/甪直/木渎/锦溪/千灯/灵隐寺/寒山寺/塔尔寺/鸣沙山月牙泉/洪崖洞/宽窄巷子/平江路/东关街 等 20 条），这些地方在旅行路线地图里也能直接搜到；⑥ 迁移 travel 0003 纯 additive（新表 + 可空外键），备份 `db_backups/travel_tables_before_wish_20260911.sql`；pytest 新增 9 条（创建/坐标解析/统计/打卡往返/加入计划与重复拦截/子项打卡联动/明细替换复原/筛选），全量 120 → **129 passed**
- **心愿地图跟随筛选缩放 + 打卡升级为「打卡记录」（迁移 travel 0005）**：① **地图联动**：此前地图只在加载/刷新时绘制一次，筛选变了点位不动、视野永远是全国——现 `watch` 分类/状态/省/市/区县/搜索六项筛选，任一变化即重绘；并按筛选结果的经纬度包围盒推算 `geo.center` 与 `zoom`（跨度越小放得越大，单点按 0.02° 兜底、上限 9 级），实现「选某个地市 → 地图自动聚焦到该地市」；点位 tooltip 补齐城市·区县/状态/分类/评分/值得反复；「值得反复」的点符号加大并加白描边，一眼可辨；② **打卡从「一键切换」升级为「打卡记录」**：`TravelWish` 新增 `visit_rating`（1-5 星，可空）、`visit_notes`（打卡评价）、`worth_revisit`（是否值得反复），迁移 travel 0005 纯 additive；新增接口 `POST /wishes/<id>/record_visit/`（body: visited_at / visit_rating / visit_notes / worth_revisit，日期缺省今天、格式非法或评分越界返回 400），未打卡调用即「打卡+记录」、已打卡调用即「修改记录」；原 `mark_visited/` 保留给「取消打卡」（状态回退、打卡日期清空，评价与「值得反复」保留，便于重新打卡不丢内容）；③ **前端**：点「✓ 打卡」弹出记录弹窗（打卡日期默认今天 + `el-rate` 星级 + 文字评价 + 「值得反复」开关），已打卡的卡片按钮变「✎ 记录」可随时回改、并新增「↩ 取消打卡」；卡片展示 ★ 星级、「🔁 反复吃 / 反复去」（按分类区分：美食·夜市=反复吃，其余=反复去）、打卡日期与评价摘要；④ 测试库同步 ALTER + conftest 镜像，新增 4 条 pytest（记录全字段 / 默认日期与二次修改 / 评分越界与日期格式校验 / 取消打卡保留记录），全量 129 → **133 passed**、vue-tsc 0 错误
- **行政区划订正：梅列区并入三元区 + 沙县/长泰/龙海撤县设区（纯数据订正，无代码改动）**：坐标表沿用 2020 年行政区划数据，未跟上 2021 年国批调整（闽政文〔2021〕49 号）——① **撤销梅列区、三元区，设立新三元区**（原两区行政区域为新三元区行政区域，区政府驻原梅列区列东街道新市北路 836 号）：三元区坐标由 117.61/26.23 更新为合并后区政府驻地 117.6459/26.2717，4 条落在「梅列区」的心愿（沙县拌面/沙县扁肉/熏鸭/蛋菰）区县重映射为「三元区」；② 同批 **沙县 → 沙县区**（区划代码 350405）、**长泰县 → 长泰区**、**龙海市 → 龙海区**，`name`/`full_name`/`city_type`/`pinyin` 一并订正（县、县级市 → 区），坐标为原政府驻地故沿用不变；③ 订正后 `resolve_wish_coords` 的城市定位仍正常（「沙县/龙海/长泰」按 startswith 命中新区名），心愿单省份筛选与区县下拉自动收敛；④ 脚本沉淀 `backend/city_fix_admin_2021.py`（只做 UPDATE，dry-run / APPLY=1）；已撤销的「梅列区」行需删除（否则最近邻匹配会把新三元区的心愿抢走），该 DELETE 由用户本人手动执行，执行前已备份 `db_backups/city_and_wish_before_sanming_merge_20260911.sql`
- **心愿清单第二批导入：闽浙粤赣四省美食 189 条 + 坐标解析加固**：① 导入用户整理的四省美食清单 **211 条**（福建 60 / 浙江 61 / 广东 55 / 江西 35，含城市标注），按「(城市, 名称) + 去掉地名前缀的核心名」双重去重（如存量「顺德双皮奶」↔ 新条目「双皮奶」、「潮汕牛肉丸」↔「牛肉丸」）跳过 22 条存量已有，**实插 189 条**，县市级条目按具体县市落位（福清/连江/晋江/石狮/永春/惠安/龙游/开化/缙云/连州/宁都/瑞金/铅山/弋阳/靖安/高安/分宜/黎川…）；② 修复**短名跨省撞车**缺陷——坐标表中「连江」（台湾省连江县，实为台北坐标）与福建「连江县」、「三门」（河南三门峡）与浙江「三门县」同名，原解析按精确名优先导致「连江鱼丸」落到台北、「三门青蟹」落到河南；现 `resolve_wish_coords` 增加**省份感知 + 排除「其他」类同名行**的双重优先级，复核 709 条后修正 2 条错配；③ 「潮汕」系列存量 7 条原无坐标（地图不可见），统一回填汕头市中心坐标（116.68/23.35）并纳入区县体系（金平区）；④ 区县回填脚本重算，704/709 条有区县（仅「雪乡」90km 超距 + 4 条福建通用小吃待定城市）；脚本沉淀 `backend/travel_import_foods_2nd.py`、`backend/travel_fix_coords_province_aware.py`（均支持 dry-run / APPLY=1）；全量 pytest 129 passed
- **心愿单地图修复 + 地点筛选升级省/市/区县三级联动（迁移 travel 0004）**：① 修复心愿地图中国边界碎裂（只剩零星轮廓、点位飘出图外）——根因是 `registerMap('china', ...)` 误把 `better-echarts-maps` 整个模块对象当 GeoJSON 注册，改为与 `ChinaHeatmap` 一致的提取写法（`pkg.China?.[0]?.[1]`）后底图正常；② `TravelWish` 新增 `district`（区县）字段，用 `toolkit_city_coordinate` 的 3006 个区/县/县级市坐标对 519 条有坐标心愿做最近邻匹配（≤60km），**回填 518 条**（仅「雪乡」最近 90km 保持为空），坐标为城市中心的心愿落至市中心所在区（如上海批量心愿→黄浦区），属预期口径；③ 心愿单筛选栏由「省份」单级升级为**省 → 市 → 区县三级联动**（上级变更自动清空下级、选项由数据实时派生、支持输入过滤），卡片定位行同步显示「城市 · 区县」；脚本 `backend/travel_match_district.py` 沉淀（APPLY=1 才写库，可 dry-run 复跑），迁移 0004 纯 additive，测试库同步 ALTER + conftest 镜像，全量 pytest 129 passed、vue-tsc 0 错误
- **全国行政区划坐标补全（797 → 3693 条，纯增量零删除）**：`toolkit_city_coordinate` 原只有部分区县有坐标（区 119 / 县 115），旅行模块「省→市→区县」三级联动大部分区县查不到——以国家统计局 2020 行政区划数据（kakuilan/china_area_mysql，GCJ-02 坐标，经 test_sycamore 中转库导入）补全缺失的市级与区县级：区县 +2460（区 1201 / 县 1411 / 县级市 405 / 旗 49 / 乡 146 / 镇 102 等，港澳台全覆盖：香港 22 区、澳门 11、台湾 391），北京/上海/天津/重庆下辖区全部补齐；映射遵循存量风格（name 不带后缀、full_name 为「省+市+区县」全称、直辖市「北京市朝阳区」、省直辖「海南省省直辖文昌市」），并排除开发区/园区/管理区等 141 条伪区划。执行前已备份 `db_backups/city_coordinate_before_completion_20260911.sql`；说明：①存量 12 个自治州标为「地级市」（如阿坝/大理），级联接口按 `city_type='地级市'` 过滤恰好可用，刻意不改；②中转表 `test_sycamore.cnarea_2020` 保留，可手动 DROP
- **城市坐标 name 类型化 + 知名景点入库（纯数据改动 + 前端兜底）**：① `toolkit_city_coordinate.name` 由不带行政后缀的短名（福清/同安/大理）统一升级为**带类型名**（福清市/福鼎市/同安区/大理州），改名 3482 行——规则从 `full_name` 自动推导：直辖市取全称（北京市），地级市取省级剥离后的带后缀名（合肥市），12 个误标地级市的自治州按「短名+州」（大理州），自治州/地区/盟同理（黔东南州/和田地区），区/县/县级市/旗/乡/镇剥离省与父级前缀取官方全名（景宁畲族自治县/达尔罕茂明安联合旗），name 本身已带后缀的（云县/乌审旗/芒市）与景区/其他类保持不变；② 新增 **80 个全国知名 5A 级景点**（`city_type='景区'`，与存量 14 条同格式）：故宫/八达岭长城/西湖/黄山/鼓浪屿/武夷山/张家界/九寨沟/布达拉宫/兵马俑/莫高窟/喀纳斯/日月潭等，覆盖全部省级行政区（含港澳台），含经纬度与拼音；③ 前端 `TravelRoute.vue` 新增 `findCity` 兜底匹配（精确 → 模糊包含），历史路线预设里存的旧短名（如「北京」）仍能命中新名（北京市），地图渲染与中心点/缩放计算不受影响；改名与插入均为纯增量/重命名零删除，表总行数 3693 → 3773，执行前已备份 `db_backups/city_coordinate_before_rename_20260911.sql`，改名规则脚本沉淀于 `backend/city_rename_typed.py`、景点清单于 `backend/city_add_scenic.py`（均可 dry-run 复跑）
- **修复系统性缺陷：点菜单偶发整页空白（需手动刷新才恢复）**：两处根因一并处理——① `AppLayout` 的 `router-view` 外包了 `<transition mode="out-in">` 切换动画，快速连续点击菜单时过渡会竞争，新页面的 enter 动画不触发，主内容区永久空白（已移除该动画包裹层，切换改为直接渲染）；② 全部页面均为懒加载 chunk，前端重新构建后旧 hash 文件失效，开着旧页面点菜单会动态导入失败导致空白（`router/index.ts` 新增 `router.onError`：识别到动态导入/chunk 加载失败时自动整页跳转目标路由，免手动刷新）；③ `main.ts` 新增全局 `errorHandler`，组件渲染/初始化报错时在控制台打出明确日志，避免「静默空白无迹可查」。顺带确认：路由无任何 `meta.keepAlive`，现有 `keep-alive` 的 `include` 恒为空数组，页面缓存实际未启用（保留该机制不影响行为，供后续按需启用）
- **书名号《》展示层统一（数据零改动）**：书名的存入口径本来是「剥离《》后入库」（`BookSerializer.validate_btitle`），但早期导入的存量记录带着《》，导致列表里有的带有的不带、看着不一致。现统一为**展示层补书名号**：① 列表「书名」列、删除确认文案一律渲染为《书名》；② 编辑弹窗载入时剥离存量《》（保存后数据自然收敛为裸名），输入框下加提示「书名号《》会自动补全，无需手动输入」，提交时也统一剥离；③ 搜索词同步剥离《》再查询（带不带书名号都搜得到）。数据与接口零改动，无需清洗
- **图书标签接入系统预设 + 日记流式点选（迁移 core 0006）**：编辑书籍弹窗的标签原为写死四项（经典必读/强烈推荐/值得重读/思维启发）的 `el-select` 下拉——① `SystemPreset` 预设类型新增 `book_tags`（图书预设标签），并播种默认四项，可在「系统预设管理」中自行增删维护；② 编辑弹窗标签区改为与日记流一致的点选交互：「常用：」预设标签单击切换选中（蓝色高亮），已有但不在预设中的历史标签显示为可关闭的橙色标签，「+ 自定义」输入框即时添加，下方提示预设维护入口。存量书籍标签数据与提交格式（逗号拼接）零改动；迁移前已备份 `db_backups/system_preset_before_book_tags_20260911.sql`
- **财富贡献图收支配色对调（绿=收入多 / 红=支出多）**：原口径「红=收入多 / 绿=支出多」观感别扭——经一段时间使用后调整为正负模式色阶对调，`ContributionGraph` 正负模式 sign>0（净值正）改用绿色阶（#9BE9A8→#216E39）、sign<0 改用红色阶（#FCA5A5→#B91C1C），图例色块同步（绿=收入 / 红=支出），页面标签文案更新为「单日收支净值（绿=收入多 / 红=支出多）」；该模式仅财富贡献图开启（健康/时间域贡献图为单向色阶 `posNeg=false`，不受影响）
- **决策追踪器支持自定义倾向选项（迁移 0023）**：原「现在的倾向」写死 想继续/不想继续/不确定 三项，但决策内容千差万别（如「眼镜啥时候买」根本不是继不继续的问题）——① `DecisionTracker` 新增 `lean_options`（JSON 字符串数组，2–6 项、每项 ≤20 字、非空去重，留空/null/空数组 = 用默认三项），`DecisionRecord.tendency` 由 varchar(10)+固定 choices 放宽为 varchar(50)（自定义追踪直接把选项文字存进 tendency，默认追踪仍存 continue/quit/uncertain，存量 24 条记录零影响）；② 序列化器校验：lean_options 格式（项数/长度/去重），tendency 必须属于所属追踪的选项（默认追踪拒收中文、自定义追踪拒收 continue，违者 400）；③ `preview` / `report` 按各自追踪的选项泛化统计——`tendency_stats`/`monthly_trend`/`reasons` 遍历自定义选项键，并返回 `options`（key+label）供前端渲染；结论文案自定义时为「目前 X% 倾向「选项」，其中高强度占 n/m」；④ 加权分口径分化：默认三选项沿用 (quit−continue) 双向分，自定义选项改「主导加权 − 次主导加权」优势分（恒 ≥ 0），`lean_label` 直接回显选项文字；⑤ 前端：新建决策弹窗新增「倾向选项」编辑器（动态增删行，留空提示用默认三项），记录弹窗倾向按钮按所属追踪选项渲染（默认三项保留 ✓/✗/？图标），报告弹窗理由分列/倾向条形图/月度趋势 ECharts 系列全部由 `options` 驱动（自定义选项用循环色板），卡片加权标签对自定义追踪改中性色并标注「主导加权差」。迁移 0023 纯 additive（加列 + 加宽），开发库已备份（`db_backups/decision_tables_before_lean_options_20260911.sql`，2 追踪 24 记录）后应用；pytest 新增 3 条（自定义全链路 / tendency 越界 400 / lean_options 校验），全量 120 passed

## [2026-09-10] v3.53.0 — 决策追踪器强度加权预览 · 工具箱瘦身（移除资金排程与 4 个死透模块）

### ✨ 新增

- **倾向随时预览（不必等到期）**：此前只能在 `end_date` 到期后生成汇总报告——观察期 54 天而采样集中在前 2 天时，中途零反馈极易放弃记录。后端新增 `GET decision-trackers/preview/`（`detail=False`，支持 `?tracker=<id>` / `?status=`），返回每条决策 quit/continue/uncertain 的**条数占比**、**强度加权分数**与**连续断记天数**及结论文案（如「目前 70.6% 倾向离开，其中高强度占 5/12」）；前端顶部横幅改由 preview 驱动，追踪卡片新增「📈 当前倾向」一行
- **观察期内封存倾向结论（本期修订）**：`preview` 数据照算，但**观察中**的决策**刻意不展示**结论——中途看到「目前 73.9% 倾向离开」会反向影响后续记录与判断，等于污染样本。卡片在观察期改为「🔒 倾向结论已封存，观察期结束后展示」（断记时替换为「已 N 天未记录 / 观察期内结论暂不展示，先坚持记录」），顶栏横幅也不再播报中途结论，只保留「到期/临近/断记」这类过程提醒；结论只在**尘埃落定后**（已到期 / 已决策 / 已归档）展示
- **强度加权口径**：强度即权重（1–5）——`weighted[t]` = 该倾向下强度之和；`weighted_score = (quit 加权 − continue 加权) / 两者加权和 × 100`，正数偏离开、负数偏留下（不确定不计入分母）；`high_count` 以强度 ≥4（强/很强）计；`tendency_stats` 逐档返回 weighted / weighted_percent / avg_intensity / high_count / high_ratio
- **断记提醒**：连续 ≥3 天没有新记录（无记录则以观察开始日计）即置 `needs_reminder` 并返回提醒文案，前端以红色横幅提示，避免长观察期中断采样
- **现金流推演结果加月/年换算**：推演结果此前只显示「可支撑 X 周」单一粒度——其下新增换算行「≈ X 个月 · X 年」（按 1 年 = 52.14 周 / 1 月 = 4.345 周，各保留 1 位小数，如 219 周 ≈ 50.4 个月 · 4.2 年），三个时间量级一眼可感；纯前端展示层换算，后端推演接口与逻辑不动，永不耗尽（∞）时不显示换算行
- **现金流推演接入真实数据与人生规划视角（P0 三连）**：① 「当前现金」旁新增「带入活期」——拉取现金盘点最新快照的活期总额（`/wealth/cashflow/overview/` → `summary.flow_total`）一键填入；「每日预算」旁新增「按上月日均」——取上月账单日均支出（`/wealth/review/monthly_summary/` → `avg_daily_expense`）一键填入，告别拍脑袋手输；② 新增「月被动收入」输入，推演按**净消耗**计算（净日预算 = 每日预算 − 月收入 ÷ 30.44，下限 0），结果区首行展示「净消耗 X 元/天（预算 − 收入折算）」明细，工具从「坐吃山空倒计时」升级为「含收入流的财务推演」；③ 结果区新增**自由缺口**行——填了日利率且净消耗 > 0 时，按「所需本金 = 净日消耗 ÷ 日利率」测算利息覆盖支出所需的自由本金，显示「还差 ¥N · 达 ¥M 后利息可覆盖净支出」，把恐惧（47 岁耗尽）转成可执行目标；「预计耗尽」下方新增绝对日期换算「≈ 2043 年 3 月」，周龄模型直观化。以上全部纯前端实现（净预算折算后走现有 `calculate_coverage` 接口），后端零改动
- **人生现金流页排版优化（功能零改动）**：推演卡表单由 6 字段单列纵排改为**两列栅格**（年龄/周数、现金/预算、收入/利率各占一行，提示与按钮跨双列），输入区高度约减半，消除 16 列宽容器下的右侧大片留白；两条输入提示合并为一行；窄屏（≤768px）自动回落单列；输入框改弹性宽度适配栅格。仅模板顺序与样式调整，不涉及任何接口与逻辑
- **收件箱排版优化（功能零改动）**：① 页面容器宽度 `max-width` 900px → **1200px**，与其他主要页面（食物/产出/关系/财富月历等）对齐，消除收件箱独有的大片两侧留白；② 快速录入主输入框由默认高度（32px / 13px 字号）加大至 40px 高 / 15px 字号，保存按钮同步加大并等高对齐（min-width 88px），「补充详情」textarea 2 行 → 3 行；类别/优先级/截止日期三个选项控件由 small 号升为 default 号（宽度 100/90/130 → 120/110/150），更易点选；录入卡内边距与行距同步放宽。仅样式调整，录入交互（Enter 保存 / 字段逻辑 / 接口）不变

### ♻️ 重构

- **记录强度由枚举改数值（迁移 0020）**：`DecisionRecord.intensity` 从 varchar 枚举「低/中/高」改为 `PositiveSmallIntegerField`（1–5，choices 很弱/弱/中/强/很强，带 1–5 校验）——迁移先把「低/中/高」就地改写为 2/3/4 再转列类型（可反向回退），开发库 17 条记录映射结果 低 1→2、中 10→3、高 6→4；旧 varchar 下 `AVG(intensity)` 返回 0 无法加权的问题随之解除。前端记录弹窗强度改 1–5 五档单选（带档位标签），明细/报告按数值显示「3 · 中」并分档着色
- `report` 理由明细新增 `intensity_label`（数值 → 中文档位）

### 🗑️ 移除

- **资金排程功能整体移除（FundSchedule / FundScheduleItem）**：快照式资金排程（手里现金 → 预留硬性/弹性 → 剩余可分配 + 历史快照列表 + 导入固定开销）经两周观察确认与预期不符、实际未使用——后端删 `models/fund_schedule.py`、`services/fund_schedule_service.py`、`views/fund_schedule_views.py`、`FundScheduleSerializer`、`/api/wealth/fund-schedule/` 路由、`migrate_json_to_tables` 一次性命令，并加迁移 0014 删两表（两张表已于 2026-09-10 由本人手动 DROP，0014 待 `--fake` 补记迁移记录）；前端删 `FundScheduleBoard.vue` + `api/fundSchedule.ts`、`/wealth/fund` 路由、财富 hub「资金排程」tab、`wealthTypes.ts` 中 4 个专用类型；前后端 README 同步摘除该章节
- **连带澄清（不影响其他功能）**：① 财富 hub 其余 6 个 tab（宏观热力图/月度日历/月度复盘/定期存款/现金盘点/贡献图）与 `/api/wealth/bills/` 均正常——`bills` 与被删的 `fund-schedule` 共用同一 router，重建 router 时保留了 bills 注册；② 固定开销不受影响——`wealth/api/fundSchedule.ts` 里的 `getFixedExpenseList` 属重复定义，固定开销实际走工具箱 `toolkitApi.ts`；③ 第六轮审计「`linked_expense_id` 悬空」「固定开销两套口径差 463.13 元」两条行动指令随功能移除自动作废
- **三个「死透」工具移除（复盘工具箱 / 语言训练 / 环境校准）**：第六轮审计显示三者近 30 天与近 7 天写入均为 0（复盘工具箱全表 0 条、语言训练末条 2026-07-06、环境校准末条 2026-08-04），确认不再使用——后端删 `ReviewRecord` / `LanguageTraining` / `EnvironmentAudit` 三个模型 + 三个序列化器 + 三个 ViewSet + `/review-records/`、`/language-training/`、`/environment-audits/` 三组路由 + `tools/` 下三个工具类（工具注册表 16 → 13）+ 仅服务于环境校准判定的 `_calculate_verdict()`，并加迁移 0021 删三表（已于 2026-09-10 由本人执行 migrate 应用）；前端删 `ReviewToolbox.vue` / `LanguageTrainer.vue` / `EnvironmentAudit.vue` 三个组件 + 路由 `/toolkit/review-toolbox`、`/toolkit/language-trainer`（含各自的 `-tool` 重定向）+ `toolkitApi.ts` 三组 API + `ToolDetail.vue` 两个嵌入分支及其数据型工具名单条目
- **上述移除的连带摘除**：① `core` 全局搜索去掉「🧭 复盘」模块（`ReviewRecord` 查询段），`SearchBar.vue` 跳转表去掉 `review → /toolkit/review-toolbox` 映射；② 职业能量审计去掉「环境分值已连续 N 个月拖后腿 → 去做一次环境校准」提示条及配套计算（`goToEnvAudit` 指向的页面已不存在），其自身 `env_score` 字段与打分逻辑不受影响
- **决策日志整体移除（DecisionLog）**：记录重大决策 + 分析决策偏误（背景/选项/选择理由/恐惧指数/实际结果/偏误）这套流程未被用起来——后端删 `DecisionLog` 模型、`DecisionLogSerializer`、`DecisionLogViewSet`、`/decision-logs/` 路由、`tools/decision_log.py` 工具类（工具注册表 13 → 12），并加迁移 0022 删表（已于 2026-09-10 由本人执行 migrate 应用）；前端删 `DecisionLog.vue` + `api/decisionLogApi.ts`、路由 `/toolkit/decision-log` 与 `-tool` 重定向、`ToolkitDashboard.vue` 分类映射
- **决策日志的连带摘除（个人画像）**：个人画像「📋 决策质量」卡片的唯一数据源就是 `DecisionLog`（`summary/views.py` 的 `_decision_profile()`），数据源消失后卡片必然空白——后端删该方法与其在 `profile/` 响应中的 `decision` 字段，前端删 `DecisionProfile` 接口、`PersonalProfile` 的 `decision` 字段、卡片模板与「数据不足」判断项（剩余 5 张卡片栅格布局仍成立）。**注意区分**：同文件内 `profile.energy.latest.decision` 是职业能量审计的判定文字，与决策日志无关，已保留
- **保留项（易混淆，务必区分）**：决策日志（`DecisionLog`）与**决策追踪器**（`DecisionTracker` + `DecisionRecord`）是两套独立功能，后者为长期观察型决策，**本次完整保留**——模型/接口/路由/前端页面/2 条 pytest 均不受影响；`decision-records` 是决策追踪器的记录子表路由，同样保留

### 🐛 修复

- **记录日期默认值差一天（UTC 偏移）**：`todayISO()` 走 `toISOString()` 取 UTC 日期，UTC+8 凌晨会把默认记录日期算成前一天——改为本地时区拼装，并抽出 `toLocalISO()` 供「延长观察」的默认新结束日期复用（与 v3.51.0 在 AI 问答库修的同类问题一致）
- **conftest 测试库镜像 DDL 同步**：`toolkit_decision_record.intensity` 由 `varchar(10)` 改为 `smallint unsigned`

### 🧪 测试

- 新增 2 条 pytest（加权分数与手工计算一致：quit 强度 5+1 / continue 强度 3 → 加权分 33.3、quit 加权占比 66.7%；零记录时 preview 全零、不虚报倾向，并顺带覆盖断记判定），全量 **121 passed**
- 随资金排程移除，删掉其 4 条 pytest（`tests/test_fund_schedule.py`）与仅含该项服务的 `tests.py`（7 条 Django TestCase），移除后全量 **117 passed**

## [2026-09-09] v3.52.0 — AI 问答库交互体验改进（PM 评审落地 · 快记流 / md 渲染 / 采纳回顾）

### ♻️ 重构

- **快记流：新建主题 + 首轮回答一弹窗归档（P0①）**：原「新建主题弹窗(5 字段) → 列表 → 详情 → 添加首轮回答弹窗(7 字段)」一条问答要 2 弹窗 + 1 抽屉 + 10+ 次点击——新建主题弹窗现直接内嵌「首轮 AI 回答」区（AI/提问时间默认当前/会话背景/回答全文），填了即与主题一次提交归档；留空只建主题；**保存后自动打开详情抽屉**，可立即「↳ 追问」续接。编辑主题弹窗保持只改主题字段
- **分类职责收敛：场景升为唯一主分类（P1④）**：原分类 4 轨重叠（scene/tags/session/background）——新建弹窗重排为「业务场景」置首屏并引导归档；主题标题 / 提问背景 / 标签**折叠进「更多选项」**（新建首屏只暴露 2 个必答点）；`background` 文案澄清职责边界（主题级背景；区分同 AI 具体对话请填回答级「会话背景」），tags 文案改为辅助分类（领域归类走场景）。零后端改动、旧数据不受影响

### ✨ 新增

- **回答正文 markdown 阅读态渲染（P0②）**：回答全文此前按纯文本堆叠，AI 回答里的列表/代码块/表格/标题不可读——`AskAnswerNode.vue` 正文改 `marked`（breaks + gfm）渲染，内联样式覆盖标题/列表/引用/代码块（横向滚动）/表格（横向滚动）/链接，代码单色高亮；折叠/展开逻辑保留，编辑态仍存 md 原文
- **采纳回顾：「仅含采纳」筛选 + 结论汇总导出（P1⑤）**——① 列表筛选项加「仅含采纳」勾选（后端 `?has_accepted=1`，`answers__verdict='采纳'` distinct，可与场景/标签叠加）；② 顶栏新增「采纳汇总」下拉（全部场景 / 未分类 / 各场景），拉取后端新 `GET ask-topics/summary/`（按范围聚合全部 ✅采纳 回答，含被采纳的追问节点带追问文本）导出 `AI采纳结论汇总_<范围>.md`——用于备考/决策场景快速回看已确认结论

### 🧪 测试

- 新增 2 条 pytest（`?has_accepted=1` 过滤与场景叠加 / summary 按场景聚合仅含采纳、追问采纳带入上下文、scene=none 生效），全量 **119 passed**

## [2026-09-09] v3.51.0 — AI 问答库：业务场景容器 · 多轮追问对话流

### ✨ 新增

- **业务场景容器（区分不同业务场景）**：AI 问答库此前只覆盖「单轮问答」，且所有主题混在一起——新增顶层容器 `AskScene`（`toolkit_ask_scene`：名称/说明/排序，迁移 0019），`AskTopic` 挂 `scene` 外键归属（删除场景主题转「未分类」，SET_NULL 不删数据）——① 后端 `AskSceneViewSet`（CRUD + list 带 `topic_count` 注解）；`AskTopicViewSet` 支持 `?scene=<id>` 与 `?scene=none`（未分类）过滤，serializer 回显 `scene_name`；② 前端 `AskLibrary.vue` 筛选栏新增「业务场景」下拉（全部/各场景计数/未分类）+「🗂 场景管理」弹窗（新建/编辑/删除，删除前确认提示主题转未分类）；新建/编辑主题可选场景；列表与详情回显场景 tag；导出 .md frontmatter 带 `scene`
- **多轮追问对话流（记录深入交流过程）**：用户基于 AI 回答继续追问的持续交互此前无法表达——`AskAnswer` 加 `parent`（自引用外键，追问挂在被追问的回答下，删除父回答级联删其追问）与 `question`（该轮追问文本；首轮留空沿用主题提问，迁移 0019）——① 后端 6 字段全文检索新增命中 `answers__question`（追问文本可检索），detail nested answers 带 parent/question；② 前端详情抽屉改为**对话流树**（新组件 `AskAnswerNode.vue` 递归渲染）：首轮多 AI 回答平级、每条可点「↳ 追问」逐轮录入（自动延续上一条的 AI/会话，追问文本必填），追问以缩进 + 竖线 + 「↳ 追问」标记递归折叠展示（超长正文单条展开），编辑/删除会提示连带追问条数；③ 导出 .md 按对话流递归输出：首轮 `##`、追问 `> **追问：**` + 逐层加深标题，整段深入交流完整落档；④ 新增 3 条 pytest（场景 CRUD/过滤/SET_NULL、追问链创建与级联删除、检索命中追问文本），全量 117 passed

### 🐛 修复

- **回答提问时间默认值差 8 小时（UTC 偏移）**：「添加首轮回答」「记录一轮追问」弹窗自动生成的提问时间用了 `new Date().toISOString()`（UTC 时间），UTC+8 下时分秒整体比本地实际时间早 8 小时（本地 14:33 自动填成 06:33）——新增 `nowLocal()`/`todayLocal()`（本地时区取时分秒/日期）替换 4 处自动生成路径（首轮/追问默认值、保存兜底、导出 `exported_at`），编辑回显（走后端本地时间字符串）不受影响

## [2026-09-09] v3.50.0 — AI 问答库（结构化沉淀 AI 答案档案）

### ✨ 新增

- **AI 问答库**：把散在 Logseq/摘录里的 AI 问答升级为结构化档案——完整记录问答（回答的 AI 对象 + 回答内容 + 提问时间 + 隔断时间 + 重复询问）+ 检索 + 预设标签 + 导出整个对话 .md。① 后端 `AskTopic`/`AskAnswer` 两表（`toolkit_ask_topic`：title/question/background/tags JSON/timestamps；`toolkit_ask_answer`：topic FK/ai/session/answer/asked_at/verdict[采纳/备用/不采用]/note，迁移 0018）+ `AskTopicViewSet`（6 字段全文检索——`search` 跨 question/title/background/answers__answer/answers__session/answers__ai，distinct 后补 order_by 防 MySQL 警告；`?tag=` tags__contains、`?ai=` answers__ai、日期范围；detail 嵌套 answers）+ `AskAnswerViewSet`（`?topic=` 过滤）；② **同一 AI 不同会话问同一问题用「会话背景」区分**（background 字段，记录提问时的场景/上下文）；③ 标签预设接入「系统预设管理」统一管——`PRESET_TYPE_CHOICES` 加 `ask_tags`（AI 问答库标签），seed 8 个默认种子（工作/学习/代码/写作/决策/健康/生活/工具）；④ 前端 `AskLibrary.vue`（`/toolkit/ask-library`，工具卡归「其他」+ **侧边栏「工具箱」分组同步新增直达菜单** `toolkit_ask_library`，ChatDotRound 图标，自动纳入菜单管理可排序/归档）：表格多选 + 详情抽屉折叠对照（同一 topic 多 AI/会话答案并列对比）+ verdict 行内 select + 单条/批量导出 .md（含 YAML frontmatter：title/tags/asked_at/ai/session）；⑤ 新增 5 条 pytest（检索跨字段/tag/ai 过滤/日期范围/导出），全量 114 passed

## [2026-09-09] v3.49.0 — 月度日历合一账单清单 · 支出必要性标记

### ✨ 新增

- **账单「必要性」标记（必要/可选/冲动，仅支出）**：账单明细新增独立维度 `necessity`（非既有 `category` 文本分类），用于消费性质复盘——① 后端 `wealth_bill_list` 原生加列（`managed=False` 遗留表，生产库 + conftest 测试镜像 DDL 同步）；`BillSerializer` 加字段并兜底（收入行强制清空）；`BillViewSet` 支持 `?necessity=`（含 `unmarked`=NULL/空串视为未分类）、新增 `POST batch-necessity`（ids 批量置标，仅支出行生效）与 `GET necessity_stats`（支出按必要/可选/冲动/未标记分组笔数与金额，可叠加日期/分类筛选）；② 前端 `BillListView.vue`（自现金盘点弹窗抽取增强）：支出小结卡（各档笔数/金额 + 合计）、必要性筛选下拉、表格支出行**行内下拉快速改标**、**多选勾选（仅支出行可勾）→ 批量标记下拉**、新增/编辑弹窗内置必要性单选（仅支出显示、收入切走自动清空）；③ 新增 4 条 pytest（necessity 过滤与 unmarked / 批量仅支出生效 / 统计聚合 / 收入兜底），全量 109 passed

### ♻️ 重构

- **账单清单迁入月度日历（月历页合一）**：原「现金盘点」页右上角的账单清单弹窗（+新增/编辑弹窗 + 相关 CRUD script）整体迁出为独立组件 `BillListView.vue`，常驻于月度日历页日历下方，**默认随月历导航的年月联动筛选**（用户手动改日期范围后脱离联动）；现金盘点页瘦身（移除账单清单按钮与两弹窗）
- **清理月度日历头部死控件（宏观热力图 tab 完整保留）**：经审计确认，月度日历头部「月视图/宏观热力图」切换按钮为**无人接线的死控件**（emit 无监听、viewMode 无渲染分支、点击无效果）——仅移除该切换按钮并连坐精简其专用 `viewMode` prop / `switch-view` emit；**财富顶栏「宏观热力图」tab（61×52 周历推演大页）为高频高价值入口，予以完整保留**——此前误删的 `WealthView.vue`/`HeatmapGrid.vue`/`Legend.vue`/`ControlPanel.vue`/`WeekDetailModal.vue` 5 个组件、`/wealth/heatmap` 路由、WealthHub tab 与 cashflow/月度复盘页内热力图跳转按钮已全部恢复；`wealthStore` 仅移除死控件专用 state/methods（`viewMode`/`setViewMode`）与 `CalendarViewMode` 类型（唯一引用即死按钮，不服务周历页），周历推演区块及其数据字段完整保留（后端周历 API 与 `wealth_bill_list` 数据全程未动）

### 🐛 修复

- 月度日历 `CalendarHeader` 移除视图切换控件后同步精简 `viewMode` prop 与 `switch-view` emit（连坐清理 `wealthStore.viewMode`/`setViewMode` 与 `CalendarViewMode` 类型）

## [2026-09-09] v3.48.0 — 决策追踪器 · relation 测试 flaky 修复

### ✨ 新增

- **决策追踪器（工具箱 · 长期观察型决策）**：给需要长期观察的决策（如「这份工作还值得继续吗」）在决策前持续采样倾向与理由、到期自动汇总，与既有「决策日志」（决策后回顾）互补——① 后端 `DecisionTracker`/`DecisionRecord` 两表（`toolkit_decision_tracker`/`toolkit_decision_record`，迁移 0017）+ `DecisionTrackerViewSet`（CRUD / 记录读取 / `report` 本地汇总 / `decide` / `archive`，观察中且过 `end_date` 的追踪在查询时自动置「已到期」）+ `DecisionRecordViewSet`；报告为本地聚合：倾向计数与占比、月度趋势（月份升序）、正反理由按倾向分列明细；② 前端工具页 `DecisionTracker.vue`（`/toolkit/decision-tracker`，工具卡与「决策日志」同入「环境侦查」筛选分组，DB 注册 tool_key `decision-tracker`）：4 TAB（追踪中/已到期/已决策/归档，带计数徽标）+ 顶部提醒横幅（到期 ≤7 天 / 已到期待处理）+ 新建（默认观察期 3 个月）/ 10 秒记录弹窗（想继续·不想继续·不确定 + 理由关键词 + 情绪强度）/ 记录明细（可删除误记）/ 汇总报告弹窗（统计比例条 + echarts 月度堆叠趋势 + 理由三列）/ 做出决定 / 归档（事后回看 30 天可补）/ 延长观察（回「观察中」）全套交互；**观察期内的追踪不提供理由查看入口**（防止倾向分布提前影响后续记录）；③ 新增 8 条 pytest（到期自动流转 / 报告聚合 / decide-archive 流转 / 误记删除），全量 105 passed

### 🐛 修复

- **relation 月度统计测试 flaky 修复**：`test_overview_monthly_count_uses_range` 用「now − 40 天」模拟上月样本，每月 1~10 号会跨到上上月导致 last_month 计数断言失败——改为取上月中 15 号（本月首日 −1 天再 `replace(day=15)`），与运行日期解耦

## [2026-09-03] v3.47.0 — 阅读图形分析独立页

### ✨ 新增

- **阅读图形分析独立页（两图迁出主页面）**：阅读管理的「年度阅读统计」「书籍类型分布」从主页面迁至独立分析页（`/books/charts`，懒加载路由、不进侧边栏菜单）——主页面右上角新增「图形分析」按钮跳转，新页 header 提供「返回阅读管理」回跳；新页面增强：顶部 4 张统计卡片（书籍总数/已完成/平均推荐/阅读中）+ 年份选择器联动 + 点击柱状图柱子联动筛选该年类型分布（选中柱橙色高亮）；后端 `stats` action 支持 `?year=`（按记录年份限定卡片计数与类型分布口径，`year_stats` 年度趋势保持全量、`month_count/year_count` 恒为当前自然月/年，默认不传完全向后兼容）；主页面移除图表区（顶部仅保留统计卡片），echarts 引入/图表渲染/resize 监听等脚本与样式一并清理

## [2026-08-31] v3.46.0 — 全系统时区修正 · 任务清单增强 · 日程完成心得

### ✨ 新增

- **全系统时区体系修复（读取路径 → 时间统计历史数据 → 全库）**：时间追踪贡献图（3-19 显示 20.6h）与任务清单（10.5h）数据对不上，根因历史 `start_time` 为 naive 本地时间（CSV 导入）被 Django 误按 UTC 解释——① 修复读取路径：`DATABASES.TIME_ZONE='Asia/Shanghai'` + MySQL 会话 `time_zone='+08:00'`，清单筛 3-19 与贡献图对齐（`get_queryset` 日期区间改 `timezone.make_aware` 消除警告）；② 修复已存数据：旧导入实际存 UTC naive（-8h），全表 2471 条 `start_time/end_time` +8h 恢复本地时间并重算 `year/mon/day/week/quarter`（跨天任务正确归日），3-19 语言学习 22:50:27 与 CSV 完全一致；③ 修复全局副作用：时区切换使所有「切换前 ORM 写入」的 datetime 显示 -8h——17 个 app 历史 `created_at/updated_at` 及系统生成字段（里程碑奖励发放/收件箱处理/财富快照等）共 86 个 表.列 **3261 行 +8h**（WHERE 值 < 2026-08-31 11:08 切换时刻，避开已正确的新数据）；用户手动/导入字段（账单日期 18-19 点记账高峰、交互时间、步数时间）经小时分布实证为本地存储不受影响；修正前备份 `temporal_tasks_backup_20260831` + 各表 `*_backup_tz_20260831`；验证修正后时间全部合理（里程碑 01:46→09:46、奖励发放 01:38→09:38、语录 02:31→10:31），pytest 97 passed
- **任务清单增强（筛选栏 + 结束时间列）**：清单弹窗新增筛选栏（日期范围 daterange / 分类下拉 4 项 / 关键词搜索任务名·备注 / 查询 / 重置，复用后端 `date_from/date_to/category/search` 参数，分页自动重置）；表格在开始时间后新增「结束时间」列（`end_time` 截取到分钟，为空显示 `-`，serializer 本就返回该字段）
- **时间追踪分类直白化（工作/学习/生活/兴趣记录）**：原四分类（生产与创造/维护与秩序/滋养与成长/连接与记录）语义抽象、边界模糊（运动归「秩序」、写作归「滋养」、牛马工作与家务混在「秩序」）——按实际内容重排为 4 个直白分类并同步 2478 条历史数据（牛马工作→工作；语言/代码/资质/阅读→学习；家务/备餐/运动/健康/生活杂事→生活；兴趣/写作/旅游/冥想/ONEDAY/社交→兴趣记录）；后端 `constants.py` 映射表/颜色/图标 + `services.py`（周报「生产占比」→「学习占比」、分类排序）同步；前端筛选下拉/趋势图/分类色标同步；备份 `temporal_tasks_backup_cat_20260831`；验证 stats/balance/trend 全返回新分类、学习占比 10.1%，pytest 97 passed
- **七维平衡雷达图优化（封顶 + tooltip 单点）**：① 封顶调整：原 `RADAR_MAX` 财富 100、阅读 60 不合理——财富增长有现实天花板、阅读 60 本/年不现实（好书要细嚼慢咽）；改为财富 **10 万元**封顶、阅读 **20 本**封顶，其他 5 维（健康 80/时间 80/小确幸 50/旅行 20/文字 20）保持。② tooltip 修 bug：原 formatter 在 radar item trigger 下 `params.value` 是整个数组被默认 toString 显示成 `33.44,18.34,.../100 点`，且 `params.name` 匹配不上 indicator 用默认 max；`trigger: 'axis'` 方案在 radar 上会崩（ECharts 访问 `params[0].axisValue` 报 TypeError）——最终方案：**关闭 ECharts 自带 tooltip，自定义几何提示**（`RadarChart` 监听 mousemove，按鼠标角度映射最近顶点 index，逆时针取反对齐 ECharts 顶点排列，环形带 0.55~1.15r 判定），hover 任一顶点只显示该维度的「name / 实际值 / max 点」。③ 修 TypeError（`parent.insertBefore` null）：根因父组件 `<RadarChart v-if>` 在 radarData 置 null 时卸载组件，watch+nextTick 的 render 在 DOM 已移除后操作空容器——父组件改 `v-show`（组件常驻）；RadarChart 加固：tip 移出 ECharts 容器、`isConnected` 检查、`getInstanceByDom` 失联自动重建、render/dispose 全 try-catch、resize 防抖 150ms。验证：type-check 0、build ✓
- **七维平衡封顶可配置（版本化历史）**：封顶值从硬编码 `RADAR_MAX` 改为可持久化配置——`SevenDimConfig` 模型升级为**版本化历史表**（每次保存新增一行，`is_active` 唯一生效、旧版本自动失效并保留，新增 `note` 备注 + `created_at` 配置时间）；`GET/PATCH /api/summary/radar_config/` + `GET /api/summary/radar_config_history/`（历史倒序）；PATCH 未传字段沿用当前值（局部修改友好），min_value≥1 校验；`get_radar` 读生效配置、未配置回退默认；前端「📡 七维平衡」卡片标题右侧「⚙️ 配置」按钮弹窗：7 维度封顶（el-input-number + 单位提示 万元/万步/小时÷30/万字/级/次/本）+ 备注输入 + **历史配置折叠列表**（时间/生效标记/备注/各维度值），保存后即时刷新雷达图
- **4 个贡献图支持点击查看当日明细**：贡献图方格点击弹出当日明细弹窗——① 后端新增 4 个 `daily_detail` action（temporal tasks 当日任务、temporal oneday 当日日记、health 当日步数、wealth 当日账单），按 `?date=YYYY-MM-DD` 查当天记录并返回汇总字段；② 前端 `ContributionGraph.vue` 给有数据方格加 `@click` + emit `cell-click` + 有值方格加 hover outline 提示；③ 新增共享 `DailyDetailDialog.vue`（el-dialog + el-table，columns 由各视图配置）；④ 4 个 contrib 视图接线（监听 cell-click → 调对应 daily_detail → 弹窗，列分别为：时间/任务/分类/时长/备注、主题/类型/字数/标签、时间/类型/步数、时间/类型/分类/商户/金额/备注，账单加收入/支出汇总）
- **仪表盘「本周步数/支出」接入真实数据**：诊断发现两卡从上线起就是死卡片（`stepCount`/`weeklyExpense` 只有声明从未赋值，永远显示 `-`）——新增后端 `GET /api/temporal/oneday/week_stats/`（本周日记数/步数/支出一次返回：日记 OneDayPage 计数、步数 HealthRecord.total 求和、支出 WealthBillList 支出金额求和，均按周一起点 aware 边界过滤）；前端 `fetchDiaryCount` 升级为 `fetchWeekStats` 一次拉三值赋值（weeklyExpense 类型 string→number 修正）
- **汇总总览统计卡片全部移除**：顶部概览 4 卡（🎯 年度总进度 / 📈 目标完成率 / ⏳ 剩余目标 / 📅 月度目标）与「📊 各模块贡献」header 进度徽章及月度明细重复——整体移除统计卡片区（含 stats-row/stat-card/stat-body 等样式）；年度进度信息集中于「各模块贡献」徽章，月度目标在月度明细表可见
- **移除「标签管理器」模块**：系统预设功能已覆盖其作用，整体下线——前端删 `TagManager.vue`、`/admin/tag-manager` 路由、`menuConfig` 菜单条目（admin_tags）、`toolkitApi` 的 `getTags/mergeTag`；后端删 `TagManagerView`（动态聚合摘录/小确幸/好东西/日记流标签）+ `urls` tags 路由 + 清理仅此处使用的 `SugarRecord/GoodThing/OneDayPage` import（Quote 保留，摘录馆仍用）；无独立数据表，各模块 tags 字段不受影响
- **日记流支持按日期查询 + 修复标题搜索**：TemporalView 筛选栏新增日期范围选择器（daterange → `date_from/date_to`，后端 `begin_date` 范围过滤早已支持，仅前端接线）；顺带修复标题搜索 bug——原传 `params.title` 后端未处理（SearchFilter 用的是 `?search=`），标题搜索一直无效，改为 `params.search`（搜 title+remark 模糊匹配）；重置按钮一并清日期范围
- **账单清单备注模糊搜索**：CashFlowView 账单清单筛选栏新增搜索框（备注/商户/分类模糊匹配，回车或清空触发，分页自动重置）——复用后端已有 `SearchFilter` + `search_fields = ['notes','merchant','category']`（`?search=` icontains），前端仅接线 `params.search` + Search 图标；重置按钮一并清空搜索词
- **各模块贡献百分比数值补全**：各模块贡献条原显示 `42.14 点 (%)` 百分号无数值——后端 `_module_entry` 之前未返回 `percent` 字段，前端 `{{ item.percent }}` 渲染为空。`get_yearly_overview` 注入 percent（该模块占总进度的百分比，如健康 32.7% / 时间投入 26.0% / ... 合计 ≈100%）
- **仪表盘去重（年度进度 → 各模块贡献聚合）**：仪表盘「📈 年度进度」卡片（进度条 + 各模块条）与汇总总览「📊 各模块贡献」重复——移除 Dashboard.vue 卡片及 `ProgressData`/`progress`/`loadingProgress`/`progressColors`/`fetchProgress` 全套；汇总总览「📊 各模块贡献」卡片 header 右侧新增进度标识徽章（`总进度 / 目标 分 (达成率%)`，灰色圆角底），信息不丢失且位置聚合
- **时间统计去重 + 汇总新增年度明细**：① TimeStatsView 移除「📅 月度统计」与「📋 年度统计」两个冗余表格（字数统计，信息已由汇总总览月度/年度明细覆盖）——删表格区块 + `monthlyStats`/`yearStats` computed + `month_stats`/`year_stats` 类型定义，后端 stats 接口字段保留（兼容，测试仍引用）；② 汇总总览「📅 月度明细」卡片 header 新增「📆 年度明细」按钮，点击弹窗展示年度表（年份/总进度/目标/财富/健康/时间投入/阅读/小确幸/旅行/文字/达成率，达成率三色标记）——后端新增 `GET /api/summary/yearly_detail/`（遍历可用年份，每行 = get_yearly_overview 的 7 模块 points + 总进度 + 达成率）
- **日程视图完成时录入心得**：抽屉点「✓ 完成」不再直接提交，而是切换为「录入心得」面板（textarea，500 字上限 + 字数统计，按事项类型给不同 placeholder）→ 填好后「确认完成」才 PATCH（收件箱传 `completion_note`、里程碑传 `completed_note`）；后端放开 `InboxItemSerializer.completion_note` 的 read_only 限制（原本误标导致 PATCH 被拒），端到端验证 PATCH 200 + 字段入库

## [2026-08-30] v3.45.0 — 贡献图 · 标签检索 · 计算器聚合 · 高频直达

### ✨ 新增

- **日程视图重构（弃用 el-calendar，自建钉钉式月视图）**：原 `ScheduleView` 用 el-calendar 黑盒组件导致每格等高、无跨天、无农历、无视图切换——重写为自建 `CalendarMonthView`（CSS Grid 7 列 + `grid-auto-rows: minmax(96px, auto)` 每行独立高度、今天蓝圈高亮、农历/节气/节日显示、收件箱橙/里程碑蓝/完成置灰标记、+N 项溢出展开、非当月淡显）+ `CalendarListView`（按月分组列表，钉钉"列表"视图）+ 月份导航（上/下月、今天按钮）；集成 `lunar-typescript` 农历库（验证 8-31「十九」、8-7「立秋」与钉钉截图一致）；数据层保留（收件箱 due_date + 里程碑 target_date），事件模型预留跨天 `endDate` 字段

- **日程视图事项详情 + 一键完成**：点击月视图/列表视图中的任意日程条目弹出详情抽屉——收件箱待办显示描述/类别/标签/提醒时间，里程碑显示描述/所属目标/完成备注；未完成事项可直接点「✓ 完成待办/里程碑」（PATCH `/goals/milestones/<id>/` 或 `/inbox/items/<id>/`），完成后实时置灰 + 刷新当月数据；`CalendarEvent` 类型扩展携带详情字段（description/category/tags/goalTitle/rawId）

- **高频工具直达菜单**：用电记录、摘录管理 加入左侧菜单栏（工具箱分组，`menuConfig.ts` 新增 `toolkit_electricity`/`toolkit_quotes`，path 分别直达 `/toolkit/electricity-record` 与 `/toolkit/quotes`），自动纳入菜单管理（可排序/归档/分组）

- **财务计算器三合一**：固定开销 / 自由支配额度 / 时薪 三个计算器合并为一个「💰 财务计算器」入口（工具箱列表折叠显示，`ToolDetail` 渲染聚合页 `FinanceCalculators.vue` 用 tab 切换）；聚合页默认定位固定开销，子组件去掉各自「返回工具集」按钮（对齐 FixedExpense 规范）；顺带接上此前未被引用的 HourlyWage 组件（原走空表单）

- **移除「图片转GIF」功能**：多轮调试后使用效果不佳（macOS 预览兼容性反复出问题），决定整体下线——删除 img2gif 后端工具、`POST /api/toolkit/execute_files/` 多文件上传执行端点、前端图片上传/参数表单/FormData 执行链路（api.executeToolFiles / store.runToolFormData / ToolDetail 图片分支）、相关测试与 22 条执行记录；`GIF 下载端点 FileDownloadView`（通用）保留；工具箱「GIF 压缩」等其他工具不受影响

- **四大模块贡献图（Roam 风格年度热力图）**：时间/日记流/财富/健康各新增贡献图页面（`/temporal/contrib`、`/temporal/oneday/contrib`、财富 tab「贡献图」、`/health/contrib`），多年 × 12 月网格、色阶深浅=当日活跃度（时间=持续小时数 / 日记流=总字数 / 财富=收支净值红收绿支 / 健康=折算步数），初始年份取各模块最早数据年（时间 2024 / 日记流 2021 / 财富 2014 / 健康 2021）；通用组件 `shared/components/ContributionGraph.vue` + 4 个后端 contrib 聚合端点（单表 GROUP BY + Cast 规避 CONVERT_TZ）；前端 localStorage 按模块+年缓存 30 分钟 + 手动刷新；性能实测 4 查询合计 34ms 不固化（未来 >500 万条再物化）；新增 4 条 contrib pytest（96 passed）

- **日记流标签列 + 标签检索**：列表新增「标签」列（flag 逗号分隔拆分为多个 el-tag 展示）；筛选栏新增标签输入框（如"待回顾"），后端 `flag__icontains` 子串检索支持多标签命中；重置会清空标签筛选；新增 pytest 检索用例（89 passed）

- **里程碑列表智能排序**：未完成（pending/in-progress）排前 → 有截止日期（target_date）排前 → 截止日期最近排最前 → 手排/ID 兜底；`MilestoneViewSet.get_queryset` 用 Case/When 生成排序键；新增 pytest 排序用例（86 passed）

- **待跟进提醒排除同事**：`get_due_reminders` 排除 `identity_then='同事'` 的关系（32 条同事不再提醒）；新增 pytest 用例（97 passed）

### ✅ 测试

- **测试用例扩充 46 → 85（新增 39 条）**：覆盖资金排程子表、账单清单 CRUD/时间筛选、好朋友跟踪（结束日期/持续天数/12 个月口径）、健康统计 ORM 化、时间追踪任务 CRUD、oneday stats 列名回归、关系统计 ORM 化、summary/goals services 跨类引用回归；conftest 补 7 张外部表镜像（task/oneday/step/relationship/interaction/balance/travel），测试库结构变更需 DROP test_sycamore 重建

- **测试暴露并修复产品 bug**：relation 能量趋势/互动频率按月分组的 `ExtractYear/Month` 受 CONVERT_TZ 影响 period 全为 `0000-00`，改 `TruncMonth(Cast(...))` 修复

### 🐛 修复

- **里程碑截止日期被编辑清空修复**：`GoalHub.saveMilestoneDate` 中 `editingMilestoneDate.value || null` 在输入为空时把 target_date 置 null——改为未改动不提交（新旧值相同直接关闭），仅显式清空才传 null；新增 3 条「编辑不丢失未改动字段」pytest 回归用例（92 passed）

## [2026-08-27] v3.44.0 — 菜单管理系统 · 补测试 · 数据库清理

### ✨ 新增

- **时间追踪任务 + 账单清单 CRUD**：

  - `temporal_time_atracker_tasks_list`（时间追踪任务）：`TemporalTaskViewSet` 由只读改为完整 ModelViewSet（列表/新增/编辑/删除）；前端「年度周度时间追踪」页新增「📋 任务清单」入口——清单弹窗（任务/开始时间/时长/分类/备注列 + 分页）+ 新增/编辑弹窗（含备注 notes 填写完善）+ 删除确认

  - `wealth_bill_list`（账单）：新增 `WealthBillList` ORM 模型（managed=False 映射外部遗留表）+ `BillViewSet`（`/api/wealth/bills/` CRUD，按类型/日期范围筛选）+ `BillSerializer`（自动补 created_at/updated_at/year/month/day，备注 notes 可编辑）；前端「现金实时盘点」页新增「📋 账单清单」入口——清单弹窗（日期/类型/金额/分类/商户/备注列 + 类型/日期筛选 + 分页）+ 新增/编辑弹窗（含备注 notes 填写完善）+ 删除确认

  - ⚠️ 前端 `createBill` 与原有快速记账同名冲突，新增的改名 `createBillRecord`

  - ⚠️ **拆分遗留跨类引用修复**：services 拆包时漏 import 兄弟类（quarterly_workbench 引用 ProgressAggregator、goal_clone/quick_goal 引用 GoalProgressService）导致季度报告/目标克隆运行时 NameError，已补 import（pytest 未覆盖该类路径，教训：拆包后需显式排查跨类引用）

- **收件箱批量「转为里程碑」**：整理模式勾选多条待办后新增「🏁 转为里程碑」操作——弹窗选择已有目标，全部条目转入同一目标成为里程碑（标题=各条内容，截止日期/详细描述随各条待办自动带过去，复用转换兜底链）；后端新增 `POST /api/inbox/items/convert-to-milestone/`（body `{item_ids, goal_id}`，返回转换/失败计数），转换后待办标记为已处理

- **菜单管理系统（可管理动态侧边栏）**：

  - 后端：`MenuPreference`（`core_menu_preference`：菜单常用/归档 + 排序）+ `MenuGroup`（`core_menu_group`：分组名称/排序/显隐）模型（迁移 0005）；API `GET /api/core/menus/user_prefs/`、`POST /api/core/menus/batch_update/`、`/api/core/menu-groups/` 分组 CRUD（list 惰性 seed 9 个默认分组，新增分组自动排最后）

  - 前端：`shared/config/menuConfig.ts` 全量 32 个菜单项（key/path/label/icon/group/defaultArchived）；`LayoutSidebar.vue` 重写为菜单配置驱动——常用菜单留在原分组、归档菜单统一收进「归档菜单 (N)」折叠区（系统运维下方，可展开）；`core/admin/views/MenuManager.vue` 菜单管理页（分组重命名/排序/显隐/增删 + 菜单常用/归档开关 + 保存全部，取消归档自动回到原分组，删除分组时组内菜单自动转归档）；路由 `/admin/menus` + 侧边栏「菜单管理」入口

  - 偏好持久化到数据库，刷新保持；无偏好记录时按 `defaultArchived` 兜底（第一轮归档的 5 模块 + 舞蹈记录默认归档）

- **补充测试（pytest + pytest-django）**：新增 6 个测试文件 46 个用例，覆盖财富周聚合/现金流推演（日利息复利）/固定开销/CSV 导入去重、里程碑奖励发放与防重复/取消与删除扣回/目标完成奖励金（顺序无关/幂等）、小确幸奖励金额=快乐程度；配套 `pytest.ini`（--no-migrations + 测试库外部表 conftest 建表）

- **系统体检报告**：`docs/Sycamore-系统体检报告-2026-08-27.docx`（三位一体审计 + 数据取证）

### 🐛 修复

- **好朋友跟踪：平均周期按最近 12 个月 + 新增本次结束日期**：

  - `stats` 接口统一 12 个月口径（按自然月精确回推 `start_date >= since`）：avg_cycle / avg_offset / min_cycle / max_cycle / predicted_next 全部基于最近 12 个月记录

  - `MenstrualRecord` 新增 `end_date`（本次结束日期）+ `duration_days`（持续天数，可编辑）字段（迁移 0006）；serializer 自动计算：未显式传 `duration_days` 时由 `end_date - start_date` 得出，用户可手动覆盖

  - 前端记录列表新增「结束日期」「持续」两列；表单新增「结束日期」（填后自动算）+「持续天数」（自动计算可手动改）；统计卡「总记录数」改为「持续时间」（`avg_duration` 12 个月口径平均持续天数，恒 12 条无信息量的记录数卡片下线）

  - 验证：自动算 5 天 ✓、手动覆盖 2 ✓、12 个月口径 stats ✓、pytest 46 passed、type-check 0 错误

- **侧边栏图标组件未注册**：`LayoutSidebar` 重写后模板直接使用的 `Expand/Fold/Box/ArrowUp/ArrowDown` 未在 script setup 显式导入，导致「归档菜单」折叠箭头与折叠按钮不渲染（Vue warn: Failed to resolve component）

- **收件箱转换异常防护**：单条「转为里程碑」未选目标/目标已失效时原抛 500，现返回友好 400（`转为里程碑需要指定目标ID` / `转换失败，请检查所选目标是否仍有效`）

- **收件箱「转为里程碑」丢失截止日期与详细描述**：转换逻辑改为兜底链——`target_date` 前端显式传的 > 待办 `due_date`；`description` 前端显式传的 > 待办 `description` > 待办 `content`。前端转换弹窗「截止日期」默认预填待办 `due_date`、「详细描述」默认预填待办 `description`（均可手动覆盖）

- **取消完成里程碑未扣减目标累计发奖**：`goals/views.py` 取消完成（completed→pending）分支补 `total_reward_issued - reward_amount`（与 `sync_on_delete` 行为对齐）

- **views「首次完成」路径未增加累计发奖**：与 service 路径行为不一致，补 `total_reward_issued + reward_amount`

- **前端 43 个既有类型错误全部修复**（11 个文件）：BehaviorTrackCard 联合类型判别收窄、SnapshotHistory formatMoney 参数允许 null、CareerEnergyAudit/ModulePoint/TrendChart/InboxStats/MonthlySummaryTab/RelationView/MonthlyReviewView/FoodForm 类型补齐与安全转换

- **temporal/travel 迁移缺陷**：`RunSQL ALTER TABLE`（假设生产外部表已存在）改为 `CREATE TABLE IF NOT EXISTS`（完整结构），全新空库可完整 migrate（73 张表），生产库无副作用

- 清除 BehaviorTrackCard 的 7 条【折叠调试】console.log 残留

### 🗑️ 数据清理与重构

- **旧库 sycamore_db 彻底移除**：50 张表逐表核实（25 张精确 0 行 + 3 张旧系统表 + 6 张已迁移业务表直接删除；含疑似未迁移数据的表经用户确认后删除），最终 `DROP DATABASE sycamore_db`；数据库仅剩 `sycamore`（唯一业务库）+ `test_sycamore`；备份留存 `db_backups/`（旧库全量 + 备份表 + 迁移前生产库）

- **备份表清理**：删除 `wealth_cash_flow_backup_20260710`（主表已覆盖）；`temporal_..._backup_20260604`（698 条独立历史数据）经用户确认后一并删除

- **迁移文件 squash：86 → 45**：core 4→1、wealth 9→1、goals 15→1、toolkit 18→2（净效果迁移 + replaces，toolkit 0016 RunPython 回填独立保留）；生产库 migrate no-op、全新库可一键部署

- **projects 空壳模块彻底删除**：后端 `apps/projects/`、前端 `modules/projects/`、路由、侧边栏颜色映射、README/CLAUDE.md 文档全清（数据库本无表）

- **侧边栏瘦身（第一轮）**：个人良品率/数字资产/美食地图/旅行计划/成长记录归档弱化，决策日志/自由支配额度/复盘工具箱/语言训练器移出独立入口

### 🎨 优化

- **拆分大 services.py（summary/health/goals）**：

  - `summary/services.py`（814 行）→ `summary/services/` 包 3 文件：progress_aggregator（358）/ quarterly_workbench（369）/ body_mind_correlation（84）

  - `health/services.py`（639 行）→ `health/services/` 包 2 文件：health_stats（372）/ weight_service（281）

  - `goals/services.py`（476 行）→ `goals/services/` 包 5 文件：goal_progress（88）/ milestone_reward（166）/ quick_goal（138）/ goal_clone（52）/ streak（52）

  - 对外接口不变：`__init__.py` 重新导出，views 的 `from .services import X` **零改动**；踩坑：① 拆包后 `from .models` 相对导入层级变深需改 `..models`；② GoalProgressService 交叉引用 MilestoneRewardService 需显式 import；③ 切分时曾误 git checkout 覆盖第二轮 health ORM 化改动，已按 memory 重做并验证（active_days 371/2026-08 7065.0）

  - 验证：pytest 46 passed、manage.py check 0、核心 API 冒烟 200（summary/goals/health records/weight）

  - ⏳ 其他超 300 行 services 待拆：temporal 457 / travel 384 / toolkit 380 / inbox 330（下轮）

- **技术债清理：原生 SQL + 驼峰字段（第二轮）**：

  - **原生 SQL 64 → 33 处**：relation services（stats_service 14 + quality_service 5）与 health services（12）共 31 处全部 ORM 化——统计聚合改 aggregate/annotate、按月分组改 ExtractYear/Month、按日分组改 `Cast('time', DateField())`（规避 USE_TZ 下 `__date` 生成 CONVERT_TZ 而 MySQL 无时区表返回 NULL 的问题）；剩余 27 处为 `wealth_bill_list` 外部遗留表（无 ORM 模型，原生 SQL 是唯一访问方式，已加注释）+ 6 处测试辅助

  - **驼峰 db_column 6 处清理**：temporal `beginDate→begin_date`/`updateDate→update_date`（外部表 RunSQL 迁移 0004，索引自动跟随）、wealth `wageIncome→wageincome`/`otherIncome→otherincome`（RunSQL 迁移 0012）、book `createDate→created_at`/`updateDate→updated_at`（迁移 0003）；前端 API 字段均无感（序列化输出字段名不变）；另 4 处 FK 显式 snake_case 声明（file_id/template_id 等）本就合规无需改

  - **时间筛选/统计 CONVERT_TZ 全家桶修复**：USE_TZ + MySQL 无时区表导致 DateTimeField 的 `__date`/`__year`/`__month`/`TruncDate` 查询返回 NULL（筛选全空、统计为 0）——账单清单时间筛选、时间追踪任务筛选、小确幸能量统计（周/月/连续打卡）、关系本月互动数 4 处全部改 datetime 区间或 `Cast`；DateField 的 `__year` 无时区正常未动；账单 8 月筛出 25 条、任务 8 月 22 条验证通过

  - **驼峰重命名后遗症修复**：`temporal/services.py` 的 `get_stats` 原生 SQL（`DATE_FORMAT(beginDate,...)`）漏改旧列名导致 `/api/temporal/oneday/stats/` 500（Unknown column 'beginDate'），已改 `begin_date`；一次性历史迁移命令（migrate_oneday/migrate_books）保留旧列名（源数据在旧表，不可改）

  - 验证：manage.py check 0、pytest 46 passed、前端 type-check 0 错误；备份 `db_backups/backup_before_round2_20260827.sql`

  - ⚠️ book `readDate` 为字段名驼峰（非 db_column，API 契约被前端 6 处引用），建议保留或下轮独立评估

- **资金排程 reserve_items JSON 字段拆分（完成两轮）**：

  - 第一轮：新增子表 `wealth_fund_schedule_item`（FundScheduleItem，迁移 0010），数据迁移命令 `migrate_json_to_tables`（1 条排程 20 项已迁，幂等），保存写子表 + 读取从子表组装（JSON 保留 deprecated）

  - 第二轮：**删除 `FundSchedule.reserve_items` JSON 字段**（迁移 0011，子表为唯一存储）；serializer 的 reserve_items 改为 write_only 入参、读取经 to_representation 从子表组装；service 不再写 JSON

  - 验证：创建写子表（201/合计正确）、旧记录子表读 20 项、响应结构不变前端无感；pytest 46 passed、type-check 0 错误

  - ⚠️ 任务描述中的 `FundPool.linked_categories` 不适用：FundPool 模型与表已于 0007 迁移删除

- **四张核心表补充业务索引（10 个）**：

  - `life_sample.obsidian_path` 唯一索引 `uq_ls_obsidian_path` + 普通索引 `idx_ls_obsidian_path`（Obsidian 同步精确匹配从全表扫描 → const 查找，O(1)）

  - `reward_transaction` 4 索引：`idx_reward_type`（按交易类型筛选）、`idx_reward_source`（source_type+source_id 查重）、`idx_reward_created`（时间倒序）、`idx_reward_type_created`（类型+时间复合，最高频）

  - `temporal_oneday_page_list` 3 索引（外部表，RunSQL 迁移 0003）：`idx_oneday_date`（beginDate 按日查重）、`idx_oneday_type_date`（otype+日期）、`idx_oneday_year_date`（years+日期）

  - `health_step_info` 1 索引（外部表，RunSQL 迁移 0005）：`idx_health_time`（时间序列范围查询）

  - EXPLAIN 验证：全部从全表扫描（ALL）变为 Index lookup / Covering index / Index range scan

- **归档体验**：归档页面保留「此模块已归档，随时可重新启用」提示条；侧边栏归档入口统一折叠（菜单系统落地后）

### 📝 文档

- 更新 `README.md`（模块归档说明）、`CLAUDE.md`（移除 projects 描述）

## [2026-08-25] v3.43.0 — 备考优化 · 项目目标 + 收件箱导入 + 截止倒计时

### ✨ 新增

- **目标类型新增「项目目标」**：`Goal.category` 增加 `project`（迁移 0015），目标类型下拉框新增「📋 项目目标」选项

- **收件箱批量导入**：`POST /api/inbox/items/import/`（multipart 文件上传），支持 CSV / Markdown 任务列表 / 纯文本三种格式自动识别；中文列名与中文标签（待办/已完成等）自动归一化为合法 code；导入项自动标记 `source='import'`；前端导入弹窗含格式说明、拖拽上传、预览、CSV 模板下载

- **目标卡片截止倒计时**：`Goal` 列表/详情序列化新增计算字段 `days_remaining`（无截止日期为 null、已过期为 0）；卡片上按剩余天数分级着色（🔥≤3天 / ⚠️≤7天 / 📅N天 / ⏰已过期）

### 📝 文档

- 更新 `inbox/README.md`（后端 + 前端）：Services 增 `InboxImportService`、API 增 `/items/import/`、Components 增 `ImportDialog.vue`

- 更新 `goals/README.md`（后端 + 前端）：Goal 模型增项目目标、API 增 `days_remaining` 说明、Components 增 `CountdownBadge.vue`；goals 前端 README 全面整理（移除已删除文件 GoalForm/MilestoneForm/ActionList/CloneDialog/output* 的过时条目、修正重复的 Views 节、补全现有文件）

## [2026-08-23] v3.42.0 — 人生样本 · 同步防重复 + Obsidian 打开修复

### 🐛 修复

- **Obsidian 打开失败（相对路径无法解析）**：`get_obsidian_uri` 原产出 `obsidian://open?path=<相对路径>`，Obsidian 无法解析。现改为拼上仓库绝对路径 → `obsidian://open?path=<绝对路径>`；前端打开时 URI 为空（集成未配置）则友好提示

- **Obsidian 同步重复创建（文件重命名后）**：旧同步仅按 `obsidian_path` 精确匹配，文件重命名后路径已变 → 找不到原索引 → 重复创建。现改为四级匹配：① 路径精确匹配 → 字段变更则更新；② 文件名（不含扩展名）在已关联记录路径里包含匹配（重命名时 frontmatter name 也可能变）→ 迁移路径 + 更新内容；③ 按姓名匹配（文件已重命名或手动索引未关联）→ 迁移/补齐路径 + 更新内容，**保留 status/relevance**；④ 都找不到 → 新建。同步结果新增 `migrated` 列表（name/old_path/new_path），前端同步结果弹窗展示「🔁 迁移 X 个（路径变更）」

- **卡片 Obsidian 路径显示过长**：仅显示文件名（`诗人_李白.md`），不再展示恒定无区分度的 `05_人生样本(LifeSamples)/` 前缀

### 🗑️ 数据清理

- 删除 40 条因 vault 文件批量重命名（`name.md` → `职业_姓名.md`）由旧 buggy 同步产生的重复记录（均无人工批注，保留指向现存 vault 文件的记录）；现 77 条记录全部指向真实 vault 文件，李白等重复名已收敛为单条

### 📝 文档

- 更新 `lifesample/README.md`（后端）：Services 增 `sync_samples` 四级匹配 + `get_obsidian_uri` 绝对路径说明、API 同步/打开端点更新

- 更新 `lifesample/README.md`（前端）：Types 增 `SyncMigration`、SampleCard 路径显示与打开流程、API 同步/打开说明

## [2026-08-21] v3.41.0 — 人生样本 · P0 状态与评级

### ✨ 新增

- **状态管理**：`LifeSample.status` ∈ 已收集/已核实/已审阅；`verified_at`/`reviewed_at` 由模型 `save()` 在状态推进时自动补齐（只读，防手填）；同步新建样本默认「已收集」

- **借鉴意义评级**：`LifeSample.relevance` ∈ 高度借鉴/参考/了解 + `relevance_reason` 评级理由（卡片上以 💡 展示）

- **状态/评级徽章组件**：`StatusBadge.vue` / `RelevanceBadge.vue`，样本卡片顶部展示；表单弹窗新增状态/评级 radio 组 + 评级理由输入

- **统计展示**：`/samples/stats/` 返回 `status`/`relevance` 分布 dict；主页新增状态/评级统计卡，**点击即筛选**（再次点击取消，卡片高亮 is-active）

- **列表筛选**：`GET /samples/?status=&relevance=` 支持按状态/评级过滤，前端筛选栏新增「全部状态」「全部评级」下拉

### 🎨 优化

- **统计区紧凑化**：13 个独立数字精简为一行 5 张核心统计卡（总样本/已收集/已核实/已审阅/已关联）+ 一行评级摘要（🔥高度借鉴/📖参考/👀了解）；点击卡片筛选、再点取消、点「总样本」清除全部筛选；筛选器紧凑化（small + 占位符）

- **移除死代码**：`useSampleStore` 删除不再使用的 `statusCounts`/`relevanceCounts` getter

### 📝 文档

- 更新 `lifesample/README.md`（后端 + 前端）：Models 增状态/评级字段、API 增筛选与分布统计、Components 增徽章组件、Store 增 statusCounts/relevanceCounts、Types 增 StatusConfig/RelevanceConfig

- 更新 `lifesample/README.md`（前端）：Views 表改为紧凑统计布局描述、Store 移除 statusCounts/relevanceCounts

## [2026-08-20] v3.40.0 — 人生样本 · Obsidian 双向同步

### ✨ 新增

- **Obsidian 双向同步端点**：`POST /api/lifesample/samples/sync-from-obsidian/` —— 扫描样本文件夹，按 `obsidian_path` 匹配：无记录则创建、字段（name/alias/tags/summary）有变化则更新、未变化则跳过；`transaction.atomic` 包裹，返回 `{success, message, created, updated, skipped, total}`（无文件时 404 + 提示）

- **frontmatter 解析扩展**：`ObsidianService.parse_frontmatter` 现解析 name/alias/era/region/birth_year/death_year/type/tags/summary；扫描结果含 `modified_at`/`exists`；frontmatter `type` 支持中文标签（如「历史人物」→ historical），非法值自动回退

- **前端「同步Obsidian」**：替代原「扫描Obsidian」逐条新建逻辑，改为调用后端同步端点，同步结果弹窗展示 新增/更新/跳过 明细；无变更时仅 toast 提示

- **系统设置 Obsidian 卡增强**：新增「测试连接」（成功 / 空文件夹 / 失败三种状态提示）、当前配置预览（完整路径 code 展示）、快速操作（📂 打开 Obsidian 仓库 / 📁 打开样本文件夹）

- **样本文件夹默认值**：`ObsidianConfig.samples_folder` 默认改为 `05_人生样本(LifeSamples)`（与用户实际仓库一致），迁移 `lifesample.0002`

### 🐛 修复

- **扫描不到文件（路径重复拼接）**：仓库路径误填为含样本文件夹的完整路径时，`get_samples_folder_path` 会把 `samples_folder` 再拼一次导致路径不存在 → 扫到 0 个。现加防御：`vault` 尾部与 `samples_folder` 同名时直接返回 vault，不再重复拼接（两种配置方式均扫描正常）

- **「测试连接」用旧配置**：扫描读数据库配置，表单里改了但没点「保存配置」时会按旧配置扫描。现「测试连接」先持久化表单当前值再扫描

- **同步跳过「待采集名单」**：`待采集名单.md` 是待采集名单而非样本本体，`sync_samples` 现跳过该文件（`SYNC_SKIP_FILENAMES`），不再被索引为样本

### 📝 文档

- 更新 `lifesample/README.md`（后端）：Services 增 `parse_frontmatter`/`sync_samples`/`_normalize_type`，API 增同步端点

- 更新 `lifesample/README.md`（前端）：Store 增 `syncing`/`syncFromObsidian`，API 增同步方法，设置卡功能说明

---

## [2026-08-19] v3.39.0 — 新增「人生样本」模块（Obsidian 轻量索引）

### ✨ 新增

- **人生样本模块**：轻量索引人生参照样本（姓名/别名/类型/标签/一句话简介/Obsidian 路径/我的笔记），深度内容存 Obsidian，Sycamore 只做索引

- **LifeSample + ObsidianConfig 模型 + API**：`life_sample` / `obsidian_config`（单例 id=1）两表；`/api/lifesample/samples/` 提供 CRUD（不分页，?search=&type=&tag= 筛选）+ `tags` + `stats` 端点；`/api/lifesample/obsidian/config/` 配置读写、`/scan/` 扫描样本文件夹（解析 frontmatter name/summary，按 mtime 倒序）、`/open/<path>/` 生成 `obsidian://open` URI

- **Obsidian 扫描自动关联**：`ObsidianService.scan_samples` 扫描仓库样本文件夹，前端「扫描Obsidian」按钮对未关联文件自动创建样本（默认类型「历史人物」）

- **前端页面**：`/lifesample` —— 4 统计卡（总样本/已关联/文件数/待关联）+ 搜索姓名 + 类型/标签筛选 + 卡片墙（卡片可打开编辑弹窗）+ 扫描导入；新建/编辑共用 `SampleForm.vue` 弹窗（标签多选可回车创建）

- **系统设置新增 Obsidian 集成配置卡**：`AdminSettings.vue` 内嵌启用开关 + 仓库路径 + 样本文件夹 + 测试扫描（实时显示扫描文件数）

### 📝 文档

- 新增 `lifesample/README.md`（后端）：Models / Services / API Endpoints（含不分页与 `open/<path>` 路由说明）

- 新增 `lifesample/README.md`（前端）：Views / Components / Store / API / Types，及系统设置卡片接入方式

---

## [2026-08-18] v3.38.0 — 旅行模块新增「旅行计划」功能

### ✨ 新增

- **TravelPlan + TravelPlanItem 模型 + API**：`travel_plan` / `travel_plan_item` 两表，`/api/travel/plans/` 提供完整 CRUD + `items`（子项列表）+ `stats`（计划统计）+ `toggle-item`（勾选/取消完成，自动记录完成时间）。创建时 POST 带 `items` 明细，服务端 `TravelPlanService.recalculate_total` 自动汇总预估总费用

- **明细四类**：美食 / 景点 / 交通 / 住宿，每项含预估费用、完成状态、备注、排序

- **前端页面**：`TravelPlanView.vue`（路由 `/travel/plans`）——4 统计卡（计划总数 / 总预估费用 / 已完成 / 计划中）+ 新建计划弹窗（四类明细编辑器）+ 可展开计划列表（逐项勾选完成划线）

- **侧边栏**：「连接与足迹」分组下新增「旅行计划」入口，旅行记录高亮互斥

### 📝 文档

- 更新 `travel/README.md`（后端）：Models / Services / API Endpoints 新增旅行计划，前端章节补 `/travel/plans`

- 新增 `travel/README.md`（前端）：补齐旅行模块缺失的前端文档（Views / Components / Store / API / Types & Constants，含旅行计划页与明细四类）

---

## [2026-08-16] v3.37.0 — 工具箱新增「用电记录」工具

### ✨ 新增

- **用电记录工具**：工具箱新增「⚡ 用电记录」(`electricity-record`)，记录电表读数，服务端自动计算**间隔用电量 / 间隔天数 / 日均用电量 / 本月累计用电量**

- **ElectricityRecord 模型 + API**：`toolkit_electricity_record` 表，`/api/toolkit/electricity-records/` 提供 CRUD——新增后自动算本记录，删除后 `recalculate_all` 自动重算后续记录，历史完整保留

- **计算口径**：间隔用电 = 本次读数 − 上次读数（首条为空）；日均 = 间隔用电 ÷ 间隔天数（`Decimal` 四舍五入，与前端 `Math.round` 一致）；本月累计 = 本次读数 − 月初基准（优先取上月最后一条，无则取本月首条，本月首条为 0）

- **前端页面**：`ElectricityRecord.vue`——4 统计卡（最新读数/本月累计/日均用电/记录次数）+ 新增表单（日期/读数/备注）+ ECharts 趋势图（读数折线 + 间隔用电柱状）+ 历史表格（全字段 + 删除）

### 🐛 修复

- **工具页面重复「返回工具集」按钮**：`FixedExpense.vue` / `ElectricityRecord.vue` 经兜底路由 `/toolkit/:toolKey` 渲染在 `ToolDetail.vue` 内部（外层已有返回按钮），组件自身又各写一个导致双按钮。删除两个组件内的冗余 back-bar（模板块 + `ArrowLeft` 导入 + `.back-bar` 样式），统一由 `ToolDetail.vue` 提供单个返回按钮，并加注释防回归。独立路由的工具页（时薪/决策/健康自查等）各自保留唯一按钮

- **工具页顶部描述卡片与误导性「历史记录」按钮**：`ToolDetail.vue` 曾为所有工具渲染共享描述卡片（图标/名称/描述 + 「历史记录」按钮跳执行历史页），但数据型工具（固定开销/用电/环境校准/旅行路线等）历史存在各自数据表、不在执行历史页展示，按钮误导。删除该描述卡片（规则：数据型 = 返回 + 内容 + 自己历史列表；执行型 = 返回 + 内容 + 执行历史入口；不允许独立描述卡片），执行型工具（gif-compressor/trad2simp）的「执行历史」入口移至返回栏右侧。为依赖卡片提供标题的 `EnvironmentAudit.vue` / `TravelRoute.vue` / `GifCompressor.vue` 及通用执行表单补自身 `page-title`

### 📝 文档

- 更新 `toolkit/README.md`（后端）：Models / API Endpoints / 内置工具 三表新增用电记录

- 更新 `toolkit/README.md`（前端）：补齐独立工具组件清单（数据型/执行型分类）+ 工具页面结构约定（数据型返回+内容+自己历史；执行型返回+内容+执行历史入口；不允许独立描述卡片）

---

## [2026-08-16] v3.36.0 — 资金排程重构为 FundSchedule 快照式（修复金额 bug + 历史计划 + 固定开销联动）

### ✨ 新增

- **FundSchedule 模型 + API**：`wealth_fund_schedule` 表（JSON `reserve_items` 预留项 + 服务端 Decimal 权威计算预留合计/剩余），`/api/wealth/fund-schedule/` 提供 list / create / detail / delete（无 update，快照不可变）

- **资金排程看板重构**：`FundScheduleBoard.vue`（替换 AllocationBoard）——手里现金 + 计划名称、硬性承诺/弹性预留可增删、汇总卡（负数红色警示 + 恒等式 `现金 = 预留 + 剩余` 兜底 alert）、历史快照列表（查看/删除）

- **固定开销联动**：「导入固定开销」弹出固定开销历史记录选择弹窗（名称/月开销/日开销/项目数/创建日期 + 选中预览部分项目），可按需选择任意一条导入，按 365 天口径（年周期 ÷12.17）折算月金额导入为硬性承诺，带 `linked_expense_id`

### 🐛 修复

- **剩余可分配金额不相等 bug**：旧代码 `remainingToAllocate = free_cash - totalAllocated` 对预留合计二次扣减（少算一份）。重构后改为单一派生链 `现金 → 预留合计 → 剩余`，结构性消除该类错误

- **负金额返回 500**：服务层 `ValidationError` 在 `serializer.create()` 内抛出未被 DRF 捕获，改为转 `serializers.ValidationError` 返回 400

- **迁移删除组合唯一索引失败**：MySQL 删除参与唯一索引的列时用剩余列重建索引撞键（Duplicate entry），迁移先 `AlterUniqueTogether` 删索引再删列

### 🗑️ 删除

- **移除分配计划系统**：`AllocationCategory`/`AllocationPlan`/`AllocationItem`/`Commitment`/`DecisionLog` 五表 + `allocation_service.py` + `AllocationViewSet` + `init_allocation_categories` 命令 + `AllocationBoard.vue` + `api/allocation.ts`，由 FundSchedule 快照式取代

### 📝 文档

- 更新 `wealth/README.md`（后端）：FundSchedule 模型/服务/API、快照语义、固定开销 365 天换算

- 更新 `wealth/README.md`（前端）：`FundScheduleBoard.vue` + 资金排程章节

---

## [2026-08-16] v3.35.0 — 资金排程 + 分配计划（分配是计划，不是记录）

> ⚠️ 该版本的分配计划系统已于 v3.36.0 移除，由 FundSchedule 快照式资金排程取代。

### ✨ 新增

- **资金排程 + 分配计划看板**：新增 `/wealth/fund` 资金排程页面（`AllocationBoard.vue`，替换原 CashFlowBoard）——四张核心卡（手头现金可编辑 / 硬性承诺 / 预留分配 / 自由支配）+ 预留分配计划 + 硬性承诺 + 自由决策记录。核心语义：**分配是计划（预留），不是记录（花费）**，流程 手头现金 → 硬性承诺 → 预留分配 → 自由支配

- **分配模型**：新增 `AllocationCategory` / `AllocationPlan` / `AllocationItem` / `Commitment` / `DecisionLog` 五表。月度计划按 `year_month` 唯一；分配项按 `(plan, category)` 唯一且 `remaining = planned - spent` 自动计算；承诺三态（待付/紧急/已付）+ 来源（账单/收件箱/手动）；决策记录自由支配的打算怎么花

- **分配服务**：`AllocationService`——幂等 `create_plan`（事务内 upsert 分配项保留已花费、重建承诺、剔除未包含项）、`get_plan_detail` 返回全部启用类别作虚拟项（未保存即可编辑）、`calculate_commitments` 经 `wealth_bill_list` 原生 SQL 按 60 天窗口聚合支出账单

- **分配 API**：`AllocationViewSet` 提供 `detail` / `create` / `update-allocations` / `record-spending` / `save-decision` / `categories` 六端点（前缀 `/api/wealth/allocation/`）

- **类别初始化命令**：`manage.py init_allocation_categories` 幂等创建 5 个默认类别（投资 / 日常生活 / 精神愉悦-旅游美食 / 家居装修 / 风险预估-留底钱）

### 🐛 修复

- **分配计划幂等化**：`create_plan` 由「重复保存产生重复记录」改为 `update_or_create` 分配项（保留已花费）+ 删除重建承诺 + 剔除未包含项，可反复保存

- **detail 端点冲突**：`@action` 方法命名 `detail` 与 DRF 的 `self.detail` 布尔实例属性冲突，抛 `TypeError: 'bool' object is not callable`；方法更名 `get_detail`（`url_path` 不变）

- **formatAmount 导入路径**：前端由 `@/shared/utils/privacy` 改为 `@/shared/utils/format`（实际导出位置）

- **账单表原生查询**：规范中的 `WealthBill` ORM 模型不存在，硬性承诺聚合改用 `wealth_bill_list` 原生 SQL

### 🗑️ 删除

- **移除资金池系统（v2.0 持续资金池）**：删除 `FundPool` / `FundTransaction` 模型、`fund_service.py`、`fund-*` 全部端点与 `FundDashboard.vue` / fund store/api/types，由资金排程 + 分配计划取代

### 📝 文档

- 更新 `wealth/README.md`（后端）：分配五模型、`allocation_service.py`、分配 API 端点、分配是计划不是记录语义；移除资金池文档

- 更新 `wealth/README.md`（前端）：`AllocationBoard.vue` + 资金排程章节；`CashFlowBoard.vue` 移除

---

## [2026-08-11] v3.34.0 — 资金分配系统 v2.0（持续资金池模式）

> ⚠️ 该版本的持续资金池功能已于 v3.35.0 移除，由「资金排程 + 分配计划」（分配是计划，不是记录）取代。

### ✨ 新增

- **持续资金池**：废弃月度预算快照模式，改为持续累积的资金池 + 流水账。池子余额 = 全部 `FundTransaction` 流水金额聚合（`Sum(amount)`），永不重置，一条流水记录对应一次 注入/分配/消费扣减/手动调整/退款

- **资金流水模型**：新增 `FundTransaction`（池子外键 + 类型 + 金额 ± + 操作后余额 + 备注 + 关联账单 ID + 时间），替换原 `MonthlyBudget`/`PoolAllocation` 两表

- **关联分类自动扣减**：`FundPool` 新增 `linked_categories` JSON 字段；快速记账（`BillCreateView`）写入支出账单后，`FundService.auto_deduct_from_bill()` 按分类匹配优先级最高的池子，自动写入 `spend` 流水扣减余额

- **资金操作 API**：`fund-transactions/inject`（注入）、`allocate`（分配多池）、`adjust`（手动调整余额）、`pool/<id>`（流水列表）；`fund-overview/summary`（总资产/健康度/各池目标进度）、`balances`（余额明细）

- **新资金分配看板**：`FundDashboard.vue` 重写为持续资金池单页——总览卡片（总资产/健康度/池子数量）+ 池子卡片网格（余额/蓄水池目标进度/关联分类标签/人生意图）+ 分配/注入/新建编辑/删除/流水详情弹窗，池子 CRUD 并入看板，删除冗余 `FundPoolManager.vue`

- **健康度算法重做**：蓄水池达标 40 分 + 无负余额 30 分 + 池子多样性 30 分，满 100 分

### 📝 文档

- 更新 `wealth/README.md`（后端）：FundPool/FundTransaction 模型、`fund_service.py`、资金分配 API 端点、持续资金池与账单自动扣减语义

- 更新 `wealth/README.md`（前端）：`FundView.vue`、`FundDashboard.vue`、fund store/api/types

---

## [2026-08-11] v3.33.0 — 自由职业资金分配系统 Phase 1

### ✨ 新增

- **资金池配置**：财富模块新增「资金分配」页面（`/wealth/fund`），支持自定义资金池管理——三种分配类型（`fixed` 固定金额 / `ratio` 收入比例 / `reservoir` 蓄水池目标），含图标、颜色、优先级、启用开关、人生意图描述。列表卡片网格 + 新增/编辑/删除弹窗。后端 `FundPool` 模型 + `FundPoolViewSet` CRUD

- **月度资金概览**：按年月维度展示资金健康度评分（0-100）、当月总收入、已分配金额、初始注入资金，各池子进度条（已分配/已花/剩余），蓄水池达标展示「已达标/蓄水中」状态

- **资金分配**：月度分配弹窗选择各池子分配金额，后端 `allocate_funds` 事务内写入 `PoolAllocation`，覆盖式更新，预算状态置为 `active`

- **初始注入资金**：设置月度一次性注入的总池资金

- **资金健康度算法**：分配执行率 25 分 + 风险缓冲达标率 30 分 + 支出偏差率 25 分 + 池子多样性 20 分，满 100 分

- **删除保护**：资金池已有分配记录时禁止删除（`ProtectedError` → 400），提示可先停用该池子

### 🐛 修复

- **「新增池子」按钮无响应**：`FundPoolViewSet` 列表默认启用 DRF 分页，`GET /fund-pools/` 返回 `{count, next, previous, results}` 包装对象；前端 store 将整个对象赋给 `pools` ref，模板 `v-for :key="pool.id"` 遍历到 `null`（next/previous 键）抛出 `Cannot read properties of null`，组件渲染崩溃导致按钮无响应。修复：`FundPoolViewSet` 设置 `pagination_class = None` 返回纯数组 + store `fetchPools` 兼容 `results` 解构

### 📝 文档

- 更新 `wealth/README.md`（后端）：资金池三模型、`fund_service.py`、资金分配 API 端点、健康度算法与分配/删除保护语义

- 更新 `wealth/README.md`（前端）：`FundView.vue`、`FundPoolManager.vue`、`FundDashboard.vue`、fund store/api/types

---

## [2026-08-09] v3.32.0 — 固定开销详情弹窗优化 + 底部状态栏周数显示

### 🔧 优化

- **固定开销详情弹窗排版优化**：弹窗加宽至 650px，开销项目改为 3 列对齐表格（项目名弹性占满、原始金额 150px 右对齐、折合月均 120px 右对齐加粗），月固定开销/日固定开销汇总改为纵向堆叠的 18px 加粗蓝色大数字，备注移至底部灰底区域；底部操作新增「复制并编辑」按钮复用表单填充逻辑。同时修复 `append-to-body` 挂载导致详情弹窗样式失效的遗留问题

- **底部状态栏周数显示**：LayoutFooter 日期时间左侧新增「第N周」徽标，按 ISO 周算法随秒级时钟刷新，12px 灰底圆角样式

---

## [2026-08-05] v3.31.0 — 打卡里程碑同步 + 收件箱已废弃 + 固定开销周期增强 + 时薪附加收入

### ✨ 新增

- **打卡自动推进里程碑**：目标打卡（今日已打卡）时，优先完成打卡日期对应的里程碑；倒计时等无日期里程碑则推进下一个未完成里程碑，自动发放奖励并同步进度。补打卡（指定日期）同样触发，重复打卡不重复推进

- **收件箱「已废弃」状态**：新增 `abandoned` 状态 + `abandon_reason` 废弃原因字段，记录头脑一热制定、因不合理或时过境迁不再需要处理的事项。统计卡片扩展为 6 张（新增 🗑️ 已废弃，可点击筛选），列表灰色删除线样式，日历视图不再展示已废弃事项

- **固定开销计算器**：工具箱全栈工具，自定义开销项目（图标/名称/金额），每条项目支持按日/月/年周期记录，后端统一换算为每天/每月/每年三档总额（日 ×30 = 月、日 ×365 = 年，旧数据默认按每月口径兼容回填）。结果区三列大数字 + 各项目「原始 → 每日 → 每月 → 每年」换算明细与占比条 + 智能提示；历史记录支持编辑/复制/查看/删除

- **时薪计算器附加收入**：支持配置额外收入来源（名称/金额/日·月·年周期），时薪改为「月总收入（工资+附加收入）÷ 总投入小时」计算；新增收入构成展示（各来源折算月额）与固定开销联动（日收入/日支出/日结余 + 开销占比健康度提示）；历史记录支持编辑/复制/查看

- **目标人生维度分布**：新增 `/goals/dimension-chart` 页面，ECharts 雷达图展示 9 大人生维度目标数与平均进度，含各维度目标明细

- **里程碑反思字段**：Milestone 新增 `difficulty_met`（遇到的困难）、`next_action`（下一步行动）；完成里程碑弹窗强制填写「此刻感悟」（含快捷短语），可补充困难与下一步行动

- **目标完成奖励金**：Goal 新增 `goal_completion_bonus` 目标完成奖励金，`default_reward_amount` 语义明确为「每项里程碑奖励」，前端表单奖励拆分为里程碑奖励/完成奖励金两项

- **管理命令 sync_field_comments**：core 新增管理命令，遍历各模型将 `verbose_name` 同步为 MySQL 字段注释（仅改 COMMENT，保留列定义/Null/默认值）

### 🐛 修复

- **工具集未显示固定开销计算器**：`ToolRegistry.auto_discover()` 仅在启动时扫描 `tools/*.py`，运行中新增的工具不会进入内存注册表。触发服务重载后工具正常出现，并归入「💰 财务」分类

- **奖励来源统计 missing goal_complete/inbox_complete**：`RewardSourceStatsSerializer` 补齐缺失的 `goal_complete`/`inbox_complete` 字段声明，来源统计前端不再始终显示 ¥0

- **目标进度 100% 未自动完成**：`recalculate()` 新增 `_auto_transition_status()`，进度达 100% 自动切换目标为已完成

- **编辑目标覆盖已完成里程碑状态**：`GoalCreateUpdateSerializer.update()` 保护已完成里程碑，编辑时不再重置为 `pending`

### 📝 文档

- 更新 `toolkit/README.md`：FixedExpense 周期换算、HourlyWageRecord 附加收入字段、内置工具表

- 更新 `inbox/README.md`：已废弃状态与统计

- 更新 `goals/README.md`：人生维度/完成奖励金/里程碑反思字段/维度统计端点

- 更新 `reward/README.md`：`goal_complete` 交易类型

- 更新 `core/README.md`：`sync_field_comments` 管理命令

---

## [2026-08-02] v3.30.0 — 工具箱新增 GIF 压缩工具

### ✨ 新增

- **GIF 压缩工具**：工具箱新增 🎞️ GIF 压缩工具，支持四种压缩手段 — 抽帧（每隔 N 帧保留 1 帧）、缩放比例/指定宽高（0 表示不限制）、颜色数（256/128/64/32 自适应调色板）、压缩质量（10-100）。前端独立组件 `GifCompressor.vue`：拖拽上传 GIF → 配置参数 → 压缩 → 实时预览压缩结果（原始/压缩后大小、压缩率、帧数对比）+ 一键下载。后端 `GifCompressorTool`（`apps/toolkit/tools/gif_compressor.py`），输出文件经 `MEDIA_URL` 可访问

- **文件上传接口泛化**：`FileToolUploadView`（`/toolkit/convert_file/`）从仅支持 `.txt` 扩展为按 `tool_key` 白名单校验扩展名（trad2simp→.txt，gif-compressor→.gif），并自动将 multipart 表单字段透传为工具参数（数值字符串自动转 int/float），`toolkitStore.runFileTool` 同步支持任意参数对象

### 📝 文档

- 更新 `toolkit/README.md`：内置工具表新增 `gif-compressor` 条目

---

## [2026-07-30] v3.29.0 — 里程碑编辑增强 + 奖励统计修复 + 表单优化

### 🐛 修复

- **奖励来源统计 missing goal_complete/inbox_complete**：`RewardSourceStatsSerializer` 声明了 4 个字段但缺少 `goal_complete` 和 `inbox_complete`，导致序列化时静默丢弃，前端始终显示 ¥0。修复：补齐两个字段声明

- **目标编辑里程碑状态被覆盖**：`GoalCreateUpdateSerializer.update()` 在更新里程碑时未保护已完成的 `status`，编辑目标时误将已完成里程碑重置为 `pending`。修复：`pop('status', None)` 跳过已完成条目的状态更新

- **目标进度未在里程碑变更后重新计算**：`GoalCreateUpdateSerializer.update()` 更新里程碑后未调用 `GoalProgressService.recalculate()`，导致 19/19 里程碑进度仍显示 84%。修复：在里程碑变更后强制重新计算进度

- **目标进度 100% 未自动跳转完成状态**：`recalculate()` 仅更新 `progress_percentage` 字段，`status` 保持 `in-progress`。修复：新增 `_auto_transition_status()` 在进度达 100% 时自动切换为 `completed`

- **目标完成奖励未触发**：`_check_goal_completion_bonus()` 仅在 `complete_milestone()` 路径检查，通过 serializer 还原里程碑进度达到 100% 时不触发。修复：在 `recalculate()` 中增加奖励检查

### ✨ 新增

- **里程碑编辑详情弹窗**：目标编辑弹窗里程碑列表改为紧凑 2 行布局（textarea + 操作按钮），点击 ✏️ 弹出详情弹窗，支持编辑里程碑描述（description）和奖励金额（reward_amount）

- **人生维度必填**：`life_dimension` 模型字段取消 `blank=True`，前端表单 added 必填校验 + 红色星标，迁移 0014

- **奖励池来源筛选新增目标完成**：流水筛选 radio-group 新增 `goal_complete` 选项

- **奖励来源分布展示目标完成和收件箱完成**：`RewardTimeline` 来源比例行新增 `goal_complete` 和 `inbox_complete` 两项统计及百分比

### 🔧 优化

- **表单必填字段红星**：全局 CSS `:deep(.el-form-item.is-required .el-form-item__label::before)` 统一显示红色星标，替代默认黑色

---

## [2026-07-27] v3.28.0 — 侧边栏导航升级 + 职业能量审计优化 + 页面整合

### ✨ 新增

- **侧边栏导航交互升级**：去除所有分类标题，使用半透明底色按模块分组（总览蓝/时间感知紫/目标琥珀/健康绿/滋养红/财富黄/连接橙/工具箱灰），菜单高度压缩（padding 8px 12px、图标 16px、间距 2px），折叠态宽度缩至 60px，侧栏独立滚动

- **职业能量审计实时分数预览**：顶部卡片实时展示当前能量指数（-100~130）及进度条，滑块根据数值动态变色（< -2 红 / < 0 橙 / ≤ 2 蓝 / > 2 绿），提交按钮改为全宽"📊 生成职业能量报告"

- **仪表盘段落金句完整展示**：段落类型金句改用 `-webkit-line-clamp: 4` 限制行数而非截断标题，超 200 字显示"点击展开全文"提示，弹窗加宽至 600px

### 🔧 优化

- **周度追踪合并到时间统计页面**：删除独立页面/路由/侧边栏入口，52 周追踪表作为时间统计底部区域，保留年份选择、基准线设置、缓存刷新、统计卡片所有功能

- **季度决策卡片迁移到汇总总览**：创建紧凑型 3 卡片组件（未达标/环比下降/最需关注），嵌入 SummaryDashboard 顶部，删除独立工作台页面/路由/侧边栏入口

- **ToolDetail 信息卡片条件隐藏**：职业能量审计页面不再显示共享工具信息卡片（该页面已有独立标题）

### 📝 文档

- 更新 `reward/README.md`：补全 `TRANSACTION_TYPES` 表格（含 inbox_complete 等 9 种类型）

- 更新 `inbox/README.md`：补全端点副作用说明（小确幸创建、奖励池同步）

- 更新 `sugar/README.md`：补全 `reward_amount` 字段说明及前端传入优先逻辑

---

## [2026-07-22] v3.27.0 — 收件箱完成修复 + 仪表盘段落金句

### 🐛 修复

- **收件箱标记完成小确幸 400 错误**：`createSugar` 缺少后端必填的 `title`/`time` 字段，`level_of_happiness` 使用前端 1-5 分制（后端要求 5-20 分制）导致请求被拒。修复：补全字段、分制映射（×4），后端 `SugarRecordSerializer.time` 增加 `input_formats` 兼容日期和时间两种格式

- **收件箱完成奖励金额不一致**：小确幸 `reward_amount` 被后端 `perform_create` 覆盖为 `level_of_happiness`（20），忽略前端传入值（12）。修复：`perform_create` 优先使用前端传入的 `reward_amount`，`sugar/serializers.py` 将该字段移出 `read_only_fields`

- **收件箱完成奖励流水类型**：`transaction_type` 从无意义的 `manual_add` 改为 `inbox_complete`，流水列表新增 `📥 收件箱完成` 绿色标签显示，`sourceEmoji` 同步支持。模型 `TRANSACTION_TYPES` 新增选项，历史 1 条数据已迁移

### ✨ 新增

- **仪表盘段落金句完整显示**：段落类型金句不再截断为缩减标题，改用 `-webkit-line-clamp: 4` 显示完整内容（最多 4 行），超 200 字显示"点击展开全文"提示，点击弹窗查看完整段落。短句类型保持不变

### 🔧 优化

- **汇总总览隐藏无数据模块**：`身体-状态关联（近12周）` 卡片暂无数据支撑，注释隐藏，下方月度明细表格自动上移

---

## [2026-07-21] v3.26.0 — Logseq 日记集成 + 覆盖进度基线修复

### ✨ 新增

- **Logseq 日记集成**：`UserProfile.logseq_path` 配置 Logseq 日记目录路径，`OneDayPageSerializer` 新增 `logseq_file` 字段根据日期自动检测对应 md 文件是否存在，`OpenLogseqView` 返回原始 Markdown 内容（剥离 YAML 元数据）。前端 `LogseqViewer.vue` 弹窗组件使用 `marked` 渲染 Markdown（GFM + 换行转 br），长词自动折行不溢出。日记流列表主题列显示链接图标 + tooltip，行单击 / 操作列「Logseq」按钮打开弹窗查看。系统设置页 `/admin/settings` 支持 Logseq 路径配置 + 隐私模式开关，侧边栏系统运维新增入口

### 🔧 优化

- **覆盖进度基线修复**：进度条从"当前已度过周数"开始计算而非 0%，三段式显示"已度过 X 周 (Y%) + 可支撑 Z 周 = 覆盖至 N%"。永不耗尽时进度条 100%

- **日利息显示条件**：利息行不再依赖 `support_weeks !== Infinity` 判断，有日利息率即显示

### 🐛 修复

- **永不耗尽覆盖进度**：后端返回 `null` 表示永不耗尽后，前端 `coveragePercent` 改用 `=== null/undefined` 判断，返回 100%

### 📝 文档

- 更新 `temporal/README.md`：新增 `logseq_file` 字段说明、`OpenLogseqView` 端点

- 更新 `core/README.md`：`UserProfile` 新增 `logseq_path` 字段说明

---

## [2026-07-19] v3.25.0 — 仪表盘快速读者互动 + 日记热力图修复

### ✨ 新增

- **仪表盘快速记录读者互动**：仪表盘新增"快速记录读者互动"卡片，粘贴读者留言 + Ctrl+Enter 两步完成录入，默认留言 +1 分覆盖 80% 场景。展开高级选项可切换互动类型（留言/点赞/转发/关注/打赏）、填写读者名、调整能量值（+1/+3/+5）。保存后自动刷新最近 3 条互动摘要，用户偏好持久化到 localStorage

### 🐛 修复

- **默认日记重复生成**：`DailyLogAutoService.generate_default_log()` 改用 `begin_date__year/month/day` 日期级检查（原逻辑只检查 `otype='ONEDAY'`），避免在有 MIGU 等类型日记的日期再生成 ONEDAY。清理 6 月至今 8 条冗余默认日记

- **热力图默认日记不可见**：热力图 `getDayColor` 区分"无记录"（灰色 `colorScale[0]`）与"有日记但当日 0 字"（浅绿 `colorScale[1]`），使默认日记也能在热力图上显现

- **类型标签 type prop 警告**：`getTypeTagType` 将 SUMMARY/ONEDAY 映射为 `'info'`，兜底返回 `'info'` 而非空字符串，消除 el-tag type prop 校验警告

### 📝 文档

- 更新 `relation/README.md`：新增 `quick_record`/`recent` 端点说明

- 更新 `temporal/README.md`：新增 `DailyLogAutoService` 说明

---

## [2026-07-13] v3.24.0 — 里程碑折叠 + 复盘工具箱修复 + 现金流推演利息复利

### ✨ 新增

- **现金流推演日利息复利**：推演算法 `calculate_coverage` 新增 `daily_interest_rate` 参数（日利息率，小数），每日扣除预算后计息再复利，支持余额宝等货基场景。`WealthCurrentScenario`/`WealthScenarioHistory` 模型新增 `daily_interest_rate` 字段，前端 `ControlPanel` 推演面板新增"日利息率"输入（万分之单位），覆盖进度条改为"已度过 + 可支撑 = 覆盖至"三段式显示

- **环境变量模板**：`.env.example` 环境变量模板，含 `SECRET_KEY`/`DB_PASSWORD` 等必要变量

### 📝 文档

- 更新 `wealth/README.md`：推演算法描述补充日利息复利说明

### ✨ 新增

- **里程碑列表连续同名折叠**：行为追踪卡片里程碑列表，连续 3 条以上相同标题的已完成记录自动折叠，保留首尾，中间显示"展开 N 条相同记录"占位符。标题比较前经 `normalizeName` 归一化（去除倒计时数字、日期等动态部分），支持展开/收起切换

### 🔧 优化

- **复盘工具箱表单回填**：每日复盘填表回填时去除冗余 `|| {}` 回退，避免空对象覆盖默认值

---

## [2026-07-06] v3.23.0 — 语言训练器 + 旅行路线全屏重构

### ✨ 新增

- **语言训练器**：工具箱全栈工具，4种训练类型 — 词汇颗粒度（粗糙→精确词汇替换）、场景描述（总结+还原）、语言素材（来源+原句+赏析）、逼近修订（初版→多轮修订→终版），TAB 切换筛选 + CRUD 历史列表，含 revisions JSON 动态数组编辑。后端 `LanguageTraining` 模型 + `LanguageTrainingViewSet` + `LanguageTrainerTool` 注册，前端 `LanguageTrainer.vue` + API 层 + 路由 + 侧边栏入口

### 🔧 优化

- **旅行路线推演全屏重构**：左侧 50px 可折叠窄条 + 340px 抽屉覆盖层滑入/滑出动画，地图占满全屏区域（`calc(100vh - 80px)`），选择路线后抽屉自动收起，空状态引导提示居中显示，控制栏 absolute 悬浮地图底部，不再使用 el-row 分栏布局

### 🐛 修复

- **语言训练器保存后列表空白**：后端 `LanguageTrainingViewSet` 设置 `pagination_class = None` 返回纯数组，前端误用 `res.data?.results` 解构分页格式导致始终取到 `undefined`。修复：`fetchRecords` 检测 `Array.isArray(data)` 兼容纯数组和分页对象两种响应格式

---

### ✨ 新增

- **父子目标关联**：Goal 模型新增 `parent_goal` 自关联外键，支持目标嵌套。后端 `GoalProgressService.recalculate` 递归向上冒泡（子目标平均进度 → 父目标进度），`GoalDetailSerializer` 嵌套 `sub_goals` 列表，`GoalListSerializer` 新增 `sub_goals_count`/`parent_goal_name`。API 端点 `GET /goals/goals/{id}/sub_goals/`。前端 `GoalCard` 显示父目标名称（紫色徽章）和子目标数量，`GoalHub` 子目标弹窗含进度条，`GoalDetail` 编辑弹窗新增父目标选择器（可搜索、排除自身和已有父目标的目标）

### 🔧 优化

- **小确幸编辑事务保护**：`perform_update` 将 `serializer.save()` 移入 `transaction.atomic()` 块，确保奖励池与记录数据一致

- **小确幸编辑 `years/month` 自动同步**：`time` 字段变更时自动更新 `years`/`month`，避免日期与年份月份脱节

- **里程碑取消完成扣回奖励**：`MilestoneViewSet.perform_update` 在里程碑从已完成变为其他状态时调用 `deduct_reward` 扣回奖励并重置 `reward_synced`

- **标签合并去重保护**：合并操作替换标签后增加顺序保持去重，防止新标签已在记录中时产生重复

- **全局搜索异常隔离**：5 个模块各自独立 `try/except`，单模块异常不级联崩溃

### 🐛 修复

- **父子目标循环引用**：Serializer 新增 `validate_parent_goal` 向上遍历检测循环引用；`GoalViewSet.perform_update` 拒绝将已是子目标的目标设为父目标。API 层双重防护

- **小确幸编辑 `serializer.save()` 在原子块外**：`serializer.save()` 在 `transaction.atomic()` 外执行，若奖励池更新失败则数据不一致。修复：移入原子块内

- **小确幸编辑不更新年份月份**：编辑 `time` 后 `years` 和 `month` 保持旧值。修复：`perform_update` 末尾自动同步

- **取消里程碑完成不扣回奖励**：completed→pending 时已发放奖励未扣回。修复：调用 `deduct_reward` + 重置状态

- **标签合并产生重复**：新标签已在记录中时替换后变成"标签A,标签A"。修复：替换后去重

- **全局搜索单模块异常导致整体 500**：任一模块查询失败（如表结构变更）导致全接口崩溃。修复：各模块独立 try/except

---

## [2026-07-03] v3.21.0 — 小确幸快乐类型重构 + 编辑修复

### ✨ 新增

- **小确幸快乐类型五类重构**：后端 `SugarRecord.joy_type` 选项从七类（创造/社交/独处/户外/美食/学习/其他）改为五类（感官型/秩序型/联结型/意外型/独处型），前端 `JOY_TYPE_OPTIONS`/`JOY_TYPE_COLORS` 同步更新，新增迁移 `0006`。旧数据保留不变，编辑时显示原值

- **小确幸编辑弹窗发生日期**：弹窗新增日期选择器，编辑时自动回填原日期，支持修改

- **全局搜索增强**：跨模块搜索（Quote/OneDayPage/SugarRecord/GoodThing/ReviewRecord），前端 SearchBar 组件+全局搜索框

- **标签管理器**：独立运维页面 `/admin/tag-manager`，聚合 Quote/Sugar/GoodThing 三模块标签，支持重命名/合并

### 🔧 优化

- **目标编辑里程碑保存**：后端 `GoalCreateUpdateSerializer.update()` 新增里程碑增量同步（匹配 ID 更新、新增、删除），前端回填带上 `id: m.id`，不再删除重建

- **小确幸奖励金额**：`perform_create` 改用 `serializer.save(reward_amount=level)`，奖励金额直接等于快乐程度值，不再经过阈值映射

- **侧边栏**：新增"系统运维"分组，标签管理器移至 `/admin/tag-manager`

### 🐛 修复

- **目标编辑新增里程碑未保存**：后端 `GoalCreateUpdateSerializer.update()` 原 `validated_data.pop('milestones', None)` 丢弃里程碑数据，重写为完整的增量同步逻辑

- **小确幸编辑日期变为修改日期**：`handleSubmit` 始终用 `new Date()` 覆盖 `time`，改为 `form.event_date` 优先

- **小确幸新增奖励金额不一致**：按钮显示 12 元，保存后变 5 元。`perform_create` 绕过 `serializer.save()` 走 `_calculate_reward_amount` 阈值映射，改为直接 save 并同步奖励池

---

## [2026-07-02] v3.20.0 — 目标看板重构 + 仪表盘金句 + 良品率 UI 修复

### ✨ 新增

- **目标看板统计卡片重构**：后端新增 `status_stats` 端点返回各状态目标数量，前端以动态卡片组替代 radio-button 筛选 Tab，仅显示有数据的状态卡片，点击卡片蓝底白字高亮筛选，默认选中"进行中"，再次点击可取消

- **仪表盘每日金句**：将汇总总览的金句卡片同步至 Dashboard 首页，含金句展示/换一句/全文弹窗，与汇总总览各自独立

- **行为追踪里程碑点击完成**：`BehaviorTrackCard` 里程碑状态图标（○/✅）增加点击事件，弹出确认框后调用 `toggle_milestone` API 切换完成/重置，含奖励发放

### 🔧 优化

- **良品率产出记录列表**：页面宽度从 1100px 调整为 1200px 对齐仪表盘，日期列 `white-space: nowrap` 防止换行

- **良品率操作列**：多轮迭代最终确定为文字按钮 + `fixed="right"` + `overflow: visible` 确保完整显示

- **目标看板筛选栏**：移除"类型"筛选下拉，保留搜索 + 优先级 + 新增行为 + 重置

### 🐛 修复

- **产出记录表格重复标签**：HTML 未闭合错误导致两套 `el-table` 嵌套渲染，删除旧表残留标签

- **产出记录删除按钮被裁切**：`el-table__fixed-right` 默认 `overflow: hidden` 截断固定列，强制 `overflow: visible` 修复

---

## [2026-06-30] v3.19.0 - 开源准备（Docker + README + LICENSE）

### ✨ 新增

- **Docker 容器化部署**：`docker-compose.yml` 编排 mysql:8.0 + backend + frontend 三服务，`backend/Dockerfile` 两阶段构建（python:3.14-slim），`frontend/Dockerfile` 两阶段构建（node:22-alpine 编译 → nginx:alpine 静态托管），`nginx.conf` SPA fallback + `/api/`/`/media/`/`/static/` 反向代理

- **开源配套文件**：`.env.example` 环境变量模板、`.dockerignore` 排除非必要文件、`LICENSE` MIT 协议、`README.md` 完整使用说明

### 🔧 优化

- **README.md** 重写：补充 Docker 部署流程、功能模块表格、设计理念，保留完整项目目录结构，GitHub 链接指向 jiumigu

---

## [2026-06-29] v3.18.0 - 月度复盘负数结余 + 盘点排序修复

### 🐛 修复

- **月度复盘结余负数截断**：后端 `get_monthly_list` 和 `_parse_balance_list` 的 `balance` 从依赖 `bi.mbalance` 改为 `income - expense` 实时计算，确保与 `savings_rate` 数据源一致，不再出现 balance=¥0 但 rate=-110.8% 的矛盾

- **月度复盘列表结余符号丢失**：前端 `formatAmount` 内部使用 `Math.abs` 导致负数符号丢失，改为模板层条件渲染 `￥` / `-￥`，负数显示红色

- **月度复盘结余率负数颜色**：`ReviewHeader` 结余率 `valueClass` 从写死 `text-info` 改为动态判断，负值时显示红色

- **月度复盘手动录入 400 错误**：前端 `handleSaveBalanceInfo` 未将弹窗字段映射为模型字段（`income→wageincome` 等），后端创建新记录时未传 `age` 等必填字段。修复：前端添加字段映射、后端统一使用 `partial=True`、序列化器增加 `extra_kwargs` 默认值

- **`wealth_balance_list` 表 `age` 字段 NOT NULL 约束冲突**：手动录入新记录时未传 `age` 导致数据库报错。删除 `age` 列（ALTER TABLE DROP COLUMN），同步清理模型、序列化器和服务的引用

- **盘点历史排序错误**：`cashflow_service.py` 排序字段从 `-yearmon` 改为 `-btime`，按复盘时间倒序而非年月，确保同月多次盘点的顺序正确

### 🔧 优化

- **MonthlyReviewSerializer extra_kwargs**：`wageincome`/`outmoney`/`mbalance` 等字段设置 `required=False` + `default=0`，避免新建记录时因缺少字段报错

---

## [2026-06-29] v3.17.0 - 打卡补签 + 旅行路线重构 + 详情弹窗优化

### ✨ 新增

- **打卡日历补签**：日历格子可点击过去未打卡日期，弹出确认弹窗后补打卡。后端 `checkin` 端点新增 `date` 参数支持指定日期，`calculate_streak` 自动重新计算连续天数

- **旅行路线推演重构**：左侧仅保留已保存路线列表（25%），输入区移至弹窗，地图扩大至 75%。新建/编辑通过统一弹窗完成，支持拖拽排序目的地，选中态高亮

### 🔧 优化

- **好恶物详情弹窗**：加宽至 700px，`white-space: pre-wrap` 保留换行，`close-on-click-modal=false` 防止误关，`el-descriptions` 表格替换为分区卡片布局

- **日记流按钮位置调整**：新增日记按钮从右上角移到筛选栏重置按钮左侧，筛选栏样式改为 `space-between` 两端对齐

### 🐛 修复

- **未来日期打卡拒绝**：后端校验 `checkin_date > date.today()` 时返回 400 错误

- **已打卡日期重复触发**：日历格子已打卡状态点击提示"该日期已打卡"而非再次弹出确认

---

## [2026-06-26] v3.16.0 - 好恶物档案馆增强 + 体重图修复

### ✨ 新增

- **好恶物详情弹窗**：点击卡片弹出详情对话框，700px 宽，内容区分好物/歹物独立展示，保留用户输入换行（`white-space: pre-wrap`），含元信息栏（类型/类别/评分）和底部状态栏

- **好恶物卡片点击跳转**：TreasureCard 新增 `click-card` 事件，整张卡片可点击打开详情

### 🔧 优化

- **好恶物卡片等高**：卡片使用 `display: flex; flex-direction: column; height: 100%` 确保网格内全部等高

- **好恶物卡片 3 行截断**：`why_good` 描述使用 `-webkit-line-clamp: 3` 限制最多 3 行，超出省略

- **好恶物卡片操作按钮不触发跳转**：`card-actions` 区域使用 `@click.stop` 阻止冒泡，编辑/删除按钮点击时不触发详情弹窗

### 🐛 修复

- **体重趋势图目标线显示错误**：markLine 从最终目标改为当前未达成里程碑的目标值（如从 127.0 斤修正为 121.0 斤），移除散点系列避免多里程碑索引重叠导致的错误渲染

---

## [2026-06-25] v3.15.0 - 时薪自由职业模式 + 工具箱 UI 统一

### ✨ 新增

- **时薪计算器自由职业模式**：支持正式职业/自由职业双模式切换。自由职业含固定时长（月工作天数+日均时长）和弹性工时（周各天时长配置+月周数）两种子模式，后端 `_calc_freelance` 独立计算逻辑，历史列表新增"模式"标签列

- **时薪计算器脱敏支持**：历史列表月薪列接入 `maskAmount`，隐私模式开启时显示 `¥*,***.**`，关闭时恢复正常格式化

- **工具栏统一"返回工具集"按钮**：TravelRoute/EnvironmentAudit/CareerEnergyAudit 嵌入 ToolDetail 组件不再自带返回按钮（由 ToolDetail 统一提供），其余工具页各保留一个

### 🔧 优化

- **工具栏页面宽度统一**：全部 9 个工具页 `padding: 20px`，移除 FreeSpending 的 `max-width: 720px` 限制，以 DecisionLog 为基准对齐

- **返回按钮 CSS 加固**：`.back-bar` 统一使用 `display: flex; flex-wrap: nowrap` 防止图标与文字在窄容器中换行分离

### 📝 文档

- 更新 CHANGELOG.md：本次变更记录

---

## [2026-06-25] v3.14.0 - 体重管理增强 + 布局修复

### ✨ 新增

- **体重目标调整记录**：`WeightGoalAdjustment` 模型追踪每次目标变更（调整前/后值、变更量、原因），API 端返回活跃目标的所有调整流水，前端 目标调整记录 时间线卡片展示（before→after + 变更标签 + 原因）

- **体重月度进度自动推进**：`check_weight_goal_status` 在里程碑达成后自动递增 `goal.current_month` 并更新 `current_month_start_weight`/`current_month_target`，兼容旧数据修复（自动扫描已达成未推进的月份）

- **体重趋势图 markLine 目标线**：目标体重以虚线 markLine 标注在图表中（"目标 105斤"标签），替代独立的 ECharts 目标线 series，legend 更简洁

### 🔧 优化

- **体重趋势图 Y 轴动态适应**：从固定 `min: 90` 改为基于目标体重和历史数据自动计算下限（`Math.floor(target - 5)`），消除下方大段留白，体重波动更明显

- **月度进度阶段列表去重**：修复展开全部时的渲染重复问题——`visibleMilestones` 始终只返回当前月份，其他阶段由 `el-collapse-transition` 独占渲染，消除 8 条重复

### 🐛 修复

- **月度进度卡片高度撑开异常**：移除 `.progress-section` 的 `height: 100%`，添加 `overflow: visible` 防止卡片被 BMI 列拉伸

- **进度卡片与趋势图间距缺失**：`.section-row` 从仅 `margin-top` 改为上下各 16px，添加 `overflow: visible` 防止裁剪

- **el-collapse-transition 动画裁剪内容**：添加 `:deep(.el-collapse-transition) { overflow: visible }` 确保展开动画不遮挡后续元素

### 📝 文档

- 更新 `CHANGELOG.md`：本次变更记录

---

## [2026-06-23] v3.13.0 - 目标行为追踪 + 小确幸修复

### ✨ 新增

- **目标行为追踪模式**：当目标仅绑定 1 个行为时，展开区自动切换为打卡追踪视图（连续天数/进度条/打卡按钮/日历热力图），下方展示完整里程碑列表（✅/○ 状态图标 + 奖励金额 + 状态标签），每条右侧保留 ✏️ 编辑入口（详情描述/完成备注/自我批阅），样式与原有里程碑列表一致

- **小确幸标签区优化**：弹窗和列表中标签在同一行内换行显示，不单独分两行，视觉更紧凑

### 🔧 优化

- **小确幸快乐程度**：后端 validator 范围从 1-10 扩展为 5-20，奖励直接跟随快乐值（取消阈值映射），编辑弹窗同步显示原始快乐值

- **小确幸编辑奖励同步**：编辑快乐程度时自动按新旧差额调整奖励池余额并生成奖励流水

### 🐛 修复

- **小确幸保存失败**：后端 validator 仍限制 1-10，与前端 5-20 滑块不匹配，导致评分 10-20 提交后校验拒绝

- **小确幸编辑保存 400**：前端 `joy_type: form.joy_type || null` 传 `null`，模型字段无 `null=True`，DRF ChoiceField 拒绝。改为 `joy_type: form.joy_type || ''`

- **小确幸编辑奖励值显示错误**：`_calculate_reward_amount` 仍使用旧阈值映射（如 17→¥10），改为直接使用 `reward_amount=level` 显示原始值

- **小确幸编辑奖励池未同步**：`perform_update` 仅存记录未调整池余额，新增 delta 差额调整 + RewardTransaction 记录

---

## [2026-06-23] v3.12.0 - 复盘工具箱 + 摘录馆增强

### ✨ 新增

- **复盘工具箱**：工具箱全栈工具，5种复盘模板 — 每日复盘（约哈里窗四象限+情绪清单）、周复盘（完成/计划/反思）、月复盘（GRAI+ORID深度复盘）、季度复盘（滋养/消耗/害怕/烦恼/80岁遗憾/5年路径）、人生编舟（生命线/目标/四象限/深度复盘），历史记录可回溯编辑

- **摘录馆标签展示**：列表卡片新增标签渲染，每条摘录显示语言标签和所有分类标签

### 🔧 优化

- **日程视图日历紧凑化**：外层 padding 缩减至 8px，日历卡片 shadow 去掉，`el-card__body` 压缩至 8px，日期格高度提升至 80px，表头/按钮/单元格全面紧凑，最大化日历显示区域

- **摘录馆统计与分页**：统计数字改为后端 `/toolkit/quotes/stats/` 接口返回真实数据库总数，列表新增分页控件（每页20条），筛选切换重置到第1页，筛选条件（language/is_paragraph）在后端正确生效

### 🐛 修复

- **摘录馆统计与实际不符**：前端的 `computeStats()` 仅基于当前页数据计算，翻页后统计错误。改为后端 `stats` 端点聚合全量数据

---

## [2026-06-22] v3.11.0 - 自由支配额度计算器

### ✨ 新增

- **自由支配额度计算器**：工具箱全栈工具，基于流动资产+年收入+债务+工作年限计算每次消费无需纠结的额度，自动保存计算历史，支持回溯删除

- **收件箱快速输入支持自定义类别**：快捷输入组件同步开放 `allow-create`，无需打开完整弹窗即可输入新类别

### 🔧 优化

- **好朋友周期趋势图分段**：默认显示最新12条记录，支持"← 更早"/"更新 →"/"最新"分页导航，避免记录过多时图表拥挤

### 🐛 修复

- **收件箱自定义类别保存失败**：模型层 `category` 字段 `choices=CATEGORY_CHOICES` 限制可选值，DRF CharField 序列化校验通过后 Django ORM 模型校验仍拒绝。删除模型 `choices` 约束，自定义类别正常持久化

- **好朋友跟踪分页 Vue 警告**：`fetchRecords` 定义在 `reactive` 对象内，模板 `@current-change` 无法访问。提取为顶层 `loadRecords()` 函数，消除控制台警告

---

## [2026-06-17] v3.10.0 - 例假跟踪 + 决策日志 + 个人画像

### ✨ 新增

- **例假跟踪**：全栈新模块，MenstrualRecord 模型 + CRUD API + 统计接口（平均周期/偏移/下次预测）+ 周期趋势折线图（ECharts）+ 56 条历史数据（2021~2026）

- **决策日志工具**：工具箱全栈工具，7大偏误分析统计 + 决策记录（含选项列表/恐惧指数/结果判定） + 回顾复盘弹窗

- **个人画像仪表盘**：`/summary/profile` 7维度聚合（健康/精力/情绪/关系/良品率/收件箱/决策），颜色编码评分卡片

- **小确幸快乐类型**：`joy_type` 字段 + 快乐偏好图谱 `/sugar/joy-types`

- **收件箱"犹豫中"状态**：hesitating 状态 + hesitate_reason 字段 + 恢复"开始行动"入口

- **收件箱自定义类别**：类别下拉支持 `allow-create` 自由输入新类型，筛选区自动包含自定义类型

- **身体-状态关联图**：汇总看板 BodyMindChart，ECharts 柱线混合图展示健康自查与精力/情绪关联

- **仪表盘随机回顾新增摘录馆**：random_retro 接口新增 Quote 来源，四种内容等概率随机

### 🔧 优化

- **定期存款倒计时列**：新增"倒计时"列，>30天绿/7~30天蓝/<=7天橙/过期红/已取出灰

- **小确幸编辑弹窗**：快乐程度 5-20 分制，奖励自动跟随快乐值，标签区预设+自定义双模式

- **职业能量审计**：表单宽度 100%，结果中嵌入环境校准提示（环境分值连续 3 个月为负时高亮提醒）

- **身体健康自查**：表格宽度 100%，日期列不换行，新增详情弹窗（2 列网格展示全部字段）

- **金句管理→摘录馆**：模型 docstring/verbose_name、前端页面/路由/侧边栏全面更名

- **仪表盘随机回顾**：后端过滤默认日记标题"幸福未被发现，就叫做普通的一天"（Quote/OneDayPage 两处）

### 🐛 修复

- **收件箱编辑保存 400**：双因修复 — `updateInboxItem` 改用 PATCH（resume 操作只发 2 个字段不再缺字段）+ `hesitate_reason` 前端传 `null` 改为 `''`（模型无 `null=True`）

- **仪表盘随机回顾仍显示默认标题**：summary random_retro 接口 OneDayPage 增加 `exclude(title__icontains='幸福未被发现')`

---

## [2026-06-10] v3.9.0 - 里程碑增强

### ✨ 新增

- **里程碑详情字段**：Milestone 模型新增 `description` 字段，编辑目标时可为每个里程碑填写详细说明，看板中以左边框蓝色标识展示

### 🔧 优化

- **新增里程碑不重置已完成记录**：`GoalCreateUpdateSerializer` 不再 `all().delete()` 所有里程碑再重建，只管理 `pending`/`in-progress` 状态，已完成的里程碑（含完成备注、奖励记录）完全保留

- **收件箱转里程碑自动同步内容**：`ConverterService` 创建里程碑时将 `inbox_item.content` 自动填入 `description` 字段

### 🐛 修复

- **编辑已完成里程碑重复发放奖励**：`MilestoneViewSet.perform_update` 用 `self.get_object()` 读取旧状态，仅当状态从非完成变为完成且未同步过奖励时才发放，编辑备注不触发

---

## [2026-06-09] v3.8.0 - 收件箱日历联动 + 日程视图

### ✨ 新增

- **收件箱与日历联动**：后端 `inbox/items/calendar/` 端点按年月筛选有截止日期的待办事项，里程碑支持 `target_date_year/month` 查询参数

- **日程视图**：`/temporal/schedule` 全功能日历页，el-calendar 聚合收件箱事项和里程碑，点击日期查看详情列表

- **事项截止日期视觉增强**：收件箱列表逾期标红、2天内标橙、"今天/明天/昨天截止"相对日期提示

### 🔧 优化

- **日历圆点状态区分**：待办红色 `#f56c6c` / 已完成绿色 `#67c23a`，8px 更醒目

- **事项列表UI重构**：来源图标标签（📥/🎯）+ 状态圆点 + 标题 + 日期，已完成标题加删除线

- **已完成事项保留在日历**：后端排除 `processed`（已转目标）而非仅 `pending`，done 状态正常显示绿色圆点

- **已转目标不重复**：收件箱 `processed` 状态不返回日历，里程碑端已显示

### 🐛 修复

- **日历圆点不可见**：CSS class 名不匹配（`.dot-todo` 定义 vs `.todo` 渲染），修复为 `.dot.todo`

---

## [2026-06-08] v3.7.0 - 季度决策工作台 + 旅行统计修复 + 收件箱UI整合

### ✨ 新增

- **季度决策工作台**：`/summary/quarterly` 全栈功能，自动生成7模块季度对比报告（环比/同比），智能追问引擎（检测暴跌/飙升/低分/年度落后等模式），追问回答持久化，ECharts 季度对比柱状图

- **收件箱统计卡片可点击筛选**：4张统计卡片（待处理/已完成/已处理/总条数）替换旧组件，点击卡片按状态筛选，再次点击取消

- **月度明细达成率列**：汇总总览月度表格新增百分比列，≥80%绿/50-80%橙/<50%红

### 🔧 优化

- **旅行省份解析**：`get_province()` 新增缩写→全称映射（"浙江"→"浙江省"）和城市名→省份反向查找，25条记录全部正确解析

- **旅行统计卡片**：从4张扩展至6张，新增"旅行记录"条数和"累计天数"，卡片布局调整为6列

- **收件箱筛选整合**：删除独立筛选按钮行，统计卡片承担筛选功能（可点选/取消），视觉更简洁

### 🐛 修复

- **旅行记录三个数字不一致**：`get_province()` 无法解析缩写省份名（"浙江"）和城市名（"宁德市"），导致热力图仅显示13/25条记录。修复后3个数字统一：25条记录=25次到访≥19个城市≥3个省份

## [2026-06-04] v3.6.0 - 周度时间追踪 + CSV 导入加固 + 里程碑弹窗

### ✨ 新增

- **年度周度时间追踪**：52周×N年矩阵表，按百分比染色，支持年份选择，统计卡片（年度总时长/周均/达标周数/达标率）

- **周度时间固化缓存**：`WeeklyTimeCache` 模型，管理命令 `refresh_weekly_cache` 聚合 TemporalTask，避免实时 CONVERT_TZ 性能问题

- **里程碑详情弹窗**：目标卡片点击标题弹出弹窗，支持查看/添加/勾选里程碑，显示进度汇总（百分比/完成数/总数/状态）

- **里程碑截止日期编辑**：已有里程碑旁显示✏️按钮修改截止日期，未设置时显示"+ 设置截止日期"入口

- **缓存刷新机制**：周度追踪页手动刷新按钮 + CSV 导入成功后自动刷新缓存

- **行为记录发生日期**：编辑弹窗新增 `action_date` 日期选择器，默认当天，支持补录历史行为；列表中显示实际发生日期

- **好东西档案馆**：全栈新模块，记录亲自验证过的好东西（吃/穿/用/店/地方/方法），卡片式布局 + 类别筛选 + 评分系统

- **好恶物双面档案**：在好东西基础上扩展，支持记录"歹物"（踩坑记录），TAB 切换查看，歹物卡片红色警告样式，含踩坑原因/实际后果字段

### 🔧 优化

- CSV 导入：支持中文日期格式（"2026年6月3日 23:29:36"）解析

- CSV 导入：编码自动回退（utf-8-sig → utf-8 → gbk → gb2312 → latin-1）

- CSV 导入：去重覆盖模式，同一任务同一天时长相同跳过、不同则更新（不删数据）

- CSV 导入：绕过 DRF parser 限制，通过 `request._request.FILES` 读取文件

- 良品率：收件箱创建时自动设置 `occurred_at` 为当天，确保出现在月度统计中

### 🐛 修复

- **CSV 导入 415 Unsupported Media Type**：DRF DEFAULT_PARSER_CLASSES 仅配了 JSONParser，`@parser_classes` 对 ViewSet action 不生效。改用 `request._request.FILES` 绕过

- **CSV 导入 Content-Type boundary 缺失**：axios 实例默认 `Content-Type: application/json` + 手动设置 multipart 不传 boundary。修复：设 `Content-Type: undefined` 让 axios 自动生成

- **周度追踪数据为空**：MySQL CONVERT_TZ 函数不可用（时区表未加载），`start_time__week` 返回 NULL。修复：使用模型预计算 `week` 字段

- **周度日期查找同样因 CONVERT_TZ 失效**：`start_time__date` 也依赖时区转换。修复：使用 `year` + `mon` + `day` 字段查询

- **行为记录列表仅显示 10 条**：`StandardPagination` 默认 page_size=10，`ActionViewSet` 未覆盖。修复：设置 `pagination_class = None`

- **行为记录排序不生效**：`OrderingFilter` 的默认排序覆盖 `get_queryset` 的 `order_by`。修复：移除 `OrderingFilter` 和 `ordering` 属性

- **行为记录排序混乱**：`action_date` 为 NULL 的记录干扰排序。修复：`Coalesce(action_date, CAST(created_at AS DATE))` 确保排序一致

- **批量创建行为 action_date 为空**：batch 端点使用 `bulk_create` 不触发 `save()`。修复：显式传入 `action_date`

- **后端 ImportError**：`Func` 不存在于 `django.db.models.functions`，改用 `Cast`

### 📝 文档

- 更新 `CHANGELOG.md`：本次变更记录

---

## [2026-06-04] v3.5.0 - 职业能量审计 + 环境校准 + 盘点增强

### ✨ 新增

- **职业能量审计工具**：工具箱全栈工具，26项细化指标分4大维度（工作内容7项/环境与人8项/成长未来5项/身体情绪6项），-5~+5分量表，自动判定（继续/待观察/准备离开/该走了），支持折叠面板分组录入、身体信号多选、历史趋势追踪

- **环境校准工具**：工具箱全栈工具，6维度评分（允许说不知道/系统能力被当资产/噪音小于信号/身体报警能被听见/高手愿意分享/输出有回路），1-5分量表，自动判定（增值/可维持/消耗/立即离开），支持历史记录

- **收件箱分页**：后端 PageNumberPagination + 前端 el-pagination，每页10条

- **收件箱"已处理"筛选**：状态筛选新增"已处理"选项（status=processed），三状态切换

- **盘点录入改为弹窗**：新增盘点从内联表单改为 el-dialog 弹窗（600px），编辑/新增共用

- **盘点历史列表完整字段**：从4列扩展至15列（支付宝/微信/现金/建行/工行/中国银行/农信社/公积金/借出/负债/总现金流/总额/复盘时间/备注/操作）

### 🔧 优化

- 盘点历史：表格支持横向滚动（overflow-x:auto + min-width:1440px）

- 盘点历史：操作按钮 flex 容器防换行

- 盘点金额：受全局隐私脱敏开关控制（privacyMode 开启时显示 \*,***）

- 环境校准：表单标签宽度适配 160px，历史列表铺满页面并新增备注列

### 📝 文档

- 更新 `toolkit/README.md`：补全 EnvironmentAudit 模型、工具注册表

- 更新 `wealth/README.md`（后端）：补全现金盘点 API 端点

- 更新 `wealth/README.md`（前端）：补全现金盘点组件清单

- 更新 `inbox/README.md`：补充分页参数、processed 状态

- 更新 `CHANGELOG.md`：本次变更记录

### 🐛 修复

- **复制上月返回"上月无盘点记录"**：`copy_last_month` 改用 Replace 注释消除 yearmon 格式差异（DB 中混用 "202605" 和 "2026-05" 两种格式），同时修复 `create_or_update_snapshot` 中 `btime` 使用 `datetime.now()` 返回 datetime 而非 date 导致序列化断言错误

---

## [2026-06-03] v3.4.0 - 冲突追踪 + 良品率管理 + 收件箱增强

### ✨ 新增

- **冲突事件追踪**：关系管理子模块，记录人际冲突（含情绪等级/解决状态/关联人搜索），支持统计总览

- **个人良品率管理**：目标管理子模块，记录事项的质量判定（良品/不良品/废品）、难度评级、失败原因分析，含月度趋势和分类统计

- **收件箱转里程碑**：单条收件箱事项可直接转为指定目标的里程碑，自动排序

- **月末读者盘点**：读者群体月末汇总（总关注数/新增/取关/最佳文章），取关人数自动计算（上月总关注 + 本月新增 − 本月总关注）

- **收件箱完成联动**：标记完成时可同时新增小确幸记录和快乐银行奖励

- **收件箱工作分类**：类别新增"工作"选项

- **快速创建目标弹窗**：目标名称与里程碑名称前缀分离，里程碑不再携带目标全名

### 🔧 优化

- 收件箱：完成时支持输入完成情况备注，已完成事项显示绿色备注

- 收件箱：编辑保存后显示"保存成功"提示并自动刷新列表

- 冲突追踪：关联人支持可搜索下拉选择器

- 冲突追踪：脱敏开关开启时关联人姓名自动脱敏

- 月末盘点：编辑/删除按钮同行显示；编辑保存后自动刷新列表；新增时默认选中"公众号读者"群体

- 良品率表单：类别/质量判定/难度各占一行，对话框 600px 宽

### 📝 文档

- 更新 `relation/README.md`（后端+前端）：冲突事件追踪、读者月末盘点

- 更新 `goals/README.md`（后端+前端）：个人良品率管理

- 更新 `inbox/README.md`（后端+前端）：工作分类、转里程碑、完成备注、小确幸/奖励联动

- 更新 `CHANGELOG.md`：本次变更记录

### 🐛 修复

- 收件箱转里程碑：修复 milestones 拼接时缺少 `from django.db import models` 导致 NameError

- 收件箱转里程碑：修复视图层未传递 goal_id/milestone_name/target_date 等参数

- 快速创建目标：修复里程碑名称拼接错误（目标名称被误用为里程碑前缀）

- 冲突追踪：修复前端 `contact_id` → 后端 `contact` 字段名不匹配导致的 400 错误

- 月末盘点：修复子组件中 readerStore 导入路径错误

- 目标管理：修复 models.py 中 OutputRecord 后残留的重复 Goal/Milestone/Action/GoalReview 定义

---

## [2026-05-24] v3.3.0 - 全局隐私脱敏体系

### ✨ 新增

- **隐私脱敏体系**：后端 `UserProfile` 模型 + `ProfileView` API（GET/PATCH）

- **隐私脱敏体系**：前端 `privacyStore` Pinia 状态管理，LayoutHeader 开关 + AppLayout 横幅提示

- **隐私脱敏体系**：`shared/utils/privacy.ts` 纯函数工具集（`maskName`/`maskAmount`/`maskAmountByType`/`maskLocation`/`maskText`/`maskTags`）

- **隐私脱敏体系**：仅收入金额脱敏、支出不脱敏策略（`maskAmountByType`）

- CSV 导入支持重复校验

### 🔧 优化

- 关系管理：分类改为 drain(疏远型)/toxic(有毒型)

- 关系管理：新增 met_place 筛选器

- 目标管理：里程碑完成后自动补全体重目标

- 目标管理：详情弹窗高度翻倍，提升长内容浏览体验

- 关系管理：SQL 批量合并重复联系人

- 代码规范化：10 个财富组件统一使用 `formatAmount` 替代内联 `fmt()`

### 🔒 隐私脱敏覆盖模块

| 模块 | 脱敏内容 |

|------|----------|

| 关系列表 | 姓名 → 首字+\*，标签 → \*\*\* |

| 关系详情 | 姓名/别名/地点/场景/身份/付出/备注 |

| 旅行记录 | 目的地/上级地点/花费 |

| 目标里程碑 | 目标值/实际值/奖励金额 |

| 定期存款 | 银行名/金额/利率/利息/备注 |

| 定期统计卡片 | 总额/未到期/已到期/利息 |

| 月度日历 | 格子收支汇总文字(收入脱敏) |

| 日明细弹窗 | 收入列表脱敏，支出列表不脱敏 |

| 周明细弹窗 | 周汇总收入脱敏，支出不脱敏 |

### 📝 文档

- 更新 `core/README.md`：增补 UserProfile、ProfileView、隐私脱敏体系文档（后端模型/前端组件/脱敏规则/覆盖模块）

- 更新 `CHANGELOG.md`：本次变更记录

### 🐛 修复

- 关系管理：分页与筛选参数联动丢失（切换页码重置筛选条件）

- 关系管理：分页总数显示与实际条数不一致

- 关系管理：SQL 批量合并重复联系人（met_place 华夏→福鼎，海量→杭州）

- 目标管理：列表总数显示 18 条但仅渲染 10 张卡片（分页截断问题）

---

## [2026-05-23] v3.2.1 - 旅行路线推演 + 热力图修复

### ✨ 新增

- 旅行路线推演：路线预设 CRUD 管理（创建/编辑/删除，含目的地拖拽排序）

- 旅行路线推演：全国 718+ 城市坐标数据库，按省份/地级市/区县三级联动

- 工具箱：`CityCoordinate` 模型 + 5 个级联查询 API 端点（省份→地级市→区县）

- 工具箱：`TravelRoutePreset` 模型 + 路线预设 REST API

- 工具箱：旅行路线推演工具（ECharts 地图，动画路线，预设加载）

- 旅行记录表单：区县（district）字段 + 省市县三级级联选择器

### 🔧 优化

- 旅行路线推演：地图站点圆圈缩小，标签移至标记下方避免文字重叠

- 旅行路线推演：目的地选择由 el-select 改为 el-autocomplete，解决城市名截断

- 旅行路线推演：移除参数设置模块，精简界面

- 旅行记录表单：省份/地级市/区县三个字段各占一行，更清晰

- 旅行记录表单：自动地理编码（城市名→经纬度）

### 📝 文档

- 创建 `travel/README.md`：旅行模块完整文档（模型/服务/API/前端）

- 更新 `toolkit/README.md`：补全 CityCoordinate、TravelRoutePreset、内置工具表

### 🐛 修复

- **现金流热力图周明细弹窗净结余为0**：三处修复

  - `BillsByWeekView` SQL 列名 `note` → `notes`（列名不匹配导致 MySQL 报错 → 前端 catch 显示空列表）

  - `BillsByWeekView` 日期上限 `week_end_date` → `week_end_date + timedelta(days=1)`（独占上限排除当天所有账单）

  - `update_lived_status()` 改用 `week_start_date__lte=today`，标记已开始的周为"已度过"，使聚合包含当前周

- **现金流热力图周格子颜色空白**：`WeekCalendarView` + `WeeklySummaryView` 自动调用 `update_lived_status()`，无需手动初始化

- **目标管理编辑行为报错**：前端 `updateAction` 改用 PATCH（PUT 需全字段提交导致校验失败）

- **旅行路线预设保存后列表不显示**：前端处理 DRF 分页响应格式（`res.data?.results || res.data`）

- **WeeklySummary 接口 404**：URL 参数名 `week_index` → `global_week_index`，与 `lookup_field` 匹配

### 🗂️ 数据

- 批量导入福建/浙江/江苏三省区县级坐标数据

---

## [2026-05-16] v3.2.0 - 仪表盘重构 + 通知体系

### ✨ 新增

- 收件箱：批量转为目标功能（多选事项 → 创建目标 + 里程碑）

- 收件箱：状态筛选标签（待处理 / 已完成 / 全部），默认显示待处理

- 仪表盘：顶部可编辑系统宣言，保存至 localStorage

- 仪表盘：随机回顾卡片，随机展示日记/小确幸/读后感历史记录

- 里程碑：完成时弹出 🎉 庆祝动画浮层

- 通知服务：新建 `Notification` 模型 + `notification_service.py`（关系/目标/资产三模块检查），注册 `apps.core` app

### 🔧 优化

- 仪表盘：每个卡片独立加载骨架屏，互不阻塞

- 仪表盘：进行中目标、本周日记显示真实数据

- 时间统计：删除时段分布图表，人生平衡轮与月度趋势并排显示

- 时间统计：删除 TOP10 任务排行图表

- 收件箱：已完成事项也可正常删除（修复 get_queryset 默认过滤导致 404）

### 🗑️ 删除

- 收件箱：移除"转为互动"功能及相关代码（types、ConvertModal、后端 service/model/serializer）

### 📝 文档

- 根 `README.md`：收件箱描述移除"互动"

- `inbox/README.md`：移除"转为互动"引用，补全 `today_pending`、`convert_to_goal` 端点

- `temporal/README.md`：修正模型名 `OneDayRecord` → `OneDayPage`，补全 API 端点表

- `goals/README.md`：修正端点路径与实际代码匹配，补全缺失端点

---

## [2026-05-16] v3.1.1 - 文档整理与分页修复

### 📝 文档

- 补充 `frontend/README.md`：技术栈、目录结构、开发命令、模块规范

- 修正 `CLAUDE.md` 中过时的前端模块 README 引用

- 创建 `CHANGELOG.md` 系统更新日志

### ✨ 新增

- 书籍模块：新增 `action_item`（行动项）字段，读完书强制输出一个行动

- 关系模块：新增 `my_action`（我为对方做了什么）字段，记录关系中的付出

### 🔧 优化

- 小确幸页面：删除"我的模板"模块，保留自定义记录表单和历史列表

### 🗂️ 归档

- 舞蹈模块：侧边栏标记为"归档"，页面顶部添加归档提示条，保留数据和页面，可随时恢复

### 🐛 修复

- 修复关系档案列表分页不生效：服务端 `RelationshipPagination` + 前端 store 分页状态 + 筛选参数联动

- 修复小确幸页面统计卡片中"累计获得"在分页后显示错误（此前已修复）

---

## [2026-05-16 00:00:00] v3.1.0 - 庄子墨子优化 + 模块整合

### ✨ 新增

- 书籍模块：新增 `action_item`（行动项）字段，读完书强制输出一个行动

- 关系模块：新增 `my_action`（我为对方做了什么）字段，记录关系中的付出

### 🔧 优化

- 时间感知：活动追踪与时间统计合并为一个页面

- 财富管理：去除月度日历中重复的视图切换按钮

- 财富管理：新增随手记 CSV 导入功能

- 关系管理：合并"读者群体"到关系管理页面（TAB 切换）

- 健康管理：去除每日步数趋势和运动类型占比，精简为里程碑地图+年度步数对比

- 侧边栏：去除"分析统计"分组，精简为"总览"

- 侧边栏：去除"今日进度"静态假数据模块

- 侧边栏：精神滋养去除"精神花园"聚合入口，书籍阅读和小确幸平级显示

- 侧边栏：快乐银行与礼物清单平级显示

- 侧边栏：去除静态数字徽章（如书籍管理的红色5）

- 侧边栏：新增"读者群体""工具箱""美食地图"入口

### 🗂️ 归档

- 舞蹈模块：侧边栏标记为"归档"，保留数据和页面，可随时恢复

### 🐛 修复

- 修复现金流热力图颜色未根据账单数据映射

- 修复健康模块 BMI 指示器位置偏移

- 修复日记流日历热图格子大小和月份对齐

- 修复月度日历农历显示异常（十十六、初初八）

- 修复现金盘点编辑回填失败

- 修复定期存款统计包含已取出记录

- 修复目标进度计算错误（里程碑完成率与实际不符）

- 修复里程碑完成后奖励未发放到奖励池

- 修复小确幸页面预设模板清空

- 修复关系管理详情页互动记录串号

- 修复美食模块图片上传和卡片展示

- 修复工具箱页面繁简转换和图片转GIF未显示

- 修复侧边栏菜单点击后需刷新才显示内容

---

## 版本说明

- 主版本号：重大架构变更

- 次版本号：新功能模块、页面整合

- 修订号：Bug 修复、样式调整

## 历史迭代

### v3.0.0 (2026-04) - 新架构重构

- 从 sycamore_django 重构为新架构 sycamore

- 按生命维度组织模块：时间感知、身心健康、精神滋养、财富管理、连接与足迹、目标与项目

- 前后端分离：Django REST + Vue 3 Composition API

- 数据库从 SQLite 迁移至 MySQL

- 新增综合进度看板（summary）模块

- 新增工具箱模块

- 新增奖励池与目标管理联动

- 新增读者群体（关系管理子模块）

- 新增美食地图模块

- 新增现金流热力图和月度日历

### v2.0.0 (2024) - 旧系统

- 基于 Django + Bootstrap + ECharts 的初始版本

- 包含：oneday、times、health、wealth、goals、book、dance、sugar、travel、relation、dams、summary 等模块
