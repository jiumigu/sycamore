## [2026-09-20] v3.58.19 — 财富模块口径纠偏：净资产正名、负债率分母补应收借出、应急金改月数

### ♻️ 重构

- 资产汇总口径显式化：`total` / `financial_assets` = 活期 + 公积金，`total_assets` 补回应收借出，`net_worth` = 总资产 − 负债（`realnum` 保留为同值兼容别名，`total` / `realnum` 数值不变）
- 三个占比指标（活期 / 负债率 / 公积金）统一以总资产为分母 —— 负债率分母此前漏计应收借出，导致其被系统性高估
- 应急金分子由「支付宝 + 微信 + 现金」扩为全部活期类账户（含银行卡），科目清单收进常量作为单一真源
- `_build_overview` / 资产趋势 / 盘点列表三处各自重复的 7 项求和收进同一个函数

### ✨ 新增

- `GET /api/wealth/cashflow/overview/` 增返 `summary.net_worth` / `summary.total_assets` 与 `health_metrics.debt_ratio_legacy`（旧口径对照，不用于展示）
- 应急金派生指标：月数 / 目标月数 / 目标金额 / 缺口；月均支出不可得时三者返回 `null`
- 资产趋势与盘点历史列表增返 `net_worth`；资产趋势图改绘「净资产 / 金融资产 / 流动资金 / 公积金」四条线，历史表补净资产列

### 🔧 优化

- 应急金改以「月数」判定，目标月数由后端下发，前端不再写死绝对金额阈值
- 月均支出对「有记录的月份数」取均值而非固定回看月数，避免无记录月份被当成零支出把月数算虚高；优先账单明细聚合，明细无数据回落月度复盘表
- 资产盘点页及关联 tab / 路由文案由「现金盘点」改为「资产盘点」，并标注资产负债表口径
- 修正健康指标进度条取色：负债率此前与其他项共用「越高越绿」逻辑，50% 以上仍显绿

### 📝 文档

- `wealth/README.md` 新增「资产口径」节，固化净资产四层定义与三条强制约定；注明 `/cashflow/*` 承载的是资产负债表快照、非现金流量表

### 🧪 测试

- 新增 13 条用例（净资产恒等式 / 净资产可为负 / 负债率分母与旧口径对照 / 三个占比同分母 / 应急金月数与缺口 / 无支出数据返回 `null` / 序列化器字段对齐 / 月均支出取数），`pytest apps` 363 passed
- `npm run type-check`（vue-tsc 全量类型检查）0 错误

## [2026-09-20] v3.58.18 — 金额脱敏补齐覆盖范围：收掉 20 余处绕过统一实现的裸渲染

### ♻️ 重构

- 明确脱敏覆盖判据并全局对齐：**输入/预览态不掩、展示态才掩** —— 已落库数据的呈现（列表行、聚合汇总行、图表与地图 tooltip、已保存记录详情、删除确认文案）一律脱敏；正在输入或由输入实时派生的值（表单联动预览、数字输入框、计算器结果与建议文案、瞬时提示）保持可读
- `RedemptionDashboard` 与 `TravelPlanView` 的本地金额格式化改用共享实现，消除最后两处 `toLocaleString` 口径分叉

### ✨ 新增

- 三个此前未覆盖的模块接入脱敏：`food`（餐厅价格）、`temporal`（赎回池余额）、`redemption`（池本金 / 中途注入 / 当前余额 / 日均净消耗 / 档位合计 / 单位成本）
- 补齐同类漏网：冲突追踪（累计与逐行损失）、账单汇总行、时薪 / 固定开销 / 自由花费三个工具页的计算历史表格及其详情抽屉、旅行临时日志与概览卡、旅行计划预算与明细、中国地图 tooltip 花费、财富贡献图明细摘要

### 🐛 修复

- 账单页「明细列已脱敏、汇总行未脱敏」的同页不一致（支出小结与赎回归属小结共 4 处）
- 旅行看板同一页三种口径：记录卡把含货币符号的返回值再拼一次（渲染成 `¥¥`），临时日志与概览卡则完全未脱敏
- 餐厅价格为字符串形态时补数值转换，避免格式化入参类型不符

### 📝 文档

- 记录一处已知未覆盖：4 处图表 `valueFormatter` 与应急备用金指标需在隐私开关切换后重算图表配置，暂列技术待办

### 🧪 测试

- `npm run type-check`（vue-tsc 全量类型检查）0 错误

## [2026-09-20] v3.58.17 — 金额展示统一口径：半角 ¥、「符号在货币符号之后」

### ♻️ 重构

- `formatSignedAmount` 成为金额带符号的唯一实现：`(value, precision = 2, showPlus = false)`，输出 `¥1,234.50` / `¥+1,234.50` / `¥-1,234.50`
- 5 处内联符号拼接（月度结余、流水金额、时薪页日结余 ×2、账单金额）改调该函数，消除「正数 `+¥500`、负数 `¥-500`」的顺序混排

### 💄 展示

- 货币符号统一为半角 `¥`（U+00A5）：清掉财富模块 9 个文件共 24 处全角 `￥`（U+FFE5）
- 修正现金流热力图 tooltip 标题把货币符号误当年龄前缀的笔误（`¥18岁` → `18岁`），收入/支出两项符号顺序对齐为 `¥+` / `¥-`

### 📝 文档

- 目标进度百分比确认为**刻意不脱敏**，并升级为不变量（掩掉后进度环与进度条失去意义，且百分比非隐私项）

### 🧪 测试

- `npm run type-check`（vue-tsc 全量类型检查）0 错误

## [2026-09-20] v3.58.16 — 隐私脱敏收敛为单一实现，补齐四个模块的覆盖

### ♻️ 重构

- 三份平行脱敏实现收敛为单一规则源 `shared/utils/privacy.ts`，`usePrivacyMask` 退化为注入 `privacyStore.privacyMode` 的薄转发层
- 口径统一为「保留首字符 + 固定星号」（星号数固定，不泄漏原始长度）：`吴琦→吴**`、`福州鼓楼区→福***`、`大学社团活动→大***`
- 收回 10 处本地 `formatMoney` 副本与 16 处内联硬编码掩码，新增 `maskRate` / `maskFreeText` / `maskAmountCompact` 收编利率、备注、日历格
- 「收入脱敏、支出不脱敏」（`maskAmountByType`）为刻意设计，本次保持不动，已标记为不变量

### 🐛 修复

- `formatAmount` 用 `Math.abs()` 丢符号（负净值、负债被显示成正数）；金额掩码保留首尾字符（`1,234.50 → 1******0`，末位恒为精度位、首位泄漏数量级），改为整串掩码
- `usePrivacyMask().unmasked()` 两分支返回同一值（永真空操作）且无调用点，删除；`ConflictTrackerView` 把开关写死为 `maskName(x, true)`，外层三元一旦被移除即变成永久脱敏
- 空值口径分叉（`formatAmount(null)→'0.00'` vs `maskAmount(null)→'¥0'`）统一；`privacy.ts` 头注释所述状态源（localStorage）实为后端 `core_user_profile.privacy_mode`，已改正

### ✨ 新增

- 四个此前完全不脱敏的模块接入：`reward`（余额/累计/礼物参考价/流水）、`sugar`（奖励金额/余额）、`goals`（里程碑奖励金额）、`treasure`（名称/场景/理由/后果/标签/在哪能找到）
- 删除确认弹窗内的金额一并脱敏（`RewardTimeline` / `SugarView` / `TreasureHub`）

### 🧪 测试

- `npm run build`（vue-tsc 全量类型检查 + vite 打包）0 错误

## [2026-09-18] v3.58.15 — 归因规则页读不出数据、台账撤销覆盖假成功

### 🐛 修复

- 列表接口被全局分页包成 `{count,results}`、前端按裸数组取用 → 恒显空白；改 `pagination_class = None`
- 台账撤销覆盖对 L2 / 任务类型规则报假成功：改按规则来源判定，命中非任务名维度即拦截
- `resolve_attribution_detail` 增返 `rule_id`/`rule_field`/`rule_value`，前端据此事先判断能否撤销
- 批量撤销「撤销 N 条」提示因取数层级写错（`res.cleared`→`res.data.cleared`）从未显示，一并修

