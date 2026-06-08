from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """标准分页：默认每页 10 条，支持 page_size 参数"""

    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100
