# Core — 系统基础设施

## 职责
Django 项目通用基础设施，不归属任何业务模块。

## 包含

| 文件 | 用途 |
|------|------|
| `pagination.py` | `StandardPagination` — 默认 10 条/页，支持 page_size 参数 |
| `models.py` | 全局共享模型 + UserProfile |
| `admin.py` | 系统管理后台配置 |
| `views.py` | 通用视图 + ProfileView |
| `db_comments.py` | **数据库注释（表 / 列）的唯一实现** —— 判据、例外文案、接管范围 |
| `management/commands/audit_comments.py` | **只读**注释体检：缺口清单（表 / 列 / 英文残留 / 外部表 / 未接管 app） |
| `management/commands/sync_field_comments.py` | ⚠️ **已被 `db_comments.py` 取代**，保留仅作应急手工入口 |

## 数据库注释（表 COMMENT / 列 COMMENT）

**为什么要有这一块**：Django 建表时**只**把 `Field.db_comment` 送进列的 `COMMENT`、
只把 `Meta.db_table_comment` 送进表的 `COMMENT`。`verbose_name` 写得再全**也不会进库**。
本项目此前 0 处用过这两个属性 ⇒ 2026-10-16 审计时 **109 张表表注释全空**、
616 个字段没有列注释 —— 数据库工具里看不出这张表是干什么的。

| 层 | 位置 | 管什么 |
|---|---|---|
| 判据（唯一实现） | `apps/core/db_comments.py` | 派生规则、例外文案、`%` 归一、接管范围白名单 |
| 挂载 | `apps/core/apps.py` 的 `CoreConfig.ready()` | 把判据写进各模型的 `field.db_comment` **与** `Meta.db_table_comment` |
| 表说明 | 各模型 `Meta.db_table_comment` | 一句话：这表是什么 / 真源还是存档 |
| 落库 | 迁移里的 `AlterField` + `AlterModelTableComment` + `RunSQL` | 批 1：`wealth/0030_db_comments.py`；批 2：`selfrun/0004`、`toolkit/0024`、`redemption/0008`、`lifesample/0005`、`temporal/0014`、`relation/0008`；批 3：`travel/0008`、`core/0010`、`works/0004`、`summary/0005`、`health/0007`、`goals/0016`、`book/0004`、`treasure/0004`、`sugar/0007`、`reward/0006`、`dams/0002`、`inbox/0006`、`food/0002`、`dance/0002` |

### 四条硬约定（改前必读）

1. 🔴 **列注释默认从 `verbose_name` 派生，不要逐字段手写 `db_comment`。**
   2026-10-16 取证：库里存量注释 **773/815（98.1%）与 `verbose_name` 逐字相同** ——
   「列注释 = verbose_name」本来就是本项目的既有口径。再手写一遍就是把同一事实
   存成两份：`verbose_name` 改了，手写的不会跟着改，**必然静默漂移**。
   `verbose_name` 说不清楚的（单位 / 「空」的含义 / 结构约束 / 真源指针）才进
   `COLUMN_COMMENT_OVERRIDES`。
2. 🔴 **注释文案只写「不随业务变化的稳定事实」。**
   不写枚举取值清单、派生公式、阈值 —— 那些的真源在 `constants.py` / `services.py`，
   抄进库里就是第三把尺子。**指针 ≠ 副本**：写「取值见 `constants.XXX_CHOICES`」
   不会漂移，抄一份会。
3. 🔴 **注释里不能出现半角 `%`（会被自动转成全角 `％`）。**
   Django 把注释内联进 `ALTER TABLE ... MODIFY COLUMN` 之后还要过一次
   `sql % params`，而注释那一路 `params` 是空列表 ⇒ 注释里的 `%` 被当成格式化
   占位符，抛 `ProgrammingError: not enough arguments for format string`，
   **整条迁移半路崩掉**，而 MySQL 的 DDL 不可回滚。详见 `db_comments.normalize_comment`。
   **表注释同样会炸**（表注释走 `sql_alter_table_comment % {dict}`，值不被二次解释，
   但最后仍落到 `cursor.execute(sql, ())`）⇒ `apply_table_comments()` 也做了归一化。
4. 🔴 **表级属性与列级属性的「可见性」不同 —— 只改 `_meta` 对 `makemigrations` 无效。**
   `ModelState.from_model()` 读表注释读的是 **`_meta.original_attrs`**（类定义时记下的
   原始 kwargs），不是 `_meta.db_table_comment`。2026-10-16 实测：只改后者，
   `ProjectState.from_apps()` 读到的**仍是旧值**，`makemigrations` 当作什么都没发生。
   字段层没这个问题（`field.db_comment` 是字段自身属性，`clone()` 会带上）。
   ⇒ `apply_table_comments()` 必须**同时**写 `_meta.db_table_comment` 与
   `_meta.original_attrs['db_table_comment']`；改完用 `ProjectState.from_apps()` 复验。

### 接管范围是白名单，分批推进

