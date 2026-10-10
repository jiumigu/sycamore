# Wealth — 财务管理

## Models

| Model | Table | 用途 |
|-------|-------|------|
| WealthLifeWeekCalendar | wealth_life_week_calendar | 3172 周周历（61年×52周） |
| WealthCurrentScenario | wealth_current_scenario | 单例推演状态 |
| WealthScenarioHistory | wealth_scenario_history | 推演历史 |
| WealthRegularList | wealth_regular_list | 定期存款 |
| WealthCashFlow | wealth_cash_flow | **已让位**（`managed=False` 外部表）：8 个科目已由 `wealth_asset_account` 数据化承载；读取已**不可达**，但**写入口仍开在路由上** —— 边界见「三表边界」节 |
| WealthBalanceList | wealth_balance_list | **半退役**（`managed=False` 外部表）：只留「收支流」6 列活着，8 个存量列 + `btime` 已退役 —— 边界见「三表边界」节 |
| WealthBillList | wealth_bill_list | 账单项明细（分类规则 / 归类汇总 / 比率取数的数据源，**managed=False 外部表**） |
| WealthLiabilityDetail | wealth_liability_detail | 负债逐笔台账（managed 新表，本金/剩余/利率/月供/还款方式） |
| WealthReceivableDetail | wealth_receivable_detail | 应收借出逐笔台账（managed 新表，借出日/约定期/已收回） |
| WealthAssetAccount | wealth_asset_account | 资产科目主数据（managed 新表，`code`/类别/形态/`is_liquid`/是否计表） |
| WealthAssetSnapshot | wealth_asset_snapshot | 资产快照头（managed 新表，年月唯一 + 负债/借出） |
| WealthAssetSnapshotItem | wealth_asset_snapshot_item | 资产快照明细行（managed 新表，一期一科目一行） |
| WealthClassifyRule | wealth_classify_rule | 账单项分类规则（managed 新表，一张表服务收入性质/支出刚性/现金流五类三个维度） |
| WealthPropertyCategory | wealth_property_category | 物件类别主数据（managed 新表，v3.60.0；唯一键 `(user_id, name)`；`default_lifespan_months` **仅作表单预填、绝不兜底**） |
| WealthProperty | wealth_property | 物件资产本体（managed 新表，v3.60.0；耐用品：冰箱/空调/床/柜子；FK `category` 用 **PROTECT**；`condition` 是 MySQL 保留字，且**只影响净值一项**（损坏 ⇒ 按 0 计，v3.60.1） |

## 三表边界与退役列（v3.60.14，**改财富表之前先读这一节**）

「我手头有多少钱」这件事，历史上先后由三张表承载。**现在只有一处是真源**，另两处是历史存档：

| 表 | 角色 | 写入 | 读取入口 |
|---|---|---|---|
| `wealth_asset_snapshot` + `wealth_asset_snapshot_item`（+ 主数据 `wealth_asset_account`） | ✅ **唯一真源**（存量 / 时点余额） | ✅ 资产盘点页 | `/asset/snapshots/*`、`/cashflow/overview/`、`/cashflow/trend/`、`/ratios/*` |
| `wealth_balance_list` | ⚠️ **半退役**：只留「收支流」列 | 仅「流」列（`total` 已转只读、写不进来） | 收入支出复盘页 |
| `wealth_cash_flow` | ❌ **已让位**（`managed=False`）：仅作历史存档 + 不可达回落 | ⚠️ **路由仍在**（UI 已无调用方，应关） | 不可达（回落分支 + 已无视图引用的列表接口） |

### 一、`wealth_balance_list`：流表里混着存量列

它的本职是**「收支流」**（某段时间赚了多少、花了多少），却同时塞了 8 个**「手头存量」**列。
2026-06 起复盘弹窗改版，弹窗只提交 6 个「流」键 ⇒ 下列列**从此再没有人写过**，逐月为 `NULL`：

| 列 | 语义 | 现状 |
|---|---|---|
| `balance` | 流水余额 | **退役**（曾被 `reconcile()` 读；该函数 v3.60.14 已删） |
| `accumulationfund` | 公积金 | 退役，无任何消费者 |
| `distance` / `borrow` / `lend` / `realnum` | 距离 / 借贷 / 借出 / 真正在手里的 | 退役，无任何消费者 |
| `btime` | 登记时间 | 录入路径从未送过（与上述同批断供） |
| `total` | 总存款 | ⚠️ **降级为只读兼容**：可读、**不可写**；新数据一律来自资产快照 |

2020-01 ~ 2026-05 这些列里的手填值是**唯一存档** ⇒ **不删列、不回填**（`managed=False`，删列不可逆）。

🔴 **口径：流表永不出现存量列。** 复盘记的是 flow、资产盘点记的是 stock；一张表同时装两者，
旧入口被新入口取代后存量列会**静默停更** —— 界面上看不出来，直到某天有人回头问「这里怎么空了」。

### 二、`wealth_cash_flow`：已让位，但**写入口还开着**

`managed = False` 外部表，**只读并行、永不加列**（见上文「资产口径」节）。
其 8 个科目已改由 `wealth_asset_account` 以**数据**承载。

**读取 —— 现实里读不到，但代码还在**：
`ratio_service.resolve_asset_source()` 只在「新体系一条快照都没有」时才回落 `RATIO_SOURCE_LEGACY`
（走 `cashflow_service.get_snapshot_series()`）。当前新体系有数据 ⇒ **该分支不可达**。
`/cashflow/snapshot/list/` 也读它，但其前端调用方（盘点历史组件）已无视图引用。
⇒ 别把它当「已彻底拆除」：**它是回落路径，不是被删掉的代码**。

**写入 —— ⚠️ 仍开着**：`POST/PUT/DELETE /cashflow/snapshot/` 与 `POST /cashflow/copy/`
经 `cashflow_service.create_or_update_snapshot()` **直接写这张表**（UI 已无调用方，但路由还在）。
⇒ 这是**尚未关闭的第二个录入口**；退役它是一轮独立改动（影响面大于字段退役），故本轮只记录、不动手。

**保留它 = 保留历史存档；不要恢复读取，也不要往里写。**

### 三、旧的「双跑对账」已下线

`GET /api/wealth/cashflow/reconcile/`（`cashflow_service.reconcile()`）已于 **v3.60.14 删除**：
它拿 `wealth_balance_list.balance` 当账面余额去比 `wealth_cash_flow` 合计，而该列自 2026-06 起恒为 `NULL`
⇒ 对 2026-06 之后的期次**恒判「不一致」**；且前端**零调用**。以后要对账请走资产快照。

### 四、🔴 「存款余额」只有一个录入口

复盘页的「存款余额」**不再手填**，由后端统一从资产快照取数（`review_service._deposit_payload()`），
并**连同来源一起下发**；前端**不判来源、不按数值猜、不自己算净值**，只按 `deposit_source` 查表渲染：

| `deposit_source` | 含义 | 前端表现 |
|---|---|---|
| `asset_snapshot` | 来自资产快照（净值） | 展示 `deposit_as_of` 期次 |
| `legacy` | 旧表 `total`（2026-06 之前存量） | 打「手填」标记 |
| `null` | 两处都没有 | 显示 `—`，**不是 0** |

「`null` ≠ 0」是本片的硬规矩：`null` = 没数据（占位 `—`），`0` = 一个已经下过的结论。

### 五、⚠️ 命名陷阱：「同名不同义」

`BalanceInfoSerializer` 里有个字段叫 `balance`，它是 `SerializerMethodField`，返回的是
**每月余额 `mbalance`**（复盘列表「每月余额」列的契约），**不是**同名 DB 列
`wealth_balance_list.balance`（流水余额，已退役）。DRF 要求**声明过的字段必须出现在 `fields` 里**，
所以这个 `'balance'` **必须留在 `fields` 中** —— 删掉它不是 DB 层 500，而是直接
`AssertionError: The field 'balance' was declared on serializer ... but has not been included in the 'fields' option`。
**改 `fields` 之前先分清：你删的是「声明字段」还是「模型列」。**

## 人生周历：「现在在第几周」只有一个真源（v3.60.15，**改推演 / 热力图之前先读这一节**）

热力图着色、账单按周聚合、推演起点全都按 `wealth_life_week_calendar.global_week_index` 对位，
所以「现在处在哪一周」这件事**只能读表**，不得按出生日期现算。

| 尺子 | 写法 | 跨年处会怎样 |
|---|---|---|
| ✅ 周历表（真源） | `is_lived=True` 里**索引最大的那一行** | 与历史着色、账单聚合天然同源 |
| ❌ 出生日期现算（已废） | `settings.WEALTH_BIRTH_DATE` + `today.isocalendar()[1]` | 与表错开：`age_year` 按**日历年年序**编（`year = 出生年 + age`）、`week_number` 以**当年第一个周一**为第 1 周 ⇒ 最坏差整整一年 |

2026-10-09 的现场：表说今天在 `(31,40)=索引 715`（最后一格彩色），现算说在 `(32,41)=索引 768`
⇒ 中间 **52 周**既非「已度过」（不上色）也不在推演覆盖范围内（无蓝框），
热力图在 31/32 岁之间裂出一条 52 格的对角缺口。

- 入口：`GET /wealth/age-week/` → `services/week_aggregator.current_age_week(user_id)`，
  响应含 `current_age` / `current_week` / `global_week_index` / `lived_weeks` / `source` / `birth_date`
- `lived_weeks` 与 `/wealth/summary/` 的 `lived_weeks` **同源同值**（都数窗口内 `is_lived`，**含本周**）；
  推演面板的进度基数直接显示它，**不再本地推算** —— 两处各算一次必然在跨年处差出 1～52 周
- 周历尚未初始化时回落到出生日期估算，并下发 `source='birthdate'`，让界面能说出「这不是按周历算的」
- ⚠️ **表是用哪个出生日期建的，决定了行标签（`age_year`）的真假**：本表的 `idx0` 落在 2013-01-07
  ⇒ 建表出生年 1995；而配置里是 1994-10-01 ⇒ 行标签整体比真实年龄**小 1 岁**。
  改它必须**先删后建**（`init_week_calendar` 靠 `ignore_conflicts` 撞主键会**静默跳过**，重跑无效），
  且删除动作按项目铁律由用户本人执行。推导与后果见 `TECH-NOTES §50`。

## Services

