# Sugar — 小确幸

## Models
| Model | Table | 用途 |
|-------|-------|------|
| SugarRecord | sugar_record | 小确幸记录（s_id PK, 快乐程度5-20, 奖励金额=快乐值, 同步标记, joy_type 五种分类） |

## 快乐程度→奖励

快乐程度范围 5-20，奖励金额直接等于快乐值（不再有阈值映射）。

- 新增：自动调用 `RewardPoolService.add_reward()`
- 编辑：`adjust_reward()` 按新旧金额差调整（`select_for_update()` 防并发）
- 删除：`deduct_reward()` 扣除已同步奖励

## 快乐类型 (joy_type)

2026-07-03 从七类重构为五类：

| 类型 | 含义 |
|------|------|
| 感官型 | 五感满足（味觉/触觉/视觉/听觉/嗅觉） |
| 秩序型 | 掌控感（完成/整理/规划/条理） |
| 联结型 | 关系满足（社交/陪伴/共鸣/被理解） |
| 意外型 | 惊喜感（偶然/发现/运气/超出预期） |
| 独处型 | 内在空间（独处/内省/自我对话/安静） |

旧数据保留不迁移，编辑时下拉框显示原值。

## API Endpoints

前缀 `/api/sugar/`

| 方法 | 端点 | 用途 |
|------|------|------|
| GET/POST | /sugar/ | 列表/创建 |
| GET/PUT/DELETE | /sugar/<pk>/ | 详情/更新/删除 |
| GET | /sugar/categories/ | 分类统计 |
