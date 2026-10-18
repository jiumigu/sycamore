"""评价徽标 —— 从档案回流到两个实物池的**只读**标识（v3.60.32）

## 三条纪律

1. 🔴 **真源唯一在本 app**（`GoodThing.record_type`）。物件资产 / 物品清单
   **不加**「是不是好东西」字段，也不缓存徽标 —— 缓存一分就会在改档案后漂移，
   而漂移是**静默的**（界面上两处说法不同，谁也看不出哪个对）。

2. 🔴 **不给前端「拉全量档案本地建 map」的口子**。档案会增长，全量拉取一旦
   被分页截断就是**静默缺标识** —— 有些行有徽标、有些没有，看起来像
   「本来就没人评过」，而不是「徽标没取到」。

3. ⚠️ **👎 ≠ 该报废**。徽标与 `status` / `condition` 是**三把正交的尺子**：
   - `status`：我还要不要它
   - `condition`：它现在好不好使（客观）
   - 徽标：我认为这东西值不值（主观）

   冰箱可以「状况=正常」却 👎（型号选错，用着别扭）；空调可以「状况=坏了」
   却仍是 👍（用了 12 年，值了）。**三者并列显示、互不推导**，
   徽标不参与任何计算，也不影响任何统计口径。
"""


def _field_for(kind: str) -> str:
    if kind == 'property':
        return 'property_id'
    if kind == 'survival_item':
        return 'survival_item_id'
    raise ValueError(f'未知的关联类型：{kind}')


def badge_map(kind: str, ids: list[int]) -> dict[int, tuple[str, int]]:
    """{实物 id: (record_type, 档案 id)}。

    一件实物最多一条档案（1:1，由 `UniqueConstraint` 保证）⇒ 直接映射，
    不需要聚合、也不会有「两条档案抢同一件实物」的歧义。

    ⚠️ 连带把**档案 id** 一起带出来：已评价时点徽标应该「打开那条去补理由」，
       而不是再建一条。只给 `record_type` 的话前端就只能重新登记一次。
    """
    clean = [i for i in ids if i is not None]
    if not clean:
        return {}
    field = _field_for(kind)
    # 函数内 import：避免 app registry 未就绪时被模块级 import 拖住
    from .models import GoodThing

    return {
        getattr(row, field): (row.record_type, row.id)
        for row in GoodThing.objects.filter(**{f'{field}__in': clean}).only(field, 'record_type')
    }


def attach_badges(rows: list[dict], kind: str) -> list[dict]:
    """就地给每行补三样东西：徽标、档案 id、类别预填建议。

    | 键 | 含义 |
    |---|---|
    | `treasure_badge` | `None` / `'好'` / `'歹'` |
    | `treasure_record_id` | 已有评价时那条档案的 id（点徽标去**同一条**补理由） |
    | `treasure_suggest_category` | 快记浮层里类别下拉的预填值（后端按物件类别猜的） |

    ⚠️ `treasure_badge` 为 `None` 表示**还没有评价** ⇒ 界面什么都不显示。
       不要渲染成灰色的「无」或占位符 —— 那会让「没人评过」看起来像
       「评过了、结论是没有」，而这两件事该采取的行动不同。

    ⚠️ 类别建议**也在后端算**：前端拿 `category_name` 自己映射就是第二份口径，
       而这类「前端猜一个看着合理的默认值」正是假话的源头
       （项目判据：字段在某条口径下没有含义时，宁可用空，不给「看着合理」的默认值）。

    ⚠️ 一次 SQL 查完这一页（不是逐行查）：列表是 78 / 58 件的量级，
       逐行查就是 N+1，而它在小数据量下**看不出来**，等数据涨了才会慢。
    """
    from .constants import suggest_category_for_property

    mapping = badge_map(kind, [row.get('id') for row in rows])
    for row in rows:
        hit = mapping.get(row.get('id'))
        row['treasure_badge'] = hit[0] if hit else None
        row['treasure_record_id'] = hit[1] if hit else None
        row['treasure_suggest_category'] = suggest_category_for_property(
            row.get('category_name') or '',
        )
    return rows
