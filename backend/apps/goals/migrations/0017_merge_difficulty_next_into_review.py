"""里程碑：「遇到的困难」「下一步行动」并入自我批阅

`difficulty_met`（4/446）与 `next_action`（2/446）跟 `self_review`（41/446）
问的是同一件事 —— 这次做得怎么样、下次怎么改。三个 TextField 并排出现在
完成弹窗里，人能填一个就不会填三个，真实填充率已经把答案写出来了。

🔴 先并再删，不是直接 `RemoveField` 一把过：这 6 条是本人写下的判断，
不是垃圾数据。并入格式 `原批阅\\n\\n困难：…\\n下一步：…`，只在该字段有值时追加。

⚠️ 反向不可逆：合并后的文本拆不回两列。`RemoveField` 的 reverse 只把列
重新建出来（空值），`reverse_merge` 只做说明、不还原数据。
"""

from django.db import migrations


def merged_review(base, difficulty, action):
    """把两列并进批阅 —— 纯函数，测试直接调它（见 `test_review_merge.py`）。

    返回 `None` 表示「这两列都没内容」，调用方跳过该行（不写库）。
    🔴 空串与非空串只在一处判断：`strip()` 后为空就当没有，
       否则会往批阅里塞一个「困难：」光秃秃的标签。
    """
    difficulty = (difficulty or '').strip()
    action = (action or '').strip()
    lines = []
    if difficulty:
        lines.append(f'困难：{difficulty}')
    if action:
        lines.append(f'下一步：{action}')
    if not lines:
        return None

    base = (base or '').strip()
    block = '\n'.join(lines)
    return f'{base}\n\n{block}' if base else block


def merge_into_review(apps, schema_editor):
    Milestone = apps.get_model('goals', 'Milestone')

    for m in Milestone.objects.all().iterator():
        merged = merged_review(m.self_review, m.difficulty_met, m.next_action)
        if merged is None:
            continue
        m.self_review = merged
        m.save(update_fields=['self_review'])


def reverse_merge(apps, schema_editor):
    """不还原 —— 并进去的句子已经和原批阅连成一段，拆开只能靠猜。

    留着空实现是为了让 `migrate goals 0016` 不至于半途炸在数据上：
    列会被 reverse 重建出来（全空），批阅保持合并后的样子。
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('goals', '0016_db_comments'),
    ]

    operations = [
        migrations.RunPython(merge_into_review, reverse_merge),
        migrations.RemoveField(
            model_name='milestone',
            name='difficulty_met',
        ),
        migrations.RemoveField(
            model_name='milestone',
            name='next_action',
        ),
    ]
