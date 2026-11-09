# Summary — 综合进度看板

> 文档对齐 v3.64.5 ｜ 最后核对 2026-10-29

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
| GET | /yearly_detail/?year= | 年度明细 |
| GET | /trend/?year= | 12个月趋势 |
| GET | /radar/?year= | 雷达图数据 |
| GET/POST | /radar_config/ | 七维配置读取 / 改配置 |
| GET | /radar_config_history/ | 雷达配置变更历史 |
| GET | /module_detail/?module=&year=&month= | 模块钻取 |
| GET | /random_retro/ | 随机回顾 |
| GET | /body_mind/ | 身心对照 |

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

