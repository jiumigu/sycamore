"""作品 · 服务层（全部业务口径都在这里，view 层不得重算）

三条口径：

1. **打勾幂等** —— 同一来源重复打勾只留一条（`(source_type, source_id)` 复合键）。
2. **合成可逆** —— 删掉一件作品，它的来源**回到待提炼**，一条都不丢。
3. **`0` 与「取不到」分开** —— 计数一律给「几件」，没有「算不出来」这一说
   （件数是直接 `COUNT`，不是推演出来的）。
"""
from django.db import transaction
from rest_framework import serializers as drf_serializers

from apps.core.models import SystemPreset

from .constants import (
    CAPTURE_SOURCE_CHOICES,
    WORK_KIND_CHOICES,
    WORK_STATUS_CHOICES,
    WORK_CHANNEL_PRESET_TYPE,
    DEFAULT_WORK_CHANNELS,
)
from .models import Work, WorkCapture

SOURCE_KEYS = {c[0] for c in CAPTURE_SOURCE_CHOICES}
KIND_KEYS = {c[0] for c in WORK_KIND_CHOICES}
STATUS_KEYS = {c[0] for c in WORK_STATUS_CHOICES}


# ══════════════════════════════════════════════════════════════
# ① 打勾 / 取消勾
# ══════════════════════════════════════════════════════════════

def capture(source_type, source_id, title, excerpt=''):
    """打一个勾（**幂等**）。

    - 同一来源第一次打勾 ⇒ 新建一条 `pending`；
    - 已存在且还是 `pending` ⇒ 原样返回（不覆盖 `title` ——
      「当时勾的是哪一条」是快照，不该被后来的重打改写）；
    - 已存在但被标过 `dropped` ⇒ **改回 `pending`**（用户改主意了）。
      ⚠️ 这里不能新建 —— 唯一约束会拦，而且会留下两条同源记录。
    - 已存在且 `used`（已收进作品）⇒ 原样返回。**不新建第二件**：
      「一件事只能进一件作品」，要复用请在那件作品里手动记一笔。
    """
    if source_type not in SOURCE_KEYS:
        raise drf_serializers.ValidationError(
            {'source_type': f'未知来源 {source_type!r}（允许：{sorted(SOURCE_KEYS)}）'},
        )
    if not title:
        raise drf_serializers.ValidationError({'title': '缺少来源标题'})

    obj, created = WorkCapture.objects.get_or_create(
        source_type=source_type,
        source_id=int(source_id),
        defaults={'title': title[:200], 'excerpt': (excerpt or '')[:300]},
    )
    if not created and obj.status == 'dropped':
        obj.status = 'pending'
        obj.save(update_fields=['status'])
    return obj, created


def uncapture(capture_id):
    """取消勾 —— **真删**。

    ⚠️ 这里不适用「撤销 ≠ 删除」：那条铁律是给**流水**的
       （库存、登记），删了就对不上账。捕获只是**一个标记**，
       删掉它不影响任何别的数 —— 它不是流水。
    ⚠️ 但**已收进作品**的不许在这里删：那会让作品凭空少一个来源。
       要拆请用「拆开」或直接删那件作品（服务层会把来源放回待提炼）。
    """
    obj = WorkCapture.objects.filter(id=capture_id).first()
    if obj is None:
        return None
    if obj.work_id is not None:
        raise drf_serializers.ValidationError(
            {'detail': '这条已经收进作品了 —— 要拆开请删那件作品，来源会自动回到待提炼。'},
        )
    obj.delete()
    return obj


# ══════════════════════════════════════════════════════════════
# ② 合成 / 拆开
# ══════════════════════════════════════════════════════════════

