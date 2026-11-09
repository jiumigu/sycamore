# SelfRun — 自我运转

> 文档对齐 v3.64.41 ｜ 最后核对 2026-11-09

KPI 的「制定 → 执行 → 复盘 → 事后分析」全生命周期。
周量「有没有在动」，月量「动出结果没有」—— **两把正交的尺子**，不互相折算。

阶段可以**分两层**（v3.64.17 起）：长阶段只汇总（零 KPI），小阶段才是跑 KPI 的那一层。
「三年赎回期」就是第一个长阶段（v3.64.20 起它不再是一个独立模块），
它下面再挂小阶段。

## Models

八张 **managed 表**：

| Model | Table | 用途 |
|-------|-------|------|
| SelfRunTemplate | selfrun_template | KPI 模板库（可自定义增删改）。建阶段时**拷贝**进 `SelfRunMetric`，此后改模板不影响已建阶段 |
| SelfRunStage | selfrun_stage | 阶段（生命周期容器）。状态机 `draft → active ⇄ paused → closed`，**同一 `parent` 下**只允许一个 `active`/`paused` |
| SelfRunMetric | selfrun_metric | 阶段下一条 KPI 定义（周期 / 目标线 / 底线 / 取数来源）。`metric_id` 必须稳定，被 `Period.readings` 引用 |
| SelfRunMetricPlan | selfrun_metric_plan | **按期目标**：`single`（只这一期）/ `from`（从这一期起），同期的 `single` 压过 `from` |
| SelfRunMetricLog | selfrun_metric_log | 配置变更留痕，**append-only**（创建也记一条） |
| SelfRunPeriod | selfrun_period | 周期快照与结论。归档后 `readings` **冻结**，不再重算 |
| SelfRunCheckin | selfrun_checkin | 唯一的手工数据入口。撤销 = 补一条负值，**原记录保留** |
| SelfRunPoolInject | selfrun_pool_inject | 账单上的「中途注入」**标记**（v3.64.26：只存 `bill_id`，金额与日期从账单读；原为自记金额的注水流水） |

`SelfRunStage` 上两个 v3.64.17 新增列：

| 列 | 含义 |
|---|---|
| `parent` | 上级阶段（`PROTECT`、最多两层）。空 = 顶级 |
| `ledger_config` | 长阶段的账本参数（目前只有 `pool_principal`）。**配置不是流水**，所以不单开表 |

⚠️ 新增 managed 表必须同步 `backend/conftest.py` 的镜像 DDL —— `--reuse-db` 下 Django 不建表，报错长相是「列不存在」。
⚠️ **加列也要补**：旧测试库的表已存在，`CREATE TABLE IF NOT EXISTS` 会静默跳过 ⇒ 走 `_patch_selfrun_stage_columns()`（幂等补列）。

## 口径（改之前必读）

### 阶段分两层（v3.64.17）

- **最多两层**：长阶段（`parent IS NULL`）挂小阶段，小阶段不能再挂。模型 `clean()` 与服务层 `create_stage()` **各判一次**（`clean()` 挡不住 `objects.create()`）。
- **互斥按 `parent` 分组**：「同一时间只允许一个 `active`/`paused`」**不再是全局唯一**，否则长阶段一开小阶段就开不了。副作用是**长阶段开着时，新阶段必须挂在它下面**（错误信息里直接给出 parent id）。
- 🔴 **KPI 只挂叶子**：长阶段零 `Metric` ⇒ 天然不产生 `SelfRunPeriod`。理由：`Period` 唯一键是 `(stage, period_type, period_key)`，长阶段若也配 KPI，**同一周会同时属于两个 Period**，判定打两遍，「本周活着 0/5」算谁的就说不清。
- 🔴 **形态必须显式声明**：`is_long_stage=True` 才是长阶段。`metrics` 空又没声明 ⇒ **400**，不靠「有没有 KPI」猜意图（猜错了会得到一个「看着正常、其实永不判定」的阶段）。
- 🔴 **`get_open_stage()` 只返回叶子**：判据是「有 active KPI」，**不是** `parent__isnull`（后者会误伤历史遗留的无父阶段）。已知副作用：某阶段 KPI 全部退役时它返回 `None`，页面落到「还没有进行中的阶段」—— 空态要说清「你有阶段，只是 KPI 全退役了」。

