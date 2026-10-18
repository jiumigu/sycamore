"""数据库注释的回归测试。

## 为什么这里只查模型层、不查 information_schema

测试库是按 `--no-migrations` + `--reuse-db` 建的（见 `pytest.ini`）：

    · 表结构来自 **models**，不是迁移 ⇒ 迁移里的 `RunSQL` 在测试下**从不执行**；
    · 复用的旧库也不会重放建表 ⇒ 库里的注释在测试环境下**不可复现**。

硬去断言库里的 `COLUMN_COMMENT`，只会得到一个「看着在测、其实测不到」的
假绿，或者一个随执行顺序时红时绿的脆弱用例。**库级验证由
「跑 `migrate wealth` + 只读复查 information_schema」承担**，不在这里假装。

这里守的是**源头**：模型上漏写、或 verbose_name 退回英文（`inspectdb` 遗留的
`'created at'` 那类），测试立刻变红 —— 这才是「以后新建表不会再忘」的保证。

真源与完整判据见 `apps/core/db_comments.py` 的模块 docstring。
"""

import re

import pytest

from apps.core.db_comments import (
    COLUMN_COMMENT_OVERRIDES,
    DOCUMENTED_APPS,
    RUNSQL_ONLY_TABLES,
    documented_models,
    normalize_comment,
)

CJK = re.compile(r'[\u4e00-\u9fff]')


def _models():
    """materialize 一次，避免生成器被多轮消费。"""
    return list(documented_models())


def test_documented_apps_is_not_empty():
    """白名单不该是空的 —— 空了整套机制等于静默失效。"""
    assert DOCUMENTED_APPS, 'DOCUMENTED_APPS 为空 ⇒ 派生根本不会跑'


def test_every_documented_model_has_a_chinese_table_comment():
    """每张接管的表都要有表注释，且是中文。

    表注释**不会派生**（`Meta.db_table_comment` 只能显式写），
    所以这条是真正能拦住「新加了表、忘了写说明」的那一道。
    """
    missing = []
    for model in _models():
        comment = str(getattr(model._meta, 'db_table_comment', '') or '').strip()
        if not comment:
            missing.append(f'{model._meta.db_table} 缺表注释')
        elif not CJK.search(comment):
            missing.append(f'{model._meta.db_table} 表注释无中文: {comment!r}')
    assert not missing, '以下表缺中文表注释：\n  ' + '\n  '.join(missing)


def test_every_documented_column_has_a_chinese_comment():
    """每个字段都要有列注释，且是中文。

    列注释大多由 `verbose_name` 派生 ⇒ 这条同时在看两件事：
      ① 派生机制还活着（`ready()` 里那一句没被删掉）；
      ② 没有哪个 `verbose_name` 退回成英文兜底 ——
         `inspectdb` 生成的 `'created at'` / `'user id'` 会在这里现形。
    """
    bad = []
    for model in _models():
        table = model._meta.db_table
        for field in model._meta.concrete_fields:
            comment = str(field.db_comment or '').strip()
            if not comment:
                bad.append(f'{table}.{field.column} 缺列注释（verbose_name={field.verbose_name!r}）')
            elif not CJK.search(comment):
                bad.append(
                    f'{table}.{field.column} 列注释无中文: {comment!r} '
                    f'（verbose_name={field.verbose_name!r}）'
                )
    assert not bad, '以下字段的注释不合格：\n  ' + '\n  '.join(bad)


def test_primary_keys_are_not_commented_as_bare_id():
    """`id` 不能只说 `ID` —— AutoField 的 verbose_name 默认就是它。"""
    bad = [
        f'{m._meta.db_table}.{f.column}'
        for m in _models()
        for f in m._meta.concrete_fields
        if f.primary_key and str(f.db_comment or '').strip().lower() == 'id'
    ]
    assert not bad, f'主键注释退化成了裸 ID：{bad}'


def test_override_keys_all_hit_real_columns():
    """覆盖表里的 key 必须都能命中真实字段。

    🔴 这条是集中式声明**唯一**的风险点：key 拼错、或字段改名之后，
    那一条覆盖会**静默失效**（不报错、只是不再生效），
    而列注释会悄悄退回 verbose_name。所以必须逐条回查。
    """
    valid = {
        f'{model._meta.db_table}.{field.column}'
        for model in _models()
        for field in model._meta.concrete_fields
    }
    dead = sorted(key for key in COLUMN_COMMENT_OVERRIDES if key not in valid)
    assert not dead, (
        '以下覆盖条目的 key 命中不到任何字段（拼错？字段已改名？）：\n  '
        + '\n  '.join(dead)
    )


