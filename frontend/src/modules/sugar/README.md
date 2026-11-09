# Sugar — 小确幸前端

> 文档对齐 v3.64.38 ｜ 最后核对 2026-11-08

## Components

| 文件/组件 | 职责 |
|-----------|------|
| `SugarView.vue` | 主页（统计卡 + 筛选栏 + 卡片时间线 + 录入弹窗） |
| `SugarCard.vue` | 单条卡片（**日期 · 分值+档位词 · 分类 · 金额 / 标题 / 备注 / 标签**） |
| `TemplateCard.vue` / `TemplateDialog.vue` | 小确幸模板 |
| `energy/*` | 能量清单（`EnergyList` / `EnergyItem` / `EnergyCustomModal`） |
| `views/JoyTypeChart.vue` | 快乐类型图 |
| `HappinessScale.vue` | ✅ **快乐程度输入唯一实现**（5–20 分滑块 + 档位词），快乐日记与收件箱完成弹窗共用 |
| `HappinessSlider.vue` | ⚠️ **全仓零引用**，且是**旧的 1–10 分刻度**（奖励 1/3/5/8/10 元），与 5–20 分体系冲突。别用，删文件需先确认 |

## 卡片版式（v3.62.5 改版）

```
2026-09-30   8.0 开心   [分类]                 +¥5.00   ← 日期 / 分值+档位词 / 分类 / 金额
标题
备注（有就整段显示，`white-space: pre-wrap`）
[快乐类型 tag] [标签 tag]…
```

| 删掉 | 理由 |
|---|---|
| 左侧表情方块（`.card-left` + `.emoji-badge`） | 同一表情在卡片上出现了 **2 次**（徽章 + 分数旁） |
| 分值进度条（`el-progress`） | 进度条与分值表达同一个数，而分值信息更全；且 64 条里 70% 集中在 4 个分数、单一个 `7.0` 就占 23 条 —— 条长几乎无区分度 |
| `expanded` 状态 + 整块 `@click` | 备注改为常显，不再需要点击展开 |

**分值 + 档位词**放在日期右侧的空白位，颜色取记录上的 `reward_color`。

## 🔴 档位词一律查表，不许自己算

```ts
import { happinessLabelOf } from '../types/sugarTypes'
happinessLabelOf(store.happinessBands, level)   // 取不到表 ⇒ ''，卡片降级为只显示分数
```

- 档位表由 `GET /sugar/records/happiness_bands/` 下发（store 里 `happinessBands`，
  `fetchHappinessBands()` 失败置 `null`、**不往外抛**）。
- 这里**没有、也不许有**档位边界数字或档位词 —— 曾经抄成四份（本目录的 `REWARD_LABELS`、
  卡片里的配色表与表情表、`SugarView.vue` 的 `happinessTexts`），抄出过
  「弹窗说非常开心、列表说很高兴」。
- 分值颜色同理取 `record.reward_color`（后端按行下发），前端**不按分数算色**。

## 🔴 筛选下拉的选项来自后端，不是 `JOY_TYPE_OPTIONS`

筛选栏四个条件（年份 / 月份 / 分类 / 快乐类型）。前三个的选项是静态的，
**快乐类型不行** —— `JOY_TYPE_OPTIONS` 是「录入时可选的五个值」，
而筛选要能命中「库里真实存在的全部值」：

| 不在 `JOY_TYPE_OPTIONS` 里但必须能筛 | 为什么 |
|---|---|
| 未标类型（`joy_type=''`，36 条） | 不筛就只能一页页翻着找 |
| 旧词表残留（社交 / 其他 / 创造，4 条） | 下拉里没有 ⇒ 既看不到也清不掉 |

所以选项取 `store.joyTypeOptions`（`GET /sugar/records/joy_types/`），
「未标注」用后端下发的哨兵 `unlabeled_value` 当 value，**不是空串**：
`el-select` 的 `clearable` 清空回 `''`，两者一旦都用空串，「清空筛选」和
「只看未标注」就成了同一件事，而失效那一边不报错。

两套筛选参数方向相反，别合并：

```ts
getFilters()        // 含 joy_type  → 列表 + 顶部统计（同一批记录）
getOptionFilters()  // 去掉 joy_type → 只给下拉条数（否则选完一个类型，其余全变 0）
```

⚠️ 下拉有 9 项，超过 Element Plus 写死的 `max-height: 274px`（≈8 行），
最后一项「未标注」会被裁在滚动区外。所以挂 `popper-class="joy-type-popper"`，
高度覆盖写在 `shared/styles/main.scss`（下拉 teleport 到 body，scoped 够不着）。

## 🔴 刻度只有一套，金额没有第二个入口

口径：**5–20 分（区间由 `happiness_bands` 下发），奖励金额 = 分数**。

| 曾经的做法 | 现在 |
|---|---|
| 收件箱完成弹窗用 `el-rate` 五颗星，提交时 `星 × 4` 折成 5–20 分 | 直接用 `HappinessScale`（与快乐日记同一个滑块） |
| 弹窗里另有一个「奖励金额」输入框（默认 5），与程度无关 | 金额跟随程度**只读显示**，不可单独填 |
| 流水文案取 `level_of_happiness` | 文案取 `reward_amount`（后端落库值） |

🔴 2026-10-26 实案：3 星 × 4 = 12 分 + 金额另填 5 ⇒ 流水写「获得 12.0 元奖励」、
右侧却是 `+¥5.00`。**根因不是文案选错了字段，而是「程度」与「金额」是两个可独立填的量** ——
只要留两个入口，任何一句话都会架空另一个。要再引入「星」「档」「系数」，
改 `HappinessScale.vue`，**不要在下游再折算一次**。