| File | 职责 |
|------|------|
| `services/calendar_init.py` | 初始化周历，按出生日期映射年龄→年份 |
| `services/week_aggregator.py` | 交易按周聚合 + net_level 7级颜色 + **`current_age_week()`（「现在」的唯一真源）** |
| `services/coverage_calculator.py` | 现金流推演算法（现金÷周预算 + 日利息复利） |
| `services/monthly_aggregator.py` | 月度日聚合 + 颜色等级 + 月度汇总 |
| `services/review_service.py` | 月度复盘（趋势/分类排行/月度清单/**月度对比**/生成盈亏；「存款余额」由 `_deposit_payload()` 从资产快照取数并**连同来源一起下发**） |
| `services/regular_service.py` | 定期存款完整业务逻辑 |
| `services/cashflow_service.py` | 现金盘点（资产全景/趋势/快照CRUD/复制上月；旧「对账」已于 v3.60.14 删除） |
| `services/debt_service.py` | 负债与应收逐笔台账（还款优先级/账龄分桶/逾期/快照对账） |
| `services/asset_service.py` | 资产科目主数据与按科目的资产快照（roll-up 汇总/种子科目/回填/跨模块取数 `net_worth_by_yearmon`；旧表双跑校验已删） |
| `services/classify_service.py` | 账单项分类（`match_classify_rule` **全项目唯一匹配实现** / 规则 CRUD / 三维度汇总与覆盖率 / 未归类候选 / 影响预览） |
| `services/expense_estimate.py` | 月均支出三点估算 `E=(O+4M+P)÷6`（应急金与比率的**共用分母**唯一实现） |
| `services/ratio_service.py` | 六项规划比率（取数 / 逐月趋势 / 锚定月 / 资产位置 / 口径元信息），**不含阈值** |
| `services/ratio_grade.py` | 判档唯一实现 `grade_ratio`（按 `constants.RATIO_BANDS` 判 good/warn/danger/normal），**不含阈值字面量** |
| `services/survival_calc.py` | 生存资源算法**唯一真源**（餐位求和/取最小、PERT 三档派生、保质期上限） |
| `services/survival_service.py` | 生存资源主数据 CRUD 与四类分析编排（删除保护在此） |
| `services/survival_combo_service.py` | 物资组合（分开登记、一起下锅）与配方组合行；成员整体替换、被引用拒删 |
| `services/survival_essential_service.py` | 必需品基准清单（一件只能挂一处、反向建物品、缺口对账） |
| `services/survival_snapshot.py` | 生存盘点快照与趋势（存结论不存明细、一天一点、不可编辑、配置指纹判可比） |
| `services/survival_stocktake.py` | 生存**实盘盘点**（工作表 / 提交即校准 / 降序历史；账面由服务端在提交那刻读，删记录不回滚库存） |
| `services/survival_flow.py` | 生存**库存流水**（v3.60.18）—— 🔴 **改库存的唯一写口 `record_flow()`**：建档 / 编辑 / 盘点三处都经它写并自动代记；`reverse_flow()` 撤销（补反向流水，**一条最多冲销一次**）；`summarize_flows()` 按月汇总**按单位分桶、跨单位不相加** |
| `services/property_calc.py` | 物件资产算法**唯一真源**（整月取整 / 直线法折旧且残值 0 / **损坏 ⇒ 净值归 0** / 净值截断到 0 / 报废那刻定格 / `zero_reason` 与五项合计） |
| `services/property_service.py` | 物件资产取数与 CRUD 编排（类别删除保护、状态离开报废时置空报废字段、保存前试算不写库） |

## API Endpoints

前缀 `/api/wealth/`

> 🔴 **路由顺序铁律（v3.60.16）：静态路径在前，`path('', include(router.urls))` 放最后。**
> DRF 详情路由 `<pk>` 的默认正则 `[^/.]+` 能匹配**任何**一段不含斜杠的字符串 ——
> 所以「`前缀/xxx/`」形式的静态路径只要写在路由器**之后**，就会被它抢走成 `pk='xxx'`
> → 详情查不到 → **404**。现场：`bills/by_week/` 被 `bills/<pk>/` 吃掉，而前端把 404
> 静默当成「这一周没有账单」⇒ 同一个弹窗里「上面有收支、下面说无记录」。
> **新增静态路径不必再操心顺序**（它们天然在前面），但**别把路由器移回列表开头**。
> 守卫用例：`tests/test_bills_by_week.py::test_no_static_path_is_shadowed_by_a_dynamic_route`
> —— 全站扫描，任何静态路径 resolve 出来的视图 ≠ 它声明的视图即失败。

| 方法 | 端点 | 用途 |
|------|------|------|
| GET | /calendar/ | 周历列表（含聚合收支） |
| GET | /weekly_summary/&lt;id&gt;/ | 单周明细（⚠️ 前端**零调用**，仍在挂着） |
| GET/PUT | /scenario/current/ | 当前推演状态 |
| POST | /calculate_coverage/ | 现金流推演计算 |
| GET | /summary/ | 人生总览 |
| GET | /bills/by_week/ | 按周账单明细（**依赖上面那条路由顺序**；`week_index` 必填且须为整数——缺失/非数字均 400；区间半开 `[周一, 下周一)`，与 `/calendar/` 的聚合**同源同区间**） |
| POST | /calendar/init/ | 初始化周历 |
| GET | /monthly_calendar/ | 月度日历数据 |
| GET | /daily_detail/ | 单日收支明细 |
| GET | /monthly_summary/ | 月度汇总统计 |
| POST | /bill/create/ | 快速记账 |
| GET | /regular/stats/ | 定期存款统计 |
| GET | /regular/expiring/ | 到期提醒 |
| GET | /regular/list/ | 列表（银行/flag/关键字筛选） |
| GET | /regular/banks/ | 银行列表 |
| POST | /regular/update_status/ | 批量更新状态 |
| GET/PUT/DELETE | /regular/<pk>/ | 单条定期详情/更新/删除 |
| POST | /regular/<pk>/mature/ | 到期处理（取款/转存） |
| GET | /cashflow/overview/ | 资产全景（最新快照 + 健康指标） |
| GET | /cashflow/trend/ | 资产趋势（?months=12 月度序列） |
| POST | /cashflow/snapshot/ | 创建/更新快照 |
| GET | /cashflow/snapshot/list/ | 快照列表（?page=&page_size= 分页） |
| POST | /cashflow/copy/ | 复制上月数据 |
| GET/POST | /asset/accounts/ | 资产科目主数据（**裸数组**；?include_inactive=1） |
| PATCH/DELETE | /asset/accounts/<pk>/ | 科目更新 / 删除（被快照引用时 400，引导改停用） |
| GET | /asset/accounts/summary/ | 科目结构汇总（按类别的科目数/计表数/可取数） |
| POST | /asset/accounts/seed/ | 初始化种子科目（幂等，`overwrite=false` 不覆盖已改的） |
| GET/POST | /asset/snapshots/ | 资产快照（**裸数组** + `?limit=24&year=`；POST 按 yearmon 幂等） |
| GET/PUT/DELETE | /asset/snapshots/<pk>/ | 快照详情（含明细）/ 更新（**不可改年月**）/ 删除 |
| GET | /asset/snapshots/by_yearmon/?yearmon= | 按年月取一期（编辑弹窗回填） |
| ~~GET~~ | ~~/asset/snapshots/compare/?yearmon=~~ | ❌ **已退役（v3.60.7）**：回填后两边同源，比对退化成恒等式且会取错行给出假差额 —— 路由已删，见「三表边界」节 |
| ~~GET~~ | ~~/asset/snapshots/legacy_totals/~~ | ❌ **已退役（v3.60.7）**：旧口径并排展示，随双跑对账一起去掉 —— 路由已删 |
| GET/POST | /debt/liabilities/ | 负债台账列表（**裸数组**）/ 新增（?status=&category= 筛选列表） |
| PATCH/DELETE | /debt/liabilities/<pk>/ | 单条负债更新 / 删除 |
| GET | /debt/liabilities/summary/ | 负债汇总（加权平均利率 / 月供合计 / 分类分布 / 与快照 borrow 对账差） |
| GET/POST | /debt/receivables/ | 应收借出台账列表（**裸数组**）/ 新增（?status=&aging_bucket= 筛选列表） |
| PATCH/DELETE | /debt/receivables/<pk>/ | 单条借出更新 / 删除 |
| GET | /debt/receivables/summary/ | 应收汇总（回收率 / 账龄分布 / 逾期 / 与快照 lend 对账差） |
| GET/POST | /classify/rules/ | 分类规则台账（**裸数组**；?include_inactive=1）/ 新增 |
| PATCH/DELETE | /classify/rules/<pk>/ | 规则更新 / 删除（响应带 hint：删规则会重算往期，建议改停用） |
| GET | /classify/rules/summary/ | 规则结构汇总（各匹配字段条数 / 各维度覆盖条数 / 默认优先级） |
| POST | /classify/rules/seed/ | 初始化种子规则（幂等，`overwrite=false` 不覆盖已改的） |
| POST | /classify/rules/preview/ | **影响预览（不写库）**：命中多少 / 真正改动多少 / 前后标签对照 |
| GET | /classify/rules/periods/ | 有账单数据的年月列表（**裸数组**，倒序） |
| GET | /classify/results/?yearmon= | 归类汇总（三个维度 + 各维度覆盖率 + 排除项；不传 = 全周期） |
| GET | /classify/results/unclassified/ | **未归类候选**（按 分类/子分类 聚合，金额降序，附建议规则） |
| GET | /ratios/ | 六项规划比率总览（?anchor=YYYY-MM 锚定月） |
| GET | /ratios/trend/ | 逐月趋势（?months=；缺月为 `available=false`，前端画断点） |
| GET | /ratios/anchors/ | 可选锚定月列表（**裸数组**） |
| GET | /ratios/asset_position/ | 资产位置（各类别金额与占比） |
| GET | /ratios/meta/ | **口径元信息**（九项 `{formula, note, bands, unit, target}` 裸数组 —— 前端气泡的唯一文案来源） |
| GET/POST | /property/categories/ | 物件类别（**裸数组**）/ 新增（同名 400） |
| PATCH/DELETE | /property/categories/<pk>/ | 类别更新 / 删除（其下有物件 → 400 + 可照做的提示，**不级联**） |
| POST | /property/categories/seed/ | 初始化六个默认类别（幂等；**不预设任何物件、不给默认年限**） |
| GET/POST | /property/items/ | 物件列表（**裸数组** + 派生列 + `issues`）/ 新增（?category=&status=&condition=&search=） |
| PATCH/DELETE | /property/items/<pk>/ | 物件更新 / **物理删除**（无软删开关：报废已承担「不用了」的语义） |
| POST | /property/items/preview/ | **保存前试算（不写库）**：走 `property_calc` 同一段代码，绝不另写第二份公式 |
| GET | /property/summary/ | 首屏四卡 + 各合计块的未计入件数 |
| GET | /property/meta/ | 状态词表 / 状况词表 / 口径元信息（`bands` 恒 `[]`）/ `issue_labels` / 固定说明句 |

## 资产口径（v3.58.19 财务规划口径纠偏）

资产类指标的**唯一实现**在 `services/cashflow_service.py`，阈值与科目清单在 `constants.py`。

| 口径 | 计算式 | 对外字段 |
|------|--------|----------|
| 流动资金 | 7 个活期账户之和（支付宝/微信/现金/建行/工行/中行/农信社） | `summary.flow_total` |
| 金融资产 | 流动资金 + 公积金 | `summary.total` / `summary.financial_assets` |
| 总资产 | 金融资产 + 应收借出 | `summary.total_assets` |
| 净资产 | 总资产 − 负债 | `summary.net_worth`（`realnum` 为兼容别名，同值） |

**三条强制约定**

1. **比率类指标一律以「总资产」为分母** —— `liquidity_ratio` / `debt_ratio` / `provident_fund_ratio` 同分母才互相可比。分母漏计应收借出会使负债率被系统性高估；`debt_ratio_legacy` 只作旧口径对照，**不用于展示**。
2. **应急金以「月数」判定** —— `emergency_fund_months = 流动资金 ÷ 近 EXPENSE_LOOKBACK_MONTHS 月平均月支出`。分子含银行卡活期（原实现只算支付宝+微信+现金）；目标月数由 `EMERGENCY_MONTHS_TARGET` 下发，**前端不写死阈值**。月均支出不可得时，`emergency_fund_months` / `emergency_gap` / `emergency_target_amount` 三个字段为 `null`。
3. **月均支出对「有记录的月份数」取均值**，不除以固定回看月数 —— 否则无记录月份被当成零支出，把月数算虚高。取数优先 `wealth_bill_list` 明细，明细无数据时回落 `wealth_balance_list.outmoney`。

⚠️ `wealth_cash_flow` 是 `managed = False` 的外部遗留表：**只读、不改结构**。科目为 8 个物理列，新增科目须另建 managed 表（P1 阶段方案见 `docs/财务三表能力评估-财务规划师视角-20260920.md`），**不得对该表执行 ALTER**。

