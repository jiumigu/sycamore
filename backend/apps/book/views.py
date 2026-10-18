from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Book
from .serializers import (
    BookBulkUpdateSerializer,
    BookCreateUpdateSerializer,
    BookDetailSerializer,
    BookListSerializer,
    BookStatsSerializer,
)
from .services import BookService


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
