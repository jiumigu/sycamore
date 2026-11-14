# Travel — 旅行记录 + 旅行计划

> 文档对齐 v3.64.52 ｜ 最后核对 2026-11-11

## Models

| Model | Table | 用途 |
|-------|-------|------|
| TravelRecord | travel_list_info | 旅行记录（managed=False） |
| ChinaCityCoord | china_city_coord | 中国城市坐标（managed=False） |
| TravelPlan | travel_plan | 旅行计划（出发前预算，快照式，user_id=1）。⚠️ v3.64.50 起 `destination` **降级为派生值**（= 最后一站的城市名），真正的路线在 `TravelPlanStop` |
| TravelPlanStop | travel_plan_stop | **路线站点**（v3.64.50）：一条路线上的有序城市，`(plan, order)` 唯一，`days` 可空（未知 ≠ 0）。坐标与到达日期**不落库**，由 `TravelPlanService` 现算 |
| TravelPlanItem | travel_plan_item | 旅行计划子项（food/scenic/transport/hotel，预估费用 + 完成状态，可关联心愿 wish）。`stop` 为空 = 城际交通（「路上」，不属于任何城市）；`stop` 的删除是 **PROTECT** |
| TravelWish | travel_wish | 旅行心愿单（景点/美食等分类 + 省市区县 + 经纬度 + 状态 想去/已列入计划/已打卡 + 打卡记录：日期/评分/评价/值得反复 + visit_plan 归属行程 + visit_record_id 已沉淀足迹） |

### 路线的三层结构（v3.64.50）

```
计划 TravelPlan
├── 站点 TravelPlanStop (order 1..n)      ← 宁德 → 泉州 → 漳州 → 潮州 → 广州
│   └── 条目 TravelPlanItem (stop=该站)   ← 该城的美食 / 打卡 / 住宿 / 当地交通
└── 城际交通 TravelPlanItem (stop=NULL)   ← 宁德→泉州 高铁，单列，不摊进任何城市
```

🔴 金额三层只由 `TravelPlanService.totals()` 算一次：
**本站合计 = Σ 本站条目**、**城际交通 = Σ `stop IS NULL`**、**计划总额 = 两者之和**（写回 `total_estimate`）。
三层都从同一个分组查询 `subtotals()` 派生（键 `None` = 不归属任何城市），**不许再各写一次 filter**。

🔴 **单站 = 多站路线的特例**（不是两套概念）：
老弹窗只填一个「目的地」时，`perform_create` 会建出唯一一站，且没写 `stop` 的条目默认归它
（`sole_stop()`）—— 与迁移把老计划条目全挂到唯一一站上同一口径。两站以上才留空、进「路上」。

🔴 **`PROTECT` 会连「删整条计划」一起挡下来**：`perform_destroy` 必须显式按序删
（条目 → 站点 → 计划），否则「有计划 → 有站 → 站下有条目」的删除报 `ProtectedError`（500）。

🔴 **`destination` 只读、顶层 `items` 已删**（v3.64.52）：
`destination` 是派生值（= 末站城市名），建计划指定城市请走 `stops`；
条目只出现在 `stops[].items` 与 `transfer_items` 两处，**同一批条目不给第三个出口**
—— 三个出口里只要有一个读到旧的那份，「归属」就又变成两把尺子。

## Services

