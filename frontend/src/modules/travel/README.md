# Travel — 旅行记录 + 旅行心愿单 + 旅行计划 + 路线推演前端

> 文档对齐 v3.64.53 ｜ 最后核对 2026-11-11

## Views

| 文件 | 路由 | 职责 |
|------|------|------|
| `TravelDashboard.vue` | /travel | 旅行足迹主页（「🗺️ 足迹地图 / 📔 行程日志」双视图：地图视图=统计卡 + 年份筛选 + 中国地图热力/气泡 + 趋势/省份图表 + 记录 CRUD；日志视图=打卡按「日期+地点」聚合的一天一卡 + 沉淀为足迹） |
| `TravelWishView.vue` | /travel/wishes | 旅行心愿单（统计 chips + 中国地图心愿点亮并随筛选联动缩放 + 分类/状态/省市区县/搜索筛选 + 按省份分组卡片 + 打卡记录弹窗（日期/归属行程/评分/评价/值得反复）+ 一键加入计划） |
| `TravelPlanView.vue` | /travel/plans | 旅行计划（4 统计卡 + 新建弹窗**路线编辑器**（按顺序填站，无「目的地」输入）+ 可展开计划列表：标题行「宁德 → 泉州 → … → 广州」「5 站 · 8 天 · ¥4,860」，展开后是**站点折叠**（每站自己的到达日/天数/本站合计/四类计数/条目 + 「路上」城际交通块 + 三层合计条）；每行「🗺 地图」打开**计划内地图抽屉**） |
| `TravelRouteView.vue` | /travel/route | 路线推演（路线预设抽屉 + 小火车沿路线动画 + 生成旅行计划弹窗：逐站勾选带入本城心愿）；原在工具箱，2026-09-11 迁入旅行模块作为主入口 |

> **入口（v3.63.8 起）**：旅行心愿单 `/travel/wishes`、路线推演 `/travel/route` 从「旅行计划」页头进入；美食地图 `/food` 从「旅行足迹」页头进入。三者不再占菜单项，路由与数据保留。

## Components

| 文件 | 职责 |
|------|------|
| `ChinaHeatmap.vue` | ECharts 中国**地级市**热力 + **省界叠加** + 城市气泡三层（显式 `geo` 组件 + 热力层 `map` 系列 `geoIndex: 0` 绑定；`visualMap` 分段 4 档并限定 `seriesIndex: 0`，避免把气泡一起染色；`lines` 系列以 polyline 画省界、`silent`；**地市名与气泡名默认隐藏，悬停/点击才显示**，tooltip 对地级市额外列出 `sources` 来源明细）。气泡直径由后端 `bubble_size` 下发（v3.64.2），前端兜底取区间下限 8、先读 `params.data.size` 再读 `params.size` |
| `plan/PlanStopList.vue` | 站点层容器：站点列表 + 加站 + 上下移（`reorder` **整份 id**）+ 删站（400 带 `blocking` 时把条目名列出来）+ 「路上（城际交通）」块 + 三层合计条。🔴 **整份列表只放一个打卡弹窗** —— 每个条目一个会白挂 100 多个隐藏实例 |
| `plan/PlanStopRow.vue` | 单站一行：站序 / 城市（未定位标记）/ 天数 / 到达日 / 本站合计 / 四类计数 / 上下移·编辑·删除；展开后是条目清单 + 行内加条目（**显式带 `stop`**，多站计划不写它会掉进「路上」） |
| `plan/PlanItemRow.vue` | 单条条目（只负责显示 + 抛事件）：勾选、图标、名称、心愿标记、金额、**「挪到别站 / 挪到路上」下拉**、删除（悬停才显形） |
| `plan/PlanRouteMap.vue` | 计划内地图（抽屉里）：按站序把**能定位的相邻站**连线（两端有一端没定位就断开并说明）+ 圈内数字=站序的圆点 + 右侧站序表（每行 `站序 城市 天数 ¥本站合计`）与选中站明细（到达日/合计/四类计数/条目，**只读**）。点圆点或点行都切换选中站 |

> 🔴 **展开计划才取详情**：列表接口不带 `stops[].items`。拿列表数据直接展开，每一站都是「还没有条目」，看着像数据丢了 —— 详情与列表是两个接口，别混用。
>
> 🔴 **地图在抽屉里，抽屉是 teleport 到 body 的**：`scoped` 的 `:deep(.el-drawer__body)` 够不到它（`.map-drawer` 上没有 `data-v`），规则会**静默失效** —— 现象是画布高度塌成 400px、地图挤在上半屏。给抽屉内部节点写样式要用**非 scoped** 的一段，选择器收窄到 `.map-drawer`。
>
> ⚠️ **地图只读**：勾完成会走「打卡并记录」的完整弹窗流程，那套逻辑只有 `PlanStopList` 一份；地图侧栏再实现一遍就是两把尺子。侧栏底部已写明「勾完成、加条目请回清单」。

## Utils

