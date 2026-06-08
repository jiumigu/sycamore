# Dance — 舞蹈记录

## Models
| Model | Table | 用途 |
|-------|-------|------|
| DanceRecord | hobby_dance_list | 舞蹈记录（managed=False，自动计算 year/month/quarter/weekinfo） |

## Services
DanceStatsService 提供 6 方法：overview / trend / teachers / types / score_trend / calendar

## API Endpoints

前缀 `/api/hobby/dance/records/`

| 方法 | 端点 | 用途 |
|------|------|------|
| GET/POST | / | 列表/创建 |
| GET/PUT/DELETE | /&lt;id&gt;/ | 详情/更新/删除 |
| GET | /stats/ | 总览 |
| GET | /trend/ | 月度趋势 |
| GET | /teachers/ | 老师统计 |
| GET | /types/ | 舞种分布 |
| GET | /score_trend/ | 评分趋势 |
| GET | /calendar/ | 日历数据 |
