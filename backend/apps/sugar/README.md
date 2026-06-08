# Sugar — 小确幸

## Models
| Model | Table | 用途 |
|-------|-------|------|
| SugarRecord | sugar_record | 小确幸记录（s_id PK, 快乐程度1-10, 奖励金额, 同步标记） |

## 快乐程度→奖励映射

| 区间 | 奖励 |
|------|------|
| 1.0 - 3.0 | ¥1 |
| 3.1 - 5.0 | ¥3 |
| 5.1 - 7.0 | ¥5 |
| 7.1 - 8.5 | ¥8 |
| 8.6 - 10.0 | ¥10 |

- 新增：自动调用 `RewardPoolService.add_reward()`
- 编辑：`adjust_reward()` 按新旧金额差调整
- 删除：`deduct_reward()` 扣除已同步奖励

## API Endpoints

前缀 `/api/sugar/`

| 方法 | 端点 | 用途 |
|------|------|------|
| GET/POST | /sugar/ | 列表/创建 |
| GET/PUT/DELETE | /sugar/<pk>/ | 详情/更新/删除 |
| GET | /sugar/categories/ | 分类统计 |