### 🧪 测试

- 新增 11 条用例覆盖接口形状 / `rule_*` 字段 / `blocked` 分支，`pytest apps` 350 passed

## [2026-09-18] v3.58.14 — 时间贡献图新增「单一任务」口径，替换空白的睡眠格

### ✨ 新增

- 后端 `contrib` 日聚合桶 `sleep` → `work`：判定由 `activity_type == '睡眠'` 改为**按任务名精确匹配**某一高占比任务（不用 L1/L2 桶口径，避免把同类任务一并算入）
- 前端 `TemporalContribView.vue` 的 `METRICS` 同步为 `{work, 该任务小时}`（位置不变）；`apps/temporal/README.md` 接口表更新

### 🔧 优化

- 旧 `?metric=sleep` 链接回落为 `hours` 口径（`metric_key.get` 兜底），不报错、无串味风险

### 🧪 测试

- 新增 4 条用例（精确匹配 / 0 值语义 / 旧 sleep 回落 / 响应结构），`pytest apps` 339 passed

## [2026-09-18] v3.58.13 — 现金流推演新增反算：给本金与期限算每日可花

### ✨ 新增

- `coverage_calculator.py` 新增 `calculate_daily_budget(cash, days, rate)`；`CalculateBudgetView`（`POST /api/wealth/calculate_budget/`）纯试算、不落库
- 前端 `ControlPanel.vue` 标题栏分段控件切换正/反算；`wealthTypes.ts`/`wealthApi.ts` 新增 `BudgetInput`/`BudgetResult`/`calculateBudget`

### 🔧 优化

- 反算与正算互为反函数；数值稳定形式（`expm1`）避免大 n 上溢，并收敛永续上限提示；抽出 `DAYS_PER_MONTH`/`DAYS_PER_YEAR` 常量共用

### 🧪 测试

- 新增 14 条用例（7 纯函数 + 7 端点，含零写库护栏），`pytest apps` 335 passed

## [2026-09-18] v3.58.12 — 归因口径收敛为单一真源、清理死选项；现金流卡片按需展开

### 🐛 修复

- 同一条 `activity_type` 规则在时间统计页生效、赎回期页被静默跳过（`getattr` 取不到值 → `continue` 不报错），根因是两处消费方各写一份判定
- 新增公共函数 `match_attribution_rule` 供两处共用，只认 `task_name`/`activity_type`/`task_type` 三项；`resolve_attribution_detail` 改调它，`MATCH_FIELD_CHOICES` 清理为三项（移除永不匹配的 `category_level2`）

### 💄 展示

- 人生现金流页顶部四张概览卡片默认折叠，点「财务概览」按钮才展开，首屏直接落热力图；`WealthView.vue` 用 `el-collapse-transition`，刻意不持久化

### 🧪 测试

- 新增 2 条用例（`activity_type` 两侧同命中、规则不外溢），`pytest apps` 321 passed

## [2026-09-18] v3.58.11 — L1 归因新增第五格「关系」，纯增量不改历史行为

### ✨ 新增

- L1 归因新增第五格「关系」：`temporal/constants.py` 的 `ATTRIBUTION_CHOICES`/`ORDER`/`COLORS`/`COUNTED` 与 `ACTIVITY_TYPE_PRESETS`（社交改挂关系）同步；`RedemptionWeekSnapshot` 增 `relation_hours` 字段

### 🔧 优化

- `ATTRIBUTION_ORDER` 保持原四词相对次序、新词插「成长」之后，避免 `dominant_attr` 并列取谁静默改变（已用回归断言钉死）；`temporal/services.py` 删除仅是 `by_l1` 副本的 `redemption_4color` 字段

### 📦 迁移

- `0010_map_social_to_relation.py`：按 L2 反查 `default_attribution='谋生'` 的「社交」行改挂「关系」（落库值，不影响其余行）

### 🧪 测试

- 新增 2 条「关系」回归断言，`pytest apps` 319 passed

## [2026-09-18] v3.58.10 — L1 归因四词改名，账单侧「外部」改为「为别人」

### ♻️ 重构

- 同组值原 3 处定义收敛为 `temporal/constants.py` 唯一真源，删除 `redemption` 副本；坑：同名 choices 元组/字符串列表形态不同，新增 `ATTRIBUTION_CHOICES_LIST` 区分

### 🔧 优化

- 时间侧 L1 改名：`ATTRIBUTION_ORDER` 投向→成长、外部→谋生（维持/流失不变），值序原样保持避免 `dominant_attr` 并列取谁静默改变
- 账单侧 `wealth_bill_list.period_tag`「外部」→「为别人」，两套词不强行统一

### 📦 迁移

- `temporal/0007`/`0008`、`redemption/0003`/`0004` 存量值幂等改名；英文列名与 API 字段保持不变

### 🧪 测试

- `pytest apps` 317 passed

## [2026-09-18] v3.58.9 — 导入补全规则 A 升级为两端补满，豁免提前下班日

### 🔧 优化

- 规则 A 从「只回补开始」升级为「补满标准工时窗口」：单段碎片记录区间取 `[min(原开始,标准上班), max(原结束,标准下班)]`，两端都缺都补、已达标不动
- 新增豁免：备注明确写「提前下班」的日子不补（`is_early_leave`）；非工作日族仍按实况、不往标准窗口拉
- 幂等键从「附注标记」换「达标判定」，避免 v3.58.8 只补开始的日子二次跑永远补不上结束且不报错
- `import_worklog.py` 的 `_extend_for` 返回值改为 `(新开始,新结束)` 并内建达标判定与豁免；补全说明「追加」而非替换旧行；仍不改 `import_batch` 以保回滚

### 🧪 测试

- `test_worklog_import.py` 82→94 条（新增 `TestEarlyLeaveDetection` 等），`pytest apps` 317 passed，无迁移

## [2026-09-18] v3.58.8 — 导入加两条补全规则：单段回补开始、非工作日兜底

### ✨ 新增

- 规则 A：当天某任务仅一段且为工作日类，开始回补标准上班、结束不动（仅工作日/仅单段）；规则 B：非工作日族无时段按标准工时登记，不再进待确认，普通无时段仍走人工确认

### 🔧 优化

- `worklog_parser.py` 新增 `is_restday()`（含调休，是 `is_offday` 超集）；规则 B 落 `plan_day()` 须显式清 `review=True`，否则静默仍报待确认
- 补全判定须排在「已导过跳过」之前并用独立标记；不改 `import_batch`；`_extend_one` 写入前 `make_aware`、附注重读后追加；`--fill-gaps` 收窄跳过规则 A 日

### 🧪 测试

- 新增 28 条 pytest，`pytest apps` 305 passed

## [2026-09-18] v3.58.7 — 新增工作日志 Excel 导入命令，零依赖解析 xlsx

### ✨ 新增

- 新增管理命令 `manage.py import_worklog <xlsx>`（默认干跑、`--apply` 落库）与纯函数模块 `worklog_parser.py`：xlsx 读取、工时窗口、状态分类、时长逐代解析、一天→一条规划

### 🔧 优化

- 零第三方依赖：标准库 `zipfile` + `xml` 直解 xlsx；解析一律按列位置而非表头名（应对表头损坏、sheet 跨年、数据区中段第二套表头、备注列三种位置）；跨零点仅在差值 > 12h 时认定
- 写入复用 `build_time_fields` 派日历字段、每条带 `import_batch='worklog'`；`temporal_time_atracker_tasks_list` 为 `managed=False` 外部表绝不加列，无迁移

### 🧪 测试

- 新增 54 条 pytest（含最小 xlsx 生成器），`pytest apps` 277 passed

## [2026-09-18] v3.58.6 — 任务清单支持手工新增，起止可改、时长自动计算

### ✨ 新增

- 任务清单新增「＋手工新增」按钮，不经 CSV 直接补一条时间记录；弹窗补齐结束时间，时长由「结束−开始」自动算（只读展示），起止不合法红字提示

### 🔧 优化

