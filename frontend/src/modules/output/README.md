# Output — 个人良品率前端

> 文档对齐 v3.64.5 ｜ 最后核对 2026-10-29

把「自我要求」从道德问题变成质量管理问题：记录做过的每件事，看**良品率**而不是给自己打分。

## Views

| 文件 | 职责 |
|------|------|
| `OutputDashboard.vue` | 主页面：时间窗口切换（看得见的选择）、一句话摘要、月度良品率图、明细表、增删改；归档横幅由 `useMenuArchive('output')` 决定，重新启用后自动消失 |

## Components

| 文件 | 职责 |
|------|------|
| `OutputForm.vue` | 新增 / 编辑一条记录（标题、日期、分类、良品判定、备注） |

## Store / API / Types

- `stores/outputStore.ts`：记录列表、窗口、统计与 CRUD
- `api/outputApi.ts`：记录 CRUD + 统计
- `types/outputTypes.ts`：类型 + 窗口选项 / 分类常量

## 注意

- v3.62.39 起**取消默认归档**（`menuConfig.ts` 已无 `defaultArchived`）——它靠频率吃饭，藏起来等于自我否证。
- 未填日期的记录进不了任何按日期过滤的口径；界面必须把这类记录说出来（`undatedNote`），不能让它们静默消失。
