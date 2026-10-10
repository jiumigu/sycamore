"""比率判定线查表 —— RATIO_BANDS 的唯一读者（v3.58.23，P2-A）

为什么单独一个模块而不是放进 ratio_service：
    `cashflow_service._build_overview` 也要给应急金月数上判定级别，
    而 `ratio_service` 又需要 `cashflow_service` 的资产取数 ——
    若把查表放在 ratio_service，两边就构成循环导入。
    查表本身只依赖 constants，抽出来即解耦，且保证**只有一份实现**。

⚠️ 本模块**不含任何阈值字面量**。所有区间都从 `constants.RATIO_BANDS` 取 ——
   想在别处再写一个 `if value > 6:` 之前，先想想为什么这里不够用。
"""

from apps.wealth.constants import RATIO_BANDS, RATIO_ORDER


def ratio_meta(key: str) -> dict:
    """取某比率的元信息（标签/单位/方向/公式/口径说明/判定区间/目标值）。

    调用方通常只需要把返回值透传给前端 —— 区间与口径说明一并下发，
    前端据此画刻度、写气泡提示，从而**不必复制任何阈值数字，也不必
    在界面上另写一份口径文案**（两处口径迟早会不一致）。
    """
    spec = RATIO_BANDS.get(key) or {}
    bands = spec.get('bands')
    return {
        'key': key,
        'label': spec.get('label') or key,
        'unit': spec.get('unit') or '',
        'direction': spec.get('direction') or 'neutral',
        'formula': spec.get('formula') or '',
        # 口径说明：给人看的口径要点（分子分母怎么取、什么情况下不算）。
        # 元组 → 列表：前端按数组遍历渲染，不必再拼字符串。
        'note': list(spec.get('note') or ()),
        # 元组 → 列表：DRF/JSON 序列化元组虽可行，但显式转成列表
        # 更贴近前端消费的形状（区间是数组的数组）。
        'bands': [list(b) for b in bands] if bands else None,
        'target': spec.get('target'),
    }


def all_ratio_meta() -> list[dict]:
    """判定线总表里**全部**指标的元信息。

    ⚠️ 包含**不进比率面板**的三项（活期占比 / 负债率 / 公积金占比）——
       它们只供资产健康指标卡。`RATIO_ORDER` 是「比率面板展示哪些」的
       唯一清单，不是「总表里有哪些」。用 `RATIO_ORDER` 过滤会给出一份
       缺三项的元信息，而那三项正是卡片上要挂气泡提示的。

    顺序：先 `RATIO_ORDER` 的六项（面板展示顺序），再补上卡片专用项
    （按 `RATIO_BANDS` 的声明顺序），保证同一份数据每次都同序。
    """
    ordered = list(RATIO_ORDER)
    ordered += [k for k in RATIO_BANDS if k not in ordered]
    return [ratio_meta(k) for k in ordered]


def grade_ratio(key: str, value) -> dict:
    """按判定区间给比率定级 → {'level', 'level_label'}。

    命中条件是「value < hi」而**不校验下界**：
      · 区间升序排列，第一个满足 `hi is None or value < hi` 的即命中；
      · 负值（净值为负、覆盖率为负）自动落进第一档，无需在服务层补特例；
      · 区间是「左闭右开」，故 6.0 落在「6–12」而不是「3–6」——
        判「尚可/充足」的分界点必须唯一，不能两个档位同时成立。
    value 为 None 或该比率没有判定区间时返回空级别：
      · 无区间 ≠ 无数据。前者是「这个指标看趋势不看绝对值」，
        由服务层写 level_label 解释（见 ratio_service._growth_level）。
    """
    spec = RATIO_BANDS.get(key) or {}
    bands = spec.get('bands')
    if value is None or not bands:
        return {'level': None, 'level_label': None}
    for _lo, hi, level, label in bands:
        if hi is None or value < hi:
            return {'level': level, 'level_label': label}
    return {'level': None, 'level_label': None}