- 后端 `TemporalTaskSerializer.validate` 新增：起止都给→算时长+派日历，只给开始→只派日历，否则 400（`read_only` 日历列不补会静默漏掉该记录）
- 抽出公共 `build_time_fields(start_dt, end_dt=None)`：CSV 导入不传 `end_dt`、手工录入传 `end_dt`；`perform_create/update` 新 `task_name` 自动进 `TaskMeta`；前端 `TaskListView.vue` 用 `isoToInput()` 转本地时刻串、computed 即时算时长、透传 `end_time` 报错

### 🧪 测试

- 新增 9 条 pytest（`TestManualTaskEntry`/`TestBuildTimeFields`），`pytest apps` 223 passed，无迁移

## [2026-09-18] v3.58.5 — 时间明细改为按原始记录逐条展开，去重键换任务名+开始时刻

### ♻️ 重构

- 旧口径一行=某任务一天汇总，新口径一条 CSV 记录→一行 DB；去重键由 `(任务名, 日期)` 改 `(任务名, start_time)`
- `import_from_csv` 重写：去按天合并、CSV 内重复行按 key 去重计数；`end_time` 取本行、半开区间查找避 `CONVERT_TZ` NULL 坑；`migrate_atracker` 同步逐条

### 💄 展示

- 导入弹窗文案改「逐条导入不按天合并」并提示去重；分类映射编辑器页头加固定返回的「返回」按钮

### 🧪 测试

- 新增 6 条 pytest（`TestCsvImportPerRecord`），`pytest apps` 214 passed，无迁移

## [2026-09-17] v3.58.4 — 任务清单新增结束时间列并显性标注累计≠跨度

### ✨ 新增

- 任务清单「开始时间」后新增「结束时间」列（`end_time` 取自 `TemporalTaskSerializer`，同日 `HH:mm`、跨零点补日期、缺失 `—`）
- 贡献图当日明细弹窗补「结束时间」；后端 `daily_detail` 增返 `end_time`（键恒在、缺失为 `None`，纯新增无迁移）

### 🔧 优化

- 一行=一个 task_name 的一天汇总，`duration_hours` 为累计，「结束−开始」可能小于时长；不一致行时长琥珀色+`*`标注并附明细（容差 2 分钟）
- 编辑弹窗只写开始+时长，`end_time` 保留原始记录值；导入更新分支只写部分字段、不刷新 `start_time`

### 🧪 测试

- 新增 2 条 pytest（`TestDailyDetailEndTime`）；`pytest apps/temporal` 41 passed、`pytest apps` 208 passed；`vue-tsc`/`vite build` 通过

## [2026-09-17] v3.58.3 — 映射编辑器改造为全量任务台账与归因复核台

### ✨ 新增

- `/temporal/mapping` 改为全量 task_name 台账（任务名/L1/L2/累计时长/次数/均时/最近使用/归因来源），概览条 + L1 chip 点选即筛；行内就地改 L1/L2 落库
- 「归因来源」列显性化：标注生效归因来自 赎回期规则/类型默认/兜底；规则来源行可「撤销覆盖」软停用（`is_active=False`）

### 🔧 优化

- 后端新增 `GET /api/temporal/tasks/meta_ledger/`（`meta_ledger`：summary+items，支持 4 筛选参数）；`resolve_attribution` 重构为 `resolve_attribution_detail`
- 聚合查询显式 `.order_by()` 清空 `TemporalTask.Meta.ordering`（否则按 `start_time` 拆行虚高）；`batch_set_meta` 加 `keep_default`/`clear_rule`

### 🧪 测试

- 新增 10 条 pytest；`pytest apps/temporal` 39 passed、`pytest apps` 206 passed；`vue-tsc` 0 错误

## [2026-09-17] v3.58.2 — 时间贡献图新增「主导归因」着色视图

### ✨ 新增

- 贡献图新增「主导归因」默认视图：每天取四 L1 归因时长最多者，按固定语义色着色；并列按价值序、当天无已归因画灰格
- 悬浮提示带归因明细（只列非零）；量值视图（记录数/小时/投向/深度工作/睡眠）全部保留可切换

### 🔧 优化

- 后端 `contrib` 新增 `metric=dominant_attr`（`mode:"attribution"`，`data` 带 `attr`/`breakdown`），归因取值先四舍五入 2 位再比较
- `ContributionGraph.vue` 加 `mode`/`palette` props（他模块零改动）；修复切换 metric 的 `localStorage` 缓存串味（按 metric 分键）

### 🧪 测试

- 新增 5 条 pytest（`TestContribDominantAttr`）；`pytest apps` 196 passed；`vue-tsc` 0 错误

## [2026-09-17] v3.58.1 — 现金流热力图显示窗口收窄为 19–60 岁

### 💄 展示

- 人生现金流热力图显示窗口由 18–78 岁收窄为 19–60 岁（42 年×52 周）；卡片标题与「19–60 岁」范围标签同步更新
- 只改渲染窗口，数据与索引不动（`global_week_index` 原点锚定 18 岁）；`HeatmapGrid.vue` 拆 `BASE_AGE` 与 `DISPLAY_*` 常量

### 🔧 优化

- 「计量窗口」落地（`apps/wealth/constants.py`：数据层 `START_AGE 18/END_AGE 78` 与窗口 `WINDOW 19/60` 分离，注释「原点勿动、窗口不删数据」）
- 「已度过」按窗口重算；`calculate_coverage` 加 `max_age`（上限收 60 岁），赎回期 `sync_to_scenario` 收口；推演面板进度基数 3172→2184、覆盖末端显「至 60 岁·窗口内不耗尽」、年龄输入收窄 19–60

### 🧪 测试

- `pytest apps/wealth apps/redemption apps/summary apps/temporal` 74 passed；`vue-tsc` 0 错误

## [2026-09-17] v3.58.0 — 时间结构图重做为三层同心环并修复标签堆叠

### 🐛 修复

- 时间结构图标签堆叠：原 `sunburst` 小扇区文字压叠，改为三层同心 `pie`（L1/L2 环内、L3 圆外引线标注、垂直避让）
- 根因：`sunburst` 不支持 `labelLine`/不走 `labelLayout`；改用多 `pie` 同心叠放（`sort:false`）拿到引线；修复空年份趋势残留、灰色占位环、`resize` 泄漏，三图统一空态
- 补齐 3 处遗留迁移：`redemption/0002`、`summary/0004`（不落库）、`temporal/0006`（Django 6.0 索引改名，2 条 `RENAME INDEX`），`makemigrations --check` 无变更

### 💄 展示

- 指标卡「总时长」改双值「已记录/总时间」，记录完整度改两位小数；后端 `get_completeness` 增 `denominator_hours`；窄屏四卡自适应等高

### 🧪 测试

- `pytest apps/temporal` 24 passed；`vue-tsc`/`vite build` 通过，无 schema 变更

## [2026-09-15] v3.57.0 — 时间统计重构 v0.3：三层分类·记录完整度·168h 结构

### ♻️ 重构

- 确立 L1/L2/L3 自顶向下，取消「自建聚合分组 ActivityGroup」层（表与 `TaskMeta.group` 列保留不删，移除路由与 ViewSet）；`get_trend` 支持 l1/l2/l3
- 彻底移除 30h/周达标规则，保留 30h=1 点换算（仅统计归因∈{投向,维持,外部}）；CSV 导入停写旧 `category_level1`/`category_color`；修复 `DISTINCT`+`Meta.ordering` 去重失效（统一加 `.order_by()`）

### ✨ 新增

- 三层分类（L1 归因/L2 类型/L3 task_name=`temporal_task_meta`）：内置 9 项预设，未命中落「未归类」；L1 复用 `redemption_attr_rule`，优先级 rule>default>兜底；外部表 `temporal_time_atracker_tasks_list`（managed=False）绝不加列
- 映射编辑器 `/temporal/mapping`、任务清单页 `/temporal/tasks`、旭日图 `SunburstChart`、168h 结构图 `Weekly168Chart`、记录完整度替代达标率、贡献图多指标；新接口 `tasks/meta/`、`batch_set_meta/`、`sunburst/`、`completeness/`、`weekly-structure/`、`trend/?level=`

### 🧪 测试

- `pytest apps` 191 passed（含 temporal/summary/redemption 38）；覆盖归因优先级/完整度/趋势三档/旭日三环/DISTINCT 回归；`vue-tsc`/`vite build` 通过