⚠️ 命名对应：`/cashflow/*` 这一组接口承载的是**资产负债表快照**（资产盘点），不是现金流量表。真正的现金流量表（按活动性质归集）尚未建设，命名空间预留给 `/cash-flow-statement/*`。

## 负债 / 应收逐笔台账（v3.58.20，P1-A）

两张 **managed 新表**（`wealth_liability_detail` / `wealth_receivable_detail`）。
派生口径的唯一实现在 `services/debt_service.py`，阈值在 `constants.py` —— **视图层不得再算一遍**。

| 口径 | 计算式 | 说明 |
|------|--------|------|
| 已还本金 | 借款本金 − 剩余本金（下限 0） | 剩余本金随还款手工更新 |
| 年利息成本 | 剩余本金 × 年利率 ÷ 100 | 单利近似，不含还款计划与复利 |
| 加权平均利率 | Σ(剩余本金 × 年利率) ÷ Σ剩余本金 | **权重是余额，不是笔数** |
| 还款优先级 | 雪崩法 = 利率降序；雪球法 = 余额升序 | 仅「在还」编号，已结清为 `null` |
| 未收回余额 | max(借出本金 − 已收回, 0) | 已收回多于本金时按 0 截断 |
| 账龄 | 今天 − 借出日 → 按 `RECEIVABLE_AGING_BUCKETS` 归桶 | 闭区间；借出日为空**不归桶** |
| 逾期 | 状态「在借」且约定还款日 < 今天 | 约定还款日为空则不做逾期判定（无依据） |

**三条强制约定**

1. **账龄分桶边界只在 `constants.RECEIVABLE_AGING_BUCKETS` 定义一份**，服务层与测试同源，前端只按后端返回顺序渲染，**不在前端重定义天数阈值**。
2. **列表端点一律返回裸数组**（`pagination_class = None`）—— 被全局分页包成 `{count, results}` 时，前端按数组消费会**静默显示为空**。新增列表接口必须断言「返回类型是数组」。
3. **台账与快照不同步时只报差额、不改数据**：`borrow_diff` / `lend_diff` = 台账合计 − 快照值，正数表示台账多于快照。快照是历史事实，**不回溯篡改**。

⚠️ 与快照的边界：`wealth_cash_flow.borrow` / `lend` 是**每月盘点一次的汇总数**，这两张表是**逐笔明细**，两者互不写入。
⚠️ 迁移 `wealth/0016_liability_receivable_detail.py` 已生成但**未在开发库执行** —— 建表由用户手动 `python manage.py migrate wealth`；测试库结构由 `backend/conftest.py` 的 session 级镜像 DDL 保证（`--no-migrations --reuse-db` 下新表不会自动出现）。

## 资产科目主数据 / 按科目的资产快照（v3.58.21，P1-B）

三张 **managed 新表**（`wealth_asset_account` / `wealth_asset_snapshot` / `wealth_asset_snapshot_item`），
把「有哪些资产科目」从**表结构**搬进**数据**。派生口径的唯一实现在 `services/asset_service.py`，
**视图层不得再算一遍**。

解决的问题：旧表 `wealth_cash_flow` 把 8 个科目硬编码成物理列，而它 `managed = False` ——
要加一个「证券账户」就得对外部表 `ALTER TABLE`，等于**加不了**。现在加科目只是插一行。

### 汇总口径（即验收标准）

| 口径 | 计算式 | 说明 |
|------|--------|------|
| 参与汇总的科目 | `include_in_balance_sheet = True` | 其余只进明细，合计落在 `excluded_total` 单独提示 |
| `liquid_total` | Σ 参与汇总且 `is_liquid` | **应急金分子** |
| `category_totals` | 四个类别各自合计 | **恒返回 4 个键**，缺失补 0（前端按固定顺序渲染） |
| `financial_assets` | Σ 参与汇总且类别 ≠ 自用 | 非自用资产合计（含应收） |
| `total_assets` | `financial_assets + self_use_total` | |
| `net_worth` | `total_assets − borrow` | borrow 在快照头上（负债不是资产，不进科目表） |
| `available_net_worth` | `financial_assets − borrow` | 「能变成钱的净值」，剔除自用资产 |

### 四条强制约定

1. **`category` 与 `is_liquid` 是两个正交维度。** `category` 回答「这是什么资产」（财务规划的配置视角），
   `is_liquid` 回答「能不能马上用」（应急金分子）。公积金是「`category=流动性` 但 `is_liquid=False`」
   的典型 —— **不是数据错误，别去"修"它**。
2. **应收借出是一个资产科目**（`code='lend'`，`category='应收'`），负债**不是**科目（以快照头 `borrow`
   参与减法）。旧表把二者并排放在一行纯属历史包袱。
   快照头的 `lend` 只作对账参考，不参与合计；与应收类科目合计不一致时返回 `receivable_gap`
   —— **只报差额、不改数据**（与 P1-A 的 `lend_diff` 同性质）。
3. **快照头不缓存任何派生合计。** 缓存会制造第二个真源：改动科目主数据的类别后，历史快照的缓存值
   会与明细对不上。对应口径：**金额是历史事实、不可变；分类是当前视角、随科目主数据联动。**
4. **科目被任何快照引用后不可删除**（FK `PROTECT` + 视图转 400），只能 `is_active=False` 停用。
   否则删科目会把历史快照悄悄挖空，往期净资产凭空变化。

### 与旧表的关系：并行 + 不自动迁移（「双跑」已于 v3.60.7 退役）

`wealth_cash_flow` **原样保留**，两套并行。回填与比对都**由用户手动触发**：

```
# 1. 建表（AI 不执行）
cd backend && ../.venv/bin/python manage.py migrate wealth

# 2. 先看会做什么
../.venv/bin/python manage.py wealth_seed_asset_accounts --dry-run

# 3. 只建科目
../.venv/bin/python manage.py wealth_seed_asset_accounts

# 4. 建科目 + 回填全部旧快照
../.venv/bin/python manage.py wealth_seed_asset_accounts --with-snapshots
```

回填已执行完毕（旧表 18 期 → 新体系 18 期）。验收：打开「资产盘点」页，资产趋势应显示
回填后的期数、概览期别为最新一期。

⚠️ 曾有的「双跑对账」（`GET /api/wealth/asset/snapshots/compare/`）已于 **v3.60.7 退役**：
回填后两边同源，比对退化成恒等式；且它对旧表「同月两行」的期次会选到与回填不同的行
（`.first()` 按主键序，回填按 `btime` 最新），给出**假差额**。旧表保留为历史存档。

✅ 迁移 `wealth/0017_asset_account_snapshot.py` 已在开发库执行（建表完成）；测试库结构由
`backend/conftest.py` 的 session 级镜像 DDL 保证（`--no-migrations --reuse-db` 下新表不会
自动出现；DDL 须与 `sqlmigrate wealth 0017` 输出逐字对齐）。

---

## 账单项分类规则（v3.58.22，P1-C）

### 解决什么

`wealth_bill_list` 只记「这笔钱归在哪个分类」（`category` / `subcategory` / `merchant`），
不记「这笔钱是什么**性质**」。于是三类财务规划指标算不出来：

| 想算的指标 | 缺的那把尺子 |
|---|---|
| 被动收入覆盖率 | 收入是 **主动 / 被动 / 一次性** |
| 刚性支出覆盖率 | 支出是 **固定 / 可变** |
| 现金流量表五类归集 | 每笔是 **收入流入 / 必需支出 / 品质支出 / 投资支出 / 债务偿还** |

三者机制同构（按特征给账单项打标签），故**合并为一张规则表** ——
只维护一套界面、一套匹配实现（财务系统里「科目映射表」的标准做法）。

⚠️ 与 `wealth_bill_list.necessity` 的区别，**不要混用**：
`necessity`（必要 / 可选 / 冲动）刻画的是「这笔钱该不该花」，是自控力；
`expense_nature`（固定 / 可变）刻画的是「这笔钱能不能不花」，是抗风险能力。
且实测 `necessity` 全表非空仅 149 / 6588 行（98% 为空），本就不可依赖。

### 匹配口径（即验收标准）

```
命中条件：账单项的 rule_field 字段值 == rule.match_value（**精确相等**，非模糊、非正则）
胜负规则：① priority 数值大者胜
          ② 同优先级时**更具体的字段胜**（merchant 30 > subcategory 20 > category 10）
```

为什么平局不看 id：那会让结论随「谁先建的规则」而变 —— 同样两条规则换个创建顺序
结论就不同。默认优先级由具体度派生（`CLASSIFY_RULE_FIELD_SPECIFICITY` × 10），
所以「子分类规则天然压过同名分类规则」这件事**不需要用户理解优先级数字**。

### 四条强制约定

1. **分类结果不落库、实时算**。账单表是 `managed=False` 外部表（加不了列），
   且「金额是历史事实、**分类是当前视角**」—— 改规则本就应当回溯地改变往期报表。
   这与 P1-B 资产快照「头部不缓存派生合计」是同一条原则。
   代价是改规则有历史影响，故提供 `POST /classify/rules/preview/`（不写库）先看会动多少。
2. **转入 / 转出 / 余额变更不计入**。前两者是账户间搬运（实测成对出现、金额恒等，
   如 2026-04 各 21 笔 48310），计进去会让收支总额双双虚增；后者是对账修正行，
   不对应任何真实经济行为。三者都在响应的 `excluded[]` 里显式报出，不静默丢弃。
3. **未归类必须显式报出**。每个维度各有一个覆盖率，分母是**该维度自己的适用金额**
   （收入维度用收入总额、支出维度用支出总额、现金流用收支合计）—— 用一个统一分母
   会把收入覆盖率被庞大的支出额稀释成接近 0，看着像规则没生效。
4. **收支方向隔离**。一条 `merchant` 规则可能同时命中收入行与支出行（如「支付宝」），
   此时收入行只认收入侧标签、支出行只认支出侧标签，另一侧自动忽略 ——
   否则会出现「支出行带了收入性质」这种脏数据。

### 加一个匹配字段必须同时改三处

`rule_field` 不是自由文本，加维度要**同时改**：

| 位置 | 文件 |
|---|---|
| 字段枚举 | `apps/wealth/constants.py` → `CLASSIFY_RULE_FIELDS` / `CLASSIFY_RULE_FIELD_SPECIFICITY` |
| 取值分支 | `services/classify_service.py` → `match_classify_rule`（**全项目唯一匹配实现**） |
| 前端下拉 | `frontend/src/modules/wealth/types/wealthTypes.ts` → `CLASSIFY_RULE_FIELDS` + `ClassifyRulePanel.vue` |

**漏前端 = 选不到，漏后端 = 静默不生效。** 与 redemption 归因外挂同款坑。

### 种子规则与「刻意不种」的项

`CLASSIFY_SEED_RULES` 共 25 条，分两层：先给整类一个默认（`priority=10`），
再用子分类规则（`priority=20`）把该类里性质相反的部分挑出来。
例：食品酒水整类按「基本伙食」计固定，而「垃圾食品」被子分类规则覆盖为可变。

**刻意不种**（判定需要用户本人拍板，不由 AI 猜）：
`其他收入` / `意外来钱` / `零花钱` / `礼金收入` / `中奖收入`（归属含糊）、
`动车`（通勤还是出行）、`无可救药`（字面无法判断）。这些会出现在
`GET /classify/results/unclassified/` 里，由用户补规则。

```bash
# 建表（AI 不执行）
cd backend && ../.venv/bin/python manage.py migrate wealth

# 先看会写什么
../.venv/bin/python manage.py wealth_seed_classify_rules --dry-run

# 建规则（幂等，不动界面上改过的）
../.venv/bin/python manage.py wealth_seed_classify_rules

# 用种子值覆盖已有规则（会冲掉界面上的改动）
../.venv/bin/python manage.py wealth_seed_classify_rules --overwrite
```

