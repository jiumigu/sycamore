# Goals — 目标管理前端

## Views

| 文件 | 职责 |
|------|------|
| `GoalHub.vue` | 目标总览（页头含「人生维度分布 / 快速创建 / 手动创建 / 刷新」+ 动态统计卡点击筛选 + 搜索/优先级/状态/类别筛选 + 看板卡片墙 + 勾选批量操作） |
| `GoalDetail.vue` | 目标详情/编辑弹窗（表单：标题/类别(含项目目标)/优先级/生命周期/人生维度/标签/备注 + 里程碑网格 + 行为时间线 + 回顾 + 父目标选择器） |
| `DimensionChart.vue` | 人生维度雷达图（按维度聚合目标数与平均进度） |

## Components

| 文件 | 职责 |
|------|------|
| `GoalCard.vue` | 目标卡片（进度环/状态/优先级/日期区间/截止倒计时/标签/里程碑计数 + 展开区含里程碑或行为追踪 + 编辑/复制/删除） |
| `CountdownBadge.vue` | 截止倒计时徽章（无截止日期/已过期/🔥≤3天/⚠️≤7天/📅N天，按剩余天数分级着色） |
| `MilestoneBoard.vue` | 里程碑面板（列表/勾选完成/展开详情） |
| `BehaviorTrackCard.vue` | 行为追踪打卡卡（连续天数/进度条/打卡按钮/日历热力图/里程碑列表含折叠与编辑弹窗） |
| `ActionDrawer.vue` | 行为记录抽屉（按目标查看/新增行为） |
| `CreateActionDialog.vue` | 创建行为弹窗 |
| `QuickGoalDialog.vue` | 快速创建弹窗（频率模板 + 批量里程碑 + 奖励设置） |

## Store

| Store | 职责 |
|-------|------|
| `goalStore.ts` | 目标主状态（goalList/currentGoal/stats + CRUD + 里程碑/状态切换 + 快速创建 + 复制） |
| `goalBoardStore.ts` | 看板状态（勾选目标 ID 集合 + 行为缓存 actionsCache: goalId→Action[]） |

## API / Types

- `api/goalApi.ts`：目标/里程碑/行为/回顾/良品率 CRUD + quick_create/clone/stats/dimension_stats/checkin 等端点封装
- `types/goalTypes.ts`：`Goal`/`Milestone`/`Action`/`GoalStats` 等类型 + `CATEGORY_OPTIONS`（含「📋 项目目标」）/`PRIORITY_OPTIONS`/`STATUS_OPTIONS`/`DIMENSION_OPTIONS` 常量
