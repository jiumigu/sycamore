# Sugar — 小确幸前端

> 文档对齐 v3.64.66 ｜ 最后核对 2026-11-14

## Components

| 文件/组件 | 职责 |
|-----------|------|
| `SugarView.vue` | 主页（统计卡 + 筛选栏五条件 + 卡片时间线 + 录入弹窗） |
| `SugarCard.vue` | 单条卡片（**日期 · 分值+档位词 · 分类 · 金额 / 标题 / 备注 / 标签**） |
| `TemplateCard.vue` / `TemplateDialog.vue` | 小确幸模板 |
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
| 分值进度条（`el-progress`） | 进度条与分值表达同一个数，而分值信息更全；且绝大多数记录集中在少数几个分数上（其中一个分数就占了三分之一）—— 条长几乎无区分度 |
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

## 🔴 筛选下拉的选项来自后端，不是常量表

筛选栏五个条件（年份 / 月份 / 分类 / 快乐类型 / 标签）。前三个的选项是静态的，
**后两个不行** —— 它们必须能命中「库里真实存在的全部值」。

### 快乐类型：`JOY_TYPE_OPTIONS` 只够录入用

| 不在 `JOY_TYPE_OPTIONS` 里但必须能筛 | 为什么 |
|---|---|
| 未标类型（`joy_type=''`，一批存量） | 不筛就只能一页页翻着找 |
| 旧词表残留（社交 / 其他 / 创造，少量几条） | 下拉里没有 ⇒ 既看不到也清不掉 |

选项取 `store.joyTypeOptions`（`GET /sugar/records/joy_types/`），
「未标注」用后端下发的哨兵 `unlabeled_value` 当 value，**不是空串**：
`el-select` 的 `clearable` 清空回 `''`，两者一旦都用空串，「清空筛选」和
「只看未标注」就成了同一件事，而失效那一边不报错。

### 标签：库里的值和「有哪些标签」都不是前端能推的

`SugarRecord.tags` 是**逗号分隔字符串**，没有标签表。所以标签下拉取
`store.tagOptions`（`GET /sugar/records/tags/`），**不要**从 `store.sugarList`
里 `flatMap` 出标签 —— 列表只有当前页 10 条，翻页/筛选一变，下拉选项就跟着变，
用户看到的是「刚才还能选的标签不见了」，而这不是错误、不会有任何提示。

「无标签」同样是后端下发的哨兵 `untagged_value`（`__untagged__`），理由同上。
库里 30/74 条没打过标签，不给这个选项，那批记录既不能按标签筛到，
也没法与「清空筛选」区分开。

下拉挂了 `filterable`：标签项随数据增长（当前 15 个），打字比滚动快。
**故意不给它撑高 popper** —— 十几个标签全展开会把下面的列表整块盖住。
（快乐类型的 `joy-type-popper` 是另一回事：它固定 9 项，撑高刚好放下。）

### 三个筛选参数函数，别合并

```ts
getFilters()             // 全部 → 列表 + 顶部统计（必须是同一批记录）
getOptionFilters()       // 去掉 joy_type → 只给类型下拉的条数
getTagOptionFilters()    // 去掉 tag      → 只给标签下拉的条数
```

两个 `*OptionFilters` 对称：各自剔除自己那一维，保留对方。选了「成就」之后，
其它标签还要各显示多少条；选了「秩序型」之后，各标签也要各显示多少条。
谁把自己也算进去，选完就只剩被选中那一项有数字，
看起来像「别的都没数据了」—— 而这是静默的。

⚠️ 类型下拉有 9 项，超过 Element Plus 写死的 `max-height: 274px`（≈8 行），
最后一项「未标注」会被裁在滚动区外。所以挂 `popper-class="joy-type-popper"`，
高度覆盖写在 `shared/styles/main.scss`（下拉 teleport 到 body，scoped 够不着）。

### 窄屏：3 列网格，不是 `flex-wrap` 自己换行

五个框加起来约 728px（130+130+130+158+140 + 四个 10px 间距），加右侧「累计奖励」
约 150px ⇒ 横向需要 ≈ 878px。窗口窄于约 1240px 时 `flex-wrap` 会换出
「4 个 + 1 个孤零零 + 奖励再一行」—— 第 2 行只有「标签」一个框，右边空掉一大半。

`@media (max-width: 1240px)` 改 `grid-template-columns: repeat(3, minmax(0, 1fr))`：
整齐的 3 + 2，奖励 `align-self: flex-end` 单独一行。每个框反而更宽，
「社交（旧词表）」这种长词也不容易被截断。

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