### 其余

- **派生值不落库**，唯一例外是**快照**：`Period.readings` / `Stage.summary_snapshot`。判据是「以后重算得出同样结果吗？不能才落」。
- **目标值是输入不是派生** ⇒ 必须落 `selfrun_metric_plan`。直接改 `metric.goal_value` 会把当期一起改掉，而归档快照保护不到未归档的当期。
- **判定阈值只此一份**：`constants.PERIOD_VERDICT_BANDS`（≥80% 我超棒 / ≥60% 合格 / ≥40% 及格 / `<40` 兜底「活着」）。前端 0 个阈值数字。
- **阶段天数由后端给**：`days_label` 用 `min(today, end_date)` 计算，起点前为 `还有 N 天开始`、终点后为 `共 N 天`；前端不自己算 `today - start + 1`（v3.63.13）。
- **阶段区间由后端给**（v3.64.10）：`range_label` = `2026-11-01 ~ 2026-12-31（61 天）`，没设终点则 `2026-11-01 起（不设终点，手动收尾）`。**起止日期只此一份**，页头 / 仪表盘 / 阶段总结 / 已收尾列表都印它；`days_label` **不回带起点**（两处都写会像两个不同的值）。
- **相位词跟着时间走**（v3.64.10）：`status='active'` 只说「这是当前在册的那一个阶段」，不等于「已经在跑」——`status_display` 在「active 且今天 < 起点」时返回「未开始」，否则页头会写成「进行中 · 还有 1 天开始」。
- **一期也要带日期**（v3.64.23）：`period_range_label(period)` = `2026-W42（10-12 ~ 10-18）`。
  单独一个 `2026-W42` 读不出「这周到几号」（ISO 周号跨年时心算必错），所以周号后必须跟区间；
  `period_end` 是**半开**的 ⇒ 显示要减一天，否则每期都印成 8 天。阶段总结的「最好的一期」用它。
- **月判定只看三问**（v3.64.6）：答「是」的个数 ÷ **3**（分母恒为 3）。**全未答 ≠ 全否**：一个都没点 ⇒ **未判定**（`value=''` + `basis='pending'`，界面显示「待答三问」），**不拿月度 KPI 顶档**（旧实现会顶，于是同一期先后出现「4/4 我超棒」和「2/3 合格」）。归档前必须三问全答，否则 400 且不落行；归档后补答**不改档**（要改走重开）。
- `empty`（真的没做）**进**分母；`unknown`（取不到）/ `skipped`（本期暂停）**不进**。
- **归档 = 定格**：`closed_at` 一落，补记 / 冲销 / 改目标 / 改配置一律 409；归档后仍可写的只有 `review_text` / `answer_sheet`（记忆型 ≠ 数据型）—— 但月度补答 `answer_sheet` **不再重判 `status`**，档位只在归档那一刻定一次。
- **重开**是改历史判定的唯一出口，必须写原因，并留 `reopen_count`。
- 🔴 模板里的加粗写 `<b>`，**不许写 markdown 的 `**`** —— 在 HTML 里它不是加粗，会原样显示成两个星号（本模块曾有 20 余处，v3.64.9 清完）。
- **`template_key` 是字符标记不是 FK**：删模板不牵连已建阶段。
- **取数器只许命中白名单** `READER_KEYS`（`temporal_hours` / `growth_hours` / `temporal_days` / `diary_migu_count` / `step_days` / `bill_income` / `module_value` / `manual_sum` / `works_count`）；**不做任意查询构建器**。
- 🔴 **取数方式在「改这条 KPI」里也能改**（v3.64.31）：此前只有「建 KPI 时从模板挑」一个入口，
  建完想改只能退役重建 —— 而退役会把手工登记一起带走。改口径走 `MetricPatchSerializer.source_kind`
  + `_validate_source_config`（与建模板**同一套**校验：取数器拼错当场 400 且**一个字不写库**）；
  `agg` 由 `READER_AGG` 按取数器推导 —— 它不参与取数、只进展示与配置指纹，所以漏改**不会报错**，
  只会让界面理直气壮地说错话（「从作品库取数 · 按手工求和」）。切到 `manual` 时
  `source_config` 被强制成 `{'kind': 'manual_sum'}`，不许「手工 + 自动取数器」这种混血。
  钉在 `tests/test_selfrun_metric_source_patch.py`。
