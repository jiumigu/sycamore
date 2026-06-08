from datetime import datetime

import os
import uuid

from django.conf import settings
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import FoodRecord
from .serializers import (
    FoodLocationSerializer,
    FoodMapDataSerializer,
    FoodRecordListSerializer,
    FoodRecordSerializer,
    FoodStatsSerializer,
)
from .services import FoodService


class FoodRecordViewSet(viewsets.ModelViewSet):
    """美食记录 CRUD"""

    queryset = FoodRecord.objects.all()
    permission_classes = [AllowAny]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'dish_name', 'location', 'notes', 'tags']
    ordering_fields = ['eat_date', 'rating', 'price', 'created_at']
    ordering = ['-eat_date', '-id']

    def get_serializer_class(self):
        if self.action == 'list':
            return FoodRecordListSerializer
        return FoodRecordSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params

        qs = qs.filter(user_id=params.get('user_id', 1))

        category = params.get('category')
        if category:
            qs = qs.filter(category=category)

        taste_level = params.get('taste_level')
        if taste_level:
            qs = qs.filter(taste_level=taste_level)

        province = params.get('province')
        if province:
            qs = qs.filter(province=province)

        city = params.get('city')
        if city:
            qs = qs.filter(city=city)

        year = params.get('year')
        if year:
            qs = qs.filter(eat_date__year=int(year))

        month = params.get('month')
        if month:
            qs = qs.filter(eat_date__month=int(month))

        min_rating = params.get('min_rating')
        if min_rating:
            qs = qs.filter(rating__gte=float(min_rating))

        return qs

    def perform_create(self, serializer):
        serializer.save(user_id=1)

    # ─── 统计 / 数据端点 ───

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """获取美食统计总览"""
        data = FoodService.get_stats(user_id=request.query_params.get('user_id', 1))
        serializer = FoodStatsSerializer(data)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def locations(self, request):
        """获取去过的地方"""
        data = FoodService.get_locations(user_id=request.query_params.get('user_id', 1))
        serializer = FoodLocationSerializer(data, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def map_data(self, request):
        """获取地图展示数据"""
        data = FoodService.get_map_data(user_id=request.query_params.get('user_id', 1))
        serializer = FoodMapDataSerializer(data, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def tags(self, request):
        """获取常用标签"""
        data = FoodService.get_tags(user_id=request.query_params.get('user_id', 1))
        return Response(data)

    @action(detail=False, methods=['get'])
    def trend(self, request):
        """获取月度趋势"""
        year = int(request.query_params.get('year', datetime.now().year))
        user_id = int(request.query_params.get('user_id', 1))
        data = FoodService.get_monthly_trend(year=year, user_id=user_id)
        return Response(data)

    @action(detail=False, methods=['get'])
    def categories(self, request):
        """获取分类分布"""
        data = FoodService.get_category_distribution(
            user_id=request.query_params.get('user_id', 1),
        )
        return Response(data)

    @action(detail=False, methods=['get'])
    def taste_distribution(self, request):
        """获取美味等级分布"""
        data = FoodService.get_taste_distribution(
            user_id=request.query_params.get('user_id', 1),
        )
        return Response(data)

    @action(detail=False, methods=['post'])
    def upload(self, request):
        """上传图片 / 创建记录。
        只传文件（无 name）→ 存文件返 URL（供 el-upload 回调）。
        传 name + 文件 → 创建完整记录，封面设为上传图片。
        """
        file = request.FILES.get('image') or request.FILES.get('file')
        if not file:
            return Response({'error': '未提供文件'}, status=status.HTTP_400_BAD_REQUEST)

        # 保存文件
        ext = os.path.splitext(file.name)[1]
        filename = f'food/{uuid.uuid4().hex}{ext}'
        upload_dir = settings.MEDIA_ROOT / 'food'
        os.makedirs(upload_dir, exist_ok=True)
        with open(upload_dir / filename.replace('food/', ''), 'wb') as f:
            for chunk in file.chunks():
                f.write(chunk)
        url = f'{settings.MEDIA_URL}{filename}'

        # 仅上传文件（el-upload / FormData 只传文件时）
        if not request.data.get('name'):
            return Response({'url': url})

        # 创建记录（含封面图）
        data = dict(request.data.items())
        for skip in ('image', 'file'):
            data.pop(skip, None)
        data['cover_image'] = url
        data['user_id'] = 1

        if not data.get('eat_date'):
            data['eat_date'] = datetime.now().strftime('%Y-%m-%d')
        if not data.get('province') and data.get('city'):
            data['province'] = data['city']

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
