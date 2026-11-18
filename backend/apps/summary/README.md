# Summary — 综合进度看板

> 文档对齐 v3.64.63 ｜ 最后核对 2026-11-14

## 口径（v3.62.43 起）

七维：财富 / 健康 / 时间投入 / 文字记录 / 小确幸 / 旅行 / 阅读。

- 每个维度给「**覆盖率** + **强度**」两个数，**不再有总分**：
  - 覆盖率 = 有记录的期数 ÷ 该有的期数（回答「有没有断」）；
  - 强度 = 总量 ÷ 有记录的期数（回答「记的时候做了多少」）。
- 七个维度量纲不同，**不相加**；`points` 仍在响应里，但只作为「对目标达成率」的内部评分单位，界面不再展示为总分。
- 覆盖率 / 强度 / 达成率都可能是 `null`（未来年份、零期数、取不到）—— **`null` 不是 `0%`**，前端显示「—」。
- 当前月**不进月粒度分母**（月结动作未完成）；单月视角的强度分母是 1。
- 季度报告仍用内部 `points` 做环比 / 同比（`QuarterlyReportSerializer`），但年度总览已无 `total_points` / `yearly_target`。

## API Endpoints

前缀 `/api/summary/`

| 方法 | 端点 | 用途 |
|------|------|------|
| GET | /years/ | 有数据的年份列表 |
| GET | /overview/?year= | 年度总览 |
| GET | /monthly_detail/?year=&month= | 月度详情 |
| GET | /yearly_detail/?year= | 年度明细（每年一行 × 七列覆盖率） |
| GET | /year_retro/?year= | 年度回顾（叙事版：有时间锚点的事实流，每段引用真实记录） |
| GET | /trend/?year= | 12个月趋势（含 `stage_spans` 阶段带） |
| GET | /stage_compare/ | 按**人生阶段**比七维覆盖率（跨年） |
| GET | /radar/?year= | 雷达图数据 |
| GET/POST | /radar_config/ | 七维配置读取 / 改配置 |
| GET | /radar_config_history/ | 雷达配置变更历史 |
| GET | /module_detail/?module=&year=&month= | 模块钻取 |
| GET | /random_retro/ | 随机回顾 |
| GET | /body_mind/ | 身心对照（周粒度，下发原始量，不发合成分） |
| GET | /pair_check/ | 跨维度配对相关性（含系数、判档、稳健性） |

### 季度报告

| 方法 | 端点 | 用途 |
|------|------|------|
| GET | /quarterly_report/ | 季度报告主体 |
| GET | /quarterly_questions/ | 季度自问清单 |
| GET/POST | /quarterly_answers/ | 季度回答（读取 / 落库） |
| GET | /quarterly_insights/ | 季度洞察汇总 |

## Models
| Model | Table | 用途 |
|-------|-------|------|
| SevenDimConfig | summary_seven_dim_config | 雷达图七维配置（含变更历史） |
| QuarterlyAnswer | summary_quarterly_answer | 季度自问的回答 |

## 阶段分段（v3.64.61）

`services/stage_span_service.py` 把 `selfrun` 的人生阶段摊到「月」与「阶段」两个尺度上。
依赖方向 **summary → selfrun 单向**（summary 早已单向依赖 temporal / sugar / book /
toolkit / goals，再加一条不产生环）；`selfrun` 侧零改动。

两个入口：

- `month_spans(year)` → 12 个月的阶段归属。一个月内可能**切换**（返回逐段
  `segments` + `is_mixed`），也可能**没有任何阶段**（`reason='no_stage'`，
  不回退成上一段的名字 —— 那会凭空延长一段人生）。
- `stage_compare()` → 各顶层阶段的七维覆盖率，跨年。

🔴 三条判据与 `selfrun.services.stage_timeline()` 逐字对齐：

1. 区间是**闭区间** `[start_date, end_date]`（那边算空档从 `end_date+1` 起算）
2. 只取**顶层**（`parent IS NULL`）—— 小阶段是长阶段内部的细分，
   两层摊平会让同一个月出现两个阶段名，而曲线一个月只有一格
3. `end_date=None` ⇒ 延伸到无限

🔴 **只比覆盖率，不比强度**：覆盖率是无量纲占比，两个阶段同尺；强度是绝对量
（步/天 vs 元/月），并排会被读成「哪段人生过得好」。

🔴 分母起点 = `max(阶段起点, 系统可观测起点)`，其中可观测起点是
`date(min(avail_years), 1, 1)` —— **全局的、七个维度共用一个**。
不要改成「该维度最早一条记录」：那会把「阶段开头几天没记」从分母里剔掉，
覆盖率虚高且页面上看不出来。虚高比虚低危险 —— 虚低至少显示 0% 让人去看。

