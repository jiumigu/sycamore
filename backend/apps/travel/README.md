# Travel — 旅行记录 + 旅行计划

## Models

| Model | Table | 用途 |
|-------|-------|------|
| TravelRecord | travel_list_info | 旅行记录（managed=False） |
| ChinaCityCoord | china_city_coord | 中国城市坐标（managed=False） |
| TravelPlan | travel_plan | 旅行计划（出发前预算，快照式，user_id=1） |
| TravelPlanItem | travel_plan_item | 旅行计划子项（food/scenic/transport/hotel，预估费用 + 完成状态） |

## Services

| Service | 职责 |
|---------|------|
| `MapDataService` | 地图展示数据聚合（省份热力 + 城市气泡） |
| `TravelStatsService` | 旅行统计总览（年度趋势、省份分布） |
| `TravelPlanService` | 旅行计划业务：`recalculate_total` 重算子项合计、`get_stats` 计划统计 |
| `get_coordinates()` | 城市名→经纬度（含区县到地级市回退） |
| `get_province()` | 城市名→所属省份 |

## API Endpoints

前缀 `/api/travel/`

| 方法 | 端点 | 用途 |
|------|------|------|
| GET/POST | /records/ | 记录列表（分页，?year=&province= 筛选）/ 创建（自动地理编码） |
| GET/PUT/DELETE | /records/&lt;pk&gt;/ | 详情 / 更新 / 删除 |
| GET | /map/data/ | 地图数据（省份热力 + 城市气泡，?year_from=&year_to=） |
| GET | /stats/ | 统计总览（?year_from=&year_to=） |
| GET | /provinces/ | 到访省份列表 |
| GET | /years/ | 旅行年份列表 |
| GET/POST | /plans/ | 计划列表 / 创建（POST 带 items，服务端自动汇总 total_estimate） |
| GET/PUT/DELETE | /plans/&lt;pk&gt;/ | 详情 / 更新（重算合计）/ 删除 |
| GET | /plans/&lt;pk&gt;/items/ | 计划子项列表 |
| POST | /plans/&lt;pk&gt;/toggle-item/ | 勾选/取消子项完成（body: item_id） |
| GET | /plans/stats/ | 计划统计（total_plans / total_estimate / completed_plans） |

## 前端

- 路由：`/travel`（旅行记录）、`/travel/plans`（旅行计划）
- 视图：`modules/travel/views/TravelDashboard.vue`、`TravelPlanView.vue`
- 包含：旅行记录 CRUD、地图展示、统计总览、年份筛选、省市县三级联动；旅行计划预算、逐项勾选、统计卡片
