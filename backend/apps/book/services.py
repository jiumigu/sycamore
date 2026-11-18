from datetime import date

from django.db import transaction
from django.db.models import Avg, Count, Q
from django.utils import timezone

from .models import Book, ReadingFocus


class FocusSwitchError(Exception):
    """换书被拒 —— 带一个稳定的 `code`，前端只查表、不解析文案。"""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


class BookService:
    """书籍业务逻辑"""

    @staticmethod
    def get_stats(year=None):
        """获取综合统计数据

        year 非空时按记录年份(years)限定统计范围（卡片计数、类型/状态等分布均基于该年）；
        年度趋势 year_stats 恒用全量，保证跨年柱状图不失真；
        month_count/year_count 恒为「当前自然月/年」真实口径，不随 year 变化。
        """
        base_qs = Book.objects.all()
        queryset = base_qs.filter(years=year) if year else base_qs

        total_count = queryset.count()
        completed_count = queryset.filter(status=Book.STATUS_FINISHED).count()
        # 🔴 「在读」= 在读 + 二刷（`STATUS_ACTIVE`）。二刷也是正在读，
        #    只数 `reading` 会让二刷的书在统计里凭空消失。
        reading_count = queryset.filter(status__in=Book.STATUS_ACTIVE).count()
        abandoned_count = queryset.filter(status=Book.STATUS_ABANDONED).count()
        # 名字仍叫 `planned`，语义已放宽成「待读」—— 前端字段名不动，避免又改一处契约。
        planned_count = queryset.filter(status=Book.STATUS_TO_READ).count()

        now = timezone.now()
        month_count = base_qs.filter(readDate__year=now.year, readDate__month=now.month).count()
        year_count = base_qs.filter(readDate__year=now.year).count()

        avg_recommend = queryset.aggregate(avg=Avg('recommend'))['avg'] or 0

        status_stats = list(
            queryset.values('status')
            .annotate(count=Count('bid'))
            .order_by('-count')
        )

        type_stats = list(
            queryset.values('btype')
            .annotate(count=Count('bid'), avg_recommend=Avg('recommend'))
            .order_by('-count')
        )

        year_stats = list(
            base_qs.values('years')
            .annotate(count=Count('bid'))
            .order_by('-years')
        )

        recommend_stats = list(
            queryset.values('recommend')
            .annotate(count=Count('bid'))
            .order_by('-recommend')
        )

        depth_stats = list(
            queryset.values('reading_depth')
            .annotate(count=Count('bid'))
            .order_by('reading_depth')
        )

        for item in type_stats:
            if item['btype'] is None:
                item['btype'] = '未分类'

        return {
            'total_count': total_count,
            'completed_count': completed_count,
            'reading_count': reading_count,
            'abandoned_count': abandoned_count,
            'planned_count': planned_count,
            'month_count': month_count,
            'year_count': year_count,
            'avg_recommend': round(avg_recommend, 1),
            'status_stats': status_stats,
            'type_stats': type_stats,
            'year_stats': year_stats,
            'recommend_stats': recommend_stats,
            'depth_stats': depth_stats,
        }

    @staticmethod
    def mark_completed(book):
        """标记为已读完"""
        book.status = Book.STATUS_FINISHED
        book.save()

    @staticmethod
    def bulk_update(bids, status=None, reading_depth=None):
        """按编号批量改「阅读状态」/「阅读深度」，返回**实际命中并改动**的行数。

        统一走 `Book.objects.filter(bid__in=...)` 一次 UPDATE —— 逐条 `save()`
        会按选中数发 N 条语句，选 100 本就是一串请求。

        🔴 **`updated_at` 必须手工带上**：`QuerySet.update()` 走的是 SQL UPDATE，
        绕过了 `Model.save()`，而 `auto_now` 那个钩子挂在 `save()` 上 ——
        不手工写就会变成「内容改了、更新日期还是旧的」（静默的假数据）。

        ⚠️ 返回的是**命中数**，可能小于 `len(bids)`（选中的书被别处删掉了）。
        调用方要把「请求了多少本」和「改了几本」分开报，不能把命中数当成请求数。
        """
        fields = {}
        if status is not None:
            fields['status'] = status
        if reading_depth is not None:
            fields['reading_depth'] = reading_depth
        if not fields:
            return 0
        fields['updated_at'] = date.today()
        return Book.objects.filter(bid__in=bids).update(**fields)


