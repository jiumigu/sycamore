from django.db.models import Avg, Count
from django.utils import timezone

from .models import Book


class BookService:
    """书籍业务逻辑"""

    @staticmethod
    def get_stats():
        """获取综合统计数据"""
        queryset = Book.objects.all()

        total_count = queryset.count()
        completed_count = queryset.filter(status='已完成').count()
        reading_count = queryset.filter(status='在读').count()
        abandoned_count = queryset.filter(status='弃读').count()
        planned_count = queryset.filter(status='计划阅读').count()

        now = timezone.now()
        month_count = queryset.filter(readDate__year=now.year, readDate__month=now.month).count()
        year_count = queryset.filter(readDate__year=now.year).count()

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
            queryset.values('years')
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
        """标记为已完成"""
        book.status = '已完成'
        book.save()