⚠️ 迁移 `wealth/0018_classify_rule.py` 已生成但**未在开发库执行** —— 建表由用户手动
`migrate`；测试库结构由 `backend/conftest.py` 的 session 级镜像 DDL 保证
（DDL 须与 `sqlmigrate wealth 0018` 输出逐字对齐）。

### 与其他阶段的关系

`classify_dimension_totals()` 是给比率体系（P2-A）取数用的轻量入口 ——
六项新增比率（被动收入覆盖率、刚性支出覆盖率、DTI 等）**已于 v3.58.23 交付**，
见 `services/ratio_service.py` / `ratio_grade.py` 与 `/ratios/*` 接口，
判定线只在 `constants.RATIO_BANDS` 一份。

**未做**：现金流量表的按月聚合（P2-B）—— 即按「收入流入 / 必需支出 / 品质支出 /
投资支出 / 债务偿还」五类出的流量表。分类标签已具备（`cashflow_class`），缺的是聚合端点。

---

## 生存资源盘点（v3.59.0 一期 / v3.59.1 二期 / v3.59.3 实盘盘点 / v3.59.7 必需品对账，P3-A）

盘的是**物**（吃 / 穿 / 用 / 数字 / 医药），回答两个问题：

> 按现在的消耗方式，这些东西还能撑多久；哪一类先断；断的是钱这条腿还是物这条腿。
>
> 以及（v3.59.7）：**「我漏了什么」** —— 天数答不了这件事，因为没录入的东西不在分母里。

与同 app 里的金融资产体系**刻意分开命名**：`WealthAsset*` 是钱，`Survival*` 是物。
`wealth_asset_snapshot` 这个表名早已被金融侧占用，照抄必撞。

### 数据模型（15 张 managed 表，八段迁移）

| 迁移 | 表 |
|---|---|
| `0019_survival_models` | `wealth_survival_category` / `_unit` / `_item` / `_recipe` / `_recipe_line` |
| `0020_survival_snapshot` | `wealth_survival_snapshot` / `_snapshot_category` |
| `0021_survival_stocktake` | `wealth_survival_stocktake` / `_stocktake_line`（并给 `_item` 加 6 列） |
| `0022_survival_cycle_nullable` | 无新表：把 `_item` 的 `use_cycle_num` / `use_cycle_unit` / `use_times` 放宽为可空，并清掉按天物品上的回填值 |
| `0023_survival_essential` | `wealth_survival_essential`（**只有 `CreateModel`、无数据迁移** —— 建表 ≠ 种清单，种清单走幂等命令 / 接口） |
| `0024_survival_essential_items` | `wealth_survival_essential_items`（**Django 自动创建的中间表**，没有显式 through 模型）+ 把原 `item_id` 单值搬进去、再删旧列 |
| `0025_survival_combo` | `wealth_survival_combo` / `_combo_item` / `_recipe_combo_line`（**只有 CreateModel、无数据迁移** —— 只建空表） |
| `0027_survival_flow` | `wealth_survival_flow`（v3.60.18；**只有 CreateModel** —— 流水从建表那刻起才有记录，**不补造期初基线**） |

⚠️ 0024 的 operations 顺序是**先建新表 → 搬数据 → 再删旧列**，不是 `makemigrations`
   默认给出的「先删列 → 再建表」—— 照默认顺序走，用户此前手工挂好的关联
   在删列那一步就没了，事后只能翻备份。

| 表 | 作用 | 关键字段 |
|---|---|---|
| `wealth_survival_category` | 物资类别 | `consume_mode`（算法分派）/ `aggregate_mode`（聚合口径：**可替代类求和、并列类取最小**；配餐类固定 min；「用」类 v3.59.7、「穿」类 v3.59.8 由 sum 改 min） |
| `wealth_survival_unit` | 消耗单位 | `base_unit` + `to_base_rate` —— 跨单位换算的唯一依据 |
| `wealth_survival_item` | 物资物品 | `satiety`（果腹/零食/调味/饮水）、`days_per_unit`、`uses_per_unit`+`use_cycle_*`（**按次三兄弟一律可空、不给默认值**：按天口径下必须是 NULL，判据只看 `uses_per_unit`）、`expire_date`、`stocktake_cycle_days`、`restock_threshold` |
| `wealth_survival_recipe` | 配餐配方 | `meals_per_day`（基准刻度） |
| `wealth_survival_recipe_line` | 配方行 | `role`（staple 主食位 / required 必配位），**真外键** |
| `wealth_survival_essential` | 必需品基准项（「本该有什么」，v3.59.7） | `scope`（core 底线必需 / optional 改善型）、`unit_name`（**仅录入提示、不参与计算**）、`hint` |
| `wealth_survival_essential_items` | 基准项 ↔ 物品 的**中间表**（v3.59.12） | 一件基准项可挂多件（睡衣分夏/秋/冬）；**组内取最小、不求和** —— 见下「十二期」 |
| `wealth_survival_combo` | 物资组合（v3.59.13） | `category` FK、`(user, category, name)` 唯一；**不存餐位、不存任何派生值** |
| `wealth_survival_combo_item` | 组合成员（v3.59.13） | `item` / `unit` 均 **PROTECT**、`quantity_per_serving`、`(combo, item)` 唯一 |
| `wealth_survival_recipe_combo_line` | 配方组合行（v3.59.13） | `combo` **PROTECT**、`role`（**餐位只在这里、不在组合本体上**）、`(recipe, combo)` 唯一；**没有用量列** |
| `wealth_survival_flow` | 库存流水（v3.60.18） | `item` **SET_NULL**（物品删了历史仍在）、`item_name`/`category_name`/`unit_name` **三列是当时的快照**、`delta`（有符号变化量）、`channel`（谁写的）/ `reason`（为什么）**正交**、`reverses`（自引用 FK，撤销时指回原笔）、🔴 **刻意没有 `quantity_after`** —— 流表永不出现存量列（同 §49 的账） |

### 算法真源 `services/survival_calc.py`（唯一实现）

```
配方可支撑餐数 = min(主食位求和, 各必配位最小值)
   同餐位可替代 → 求和；跨餐位必配 → 取最小（木桶效应只在这里成立）
   组合行（v3.59.13）= min(组内各件单独可撑餐数)
       组内并列缺一不可 → 取最小；短板点名**组内那件物品**，不是组合名
       组内任一件算不出 ⇒ 整行 null（逐件 issues 原样收进这一行，不静默跳过）
非配餐天数     = 数量 × 单件可用天数 ÷ 消耗速率系数
单件可用天数   = 按天：days_per_unit
                 按次：uses_per_unit × (use_cycle_num × CYCLE_DAYS[unit] ÷ use_times)
保质期是硬上限 = min(库存天数, 最近到期距今)
PERT           = (O + 4M + P) ÷ 6，σ = (O − P) ÷ 6
   三档由**消耗速率**派生（配餐：省2/常3/放4 餐；其余：0.8 / 1.0 / 1.3 倍）
类别聚合       = sum（可替代求和）或 min（并列短板）—— **没有「平均」这一档**
综合           = 跨类别取最小
```

**计量口径两条，单向优先、绝不回退**（v3.59.3）：

| 情形 | 结果 |
|---|---|
| 填了 `uses_per_unit` | 按次（**原始输入**） |
| 否则 | 按天（`days_per_unit`，**派生值**） |
| 两条都没填 | `ISSUE_NO_DAYS_PER_UNIT` |
| 按次配置残缺（`use_cycle_num` 或 `use_times` ≤ 0） | `ISSUE_BAD_CYCLE`，**不静默回退到按天** |

⚠️ **残缺时为什么不许回退**：按天是派生值，可能早就过期；回退等于拿它顶替用户刚改的原始输入，
用户会把「我明明填了」看成另一个数、还找不到地方改。宁可报错让他去补全。

周期 → 天 的换算**只在一个地方**：`constants.SURVIVAL_CYCLE_DAYS = {'day':1,'week':7,'month':30}`，
由 `use_interval_days()` 独家使用（与 `cash_days_from_months` 的 30 天/月同惯例）。
折算后的 `days_per_unit_effective` 与口径标记 `life_mode` 一并下发，前后端共用一条判据 ——
界面显示「一件可用」必须用前者：按次物品的 `days_per_unit` 是空的，直接读会显示成「未填」。

四条不变量：

1. **配餐类跨配方固定取最小**（早/正餐每天都在吃），`aggregate_mode` 对它不生效；
   界面显示 `aggregate_mode_effective` 而不是用户填的值，避免「写求和、算取最小」。
2. **分派只看 `consume_mode`，不看类别名** —— 把「吃」改名成「口粮」算法照常。
3. **算不出来返回 `null` + `issues`，绝不返回 0**；配方缺件判 `trustworthy=False` 并
   在 `issues` 里点名是哪个配方、哪件食材 —— 静默跳过会让这道菜算得更耐吃。
4. **派生值一律不落库**（可支撑餐数、三档、期望值全部运行时算）。

### 接口

```
GET    /api/wealth/survival/analysis/?date=YYYY-MM-DD   综合分析（首屏一次取全）
GET    /api/wealth/survival/meta/                        枚举 + 口径（单一出口）
GET    /api/wealth/survival/metrics/meta/                口径元信息（裸数组）
CRUD   /api/wealth/survival/categories/                  含 POST seed（幂等初始化五类 + 基准清单）
CRUD   /api/wealth/survival/units/
CRUD   /api/wealth/survival/items/
CRUD   /api/wealth/survival/recipes/                     配方行整体替换（含 combo_lines）
CRUD   /api/wealth/survival/combos/                      组合（成员整体替换；被配方引用时删除 → 400）
CRUD   /api/wealth/survival/essentials/                  基准清单（默认按紧迫度排；`?sort=order` 得录入顺序）
GET    /api/wealth/survival/essentials/reconcile/        缺口对账汇总（**刻意不下发明细**）
POST   /api/wealth/survival/essentials/seed/             写入基准清单（幂等，**不预设任何库存数量**）
```

⚠️ `survival/essentials` 与 `survival/items` 是**两条路径，别合并** —— 一个是「本该有什么」
（认知），一个是「实际有多少」（库存）；合并后「我漏了牙膏」会被读成「牙膏数量是 0」。

列表端点均 `pagination_class = None`（裸数组）—— 六个：categories / units / items / recipes / essentials / combos。

### 删除保护

删类别时若其下仍有物品 / 配方 / 单位 / 组合 → **400 + 可照做的提示**，不级联；
删单位仍被引用、删物品仍被配方 / 组合引用、删组合仍被配方引用同理。级联会让「删掉一个建错的空类别」与
「删掉整柜粮食」走同一个按钮，代价不对称且不可逆。

### 盘点快照（v3.59.1，二期）

一期回答「现在能撑多久」，二期回答**「比上次是变长了还是变短了」** ——
只有第一个问题时，那个数字每看一次都像第一次看。

迁移 `wealth/0020_survival_snapshot`（**已生成、未执行**）

| 表 | 作用 | 关键点 |
|---|---|---|
| `wealth_survival_snapshot` | 快照**头**（那一天的结论） | `UniqueConstraint(user_id, snapshot_date)` —— **一天一点** |
| `wealth_survival_snapshot_category` | 类别明细 | `category` 用 `SET_NULL`；`UniqueConstraint(snapshot, category_name)` |

三条必须守住的判据：