- 🔴 `growth_hours`（v3.64.11）：成长计时的**唯一口径**，只读 `temporal_task_meta.counts_growth`，
  **不读** `metric.source_config.where` —— 留一个可配的 where 就等于同一个量有两处定义。
  此前是 `temporal_hours + where.l2=['深度工作']`（隐式、界面上看不见、改 L2 会顺手改口径）。
  钉在 `tests/test_selfrun_growth_hours.py`。
- `works_count` 直接数 `works.Work`，**刻意不给新鲜度规则** ——「这周一件都没留」是事实，不是数据源过期。
- 🔴 `works_count` 的 `where.work_kind`（v3.64.30）：按**作品类型**过滤，「这月画了几张」就走这条路
  （`{'kind': 'works_count', 'where': {'work_kind': 'drawing'}}`）。
  留空 = 数全部类型（「留下件数」那条）；**类型名配错直接抛 `ValueError`，绝不返 0** ——
  `0` 是「一张都没画」这个**结论**，不能由笔误冒充。候选值随 `/templates/` 的
  `enum.work_kind_options` 下发（真源 `works.constants.WORK_KIND_CHOICES`）。
  ⚠️ 配套前提：作品页填类型时得选对 —— 所以 `craft` 的 label 从「实物」改成「其他手作」，
  不留一个能装下所有手工实物的桶（否则自动数静默少算）。
- 🔴 `module_value` 的 `redemption.runway`（可支撑月数）：v3.64.20 起数据源是
  **当前长阶段**（本金取 `ledger_config.pool_principal`、窗口取阶段起止），
  不再是 `redemption_period`。**键名故意不改** —— 它已经写进用户配好的 KPI 定义里，
  改键名会让存量 KPI **静默**失效（取数器命中不了白名单 = 那条 KPI 变空，不报错）。
  空态码也从 `no_period` 改成 `no_long_stage`（两个码指的不是同一件事）。
  🔴 v3.64.41 起这段计算抽成 `readers.runway_reading()`：KPI 与仪表盘
  `GET /runway/` **共用同一个函数**，另外多给 `covers_stage`（按当前速度能否撑到
  阶段终点；阶段没设终点时是 `None`，不是 `True`）。两张屏读两个数时，
  用户没有任何办法判断哪个对 —— 所以只许有一份实现。
- 心跳只 UPDATE `last_seen_at`，**不判好坏、不改任何 KPI、不建记录**。
- 前端 `types/selfrunTypes.ts` 是枚举的**副本**（不是接口下发），改 `constants.py` 必须同步改它，否则静默少选项。

## API Endpoints

前缀 `/api/selfrun/`

