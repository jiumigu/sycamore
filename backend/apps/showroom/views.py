"""展厅 · 视图层。

🔴 三条约定（与 works / treasure 同款）：

1. **GET 一律不写库**：品牌单例在 GET / 预览里用 `.first()`，绝不 `get_or_create`；
   `get_solo()` 只在 PUT（编辑）里用。
2. **列表端点 `pagination_class = None` 返回裸数组**（DRF 全局分页会包成
   `{count, results}`，前端按数组取用即「假 0」）。
3. **预览只下发可见项**（`is_visible=True`）——策展的显隐开关在预览里才真正生效。
"""
from rest_framework import viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

# 🔴 媒体白名单 / 大小上限 / 保存逻辑唯一实现（works 与 showroom 共用）——
#    这里不再有第二份判据。
from apps.core.media import MediaUploadError, save_upload_file

from .constants import SKILL_LEVEL_OPTIONS
from .models import ShowroomCase, ShowroomProfile, ShowroomSkill, ShowroomWork
from .serializers import (
    ShowroomCaseSerializer,
    ShowroomProfileSerializer,
    ShowroomSkillSerializer,
    ShowroomWorkSerializer,
)


def _empty_profile():
    """品牌单例还不存在时的空结构（字段与序列化器出参对齐，id / updated_at 为 null）。"""
    return {
        'id': None, 'ip_name': '', 'tagline': '', 'positioning': '',
        'bio': '', 'email': '', 'wechat': '', 'other_contact': '', 'updated_at': None,
    }


class ShowroomProfileView(APIView):
    """品牌层单例。GET 只读、PUT 编辑。"""

    permission_classes = [AllowAny]

    def get(self, request):
        profile = ShowroomProfile.objects.first()
        if profile is None:
            return Response(_empty_profile())
        return Response(ShowroomProfileSerializer(profile).data)

    def put(self, request):
        profile = ShowroomProfile.get_solo()
        ser = ShowroomProfileSerializer(profile, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


class ShowroomCaseViewSet(viewsets.ModelViewSet):
    queryset = ShowroomCase.objects.all()
    permission_classes = [AllowAny]
    serializer_class = ShowroomCaseSerializer
    pagination_class = None


class ShowroomSkillViewSet(viewsets.ModelViewSet):
    queryset = ShowroomSkill.objects.all()
    permission_classes = [AllowAny]
    serializer_class = ShowroomSkillSerializer
    pagination_class = None


class ShowroomWorkViewSet(viewsets.ModelViewSet):
    queryset = ShowroomWork.objects.select_related('work')
    permission_classes = [AllowAny]
    serializer_class = ShowroomWorkSerializer
    pagination_class = None


class ShowroomMediaUploadView(APIView):
    """展厅媒体上传（图片 / 视频）。

    multipart 字段 `file`；存 `MEDIA_ROOT/showroom/YYYYMM/<uuid><ext>`，
    返回 `{url, type}` —— type 由扩展名白名单判定，前端只存不用再判。
    """

    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file = request.FILES.get('file')
        try:
            url, media_type = save_upload_file(file, 'showroom')
        except MediaUploadError as exc:
            return Response({'error': exc.message}, status=exc.status)
        return Response({'url': url, 'type': media_type})


class ShowroomMetaView(APIView):
    """界面枚举（技能熟练度三级）—— 前端下拉用，不写第二份文案。"""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response({'skill_levels': SKILL_LEVEL_OPTIONS})


class ShowroomPreviewView(APIView):
    """预览聚合（只读，只下发可见项）。"""

    permission_classes = [AllowAny]

    def get(self, request):
        profile = ShowroomProfile.objects.first()
        return Response({
            'profile': ShowroomProfileSerializer(profile).data if profile else _empty_profile(),
            'cases': ShowroomCaseSerializer(
                ShowroomCase.objects.filter(is_visible=True), many=True,
            ).data,
            'skills': ShowroomSkillSerializer(
                ShowroomSkill.objects.filter(is_visible=True), many=True,
            ).data,
            'works': ShowroomWorkSerializer(
                ShowroomWork.objects.filter(is_visible=True).select_related('work'), many=True,
            ).data,
        })