1. **存结论，不存明细。** 落的是那一天的**天数 / 最短类别 / 瓶颈 / 覆盖率 / 计数 / 可信度**，
   不是那一天的库存列表。若只存明细、每次按今天的配置重算，历史曲线会被**追溯性改写**
   —— 今天改一次消耗速率，过去三个月的点会一起跟着变，而使用者看不出来。
   ❗ 这与一期「派生值不落库」**不冲突**：一期禁的是「缓存当下随时可重算的值」，
   二期要的**恰恰是**「那时我以为能撑多久」这个历史事实。**当下不缓存，历史不自算。**
2. **快照不可编辑。** `PUT` / `PATCH` 一律 `405`。可编辑的历史等于伪造的历史 ——
   把上个月那个不好看的数改掉，曲线就永远只升不降了。要改只能删掉重盘。
3. **可比与否必须说出来。** 对比两点的**配置指纹**（类别集合 + 各自消耗模式 +
   生效聚合口径），变过就标 `comparable = False` 并给 `reason` ——
   否则是把「换了算法」当成了「物资变化」。

日期类字段**可 `NULL` 且与 0 不同义**：`NULL` = 那天算不出来，`0` = 那天真的撑不了。
混起来会把「还没录数据」显示成**最坏结论**。

### 服务层 `services/survival_snapshot.py`（唯一实现）

```
take_snapshot(date?, note?, overwrite?)   落一份快照（同一天默认拒绝，overwrite 才是显式替换）
list_snapshots(limit?)                    **降序**（最近的在前）—— 给表格
get_trend(limit?)                         **升序** —— 给折线，附 delta + 对比 + series
get_snapshot(pk)                          单份（含类别明细）
delete_snapshot(pk)                       级联带走明细（明细脱离头没有意义）
```

⚠️ 两个读函数的顺序**刻意相反**：表格要「最近的在上」，折线要「从左到右按时间」。
同一个数组在两处用不同顺序，早晚会被后来者「顺手统一」成一个、然后**必然有一处显示反**。

⚠️ **命名冲突已避开**：`list_snapshots` / `delete_snapshot` 这两个名字**已被
`asset_service` 占用**（金融侧资产快照）。本次不覆盖、不改名，在 `services/__init__.py`
里用**别名导入**（`list_survival_snapshots` 等），视图直接 import 本模块而不走包级导入。

```
GET    /api/wealth/survival/snapshots/            历史列表（裸数组，**降序**）
POST   /api/wealth/survival/snapshots/            盘点一次 → 201；同一天重复 → 400 + 提示
GET    /api/wealth/survival/snapshots/{id}/       单份（含类别明细）
DELETE /api/wealth/survival/snapshots/{id}/       删除
PUT / PATCH  /api/wealth/survival/snapshots/{id}/ 405（刻意不提供修改）
GET    /api/wealth/survival/snapshots/trend/      趋势（**升序**）+ 对比 + series
```

列表端点 `pagination_class = None`（裸数组）；`trend` 不分页（点数由 `limit` 控制）。
`series` 里的空值**保持 `null`** —— 前端据此画断点，补 0 会画出一条「那天物资归零」的假线。

### 实盘盘点（v3.59.3）

⚠️ **与上面那个面板不是一回事，不要合并**：

| | 快照（`survival_snapshot`） | 实盘盘点（`survival_stocktake`） |
|---|---|---|
| 数据来源 | 系统算 | **人数出来** |
| 需要人动手 | 不需要 | 必须一件件数 |
| 回答 | 比上次是变长了还是变短了 | 实物与账面差多少 |

合在一起的后果是「点一下按钮就说自己盘过了」—— 那是**假盘点**，
而且会把历史记录的证据价值一并毁掉：记录还在，但它证明不了任何事。

迁移 `wealth/0021_survival_stocktake`（**已生成、未执行**）

| 表 | 作用 | 关键点 |
|---|---|---|
| `wealth_survival_stocktake` | 盘点**头** | **刻意没有** `UniqueConstraint(user_id, date)` —— 与快照「一天一点」相反，盘点**可以分批** |
| `wealth_survival_stocktake_line` | 明细 | `stocktake` 用 `CASCADE`；`item` 用 `SET_NULL`；`item_name`/`category_name`/`unit_name` 冗余留存 |

四条铁律：

1. **账面数量由服务端在提交那一刻读，不信前端传的。**
   入参序列化器 `SurvivalStocktakeLineWriteSerializer` **刻意没有** `book_quantity` 字段。
   初看像防篡改，其实是防一个**必然发生**的过期读：盘点页可能开着半小时，
   其间库存在别处已经改过，用前端那个数会把「盘点期间的变化」算进盘盈盘亏。
   服务层在 `transaction.atomic()` 里 `select_for_update()` 锁住这批物品后再读 `item.quantity`。
2. **提交即校准。** 库存直接改成实盘数。否则「我数过了」只留下一张纸，账还是错的。
   代价是界面必须把这句话写在按钮上方、确认框再说一次 —— 它是改账的动作。
3. **删除记录不回滚库存。** 库存已经是**被核实过的事实**，删记录只是删掉凭据。
   若删一条历史能把库存静默改回去，「删记录」就成了一个**能改现状、
   却在界面上看起来只影响历史**的按钮。要改数量请去编辑物品。
4. **`book_quantity` 落库、`delta` 不落库。** 看着矛盾，其实是「以后重算得出同样结果吗」的两侧：
   账面与实盘都在表里，一减就有 ⇒ `delta` / `delta_kind` / 四个计数都不落库；
   而「盘点那一刻账上有多少」在库存被校准之后**永久消失** ⇒ 必须落库。

```python
# services/survival_stocktake.py（唯一实现）
get_worksheet(category_id?, item_ids?, keyword?)   # 工作表：账面 + 上次盘点 + 该不该盘 + 补货线
create_stocktake(stocktake_date?, note?, lines, source?)  # 提交即校准，返回头 + 明细
list_stocktakes(limit?)                            # **降序**（最近一次在最上面）—— 给表格
get_stocktake(pk)                                  # 单次（含明细）
delete_stocktake(pk)                               # **不回滚库存**
delta_kind(book, actual) -> surplus / deficit / flat
```

```
GET    /api/wealth/survival/stocktakes/worksheet/       工作表（三个可选参数可组合）
GET    /api/wealth/survival/stocktakes/                 历史（裸数组，**降序**，**带明细**）
POST   /api/wealth/survival/stocktakes/                 提交一次 → 201
GET    /api/wealth/survival/stocktakes/{id}/            单次（含明细）
DELETE /api/wealth/survival/stocktakes/{id}/            删除记录（不回滚库存）
PUT / PATCH  /api/wealth/survival/stocktakes/{id}/      405（刻意不提供修改）
```

三处约定：

- `item_ids` 传空串或写坏时**当成不按 id 过滤**（而不是「一件都不选」）——
  否则参数写错会伪装成「你的清单是空的」
- 盘点列表**带明细**，与快照列表「刻意不带明细」相反。判据不同：快照的明细是另一个维度
  （各类别的结论），列表只要读数就够；而盘点的明细**就是内容本身** ——
  只给「盘了 12 项、3 盈 2 亏」，还得再点一次才知道是哪三件，等于把唯一的答案藏起来
- `PUT` / `PATCH` 一律 `405`：可编辑的盘点记录等于伪造的核对结果

⚠️ 归口方向：`list_snapshots` / `delete_snapshot` 那两个名字**已被 `asset_service` 占用**
（金融侧资产快照），本轮新增的 `list_stocktakes` / `delete_stocktake` 无冲突，
但同名的 `_row` 构造器一律加模块内私有前缀。新增读函数前先搜一遍**有没有同名**。

### 库存流水（v3.60.18 · P0）

上面三张表各答一件事，**第四张才答「库存怎么变的」**（三张表刻意不合并 ——
合并后「这 2 罐是被我吃了，还是被脚本改了」再也分不出来）：

| 表 | 回答什么 | 谁动手 |
|---|---|---|
| `wealth_survival_snapshot` | 系统算出来的**结论**（我以为能撑多久） | 不用人动手 |
| `wealth_survival_stocktake` | 人**核对过**（账面 vs 实盘） | 必须人动手 |
| `wealth_survival_flow` | 库存**怎么变的**（连续流水） | 人登记 / 系统代记 |

迁移 `wealth/0027_survival_flow`（**已生成、未执行**）

四条铁律：

1. 🔴 **改库存只有一个写口：`record_flow()`。** 任何绕过它的库存写入
   （ViewSet 直接 `save()`、脚本、后台、以后新加的编辑入口）都会造出**无痕变化** ——
   库存少了 2 件、流水里却没有这一笔，而界面看起来完全正常。所以三处既有入口都改了：

   | 入口 | 落法 |
   |---|---|
   | `create_item` | 先建 `quantity=0` 再 `record_flow(初始值, channel='create')`；初始 0 **不记** |
   | `update_item` | 数量单独摘出 → `record_flow(delta, channel='edit')`，其余字段照常 `setattr` |
   | `create_stocktake` | `delta = actual − book`，`delta != 0` 才记（实盘 == 账面**不记**） |

   ⚠️ **加/改任何表单里的「数量」字段，都要回到这张表上加一行** —— 漏了不报错，只静默少一条流水。

2. **写流水与改库存同一事务**，且 `select_for_update()` 锁物品。否则出现「流水说有、账上没有」。
3. **不做物理删除，只做「撤销」**（`reverse_flow()` 补一条反向流水，`reverses` 指回原笔）。
   账正回来、历史全留；**一条流水最多被冲销一次**（拒「冲销记录本身 / 已撤销 / 物品已删」）。
4. **流表不存 `quantity_after`** —— 存量列不许进流表（§49 的账）。要展示「3 → 2」用当前
   `quantity` 反推一次即可（纯展示、不落库）。

**渠道与原因正交**（渠道答「谁写的」，原因答「为什么」），别合并：

```
channels  manual / stocktake / shelter / edit / create / import
reasons   eat / use / broken / expired / discard / gift / buy / receive / correct / revert / other
         原因留空时后端按类别 consume_mode 预填（meal → eat，其余 → use），**只在负 delta** ——
         正 delta 不猜；前端**不复制这张映射表**（那是第二份口径）
```

```python
# services/survival_flow.py（唯一实现）
record_flow(item_id, delta, channel='manual', reason='', note='', occurred_at=None, reverses=None)
reverse_flow(flow_id)                    # 补反向流水；一条最多冲销一次
record_batch(rows, occurred_at=None)     # 整批一个事务：任一变负则**全不写**
list_flows(...)                          # 裸数组；item_id / category_name / channel / reason / 日期段 / keyword
summarize_flows(month=None)              # 按月，**按单位分桶**，跨单位不相加
_month_range(month)                      # → [月初, 下月初) 的 **aware datetime**
```

```
GET  /api/wealth/survival/flows/                    流水列表（**裸数组**，新的在前；支持筛选）
POST /api/wealth/survival/flows/                    记一笔（单笔 `{item_id, delta, ...}`；批量 `{rows:[...]}`）→ 201
POST /api/wealth/survival/flows/{id}/reverse/       撤销 → 补一条反向流水
GET  /api/wealth/survival/flows/summary/            按月汇总（`?month=YYYY-MM`）
```

三处约定：

- 列表端点 `pagination_class = None`（裸数组）；`summary` 写成 `detail=False` 的 action，
  **不被 `<pk>` 抢**（被抢的症状是 404，像路由没注册）
- `delta = 0` 拒绝、改完 `< 0` 拒绝且**不夹到 0**（夹 0 会造出「账对了、事没了」的假象）；
  `occurred_at` 可以是过去、**不许是未来**
