"""导入预演（`CSVImportService.preview_from_csv`）的回归守卫（v3.64.32）。

为什么这一层需要单独的测试
--------------------------
预演的产物是**行号**：用户在界面上勾掉「第 7 行」，落库时按行号跳过。
所以这里的错法都很安静 ——

1. **预演自己写库**（顺手建了 TaskMeta / 刷了周缓存）⇒「只是看一眼」变成一次写入，
   而且界面上完全看不出来；
2. **两份解析差一行** ⇒ 跳错记录，该留的被吞、该跳的留下，两边都不报错；
3. **分类顺序颠倒** ⇒ 把「上班时段里记代码」这种合法细分判成疑似重复。
   本库实测 262 对重叠里 214 对是这种包含关系（82%）—— 顺序错了就是大面积误判；
4. **summary 加不起来** ⇒ 屏幕上「将导入 96 条」，实际落 91 条，没人能对账。

口径推导见 `.workbuddy/memory/TECH-NOTES.md` §157。
"""

from datetime import datetime, timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.temporal.models import TaskMeta, TemporalTask, WeeklyTimeCache
from apps.temporal.services import (
    CONFLICT_CONTAINED,
    CONFLICT_EDGE,
    CONFLICT_LIKELY_DUP,
    CONFLICT_REVIEW,
    CSVImportService,
    classify_overlap,
)

HEAD = '任务名称,任务说明,开始时间,结束时间,持续时间（小时）,附注,标签'


def _csv(*rows) -> SimpleUploadedFile:
    body = HEAD + '\n' + '\n'.join(','.join(str(c) for c in r) for r in rows) + '\n'
    return SimpleUploadedFile('atracker.csv', body.encode('utf-8'), content_type='text/csv')


def _aware(text: str) -> datetime:
    return timezone.make_aware(datetime.strptime(text, '%Y-%m-%d %H:%M:%S'))


def _mk(task_name, start, end, duration, batch='import_orig001'):
    s = _aware(start)
    return TemporalTask.objects.create(
        task_name=task_name, task_description='', start_time=s, end_time=_aware(end),
        duration_hours=duration, notes='', tags=None, task_type=task_name,
        import_batch=batch, year=s.year, mon=f'{s.month:02d}', day=s.day,
        week=s.isocalendar()[1], quarter=(s.month - 1) // 3 + 1,
    )


def _span(a: str, b: str) -> tuple:
    return (datetime.strptime(a, '%H:%M'), datetime.strptime(b, '%H:%M'))


# ── 四类判定（纯函数，不需要数据库）────────────────────────────────────

class TestClassifyOverlap:
    """四类的不变量。每条都对着一份真实数据的形态。"""

    def test_subdivide_inside_long_block_is_contained(self):
        """`牛马工作 09:00-18:00` 里记 `代码编程 10:00-11:00` —— 本库最常见的合法形态。

        🔴 这条是顺序护栏：`_overlap_ratio` 的分母是「较短一方」，
           所以包含关系的比值恒为 1.0。先看比值 ⇒ 这里会返回 likely_dup，
           而它是 214 对（82%）中的一员。
        """
        assert classify_overlap(_span('09:00', '18:00'), _span('10:00', '11:00')) \
            == CONFLICT_CONTAINED

    def test_similar_length_almost_same_block_is_likely_dup(self):
        """09:00-17:00 与 09:00-17:30：包含关系，但长度比 0.94 ⇒ 同一件事记了两遍。"""
        assert classify_overlap(_span('09:00', '17:30'), _span('09:00', '17:00')) \
            == CONFLICT_LIKELY_DUP

    def test_crossing_with_high_ratio_is_likely_dup(self):
        """`整理房间 08:28-08:44` vs `美食备餐 08:29-09:19`（真实数据，比值 0.94）。"""
        assert classify_overlap(_span('08:28', '08:44'), _span('08:29', '09:19')) \
            == CONFLICT_LIKELY_DUP

    def test_edge_hit_at_shift_boundary(self):
        """`运动健身 08:28-09:09` vs `牛马工作 09:00-18:00`：只咬 9 分钟，跨整点摩擦。"""
        assert classify_overlap(_span('08:28', '09:09'), _span('09:00', '18:00')) \
            == CONFLICT_EDGE

    def test_middle_ground_needs_human(self):
        """7/10 分钟 = 0.7：既不算摩擦也不算重复 ⇒ 摊开给人看。"""
        assert classify_overlap(_span('19:01', '20:12'), _span('20:05', '20:15')) \
            == CONFLICT_REVIEW

    def test_zero_width_is_never_folded_away(self):
        """只记了开始时刻的记录不参与折叠 —— 猜成 edge 会把它从清单里藏掉。"""
        zero = (datetime(2026, 1, 1, 10), datetime(2026, 1, 1, 10))
        assert classify_overlap(zero, _span('09:00', '18:00')) == CONFLICT_REVIEW

    def test_disjoint_never_reaches_classifier_but_is_safe(self):
        """调用方已按交集过滤；万一传进来也不能崩（不返回 None）。"""
        assert classify_overlap(_span('09:00', '10:00'), _span('11:00', '12:00')) \
            == CONFLICT_REVIEW


