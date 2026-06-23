# Sugar — 小确幸

## Models
| Model | Table | 用途 |
|-------|-------|------|
| SugarRecord | sugar_record | 小确幸记录（s_id PK, 快乐程度5-20, 奖励金额=快乐值, 同步标记） |

## 快乐程度→奖励

快乐程度范围 5-20，奖励金额直接等于快乐值（不再有阈值映射）。

- 新增：自动调用 `RewardPoolService.add_reward()`
- 编辑：`adjust_reward()` 按新旧金额差调整（`select_for_update()` 防并发）
- 删除：`deduct_reward()` 扣除已同步奖励

## API Endpoints

前缀 `/api/sugar/`

| 方法 | 端点 | 用途 |
|------|------|------|
| GET/POST | /sugar/ | 列表/创建 |
| GET/PUT/DELETE | /sugar/<pk>/ | 详情/更新/删除 |
| GET | /sugar/categories/ | 分类统计 |
