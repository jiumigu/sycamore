# Food — 美食记录

## Models

| Model | Table | 用途 |
|-------|-------|------|
| FoodRecord | food_record | 美食记录（name/city/taste_level/eat_date/rating/price/images/cover_image 等） |

关键字段：
- `cover_image` — 封面图路径（由 upload 端点设置）
- `images` — JSONField，多图列表（由表单正常流程填充）
- `image_url` — SerializerMethodField，优先返回 `cover_image`，降级到 `images[0]`

## API Endpoints

前缀 `/api/food/`，全部绑定 `FoodRecordViewSet`：

### CRUD

| 方法 | 端点 | 用途 |
|------|------|------|
| GET | /records/ | 列表（支持筛选/搜索/排序/分页） |
| POST | /records/ | 创建 |
| GET | /records/`<pk>`/ | 详情 |
| PUT | /records/`<pk>`/ | 更新 |
| DELETE | /records/`<pk>`/ | 删除 |

### 筛选参数（列表）

`user_id` `category` `taste_level` `province` `city` `year` `month` `min_rating`

### 数据端点

| 方法 | 端点 | 用途 |
|------|------|------|
| GET | /records/stats/ | 统计总览 |
| GET | /records/locations/ | 地点聚合 |
| GET | /records/map_data/ | 省→市地图数据 |
| GET | /records/tags/ | 标签频次 |
| GET | /records/trend/ | 月度趋势（?year=） |
| GET | /records/categories/ | 分类分布 |
| GET | /records/taste_distribution/ | 美味等级分布 |
| POST | /upload/ | 图片上传 / 快捷创建 |

### 上传（/upload/）

两种模式：
1. **仅上传文件**：无 `name` 参数 → 存文件返 URL。
2. **完整创建**：传 `name` + 其他字段 → 创建记录，`cover_image` 设为上传图。

## Services

`FoodService`（7 个 `@staticmethod`）：

| 方法 | 用途 |
|------|------|
| `get_stats()` | 总数/城市/均分/还想去/本月新增 |
| `get_locations()` | 省份+城市去重计数 |
| `get_map_data()` | 省→市嵌套聚合 |
| `get_tags()` | 逗号分隔标签拆分计数 |
| `get_monthly_trend()` | 按月统计 |
| `get_category_distribution()` | 分类计数 |
| `get_taste_distribution()` | 美味等级计数 |

## 图片处理

- `cover_image` 存相对路径（`/media/food/<uuid>.ext`）
- 序列化器 `get_image_url` 通过 `build_absolute_uri` 转为绝对 URL
- 降级逻辑：`cover_image` 为空时取 `images[0]`