`pct=null` 三种原因，都不是 0%：

| 原因码 | 含义 |
|---|---|
| `no_records` | 这个维度从来没有任何记录（模块还没开始用） |
| `before_data` | 整段都在系统有数据之前（分母不存在） |
| `no_complete_period` | 月粒度维度，阶段还不足一个完整月 |

可观测维度 < 2 时不下发 `weakest`（一个候选里挑最差没有比较意义），
同时给 `comparable_modules` 让前端说清为什么是「—」。

⚠️ 取年份必须遍历**全部记账年**再按实际日期分箱：`_covered_marks` 有些维度按
年字段过滤（旅行 `tyear`、财富 `yearmon`）、返回的却是实际日期（`ttime`），
而旅行允许**补记**（`tyear` 与 `ttime` 可以不同年）。只取区间内的年份会漏掉
补记的行，只取记账年又会把它们算成记账那年有记录。

## 跨维度相关性（v3.64.62）

`services/correlation_service.py`。两个尺子：月粒度相关（`CORRELATION_PAIRS` 五组）、
周粒度身心对照（`body_mind_correlation_service.py`）。

### 判据

- **主判据是秩相关 ρ（Spearman），不是 Pearson r**：支出有单月数万的极端值，
  Pearson 会被一两个点绑架。ρ 先转秩，极端值只算「最高的一名」。
- **但秩相关下单点也撑不起系数**：n=12 时一点最多贡献约 0.17。
  「不稳健」的真正形状是**两端点对齐、中间段反向**（两个尾巴凑巧同向，
  中间十几个点全在往下走），不是「被离群点拉偏」。
- 稳健性 = **去掉两端各一点后重算**：

  ```python
  robust = abs(trimmed) >= CORRELATION_ROBUST_MIN or abs(rho) < CORRELATION_ROBUST_MIN
  ```

  第二项不能省：本来就「无明显关系」的配对，去两端后跳到 0.5 只是**样本太少**，
  算不上「稳健的强关系」。

### 三态（都不是 0）

| 情况 | 返回 |
|---|---|
| 一个共同月份都没有 | `rho=None` + `no_data` |
| 有月份但 < `CORRELATION_MIN_N`(12) | `rho=None` + `not_enough`，**不判档** |
| 某一边全月同值（方差 0） | `rho=None` + `constant` |

`n < 12` 只给系数不判档 —— 十几个点能算出任何数，写「明显」就是把噪声当结论。

### 取数

一律**复用既有口径，不另写 SQL**：时间走 `ProgressAggregator._times_counted_year`
（含 `ATTRIBUTION_COUNTED` 与「未归类」排除），财富走 `WealthBalanceList`
（七维用同一个源，不另取 `WealthBillList` —— 两个源在重叠月份会差几十元）。

🔴 缺失月份**不进 dict、绝不补 0**：走 `is None` 才跳过。支出真为 0 的月份是有效数据。

`sugar` 的快乐程度取**均值**而非次数 —— 一个月吃 20 次廉价糖和吃 2 次，
快乐程度不是同一件事。

### 防因果

每组配对必带 `why` **疑问句**（「多花时间就一定会多花钱吗」）。表里不出现因果断言，
问句字号大于结论字号 —— 读的人先看到问句。

### 身心对照的口径变更

旧版有两个假数，均已删除：

| 旧 | 问题 |
|---|---|
| `aggregate(...)['avg'] or 0` | 无数据时聚合返回 `None`，`or 0` 变成 0 再参与后续计算 |
| `sleep_score = 100 - 延迟×1.5 - 夜醒×15` | 系数无出处；延迟 60 分钟就算成负数 |

现在下发五个**原始量**：`sleep_latency` / `awakenings` / `nights` /
`output_rate` + `output_count` / `mood`，缺一个整行 `None`。

🔴 `mood` 量程 **5–20**。旧前端写死 `min:1, max:10` ⇒ 所有点顶在天花板上，
形成一条假水平线，图表看着「很稳定」其实是裁的。**改前端量程前先读这条。**

## 年度回顾 · 叙事版（v3.64.63）

`services/year_retro_service.py`。与 `/yearly_detail/` 的分工一句话：
**那边是测量，这边是「我发生了什么」。**

审计报告的原始约束是「需要先定叙事取自哪里，否则会变成又一张表」。
所以判据先立在前面：

