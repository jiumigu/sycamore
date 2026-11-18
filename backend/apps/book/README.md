# Book — 书籍阅读

> 文档对齐 v3.64.79 ｜ 最后核对 2026-11-18

## Models
| Model | Table | 用途 |
|-------|-------|------|
| Book | book_read_list | 书籍阅读记录（含 11 种分类、**6 种状态**、5 级阅读深度） |
| ReadingFocus | book_reading_focus | 当前在读的那一本（全库一行；与 `Book.status` 无关） |

## 状态只有 6 个（v3.64.79）

`status` 只说「这本书在流程的哪一步」，**不说读得多细** —— 读法看 `reading_depth`。

| key | label | 说明 |
|---|---|---|
| `to_read` | 待读 | 还没开始（含「想再读一遍」） |
| `reading` | 在读 | 正在读 |
| `rereading` | 在读二刷 | 读完了，正在读第二遍 —— 与 `reading` **同色**，靠文字区分 |
| `finished` | 已读完 | 读完并记了阅读日期 |
| `shelved` | 搁置 | 暂停但没弃，可以捡回来 |
| `abandoned` | 弃读 | 终止；`abandon_reason` 必填（逐本，不允许批量） |

🔴 判断状态**一律用 `Book.STATUS_*` 常量**，不许写中文字面量也不许写裸英文字符串：
v3.64.79 之前 `summary` 里 `status='已完成'` 就是这么漏的，漏了不报错，
只是「某天读完的书」静默变成 0。

🔴 **「在读」统计含二刷**（`Book.STATUS_ACTIVE = (reading, rereading)`）：
二刷也是正在读，只数 `reading` 会让二刷的书在统计里凭空消失。

`精读 / 通读 / 消遣` 已并入 `reading` / `finished`（迁移 `0006_book_status_v2`，多对一、不可逆）；
它们原本说的「读得多细」由 `reading_depth`（速读浏览 → 践行内化）承担，迁移**不动这个字段**。

## API Endpoints

前缀 `/api/books/`

| 方法 | 端点 | 用途 |
|------|------|------|
| GET | /books/ | 列表（?type=&status=&year= 筛选） |
| POST | /books/ | 创建 |
| GET/PUT/DELETE | /books/&lt;pk&gt;/ | 详情/更新/删除 |
| GET | /books/stats/ | 年度/月度阅读统计 |
| GET | /books/by_year/ | 按年份列表（?year=） |
| GET | /books/by_type/ | 按类型列表（?btype=） |
| GET | /books/search_by_tag/ | 按标签检索（?tag=） |
| POST | /books/&lt;pk&gt;/mark_completed/ | 标记读完 |
| DELETE | /books/bulk_delete/ | 批量删除（body: `{bids: []}`） |
| GET | /books/reading-focus/ | 当前在读的那一本（`book` / `started_on` / `days`）。只读，看一眼**不会建行** |
| GET | /books/reading-focus/candidates/ | 换书的候选（?search=）。口径见下节，不分页，上限 `CANDIDATE_LIMIT=20` |
| POST | /books/reading-focus/switch/ | 换书（body: `{book_id, close_mode?, reason?}`）。有旧书**必须**给结论，否则 400 |

## 换书的候选集（v3.64.81）

`GET /books/reading-focus/candidates/` 只返回**还能读**的书：

- ✅ `to_read` / `reading` / `rereading` / `shelved`
- ❌ `finished` / `abandoned`（要二刷先把状态改成「在读二刷」；弃读是已经决定不读的书）
- ❌ 当前这本（选它会被 switch 400 拒掉，摆在下拉里就是让人点一个必然失败的选项）

口径的唯一实现在 `ReadingFocusService.candidate_queryset()`，元组是 `Book.STATUS_SELECTABLE`。
🔴 前端**不许**再筛一遍：v3.64.81 之前候选集就是「整张书单按 `-updated_at` 截 20 条」，
93 本「已读完」全躺在「接下来读哪本」里 —— 一个没写过滤的列表，看起来毫无破绽。

选中后的状态推进：`to_read` → `reading`；**`shelved` → `reading`**（捡回来了，留着「搁置」与指针矛盾）；
`reading` / `rereading` 不动（降级会抹掉「第几遍」）。
