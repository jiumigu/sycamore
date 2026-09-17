# Travel — 旅行记录 + 旅行心愿单 + 旅行计划 + 路线推演前端

## Views

| 文件 | 路由 | 职责 |
|------|------|------|
| `TravelDashboard.vue` | /travel | 旅行足迹主页（「🗺️ 足迹地图 / 📔 行程日志」双视图：地图视图=统计卡 + 年份筛选 + 中国地图热力/气泡 + 趋势/省份图表 + 记录 CRUD；日志视图=打卡按「日期+地点」聚合的一天一卡 + 沉淀为足迹） |
| `TravelWishView.vue` | /travel/wishes | 旅行心愿单（统计 chips + 中国地图心愿点亮并随筛选联动缩放 + 分类/状态/省市区县/搜索筛选 + 按省份分组卡片 + 打卡记录弹窗（日期/归属行程/评分/评价/值得反复）+ 一键加入计划） |
| `TravelPlanView.vue` | /travel/plans | 旅行计划（4 统计卡 + 新建弹窗明细编辑器 + 可展开计划列表逐项勾选（关联心愿时弹打卡录入）+ 查看路线跳转） |
| `TravelRouteView.vue` | /travel/route | 路线推演（路线预设抽屉 + 小火车沿路线动画 + 生成旅行计划弹窗：逐站勾选带入本城心愿）；原在工具箱，2026-09-11 迁入旅行模块作为主入口 |

## Components

| 文件 | 职责 |
|------|------|
| `ChinaHeatmap.vue` | ECharts 中国**地级市**热力 + **省界叠加** + 城市气泡三层（显式 `geo` 组件 + 热力层 `map` 系列 `geoIndex: 0` 绑定；`visualMap` 分段 4 档并限定 `seriesIndex: 0`，避免把气泡一起染色；`lines` 系列以 polyline 画省界、`silent`；**地市名与气泡名默认隐藏，悬停/点击才显示**，tooltip 对地级市额外列出 `sources` 来源明细） |

## Utils

| 文件 | 职责 |
|------|------|
| `chinaCitiesMap.ts` | 全国地级市底图：把 `better-echarts-maps` 的 `china-provinces.js`（按省打包的 38 份地级市 GeoJSON）合并成一张 493 区域的地图并注册为 `china-cities`；`resolveRegionName()` 做容错对齐（精确 → 去后缀补后缀 → 旧称别名），未对齐返回 `null`；`getProvinceBorderRings()` 从 `china.js` 取 34 个省级单位的边界环（约 2600 点）供省界叠加层使用 |

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
- 旅行计划：`getTravelPlans` `getTravelPlanDetail` `createTravelPlan` `updateTravelPlan` `deleteTravelPlan`
  `getTravelPlanItems` `getTravelPlanStats` `toggleTravelPlanItem`（POST `/plans/<id>/toggle-item/`，body `{item_id}`）
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
| `TravelPlan` / `TravelPlanItem` / `TravelPlanStats` | 旅行计划 / 子项 / 统计 |
| `TravelPlanInput` / `TravelPlanItemInput` | 计划 / 子项提交数据 |
| `TravelWish` / `WishStats` / `WishStatus` / `TravelPlanOption` | 心愿单 / 统计 / 状态 / 计划下拉项 |
| `TripLog` / `TripLogDay` / `TripLogItem` / `TripLogRecord` / `ConsolidatePayload` | 行程日志（聚合结果 / 一天一卡 / 卡内打卡项 / 已沉淀足迹 / 沉淀入参） |
| `RouteStation` / `RouteWishOption` / `PlanFromRouteInput` | 路线预检站点 / 站点心愿 / 由路线生成计划入参 |

| 常量 | 值 |
|------|-----|
| `TRAVEL_PLAN_ITEM_TYPES` | 4 类明细：🍽️ 美食 / 📍 景点 / 🚗 交通 / 🏠 住宿 |