`DOCUMENTED_APPS` 显式列出已接管的 app。派生一旦生效，
`makemigrations` 就会为该 app 的每个字段生成 `AlterField` ⇒ 全项目一起生效
等于一步生成 600 多个列变更的迁移。**未列出的 app 不派生、也不产生迁移。**

| 批次 | app | 规模 |
|---|---|---|
| 批 1（v3.62.20） | `wealth` | 27 表 / 294 列 |
| 批 2（v3.62.21） | `selfrun` `toolkit` `redemption` `lifesample` `temporal` `relation` | 34 表 / 436 列 |
| 批 3（v3.62.22，收尾） | `travel` `core` `works` `summary` `health` `goals` `book` `treasure` `sugar` `reward` `dams` `inbox` `food` | 38 表 / 438 列 |

**批 3 之后已收尾**：白名单 = 全项目所有 `managed` 表所在的 app（20 个）。
以后**新增 app 或新增表**时必须同步动作，否则会有静默缺口：

| 加了什么 | 必须做什么 | 谁会报出来 |
|---|---|---|
| 新增一个 app | 往 `DOCUMENTED_APPS` 补一行 | `test_db_comments` 的「每张接管的表都要有中文表注释」不会报（新 app 不在白名单里）；`audit_comments` 会报「未接管的 app」 |
| 新增一张 `managed` 表 | 写 `Meta.db_table_comment` + 进白名单 | `test_every_documented_model_has_a_chinese_table_comment` 立刻变红 ✅ |
| 新增一张外部表 / M2M 自动中间表 | 迁移里补 `RunSQL` | M2M 有 `test_auto_created_through_tables_are_registered` 兜；**外部表只能靠 `audit_comments`** |

> `dance` 是**纯外部表 app**（只有一个 `managed=False` 的 `DanceRecord`），
> 没有 managed 表可接管 ⇒ 不进白名单；它的表注释由 `dance/0002_db_comments.py` 的 `RunSQL` 负责。

⚠️ **分发批次时的判据**：取「**含待修 bug 的 app**」与「**缺口最大的 app**」的**并集**。
只按缺口排会漏掉 bug（批 2 的英文注释分散在 5 个小 app 里，只做 selfrun 就修不干净）。

### 两张管不到的表

- **M2M 自动中间表**：autodetector 完全忽略（2026-10-16 实测检出操作数 0）
  ⇒ 只能走迁移里的 `RunSQL`，并登记进 `RUNSQL_ONLY_TABLES`。
- **`managed=False` 的外部表**：autodetector 同样跳过 ⇒ 表注释只能 `RunSQL`。
  ⚠️ 它们的列注释当年导进来时就是齐的，**通常比 `verbose_name` 更准**，
  发表注释可以、**别用 `verbose_name` 去覆盖列注释**。
  ⚠️ 列注释要改得 `MODIFY COLUMN` 并带**完整列定义** —— Django 不托管这些表的结构，
  动列定义风险大于收益 ⇒ **一律不动列注释**，这是有意为之的已知例外。

  **全项目外部表 14 张**（2026-10-16 批 3 清点）。其中**由本机制补表注释**的 8 张：
  `wealth_cash_flow` / `wealth_balance_list` / `wealth_regular_list`（批 1）、
  `temporal_time_atracker_tasks_list` / `temporal_oneday_page_list`（批 2）、
  `travel_list_info` / `health_step_info`（批 3）、`hobby_dance_list`（批 3，`dance`）。
  其余 6 张（`china_city_coord` / `relationship_relationship` / `relationship_interaction` /
  `toolkit_definition` / `toolkit_execution` / `wealth_bill_list`）**库里本就有中文表注释**，不重复改。

  ⚠️ 接管一张外部表之前，先确认它在 `conftest.py` 里有镜像，否则重建测试库时 `RunSQL` 会中断整轮（§98.7）。
  ⚠️ 测试库里读不到这些注释是**正常的**（`--no-migrations` 建库，注释只存在于开发库），
  别把它当成缺口 —— 这正是「库级验证」不能塞进单元测试的原因。

### 回归用例

`apps/core/test_db_comments.py`（11 条）。守的是**源头**：漏写表说明、`verbose_name`
退回英文、覆盖表 key 拼错、注释含半角 `%`。

⚠️ 它**不查 information_schema** —— 测试库用 `--no-migrations` + `--reuse-db` 建，
迁移里的 `RunSQL` 在测试下从不执行，库里的注释不可复现。**库级验证由
「跑 `migrate` + 只读复查 information_schema」承担**，不在测试里假装。

### 库级自检（迁移跑完之后）

```bash
cd backend && ../.venv/bin/python manage.py audit_comments          # 只读；有缺口则退出码 1
cd backend && ../.venv/bin/python manage.py audit_comments --verbose  # 列全清单
```

打出来的五节就是全部缺口类型：表注释缺失 / 列注释缺失 / 注释不含中文 / 半角 `%` /
外部表表注释为空，外加「还有哪些 app 没接管」。

**期望**：`migrate` 跑完之后**全部为 0**，末行显示
`✅ 无缺口：表注释、列注释、语言、外部表 全部就绪`。
若还留着缺口，顺序是：先确认 `migrate` 跑没跑（`verbose_name` 写全了也不进库），
再查是不是新加的表忘了写 `Meta.db_table_comment`。