- `_month_range` 必须返回 **aware datetime**：拿 `date` 去过滤 datetime 字段时，
  Django 会把它摊成当天午夜的 **naive** datetime 再按当前时区猜一次 ——
  既报 `RuntimeWarning`，也让「按哪个时区算月界」变成隐式约定（同 `wealth_bill_list.date` 那一类）。
  **判据用例钉在类型上**（`timezone.is_aware(start)`）

### 必需品基准清单与缺口对账（v3.59.7，P3-A 七期）

**天数答不了「我漏了什么」** —— 没录入的东西不在分母里，就不构成缺口。实测原状：
「用」类底下只录了 2 件（纸巾、洗脸巾），牙膏、洗发水、卫生纸、洗衣液从来没进过系统，
而短板照样理直气壮地判在「吃」上。本期补的就是这把尺子。

两条口径修正：

1. **「用」类聚合口径 `sum` → `min`**。判据是**可替代性**：「米粉与面条都能当一顿饭」
   属可替代（求和）；「牙膏用完了，洗发水囤再多也刷不了牙」属并列缺一不可（取最小）。
   用 `sum` 的后果是**静默**的 —— 一件洗脸巾折算 45,000 天就能把整类撑到 45,050 天，
   数字看着完全合理，没人会去查。
2. **新开「医药」类别**（`consume_mode=on_demand` / `aggregate_mode=min`）。药品不按消耗
   速率算，而是「有没有、过没过期」；混进「用」里会与洗衣液、垃圾袋共用同一套聚合，
   把「缺一盒创可贴」稀释成「这一类还够撑很久」。单开一类才能用「取最小」，
   并让有效期封顶（`expiry_cap_days`）说了算。

**基准清单是一张表，不是一份常量**（`wealth_survival_essential`，见上面的表清单）：

- 与 `SurvivalItem`（「实际有多少」）是**两件事，刻意分开存**，接口也是两条路径 ——
  合并后「我漏了牙膏」会被读成「牙膏数量是 0」。
- 🔴 **为什么不是给物品加一个 `is_essential` 开关**：开关加在**物品**上就永远表达不了
  「这东西根本没录入」—— 物品不存在时那个开关也不存在，而「漏了」恰恰是本表要抓的主要缺口。
  开关只会回答「我录的里面哪些重要」。
- **表不存任何派生值**（覆盖天数、档位都不落库）：库存或用量一改就陈旧，
  而陈旧的分档比没有分档更糟 —— 它看起来是对的。
- 关联物品是**多对多**（v3.59.12，原为单个 FK）：删掉一件物品时中间表的行跟着没，
  基准项自动回到「未录入」—— 这正是要的语义。判据与旧版的 `SET_NULL` 相同：
  删一件物品不该连带删掉「我本该有牙膏」这条认知（同快照明细判据：
  删除保护只管当下的引用，不管认知）。详细推导见下「十二期」。
- `UniqueConstraint(user_id, name)` 走 `Meta.constraints` ⇒ **DRF 不自动校验，必须手写
  `validate()`**（硬坑 6）。

**缺口五档**（分档**只在后端做一次**，前端只按返回的 `level` 上色、不重算）：

| level | 含义 | 覆盖天数 | 该做什么 |
|---|---|---|---|
| `missing` | 没关联物品（或关联的物品已被删） | — | 去录入，或确认自己根本用不着（那就删掉这项） |
| `unknown` | 物品在但算不出（用量口径没填、已过期） | — | 去补口径 / 去换新的 |
| `critical` | 告急 | < 30 | 该补货了 |
| `tight` | 偏紧 | 30 ~ 90 | 记着，可以开始留意 |
| `adequate` | 充足 | ≥ 90 | 不用管 |

⚠️ `missing` 与 `unknown` **必须分开**：一个要去录入、一个要去补口径；一律渲染成
「算不出来」会把「还没录数据」说成「配置出错」，令人去改一个本来没坏的东西。
阈值真源 `SURVIVAL_ESSENTIAL_LEVEL_FLOORS`（唯一一处）。

⚠️ **「核心项没录全」是独立的可信度信号，不是天数**：`summarize_essentials()` 给
`unclosed_core` / `unclosed_core_count` / `complete`，**不折算进综合天数** ——
把「还没录」显示成「只够撑 0 天」是另一个错误（0 是「真的撑不了」的**结论**）。

⚠️ **`seed_essentials` 必须先建类别**：种子里的类别是按**名字**查的，查不到就跳过并计入
`missing_categories`（凭空建类别会绕过「不预设用户的分类结构」那条判据）；顺序反了整份清单
会全跳过，而失败长相只是 `created: 0`，看着像「本来就没事可做」。接口与前端都会把跳过的
类别**说出来**。整段 `@transaction.atomic`：中途失败留下半份清单比完全没有更容易误导。

### 衣物口径与录入参考（v3.59.8，P3-A 八期）

**「穿」是「用」那处病根的第二个病例，而且这一例更不容易被发现。**

只读查库复现原状（3 条记录、共 8 件，**全是睡衣**）：

| 物品 | 数量 | 单件天数 | 小计 |
|---|---|---|---|
| 冬季睡衣 | 3 件 | 1095 | 3285 天 |
| 睡衣（无袖套装） | 3 件 | 1095 | 3285 天 |
| 睡裙 | 2 件 | 1095 | 2190 天 |
| **sum 聚合** | | | **8760 天 = 24.0 年** |

PERT 期望 8788 天 = **24.1 年**、离散度 701.9 天 —— 与四卡上那个数字一字不差。
而内裤、袜子、外衣、鞋**一件都没录**。

两层错各自独立，缺一不可：

1. **数值层**：`aggregate_mode` 由 `sum` 改成 `min`。判据与「用」同一条 ——
   类内几件是**可替代**还是**并列缺一不可**。「米粉与面条都能当一顿饭」属可替代（求和）；
   「袜子破了，大衣囤再多也解决不了穿什么出门」属并列（取最小）。衣物是后者。
   改后 24.0 年 → **6.0 年**。
2. **认知层**：分母里全是睡衣 —— 由 v3.59.7 的基准清单管（穿类内置内裤 / 袜子 /
   外衣 / 鞋 / 睡衣五项，对账卡会点名「未录入」）。但**类别四卡那个数字仍然会被读成
   「我的衣服够穿 24 年」**，所以第 1 层非改不可。

**第三层是本期新增的语义修正：「一件还能穿多久」不是常量。**

同一件纯棉 T 恤，只求「遮体保暖」可以穿 5 年，要求「体面、不起球、不褪色」约 1.5 年 ——
差三倍以上，**而且两个答案都不算错**。系统原先把 `days_per_unit=1095` 当客观事实，
其实那只是用户在某一种标准下拍的数。两处落点：

- `SURVIVAL_METRIC_NOTES['life_days']` 显式声明：填的是**你接受的标准**，不是衣服的固有属性；
  并补一句「衣物按次比按天可比 —— 次数说的是『还能穿几次』，天数隐含了一个穿着频次」。
- `SURVIVAL_WEAR_REFERENCE`（新增常量，10 类常见衣物）：只在**录入弹窗**里当锚点。

🔴 **参考表不进算法。** 它是「别人一般填多少」，不是这件物品的参数；混进计算就等于
给所有衣物套一个统一寿命 —— **那恰恰是这次要修的错**。三条硬约束：

| 约束 | 为什么 |
|---|---|
| **不预填、不兜底** | 没填口径就是「算不出来」；让参考值顶上会给出一个「看着合理」的天数，比报错难查得多（用例 `test_reference_never_fills_in_a_missing_value`） |
| **不按名称自动写值** | 只在用户**显式点按钮**时才写进表单；自动填会制造「我没动过它却变了」的账 |
| **两列不互相换算** | `uses_*`（可穿次数）与 `days_*`（可用天数）不是同一把尺子：次数与穿法无关、跨人可比；天数隐含了一个穿着频次。拿天数反推次数会得到一个没人核对过的假设 |

**衣物的五个寿命变量，系统支持两个**（其余属录入口径，不是算法能算的）：

| 变量 | 落点 |
|---|---|
| 穿着频次 | ✅ 按次三字段（`uses_per_unit` + 「每 X 天/周/月穿 Y 次」） |
| 轮换穿着 | ✅ **数量字段**。3 件轮换填数量 3，总覆盖确实是单件的 3 倍 —— 轮换与「接续」在**总日历覆盖上等价**，所以原口径这一处是对的，不必改 |
| 材质 / 洗涤方式 | ⚠️ 影响**标称次数**，属录入口径 |
| 体重变化 | ⚠️ 不可建模的「非物理报废」，只能靠状态 / 数量手工修正 |

⚠️ **本期明确不做「穿着次数计数器」**：内裤袜子是成批轮换，逐件记次数要每天手工维护，
实际上会被放弃 —— 落一个每天要点一次的按钮，比不做更糟。

### 结论条口径（v3.59.10，P3-A 九期）

前端做了一轮排版 / 交互审视，后端这边只补了一条**缺失的口径键**：

**「钱能撑多久」此前没有可挂的口径。** `SURVIVAL_METRIC_NOTES` 里有
`pert_expected`（综合能撑）、`bottleneck`、`coverage`，而「钱能撑」只在
`bottleneck` 的 note 里被顺带提过一句 —— 于是结论条上四个数里，唯独这一个
没有可解释的落点。补 `SURVIVAL_METRIC_NOTES['cash_days']`。

🔴 **公式里刻意不写分子那半段**（现金类资产 ÷ 近 12 月 PERT 月支出）：
那一段归资产健康指标管，写在这里就是第二份口径，改那边时必然漏改。
本条的 `formula` 只说 `应急金月数 × 30` —— 那是本模块**唯一**属于自己的换算。

⚠️ 公式与算法不许漂移：`test_survival_banner_meta.py` 直接断言
`cash_days_from_months(2.0) == 60.0`，并核对文案里写的倍数。
⚠️ 前端 `bannerMeta(key)` 取不到时是**静默不渲染**气泡（不是渲染一个空的），
所以键名写错在界面上完全看不出来 —— 同一份用例里有一份 `BANNER_KEYS`
名单，把结论条要挂的四个键与文案钉在一起。

### 保存前试算（v3.59.11，P3-A 十一期）

**起因**：洗脸巾「数量 300 抽 + 一份能用几次 300 + 每 1 天用 2 次」，页面报 123.7 年。

算法没错 —— `300 × 300 × (1 ÷ 2) = 45,000 天`，PERT 期望 45,144.2 天 = 123.7 年，
与页面逐位一致。错在**同一个 300 被填了两遍**：
一次是「我有 300 抽」，一次是「一份里有 300 抽」。
而表单从来没把这两个数**乘出来**给人看过 —— 中间量「一份可用 150 天」
完全正常，错在最后一跳（乘以 300）。

**接口**：`POST /api/wealth/survival/items/preview/`（`detail=False` 的 action）

请求体与**新增物品完全一样**；返回体与明细表那一行**同形**
（`SurvivalItemPreviewSerializer` 继承 `SurvivalItemLifeSerializer`，只把
`item_id` 放开为可空）。它**不写库**。

🔴 **四条刻意约定**：

1. **不写第二份公式。** 服务层造一个只活在内存里的物品
   （`SimpleNamespace` + `_PREVIEW_DEFAULTS`），交给 `compute_item_life` 算 ——
   与保存后列表跑的是**同一行代码**。前端自己乘一遍确实更快，
   但那会得到第二份公式，而两份公式迟早分叉、**分叉是静默的**：
   试算说 150 天、保存后写着 123.7 年，两边都像个正常的数。
2. **校验复用同一个表单序列化器。** 试算放行、一按保存报 400，
   比没有试算更误导 —— 它先把人哄住了。
3. **`_PREVIEW_DEFAULTS` 是按「`compute_item_life` 读什么给什么」逐个对齐的。**
   少给一个属性不是「按缺省算」而是 `AttributeError`，
   且只会在某条从没被点过的分支上炸。
