# Health — 健康管理

## Models
| Model | Table | 用途 |
|-------|-------|------|
| HealthRecord | health_step_info | 健康记录（managed=False，自动计算 total/years） |

## Services
HealthStatsService 提供 8 方法：summary / milestones / daily_trend / calendar / timeline / type_stats / yearly_comparison

## Constants
- 目标：1 亿步 = 50 里程碑 × 200 万步
- 转换系数：步数(1:1) / 跳绳(1个:0.5步) / 跑步(1km:1300步) / 骑行(1km:400步)

## API Endpoints

前缀 `/api/health/records/`

| 方法 | 端点 | 用途 |
|------|------|------|
| GET/POST | / | 列表/创建 |
| GET/PUT/DELETE | /&lt;hid&gt;/ | 详情/更新/删除 |
| GET | /summary/ | 目标总览 |
| GET | /milestones/ | 50个里程碑状态 |
| GET | /daily_trend/ | 每日步数趋势 |
| GET | /calendar/ | 日历热力图 |
| GET | /milestone_timeline/ | 里程碑时间线 |
| GET | /type_stats/ | 运动类型占比 |
| GET | /yearly_comparison/ | 年度步数对比 |

## 体重管理 (weight)

### Models
| Model | Table | 用途 |
|-------|-------|------|
| WeightRecord | health_weight_record | 每日体重记录（kg/bmi/body_fat） |
| WeightGoal | health_weight_goal | 减重目标（起止体重/月目标/当前月/状态） |
| WeightMilestone | health_weight_milestone | 月度里程碑（每月目标/是否达成） |
| WeightGoalAdjustment | health_weight_goal_adjustment | 目标调整流水（调整前/后值/原因） |
| UserBodyInfo | health_user_body_info | 身体信息（身高/性别/年龄） |

### Services
`WeightService` 提供：
- `get_stats` — 统计概览（当前/目标体重、总体进度、月度进度、BMI）
- `get_trend` — 体重趋势 + 里程碑标记数据
- `create_goal` — 创建/调整目标，自动生成里程碑，记录调整流水
- `check_weight_goal_status` — 检查里程碑达成状态，自动推进 `current_month`

### API Endpoints

前缀 `/api/health/weight/`

| 方法 | 端点 | 用途 |
|------|------|------|
| GET/POST | /records/ | 体重记录列表/创建 |
| GET/PUT/DELETE | /records/&lt;id&gt;/ | 记录详情/更新/删除 |
| GET | /stats/ | 统计概览 |
| GET | /trend/ | 趋势数据 |
| GET/POST | /goal/ | 获取/创建活跃目标 |
| GET | /milestones/ | 月度里程碑列表 |
| GET/PUT | /body-info/ | 身体信息获取/更新 |
| GET | /adjustments/ | 目标调整流水 |