# ── 预演：只读 ────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestPreviewIsReadOnly:
    def test_preview_writes_nothing(self, db):
        """「只是看一眼」不能建 TaskMeta、不能刷周缓存。"""
        _mk('牛马工作', '2026-03-02 09:00:00', '2026-03-02 18:00:00', 9.0)
        before = (TemporalTask.objects.count(), TaskMeta.objects.count(),
                  WeeklyTimeCache.objects.count())

        out = CSVImportService().preview_from_csv(_csv(
            ['晨跑', '', '2026-03-02 06:00:00', '2026-03-02 06:40:00', '0.67', '', ''],
            ['一个库里没有的新任务', '', '2026-03-12 10:00:00',
             '2026-03-12 11:00:00', '1', '', ''],
        ))

        assert 'error' not in out
        after = (TemporalTask.objects.count(), TaskMeta.objects.count(),
                 WeeklyTimeCache.objects.count())
        assert after == before, '预演写了库 —— 这一层必须是纯读的'
        # 新任务名不该被顺手建档（落库时才建）
        assert not TaskMeta.objects.filter(task_name='一个库里没有的新任务').exists()


# ── 预演：行号 ────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestRowNumbers:
    def test_row_no_is_physical_line_and_survives_bad_rows(self):
        """坏行占掉一个行号 ⇒ 它后面的行号不能整体前移。"""
        out = CSVImportService().preview_from_csv(_csv(
            ['甲', '', '2026-03-02 09:00:00', '2026-03-02 10:00:00', '1', '', ''],   # 第 2 行
            ['乙', '', 'bad-date', '', '1', '', ''],                                  # 第 3 行（坏）
            ['丙', '', '2026-03-02 11:00:00', '2026-03-02 12:00:00', '1', '', ''],   # 第 4 行
        ))
        rows, _, err = CSVImportService()._read_rows(_csv(
            ['甲', '', '2026-03-02 09:00:00', '2026-03-02 10:00:00', '1', '', ''],
            ['乙', '', 'bad-date', '', '1', '', ''],
            ['丙', '', '2026-03-02 11:00:00', '2026-03-02 12:00:00', '1', '', ''],
        ))
        assert err == ''
        assert [r['row_no'] for r in rows] == [2, 4], '坏行必须占号，否则会跳错记录'
        assert out['parse_errors']['bad_date'] == 1

    def test_two_parses_of_same_file_agree(self):
        """预演与落库各解析一次 —— 行号必须完全一致（这是 skip_rows 的契约）。"""
        def payload():
            return _csv(
                ['甲', '', '2026-03-02 09:00:00', '2026-03-02 10:00:00', '1', '', ''],
                ['', '', '2026-03-02 10:00:00', '2026-03-02 11:00:00', '1', '', ''],   # 无名字
                ['丙', '', '2026-03-02 11:00:00', '2026-03-02 12:00:00', '1', '', ''],
            )
        first, _, _ = CSVImportService()._read_rows(payload())
        second, _, _ = CSVImportService()._read_rows(payload())
        assert [r['row_no'] for r in first] == [r['row_no'] for r in second] == [2, 4]


# ── 预演：汇总是能加总的 ──────────────────────────────────────────────