4. **配餐类直接拒绝**（400）。那类物品的时长由配方决定，
   按单件口径算出来的是一个没人核对过的数 —— 而它看着完全合理。

⚠️ 试算是**护栏不是闸门**：前端在它失败时只降级成一句「试算暂时不可用
（不影响保存）」，绝不阻断保存。

**用例**（`tests/test_survival_item_preview.py`，12 条）钉死的东西：
① **试算的数 == 保存后的数**（两条路径都走接口，不是「都调了同一个函数」）；
② 本案 300 × 300 → 45,144.2 天、改成 1 → 150.5 天；
③ 试算不写库、`item_id` 恒为 null；
④ 校验与 `create` 一致（`use_times=0` 与跨类别单位两边都 400）；
⑤ 没填口径返回 `None` + `no_days_per_unit`，**不是 0 天**；
⑥ 配餐类返回 400 且文案里点明「配方」。

### 一条基准项挂多件物品（v3.59.12，P3-A 十二期）

原状是**单个外键**，逼用户在「夏季睡衣」和「冬季睡衣」里二选一 ——
无论选哪件都答不对「睡衣还能撑多久」：冬天还是没得穿。

**判据与类别口径同源**（可替代才求和，并列缺一不可就取最小）：

| 关系 | 例子 | 口径 |
|---|---|---|
| 并列缺一不可 | 夏 / 秋 / 冬睡衣、日用 / 夜用卫生巾、室内 / 室外鞋 | **取最小** |
| 可替代 | 矿泉水 + 纯净水（同类同用） | 求和 |

⚠️ 组内**一律取最小**，本轮不做逐项开关（用户拍板）。方向是**刻意选的保守**：
算错成「虚报缺口」，用户在界面上看得见并会去核实；反过来求和错了是「掩盖缺口」，
静默且危险 —— 「用」类曾被一件洗脸巾撑到 4.5 万天，而牙膏剩 5 天没人看见。

🔴 **三档是逐档取最小**，不是「挑出最短那件、再抄它的三档」——
一件有到期日封顶、另一件没有时两条曲线会**交叉**：

```
A 无到期日，base 100      → 125 / 100 / 76.9
B 90 天后过期，base 200   → 被保质期压成 90 / 90 / 90
逐档取最小  → 90 / 90 / 76.9    （乐观档来自 B、悲观档来自 A）
抄最短那件（B）→ 90 / 90 / 90   ← 漏掉 A 的悲观档 76.9
```

⚠️ **只要一件算不出，整条报 `unknown`**，`expected` 也回到 `None` ——
不拿部分数据充完整答案。把「有一件还没填口径」说成「另外两件能撑 300 天」，
用户看到 300 天就不会去补那一件了。
`issues` 里带上**是哪几件、为什么**（复用 `compute_item_life` 已有的 `item=` 标注）。

⚠️ **顶层 `item_*` 字段的含义变了**：现在是**代表件**（正常用量下最短的那件），
不再是「唯一那件」。`find_essential_shortest` 用的就是这个代表件的名字。
逐件明细在 `items[]` 里，顺序由后端定（最短在前、算不出的最后）——
有数字的是**结论**、算不出的是**待办**，不该混在一起排。

⚠️ **空数组 ≠ 不传**（`update_essential`）：空数组是「把勾选全取消了」，
不传是「这次不动它」。写成 `if item_ids:` 会让前者退化成后者 ——
界面看着清空了、刷新又回来。

⚠️ **重复 id 必须在服务层与序列化器各收敛一次**：中间表上有
`UNIQUE(survivalessential_id, survivalitem_id)`，重复项会以 `IntegrityError`
崩在事务里，而界面上只剩一句兜底的「保存失败」—— 看不出是「同一件勾了两遍」
（同硬坑 6：不落在模型 `unique=True` 上的约束，DRF 不自动校验）。

**用例**（`tests/test_survival_essential_multi.py`，23 条）里最关键的几条：
① 三件睡衣取**最短**、给最长那件加 100 倍库存后**结论不动**（反求和的可观测形式）；
② 逐档取最小 ≠ 抄最短那件（上面那个交叉构造）；
③ 一件算不出 ⇒ 整条 `unknown` 且 `expected is None`；
④ 重复 id 走接口仍是 201；⑤ 空列表清空、不传保持不动。

### 组合配置（v3.59.13，P3-A 十三期）

「燕麦米 / 绿豆 / 薏仁 / 紫米是**分开登记**的（各自算数量、各自算保质期），
但烹饪时**一起下锅**。」登记与「一起用」是两件事 —— 组合只管后者。

**组合在配方里占一行**，不展开成 N 行：

| 做法 | 判据 |
|---|---|
| 展开成 4 行 | ❌ 挂主食位时与一行**数学等价**（`min-of-min = min`，`TestComboEqualsExpansion` 钉住）；等价的东西展开只买到坏处：列表膨胀、「这四件是一锅的」这个事实消失、**改组合时已展开的行不会跟着改 ⇒ 静默分叉** |
| 组合自带倍率 | ❌ 就是「两个数相乘」的形状（见 v3.59.11 那份 45,000 天） |
| 嵌套 | ❌ 本轮不做 |
| **一行 + 组内取最小** | ✅ |

口径（`calc.compute_combo_line`，唯一实现）：

- 组内**取最小**（并列缺一不可，与必配位同一条判据）；`expire_cap_days = min(各件封顶)`
- `bottleneck_item` = **组内最先耗尽的那件物品**，不是组合名 —— 缺口必须点到具体物品
- 组内任一件算不出 ⇒ **整行 `None`**，逐件 `issues` 原样收进这一行；**不静默跳过**
  （漏一项分母会让这道菜算得更耐吃）
- 组内为空 ⇒ `ISSUE_EMPTY_COMBO`
- ⚠️ `used_item_ids` 必须收 `member['item_id']`，否则「只通过组合下锅」的物品会被全误报成「白存」

🔴 **聚合键必须是 `line_key`（`item-3` / `combo-1`），不能是裸 `id`**：
两类配方行来自**两张表**，id 空间会撞号，撞了就**静默合并两条行**。

**为什么另起一张表**（`wealth_survival_recipe_combo_line`）而不是把
`SurvivalRecipeLine.item` 改可空 + 加一个 `combo` 外键做「二选一」：
既有的 `wealth_survival_recipe_line` **一个字节都没动**，存量数据与既有用例零风险。

**餐位只在配方行上**（`SurvivalRecipeComboLine.role`）—— 组合本体**不存餐位**：
同一锅粥在早餐配方里可能是必配位、在别处可能是主食位。

**空数组 ≠ 不传**：`create_recipe` / `update_recipe` 里 `lines` 与 `combo_lines`
**各自独立判 `is not None`** —— 只传 `lines` 时组合行原样留着。
「至少一样主食」**两条线一起判**：只看 `lines` 的话，「只挂组合」的配方会被放过去、
然后算出个空值。

**服务层 `services/survival_combo_service.py`**：
`_members` 四道校验（空成员拒绝 / 去重 / 同类别 / 用量 > 0）；
`delete_combo` 被配方引用 → `ValueError` → 400；
提交的 `combo_lines` 会**静默去重**（同一个组合挂两次与挂一次结果相同 ——
报错只会让人觉得系统在挑刺）。

**一件物品只能挂一处**（同一版修掉的干扰源）：
`SurvivalEssentialFormSerializer.validate_item_ids` 硬拒（`exclude(pk=instance.pk)`，
否则编辑自己时连「保留已勾」都会被拒），`survival_essential_service._assert_items_unclaimed`
服务层再判一次 —— 序列化器挡 HTTP 面，服务层挡脚本调用方。
前端候选列表同步去掉已挂在别处的物品，并**保住自己已勾的那几件**
（否则取消勾选都点不到）。

**用例**（`tests/test_survival_combo.py`，35 条）：组内取最小与短板落点、
组合版与展开版 `meals` 等价、缺件点名到物品、空组合、跨类别与重复成员被拒、
被引用删除 400、配方两类行独立提交、只挂组合不算孤儿。

### 待用户手动执行

```bash
cd backend && ../.venv/bin/python manage.py migrate wealth
```

迁移 `wealth/0001` ~ `wealth/0024` **已全部在开发库应用**（用户手动执行）；
**v3.59.9 / v3.59.10 / v3.59.11 均无新迁移** ——
这三期只改展示层、常量与文案，没有新表、没有新列。
（试算端点也是零迁移：它复用了既有的 `SurvivalItemFormSerializer`。）

✅ **`wealth/0024`（v3.59.12）已应用** —— 只读回查（2026-09-22）：

| 项 | 现状 |
|---|---|
| `wealth_survival_essential_items` 中间表 | **已存在** |
| `wealth_survival_essential.item_id` 旧列 | **已删** |
| 基准项总数 / 已挂关联 | **20 条 / 17 条** |

⇒ 关联已由 `RunPython` 搬进新表，无丢失。另：**当前没有任何一件物品被挂在两处**
（「一件只能挂一处」的新校验不会拦下存量行）。

🔴 **`wealth/0025`（v3.59.13，组合配置）还没应用** —— 只读回查（2026-09-22）：

| 项 | 现状 |
|---|---|
| `wealth_survival_combo` / `_combo_item` / `_recipe_combo_line` | **三张表都不存在** |
| 最新已应用迁移 | `0024_survival_essential_items` |

⇒ 跑 `migrate wealth` 时只建这三张空表，**不动任何既有表、不动任何行**。

🔴 **但「口径」是数据，不是常量。** 所以「代码升级了」不等于「口径跟着变了」。
开发库只读回查（2026-09-22）：

| 项 | 现状 |
|---|---|
| `wealth_survival_essential` 表 | 已建 |
| 类别 | 仍是 **4** 个（**无「医药」**） |
| 「穿」/「用」的 `aggregate_mode` | 仍是 **`sum`** |

⇒ 四卡上的「穿 24.1 年」**不会**因为升级而变，还要在页面上走两步：

1. 页头「**初始化默认类别**」→ 首次会建出 5 个类别（含医药）；类别已存在时会弹一次
   「覆盖类别口径」确认 —— **要点「覆盖」**，「穿」「用」才会从求和改成取最小；
2. 缺口对账卡里的「**初始化基准清单**」→ 写入 29 项基准项（缺类别时被跳过的项会列出来，
   不静默略过）。

不跑第 1 步的后果：「医药」类基准项**全被跳过**（对账卡会指明是哪几类缺失），
且「穿」「用」仍按求和算 —— 短板判断与修正前**完全一样**。

测试库结构由 `backend/conftest.py` 的 session 级镜像 DDL 保证
（DDL 与 `sqlmigrate wealth 0019` / `0020` / `0021` / `0023` / `0024` / `0025` 输出逐字对齐）。

⚠️ `0024` 的中间表是本项目**第一张由 Django 自动创建的表**（没有显式 through 模型）：
表名 `wealth_survival_essential_items` 与列名 `survivalessential_id` /
`survivalitem_id` 都是 Django 按规则拼出来的，**不能凭印象写** ——
照样得照抄 `sqlmigrate` 的输出。⚠️ 它的主键是 `bigint`，而其它表都是 `integer`。
⚠️ 它必须排在 `wealth_survival_essential` 与 `wealth_survival_item` **都建好之后**，
否则建表直接失败（两个外键分别指向那两张表）。

