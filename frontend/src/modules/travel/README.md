# Travel — 旅行记录 + 旅行计划前端

## Views

| 文件 | 路由 | 职责 |
|------|------|------|
| `TravelDashboard.vue` | /travel | 旅行足迹主页（统计卡 + 年份筛选 + 中国地图热力/气泡 + 趋势/省份图表 + 记录 CRUD） |
| `TravelPlanView.vue` | /travel/plans | 旅行计划（4 统计卡 + 新建弹窗明细编辑器 + 可展开计划列表逐项勾选） |

## Components

| 文件 | 职责 |
|------|------|
| `ChinaHeatmap.vue` | ECharts 中国地图（省份热力 + 城市气泡双层叠加） |

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
- 旅行计划：`getTravelPlans` `getTravelPlanDetail` `createTravelPlan` `updateTravelPlan` `deleteTravelPlan`
  `getTravelPlanItems` `getTravelPlanStats` `toggleTravelPlanItem`（POST `/plans/<id>/toggle-item/`，body `{item_id}`）

## Types & Constants

`types/travelTypes.ts`

| 接口 | 用途 |
|------|------|
| `TravelRecord` / `TravelFormData` | 旅行记录 / 表单 |
| `MapData` / `HeatmapItem` / `BubbleItem` | 地图数据 |
| `TravelStats` / `YearlyTrend` / `ProvinceDist` | 统计总览 |
| `TravelPlan` / `TravelPlanItem` / `TravelPlanStats` | 旅行计划 / 子项 / 统计 |
| `TravelPlanInput` / `TravelPlanItemInput` | 计划 / 子项提交数据 |

| 常量 | 值 |
|------|-----|
| `TRAVEL_PLAN_ITEM_TYPES` | 4 类明细：🍽️ 美食 / 📍 景点 / 🚗 交通 / 🏠 住宿 |
