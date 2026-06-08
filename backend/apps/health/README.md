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
