# Travel — 旅行记录 + 旅行计划

## Models

| Model | Table | 用途 |
|-------|-------|------|
| TravelRecord | travel_list_info | 旅行记录（managed=False） |
| ChinaCityCoord | china_city_coord | 中国城市坐标（managed=False） |
| TravelPlan | travel_plan | 旅行计划（出发前预算，快照式，user_id=1） |
| TravelPlanItem | travel_plan_item | 旅行计划子项（food/scenic/transport/hotel，预估费用 + 完成状态，可关联心愿 wish） |
| TravelWish | travel_wish | 旅行心愿单（景点/美食等分类 + 省市 + 经纬度 + 状态 想去/已列入计划/已打卡） |

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
| POST | /plans/&lt;pk&gt;/toggle-item/ | 勾选/取消子项完成（body: item_id；已关联心愿时同步心愿状态） |
| GET | /plans/stats/ | 计划统计（total_plans / total_estimate / completed_plans） |
| GET/POST | /wishes/ | 心愿列表（不分页，?category=&status=&province=&city=&search= 筛选）/ 创建（坐标自动解析） |
| GET/PATCH/DELETE | /wishes/&lt;pk&gt;/ | 详情 / 更新 / 删除 |
| POST | /wishes/&lt;pk&gt;/mark_visited/ | 打卡 / 取消打卡（转「已打卡」记日期，取消回「已列入计划」或「想去」） |
| POST | /wishes/&lt;pk&gt;/add_to_plan/ | 加入旅行计划（body: plan_id 或新建 {name,destination,start_date}），生成关联子项 |
| GET | /wishes/stats/ | 心愿统计（total / located / by_status / by_category） |

## 前端

- 路由：`/travel`（旅行记录）、`/travel/wishes`（旅行心愿单）、`/travel/plans`（旅行计划）
- 视图：`modules/travel/views/TravelDashboard.vue`、`TravelWishView.vue`、`TravelPlanView.vue`
- 包含：旅行记录 CRUD、地图展示、统计总览、年份筛选、省市县三级联动；旅行心愿单（地图点亮 + 分类/状态/省份筛选 + 一键加入计划 + 打卡）；旅行计划预算、逐项勾选、统计卡片