@pytest.mark.django_db
class TestSummaryAddsUp:
    def test_total_equals_sum_of_buckets(self, db):
        _mk('牛马工作', '2026-03-02 09:00:00', '2026-03-02 18:00:00', 9.0)
        out = CSVImportService().preview_from_csv(_csv(
            # 与库里同一条（同名 + 时段几乎一致）⇒ already_exists
            ['牛马工作', '', '2026-03-02 09:00:00', '2026-03-02 18:00:00', '9', '', ''],
            # 落在上班时段里 ⇒ contained（必须与牛马工作同一天，否则根本不相交）
            ['代码编程', '', '2026-03-02 10:00:00', '2026-03-02 11:00:00', '1', '', ''],
            # 与牛马工作只咬 9 分钟（这一天没有别的记录）⇒ edge
            ['晨跑', '', '2026-03-02 08:28:00', '2026-03-02 09:09:00', '0.68', '', ''],
            # 整周都没人碰的时段 ⇒ clean
            ['读书', '', '2026-03-09 20:00:00', '2026-03-09 21:00:00', '1', '', ''],
            # 同一行再来一次 ⇒ inner_duplicate
            ['读书', '', '2026-03-09 20:00:00', '2026-03-09 21:00:00', '1', '', ''],
        ))
        s = out['summary']
        counted = (out['inner_duplicate'] + s['already_exists'] + s['clean']
                   + s['contained'] + s['edge'] + s['review'] + s['likely_dup'])
        assert counted == s['total'] == out['total_parsed'] == 5
        assert s['already_exists'] == 1
        assert out['inner_duplicate'] == 1, 'CSV 内部重复只计数，不占 summary 的桶'
        assert s['contained'] >= 1
        assert s['needs_review'] == s['review'] + s['likely_dup']

    def test_rows_only_contains_what_needs_eyes(self, db):
        """干净行不进 `rows` —— 96 行干净不该占满屏幕。"""
        out = CSVImportService().preview_from_csv(_csv(
            ['读书', '', '2026-03-09 20:00:00', '2026-03-09 21:00:00', '1', '', ''],
        ))
        assert out['summary']['clean'] == 1
        assert out['rows'] == []

    def test_contained_and_edge_are_counted_but_not_listed(self, db):
        """合法的包含/摩擦只计数、不进清单。

        🔴 这条守的是「文案与清单同源」：前端写着「下面 N 行需要你看」，
           表格里就不能混进 `contained` 行 —— 那会让用户以为
           「上班时段里记代码」也需要他裁决。
        """
        _mk('牛马工作', '2026-03-02 09:00:00', '2026-03-02 18:00:00', 9.0)
        out = CSVImportService().preview_from_csv(_csv(
            ['代码编程', '', '2026-03-02 10:00:00', '2026-03-02 11:00:00', '1', '', ''],
            ['晨跑', '', '2026-03-02 08:28:00', '2026-03-02 09:09:00', '0.68', '', ''],
        ))
        assert out['summary']['contained'] == 1
        assert out['summary']['edge'] == 1
        assert out['summary']['needs_review'] == 0
        assert out['rows'] == [], 'contained/edge 不该出现在需要人看的清单里'


# ── 落库：skip_rows ───────────────────────────────────────────────────

@pytest.mark.django_db
class TestSkipRows:
    def test_skips_only_listed_rows(self, db):
        stats = CSVImportService().import_from_csv(
            _csv(
                ['甲', '', '2026-03-02 09:00:00', '2026-03-02 10:00:00', '1', '', ''],  # 2
                ['乙', '', '2026-03-02 11:00:00', '2026-03-02 12:00:00', '1', '', ''],  # 3
                ['丙', '', '2026-03-02 13:00:00', '2026-03-02 14:00:00', '1', '', ''],  # 4
            ),
            'import_test_skip', skip_rows=[3],
        )
        assert stats['inserted'] == 2
        assert stats['skipped_by_user'] == 1
        assert stats['total_parsed'] == 3, 'total_parsed 是「勾掉之前」的总数'
        names = set(TemporalTask.objects.filter(import_batch='import_test_skip')
                    .values_list('task_name', flat=True))
        assert names == {'甲', '丙'}

    def test_unknown_row_number_refuses_to_write(self, db):
        """行号对不上 ⇒ 400 且一条都不写（不许「跳了别的、报成功」）。"""
        stats = CSVImportService().import_from_csv(
            _csv(['甲', '', '2026-03-02 09:00:00', '2026-03-02 10:00:00', '1', '', '']),
            'import_test_bad', skip_rows=[99],
        )
        assert 'error' in stats and '99' in stats['error']
        assert not TemporalTask.objects.filter(import_batch='import_test_bad').exists()

    def test_zero_based_indices_are_rejected(self, db):
        """传成 0-based（第 1 行 = 数据第 1 条）时必须报错，不能默默跳掉第 1 行。"""
        stats = CSVImportService().import_from_csv(
            _csv(
                ['甲', '', '2026-03-02 09:00:00', '2026-03-02 10:00:00', '1', '', ''],
                ['乙', '', '2026-03-02 11:00:00', '2026-03-02 12:00:00', '1', '', ''],
            ),
            'import_test_zero', skip_rows=[0],
        )
        assert 'error' in stats
        assert not TemporalTask.objects.filter(import_batch='import_test_zero').exists()