| Service | 职责 |
|---------|------|
| `MapDataService` | 地图展示数据聚合（**地级市热力** + 城市气泡）：`heatmap` 项为 `{name, count, level, sources}`（level 取 偶尔/多次/频繁/深度游；`sources` 为计数来源明细，如宁德市含「福鼎市×1、寿宁县×1」），另返回 `heat_max`；气泡按坐标表**规范名归并**（「温州」+「温州市」= 一个气泡），同 `tname` 的多次到访聚合为一次气泡并累加次数/花费/年份 |
| `resolve_prefecture(city, parent)` | 把「城市 + 上级」归到地级市（tname 本身是地级市 / tname 是县级市或区县则取其 parentnode / 直辖市保留区名）；索引来自 `toolkit_city_coordinate` 的地级市·自治州·地区·盟，进程内缓存，`reset_prefecture_index()` 可失效 |
| `heat_level(count)` | 到访次数 → 热力档位（1=偶尔 / 2=多次 / 3-4=频繁 / ≥5=深度游） |
| `bubble_size(total_cost, count)` | 城市气泡直径唯一实现（v3.64.2）：花费与次数**开方压缩**后才进 `BUBBLE_SIZE_MIN=8 / MAX=20` 区间；旧公式 1250 元就撞 50px 上限，几乎每座城同样大。改上限不是解法，先验「真实数据多久饱和」 |
| `TravelStatsService` | 旅行统计总览（年度趋势、省份分布） |
| `TravelPlanService` | 旅行计划业务。金额：`subtotals(plan)`（**按站分组一次算完**，键 `None`=不归属城市）、`totals()` 三层从它派生、`stop_subtotal(stop)`、`recalculate_total(plan)`（同时同步派生 `destination`）；站点：`add_stop()` / `sole_stop()`（只一站时返回它，用于「没写 stop 的条目默认归它」）/ `reorder_stops()`（**必须整份给 id**，内部两趟写入绕开唯一约束）/ `arrive_dates()`（任一前置站 `days` 为空 ⇒ 其后全部 None）/ `total_days()`（任一站未知 ⇒ `None`，不当 0 加）；另有 `get_stats()` |
| `TripLogService` | 行程日志：把已打卡心愿按「日期 + 地点」聚合为一天一张卡（含已沉淀足迹回填） |
| `norm_place()` / `place_key()` | 地点名归一（优先城市、缺省省份；`place_key` 剥离行政后缀做分组键，不剥离单字「州」） |
| `resolve_place()` | 地名 → `(规范名, lat, lng)`：查 `toolkit_city_coordinate`（全称/去后缀简称，带省份时本省优先，县级市用自身点位），硬编码表兜底 |
| `get_coordinates()` | `resolve_place()` 的薄封装，只取经纬度（含区县到地级市回退） |
| `get_province()` | 城市名→所属省份（硬编码表 + 坐标表兜底） |
| `resolve_prefecture()` | 城市 + 上级 → 地级市（热力着色用，索引进程内缓存、`reset_prefecture_index()` 失效） |

## API Endpoints

前缀 `/api/travel/`

