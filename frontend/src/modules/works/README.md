# Works — 作品前端

> 文档对齐 v3.64.34 ｜ 最后核对 2026-11-07

作品库是**结果页**：顶部计数卡 + 下面的清单。整理动作（收口台）在「本周状态」页末，不在本页。

## Views

| 文件 | 职责 |
|------|------|
| `WorkView.vue` | 作品库主页面：计数卡（累计 / 已发 / 待提炼）、类型与出口筛选、作品清单（首图缩略 + 数量角标）、删除（来源回待提炼） |

## Components

| 文件 | 职责 |
|------|------|
| `ComposeDialog.vue` | 收口台 / 合成弹窗：把若干条待提炼合成一件作品 |
| `KeepMark.vue` | 「值得留」勾（popover 说明 + 勾选态） |
| `PendingDialog.vue` | 待提炼明细浮层：只读 + 两个出口（不收了 / 去收口台） |
| `@/shared/components/MediaPicker.vue` | 作品编辑弹窗里的媒体选择 / 上传（共用唯一实现，`upload` prop 注入） |

## Composables / Utils

| 文件 | 职责 |
|------|------|
| `composables/useWorkKeep.ts` | 七个入口共享的勾状态机（`useWorkKeep('treasure')`）；**再加入口零改动**，只改后端 `CAPTURE_SOURCE_CHOICES` 与前端 `SOURCE_SHORT` |
| `utils/captureText.ts` | 捕获在列表里的显示文案（收口台与待提炼明细共用一份，含省略号 / 公共前缀处理） |

## Store / API / Types

- `stores/workStore.ts`：作品 / 捕获 / 计数 / 枚举状态
- `api/workApi.ts`：items CRUD、captures、compose、overview、meta、channels、media 封装
- `types/workTypes.ts`：类型 + 界面枚举；**枚举以 `/api/works/meta/` 下发为准，前端零副本**
  - 作品类型 9 项（含 v3.64.30 新增的绘画 / 刺绣，`craft` 显示为「其他手作」）全部来自后端 `WORK_KIND_CHOICES`，前端**不写**这一列中文 —— 抄一份就会漏改、且静默。

## 边界

- 七个入口是**同一个勾**，不要在某个源页面里另存「值得留」字段 —— 那就是第二份真源。
- 「待提炼」量的是**捕获**（还没成形的东西），与上面的作品清单不是同一类，所以点它开明细、不筛表。
- 作品媒体是**媒体真源**；展厅馆藏只引用，不重复上传。
