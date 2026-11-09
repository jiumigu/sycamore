# Health — 健康管理前端

> 文档对齐 v3.64.7 ｜ 最后核对 2026-10-30

| 文件/组件 | 职责 |
|-----------|------|
| `HealthDashboard.vue` | 首页 —— **只做「每天要干的活」**：筛选栏（年份 / 类型 / 日期范围 / 备注关键字）+ 记录表 + 分页（10 / 20 / 30 / 50，默认 20） |
| `views/overview/HealthOverviewView.vue` | 步数总览页 —— **长期不变的那几块**：超大进度条 + 4 张统计卡 + 完整里程碑地图（点格子看详情）+ 年度步数对比。从首页「📈 步数总览」按钮进 |
| `views/contrib/HealthContribView.vue` | 贡献图页（单日步数热力图），从首页「📊 贡献图」按钮进 |
| `views/MenstrualView.vue` | 好朋友跟踪主页（记录 + 统计 + 趋势）；从首页「🩷 好朋友跟踪」按钮进；路由 `/health/menstrual` |
| `healthApi.ts` | API 调用封装 |
| `healthStore.ts` | Pinia 状态管理（首页只取记录；总览页走 `fetchOverview()` 取 summary / milestones / yearlyComparison） |
| `healthTypes.ts` | 类型定义 |

> **入口（v3.63.12 起）**：体重管理与好朋友跟踪不再占菜单项，改从 `HealthDashboard.vue` 页头按钮进入；两页均补「← 健康管理」回程，路由保持不变。

> **好朋友跟踪的两条口径（v3.64.7 起）**：
> ① 可空日期**不能把 `''` 原样发出去** —— 后端 `DateField` 会把空串判成格式错，
>    「这次还没结束、先不填结束日期」就成了必然失败；`payload` 里统一 `|| null`。
> ② 保存失败走 `shared/utils/apiError.ts`：**4xx 带字段名原样透出**，只写死「保存失败」
>    等于把可行动的信息丢掉。另外表单重置只有 `resetForm()` 一份 —— 新建与关闭共用，
>    否则「编辑过带结束日期的记录 → 关窗 → 新增」会残留上一条的日期。

> 原 `MilestoneMap.vue`（独立里程碑地图页）与首页上的进度条 / 统计卡 / 里程碑预览 / 年度对比图，
> 均已并入 `views/overview/HealthOverviewView.vue`（v3.62.15）—— 旧路径 `/health/milestones`
> 保留一条 redirect 软着陆，避免旧书签撞 404。

### 体重管理 (weight)

| 文件/组件 | 职责 |
|-----------|------|
| `views/weight/WeightDashboard.vue` | 体重管理主页（统计卡片 + 趋势图 + 历史记录分页；页头三枚入口按钮通向下面三个子页面） |
| `views/weight/WeightMonthlyPage.vue` | 子页面「月度进度追踪」（`/health/weight/monthly`，整页展示全部阶段） |
| `views/weight/WeightBmiPage.vue` | 子页面「BMI」（`/health/weight/bmi`，BMI 放大卡 + 身体信息只读 + 区间对照） |
| `views/weight/WeightAdjustmentsPage.vue` | 子页面「目标调整记录」（`/health/weight/adjustments`，当前目标概览 + 完整时间线） |
| `components/weight/WeightSubHeader.vue` | 三个子页面共用页头（返回按钮恒定回 `health-weight`，不用 `router.back()`） |
| `components/weight/MonthlyProgress.vue` | 月度进度追踪卡片（环形进度 + 阶段列表折叠/展开 + 4 项概览；`page-mode` 时全展开且不画卡内标题） |
| `components/weight/BMIStatus.vue` | BMI 状态指示器（`page-mode` 时数字与刻度条放大一档） |
| `components/weight/WeightTrendChart.vue` | 体重趋势 ECharts 折线图（markLine 目标线 + 动态 Y 轴） |
| `components/weight/WeightStatsCards.vue` | 4 张统计卡片 |
| `components/weight/WeightRecordList.vue` | 体重记录列表（后端分页，默认 20 条/页 + 编辑/删除；`total` 取后端 `count`，不是 `records.length`） |
| `components/weight/WeightForm.vue` | 记录添加/编辑弹窗 |
| `components/weight/GoalSettingModal.vue` | 目标设定/调整弹窗 |
| `api/healthApi.ts` | 体重模块 API（`getWeightStats`/`getWeightTrend`/`getWeightGoal`/`getWeightMilestones`/`getWeightAdjustments` 等） |
| `stores/healthStore.ts` | `useWeightStore` — 体重模块 Pinia 状态管理 |
| `types/healthTypes.ts` | 体重模块类型定义（`WeightRecord`/`WeightGoal`/`WeightMilestone`/`WeightGoalAdjustment`/`WeightStats`/`WeightTrend`） |