| 方法 | 端点 | 用途 |
|------|------|------|
| GET/POST | /records/ | 记录列表（分页，?year=&province= 筛选）/ 创建（自动地理编码） |
| GET/PUT/DELETE | /records/&lt;pk&gt;/ | 详情 / 更新 / 删除 |
| GET | /map/data/ | 地图数据（地级市热力项含 `sources` 来源明细 + 城市气泡，?year_from=&year_to=） |
| GET | /stats/ | 统计总览（?year_from=&year_to=） |
| GET | /provinces/ | 到访省份列表 |
| GET | /years/ | 旅行年份列表 |
| GET | /trip-log/ | 行程日志（已打卡心愿按日期+地点聚合，?from=&to=&plan=&city=） |
| POST | /trip-log/consolidate/ | 把某天某地的打卡清单沉淀为一条旅行足迹（body: date/city/tcost/rating/duration_days/companions/tremark），只新增不改存量 |
| GET/POST | /plans/ | 计划列表（站点**不含** `items`，列表不需要条目）/ 创建（body 带 `stops: [{city, days?}]` 一次建整条路线，`items` 用 `stop_index` 指认归属；只填一个 `destination` 的**老调用方**仍按「唯一一站」兼容） |
| GET/PATCH/DELETE | /plans/&lt;pk&gt;/ | 详情（三层：`stops[]` + `transfer_items[]` + `stops_total`/`transfer_total`/`total_estimate`/`total_days`）/ 更新（重算合计；`destination` 只读）/ 删除（先删条目再删站，绕开 PROTECT） |
| GET/POST | /plans/&lt;pk&gt;/items/ | 子项列表（含 `stop`）/ 新增一条（body 带 `stop`，缺省归「唯一一站」） |
| DELETE | /plans/&lt;pk&gt;/items/&lt;iid&gt;/ | 删一条（带心愿 ⇒ 心愿退回「想去」）。存在的理由：老界面靠「编辑弹窗整份替换」删条目，那条路已拆 |
| POST | /plans/&lt;pk&gt;/items/&lt;iid&gt;/move/ | 条目挪站（body `{stop: 32}`，挪到路上必须**显式** `null`；跨计划的 stop ⇒ 400） |
| POST | /plans/&lt;pk&gt;/stops/ | 加一站（body: city/province?/days?/notes?，追加到末尾；返回该站完整出参） |
| PATCH/DELETE | /plans/&lt;pk&gt;/stops/&lt;sid&gt;/ | 改站（城市/天数/备注，事后重算到达日期与派生 `destination`）/ 删站（有条目 ⇒ 400 并列出挡路的条目，**不级联**；空站 204 且总额重算） |
| POST | /plans/&lt;pk&gt;/stops/reorder/ | 重排全部站点（body: `{order: [31,33,32]}`，**必须整份给**；只动 `order`，不动金额与归属） |
| POST | /plans/&lt;pk&gt;/toggle-item/ | 勾选/取消子项完成（body: item_id；已关联心愿时同步心愿状态） |
| GET | /plans/stats/ | 计划统计（total_plans / total_estimate / completed_plans） |
| POST | /plans/route-preview/ | 路线预检：按站返回该城「想去」心愿（body: destinations） |
| POST | /plans/from-route/ | 由路线生成计划（body: name/origin/destinations/start_date/wish_ids），勾选心愿则挂 wish 并转「已列入计划」 |
| GET/POST | /wishes/ | 心愿列表（不分页，?category=&status=&province=&city=&search= 筛选）/ 创建（坐标自动解析） |
| GET/PATCH/DELETE | /wishes/&lt;pk&gt;/ | 详情 / 更新 / 删除 |
| POST | /wishes/&lt;pk&gt;/mark_visited/ | 打卡 / 取消打卡（转「已打卡」记日期，取消回「已列入计划」或「想去」） |
| POST | /wishes/&lt;pk&gt;/record_visit/ | 打卡记录（body: visited_at / visit_rating 1-5 / visit_notes / worth_revisit）；已打卡再调即修改记录 |
| POST | /wishes/&lt;pk&gt;/add_to_plan/ | 加入旅行计划（body: plan_id 或新建 {name,destination,start_date}），生成关联子项 |
| GET | /wishes/stats/ | 心愿统计（total / located / by_status / by_category） |

## 前端

- 路由：`/travel`（旅行足迹：地图 + 行程日志双视图）、`/travel/wishes`（心愿单）、`/travel/plans`（计划）、`/travel/route`（路线推演，主入口已从工具箱迁入）
- 视图：`modules/travel/views/TravelDashboard.vue`、`TravelWishView.vue`、`TravelPlanView.vue`、`TravelRouteView.vue`
- 包含：旅行记录 CRUD、地图展示、统计总览、年份筛选、省市县三级联动；行程日志（打卡按天聚合 + 沉淀为足迹）；旅行心愿单（地图点亮且随筛选联动缩放 + 分类/状态/省市区县筛选 + 一键加入计划 + 打卡记录：日期/评分/评价/值得反复）；旅行计划预算、逐项勾选（关联心愿时弹打卡录入）、统计卡片、查看路线；路线推演（路线预设 + 小火车动画 + 生成旅行计划并带入心愿）
