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

## 快乐程度档位（唯一真源，v3.62.5）

档位**边界与显示词只在 `constants.py` 出现一次**（`SUGAR_HAPPINESS_BANDS`，5 档），三个出口都读它：

| # | 出口 | 用途 |
|---|---|---|
| 1 | `serializers._reward_label()` | 每条记录下发 `reward_label` |
| 2 | `serializers.get_reward_color()` | 每条记录下发 `reward_color` |
| 3 | `GET /records/happiness_bands/` | 前端录入弹窗**拖滑块时实时预览** |

为什么要有第 3 个出口：预览那一刻**还没有记录**，拿不到记录上的 `reward_label`，整张表必须下发一次。
在此之前同一套档位被抄成了**五份**（后端一处、卡片配色一处、卡片表情一处、弹窗词表一处，
外加一份无人引用的 `REWARD_LABELS`），其中两份已经对不上 ——
**同一个 12 分，弹窗说「非常开心」、列表说「很高兴」**。⇒ 前端零副本，只许查表。

### 两处边界，处置相反

| 情形 | 处置 | 原因 |
|---|---|---|
| 分数**超出** 5~20 | **夹取**到最近一档 | 库里真有 3.0 / 4.0（早于校验上线）。抛异常 = 整页 500；返回 `None` = 「有分数、没有词」 |
| **取不到**档位表 | 前端降级为**只显示分数**、不编词 | 宁可少说，不能说错（编一个词出来就是又造了第二份表） |

⚠️ 改档位时**同步改两处**：`SUGAR_HAPPINESS_BANDS` 与前端 `sugarTypes.ts` 的 `SugarHappinessBand` 类型
（后者只是类型，**不含任何边界数字**）。`test_sugar_happiness_bands.py` 里的
`test_bands_endpoint_rejects_retired_keys` 会拦住 `emoji` / `icon` / `desc` / `min_level` 这些已废弃键名回来。

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
| GET | /records/happiness_bands/ | **快乐程度档位表**（`{min, max, bands:[{max_level,label,color}]}`，前端零副本） |
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
