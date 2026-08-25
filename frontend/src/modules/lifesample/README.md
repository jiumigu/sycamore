# LifeSample — 人生样本前端

## Views

| 文件 | 路由 | 职责 |
|------|------|------|
| `Index.vue` | /lifesample | 人生样本主页（紧凑统计：5 核心统计卡 + 评级摘要，点击筛选/清除 + 搜索/类型/状态/评级/标签筛选 + 卡片墙 + 「同步」自动创建/更新索引，结果弹窗 + 「打开」样本文件夹） |

## Components

| 文件 | 职责 |
|------|------|
| `SampleCard.vue` | 样本卡片（状态徽章 + 评级徽章 + 头像图标 + 姓名/类型 tag/一句话简介/评级理由/标签 + Obsidian 徽标（仅显示文件名）+ 打开按钮，打开用绝对路径 URI，未配置时友好提示） |
| `SampleForm.vue` | 新建/编辑弹窗（姓名/别名/类型/标签多选可创建/状态/评级/评级理由/Obsidian 路径/我的笔记） |
| `StatusBadge.vue` | 状态徽章（已收集/已核实/已审阅，按状态着色） |
| `RelevanceBadge.vue` | 评级徽章（高度借鉴/参考/了解，按评级着色） |

## Store

`useSampleStore`（`stores/sample.ts`，Composition API）

| 状态 | 类型 | 说明 |
|------|------|------|
| `samples` | `LifeSample[]` | 当前筛选结果 |
| `stats` | `Stats \| null` | 统计（total/synced/pending/obsidian_files） |
| `allTags` | `string[]` | 全部标签 |
| `loading` | `boolean` | 加载状态 |
| `syncing` | `boolean` | 同步中状态（驱动按钮 loading） |

| 方法 | 用途 |
|------|------|
| `loadAll(params)` | 并行拉取 samples + stats + tags（params 含 search/type/status/relevance/tag） |
| `createSample()` / `updateSample()` / `deleteSample()` | CRUD |
| `scanObsidian()` | 扫描 Obsidian 返回文件列表（预览） |
| `syncFromObsidian()` | **双向同步**：调后端同步端点，成功后 `loadAll` 刷新，返回 `SyncResult` |

## API

`api/index.ts` — `sampleApi` 对象

- 样本：`getList`（?search=&type=&tag=） `getDetail` `create` `update`（PATCH） `delete` `getTags` `getStats`
- 同步：`syncFromObsidian`（POST `/samples/sync-from-obsidian/`，返回 `SyncResult`，含 `migrated` 路径迁移列表）
- Obsidian：`getObsidianConfig` `updateObsidianConfig`（POST） `scanObsidian` `openObsidianFile`（后端返回 `obsidian://open?path=<绝对路径>`，`window.open` 打开；URI 为空则提示先配置集成）
- `encodePath()`：路径按 `/` 分段 `encodeURIComponent` 再拼接，避免 `%2F` 被 URL 解析器预解码

## Types & Constants

`types/index.ts` — `SampleType`、`SampleStatus`（collected/verified/reviewed）、`SampleRelevance`（high/reference/knowledge）、`SampleTypeLabels`/`SampleTypeIcons`/`StatusConfig`/`RelevanceConfig`（label/icon/color）、`LifeSample`/`LifeSampleForm`/`ObsidianConfig`/`ScanResult`（含 era/region/birth_year 等扩展字段）/`SyncResult`（含 `migrated: SyncMigration[]`）/`Stats`（含 status/relevance 分布）

## 相关

系统设置页（`core/admin/views/AdminSettings.vue`）内嵌 Obsidian 集成配置卡——启用开关 + 仓库路径 + 样本文件夹（默认 `05_人生样本(LifeSamples)`）+ 保存 + **测试连接**（成功/失败/空文件夹三种状态）+ 当前配置预览（完整路径）+ 快速操作（打开仓库 / 打开样本文件夹），直接走 `shared/utils/request`，不反向引用业务模块 api。
