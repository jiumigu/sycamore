"""L1 归因值改名：投向 → 成长、外部 → 谋生（维持 / 流失 不变）

与 temporal 0008 同源：沉淀在 `redemption_attr_rule.attribution` 的覆盖规则也要跟着换名，
否则归因规则会匹配不到新枚举（`resolve_attribution` 的优先级里它最高，失效后整条链路降级）。
"""
from django.db import migrations

RENAME = {'投向': '成长', '外部': '谋生'}
REVERT = {new: old for old, new in RENAME.items()}


def _swap(apps, mapping):
    AttrRule = apps.get_model('redemption', 'RedemptionAttrRule')
    for old, new in mapping.items():
        AttrRule.objects.filter(attribution=old).update(attribution=new)


def forwards(apps, schema_editor):
    _swap(apps, RENAME)


def backwards(apps, schema_editor):
    _swap(apps, REVERT)


class Migration(migrations.Migration):

    dependencies = [
        ('redemption', '0003_alter_redemptionattrrule_attribution_and_more'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
