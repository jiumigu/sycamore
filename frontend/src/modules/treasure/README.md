# Treasure — 好恶物档案馆前端

## Views

| 文件 | 路由 | 职责 |
|------|------|------|
| `views/TreasureHub.vue` | `/treasure` | 主页面：类型/记录对象/类别三层筛选 + 待补理由出口 + 卡片网格 + 新增编辑弹窗 + 详情弹窗 |

## Components

| 文件 | 职责 |
|------|------|
| `components/TreasureCard.vue` | 单张档案卡。`categoryText` computed 按侧取文案；方法型显示「💡 方法 · 生活」 |
| `@/modules/wealth/components/common/TreasureQuickMark.vue` | **两秒快记浮层 + 评价徽标**（两处实物列表共用）。放在 wealth 下是因为使用点都在 wealth 内，放进 `shared/` 会让 shared **反向依赖 module** |

## Store

`useTreasureStore`（`stores/treasureStore.ts`，Composition API，带 `acceptHMRUpdate`）

| 状态 | 类型 | 说明 |
|------|------|------|
| `thingList` | `GoodThing[]` | 列表（**后端不分页 ⇒ 裸数组**） |
| `loading` | `boolean` | 加载中 |
| `loadError` | `boolean` | 🔴 **列表取数失败**（区别于「一条都没有」） |
| `meta` | `TreasureMeta \| null` | 口径与枚举（类别文案按侧各一套） |
| `metaUnavailable` | `boolean` | computed，`meta === null` |
| `pendingCount` | `number` | ⭐ 待补理由的条数 |

| 方法 | 用途 |
|------|------|
| `fetchMeta()` | 拉口径。失败置 `meta = null`（**不顶一份前端默认文案**） |
| `categoriesFor(recordType)` | 取某一侧的类别选项；取不到返回 **`[]`** |
| `fetchThingList(params)` | 拉列表。失败置 `loadError = true` |
| `fetchPendingCount()` | 单独查一次「待补理由」条数 |

⚠️ `fetchPendingCount()` 是**拉全量再 `.length`**（后端列表不分页，没有 count 接口）。
档案量大了会白拉一批数据 —— 要优化就先在后端加一个 count 端点，别在前端猜。

## API

`api/treasureApi.ts` — 7 个函数：`getThingList` `getThingDetail` `createThing`
`updateThing` `deleteThing` `getTreasureMeta` `getLinkCandidates`

## Types

`types/treasureTypes.ts` —— `GoodThing` / `TreasureOption` / `TreasureMeta` /
`LinkCandidate` / `LinkCandidateResult` / `LinkedFacts`

🔴 **本文件不再有 `CATEGORY_OPTIONS` / `CATEGORY_EMOJI`** ——
类别文案的唯一真源是后端 `categories_by_type`。前端写第二份的后果是
「歹物下拉里躺着『好店』」那个 bug 的复现（label 自带褒贬，分不了侧就是错的）。
常量只留 `SUBJECT_KIND_PHYSICAL` / `SUBJECT_KIND_METHOD` 两个字面量。

## 三个「错了也不报错」的地方（改这块前先读）

1. **类别文案必须按侧取。** `store.categoriesFor(record_type)`，好物侧「🏪 好店」、
   歹物侧「🏪 坑店」。写死一份就是上面那个 bug。
2. **`el-form` 的 `:validate-on-rule-change="false"` 是必需的**（不是优化）。
   `formRules` 是 computed（类别必填跟着 `isPhysical` 走），而 Element Plus
   默认 `validateOnRuleChange: true`，对 `rules` 挂了 `watch(deep)`，一变就校验整张表
   ⇒ 用户刚打开弹窗、只是戳了一下「记录对象」，空表单立刻满屏飘红。
   关掉它**不影响提交校验**，`handleSubmit` 里是显式 `validate()`。
3. **名称那一格变了，要分清「从候选选中」与「手工敲的」。**
   手工敲 ⇒ **清掉旧关联**。留着它就会出现「档案名是手工写的、却关联着另一件东西」，
   界面看起来完全正常。**不做「按名字猜着关联」的兜底。**

## 三处「取不到 ≠ 没有」

| 位置 | 现象 | 处置 |
|---|---|---|
| `loadError` | 接口挂了 → 列表空 → 用户去重复登记一条 | 红色 alert + 空态文案改成「列表没取到 —— 先看上面那条红字」 |
| `metaUnavailable` | 口径没取到 → 下拉空 → 看起来像「这模块本来就只有这些类别」 | 黄色 alert |
| `badge is None` | 从没评过 | **什么都不显示**，不渲染灰色「无」 |

⚠️ `emptyText` computed 里的**顺序有意义**：先问「是不是没取到」，再问「是不是真的没有」。

## 交互入口（跨模块联动）

| 入口 | 在哪 | 说明 |
|---|---|---|
| ① 行内两秒快记 | 物件资产 / 物品清单的行内 | Popover 不是 Dialog。**理由可留空** |
| ② 徽标回流 | 同上 | 后端下发只读字段，前端**不拉全量档案建 map**（会被分页静默截断） |
| ③ 名称输入即搜 | 档案馆新增弹窗的「名称」格 | `el-select` filterable remote；footer 提示「还有 N 条没显示」 |
| ④ 待补理由出口 | 页头 | `pendingCount > 0` 时显示「📝 N 条待补理由」，点一下筛出留空的那批 |
| ⑤ 关联事实 + 🔗 跳回 | 详情弹窗 / 卡片 | 事实只在**详情**下发（列表里逐条算折旧是 N+1） |

`?focus=<档案 id>` —— 从物件行内点已有徽标时跳过来，直接打开那条去补理由。

## 🔴 快记浮层两个「点了没反应 / 选了丢」的坑（`TreasureQuickMark.vue`）

两条都是**实测**揪出来的，都不报错，只是交互静默失效（详见 TECH-NOTES §67 之 §10/§11）：

1. **`el-popover` 的 `trigger="click"` 与 reference 内按钮的 `@click` 各消费一次同一点击。**
   按钮的 `open()` 设 `visible = true`，事件继续冒泡到 reference ⇒ trigger 又 toggle 回 `false`
   ⇒ 净效果「打开又被立刻关掉」。
   ✅ 必须写 `@click.stop`。判据：**popover / dropdown 的 reference 里放自己的可点元素时都要 `.stop`**。
   ⚠️ 点面板外关闭不受影响（那是 document 级监听）。
2. **浮层里的 `el-select` 必须 `:teleported="false"`。**
   下拉默认 teleport 到 `<body>` ⇒ 不在 popover 子树里 ⇒ 被 click-outside 判成「点了外面」
   ⇒ 浮层关闭、选择丢失（`persistent:false` 时直接卸载，Playwright 报 `element was detached`）。
   ⚠️ 副作用：下拉不再逃逸于浮层之外，浮层若有 `overflow: hidden` 会被裁 —— 改布局要实测。

另：列表行内浮层应加 `:persistent="false"`（物件资产一页 78 行 = 78 份常驻 DOM，关闭即卸载）。
