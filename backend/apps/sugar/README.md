# Sugar — 小确幸

## Models
| Model | Table | 用途 |
|-------|-------|------|
| SugarRecord | sugar_record | 小确幸记录（s_id PK, 快乐程度5-20, 奖励金额优先取前端传入值否则=快乐值, 同步标记, joy_type 五种分类） |
| SugarTemplate | sugar_template | 小确幸模板（预置记录，一键套用） |
| EnergyTemplate | sugar_energy_template | 能量清单模板（模板项 + 分值） |
| EnergyLog | sugar_energy_log | 能量清单完成记录 |
| EnergyDailyStats | sugar_energy_daily_stats | 每日能量统计（按日聚合，供趋势） |

## 快乐程度→奖励

快乐程度范围 5-20。奖励金额默认等于快乐程度，但前端创建时可传入 `reward_amount` 覆盖（如收件箱完成时取用户填的金额）。

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
| GET/POST | /records/ | 小确幸列表/创建 |
| GET/PUT/DELETE | /records/&lt;pk&gt;/ | 详情/更新/删除 |
| GET | /records/joy_type_stats/ | 快乐类型统计 |
| GET | /records/categories/ | 分类统计 |
| GET | /categories/ | 分类统计（与上一条同实现，旧入口兼容） |
| GET/POST | /templates/ | 小确幸模板列表/创建 |
| GET/PUT/DELETE | /templates/&lt;pk&gt;/ | 模板详情/更新/删除 |
| GET/POST | /energy/templates/ | 能量清单模板列表/创建 |
| POST | /energy/complete/ | 完成一项能量清单 |
| GET | /energy/stats/ | 能量统计 |
| GET | /energy/history/ | 完成历史 |
| GET | /energy/daily/ | 按日明细 |
| GET | /energy/trend/ | 能量趋势 |

⚠️ 记录端点的路径是 `/records/`，**不是** `/sugar/` —— viewset 注册名为 `records`（`urls.py:7`）。
