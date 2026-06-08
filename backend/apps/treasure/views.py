from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from .models import GoodThing
from .serializers import GoodThingSerializer


class GoodThingViewSet(viewsets.ModelViewSet):
    """好东西档案馆视图集"""

    queryset = GoodThing.objects.all()
    permission_classes = [AllowAny]
    serializer_class = GoodThingSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        record_type = self.request.query_params.get('record_type')
        if record_type:
            qs = qs.filter(record_type=record_type)
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)
        return qs
