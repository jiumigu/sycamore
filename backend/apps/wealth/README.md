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
