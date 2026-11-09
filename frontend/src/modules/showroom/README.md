# Showroom — 展厅前端

> 文档对齐 v3.64.5 ｜ 最后核对 2026-10-29

对外输出的**策展空间**：品牌信息 + 能力馆（案例 / 技能）+ 作品馆。
两个页面：`/showroom/preview`（只读预览）与 `/showroom/edit`（策展编辑），各自占一个菜单项。

## Views

| 文件 | 职责 |
|------|------|
| `ShowroomPreview.vue` | 展厅预览：只读聚合（只展示 `is_visible` 项），可跳回策展编辑 |
| `ShowroomEdit.vue` | 策展编辑：品牌信息 / 案例与技能 / 作品馆三页签 |

## Components

| 文件 | 职责 |
|------|------|
| `CaseForm.vue` | 能力馆案例编辑（问题 / 成果 / 技能标签 / 媒体 / 可见性） |
| `SkillForm.vue` | 技能编辑（三级熟练度，枚举随 `/meta/` 下发） |
| `WorkForm.vue` | 馆藏作品编辑（引用作品库 + 手写导语 / 快照 / 可见性） |
| `@/shared/components/MediaGallery.vue` | 媒体展示（图片 / 视频）—— 展示层共用唯一实现 |
| `@/shared/components/MediaPicker.vue` | 媒体选择 / 上传（`upload` prop 注入）—— 共用唯一实现 |

## Store / API / Types

- `stores/showroomStore.ts`：品牌 / 案例 / 技能 / 馆藏作品 / 预览状态
- `api/showroomApi.ts`：profile、cases、skills、works、meta、preview、media 封装
- `types/showroomTypes.ts`：类型 + 技能熟练度选项

## 边界

- **数据引用、叙事手写**：作品馆引用作品库（`works.Work`），媒体不重复上传。
- 预览页只读；编辑动作全在 `/showroom/edit`。
- 本地 `components/MediaGallery.vue` / `MediaPicker.vue` 已被 shared 版取代、**不再被引用**；文件保留待用户删除（铁律一）。
