# Sugar — 小确幸前端

## Components

| 文件/组件 | 职责 |
|-----------|------|
| `SugarView.vue` | 主页（统计卡 + 筛选栏 + 卡片时间线 + 录入弹窗） |
| `SugarCard.vue` | 单条卡片（**日期 · 分值+档位词 · 分类 · 金额 / 标题 / 备注 / 标签**） |
| `TemplateCard.vue` / `TemplateDialog.vue` | 小确幸模板 |
| `energy/*` | 能量清单（`EnergyList` / `EnergyItem` / `EnergyCustomModal`） |
| `views/JoyTypeChart.vue` | 快乐类型图 |
| `HappinessSlider.vue` | ⚠️ **全仓零引用**（只在本文档被提到过）。保留未删，删文件需先确认 |

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