| 文件 | 职责 |
|------|------|
| `chinaCitiesMap.ts` | 全国地级市底图：把 `better-echarts-maps` 的 `china-provinces.js`（按省打包的 38 份地级市 GeoJSON）合并成一张 493 区域的地图并注册为 `china-cities`；`resolveRegionName()` 做容错对齐（精确 → 去后缀补后缀 → 旧称别名），未对齐返回 `null`；`getProvinceBorderRings()` 从 `china.js` 取 34 个省级单位的边界环（约 2600 点）供省界叠加层使用 |
| `chinaProvinceMap.ts` | 全国**省级**底图注册（`registerChinaProvinceMap()`，幂等，返回 `PROVINCE_MAP_NAME`）。🔴 「从 `better-echarts-maps` 取出 `China[0][1]` 再注册」原先在 3 个页面各抄一遍（心愿 / 推演 / 计划地图），两处还用不同的兜底运算符 —— 直接注册模块对象会让省界碎成乱线，统一在这里 |
| `routeView.ts` | `fitRouteView(coords)`：一组经纬度 → 地图中心与缩放（唯一实现，推演页与计划地图共用）。阈值是经验刻度，**与画布尺寸相关**，只保证相近量级给相近缩放；没有可定位点时才用兜底视野 |
| `stopText.ts` | 站点文案唯一实现：`daysLabel`（`null`=天数待定 / `0`=路过不过夜 / `N 天`）、`arriveLabel`（`12/02 到` / `到达待定`）、`countChips`（四类只列非零）。清单行与地图侧栏共用，避免一条数据两个界面说得不一样 |

## Store

`useTravelStore`（`stores/travelStore.ts`，Composition API）— 管理旅行记录数据

| 状态 | 类型 | 说明 |
|------|------|------|
| `records` | `TravelRecord[]` | 当前页记录 |
| `total` / `currentPage` / `pageSize` | 分页 | 分页状态 |
| `mapData` | `MapData \| null` | 地图数据（热力 + 气泡） |
| `stats` | `TravelStats \| null` | 统计总览 |
| `years` | `number[]` | 年份筛选列表 |
| `loading` | `boolean` | 加载状态 |

| 方法 | 用途 |
|------|------|
| `fetchRecords()` | 获取列表（处理分页 response） |
| `setPage()` | 翻页 |
| `fetchMapData()` / `fetchStats()` | 地图/统计 |
| `fetchYears()` | 年份列表 |
| `createRecord()` / `updateRecord()` / `deleteRecord()` | CRUD（成功后刷新列表） |

> 旅行计划页不经过 store，直接走 `api/travelApi.ts`。

## API

`api/travelApi.ts`

- 旅行记录：`getTravelRecords` `getTravelRecordDetail` `createTravelRecord` `updateTravelRecord` `deleteTravelRecord`
- 地图/统计：`getMapData` `getTravelStats` `getProvinceList` `getYearList`
- 行程日志：`getTripLog`（GET `/trip-log/`，params `{from,to,plan,city}`）`consolidateTripDay`（POST `/trip-log/consolidate/`）
- 旅行计划：`getTravelPlans` `getTravelPlanDetail` `createTravelPlan`（可带 `stops` + `items[].stop_index`，一次建整条路线）`updateTravelPlan`（**PATCH**：非 partial 的 PUT 会把没传的 `status`/`notes` 重置成模型默认值）`deleteTravelPlan`
  `getTravelPlanItems` `getTravelPlanStats` `toggleTravelPlanItem`（POST `/plans/<id>/toggle-item/`，body `{item_id}`）
- 站点：`addPlanStop` `updatePlanStop` `deletePlanStop` `reorderPlanStops`（body `{order: [全部站点 id]}`）
- 条目：`addPlanItem`（`stop` 可为 `null` = 路上）`deletePlanItem` `movePlanItem`（挪到路上必须显式 `null`）
- 路线 → 计划：`getRoutePreview`（POST `/plans/route-preview/`）`createPlanFromRoute`（POST `/plans/from-route/`）
- 心愿：`getWishes` `createWish` `updateWish` `deleteWish` `getWishStats` `markWishVisited` `recordWishVisit` `addWishToPlan`
- 路线预设（仍走工具箱接口）：`getTravelRoutes` `createTravelRoute` `updateTravelRoute` `deleteTravelRoute`（`modules/toolkit/api/toolkitApi.ts`）

## Types & Constants

`types/travelTypes.ts`

| 接口 | 用途 |
|------|------|
| `TravelRecord` / `TravelFormData` | 旅行记录 / 表单 |
| `MapData` / `HeatmapItem` / `BubbleItem` | 地图数据（`HeatmapItem` = 地级市名 + 到访次数 + 档位 + `sources` 来源明细；`MapData` 另含 `heat_max`） |
| `TravelStats` / `YearlyTrend` / `ProvinceDist` | 统计总览 |
| `TravelPlan` / `TravelPlanStop` / `TravelPlanItem` / `TravelPlanStats` | 旅行计划（含 `stops[]` / `transfer_items[]` / `stops_total` / `transfer_total` / `total_days`）/ 站点（`city` 规范名 + `city_input` 原样 + `days: number \| null` + `arrive_date` + `located` + `subtotal` + `counts`）/ 子项 / 统计 |
| `TravelPlanInput` / `TravelPlanPatch` / `TravelPlanStopInput` / `TravelPlanItemInput` | 计划（新建，含 `stops`）/ 计划（改基本信息，PATCH）/ 站点 / 子项（新建时用 `stop_index`，已有计划用 `stop`） |
| `TravelWish` / `WishStats` / `WishStatus` / `TravelPlanOption` | 心愿单 / 统计 / 状态 / 计划下拉项 |
| `TripLog` / `TripLogDay` / `TripLogItem` / `TripLogRecord` / `ConsolidatePayload` | 行程日志（聚合结果 / 一天一卡 / 卡内打卡项 / 已沉淀足迹 / 沉淀入参） |
| `RouteStation` / `RouteWishOption` / `PlanFromRouteInput` | 路线预检站点 / 站点心愿 / 由路线生成计划入参 |

| 常量 | 值 |
|------|-----|
| `TRAVEL_PLAN_ITEM_TYPES` | 4 类明细：🍽️ 美食 / 📍 景点 / 🚗 交通 / 🏠 住宿 |