## [2026-09-14] v3.56.0 — 三年赎回期：账单赎回归属标记·赎回仪表盘·暂停追踪

### ✨ 新增

- 「三年赎回期」功能：账单赎回归属标记 + 赎回仪表盘 + 暂停追踪 + 资金推演打通，作为可监督子系统
- 账单赎回归属标记（`WealthBillList.period_tag`：为自己/过渡/外部/不计入，窗口外按日期自动推算）：小结条/筛选/行内下拉/表单，新增 `batch_period_tag`（收支都生效）、`period_tag_stats`（含收入）

### 🔧 优化

- 赎回仪表盘 `/redemption`：窗口/现金池/四档分布/时间归因（覆盖率 <50% 提示「仅基于已记录部分」）/单位赎回成本；暂停追踪 `RedemptionPauseView`/`ResumeView`（暂停期不计指标、不暂停记录）
- 赎回期判定层（新建 `redemption` app，4 表：period/pool_inject/attr_rule/week_snapshot）；`attr_rule` 按 `task_type`/`task_name` 映射归因，绝不向 managed=False 表加列；打通 `WealthCurrentScenario` 推演（`sync_to_scenario` 复用 `calculate_coverage`，preview 只读/apply 写库）

### 🧪 测试

- 新增 `test_period_tag.py` 4 条、`test_redemption.py` 7 条；wealth/temporal/redemption 54 passed；`vue-tsc` 0 错误

## [2026-09-12] v3.55.0 — 旅行足迹地图：省界叠加·悬停标签·权威坐标落点

### ✨ 新增

- 旅行足迹地图三处改进：省界叠加（`getProvinceBorderRings()` 用 `china.js` 省级边界画最上层）、地市名改悬停显示（默认态 0 文字、移上才浮出）
- 气泡落点改由权威坐标表 `toolkit_city_coordinate` 驱动（`resolve_place()`：全称/去后缀精确匹配、带省份本省优先、县级市用自身点位），硬编码表仅兜底；按坐标表规范名归并同地点写法
- 热力项新增 `sources` 来源明细（tooltip 显示归属明细），县级市/区县并入所属地级市着色的归属透明

### 🧪 测试

- 新增 7 条 pytest（来源明细/县级市独立点位/简称归一/省份感知/硬编码兜底/气泡归并/不塌陷）；全量 159→166 passed；`vue-tsc` 0 错误

## [2026-09-11] v3.54.0 — 决策追踪器自定义倾向·旅行流水线打通·城市坐标类型化

### ✨ 新增

- 决策追踪器支持自定义倾向选项（迁移 0023）：`lean_options` JSON 数组（2–6 项）+ `tendency` 放宽 varchar(50)，报告按选项泛化、加权分口径分化
- 旅行足迹热力下沉到地级市 + 修复城市气泡从未渲染（`scatter` 未定义 `geo`）；旅行流水线打通（心愿打卡→行程日志→足迹）、路线推演迁入旅行模块
- 心愿单地图随筛选缩放聚焦、打卡升级「打卡记录」；行政区划订正（撤县设区，纯数据）+ 坐标表补全与 `name` 类型化、5A 景点入库
- 书名号《》展示统一、图书标签接入系统预设（迁移 core 0006）、财富贡献图配色对调（绿=收入/红=支出）；修复点菜单偶发整页空白

### 🧪 测试

- 多批新增 pytest（归属/档位/聚合/沉淀/路线/坐标/lean 校验等）；全量由 120 逐步增至 159 passed；`vue-tsc` 0 错误

## [2026-09-10] v3.53.0 — 决策追踪器强度加权预览·工具箱瘦身（移除死模块）

### ✨ 新增

- 倾向随时预览（`GET decision-trackers/preview/` 返回条数占比/强度加权/断记天数）与观察期内封存结论（防反向影响记录）
- 记录强度由枚举改数值（迁移 0020，`intensity` 改 1–5），`report` 加 `intensity_label`；现金流推演加月/年换算并接入真实数据（净消耗/自由缺口），纯前端
- 人生现金流页与收件箱两列栅格排版优化（功能零改动）；记录日期默认值差一天修复（`todayISO()` 改本地时区，抽出 `toLocalISO()`）

### 🗑️ 移除

- 资金排程整体移除（迁移 0014 删两表）；复盘工具箱/语言训练/环境校准移除（迁移 0021）；决策日志 `DecisionLog` 移除（迁移 0022），个人画像「决策质量」卡摘除；决策追踪器完整保留

### 🧪 测试

- 新增 2 条 pytest（加权分数/断记）；移除资金排程相关测试；全量 121→117 passed

## [2026-09-09] v3.52.0 — AI 问答库交互改进：快记流·md 渲染·采纳回顾

### ♻️ 重构

- 快记流：新建主题弹窗内嵌首轮 AI 回答区，填了即与主题一次提交归档，保存后自动打开详情抽屉可追问
- 分类职责收敛：场景升为唯一主分类，标题/背景/标签折叠进「更多选项」，零后端改动

### ✨ 新增

- 回答正文 markdown 阅读态渲染（`AskAnswerNode.vue` 用 `marked` 渲染列表/代码块/表格/标题，编辑态仍存 md 原文）
- 采纳回顾：「仅含采纳」筛选（`?has_accepted=1`）+「采纳汇总」导出（`GET ask-topics/summary/`，导出 `.md`）

### 🧪 测试

- 新增 2 条 pytest（`has_accepted` 过滤与场景叠加 / summary 聚合仅含采纳）；全量 119 passed

## [2026-09-09] v3.51.0 — AI 问答库：业务场景容器·多轮追问对话流

### ✨ 新增

- 业务场景容器：新增 `AskScene`（`toolkit_ask_scene`）+ `AskTopic.scene` 外键，列表/详情回显场景，删除场景主题转「未分类」
- 多轮追问对话流：`AskAnswer.parent` 自引用（追问挂被追问回答下，级联删），前端详情改对话流树 `AskAnswerNode.vue` 递归渲染，导出 .md 按对话流递归

### 🐛 修复

- 回答提问时间默认值差 8 小时（UTC 偏移）：新增 `nowLocal()`/`todayLocal()` 替换 4 处自动生成路径

### 🧪 测试

- 新增 3 条 pytest（场景 CRUD/过滤/SET_NULL、追问链与级联删除、检索命中追问）；全量 117 passed

## [2026-09-09] v3.50.0 — AI 问答库：结构化沉淀 AI 答案档案

### ✨ 新增

- AI 问答库：`AskTopic`/`AskAnswer` 两表（迁移 0018）+ `AskTopicViewSet`（6 字段检索、tag/ai/日期筛选、嵌套 answers）；同一 AI 不同会话用「会话背景」区分；标签预设接入系统预设（`ask_tags`，种子 8 个）
- 前端 `AskLibrary.vue`（`/toolkit/ask-library` + 侧边栏直达菜单）：表格+详情抽屉对照、verdict 行内 select、单条/批量导出 .md（含 YAML frontmatter）

### 🧪 测试

- 新增 5 条 pytest（检索跨字段/tag/ai/日期/导出）；全量 114 passed

## [2026-09-09] v3.49.0 — 月度日历合一账单清单·支出必要性标记

### ♻️ 重构

- 账单清单迁入月度日历（`BillListView.vue` 常驻月历页，随年月联动）；清理头部死控件（移除无人接线的「月视图/宏观热力图」切换，保留财富顶栏「宏观热力图」tab 与周历推演）
- `CalendarHeader` 移除视图切换控件后同步精简 `viewMode` prop 与 `switch-view` emit

### ✨ 新增

- 账单「必要性」标记（必要/可选/冲动，仅支出）：`wealth_bill_list` 加 `necessity` 列，`BillViewSet` 支持 `?necessity=`、新增 `POST batch-necessity`、`GET necessity_stats`；前端行内下拉+批量标记

### 🧪 测试

- 新增 4 条 pytest（necessity 过滤/批量/统计/收入兜底）；全量 109 passed

## [2026-09-09] v3.48.0 — 决策追踪器上线·relation 测试 flaky 修复

### ✨ 新增

