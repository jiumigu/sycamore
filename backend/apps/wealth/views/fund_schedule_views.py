"""资金排程计划 API（快照式：list / retrieve / create / destroy）"""
from rest_framework import mixins, viewsets

from ..models import FundSchedule
from ..serializers import FundScheduleSerializer


class FundScheduleViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """资金排程：只读 + 创建 + 删除，不提供更新（每次保存即新快照）"""

    queryset = FundSchedule.objects.all()
    serializer_class = FundScheduleSerializer

    def get_queryset(self):
        return FundSchedule.objects.filter(user_id=1)