| 分组 | 方法 | 端点 | 用途 |
|------|------|------|------|
| T1 制定 | GET/POST | /templates/ | 模板列表 / 新建 |
| | PUT/DELETE | /templates/&lt;pk&gt;/ | 改 / 删模板 |
| | POST | /metrics/preview/ | 取数试算（**绝不落库**） |
| | GET/POST | /stages/ | 阶段列表 / 生效新阶段（一个事务写 3 张表） |
| | GET/PATCH | /stages/&lt;pk&gt;/ | 阶段详情 / 改备注 |
| | POST | /stages/&lt;pk&gt;/pause/ · /resume/ | 暂停（休耕）/ 恢复 |
| | GET/POST | /stages/&lt;pk&gt;/summary/ | 阶段总结：看实时数字 / 写总结 |
| | GET | /stages/&lt;pk&gt;/ledger/ | **阶段账本**（区间 / 时间 / 钱 / 作品 / 子阶段，只读现算） |
| | PATCH | /stages/&lt;pk&gt;/ledger-config/ | 改账本参数（**只收 `pool_principal`**，多余键 400） |
| | POST | /stages/&lt;pk&gt;/close/ | 收尾阶段 |
| | POST | /stages/copy/ | 用当前配置开新阶段（不复制 Period / Checkin） |
| T1b 按期修订 | GET | /period-options/ | 可修订的周期（上一期 + 本期 + 往后 N 期） |
| | GET | /targets/ | 某期生效目标清单 |
| | GET/POST | /metrics/&lt;pk&gt;/plans/ | 该 KPI 的按期设定 |
| | DELETE | /metrics/&lt;pk&gt;/plans/&lt;plan_id&gt;/ | 取消某期设定（回落上一层口径） |
| T2 执行 | GET | /periods/current/ | 本周 / 本月状态（**GET 不写库**，无行返回虚拟对象） |
| | GET/POST | /checkins/ | 手工登记流水 |
| | DELETE | /checkins/&lt;pk&gt;/ | **冲销**（补负值，不删原记录） |
| | PATCH | /metrics/&lt;pk&gt;/ | 改 KPI 配置（不新建行 + 留痕） |
| | POST | /metrics/&lt;pk&gt;/retire/ · /revive/ | 退役 / 恢复 |
| | POST | /heartbeat/ | 回访握手（只更新 last_seen_at） |
| T3 复盘 | GET | /periods/ | 历史周期（归档后读数取自快照） |
| | POST | /periods/close/ | 归档（**系统不自动归档**） |
| | GET/PATCH | /periods/&lt;pk&gt;/ | 详情 / 补写复盘（归档后仅 review_text / answer_sheet 可写） |
| | POST | /periods/&lt;pk&gt;/reopen/ | 重开（必须写原因） |
| 跨模块 | GET | /overview/ | 仪表盘小卡（只读、不写库） |
| | GET | /runway/ | 仪表盘「跑道」卡（只读、不写库；与 KPI `redemption.runway` 同一取数函数） |

## 边界

- **长阶段没有期**：`/periods/*` 对它全部无意义（调 `close` 会 400「当前没有进行中的阶段」）；它也不该有 KPI —— `POST /stages/copy/` 拿长阶段当源会 400「没有 KPI」。
- 历史归档周期**绝不重算**；要看「当时为什么是这个数」，读 `readings` 里的
  `auto_value` / `manual_value` / `final_value` 三个数，不要只看 `final_value`。

### 阶段账本（`stage_ledger`，v3.64.18）

`GET /stages/<pk>/ledger/` 给**任意阶段**一份「钱 / 时间 / 作品」的汇总，只读现算、不落库。
叶子阶段也能用（只看钱与时间），不设「只给长阶段」的闸门。

🔴 **它不自己算钱与时间**，一律调 `apps.redemption.services` 的那几个函数。
   同一件事两份实现 ⇒ 两个数迟早分叉，而分叉是静默的（页面上下两块各自看着都合理）。
🔴 **本金与注入由本模块算好传进去**（`ledger_config.pool_principal`、
   `readers.pool_inject_totals(start, end)`）：那两个函数不查表，所以它们能被任意阶段复用。
   若哪天有人把它们改回「自己查 `redemption_period`」，账本会立刻只剩一个阶段能用。
🔴 **注入的金额只有一个来源：账单**（v3.64.26）。标记表只存 `bill_id`；
   被标注入的收入同时要从净消耗里排除（`exclude_bill_ids`），否则同一笔钱
   既加进注入又减少消耗，余额凭空翻倍 —— 而页面上下两个数各自看着都合理。

