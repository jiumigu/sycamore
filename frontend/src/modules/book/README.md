# Book — 书籍阅读前端

> 文档对齐 v3.64.81 ｜ 最后核对 2026-11-18

| 文件/组件 | 职责 |
|-----------|------|
| `BookView.vue` | 主页（当前这本横条 + 筛选 + 列表 + 统计卡 + 编辑弹窗 + 换书弹窗 + 批量工具条） |
| `BookChartView.vue` | 阅读图形分析（年度统计与类型分布） |
| `bookStore.ts` | Pinia 状态管理 |
| `bookApi.ts` | API 调用封装 |
| `bookTypes.ts` | 类型定义 + `STATUS_OPTIONS` / `STATUS_LABELS` / `STATUS_TAG_TYPE` |

## 状态：三张表，一份口径（v3.64.79）

```
STATUS_OPTIONS   6 个 key（to_read / reading / rereading / finished / shelved / abandoned）
STATUS_LABELS    key → 中文词（待读 / 在读 / 在读二刷 / 已读完 / 搁置 / 弃读）
STATUS_TAG_TYPE  key → el-tag type（灰 / 蓝 / 蓝 / 绿 / 橙 / 红）
```

- 🔴 这三张表是 `bookTypes.ts` 里的**唯一一份**：列表、筛选下拉、编辑弹窗、批量工具条
  都从这里取。`BookView` 里再写一份 map 就会出现「同一条状态两个颜色」，
  而两处各自都看着正常。
- 🔴 颜色只答「还能不能推进」，文字答「第几遍」—— 所以 `reading` 与 `rereading` **同色**。
- 🔴 批量工具条的文案必须用 `STATUS_LABELS`：`status` 是英文 key，
  直接拼进句子会写成「把 3 本改成「shelved」？」。
- 状态值改英文后，`status_display` 仍由后端给中文（`get_status_display`），
  列表 Tag 的文字取 `status_display`，不从本地表推。

## 换书弹窗的候选：口径在后端（v3.64.81）

`bookStore.searchFocusCandidates()` 只做一件事 —— 调
`GET /books/reading-focus/candidates/?search=`，把 `results` 塞进 `focusCandidates`。

- 🔴 **前端不许再 filter**。原来那句 `list.filter(b => b.bid !== focus.book.bid)`
  是仅剩的本地口径；后端 `candidate_queryset()` 已经排除过当前这本与
  「已读完 / 弃读」。两边各写一份，将来放宽规则必有一边漏 —— 漏了不报错，
  只是下拉里多出几本不该出现的书。
- 🔴 候选集**不复用 `getBookList`**：那会顺带改写 `bookList` / `totalCount`，
  弹窗里搜一次，背后的表格就被换成搜索结果，而筛选条还写着原来的条件。
- 下拉里那一行是「书名 / 作者 · `status_display`」——中文词由后端给，
  前端不查 `STATUS_LABELS`（同一件事在两个地方各译一遍，早晚不一致）。
