"""自我运转 · KPI 模板库（**seed 源，不是运行时真源**）

🔴 2026-10-13 起模板**已落库**（`SelfRunTemplate` / `selfrun_template`）：

- 本文件的 `KPI_TEMPLATES` **只在迁移 `0002_...` 里被读一次**（seed 那 9 条内置模板）；
- **运行时一律读表**（`services.list_templates` / `services.find_template`）；
- ⇒ 改本文件**不影响任何已存在的数据库**，也**不会**让用户在界面上删掉的模板复活
  （这是刻意的：`表空就补` 会把用户删掉的条目在下次启动时悄悄放回来）。
- 要给新库补一条内置模板 ⇒ **写一条新的迁移**，别改这里再指望它生效。
- 🔴 本文件是**新库的 seed 源**，而**已存在的库**靠迁移追平：
  改「输出次数 / 内容输出」的口径（v3.62.0）时，本文件与
  `migrations/0003_switch_output_kpi_to_works_count.py` **两处都要改**，
  且**两处都要绕开已建阶段**（`selfrun_metric`）—— 见下条铁律 1。

🔴 四条铁律（`sycamore-managed-table-feature` §3.4）：

1. **模板是「拷贝」不是「引用」** —— 阶段生效时把模板值**抄进** `SelfRunMetric`。
   模板后来改了，**不影响已建阶段**；否则「改模板」会**回溯改写历史口径**。
2. **`template_key` 只记来源，不参与取数** —— 它只回答「这条 KPI 是哪来的」。
3. **`source_config` 里不含 `agg`** —— `agg` 是 `SelfRunMetric` 的**列**，
   两处都存就是「第二份真源」。
4. **`goal_value` / `floor_value` 允许为 `None`** ——「只有目标没有底线」是合理状态；
   `None` ≠ 0，界面显示「—」，且**两条都空 ⇒ 该条只展示不判定**（`unconfigured`）。

⚠️ 改本文件**不会**影响任何已存在的阶段（见铁律 1）。
"""

# ══════════════════════════════════════════════════════════════
# 首轮 9 条（周 5 + 月 4）
# ══════════════════════════════════════════════════════════════

