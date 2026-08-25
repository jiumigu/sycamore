# Wealth — 财务前端

## Views
| 文件 | 职责 |
|------|------|
| `WealthView.vue` | 宏观热力图主页（统计卡+推演面板+图例+热力图） |
| `MonthlyCalendarView.vue` | 月度日历主页（导航+网格+统计） |
| `MonthlyReviewView.vue` | 月度复盘 |
| `RegularDeposit.vue` | 定期存款管理 |
| `CashFlowView.vue` | 现金盘点 |
| `FundScheduleBoard.vue` | 资金排程看板（手里现金/预留硬性·弹性/剩余可分配 + 历史快照列表 + 导入固定开销，路由 `/wealth/fund`） |
| `WealthHub.vue` | 财务管理入口（子路由容器，含「资金排程」tab） |

## Components
| 文件 | 职责 |
|------|------|
| `HeatmapGrid.vue` | 61行×52列 CSS Grid 热力图 |
| `ControlPanel.vue` | 推演输入+结果+进度条 |
| `Legend.vue` | 收支等级图例 |
| `WeekDetailModal.vue` | 周明细弹窗 |
| `monthly/` | 月度日历子组件（CalendarHeader/CalendarGrid/StatsFooter/DayDetailModal） |
| `common/QuickBillForm.vue` | 快速记账表单 |
| `common/LunarUtil.js` | 农历/节气/节日计算 |
| `regular/RegularStatsCards.vue` | 定期统计卡 |
| `regular/ExpiringAlert.vue` | 到期提醒列表 |
| `regular/RegularFilter.vue` | 筛选栏 |
| `regular/RegularForm.vue` | 创建/编辑弹窗 |
| `regular/MatureHandler.vue` | 到期处理弹窗 |
| `cashflow/AssetOverview.vue` | 资产全景卡片（11项资产分布） |
| `cashflow/AssetTrend.vue` | 资产趋势折线图（ECharts） |
| `cashflow/HealthMetrics.vue` | 健康指标卡片（负债率/自由资金等） |
| `cashflow/SnapshotHistory.vue` | 盘点历史列表（15列全字段 + 隐私脱敏 + 分页） |

## 资金排程（FundScheduleBoard）

核心逻辑：**预留是打算留作某用途的钱**。流程：手里现金 → 预留（硬性/弹性）→ 剩余可分配。每次保存生成一条历史快照。

- 顶部：手里现金（可编辑）+ 计划名称
- 预留项：硬性承诺（hard，红标）/ 弹性预留（soft，橙标）可增删，逐项设置名称与金额
- 汇总：手里现金 / 预留合计 / 剩余可分配（负数红色警示）；恒等式 `现金 = 预留 + 剩余` 由单一派生链保证（结构性消除二次扣减 bug），另留 `balanceMismatch` 警示兜底
- 保存计划 → 新增一条历史快照并清空表单
- 历史列表：计划名称/手里现金/预留合计/剩余可分配/日期 + 查看/删除
- 导入固定开销：弹出固定开销历史记录选择弹窗（名称/月开销/日开销/项目数/创建日期 + 选中预览部分项目），可选任意一条导入，按 365 天口径（年周期 ÷12.17）折算月金额导入为硬性承诺，带 `linked_expense_id`

后端：`backend/apps/wealth/models/fund_schedule.py` + `services/fund_schedule_service.py` + `views/fund_schedule_views.py`，API 前缀 `/api/wealth/fund-schedule/`（list/create/detail/delete，无 update）。
