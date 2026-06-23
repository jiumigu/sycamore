# Goals — 目标管理

## Models
| Model | Table | 用途 |
|-------|-------|------|
| Goal | goals_goal | 目标（年度/季度/月度/长期，P0-P3 优先级） |
| Milestone | goals_milestone | 里程碑（按序排列，含奖励同步） |
| Action | goals_action | 行为记录 |
| GoalReview | goals_review | 目标回顾（周/月/里程碑三种回顾类型） |
| OutputRecord | goals_output_record | 良品率记录（类别/质量判定/难度/失败原因/失败类型，含 created_at 月度聚合） |

## Services
- `GoalProgressService`：进度重算（里程碑完成占比）
- `QuickGoalService`：快速创建含批量里程碑模板的目标（月度/季度/每周模板）
- `GoalCloneService`：复制目标及其里程碑和行为
- `MilestoneRewardService`：里程碑完成时同步奖励池
- `calculate_streak`：从 completion_log（`{"date": true}`）计算连续打卡天数（current/longest/total）

## API Endpoints

前缀 `/api/goals/`

| 方法 | 端点 | 用途 |
|------|------|------|
| GET/POST | /goals/ | 列表（?year=&category=&status=&priority= 筛选）/ 创建 |
| GET/PUT/PATCH/DELETE | /goals/&lt;pk&gt;/ | 详情/更新/删除 |
| POST | /goals/quick_create/ | 快速创建（含批量里程碑） |
| POST | /goals/&lt;pk&gt;/clone/ | 复制目标 |
| POST | /goals/&lt;pk&gt;/toggle_milestone/ | 切换里程碑状态 |
| POST | /goals/&lt;pk&gt;/recalculate/ | 手动重算进度 |
| GET | /goals/stats/ | 统计总览 |
| DELETE | /goals/bulk_delete/ | 批量删除 |
| GET/POST | /milestones/ | 里程碑列表（?goal= 筛选）/ 创建 |
| GET/PUT/PATCH/DELETE | /milestones/&lt;pk&gt;/ | 详情/更新/删除 |
| GET/POST | /actions/ | 行为列表（?goal_id=&milestone_id= 筛选）/ 创建 |
| GET/PUT/DELETE | /actions/&lt;pk&gt;/ | 详情/更新/删除 |
| GET | /actions/today_pending/ | 今日未完成行为 |
| POST | /actions/batch/ | 批量创建行为 |
| POST | /actions/&lt;pk&gt;/checkin/ | 今日打卡（更新 completion_log + 完成今日里程碑 + 发放奖励 + 重算进度） |
| GET | /actions/&lt;pk&gt;/checkin_stats/ | 打卡统计（连续天数/里程碑进度/日历数据/完整里程碑列表含编辑字段/里程碑奖励） |
| GET/POST | /reviews/ | 回顾列表/创建 |
| GET/PUT/DELETE | /reviews/&lt;pk&gt;/ | 详情/更新/删除 |
| GET/POST | /outputs/ | 良品率记录列表（?category=&quality=&difficulty= 筛选）/ 创建 |
| GET/PUT/DELETE | /outputs/&lt;pk&gt;/ | 记录详情/更新/删除 |
| GET | /outputs/stats/ | 统计（按类别/难度汇总 + 月度趋势 + 总良品率/容错率/废品率） |