- 决策追踪器（工具箱，长期观察型决策）：`DecisionTracker`/`DecisionRecord` 两表（迁移 0017）+ `DecisionTrackerViewSet`（CRUD/记录/report/decide/archive）+ `DecisionRecordViewSet`；前端 `DecisionTracker.vue` 4 TAB+提醒横幅+10 秒记录弹窗+报告/决定/归档全套
- 观察期内的追踪不提供理由查看入口（防倾向分布提前影响后续记录）

### 🐛 修复

- relation 月度统计测试 flaky 修复：`test_overview_monthly_count_uses_range` 改用上月中 15 号，与运行日期解耦

### 🧪 测试

- 新增 8 条 pytest（到期流转/报告聚合/decide-archive/误记删除）；全量 105 passed

## [2026-09-03] v3.47.0 — 阅读图形分析独立页

### ✨ 新增

- 阅读图形分析独立页（`/books/charts`，懒加载不进侧边栏）：年度阅读统计/书籍类型分布迁出主页，顶部 4 卡+年份选择器联动+点柱联动筛选该年类型分布；`stats` action 支持 `?year=`
- 主页面移除图表区（仅留统计卡片），echarts 引入/渲染/resize 脚本与样式清理

## [2026-08-31] v3.46.0 — 全系统时区修正·任务清单增强·多模块清理

### ♻️ 重构

- 日记流支持按日期查询（修复标题搜索 bug：`params.title`→`params.search`）；账单清单备注模糊搜索接线；各模块贡献百分比数值补全（`percent` 字段注入）

### ✨ 新增

- 全系统时区修复：历史 naive 本地时间被误按 UTC 解释；修正读取路径、已存 `start_time/end_time` 全表 +8h 恢复本地并重算周期、修正全局写入字段的时区偏移
- 任务清单增强（筛选栏 + 结束时间列）；4 个贡献图支持点击查看当日明细（新增 `daily_detail` action + 共享 `DailyDetailDialog.vue`）；仪表盘「本周步数/支出」接入真实数据（此前为死卡片）
- 七维平衡雷达图优化（封顶值可配置化 `SevenDimConfig` 并保留版本化历史；自定义几何 tooltip 修复）；时间追踪分类重排为 4 类（工作 / 学习 / 生活 / 兴趣记录）并同步历史数据

### 🗑️ 移除

- 移除「标签管理器」；汇总总览冗余卡片/仪表盘去重、时间统计冗余表格移除并增年度明细；日程完成改录入心得面板

## [2026-08-30] v3.45.0 — 贡献图·标签检索·计算器聚合·高频直达

### ✨ 新增

- 日程视图重构：弃用 el-calendar，自建 `CalendarMonthView`（CSS Grid 7 列、农历/节气/溢出展开）+ `CalendarListView`，点击日程弹详情抽屉并可一键完成
- 高频工具直达菜单（用电记录/摘录管理加入侧边栏）；财务计算器三合一（`FinanceCalculators.vue` tab 切换）；移除「图片转 GIF」
- 四大模块贡献图（Roam 风格年度热力图，`ContributionGraph.vue` + 4 后端 contrib 端点）；日记流标签列 + 标签检索（`flag__icontains`）；里程碑列表智能排序；待跟进提醒排除同事

### 🐛 修复

- 里程碑截止日期被编辑清空修复：`saveMilestoneDate` 未改动不提交，仅显式清空才传 null；新增 3 条回归 pytest

### 🧪 测试

- 用例扩充 46→85（新增 39 条），覆盖资金排程/账单/好朋友跟踪/健康统计 ORM 化等；暴露并修复 relation 按月分组受 CONVERT_TZ 影响 period 全 `0000-00` 的 bug

## [2026-08-27] v3.44.0 — 菜单管理系统·补测试·数据库清理

### ✨ 新增

- 时间追踪任务 + 账单清单 CRUD（`TemporalTaskViewSet` 改完整 ModelViewSet；`WealthBillList` 映射外部遗留表 + `BillViewSet` CRUD）
- 收件箱批量「转为里程碑」（`POST /api/inbox/items/convert-to-milestone/`）；菜单管理系统（`MenuPreference`/`MenuGroup` 迁移 0005 + `LayoutSidebar.vue` 重写 + `MenuManager.vue`）；补充测试（6 文件 46 用例）

### 🐛 修复

- 好朋友跟踪改最近 12 月口径（`MenstrualRecord` 加 `end_date`/`duration_days`）；侧边栏图标未注册；转里程碑异常防护与字段兜底；累计发奖修正；前端 43 类型错误修复
- 迁移 `CREATE TABLE IF NOT EXISTS`（全新空库可完整 migrate）；CONVERT_TZ 全家桶修复（账单/任务/关系时间筛选与统计）

### 🗑️ 移除

- 旧业务库彻底移除（仅剩唯一业务库+测试库）；备份表清理；迁移 squash 86→45；`projects` 空壳模块删除；侧边栏第一轮瘦身归档

## [2026-08-25] v3.43.0 — 备考优化·项目目标+收件箱导入+截止倒计时

### ✨ 新增

- 目标类型新增「项目目标」（`Goal.category` 加 `project`，迁移 0015），目标类型下拉新增选项
- 收件箱批量导入（`POST /api/inbox/items/import/`，CSV/Markdown/纯文本自动识别、中文列名归一、预览+模板下载）
- 目标卡片截止倒计时（`Goal` 新增计算字段 `days_remaining`，按剩余天数分级着色）

### 📝 文档

- 更新 `inbox/README.md`、`goals/README.md`（导入服务/API/组件、`days_remaining`、项目目标说明）

## [2026-08-23] v3.42.0 — 人生样本：Obsidian 打开与同步防重复修复

### 🐛 修复

- `get_obsidian_uri` 改用仓库绝对路径，修复相对路径无法解析
- 同步改四级匹配（路径/文件名/姓名/新建），杜绝重命名后重复创建
- 同步返回 `migrated` 列表，前端展示「迁移 N 个（路径变更）」
- 卡片 Obsidian 路径仅显示文件名，去除无区分度的固定前缀

### 🗑️ 移除

- 清理 vault 批量重命名产生的重复样本记录（均无人工批注）

## [2026-08-21] v3.41.0 — 人生样本：状态管理与借鉴意义评级

### ✨ 新增

- `LifeSample.status`（已收集/已核实/已审阅）由 `save()` 自动补齐时间戳
- `LifeSample.relevance`（高度借鉴/参考/了解）+ 评级理由，卡片以 💡 展示
- 状态/评级徽章组件；`/samples/stats/` 返回分布，列表与统计卡可筛选

### 🔧 优化

- 统计区精简为核心统计卡 + 评级摘要，点击卡片筛选/取消
- `useSampleStore` 删除无用 `statusCounts`/`relevanceCounts` getter

## [2026-08-20] v3.40.0 — 人生样本：Obsidian 双向同步

### ✨ 新增

- `POST /api/lifesample/samples/sync-from-obsidian/` 扫描按 `obsidian_path` 同步
- `parse_frontmatter` 扩展解析 name/alias/era/region/type/tags/summary
- 系统设置 Obsidian 卡：测试连接/配置预览/快速打开；`samples_folder` 默认改 `05_人生样本(LifeSamples)`（迁移 0002）

### 🐛 修复

- 修复路径重复拼接（`vault` 尾部同名直接返回）；「测试连接」先持久化当前值再扫描
- `sync_samples` 跳过 `待采集名单.md`，不再被索引为样本

## [2026-08-19] v3.39.0 — 新增「人生样本」模块（Obsidian 轻量索引）

### ✨ 新增

- 人生样本模块：轻量索引参照样本，深度内容存 Obsidian，Sycamore 仅索引
- `life_sample`/`obsidian_config` 两表 + CRUD + `tags`/`stats` + `/scan/` + `/open/<path>/`
- 前端 `/lifesample` 卡片墙/搜索/筛选 + `SampleForm.vue`；设置卡配置 Obsidian

## [2026-08-18] v3.38.0 — 旅行模块新增「旅行计划」功能

### ✨ 新增

