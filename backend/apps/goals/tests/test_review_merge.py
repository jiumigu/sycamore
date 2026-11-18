"""0017 迁移的合并逻辑 —— 只钉「写进批阅的那段文字」，不碰库。

为什么不迁移真库来测：`MigrationExecutor` 前后倒腾会把整轮 `--reuse-db`
的 schema 拖到中间态，一旦断言失败，后面两千多条用例会以「缺列」的
面目连环报错 —— 用一次数据形态的错误换一场连环误报，不划算。
所以把文本合成抽成纯函数 `merged_review()`，这里直接调它。

⚠️ 导入方式：迁移文件名以数字开头，不是合法标识符，只能走 `importlib`。
"""

import importlib

import pytest

migration = importlib.import_module(
    'apps.goals.migrations.0017_merge_difficulty_next_into_review'
)
merged_review = migration.merged_review


def test_both_empty_returns_none():
    """两列都空 ⇒ 不写库。

    `None` 与 `''` 必须分开：返回 `''` 会让 `save()` 把原本有内容的批阅
    抹成空串（调用方无从判断「没内容」和「清空」）。
    """
    assert merged_review('做得不错', '', '') is None
    assert merged_review('', None, None) is None
    assert merged_review('', '  \n ', '   ') is None


def test_difficulty_only():
    assert merged_review('', '记不住知识点', '') == '困难：记不住知识点'


def test_action_only():
    assert merged_review('', '', '补缺补漏') == '下一步：补缺补漏'


def test_both_without_base():
    assert merged_review('', '空调耗电量比较高', '采购保温箱') == (
        '困难：空调耗电量比较高\n下一步：采购保温箱'
    )


def test_base_kept_and_separated_by_blank_line():
    """原批阅在前、空行分隔 —— 不覆盖，只追加。"""
    assert merged_review('完成了！下一个目标是安装热水器？', '装修磕磕绊绊', '') == (
        '完成了！下一个目标是安装热水器？\n\n困难：装修磕磕绊绊'
    )


def test_full_merge_order():
    assert merged_review('还行', '难在开头', '先做十分钟') == (
        '还行\n\n困难：难在开头\n下一步：先做十分钟'
    )


@pytest.mark.parametrize('blank', ['', '   ', '\n', '\t\n '])
def test_blank_base_does_not_leave_leading_blank(blank):
    """空批阅不能被拼成「\\n\\n困难：…」—— 那会在复盘卡里顶出一个空行。"""
    assert merged_review(blank, '难', '') == '困难：难'


def test_serializer_no_longer_exposes_the_retired_fields():
    """接口出参不再有这两列 —— 否则前端删了字段、接口还在发，等于假删除。

    这一条只钉「说了退役就真退役」。模型列由 0017 的 `RemoveField` 删，
    这里不碰库，所以删掉模型字段后它才会红 —— 正是想要的顺序。
    """
    from apps.goals.serializers import MilestoneSerializer

    fields = MilestoneSerializer().fields
    assert 'self_review' in fields
    assert 'difficulty_met' not in fields
    assert 'next_action' not in fields
