# Travel — 旅行记录

## Models

| Model | Table | 用途 |
|-------|-------|------|
| TravelRecord | travel_list_info | 旅行记录（managed=False） |
| ChinaCityCoord | china_city_coord | 中国城市坐标（managed=False） |

## Services

| Service | 职责 |
|---------|------|
| `MapDataService` | 地图展示数据聚合（省份热力 + 城市气泡） |
| `TravelStatsService` | 旅行统计总览（年度趋势、省份分布） |
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

## 前端

- 路由：`/travel`
- 视图：`modules/travel/views/TravelDashboard.vue`
- 包含：旅行记录 CRUD、地图展示、统计总览、年份筛选、省市县三级联动