- `travel_plan`/`travel_plan_item` 两表 + `/api/travel/plans/` CRUD + `items`/`stats`
- 明细四类（美食/景点/交通/住宿），`recalculate_total` 自动汇总预估费用
- 前端 `TravelPlanView.vue`（`/travel/plans`）+ 侧边栏「旅行计划」入口

## [2026-08-16] v3.37.0 — 工具箱新增「用电记录」工具

### ✨ 新增

- 工具箱新增「⚡ 用电记录」(`electricity-record`)：记录读数自动算间隔/日均
- `toolkit_electricity_record` 表 + CRUD（删后 `recalculate_all` 重算）；口径：间隔=本次−上次、日均=间隔÷天数、本月累计=月初基准
- 前端 `ElectricityRecord.vue`：统计卡 + ECharts 趋势图 + 历史表格

### 🐛 修复

- 删除 `FixedExpense.vue`/`ElectricityRecord.vue` 冗余「返回」按钮（双按钮）
- 移除 `ToolDetail.vue` 共享描述卡片（误导数据型工具），执行型入口迁移

## [2026-08-16] v3.36.0 — 资金排程重构为 FundSchedule 快照式

### ✨ 新增

- `wealth_fund_schedule` 表（JSON `reserve_items`）+ `/api/wealth/fund-schedule/` 快照 CRUD
- `FundScheduleBoard.vue` 替换 `AllocationBoard`；固定开销按 365 天口径折算导入
- 取代分配计划系统（五表 + `allocation_service.py` + `AllocationBoard.vue`）

### 🐛 修复

- 剩余金额 bug：旧代码对预留二次扣减，重构为单一派生链消除
- 负金额 500：服务层 `ValidationError` 转 `serializers.ValidationError`→400；迁移删列先删索引再删列

## [2026-08-16] v3.35.0 — 资金排程 + 分配计划（分配是计划，非记录）

### ✨ 新增

- 资金排程页 `AllocationBoard.vue`：现金/硬性承诺/预留分配/自由支配
- 五表 `AllocationCategory`/`AllocationPlan`/`AllocationItem`/`Commitment`/`DecisionLog`
- `AllocationService`（`create_plan` 幂等 upsert）+ `AllocationViewSet` 六端点
- 取代 v2.0 持续资金池；`init_allocation_categories` 幂等建 5 默认类

### 🐛 修复

- `@action` 方法名 `detail` 与 DRF `self.detail` 冲突，更名 `get_detail`
- `formatAmount` 导入路径由 `privacy` 改 `format`；承诺聚合改用 `wealth_bill_list` 原生 SQL

## [2026-08-11] v3.34.0 — 资金分配系统 v2.0（持续资金池模式）

### ✨ 新增

- 持续资金池：余额=全部 `FundTransaction` 流水 `Sum(amount)` 永不重置
- `FundTransaction` 替换月度预算表；`FundPool.linked_categories` 记账后自动扣减
- 资金操作 API（`inject`/`allocate`/`adjust`/`summary`/`balances`）+ `FundDashboard.vue`
- 健康度算法：蓄水池达标 40 + 无负余额 30 + 池子多样性 30

### 🗑️ 移除

- 注：本版持续资金池功能已于 v3.35.0 由「资金排程+分配计划」取代

## [2026-08-11] v3.33.0 — 自由职业资金分配系统 Phase 1

### ✨ 新增

- 资金池配置：`/wealth/fund` 自定义池（fixed/ratio/reservoir），`FundPool`+`FundPoolViewSet`
- 月度资金概览：健康度评分 + 总收入/已分配/初始注入 + 各池进度
- `allocate_funds` 事务写 `PoolAllocation`（覆盖式）；初始注入一次性总池资金
- 健康度算法（执行率25+缓冲30+偏差25+多样性20）；有分配记录禁止删除

### 🐛 修复

- `FundPoolViewSet` 分页包装致前端遍历 null 崩溃；设 `pagination_class=None` + store 兼容

## [2026-08-09] v3.32.0 — 固定开销详情弹窗优化 + 底部状态栏周数显示

### 🔧 优化

- 固定开销详情弹窗加宽、3 列对齐表格、汇总大数字、新增「复制并编辑」
- 修复 `append-to-body` 挂载导致详情弹窗样式失效的遗留问题
- 底部状态栏新增「第N周」徽标（ISO 周算法，随秒级时钟刷新）

## [2026-08-05] v3.31.0 — 打卡里程碑同步 + 收件箱废弃 + 固定开销周期 + 时薪附加

### ✨ 新增

- 目标打卡自动推进对应/下一里程碑，自动发奖；补打卡同触发不重复
- 收件箱新增 `abandoned` 状态 + `abandon_reason`，统计卡扩展、日历不展示
- 工具箱新增固定开销计算器（周期换算）与时薪附加收入联动；目标维度分布页 + 里程碑反思字段 + `sync_field_comments` 命令

### 🐛 修复

- `ToolRegistry.auto_discover()` 仅启动扫描，新工具需重载才注册（归入「财务」）
- `RewardSourceStatsSerializer` 补齐 `goal_complete`/`inbox_complete` 字段
- `recalculate()` 自动完成（进度 100% 转完成）+ 保护已完成里程碑不被重置

## [2026-08-02] v3.30.0 — 工具箱新增 GIF 压缩工具

### ✨ 新增

- GIF 压缩工具：抽帧/缩放/颜色数/质量四手段；`GifCompressor.vue` 预览下载
- 文件上传接口泛化：`FileToolUploadView` 按 `tool_key` 白名单校验扩展名并透传参数

## [2026-07-30] v3.29.0 — 里程碑编辑增强 + 奖励统计修复 + 表单优化

### ✨ 新增

- 里程碑编辑详情弹窗：编辑描述与奖励金额
- 人生维度必填（`life_dimension` 取消 blank，迁移 0014）；奖励池来源筛选新增 `goal_complete`

### 🔧 优化

- 全局 CSS 统一显示必填红色星标，替代默认黑色

### 🐛 修复

- `RewardSourceStatsSerializer` 补齐 `goal_complete`/`inbox_complete` 字段声明
- `GoalCreateUpdateSerializer.update()` 保护已完成里程碑 + 变更后强制 `recalculate()`
- `recalculate()` 新增 `_auto_transition_status()`（100% 自动完成）与奖励检查

## [2026-07-27] v3.28.0 — 侧边栏导航升级 + 职业能量审计优化 + 页面整合

### ✨ 新增

- 侧边栏按模块半透明分组、高度压缩、折叠 60px、独立滚动
- 职业能量审计实时分数预览（滑块动态变色）+ 仪表盘金句完整展示

### 🔧 优化

- 周度追踪合并到时间统计页；季度决策卡片迁移到汇总总览
- `ToolDetail` 信息卡条件隐藏（职业能量审计页不显示共享卡）

## [2026-07-22] v3.27.0 — 收件箱完成修复 + 仪表盘段落金句

### ✨ 新增

- 仪表盘段落金句完整显示：`-webkit-line-clamp: 4`，超 200 字可展开全文

### 🔧 优化

- 汇总总览隐藏无数据模块（`身体-状态关联（近12周）`），明细表上移

### 🐛 修复

- `createSugar` 补全 `title`/`time` 且分制映射（×4），`time` 增 `input_formats`
- 收件箱完成奖励 `perform_create` 优先用前端 `reward_amount`（移出 read_only）
- `transaction_type` 改 `inbox_complete`，模型 `TRANSACTION_TYPES` 增选项（迁存量）

## [2026-07-21] v3.26.0 — Logseq 日记集成 + 覆盖进度基线修复

### ✨ 新增

- Logseq 日记集成：`UserProfile.logseq_path` + `logseq_file` 字段 + `OpenLogseqView`
- 前端 `LogseqViewer.vue` 用 `marked` 渲染 Markdown；设置页支持路径与隐私开关

### 🔧 优化

- 覆盖进度基线改为从已度过周数起算，三段式显示；日利息显示条件修正

### 🐛 修复

- 永不耗尽时后端返 `null`，前端 `coveragePercent` 判 `null` 显示 100%

## [2026-07-19] v3.25.0 — 仪表盘快速读者互动 + 日记热力图修复

### ✨ 新增

- 仪表盘快速记录读者互动卡片：粘贴留言+Ctrl+Enter，可选类型/能量值，偏好存 localStorage