| 块 | 内容 | 唯一出口 |
|---|---|---|
| `range` | 起点 / 终点 / 总天数 / 已过 / 剩余 | `stage_elapsed_days()` |
| `time` | 六类小时（**不含睡眠**）/ `covered_hours` / `excluded_sleep_hours` / `fallback_hours` / 覆盖率 / 成长占比 | `compute_time_attribution(start, end)` |
| `money` | 池（本金 / 注入 / 余额 / 日均 + 样本天数 / 撑到哪天 + 原因码）/ 档位分布 / 允许日均 / 预算占用 | `compute_pool_balance` 等四个 |
| `works` | 区间内成形的作品：`count` + 明细 `items`（同一次取数）+ `limit`/`truncated` | `_stage_works` → `readers.works_count` |
| `children` | 子阶段（名字 / 区间 / 状态 / `hit` / `judged` / `reach_rate`） | `compute_stage_summary()` 逐个子阶段 |

四条口径红线（都有测试钉住，改之前先看 `tests/test_stage_ledger.py`）：

1. **六类小时之和 == `covered_hours`** —— 兜底那部分单列 `fallback_hours`，但不排除；
   **睡眠（夜间 + 午睡）不在这条里**：它在摊进六类之前就被跳过，单列 `excluded_sleep_hours`，
   且 `covered_hours + excluded_sleep_hours` == 区间全部记录时长（v3.64.22）。
   分母是「每天可支配 14h」（`redemption.services.THEORETICAL_DAILY_HOURS`，v3.64.25 由 12h 调到 14h），
   分子若含睡眠，覆盖率必然冲破 100%（实测 141.5%）。页面文案里的「每天几小时」
   由后端下发（`time.theoretical_daily_hours`），**前端不许写死**。
2. **`avg_daily <= 0` 不是「永不耗尽」** —— `support_until` 为 `None`，并附一个**原因码**，
   前端查表出人话。`0` 不能当 `∞`。原因分两种（v3.64.26）：
   `no_self_expense`（一条账都没有）与 `net_inflow`（钱在变多、不存在耗尽日）——
   两者都给 `None`，但说的是完全相反的事，所以不能共用一个码。
3. **笔数用 `Count`** —— 曾经用 `Sum('id')`，2 条账单会显示成 14 笔（且不离谱到能被一眼看出）。
4. **表缺失时返 503，不兜成「注入 = 0」**（v3.64.27）—— 兜成 0 会让余额凭空少一块且静默；
   留 500 堆栈则长得和「代码坏了」一样。503 的 `detail` 就是给用户的操作指引，
   前端必须把它原样显示出来（只弹一句「加载失败」等于把唯一线索扔了）。

🔴 **钱的图只能有一把尺子：每天多少钱**（v3.64.24）。曾经的「单位赎回成本 ¥28.56/h」
除**已过小时**、「理论下限 ¥11.74/h」除**全期小时**，分子还不同（实花 vs 本金）——
并排看必然读出「28.56 高于 11.74 ⇒ 超标」，而阶段第 5 天根本没到该比的时候。
现在只留 `daily_allowance`（剩余余额 ÷ 剩余天数）与 `pool.avg_daily` 同量纲相比，
`daily_use_rate` 是二者的比、过 100% 才叫撑不到终点。**不要再把 ¥/h 加回来**。

⚠️ `range` / `status` / `days` 三处显示词也搬到了 services
（`stage_range_label` / `stage_status_display` / `stage_days_label`），
serializer 的 `get_*` 只是委托 —— 账本的子阶段行与阶段页头必须印同一个「第 N 天」。
- 补归档超过 `BACKFILL_WARN_DAYS`（7 天）必须标 `is_backfilled`，界面显式说明「此数事后补算」。
- 阶段起于周中时第一个周期是**残缺周**：参与展示，**不进**阶段达标率。
- `/periods/<pk>/` 的 `extras`（`what_happened` / `goals` / `time_loss` / `outcomes`）是**当期现算**的派生值，
  不落库；归档后它与快照里的读数不一致属正常 —— 快照存的是**结论**，`extras` 算的是**当下**。
