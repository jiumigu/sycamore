"""书籍状态重构（v3.64.79）—— 7 条

这一组只钉一件事：**迁移表必须覆盖旧枚举的每一个值**。

🔴 为什么值得单独一组：`status` 是 `CharField`，改 `choices` **不会**在数据库层
   拒绝旧字符串。漏掉一个旧值，它就会原样留在库里 —— 不报错、不告警，
   只是那一本在新界面上的状态是空白、在筛选里查不到、在统计里算不进任何一类。
   这种漏法唯一能发现的地方就是这里：拿「旧枚举全集」和「映射表」做集合相等。

`FORWARD` 是迁移文件里的那张表，这里是**唯一**允许按字面列旧值的地方
（其余代码一律用 `Book.STATUS_*`）。
"""
import importlib

import pytest

from apps.book.models import Book

pytestmark = pytest.mark.django_db

migration = importlib.import_module('apps.book.migrations.0006_book_status_v2')

# 重构前的 8 个值（v3.64.78 时的 STATUS_CHOICES）。这份清单只在这里出现一次。
LEGACY = {
    '计划阅读', '在读', '精读', '通读', '消遣', '弃读', '已完成', '待重读',
}

NEW = {key for key, _label in Book.STATUS_CHOICES}


class _FakeApps:
    """迁移函数只用 `apps.get_model` —— 给它真模型即可，不必真跑 schema。"""

    @staticmethod
    def get_model(app_label, model_name):
        assert (app_label, model_name) == ('book', 'Book')
        return Book


def test_forward_covers_every_legacy_value():
    """旧 8 个值一个都不能漏。漏一个 = 那一本静默变成「没有状态」。"""
    assert set(migration.FORWARD) == LEGACY


def test_forward_only_outputs_valid_statuses():
    """映射的输出必须都落在新枚举里 —— 否则写进去的是库里不存在的值。"""
    assert set(migration.FORWARD.values()) <= NEW


def test_backward_covers_every_new_value():
    """反向也要全覆盖：少一个，回滚时那一批就留在英文 key 上。"""
    assert set(migration.BACKWARD) == NEW
    assert set(migration.BACKWARD.values()) <= LEGACY


def test_forward_really_maps_rows():
    """真写 8 行旧值，跑一遍迁移函数，逐条核对映射结果。"""
    for legacy in sorted(LEGACY):
        Book.objects.create(btitle=f'旧值-{legacy}', status=legacy)

    migration.forwards(_FakeApps, None)

    got = set(Book.objects.values_list('status', flat=True))
    assert got == set(migration.FORWARD.values())
    assert got <= NEW
    # 逐条：同一旧值的书全部落到它该去的地方
    for legacy, new in migration.FORWARD.items():
        assert Book.objects.filter(btitle=f'旧值-{legacy}').first().status == new


def test_backward_is_total_but_lossy():
    """反向把所有新值都带回旧值（完整），但分不清原来是不是通读（有损）。

    这条不是「应该无损」，而是把「有损」钉成事实：回滚一次再前进一次，
    那些书不会回到原来那个词，只会回到「最大公约数」。
    """
    for status in sorted(NEW):
        Book.objects.create(btitle=f'新值-{status}', status=status)

    migration.backwards(_FakeApps, None)

    assert set(Book.objects.values_list('status', flat=True)) <= LEGACY
    for status, legacy in migration.BACKWARD.items():
        assert Book.objects.filter(btitle=f'新值-{status}').first().status == legacy


def test_status_choices_are_six_and_labelled_in_chinese():
    """6 个值、key 全英文、label 全中文 —— 下拉里不该再出现读法词。"""
    assert len(Book.STATUS_CHOICES) == 6
    for key, label in Book.STATUS_CHOICES:
        assert key.isascii() and key.islower()
        assert not label.isascii(), f'{label} 应该是中文'
    assert not ({'精读', '通读', '消遣', '计划阅读', '待重读'} & set(NEW))


def test_is_finished_and_is_abandoned_follow_new_values():
    finished = Book(btitle='x', status=Book.STATUS_FINISHED)
    abandoned = Book(btitle='y', status=Book.STATUS_ABANDONED)
    reading = Book(btitle='z', status=Book.STATUS_READING)

    assert finished.is_finished and not finished.is_abandoned
    assert abandoned.is_abandoned and not abandoned.is_finished
    assert not reading.is_finished and not reading.is_abandoned
