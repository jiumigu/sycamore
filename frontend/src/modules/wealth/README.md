# Wealth — 财务前端

## Views
| 文件 | 职责 |
|------|------|
| `WealthView.vue` | 宏观热力图主页（统计卡+推演面板+图例+热力图） |
| `MonthlyCalendarView.vue` | 月度日历主页（导航+网格+统计） |
| `MonthlyReviewView.vue` | 月度复盘 |
| `RegularDeposit.vue` | 定期存款管理 |
| `CashFlowView.vue` | 现金盘点 |
| `WealthHub.vue` | 财务管理入口（子路由容器） |

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
