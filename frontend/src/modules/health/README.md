# Health — 健康管理前端

| 文件/组件 | 职责 |
|-----------|------|
| `HealthDashboard.vue` | 首页 —— **只做「每天要干的活」**：筛选栏（年份 / 类型 / 日期范围 / 备注关键字）+ 记录表 + 分页（10 / 20 / 30 / 50，默认 20） |
| `views/overview/HealthOverviewView.vue` | 步数总览页 —— **长期不变的那几块**：超大进度条 + 4 张统计卡 + 完整里程碑地图（点格子看详情）+ 年度步数对比。从首页「📈 步数总览」按钮进 |
| `views/contrib/HealthContribView.vue` | 贡献图页（单日步数热力图），从首页「📊 贡献图」按钮进 |
| `healthApi.ts` | API 调用封装 |
| `healthStore.ts` | Pinia 状态管理（首页只取记录；总览页走 `fetchOverview()` 取 summary / milestones / yearlyComparison） |
| `healthTypes.ts` | 类型定义 |

> 原 `MilestoneMap.vue`（独立里程碑地图页）与首页上的进度条 / 统计卡 / 里程碑预览 / 年度对比图，
> 均已并入 `views/overview/HealthOverviewView.vue`（v3.62.15）—— 旧路径 `/health/milestones`
> 保留一条 redirect 软着陆，避免旧书签撞 404。

### 体重管理 (weight)

| 文件/组件 | 职责 |
|-----------|------|
| `views/weight/WeightDashboard.vue` | 体重管理主页（统计卡片 + 月度进度 + BMI + 趋势图 + 目标调整记录 + 记录列表） |
| `components/weight/MonthlyProgress.vue` | 月度进度追踪卡片（环形进度 + 阶段列表折叠/展开 + 4 项概览） |
| `components/weight/BMIStatus.vue` | BMI 状态指示器 |
| `components/weight/WeightTrendChart.vue` | 体重趋势 ECharts 折线图（markLine 目标线 + 动态 Y 轴） |
| `components/weight/WeightStatsCards.vue` | 4 张统计卡片 |
| `components/weight/WeightRecordList.vue` | 体重记录列表（分页 + 编辑/删除） |
| `components/weight/WeightForm.vue` | 记录添加/编辑弹窗 |
| `components/weight/GoalSettingModal.vue` | 目标设定/调整弹窗 |
| `api/healthApi.ts` | 体重模块 API（`getWeightStats`/`getWeightTrend`/`getWeightGoal`/`getWeightMilestones`/`getWeightAdjustments` 等） |
| `stores/healthStore.ts` | `useWeightStore` — 体重模块 Pinia 状态管理 |
| `types/healthTypes.ts` | 体重模块类型定义（`WeightRecord`/`WeightGoal`/`WeightMilestone`/`WeightGoalAdjustment`/`WeightStats`/`WeightTrend`） |