### 🐛 修复

- `generate_default_log()` 改用日期级检查，避免有 MIGU 等类型日记的日期重复生成
- 热力图 `getDayColor` 区分「无记录」与「有日记但当日0字」，默认日记可见
- `getTypeTagType` 将 SUMMARY/ONEDAY 映射 `'info'`，消除 el-tag 警告

## [2026-07-13] v3.24.0 — 里程碑折叠 + 复盘工具箱修复 + 现金流推演利息复利

### ✨ 新增

- 现金流推演 `calculate_coverage` 新增 `daily_interest_rate` 日复利；模型新增该字段
- `.env.example` 环境变量模板（含 `SECRET_KEY`/`DB_PASSWORD`）
- 里程碑列表连续同名折叠（`normalizeName` 归一化，支持展开/收起）

### 🔧 优化

- 复盘工具箱表单回填去除冗余 `|| {}`，避免空对象覆盖默认值

## [2026-07-06] v3.23.0 — 语言训练器 + 旅行路线全屏重构

### ✨ 新增

- 语言训练器工具：4 种训练类型（词汇颗粒度 / 场景描述 / 语言素材 / 逼近修订）+ CRUD 历史，`LanguageTraining` 模型与 `LanguageTrainingViewSet`

### 🔧 优化

- 旅行路线推演全屏重构：左侧可折叠窄条 + 抽屉覆盖层滑入滑出，地图占满全屏，控制栏悬浮底部

### 🐛 修复

- 语言训练器保存后列表空白：`LanguageTrainingViewSet` 设 `pagination_class = None` 返纯数组，前端兼容数组与分页对象两种响应

## [2026-07-04] v3.22.0 — 父子目标嵌套 + 小确幸编辑加固

### ✨ 新增

- 父子目标关联：`Goal.parent_goal` 自关联，递归汇总子目标进度，新增 `sub_goals` 端点与嵌套序列化

### 🐛 修复

- 小确幸编辑移入 `transaction.atomic()`、`time` 自动同步 `years`/`month`、标签合并后顺序去重
- 父子目标循环引用防护（向上遍历 + 拒绝已有子目标设为父）；修复取消完成未扣回奖励、标签合并重复、单模块异常致整体 500

## [2026-07-03] v3.21.0 — 小确幸快乐类型重构 + 编辑修复

### ✨ 新增

- 小确幸快乐类型七类→五类（迁移 `0006`，旧数据保留）+ 编辑发生日期；目标编辑里程碑增量同步、奖励金额直等于快乐值
- 全局搜索跨模块（Quote/OneDayPage/SugarRecord 等）+ 独立标签管理器 `/admin/tag-manager`

### 🐛 修复

- 目标编辑新增里程碑未保存（`milestones` 被丢弃已重写）；小确幸编辑日期被覆盖为今天、新增奖励金额不一致

## [2026-07-02] v3.20.0 — 目标看板重构 + 仪表盘金句

### ✨ 新增

- 目标看板统计卡片重构：动态卡片替代筛选 Tab，点击高亮筛选；仪表盘每日金句同步首页
- 行为追踪里程碑点击完成（`toggle_milestone` 含奖励发放）

### 🐛 修复

- 良品率产出记录表格重复标签（HTML 未闭合）；删除按钮被固定列 `overflow:hidden` 裁切

## [2026-06-30] v3.19.0 — 开源准备：Docker 部署 + 配套文件

### ✨ 新增

- Docker 容器化：`docker-compose` 编排 mysql/backend/frontend，`nginx.conf` 反向代理 + SPA fallback
- 开源配套：`.env.example`、`.dockerignore`、MIT `LICENSE`、完整 `README.md`

### 🔧 优化

- `README.md` 重写：补 Docker 部署流程、功能模块表与设计理念

## [2026-06-29] v3.18.0 — 月度复盘结余修复 + 盘点排序

### 🐛 修复

- 月度复盘结余改由 `income - expense` 实时计算，消除结余为 0 但结余率为负的矛盾；符号/负数颜色修正
- 月度复盘手动录入 400（字段映射 + `partial=True`）；`wealth_balance_list` 删除 `age` 列解决 NOT NULL 冲突
- 盘点历史排序由 `-yearmon` 改为 `-btime`，同月多次盘点顺序正确

### 🔧 优化

- `MonthlyReviewSerializer` 字段设 `required=False` + `default=0`，避免新建记录缺字段报错

## [2026-06-29] v3.17.0 — 打卡补签 + 旅行路线重构

### ✨ 新增

- 打卡日历补签：点击过去日期补打卡，后端 `checkin` 支持指定 `date` 并重算连续天数
- 旅行路线推演重构：左侧路线列表 25% + 地图 75%，统一弹窗编辑、拖拽排序

### 🐛 修复

- 未来日期打卡拒绝（400）；已打卡日期重复点击提示而非再次弹窗

## [2026-06-26] v3.16.0 — 好恶物档案馆增强 + 体重图修复

### ✨ 新增

- 好恶物详情弹窗（700px，`pre-wrap` 保留换行）+ `TreasureCard` 卡片点击跳转打开详情

### 🐛 修复

- 体重趋势图目标线修正：markLine 改为当前未达成里程碑目标值，移除散点系列避免渲染错误

## [2026-06-25] v3.15.0 — 时薪自由职业模式 + 工具箱 UI 统一

### ✨ 新增

- 时薪计算器自由职业模式（`_calc_freelance` 双模式，历史列表"模式"标签列）；历史列表接入 `maskAmount` 脱敏
- 工具栏统一"返回工具集"按钮（由 `ToolDetail` 提供）

### 🔧 优化

- 9 个工具页宽度统一（`padding:20px` 移除 `max-width`）；`.back-bar` 改 `flex nowrap` 防换行

## [2026-06-25] v3.14.0 — 体重管理增强 + 布局修复

### ✨ 新增

- 体重目标调整记录（`WeightGoalAdjustment` 模型 + API 时间线）；月度进度自动推进（`check_weight_goal_status`）
- 体重趋势图改用 markLine 虚线标注目标，替代独立目标线 series

### 🐛 修复

- 月度进度卡片高度撑开、与趋势图间距缺失、`el-collapse-transition` 动画裁剪内容

## [2026-06-23] v3.13.0 — 目标行为追踪 + 小确幸修复

### ✨ 新增

- 目标行为追踪模式（单行为目标展开打卡视图 + 里程碑列表）；小确幸快乐程度扩至 5-20、奖励跟随快乐值
- 小确幸标签区同行换行显示

### 🐛 修复

- 小确幸保存失败（validator 与前端不匹配）；编辑 400（`joy_type` null→`''`）；奖励值与池余额同步

## [2026-06-23] v3.12.0 — 复盘工具箱 + 摘录馆增强

### ✨ 新增

- 复盘工具箱：5 种模板（每日/周/月/季度/人生编舟），历史可回溯编辑
- 摘录馆列表卡片新增标签渲染（语言 + 分类标签）

### 🐛 修复

- 摘录馆统计仅基于当前页计算导致翻页错误，改为后端聚合全量数据

## [2026-06-22] v3.11.0 — 自由支配额度计算器

### ✨ 新增

- 自由支配额度计算器（流动资产 + 年收入 + 债务 + 工作年限，历史保存/删除）
- 收件箱快速输入开放 `allow-create` 自定义类别

### 🐛 修复

- 收件箱自定义类别保存失败（模型 `choices` 约束移除）；好朋友跟踪分页 Vue 警告（`fetchRecords` 提为顶层）

## [2026-06-17] v3.10.0 — 例假跟踪 + 决策日志 + 个人画像

### ✨ 新增

- 例假跟踪（`MenstrualRecord` + 统计 + 趋势图）；决策日志工具；个人画像仪表盘（`/summary/profile` 7 维度）
- 小确幸快乐类型；收件箱"犹豫中"状态 + 自定义类别；身体-状态关联图；随机回顾新增摘录馆

### 🐛 修复

- 收件箱编辑保存 400（改用 PATCH + `hesitate_reason` null→`''`）；随机回顾过滤默认日记标题避免重复

## [2026-06-10] v3.9.0 — 里程碑增强