⚠️ `--reuse-db` 下 `CREATE TABLE IF NOT EXISTS` **对已存在的表既加不上列、也改不了列定义** ——
0021 给 `wealth_survival_item` 加的 6 列要靠 `_patch_survival_item_columns()`
用 `information_schema` 探一遍、只补缺的；0022 把 `use_cycle_*` 三列放宽为可空，
靠同一个函数查 `IS_NULLABLE`、只把还是 `NO` 的列 `MODIFY` 一次（幂等、非破坏）。
漏了后半步，测试库仍停在 `NOT NULL`，新用例会以**与线上一样的 500** 失败 ——
看起来像代码没改对，其实是环境没跟上。
手写 `ALTER` 补列会让下一次全量重建的表结构与迁移漂移，**别走这条路**。

（`wealth/0016` ~ `wealth/0018` 也已随那一次 `migrate wealth` 一并应用完毕。）

### 未做（明确留给后续）

- **三期**：从账单 / 时间记录反推真实消耗率；把「该补货」接进 `Notification`
  （现在 `restock_threshold` 只在清单上标一个标记，不会提醒）
- **物与钱的联合推演**：现在两腿各自给数（物能撑多少天 / 钱能撑多少天），
  未做「谁先断」的联动判定
- **快照导出**：历史目前只能在页面看，未提供 CSV 导出
- **盘点趋势图**：`list_stocktakes` 只有降序一个出口。将来要做图**另开升序函数**，
  **不要**把这条改成升序 —— 那会让表格反过来（同快照 `get_trend` 的处置）
- **自动盘点**：`SURVIVAL_SNAPSHOT_SOURCES` 与 `SURVIVAL_STOCKTAKE_SOURCES`
  目前都只有 `manual`。枚举位已留、逻辑未写 ——
  做之前要先想清楚：自动生成的那一份**不可编辑**、库存还会被直接校准，
  必须明确失败时的处理，否则会造出一批改不掉的假历史 + 被悄悄改坏的库存
- 数字类（书）**不重复建模书单**：只建「物品行」表达可消费时长；
  若要读已有 `book` app 数据，三期再做只读聚合
- **必需品缺口接进 `Notification`**（v3.59.7）：现在只在面板上显示，不会主动提醒。
  做时要分「核心项未闭合」与「已告急」两类 —— 合成一个「物资告警」会让人分不清
  该去补数据还是该去补货
- **「这条基准项该有几件」**（v3.59.12 明确没做）：多选让用户能挂夏 / 秋 / 冬三件睡衣，
  但只挂一件时系统**分不出来** —— 它算出的天数只看那一件，看不出你挂少了。
  要抓这一类缺口，得先让用户填一个「应有件数」（留空 = 不限），
  再在对账里点名「还差 N 件」。本轮按用户拍板不做。
- **组合不嵌套**（v3.59.13）：嵌套会让「组内取最小」变成递归 + 防环，本轮不做
- **组合行没有倍率**（v3.59.13）：要加量就改组内那一件的用量 —— 刻意不引入「份数」，
  形状与 v3.59.11 那个 45,000 天完全相同
- **按基准项反向建物品**（v3.59.7）：本轮只做「关联到已有物品」，未做「按基准项一键建出物品」
- **`quantity` × `uses_per_unit` 的量纲重复校验**（v3.59.7 记录 → v3.59.11 部分落地）：
  一件物品若同时填「一份可用 N 次」与「库存 M 抽」，语义会被重复计算成 M×N
  （实测把洗脸巾算成 45,000 天 = 123.7 年）。
  **v3.59.11 已处理的是根因与可见性**：① 标签绑定数量单位（`每抽能用几次`），
  「一份」不再有第二种解释；② 保存前试算把最终天数摆在眼前。
  **仍未做的**是那条**启发式交叉提示**（数量与一份次数填了同一个数时指名道姓地提醒）——
  它在极少数正当填法下会误报，且试算已经把两个数并排念出来了。
  🔴 无论做哪一版，**都不替用户改存量数据**。
- **物品类别可迁移的闸**（沿用 §26.6 / §27.7 的待办）：给 `update_item` 补
  「被配方引用则拒绝改类别」


---

## 物件资产（v3.60.0，P4-A 一期；v3.60.1 订正净值口径）

耐用品台账：冰箱 / 空调 / 床 / 柜子。判据一句话：
**纸巾会被用完 → 生存资源；冰箱会被用坏 → 物件资产。**

| 盘什么 | 表前缀 | 单位 | 判据 |
|---|---|---|---|
| 钱 | `WealthAsset*` | 元 | 账上有多少、在哪 |
| 消耗物 | `Survival*` | 天 | 会被用完 |
| **耐用品** | `WealthProperty*` | 年 / 元 | **会被用坏** |

前缀与路径全线避让：表 `wealth_property_*`、类 `WealthProperty*`、
接口 `/api/wealth/property/*` —— 与「资产盘点」（`/wealth/cashflow` 里的
`asset/snapshots`）**刻意分开命名**：那条是钱的去向，这条是家里那台冰箱。

### 数据模型（2 张 managed 表，一段迁移 `wealth/0026_property`）

| 表 | 关键点 |
|---|---|
| `wealth_property_category` | 轻量主数据，用户可增删改；唯一键 `(user_id, name)`；`default_lifespan_months` 可空，**仅作表单预填、绝不兜底** |
| `wealth_property` | 物件本体；FK `category` 用 **`PROTECT`**；索引显式命名 `wealth_prop_user_cat_idx` / `wealth_prop_status_idx` |

⚠️ `condition` 是 MySQL 保留字（建表语句里带反引号）。
⚠️ `conftest.py` 已同步两条 `CREATE TABLE IF NOT EXISTS`，DDL 与
`sqlmigrate wealth 0026` 输出**逐字对齐**（主键 `integer`、FK 名
`wealth_property_category_id_7d927051_fk_wealth_pr`），类别表排在物件表**之前**（FK 依赖）。

### 算法真源 `services/property_calc.py`（唯一实现）

一、**主产出是「已用月数 vs 计划月数」，净值只是附带**。
   净值不涂色、不做健康度评分；超期只做**中性标注**（「用超了」是事实，不是错误）。

二、**净值在报废那刻定格**。
   在用 / 闲置按「今天」算（它还在折旧）；已报废按**报废那天**算。
   报废却没填日期 → `null` + `NO_SCRAP_DATE`（不兜底成今天 —— 那等于假装它今天才报废）。

三、**算不出来就说算不出来**。
   缺金额 / 缺日期 / 缺年限 / 购买日在未来 → `null` + issues，**不返回 0**。
   0 是「真的折完了」的结论，跟「算不出来」不是一回事（净值截断到 0，不出现负值）。

四、**年限只在一个地方换算**。
   `years_to_months()` 是后端唯一入口；界面按年填（支持小数，8.5 = 8 年 6 月），库里按月存。

五、**状况是「损坏」⇒ 净值归 0**（⚠️ 2026-09-26 订正，见 §口径纠偏）。
   坏了就不值钱 —— 这一跳**压过**折旧，且**不看**金额 / 年限 / 日期
   （「坏了不值钱」独立成立，所以缺哪格都照样是 `0.00` 而不是 `None`）。
   它只改净值一项：件数 / 原值 / 已用 / 计划 / 超期 / 月折旧**一概不动**。
   净值为 0 的两个来源由 `zero_reason` 区分（`depreciated` 已折完 / `broken` 损坏归 0）。

🔴 **派生值一律不落库**（净值 / 已用月数 / 剩余月数 / 月折旧 / 五项合计）。
   判据「以后重算得出同样结果吗」→ 能，所以不落库。

### 合计口径（`summarize`）

四卡：在用件数 / 原值合计 / 在用净值合计 / 已报废。两个合计块各带**四个数**，
净值块再多一个 `broken_count`：

| 字段 | 含义 | 出现在哪一块 |
|---|---|---|
| `total` | 合计 | 两块 |
| `counted` | 计入件数 | 两块 |
| `unpriced_count` | 没填金额（连原值都没有）的件数 | 两块 |
| `unvalued_count` | 填了金额却算不出净值的件数（缺日期 / 缺年限 / 日期在未来） | 两块 |
| `broken_count` | 因状况=损坏而按 0 计的件数（**仍计入 `counted`**） | **只有净值块** |

- **原值合计含已报废**：那是「一共投进去多少钱」的历史总投入，淘汰掉的也是花掉的钱。
- **在用净值合计不含已报废**：它的价值在报废那天就定格了，不再随日历变化。
- 「没填金额」与「填了但算不出」**必须分开报** —— 一个去补价格、一个去补日期或年限。
- 🔴 `broken_count` 存在的理由：**不让合计悄悄变小**。勾一下「损坏」会让在用净值合计
  掉一截、而「计入件数」纹丝不动 —— 总数小了、件数还是全的，正是那种「两个数对不上
  还没人会去查」的形态，界面上必须有一句「N 件损坏按 0 计」把它说破。
  它**只属于净值块**：原值合计与状况无关（买的时候花了多少，不会因为后来坏了就变），
  给它也挂一个恒为 0 的字段只会让人以为「这个数坏了」。
- 闲置计入「在用」（它还在我手上）；状况**只影响净值一项**（见下节订正）。

### 口径纠偏（v3.60.1，2026-09-26）

| 项 | 订正前 | 订正后 |
|---|---|---|
| `condition = broken` 的物件 | 净值照直线折旧算残值 | **净值按 `0.00` 计** |
| 件数 / 原值 / 已用 / 计划 / 超期 / 月折旧 | 不受影响 | **仍不受影响**（时间事实与好不好使无关） |
| 报表上怎么分辨是哪种 0 | 一律只是 `¥0.00` | 行内小字按 `zero_reason` 分「已折完」/「损坏归 0」 |

⚠️ 无表结构变化 ⇒ **本次没有新迁移**（`condition` 列自 `0026_property` 起就在）。
完整推导、实测数字与未做项见 `docs/物件资产-净值口径纠偏-改动清单-20260926.md`。

### 状态与报废字段的耦合

三态 `in_use` / `idle` / `scrapped`。**两态不够**：买了还没装的空调、放老家的床垫，
只能选「在用」的话语义就错了，而错的语义会污染「在用件数」这张卡。

**置空由服务端保证**：状态不是 `scrapped` 时 `scrapped_date` 与 `dispose_note` 一律清空
（序列化器 `validate()` 与服务层 `_clear_scrap_fields_if_needed` 各判一次）。
不指望客户端记得送 null —— 漏了会出现「状态是在用、却带着报废日期」的自相矛盾行，
而那种行在列表里看起来完全正常。

### 管理命令

```bash
# 表未建时给「请先执行迁移 wealth/0026_property」，不抛 MySQL traceback
python manage.py wealth_seed_property_categories --dry-run
python manage.py wealth_seed_property_categories              # 幂等，只补缺
python manage.py wealth_seed_property_categories --overwrite  # 覆盖图标 / 说明 / 排序
```

🔴 覆盖**不碰** `default_lifespan_months`（种子值里根本没有它），也不预设任何物件。

### 未做（明确留给后续）

- **四卡卡①/卡④ 的副行**（如「近三年报废 N 件」）：需要后端先下发这个量。
  前端不按日期自己数一份 —— 那是第二份口径，而且会随日历变化。
- **类别图标**：`icon` 已落库（六个种子值），但界面**刻意不依赖它**。
  要用就一次做对（白名单 + 预览）：自由填图标名写错不报错，只会静默退化成默认图标。
- **物件与「三年赎回期」/「里程碑」的关联**：一期明确不做，避免「一笔钱算两遍」。
- **批量录入 / 导入**：一期只有逐件录入。
- **自定义折旧方式**（双倍余额递减等）：刻意只保留直线法 + 残值 0，
  **不提供残值率之类的可调参数** —— 可调参数会让两台空调的净值不可比。
- **`icon` 字段目前没有编辑入口**：类别弹窗刻意不放（见上）。
