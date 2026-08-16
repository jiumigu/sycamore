# Wealth — 财务前端

## Views
| 文件 | 职责 |
|------|------|
| `WealthView.vue` | 宏观热力图主页（统计卡+推演面板+图例+热力图） |
| `MonthlyCalendarView.vue` | 月度日历主页（导航+网格+统计） |
| `MonthlyReviewView.vue` | 月度复盘 |
| `RegularDeposit.vue` | 定期存款管理 |
| `CashFlowView.vue` | 现金盘点 |
| `AllocationBoard.vue` | 资金排程 + 分配计划看板（手头现金/硬性承诺/预留分配/自由支配 + 决策记录，路由 `/wealth/fund`） |
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

## 资金排程 + 分配计划（AllocationBoard）

核心逻辑：**分配是计划（预留），不是记录（花费）**。流程：手头现金 → 硬性承诺 → 预留分配 → 自由支配。

- 四张核心卡：手头现金（可编辑）/ 硬性承诺 / 预留分配 / 自由支配
- 预留分配计划：5 个默认类别（投资/日常生活/精神愉悦-旅游美食/家居装修/风险预估-留底钱），可按类别设置预留金额
- 硬性承诺：手动添加/删除（未来必须花的钱）
- 自由决策：记录自由支配打算怎么花（save/learn/travel/home/venture）

后端：`backend/apps/wealth/models/allocation_plan.py` + `services/allocation_service.py` + `views/allocation_views.py`，API 前缀 `/api/wealth/allocation/`（detail/create/update-allocations/record-spending/save-decision/categories）。
分配类别通过 `manage.py init_allocation_categories` 初始化。
