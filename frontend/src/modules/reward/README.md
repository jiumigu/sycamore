# Reward — 奖励池前端

> 文档对齐 v3.64.5 ｜ 最后核对 2026-10-29

> **口径（v3.63.16 / v3.63.19）**：余额 / 累计获得 / 累计提取 / 四源合计全部由后端流水派生，
> 前端**不做二次计算、不做 `Number()` 兜底**。金额字段已由 `AmountNumberField` 保证是 JSON number；
> store 里原来的 `Number(x) || 0` 已删 —— 它既藏「后端吐字符串」，又把 `null` 与真 `0` 抹平。

## Pages
| 文件/组件 | 职责 |
|-----------|------|
| `RewardPoolView.vue` | 主页面（BalanceCard + 来源筛选 + RewardTimeline；页头「🎁 礼物清单」入口） |
| `GiftListView.vue` | 礼物清单独立页（`/reward/gifts`，从快乐银行页头进入） |

> **入口（v3.63.11 起）**：礼物清单不再占菜单项；页头抽屉实现已删除，只保留独立页，路由保留。
> `RewardStats.vue` 自 v3.63.11 起已无调用方（原「Gift 概览」随抽屉一并移除），文件等用户决定是否删除。

## Components
| 文件 | 职责 |
|------|------|
| `BalanceCard.vue` | 3张统计卡（余额/获得/提取） |
| `RewardStats.vue` | 来源分布（里程碑/小确幸）—— **⚠️ 已无调用方** |
| `RewardTimeline.vue` | 流水时间线 |
| `GiftCard.vue` | 礼物卡片（分类图标+进度条+状态标签，礼物清单页使用） |
| `GiftForm.vue` | 创建/编辑弹窗（礼物清单页使用） |
| `GiftExchangeModal.vue` | 兑换确认弹窗（礼物清单页使用） |
