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
| FundSchedule | wealth_fund_schedule | 资金排程快照（JSON 预留项目，服务端计算预留合计/剩余） |

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
| `services/fund_schedule_service.py` | 资金排程（校验预留项 + Decimal 计算预留合计/剩余 + 快照创建） |

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
| GET/POST | /fund-schedule/ | 资金排程历史列表（分页）/ 创建快照 |
| GET/DELETE | /fund-schedule/<id>/ | 资金排程快照详情/删除 |

## 资金排程（FundSchedule 快照式）

核心语义：**预留是打算留作某用途的钱**。流程：手里现金 → 预留（硬性/弹性）→ 剩余可分配。

- **快照式历史**：`FundSchedule` 每次保存新增一条独立记录（无月份唯一约束），`created_at` 倒序，天然支持历史计划列表；不提供更新（PUT/PATCH 返回 405）
- **预留项目**：`reserve_items` JSON 存储 `[{name, amount, type: hard|soft, linked_expense_id}]`；`hard` 硬性承诺（必花）、`soft` 弹性预留
- **服务端权威合计**：`FundScheduleService.compute_totals` 用 Decimal 计算 `total_reserved = Σamount`、`remaining = cash_on_hand - total_reserved`（允许负数），序列化器中合计字段 `read_only`，客户端传值被忽略
- **校验**：`validate_items` 逐项校验名称非空、type 仅 hard/soft、金额非负，违反返回 400
- **固定开销联动**：前端 `getLatestFixedExpense()` 取固定开销计算器最新记录，按 365 天口径（`amount / {daily:1,monthly:30,yearly:365} × 30`，年周期 ÷12.17）折算为月金额，导入为 hard 预留项并带 `linked_expense_id`