def test_override_values_are_not_plain_verbose_name_copies():
    """覆盖条目要说的是 verbose_name **说不了**的事。

    判据：覆盖文案不得与 verbose_name 逐字相同 —— 那属于派生该干的活，
    写进覆盖表就是同一事实的第二份副本（改了 verbose_name 这边不会跟）。
    """
    copies = []
    for model in _models():
        table = model._meta.db_table
        for field in model._meta.concrete_fields:
            key = f'{table}.{field.column}'
            if COLUMN_COMMENT_OVERRIDES.get(key) == str(field.verbose_name):
                copies.append(key)
    assert not copies, f'以下覆盖条目只是把 verbose_name 抄了一遍：{copies}'


def test_auto_created_through_tables_are_registered():
    """接管范围内的 M2M 自动中间表必须登记，否则它在库里永远没有表注释。

    autodetector 完全忽略 `auto_created` 的表（2026-10-16 实测）⇒
    这类表的注释只能靠迁移里的 `RunSQL`。没登记 = 漏一张表，
    而**不会有任何报错**提示这件事。
    """
    from django.apps import apps

    actual = {
        model._meta.db_table
        for model in apps.get_models(include_auto_created=True)
        if model._meta.auto_created
        and model._meta.app_label in DOCUMENTED_APPS
    }
    unregistered = sorted(actual - set(RUNSQL_ONLY_TABLES))
    assert not unregistered, (
        '以下 M2M 自动中间表没在 RUNSQL_ONLY_TABLES 登记，'
        f'库里不会有表注释：{unregistered}'
    )

    stale = sorted(set(RUNSQL_ONLY_TABLES) - actual)
    assert not stale, f'RUNSQL_ONLY_TABLES 里有过期条目：{stale}'


def test_no_halfwidth_percent_in_column_comments():
    """列注释里不得出现半角 `%` —— 它会让下一条迁移在 `migrate` 时崩掉。

    详见 `db_comments.normalize_comment`：Django 把注释内联进
    `ALTER TABLE ... MODIFY COLUMN` 之后还要走一次 `sql % params`，
    注释里的 `%` 会被当成格式化占位符，抛
    `ProgrammingError: not enough arguments for format string`。
    机制层已把 `%` 归一成全角 `％`，这条守着那个不变量不被绕过。
    """
    bad = [
        f'{m._meta.db_table}.{f.column}: {f.db_comment!r}'
        for m in _models()
        for f in m._meta.concrete_fields
        if '%' in str(f.db_comment or '')
    ]
    assert not bad, '以下列注释含半角 %（迁移会在 migrate 时崩）：\n  ' + '\n  '.join(bad)


def test_no_halfwidth_percent_in_table_comments():
    """表注释同理 —— `sql_alter_table_comment` 走的是同一条 `sql % params`。

    ⚠️ 表注释的归一化落在 `apply_table_comments()`（2026-10-16 批 2 补），
    且必须**同时改 `_meta.original_attrs`** —— autodetector 读的是后者，
    只改 `_meta` 是静默无效的（实测见 `db_comments.apply_table_comments`）。

    这条断言守的是「**生成迁移时**用的那个值」不含 `%` ——
    正是真正决定迁移会不会崩的那一个。源码字面量与它可能有 1 个字符的
    差异（半角 `%` vs 全角 `％`），这是有意接受的代价：迁移安全优先，
    且机制已在运行时统一，不会反复生成新迁移。
    """
    bad = [
        f'{m._meta.db_table}: {m._meta.db_table_comment!r}'
        for m in _models()
        if '%' in str(getattr(m._meta, 'db_table_comment', '') or '')
    ]
    assert not bad, '以下表注释含半角 %：\n  ' + '\n  '.join(bad)


def test_normalize_comment_is_the_landmine_defuser():
    """归一化本身的行为要锁住，别被人「顺手简化」掉。"""
    assert normalize_comment('年利率(%)') == '年利率(％)'
    assert normalize_comment('无百分号') == '无百分号'
    assert normalize_comment('') == ''
    assert normalize_comment(None) == ''


@pytest.mark.parametrize('key', sorted(RUNSQL_ONLY_TABLES))
def test_runsql_registry_carries_a_reason(key):
    """登记项要写清「为什么它只能走 RunSQL」，不能只留个表名。"""
    assert len(str(RUNSQL_ONLY_TABLES[key]).strip()) >= 6, f'{key} 的登记理由太短'