@transaction.atomic
def compose(capture_ids, name, summary='', kind='other', status='private',
            channel='', note=''):
    """把若干条捕获**合成一件作品**（这就是「编译」在界面上的形态）。

    一次合成至少选一条来源 —— 但**允许**一条都不选吗？不允许：
    那样它就从「把散的东西收成一件」退化成「又一个新建入口」，
    于是同一件事会有两个录入口（项目铁律：同一事实只能有一个录入口）。
    ⇒ 想随手记一件，请明确地在作品页新建（那里**不**消耗捕获）。
    """
    ids = [int(i) for i in (capture_ids or [])]
    if not ids:
        raise drf_serializers.ValidationError(
            {'capture_ids': '至少要选一条待提炼的东西 —— 什么都不选的话，'
                            '请直接在作品页新建一件。'},
        )
    if not name or not name.strip():
        raise drf_serializers.ValidationError({'name': '给它起个名字'})
    if kind not in KIND_KEYS:
        raise drf_serializers.ValidationError({'kind': f'未知类型 {kind!r}'})
    if status not in STATUS_KEYS:
        raise drf_serializers.ValidationError({'status': f'未知出口状态 {status!r}'})

    caps = list(WorkCapture.objects.filter(id__in=ids))
    if len(caps) != len(set(ids)):
        found = {c.id for c in caps}
        raise drf_serializers.ValidationError(
            {'capture_ids': f'有 {len(set(ids) - found)} 条已经不在了，请刷新后重试。'},
        )
    taken = [c for c in caps if c.work_id is not None]
    if taken:
        raise drf_serializers.ValidationError(
            {'capture_ids': f'有 {len(taken)} 条已经收进别的作品了，请刷新后重试。'},
        )

    work = Work.objects.create(
        name=name.strip(), summary=(summary or '')[:200], kind=kind,
        status=status, channel=(channel or '')[:40], note=(note or '')[:200],
    )
    WorkCapture.objects.filter(id__in=[c.id for c in caps]).update(
        work=work, status='used',
    )
    return work


@transaction.atomic
def delete_work(work):
    """删掉一件作品 —— 它的来源**回到待提炼**（合成可逆，一条都不丢）。

    ⚠️ 与「撤销 ≠ 删除」无关：作品是**配置/清单**，不是流水。
       删一件作品不会让任何往期数字对不上（期数是现算的）。
    """
    n = WorkCapture.objects.filter(work=work).update(work=None, status='pending')
    work.delete()
    return n


# ══════════════════════════════════════════════════════════════
# ③ 计数
# ══════════════════════════════════════════════════════════════

def overview():
    """顶部计数。**列不出数就报 `None`** —— 本模块全是直接 COUNT，没有推演值。"""
    return {
        'total': Work.objects.count(),
        'published': Work.objects.filter(status='published').count(),
        'ready': Work.objects.filter(status='ready').count(),
        'pending_captures': WorkCapture.objects.filter(status='pending').count(),
        'total_captures': WorkCapture.objects.count(),
    }


# ══════════════════════════════════════════════════════════════
# ④ 出口去向清单（用户自己维护，存在 core 的 SystemPreset）
# ══════════════════════════════════════════════════════════════

def list_channels():
    """读出口去向清单。

    ⚠️ **不做 `get_or_create`**（项目铁律：只读接口别写库）。
       还没有那行 ⇒ 下发默认清单，但**不落库**；
       用户第一次改动时才写。
    """
    row = SystemPreset.objects.filter(preset_type=WORK_CHANNEL_PRESET_TYPE).first()
    if row and isinstance(row.values, list) and row.values:
        return [str(v) for v in row.values]
    return list(DEFAULT_WORK_CHANNELS)


def save_channels(values):
    """覆盖式保存出口去向清单（与「系统预设」页的行为一致）。"""
    cleaned = []
    for v in values or []:
        s = str(v).strip()
        if s and s not in cleaned:
            cleaned.append(s[:40])
    if not cleaned:
        raise drf_serializers.ValidationError({'values': '至少留一个去向。'})
    row, _ = SystemPreset.objects.get_or_create(
        preset_type=WORK_CHANNEL_PRESET_TYPE, defaults={'values': cleaned},
    )
    row.values = cleaned
    row.save(update_fields=['values', 'updated_at'])
    return cleaned
