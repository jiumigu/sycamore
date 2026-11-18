from django.utils import timezone
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Book
from .serializers import (
    BookBulkUpdateSerializer,
    BookCreateUpdateSerializer,
    BookDetailSerializer,
    BookListSerializer,
    BookStatsSerializer,
    ReadingFocusSerializer,
    ReadingFocusSwitchSerializer,
)
from .services import BookService, FocusSwitchError, ReadingFocusService


class BookPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.all()
    permission_classes = [AllowAny]
    pagination_class = BookPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['btitle', 'author', 'closedop', 'openop']
    ordering_fields = ['readDate', 'updated_at', 'recommend', 'btitle']
    ordering = ['-readDate']

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return BookCreateUpdateSerializer
        elif self.action == 'list':
            return BookListSerializer
        return BookDetailSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        filters_dict = {}
        for param, field in [
            ('btype', 'btype'), ('status', 'status'), ('years', 'years'),
            ('reading_depth', 'reading_depth'),
        ]:
            val = params.get(param)
            if val:
                filters_dict[field] = val

        recommend_min = params.get('recommend_min')
        recommend_max = params.get('recommend_max')
        if recommend_min:
            filters_dict['recommend__gte'] = recommend_min
        if recommend_max:
            filters_dict['recommend__lte'] = recommend_max

        tag = params.get('tag')
        if tag:
            filters_dict['tags__icontains'] = tag

        search = params.get('search')
        if search:
            filters_dict['btitle__icontains'] = search

        return queryset.filter(**filters_dict)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        year = request.query_params.get('year') or None
        data = BookService.get_stats(year)
        serializer = BookStatsSerializer(data)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_year(self, request):
        year = request.query_params.get('year')
        queryset = self.get_queryset()
        if year:
            queryset = queryset.filter(years=year)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = BookListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = BookListSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_type(self, request):
        btype = request.query_params.get('btype')
        queryset = self.get_queryset()
        if btype:
            queryset = queryset.filter(btype=btype)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = BookListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = BookListSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def search_by_tag(self, request):
        tag = request.query_params.get('tag', '')
        queryset = self.get_queryset()
        if tag:
            queryset = queryset.filter(tags__icontains=tag)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = BookListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = BookListSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def mark_completed(self, request, pk=None):
        book = self.get_object()
        BookService.mark_completed(book)
        return Response({'status': 'ok'})

    @action(detail=False, methods=['post'])
    def bulk_update(self, request):
        """批量改「阅读状态」/「阅读深度」（阅读管理页的批量工具条）。

        `requested` 与 `updated` **分开报**：传进来的编号里可能有已被删掉的，
        只回一个数会让前端把「命中 3 条」说成「改了 5 条」—— 静默的谎。

        至于「哪些状态能批量改」，口径在 `BookBulkUpdateSerializer`（排除「弃读」）。
        """
        serializer = BookBulkUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        updated = BookService.bulk_update(
            data['bids'],
            status=data.get('status'),
            reading_depth=data.get('reading_depth'),
        )
        return Response({'updated': updated, 'requested': len(data['bids'])})

    @action(detail=False, methods=['delete'])
    def bulk_delete(self, request):
        bids = request.data.get('bids', [])
        if not bids:
            return Response({'error': '请提供要删除的编号列表'}, status=400)
        count, _ = Book.objects.filter(bid__in=bids).delete()
        return Response({'deleted': count})


def _focus_payload(focus, *, today) -> dict:
    """把指针行拼成出参：书 + 从哪天开始 + 第几天。

    🔴 「今天」一律 `timezone.localdate()`（`USE_TZ=True` 下 `date.today()` 取的是
       进程本地日期，容器里通常是 UTC —— 凌晨 0～8 点会整整差一天）。
    """
    book = focus.book if focus and focus.book_id else None
    started_on = focus.started_on if focus else None
    return {
        'book': book,
        'started_on': started_on,
        'days': ReadingFocusService.days_on(book, started_on, today=today),
    }


class ReadingFocusView(APIView):
    """`GET /api/books/reading-focus/` —— 当前在读的是哪一本。

    只读：不 `get_or_create`。没有指针就是没有，不能因为「有人看了一眼」
    就凭空建出一行空指针（那样「表里有几行」就不再说明任何事）。
    """

    permission_classes = [AllowAny]

    def get(self, request):
        today = timezone.localdate()
        focus = ReadingFocusService.get_focus()
        return Response(ReadingFocusSerializer(instance=_focus_payload(focus, today=today)).data)


class ReadingFocusCandidatesView(APIView):
    """`GET /api/books/reading-focus/candidates/?search=` —— 「接下来读哪本」的候选。

    🔴 只给**还能读**的书（待读 / 在读 / 二刷 / 搁置），且不含当前这本 ——
       口径在 `ReadingFocusService.candidate_queryset`，这里只管取和丢给序列化器。
    🔴 不分页：候选集是「还没读完、没弃读」的书，个位数到两位数。
       分页在这种基数上是负资产（前端还得处理 page / 越界 / 页码漂移）。
    🔴 `search` 与列表接口的 `?search=` 同口径（书名 + 作者），
       因为弹窗那个下拉框写的就是「搜书名或作者」。
    """

    permission_classes = [AllowAny]

    def get(self, request):
        focus = ReadingFocusService.get_focus()
        qs = ReadingFocusService.candidate_queryset(
            focus=focus,
            keyword=request.query_params.get('search', ''),
        )
        books = qs[:ReadingFocusService.CANDIDATE_LIMIT]
        return Response({
            'results': BookListSerializer(books, many=True).data,
            # ⚠️ `count` 是**这批返回的条数**，不是全库可读总数 ——
            #    候选集上限 20，前端若想提示「还有更多」得另给字段。
            #    现在不提示：读不完的书本来就不可能超过几十本。
            'count': len(books),
        })


class ReadingFocusSwitchView(APIView):
    """`POST /api/books/reading-focus/switch/` —— 换书（必须给旧书结论）。

    语义校验全部在 `ReadingFocusService.switch`，这里只做三件事：
    取书、翻译异常成 `{code, error}`、回报写了哪些表。
    """

    permission_classes = [AllowAny]

    def post(self, request):
        payload = ReadingFocusSwitchSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        book = Book.objects.filter(pk=data['book_id']).first()
        if book is None:
            return Response(
                {'code': 'book_not_found', 'error': '这本书不存在（可能已被删除）'},
                status=404,
            )

        today = timezone.localdate()
        try:
            result = ReadingFocusService.switch(
                book,
                today=today,
                close_mode=data.get('close_mode'),
                reason=data.get('reason', ''),
            )
        except FocusSwitchError as exc:
            return Response({'code': exc.code, 'error': exc.message}, status=400)

        body = ReadingFocusSerializer(instance=_focus_payload(result['focus'], today=today)).data
        body['written'] = result['written']
        return Response(body)