KPI_TEMPLATES = [
    # ── 周度 ──────────────────────────────────────────────────
    {
        'key': 'grow_hours',
        'name': '成长小时数',
        'period_type': 'weekly',
        'unit': 'h',
        'direction': 'at_least',
        'goal_value': 12,
        'floor_value': 5,
        'agg': 'sum_hours',
        'source_kind': 'auto',
        # 🔴 口径：读**库**里的 `activity_type`（`temporal_task_meta`），
        #    不是读常量表、也不走 redemption 侧的归因规则。
        #    `ONEDAY`（写日记）当前就在「深度工作」桶里 —— 用户 2026-10-12 拍板**计入**。
        'source_config': {'kind': 'temporal_hours', 'where': {'l2': ['深度工作']}},
        'goal_why': '你写的：一天 3 小时 × 4 天 = 12h',
        'floor_why': '近 11 周中位数 5.50h · 达标 7/11（2026-10-13 设）',
        'sort_order': 10,
    },
    {
        'key': 'output_count',
        'name': '留下件数',
        'period_type': 'weekly',
        'unit': '件',
        'direction': 'at_least',
        'goal_value': 2,
        'floor_value': 1,
        'agg': 'count',
        'source_kind': 'auto',
        # 🔴 v3.62.0 口径变更：从「数日记流 MIGU 的条数」改成「数**作品库**的件数」。
        #    理由：「输出 2 次」与「留下 2 件」在你的真实场景里**大半是同一件事**
        #    （写一篇公众号 = 输出一次 = 留下一件），数两遍迟早得出
        #    「输出达标了但沉淀没达标」这种荒谬结论。
        #    ⚠️ `key` **刻意不改** —— 它是 `Metric.template_key` 的指向。
        #    ⚠️ 旧口径的 64 行越界值那条注意，随本次变更**一并作废**（不再走日记流）。
        'source_config': {'kind': 'works_count'},
        'goal_why': '一周留下两件是节奏',
        'floor_why': '一件是底线',
        'sort_order': 20,
    },
    {
        'key': 'go_out_days',
        'name': '出门天数',
        'period_type': 'weekly',
        'unit': '天',
        'direction': 'at_least',
        'goal_value': 5,
        'floor_value': None,
        'agg': 'distinct_days',
        'source_kind': 'auto',
        'source_config': {'kind': 'step_days', 'where': {}},
        'goal_why': '中午前离开房子就算；你的身体需要光、需要动',
        'floor_why': '',
        'sort_order': 30,
    },
    {
        'key': 'social_days',
        'name': '社交连接',
        'period_type': 'weekly',
        'unit': '天',
        'direction': 'at_least',
        'goal_value': 1,
        'floor_value': 1,
        'agg': 'distinct_days',
        # 🔴 首轮**唯一**的 `auto_plus_manual`：
        #    线下聊天你未必记时间 ⇒ 自动源**结构上覆盖不到**，需要补记。
        'source_kind': 'auto_plus_manual',
        'source_config': {'kind': 'temporal_days', 'where': {'l2': ['社交']}},
        'goal_why': '1 次是通风，不是社交',
        'floor_why': '同上：1 天',
        'sort_order': 40,
    },
    {
        'key': 'xuanzhi',
        'name': '宣纸',
        'period_type': 'weekly',
        'unit': '张',
        'direction': 'at_least',
        'goal_value': 6,
        'floor_value': None,
        'agg': 'manual_sum',
        'source_kind': 'manual',
        # ⚠️ 系统里**真的没有**书法相关模块（全仓搜「宣纸/习字/练字/书法」零命中）
        #    ⇒ 手工是**唯一入口**。
        'source_config': {'kind': 'manual_sum'},
        'goal_why': '你写的：每周 6 张宣纸',
        'floor_why': '',
        'sort_order': 50,
    },
    # ── 月度 ──────────────────────────────────────────────────
    {
        'key': 'painting',
        'name': '画',
        'period_type': 'monthly',
        'unit': '张',
        'direction': 'at_least',
        'goal_value': 2,
        'floor_value': None,
        'agg': 'manual_sum',
        'source_kind': 'manual',
        'source_config': {'kind': 'manual_sum'},
        'goal_why': '你写的：一个月 2 张画',
        'floor_why': '',
        'sort_order': 60,
    },
    {
        'key': 'income_verify',
        'name': '收入验证',
        'period_type': 'monthly',
        'unit': '元',
        'direction': 'at_least',
        'goal_value': 100,
        'floor_value': None,
        'agg': 'sum_value',
        'source_kind': 'auto',
        # 🔴 **两把尺子打架，此处显式选了账单明细侧**：
        #    月结表 `wealth_balance_list.otherincome` 自 2026-05 起就是 0.0（停更），
        #    账单侧还在记（2026-07 有 1447 元、2026-10 有 6000 元）。
        #    ⇒ 走账单明细（**可逐笔溯源**），并在 `warnings` 里报月结表的差异（V2）。
        'source_config': {
            'kind': 'bill_income',
            'where': {'transaction_type': '收入', 'category': '其他收入'},
        },
        'goal_why': '100 元是「验证」不是「生存」：证明有人愿意为你的东西付钱',
        'floor_why': '',
        'sort_order': 70,
    },
    {
        'key': 'content_output',
        'name': '留下件数',
        'period_type': 'monthly',
        'unit': '件',
        'direction': 'at_least',
        'goal_value': 4,
        'floor_value': None,
        'agg': 'count',
        'source_kind': 'auto',
        # 与周「留下件数」**同名同源**：同一条尺子的两个粒度
        # （周量「这一周动了没有」、月量「这一个月攒下什么」）。
        # 名字不同反而会让人以为是两件事 —— 它们不是。
        'source_config': {'kind': 'works_count'},
        'goal_why': '每月 4 件（每周 1 件）—— 你不是全职博主，是「正在建造的人」',
        'floor_why': '',
        'sort_order': 80,
    },
    {
        'key': 'asset_checkup',
        'name': '资产盘点',
        'period_type': 'monthly',
        'unit': '次',
        'direction': 'at_least',
        'goal_value': 1,
        'floor_value': None,
        'agg': 'boolean',
        'source_kind': 'auto',
        # ⚠️ 设计稿附录 A 留了一条「待修正：`wealth_asset_snapshot` 的取数形态」——
        #    本模板只问「**本月有没有盘过**」（快照新鲜度），不问金额。
        'source_config': {'kind': 'module_value', 'where': {'key': 'wealth.snapshot_fresh'}},
        'goal_why': '每月 1 次，确认「我还安全」，不是反复审判「我够不够」',
        'floor_why': '',
        'sort_order': 90,
    },
]

# 便于按 key 取
TEMPLATE_BY_KEY = {t['key']: t for t in KPI_TEMPLATES}

# 模板字段 → `SelfRunMetric` 字段的**拷贝映射**（只列要抄的键，顺序也是写入顺序）
TEMPLATE_COPY_FIELDS = (
    'name', 'period_type', 'unit', 'direction', 'agg', 'source_kind', 'sort_order',
)
