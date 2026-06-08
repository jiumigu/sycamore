from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import DanceRecord
from .serializers import DanceRecordSerializer
from .services import DanceStatsService


class DanceRecordViewSet(viewsets.ModelViewSet):
    """舞蹈记录视图集"""

    queryset = DanceRecord.objects.all()
    permission_classes = [AllowAny]
    serializer_class = DanceRecordSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['remark', 'teacher_name']
    ordering_fields = ['study_time', 'score']
    ordering = ['-study_time']

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        year = params.get('year')
        if year:
            qs = qs.filter(year=int(year))

        month = params.get('month')
        if month:
            qs = qs.filter(month=int(month))

        dance_type = params.get('dance_type')
        if dance_type:
            qs = qs.filter(dance_type=dance_type)

        teacher = params.get('teacher')
        if teacher:
            qs = qs.filter(teacher_name=teacher)

        difficulty = params.get('difficulty')
        if difficulty:
            qs = qs.filter(difficulty=difficulty)

        return qs

    @action(detail=False, methods=['get'])
    def stats(self, request):
        data = DanceStatsService.get_overview()
        return Response(data)

    @action(detail=False, methods=['get'])
    def trend(self, request):
        year = request.query_params.get('year')
        data = DanceStatsService.get_trend(int(year) if year else None)
        return Response(data)

    @action(detail=False, methods=['get'])
    def teachers(self, request):
        data = DanceStatsService.get_teachers()
        return Response(data)

    @action(detail=False, methods=['get'])
    def types(self, request):
        data = DanceStatsService.get_types()
        return Response(data)

    @action(detail=False, methods=['get'])
    def score_trend(self, request):
        data = DanceStatsService.get_score_trend()
        return Response(data)

    @action(detail=False, methods=['get'])
    def calendar(self, request):
        year = request.query_params.get('year')
        month = request.query_params.get('month')
        data = DanceStatsService.get_calendar(
            int(year) if year else None,
            int(month) if month else None,
        )
        return Response(data)
