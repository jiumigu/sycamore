# Works — 作品

> 文档对齐 v3.64.34 ｜ 最后核对 2026-11-07

> **一件从经历里长出来、以后还能再用的东西。**（可以只有自己看）

它不是「输出次数」的翻版：KPI 是**计数**（这一期做了几回），本模块是**清单**（留下了哪几件、分别是什么）。两者是同一件事的两面，所以**共用同一份数据** —— 自我运转「留下件数」直接数这里（`selfrun.readers.works_count`）。

## Models

两张 **managed 表**：

| Model | Table | 用途 |
|-------|-------|------|
| Work | works_work | 作品本体（名称 / 类型 / 出口状态 / 发到哪 / 展示媒体） |
| WorkCapture | works_capture | 「值得留」的勾 —— **唯一真源**，`(source_type, source_id)` 唯一 |

### 为什么捕获要单独一张表

1. 日记流是 `managed=False` 外部表，**绝不给它加列**；
2. 「待提炼」是独立事实（有自己的生命周期：待提炼 → 已收进作品），源记录删了它也在；
3. 分散加列会让收口台 JOIN 六张表，且「同一件事」的定义随各处漂移。

捕获存的是**快照**（`title` / `excerpt`），源记录改名或被删后，收口台仍能看出「当时勾的是哪一条」。

## 口径

- **七个入口**（`CAPTURE_SOURCE_CHOICES`，新增一律加在**末尾**）：里程碑 / 收件箱 / 读书 / 日记 / 摘录 / AI 问答 / 档案馆。
- **身份键必须复合** `(source_type, source_id)` —— `source_id` 是跨七张源表的裸 id，单看会撞号。
- **打勾幂等**：同一来源重复打勾只留一条；`dropped` 的来源重新打勾 ⇒ 改回 `pending`。
- **合成可逆**：删掉一件作品，它的来源**回到待提炼**（`SET_NULL` + 服务层回滚 `status`）。
- `dropped` 与「删除」不同：删除 = 误勾；`dropped` = 想留但觉得不值得单独成一件。**本模块不提供 `dropped` 界面入口**。
- **不落 `period_key`**：属于哪一期按 `created_at` 现算（ISO 周 / 自然月），落库就是第二份真源。
- **作品类型九类**（`WORK_KIND_CHOICES`，v3.64.30 起 `craft` 的 label 由「实物」改为「**其他手作**」，并列加 `drawing` / `embroidery`）：文章 / 模型 / 模板 / 清单 / 其他手作 / 绘画作品 / 刺绣作品 / 教程 / 其他，`other` 永远在最后（兜底桶）。
  🔴 改的是**取数口径**不是措辞：自我运转月度 KPI 可按作品类型自动数（`selfrun.readers.works_count` + `where.work_kind`），「画」能被填进「实物」就会**少算一件且不报错**。
  `where.work_kind` 填了不存在的类型 ⇒ `ValueError`，**绝不返回 0**（0 会被读成「这一期一件都没做」）。
- **作品媒体是媒体真源**：展厅馆藏只引用，**不重复上传**。
- 出口状态三态 `private`（只给自己）/ `ready`（准备发）/ `published`（已发）—— 「只给自己」**不是未完成**，刻意不叫 `draft`。
- 出口去向是用户维护的短清单（`core.SystemPreset` 的 `work_channels`），`DEFAULT_WORK_CHANNELS` 只在第一次开箱时 seed。

## API Endpoints

前缀 `/api/works/`

| 方法 | 端点 | 用途 |
|------|------|------|
| GET/POST | /items/ | 作品列表（?kind=&status=&period_type=）/ 新建 |
| GET/PATCH/PUT/DELETE | /items/&lt;pk&gt;/ | 作品详情 / 编辑 / 删除（来源回待提炼） |
| GET/POST | /captures/ | 待提炼列表（?source_type=&status=）/ 打勾 |
| DELETE | /captures/&lt;pk&gt;/ | 取消勾 |
| POST | /compose/ | 把若干条待提炼**合成一件作品** |
| GET | /overview/ | 顶部计数：累计 N 件 · 已发 M 件 · 待提炼 K 条 |
| GET | /meta/ | 界面枚举（类型 / 出口状态 / 来源）—— **随接口下发，前端零副本** |
| GET/PUT | /channels/ | 出口去向清单 |
| POST | /media/ | 作品媒体上传（multipart 字段 `file`） |

## 边界

- 七个入口是**同一个勾、同一个含义**，不是七次设计；新增入口必须同时改 `CAPTURE_SOURCE_CHOICES` 与对应前端页面的触发点。
- 作品删除是**可逆的**（来源回待提炼）；捕获本身被删才是「误勾」。
