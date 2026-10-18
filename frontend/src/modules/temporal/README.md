# Temporal — 时间感知前端

| 文件/组件 | 职责 |
|-----------|------|
| `TemporalDashboard.vue` | 时间追踪面板（4分类统计卡+4ECharts+任务表格+CSV导入） |
| `TimeStatsView.vue` | 时间统计首页（`/temporal`）：概览卡 + 记录完整度 + **近 12 周 168h 结构**（`Weekly168Chart`）+ 赎回时间面 mini + 月度趋势 + 旭日图 |
| `TemporalView.vue` | 日记流主页 |
| `temporalStore.ts` | Pinia 状态管理 |
| `temporalApi.ts` | API 调用封装 |
| `temporalTypes.ts` | 类型定义 |

> ⚠️ **`WeeklyTrackingView.vue` 已于 v3.60.34 移除**：它做的是「30h/周达标表」（原
> `/temporal/weekly-tracking` 页），v0.2 设计稿决策 4 废除该基准后按 v0.3 稿改写成 168h 周结构，
> 但**没挂回路由**、功能又已被 `TimeStatsView` 覆盖 ⇒ 连同 `getWeeklyTracking` /
> `refreshWeeklyCache` 两个封装一并删。**168h 周结构在用的调用链**：
> `TimeStatsView` → `temporalStore.fetchWeeklyStructure()` → `getWeeklyStructure` →
> `WeeklyStructureView`（**实时聚合源表**，不读 `temporal_weekly_time_cache` 固化表）。
> 后端 `/weekly-tracking/` 按设计稿刻意保留，**别接回前端**。