1. **只讲有时间锚点的事**。「今年读了几本书」没有时间锚点，留给年度明细那张表。
2. **每段必须带 `evidence`**（一条真实记录的日期 + 摘要）。取不到就不生成 —— 宁可少讲。
3. **只陈述事实**，不评价、不建议、不打分。

### 五类段

| kind | 含义 | 锚点 |
|---|---|---|
| `first` | 今年第一条记录 | 那天 |
| `gap` | 两条记录之间最长的一段空档 | 空档前一条的日期 |
| `stage` | 人生阶段开始 / 结束 / 换段 | 切换日 |
| `densest` | 连续有记录的最长一段 | 段首 |
| `last` | 今年最后一条记录 | 那天 |

### 🔴 四个实测撞出来的坑

**① 开头和结尾的空档不算断档**

`end` 是今天，而记账通常月末才落 ⇒ 末尾那一段会被报成「断了 44 天」，
其实是「本月还没结账」。开头那段则在去年已经算过一次。
两处都会造假警报，而且「最后一条记录」那段已经把同一件事说过了。
⇒ 只统计**两条记录之间**的空档。

**② 每个维度最多一条空档**

2024 的小确幸先空 154 天、再空 87 天，两条都进榜就变成同一件事讲两遍，
真正长的别处反而挤不进来。⇒ 模块内取最长，再全局排序取前 `RETRO_MAX_GAPS`。

**③ 月粒度维度按「月」算，不按天**

记账按月落、读完一本书按月落，本来就不是天天有。按天算会把它自己的
记账节奏误报成断档（实测 2024 旅行「空 284 天」其实是年内只有两次出行）。
⇒ 走 `COVERAGE_SPEC[module]['period']`，月粒度用月数与 `RETRO_GAP_MIN_MONTHS` 判。

**④ 全程连续不算「一段」**

2026 实测 318/318 天都有记录（时间投入几乎每天有任务）。
这时最长连续 = 整个区间，它不是「一段」而是「全程」——
汇总句已经说了「每一天都至少留下一项记录」，再单列一段就是同一句话讲两遍。
⇒ `best_len >= elapsed` 时不生成 `densest`。

### 截断与空态

- 超过 `RETRO_MAX_SEGMENTS` 时按权重留，但 **`first` / `last` 必留** —— 叙事的两头不能丢。
- `thin_reason` 三态（都是「讲不出来」，但不是一件事）：
  `future`（还没到）/ `no_data`（一条记录都没有）/ `sparse_data`（记录太少）/
  `few_events`（记录够勤，但这一年确实平顺）。
- `absences`：整年 0 条的维度单独列名字，不塞进时间线 —— 它没有时间锚点。

### 与既有口径的关系

- 取数只用 `ProgressAggregator._covered_marks()`：七维「有没有记录」只有这一把尺子
  （含日记空占位不算、书籍只算读完、时间投入走归因排除）。
- 阶段的闭区间 / 只取顶层 / `end_date=None` 无限延伸，与 `StageSpanService` 逐字对齐。
- 证据里的金额**只来自用户自己写的备注**，系统不拼「本月净增 ¥X」——
  否则和 `privacy_mode` 的整串掩码口径打架。
- 时间区间一律半开 `[天 00:00, 次日 00:00)`，不用 `time__date`（`USE_TZ` 撞 `CONVERT_TZ`）。

## 取数约束（2026-10-28）

**一次请求只许取一份事实。** 「时间投入」这份数据会被年覆盖率、年总量、强度三处同时需要，
旧实现各自回库 ⇒ `overview` 一个请求 35 条 SQL（其中 12 条是同一份数据取了三遍）。

现在的做法：

- `_times_counted_year(year)` 整年取一次，「计入/排除」判据与 `_times_raw` **同源**；
- `_times_rows(year, month)` 在内存里按 `mon` **字符串**过滤（不是 `date.month` ——
  那会把没补零的历史行放进来，月度总量静默变大）；
- `ProgressAggregator.request_scope()` 在 `SummaryViewSet.dispatch` 开一次作用域，
  **出作用域即销毁**。🔴 绝不能改成模块级/进程级缓存：归因（任务的 L1 默认值）
  是用户可改的，进程级缓存会让改完映射表的页面继续显示旧口径，而界面上完全看不出来。

实测：`overview` 35→18 条 / 27.8→15ms；`monthly_detail` 30→17 条；`trend` 106→66 条。

回归测试在 `tests/test_query_budget.py`：ATracker 同请求只许 SELECT 一次、
SQL 总条数预算、月度过滤口径、**以及「改完归因下一次请求必须看到新口径」**。