### ✨ 新增

- 里程碑详情字段（`description`，看板蓝色标识）；新增里程碑不再重建已完成记录，收件箱转里程碑自动填 `description`

### 🐛 修复

- 编辑已完成里程碑重复发放奖励：读取旧状态，仅状态变完成且未同步才发放

## [2026-06-09] v3.8.0 — 收件箱日历联动 + 日程视图

### ✨ 新增

- 收件箱与日历联动（`inbox/items/calendar/`）；日程视图 `/temporal/schedule` 聚合事项与里程碑
- 事项截止日期视觉增强（逾期标红/临期标橙）；日历圆点状态区分、列表重构、已完成与已转目标不重复

### 🐛 修复

- 日历圆点不可见：CSS class 名不匹配（`.dot-todo` → `.dot.todo`）

## [2026-06-08] v3.7.0 — 季度决策工作台 + 旅行统计修复

### ✨ 新增

- 季度决策工作台（`/summary/quarterly` 7 模块对比 + 智能追问引擎 + ECharts 柱状图）
- 收件箱统计卡片可点击筛选；月度明细新增达成率列（按阈值着色）

### 🐛 修复

- 旅行记录统计数字不一致：`get_province` 无法解析缩写/城市名致热力图漏显，修复后三处数字统一

## [2026-06-04] v3.6.0 — 周度时间追踪 + CSV 导入加固 + 里程碑弹窗

### ✨ 新增

- 年度周度时间追踪：52 周矩阵染色 + 年份选择 + 统计卡片；`WeeklyTimeCache` 模型与 `refresh_weekly_cache` 命令固化缓存
- 里程碑详情弹窗与截止日期编辑；行为记录新增 `action_date` 支持补录；好东西档案馆 + 好恶物双面档案（歹物 TAB 切换）

### 🐛 修复

- CSV 导入加固：改用 `request._request.FILES` 绕过 parser；axios `Content-Type: undefined` 自动生成 boundary；支持中文日期、编码回退、去重覆盖
- 周度追踪修复：MySQL `CONVERT_TZ` 不可用，改用预计算 `week`/`year`/`mon`/`day` 字段查询
- 行为记录修复：分页截断改 `pagination_class = None`；移除 `OrderingFilter`；`Coalesce(action_date,...)` 排序；`bulk_create` 显式传 `action_date`；`Func`→`Cast`

## [2026-06-04] v3.5.0 — 职业能量审计 + 环境校准 + 盘点增强

### ✨ 新增

- 职业能量审计工具（26 项 4 维度、-5~+5 自动判定）；环境校准工具（6 维度 1-5 自动判定）
- 收件箱分页 + "已处理"筛选；盘点录入改弹窗；盘点历史列表扩至 15 列

### 🐛 修复

- 复制上月报"无盘点记录"：`copy_last_month` 消除 `yearmon` 格式差异 + `btime` 类型修正

## [2026-06-03] v3.4.0 — 冲突追踪 + 良品率管理 + 收件箱增强

### ✨ 新增

- 冲突事件追踪（情绪等级/解决状态/关联人搜索 + 统计）；个人良品率管理（良品/不良品/废品 + 难度 + 趋势）
- 收件箱转里程碑、完成联动小确幸与奖励、工作分类、快速创建目标弹窗；月末读者盘点

### 🐛 修复

- 收件箱转里程碑（import 缺失/参数未传）；快速创建目标名称拼接；冲突 `contact_id`→`contact` 400；月末盘点路径；重复模型定义清理

## [2026-05-24] v3.3.0 — 全局隐私脱敏体系

### ✨ 新增

- 隐私脱敏体系：`UserProfile` + `ProfileView` API、`privacyStore` + 开关横幅、`privacy.ts` 脱敏工具集（仅收入脱敏）
- 脱敏覆盖关系/旅行/目标/定期存款/日历/日周明细等模块的姓名、金额、地点字段；CSV 导入重复校验

### 🐛 修复

- 关系分页与筛选联动丢失、总数不一致；标签合并重复联系人；目标列表总数与实际渲染不符（分页截断）

## [2026-05-23] v3.2.1 — 旅行路线推演 + 热力图修复

### ✨ 新增

- 旅行路线推演：路线预设 CRUD + 全国城市坐标数据库（省/市/区县三级）+ ECharts 地图动画；旅行记录表单新增区县字段（三级级联 + 自动地理编码）
- 地图站点圆圈缩小、目的地改 `el-autocomplete`；移除参数设置模块；表单字段各占一行

### 🐛 修复

- 现金流热力图周明细净结余为 0（`note`→`notes`/日期上限/已度过标记）与周格子颜色空白（自动调 `update_lived_status`）
- 目标编辑行为 PUT→PATCH；路线预设列表 `res.data?.results`；`WeeklySummary` 404 参数名修正

## [2026-05-16] v3.2.0 — 仪表盘重构 + 通知体系

### ✨ 新增

- 收件箱批量转目标、状态筛选标签；仪表盘系统宣言（localStorage）+ 随机回顾卡片；里程碑庆祝动画
- 通知服务（`Notification` 模型 + `notification_service.py`，三模块检查）

### 🗑️ 移除

- 收件箱移除"转为互动"功能及相关代码

## [2026-05-16] v3.1.1 — 文档整理与分页修复

### 📝 文档

- 补充 `frontend/README.md`（技术栈 / 目录结构 / 开发命令 / 模块规范），修正 `CLAUDE.md` 中的过时引用
- 建立 `CHANGELOG.md` 系统更新日志

### ✨ 新增

- 书籍模块 `action_item`（读完强制输出一个行动）；关系模块 `my_action`（记录我为对方做了什么）

### 🔧 优化

- 小确幸页删除「我的模板」模块，保留自定义记录表单与历史列表；舞蹈模块侧边栏标记「归档」（数据与页面保留，可恢复）

### 🐛 修复

- 关系档案列表分页不生效（服务端分页 + 前端 store 状态与筛选联动）；小确幸「累计获得」分页后显示错误

## [2026-05-16] v3.1.0 — 模块整合与批量修复

### ♻️ 重构

- 时间感知：活动追踪与时间统计合为一页；读者群体并入关系管理（TAB 切换）
- 侧边栏：去掉「分析统计」分组与「今日进度」假数据、去掉静态数字徽章，精神滋养下书籍与小确幸平级，新增读者群体 / 工具箱 / 美食地图入口

### 🔧 优化

- 财富管理：去掉月度日历中重复的视图切换按钮，新增随手记 CSV 导入；健康管理精简为里程碑地图 + 年度步数对比；舞蹈模块归档（保留数据与页面）

### 🐛 修复

- 现金流热力图颜色未按账单数据映射、BMI 指示器位置偏移、日记流热图格子与月份对齐、农历显示异常（十十六 / 初初八）
- 现金盘点编辑回填失败、定期存款统计含已取出记录、目标进度计算错误、里程碑奖励未发放到奖励池
- 小确幸预设模板被清空、关系详情页互动记录串号、美食图片上传与展示、工具箱繁简转换与图片转 GIF 未显示、侧边栏点击后需刷新才显示内容

---

## 版本规则

- **第一位**：重大架构变更
- **第二位**：侧边栏顶级菜单项增减
- **第三位**：小功能 / 重构 / 修复（含页内新功能、tab 页）

> 2026-08 之前，第二位曾用于「新增功能模块 / 页面整合」；此后按上表执行。

## 历史迭代

### v3.0.0（2026-04）— 新架构重构

- 从 `sycamore_django` 重构为新架构 `sycamore`
- 按生命维度组织模块：时间感知 · 身心健康 · 精神滋养 · 财富管理 · 连接与足迹 · 目标与项目
- 前后端分离：Django REST framework + Vue 3 Composition API
- 数据库由 SQLite 迁移至 MySQL
- 新增 `summary` 综合进度看板、工具箱、奖励池与目标联动、读者群体、美食地图、现金流热力图与月度日历

### v2.0.0（2024）— 旧系统

- 基于 Django + Bootstrap + ECharts 的初始版本
- 模块：`oneday` `times` `health` `wealth` `goals` `book` `dance` `sugar` `travel` `relation` `dams` `summary`