class ReadingFocusService:
    """「当前在读哪本」的唯一读写入口。

    🔴 全库只有一行（`pk=1`）。任何写操作都必须经过这里 ——
       直接 `ReadingFocus.objects.create()` 会造出第二行，
       于是「现在读哪本」有两个答案，页面再也不会一致。
    """

    FOCUS_PK = 1

    CLOSE_FINISHED = 'finished'     # 旧书：已完成（记今天为阅读日期）
    CLOSE_ABANDONED = 'abandoned'   # 旧书：弃读（必须写原因）
    CLOSE_LATER = 'later'           # 旧书：放回待读池

    CLOSE_CHOICES = [
        (CLOSE_FINISHED, '读完'),
        (CLOSE_ABANDONED, '弃读'),
        (CLOSE_LATER, '先放回'),
    ]

    # ── 读 ────────────────────────────────────────────────
    @staticmethod
    def get_focus():
        """取指针行（可能不存在）。`select_related` 一次取回书，避免详情页多一次查询。"""
        return ReadingFocus.objects.select_related('book').filter(pk=ReadingFocusService.FOCUS_PK).first()

    @staticmethod
    def current_book():
        """当前在读的书；没有指针、或指针指向的书已被删 ⇒ `None`。

        🔴 这里**不看** `Book.status`：状态是「在读」的书可能有一堆，
           「当前这本」永远只有一本 —— 判断依据是这张表，不是状态字段。
        """
        focus = ReadingFocusService.get_focus()
        return focus.book if focus and focus.book_id else None

    @staticmethod
    def days_on(book, started_on, *, today) -> int | None:
        """当前这本读到第几天（开始当天算第 1 天）。

        算不出来就返回 `None` —— 不返回 0（`0` 会被读成「今天刚开始」）。
        """
        if not book or not started_on:
            return None
        return (today - started_on).days + 1

    # ── 换书的候选（v3.64.81）─────────────────────────────
    CANDIDATE_LIMIT = 20

    @staticmethod
    def candidate_queryset(*, focus=None, keyword: str = ''):
        """「接下来读哪本」的候选集：**只含还能读的书**，不含当前这本。

        🔴 这个口径从前端搬进来的（`bookStore.searchFocusCandidates` 原来直接拿
           整张书单按 `-updated_at` 截 20 条）—— 于是 93 本「已读完」和 4 本
           「弃读」都躺在选择列表里，用户报的就是这个。放在后端是**唯一实现**：
           前端再筛一遍就是第二份口径，改一处漏一处、还不报错。

        🔴 已读完 / 弃读被排除（见 `Book.STATUS_SELECTABLE` 的注释）。
           它们的入口是「编辑 → 阅读状态」，不是换书弹窗。
        """
        qs = Book.objects.filter(status__in=Book.STATUS_SELECTABLE)
        if focus is not None and focus.book_id:
            qs = qs.exclude(pk=focus.book_id)
        keyword = (keyword or '').strip()
        if keyword:
            qs = qs.filter(Q(btitle__icontains=keyword) | Q(author__icontains=keyword))
        # 次级键 `-bid`：`updated_at` 撞秒时不靠数据库默认顺序（那玩意儿没人保证）
        return qs.order_by('-updated_at', '-bid')

    # ── 写（唯一入口）─────────────────────────────────────
    @staticmethod
    def switch(book: Book, *, today, close_mode: str | None = None,
               reason: str = '') -> dict:
        """换书：先给旧书结论，再把指针移到新书。整体一个事务。

        返回 `{'focus': ReadingFocus, 'written': {...}}`，
        `written` 逐表报**实际改动的行数**（本项目写接口的约定：
        不能只说「成功了」，因为「关掉旧书 0 行」和「关掉旧书 1 行」是两件事）。
        """
        written = {'book_read_list': 0, 'book_reading_focus': 1}
        touched = 0          # 本轮**真的**写了几行 `book_read_list`（同状态不重复写、不谎报）

        with transaction.atomic():
            focus = (
                ReadingFocus.objects
                .select_for_update()
                .select_related('book')
                .filter(pk=ReadingFocusService.FOCUS_PK)
                .first()
            )
            old = focus.book if focus and focus.book_id else None

            # ① 切到自己 ⇒ 拒绝。放行的话会先给自己写一个结论（比如「已完成」），
            #    再把自己设成在读 —— 一次点击把书的状态改坏。
            if old is not None and old.pk == book.pk:
                raise FocusSwitchError('same_book', '这一本已经是当前在读')

            # ② 旧书结论
            if old is None:
                # 没有旧书却传了结论：说明调用方以为在关一本书。静默忽略就是
                # 「用户以为点完了，其实什么也没发生」—— 直接说清楚。
                if close_mode:
                    raise FocusSwitchError('no_current_book', '当前没有在读的书，不需要给结论')
            else:
                if not close_mode:
                    raise FocusSwitchError('close_mode_required', '换书前要先给现在这本一个结论')

                if close_mode == ReadingFocusService.CLOSE_FINISHED:
                    # 🔴 已经是「已读完」就不动 `readDate`：那本书的完成日期是
                    #    既成事实，再点一次「读完了」不该把它改成今天
                    #    （书页的编辑弹窗可以单独把状态改成已读完，之后再换书就会走到这里）。
                    if old.status != Book.STATUS_FINISHED:
                        old.status = Book.STATUS_FINISHED
                        old.readDate = today
                        old.save(update_fields=['status', 'readDate', 'updated_at'])
                        touched += 1
                elif close_mode == ReadingFocusService.CLOSE_ABANDONED:
                    text = (reason or '').strip()
                    if not text:
                        raise FocusSwitchError('reason_required', '弃读必须写原因')
                    old.status = Book.STATUS_ABANDONED
                    old.abandon_reason = text
                    old.save(update_fields=['status', 'abandon_reason', 'updated_at'])
                    touched += 1
                elif close_mode == ReadingFocusService.CLOSE_LATER:
                    # 只回待读池：`abandon_reason` 原样保留 —— 之前写过弃读原因的，
                    # 不因为「暂时放回」被抹掉。
                    if old.status != Book.STATUS_TO_READ:
                        old.status = Book.STATUS_TO_READ
                        old.save(update_fields=['status', 'updated_at'])
                        touched += 1
                else:
                    raise FocusSwitchError('bad_close_mode', '不认识的结论')

            # ③ 新书：待读 / 搁置 → 在读；在读 / 二刷不动。
            #    · 搁置被选中 = 捡回来了，留在「搁置」里与指针矛盾（页头写「现在读这本」，
            #      列表里挂着「搁置」标签）；
            #    · 二刷尤其不能动 —— 降级会把「第几遍」抹掉；
            #    · 已在读的那本被选中，状态本来就是对的。
            if book.status in (Book.STATUS_TO_READ, Book.STATUS_SHELVED):
                book.status = Book.STATUS_READING
                book.save(update_fields=['status', 'updated_at'])
                touched += 1

            written['book_read_list'] = touched

            # ④ 指针（`update_or_create(pk=1)` 是单行的唯一保证）
            focus, _ = ReadingFocus.objects.update_or_create(
                pk=ReadingFocusService.FOCUS_PK,
                defaults={'book': book, 'started_on': today},
            )

        return {'focus': focus, 'written': written}