- `outcomes`（v3.64.37）回答「这一期**干成了什么**」，与 `what_happened` 是两个视角：
  前者量**产出**（有结果的），后者量**投入**（花掉的时间）。三栏：
  - `works` —— 成品，按 `Work.created_at`（成形于）**半开**区间；复用 `readers.works_count`，
    不调 `_stage_works`（那个内部 `end + 1 天`，在这里会多吃一天）
  - `milestones` —— 本期该交且已交，**复用** `goals` 的同一份 `due_rows`，绝不另查一次
  - `finished` —— 办完的事 = 小确幸 `joy_type='秩序型'` + 收件箱 `status='done'`，
    标题去掉「完成：」前缀后**精确相等**去重（命中标 `source='both'`，保留小确幸那条）

  🔴 **不给跨源总数**：同一件事可能既是成品又被记进小确幸（10-18 那篇文章两处都有），
  合并成一个数就是重复计数，且事后无法回溯去重。三栏各报各的数。
  🔴 **只收「秩序型」**：未标快乐类型的条数单列 `untyped_count`（卡片底部印「另有 N 条未计入」）——
  过滤条件可以狠，但砍掉多少必须说出来，否则页面少几行没人发现。
  三栏全空时 `empty=true`，前端**整卡不渲染**（不是显示三行 0）。
- `what_happened` 按**本地日期**分组（`start_time` 存 UTC），且排除**睡眠类**（`contrib_excluded_names()`，
  与贡献图同一份）；流失统计走 `resolve_attribution`（v3.64.16 起它只剩一层：映射表的
  `default_attribution` + 兜底），不另推一套 —— 与仪表盘护栏卡、贡献图同一把尺子。
- `what_happened` 同时给**两套视图**（v3.64.35，同一个函数产出，不各查一次库）：
  - `days` —— 同名任务**合并**后的小时数（清单用，回答「今天做了几件事」）
  - `blocks` —— **不合并**的时段区间（时段轴用，回答「几点到几点」）

  `blocks` 的每块是 `{date, from, to, minutes, task_name, attribution, split}`，
  `from`/`to` 是**当天第几分钟（0–1440）**，不是时间串 —— 前端只做乘除，不解析日期、不碰时区。
  跨午夜的记录按天切成多段（`split` = `head`/`tail`/`mid`），`end_time` 为空时用
  `duration_hours` 兜。另有 `columns`（周期内每一天，含没记录的天）、`span`（块覆盖的分钟范围，
  用于**自适应纵轴**，不给 0–24）、`truncated`（超 `WHAT_HAPPENED_BLOCK_LIMIT` 时被丢掉的块数）。

  🔴 `span` 的**上边界只由「主体块」决定**（v3.64.36，`_span_of`）：跨午夜切出来的段若短于
  `WHAT_HAPPENED_FRAGMENT_MIN`（60 分钟）就不参与上边界计算，下边界仍取全部块最晚结束。
  起因是 W42：三条 37/9/5 分钟的尾巴落在 00:00，把纵轴从 06:55 拉回 0 点，整图多出 235px
  空白（刻度上写着 02:00/04:00/06:00 却什么都没记）。⚠️ 这些残片**仍在 `blocks` 里**，
  前端在列顶标「＋37m」—— 只裁范围不裁数据，也不把它们夹到边线上画（那会读成另一个时刻）。
  只裁上边界是因为：尾巴的另一半（头段）已经在左边那列画到 24:00；下边界的头段若被裁，
  一条真实的深夜活动就只剩一个数字。

  ⚠️ 列表按**开始日**归类、时段轴按**实际占用**画：跨午夜那条会在两列各出现一次，
  而清单里只有一天。这不是不一致，是「发生在哪天」和「记在哪天」两件事。
  ⚠️ 图与表必须能对账：`Σ blocks.minutes ÷ 60 == days[i].total_hours`
  （`test_blocks_minutes_match_day_hours` 守着这条）。
