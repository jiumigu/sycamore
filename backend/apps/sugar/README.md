# Sugar — 小确幸

> 文档对齐 v3.64.38 ｜ 最后核对 2026-11-08

## Models
| Model | Table | 用途 |
|-------|-------|------|
| SugarRecord | sugar_record | 小确幸记录（s_id PK, 快乐程度5-20, 奖励金额优先取前端传入值否则=快乐值, 同步标记, joy_type 五种分类） |
| SugarTemplate | sugar_template | 小确幸模板（预置记录，一键套用） |
| EnergyTemplate | sugar_energy_template | 能量清单模板（模板项 + 分值） |
| EnergyLog | sugar_energy_log | 能量清单完成记录 |
| EnergyDailyStats | sugar_energy_daily_stats | 每日能量统计（按日聚合，供趋势） |

## 快乐程度→奖励（v3.63.21 起单一刻度）

快乐程度范围 5-20，**奖励金额 = 快乐程度**，没有第二个可填入口。收件箱完成弹窗与快乐日记共用
`HappinessScale`，提交时 `level_of_happiness` 与 `reward_amount` 同传该值，金额只读显示。

- 新增：`perform_create` 加 `@transaction.atomic`，文案取落库后的 `record.reward_amount`（不取入参）；自动调用 `RewardPoolService.add_reward()`。
- 编辑：三级判断（顺序不能换）——显式金额优先 → 程度**真的变了**才按「金额=分数」重算 → 否则不动。否则只改标题也会重写历史金额并记一笔流水。
- 删除：`deduct_reward()` 扣除已同步奖励。
- 出参用 `core.fields.AmountNumberField`（出参 number / 入参 Decimal）。**不能**用 `DecimalField(coerce_to_string=False)`：入参也会变 Decimal，`response.data` 类型契约随之改变。
- ⚠️ `_calculate_reward_amount`（1/3/5/8/10 五档）与 `SugarRecordService.create/update` 是**死代码**，已加警告；`energy_gained * 2` 是独立的双倍快乐规则，不动。

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

### 列表按快乐类型筛选（v3.64.38）

`GET /records/?joy_type=<值>`，值有三种来源，**缺任何一种都会静默漏数**：

| 来源 | 例 | 为什么必须在下拉里 |
|---|---|---|
| `choices` 的 5 个标准型 | `秩序型` | 即便本期 0 条也列出，否则「录入能选、筛选没有」 |
| 库里出现但不在 `choices` 的值 | `社交` / `其他` / `创造` | 下拉里没有 ⇒ 这几条永远筛不出来、也找不到来清理（下拉标「（旧词表）」） |
| 哨兵 `__unlabeled__` | `joy_type=''` | 那批未标类型的记录，不靠它只能一页页翻 |

🔴 **「未标注」必须用哨兵值，不能传空串**：`?joy_type=` 与「没传」在 query string 里
一模一样，`params.get()` 两种都返回 `''` ⇒ 清空筛选和「只看未标注」会变成同一件事，
而失效的那一边不会报错。`_apply_record_scope()` 里 `joy_type == ''` 走「不筛」。

筛选走模块级 `_apply_record_scope()`，**列表 / 分类统计 / 类型选项三处共用**：
只给列表加而统计不加，顶部「累计获得」就还是全量，同屏两个数互相矛盾（都不报错）。

选项由 `GET /records/joy_types/` 下发（前端零副本，别在页面上 v-for `JOY_TYPE_OPTIONS`）：

```json
{ "unlabeled_value": "__unlabeled__",
  "options": [{ "value": "秩序型", "label": "📋 秩序型", "count": 14, "kind": "standard" }] }
```

- `count` 只按 year/month/category 统计，**剔除 `joy_type` 自身** —— 否则选完一个类型，
  其它类型的条数全变 0，下拉就再也指不出「别处还有多少条」。
- 选项集合取**全库 DISTINCT**，不随筛选变化；否则某值的最后一条记录落在别的月份时，
  选项会忽隐忽现（下拉自己会变，比缺选项更难察觉）。


## API Endpoints

前缀 `/api/sugar/`

| 方法 | 端点 | 用途 |
|------|------|------|
| GET/POST | /records/ | 小确幸列表/创建 |
| GET/PUT/DELETE | /records/&lt;pk&gt;/ | 详情/更新/删除 |
| GET | /records/joy_type_stats/ | 快乐类型统计 |
| GET | /records/joy_types/ | **快乐类型筛选项**（`{unlabeled_value, options:[{value,label,count,kind}]}`，下拉框唯一来源） |
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
