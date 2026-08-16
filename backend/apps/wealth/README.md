# Wealth — 财务管理

## Models

| Model | Table | 用途 |
|-------|-------|------|
| WealthLifeWeekCalendar | wealth_life_week_calendar | 3172 周周历（61年×52周） |
| WealthCurrentScenario | wealth_current_scenario | 单例推演状态 |
| WealthScenarioHistory | wealth_scenario_history | 推演历史 |
| WealthRegularList | wealth_regular_list | 定期存款 |
| WealthCashFlow | wealth_cash_flow | 现金盘点（各账户余额月度快照 + 自动计算总现金流/总额/实有数） |
| WealthBalanceList | wealth_balance_list | 盈亏账单（余额流水） |
| AllocationCategory | wealth_allocation_category | 分配类别（图标/颜色/优先级/默认金额，可自定义） |
| AllocationPlan | wealth_allocation_plan | 月度分配计划（手头现金/硬性承诺/预留分配/自由支配） |
| AllocationItem | wealth_allocation_item | 分配明细项（计划预留金额/已花费/剩余，remaining 自动计算） |
| Commitment | wealth_commitment | 硬性承诺（未来必须花的钱，来源：账单/收件箱/手动） |
| DecisionLog | wealth_decision_log | 自由决策记录 |

## Services

| File | 职责 |
|------|------|
| `services/calendar_init.py` | 初始化周历，按出生日期映射年龄→年份 |
| `services/week_aggregator.py` | 交易按周聚合 + net_level 7级颜色 |
| `services/coverage_calculator.py` | 现金流推演算法（现金÷周预算 + 日利息复利） |
| `services/monthly_aggregator.py` | 月度日聚合 + 颜色等级 + 月度汇总 |
| `services/review_service.py` | 月度复盘（趋势/分类排行/月度清单/对账/生成盈亏） |
| `services/regular_service.py` | 定期存款完整业务逻辑 |
| `services/cashflow_service.py` | 现金盘点（资产全景/趋势/快照CRUD/复制上月/对账） |
| `services/allocation_service.py` | 资金排程 + 分配计划（计划 CRUD/幂等保存/记录花费/自由决策） |

## API Endpoints

前缀 `/api/wealth/`

| 方法 | 端点 | 用途 |
|------|------|------|
| GET | /calendar/ | 周历列表（含聚合收支） |
| GET | /weekly_summary/<id>/ | 单周明细 |
| GET/PUT | /scenario/current/ | 当前推演状态 |
| POST | /calculate_coverage/ | 现金流推演计算 |
| GET | /summary/ | 人生总览 |
| GET | /bills/by_week/ | 按周账单 |
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
| GET | /cashflow/reconcile/ | 账面与实际对账 |
| GET | /allocation/detail/?year_month= | 获取月度分配计划详情（含全部启用类别作为明细项） |
| POST | /allocation/create/ | 创建/更新分配计划（幂等，可反复保存） |
| POST | /allocation/update-allocations/ | 增量更新分配项 |
| POST | /allocation/record-spending/ | 记录某分类实际花费 |
| POST | /allocation/save-decision/ | 保存自由决策 |
| GET | /allocation/categories/ | 获取可用分配类别 |

## 资金排程 + 分配计划

核心语义：**分配是计划（预留），不是记录（花费）**。流程：手头现金 → 硬性承诺 → 预留分配 → 自由支配。

- **月度计划**：`AllocationPlan` 按 `year_month` 唯一（`unique_together`），记录手头现金/硬性承诺合计/预留分配合计/自由支配，状态 draft/active/closed
- **预留分配**：`AllocationItem` 按 `(plan, category)` 唯一；`save()` 自动计算 `remaining = planned - spent`；`get_plan_detail` 返回全部启用类别（未保存的为 id=null 虚拟项 + 默认金额），看板首次进入即可编辑
- **幂等保存**：`create_plan` 在事务内 `update_or_create` 分配项（保留已花费）、删除并重建承诺、剔除未包含的分配项，可反复保存
- **硬性承诺**：`Commitment` 待付/紧急/已付三态，来源 bill/inbox/manual；`calculate_commitments` 通过 `wealth_bill_list` 原生 SQL 按 60 天窗口聚合支出账单生成
- **自由决策**：`DecisionLog` 记录自由支配的打算怎么花（save/learn/travel/home/venture）
- **类别初始化**：`manage.py init_allocation_categories` 幂等创建 5 个默认类别（投资/日常生活/精神愉悦-旅游美食/家居装修/风险预估-留底钱）
