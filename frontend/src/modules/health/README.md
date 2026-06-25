# Health — 健康管理前端

| 文件/组件 | 职责 |
|-----------|------|
| `HealthDashboard.vue` | 主页（进度条+4统计卡+里程碑网格+3ECharts+CRUD） |
| `MilestoneMap.vue` | 5×10里程碑网格+详情弹窗 |
| `healthApi.ts` | API 调用封装 |
| `healthStore.ts` | Pinia 状态管理 |
| `healthTypes.ts` | 类型定义 |

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
