# Food — 美食记录前端

## Views

| 文件 | 路由 | 职责 |
|------|------|------|
| `FoodMapView.vue` | /food | 主页面（统计卡+筛选栏+卡片网格+分页+弹窗表单） |
| `FoodDashboard.vue` | — | 旧版主页（已废弃，不再被路由引用） |

## Components

| 文件 | 职责 |
|------|------|
| `FoodForm.vue` | 添加/编辑弹窗（el-dialog + el-form + el-upload） |
| `stats/FoodStatsCards.vue` | 5 个统计卡片（总数/城市/均分/还想去/本月） |

## Store

`useFoodStore`（`stores/foodStore.ts`，Composition API）

| 状态 | 类型 | 说明 |
|------|------|------|
| `records` | `FoodRecordList[]` | 当前页列表 |
| `currentRecord` | `FoodRecord \| null` | 当前选中的完整详情 |
| `stats` | `FoodStats \| null` | 统计总览 |
| `maps` / `tags` | 数组 | 地图/标签数据 |
| `loading` / `submitting` | `boolean` | 加载/提交状态 |

| 方法 | 用途 |
|------|------|
| `fetchRecords()` | 获取列表（处理分页 response） |
| `fetchStats()` | 获取统计 |
| `createRecord()` / `updateRecord()` | 新建/更新 |
| `deleteRecord()` | 删除并更新本地列表 |
| `refreshAll()` | 并行刷新列表+统计 |

## API

`api/foodApi.ts` — 13 个函数：
- CRUD: `getFoodList` `getFoodDetail` `createFood` `updateFood` `deleteFood`
- 数据: `getFoodStats` `getFoodLocations` `getFoodMapData` `getFoodTags` `getFoodTrend` `getFoodCategories` `getFoodTasteDistribution`
- 上传: `uploadFood(formData)`

## Types & Constants

`types/foodTypes.ts`

| 接口 | 用途 |
|------|------|
| `FoodRecord` | 完整详情 |
| `FoodRecordList` | 列表轻量 |
| `FoodStats` | 统计 |
| `FoodLocation` / `FoodMapData` | 地图数据 |
| `TagCount` | 标签频次 |
| `FoodFormData` | 表单数据 |

| 常量 | 值 |
|------|-----|
| `CATEGORY_OPTIONS` | 7 个分类（中餐/西餐/日料/甜品/小吃/饮品/其他） |
| `TASTE_LEVELS` | 4 级（好吃/特别好吃/还想吃/一定要再吃） |
| `EAT_TIME_OPTIONS` | 4 时段 |
| `OCCASION_OPTIONS` | 5 场景 |

## 图片上传流程

1. el-upload 逐张上传到 `/api/food/upload/`（仅文件，不包含表单字段）
2. 后端存储文件，返回 `{"url": "/media/food/<uuid>.ext"}`
3. 前端将 URL 追加到 `form.images[]`
4. 提交表单时，`images` 数组随 JSON 请求发送到 POST `/records/`
5. 后端序列化器 `get_image_url` 优先返回 `cover_image`，降级到 `images[0]`