⚠️ **它只读，不是第二个写入口** —— 改注释的唯一路径是「改模型 → `makemigrations` → `migrate`」。
别把它改成写入口（那就会长出一个绕过迁移的旁路，与 `sync_field_comments.py` 同样的病）。

## 管理命令

```bash
.venv/bin/python backend/manage.py audit_comments        # 只读体检（推荐）
.venv/bin/python backend/manage.py sync_field_comments   # ⚠️ 已被取代，不推荐
```

⚠️ **`sync_field_comments` 已被 `apps/core/db_comments.py` 取代（v3.62.20）**，保留仅作应急手工入口。
它与新机制的三处本质差异：**不写表注释**、**无法表达例外文案**、**结果不可追溯**
（手工执行，不进迁移）。另外它原先会连 `managed=False` 的外部表一起改 ——
那会把库里本来更准的注释覆盖成 `inspectdb` 生成的英文 —— 现已加护栏跳过外部表。
是否删除该命令属**用户决策**。

> 两者的关系不是「替代」而是「分工」：`sync_field_comments` 是**写**（已退役），
> `audit_comments` 是**读**（新补的体检口子）。体检这件事以前没有工具，
> 所以「`hobby_dance_list` 表注释空着」才一直没人发现。

## Pagination

所有 ModelViewSet 默认使用 `StandardPagination`，返回格式：
```json
{
  "count": 总条数,
  "next": 下一页URL,
  "previous": 上一页URL,
  "results": [...]
}
```

## 跨模块配置项（统一挂 UserProfile）

单人系统没有独立的配置表，**跨模块的用户配置一律挂在 `UserProfile`**（单例，`user_id=1`）。

| 配置 | 字段 | 默认 | 读取方 | 写入方 |
|---|---|---|---|---|
| 金句池长度上限 | `quote_pool_max_len` | 500 | `toolkit` 的 `resolve_quote_pool_max_len()`（供 `QuoteViewSet.next` / `stats` / `?pool=` 用） | 系统设置页 `core/admin/views/AdminSettings.vue` |

约定（三条，改配置项时都适用）：

- 🔴 **默认值的单一真源是模型字段的 `default`**（`DEFAULT_QUOTE_POOL_MAX_LEN`）——
  读取端在缺配置行时**回落到它**，不另写一个数字（否则改默认值时两处不一致，而界面上看不出来）。
- 🔴 **合法区间也是单一真源**（`QUOTE_POOL_LEN_RANGE`），由
  `GET /core/profile/` 的 `quote_pool_len_range` **下发给前端**，
  前端不硬编码 min/max（同 `RATIO_BANDS` 的判据：阈值只该有一份，前端只负责显示）。
- 🔴 越界值 **400 报错，不静默夹取** —— 悄悄改成边界值会让用户以为配置生效了。
## Privacy Mode

单人系统的隐私脱敏体系，通过 `UserProfile` 模型控制全局开关。

### Backend

| 文件 | 用途 |
|------|------|
| `models.py:UserProfile` | `user_id`(PK) + `privacy_mode`(BooleanField) + `logseq_path`(CharField) + `quote_pool_max_len`(PositiveIntegerField)，单例模式 |
| `views.py:ProfileView` | `GET /api/core/profile/` 获取配置，`PATCH /api/core/profile/` 更新开关 |
| `urls.py` | `path('profile/', ProfileView.as_view())` |

### Frontend

| 文件 | 用途 |
|------|------|
| `core/privacy/api/privacyApi.ts` | `getProfile()` / `updateProfile(data)` |
| `core/privacy/stores/privacyStore.ts` | Pinia store: `privacyMode` ref, `fetchProfile()`, `togglePrivacyMode()` |
| `shared/utils/privacy.ts` | 纯函数脱敏工具：`maskName`、`maskAmount`、`maskAmountByType`、`maskLocation`、`maskText`、`maskTags` |
| `shared/components/layout/LayoutHeader.vue` | 隐私开关按钮（Lock/Unlock 图标） |
| `shared/components/layout/AppLayout.vue` | 隐私模式蓝色横幅提示 |

### 脱敏规则

| 函数 | 规则 | 示例 |
|------|------|------|
| `maskName` | 首字 + `*` | 吴琦 → 吴\* |
| `maskAmount` | 固定掩码 | ¥50,000 → ¥\*,***.** |
| `maskAmountByType` | 仅收入脱敏，支出不脱敏 | 收入→¥\*,***.** / 支出→¥50,000.00 |
| `maskLocation` | 前2字 + `***` | 福州鼓楼区 → 福州\*\*\* |
| `maskText` | 前2字 + `***` | 大学社团活动认识 → 大学\*\*\* |
| `maskTags` | 固定 `***` | 朋友, 同事 → \*\*\* |

### 已覆盖模块

关系（姓名/标签/地点/场景/备注）、旅行（目的地/花费）、目标（里程碑金额）、理财（月度日历收支汇总/日明细/周明细/定期存款）
