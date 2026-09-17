from collections import defaultdict

from django.db.models import Max
from django.utils import timezone
from django.utils.dateparse import parse_date

from rest_framework import status, views
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.toolkit.models import CityCoordinate

from .models import TravelPlan, TravelPlanItem, TravelRecord, TravelWish
from .serializers import TravelPlanItemSerializer, TravelPlanSerializer, TravelRecordSerializer, TravelWishSerializer
from .services import MapDataService, TravelPlanService, TravelStatsService, TripLogService, get_coordinates, get_province, place_key

# 心愿分类 → 计划子项类型（food/scenic/transport/hotel）
WISH_FOOD_CATEGORIES = {'美食', '夜市', '路线'}


def _lookup_coord(qs, name: str, city: str):
    """在给定候选集内解析：名称精确 → 名称模糊（景区优先）→ 城市定位"""
    if name:
        row = qs.filter(name=name).first()
        if row:
            return row
        row = (
            qs.filter(city_type='景区', name__icontains=name).first()
            or qs.filter(name__icontains=name).first()
        )
        if row:
            return row
    if city:
        for cand in (city, f'{city}市', f'{city}州'):
            row = qs.filter(name=cand).first()
            if row:
                return row
        row = qs.filter(name__istartswith=city).order_by('id').first()
        if row:
            return row
    return None


def resolve_wish_coords(name: str, city: str, province: str = ''):
    """心愿坐标解析，返回 (province, lng, lat)

    解析顺序（避免短名跨省撞车，如「连江」台湾省连江县 /「三门」河南三门峡市）：
    ① 行政区/景区类行（排除 city_type='其他'）本省 → ② 行政区/景区类全国
    → ③ 含「其他」类行本省 → ④ 含「其他」类全国
    """
    base = CityCoordinate.objects.all()
    ordered = [base.exclude(city_type='其他'), base]
    for qs in ordered:
        if province:
            row = _lookup_coord(qs.filter(province=province), name, city)
            if row:
                return row.province, row.lng, row.lat
        row = _lookup_coord(qs, name, city)
        if row:
            return row.province, row.lng, row.lat
    return '', None, None


class TravelPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'


class TravelRecordListCreateView(views.APIView):
    """旅行记录 列表 / 创建"""

    permission_classes = [AllowAny]

    def get(self, request):
        qs = TravelRecord.objects.all().order_by('-tyear', '-ttime')

        # 筛选
        year = request.query_params.get('year')
        province = request.query_params.get('province')
        if year:
            qs = qs.filter(tyear=int(year))
        if province:
            qs = qs.filter(parentnode__contains=province)

        paginator = TravelPagination()
        page = paginator.paginate_queryset(qs, request)
        if page is not None:
            serializer = TravelRecordSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = TravelRecordSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = TravelRecordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        # 自动地理编码
        city_name = data.get('tname', '')
        if city_name and not data.get('latitude'):
            coord = get_coordinates(city_name)
            if coord:
                data['latitude'] = coord[0]
                data['longitude'] = coord[1]

        record = TravelRecord.objects.create(**data)
        return Response(TravelRecordSerializer(record).data, status=status.HTTP_201_CREATED)


class TravelRecordDetailView(views.APIView):
    """旅行记录 详情 / 更新 / 删除"""

    permission_classes = [AllowAny]

    def get_object(self, pk):
        try:
            return TravelRecord.objects.get(tid=pk)
        except TravelRecord.DoesNotExist:
            return None

    def get(self, _request, pk):
        record = self.get_object(pk)
        if not record:
            return Response({'error': '记录不存在'}, status=status.HTTP_404_NOT_FOUND)
        return Response(TravelRecordSerializer(record).data)

    def put(self, request, pk):
        record = self.get_object(pk)
        if not record:
            return Response({'error': '记录不存在'}, status=status.HTTP_404_NOT_FOUND)

        serializer = TravelRecordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        # 自动补全地理编码
        city_name = data.get('tname', '')
        if city_name and not data.get('latitude'):
            coord = get_coordinates(city_name)
            if coord:
                data['latitude'] = coord[0]
                data['longitude'] = coord[1]

        for key, value in data.items():
            setattr(record, key, value)
        record.save()
        return Response(TravelRecordSerializer(record).data)

    def delete(self, _request, pk):
        record = self.get_object(pk)
        if not record:
            return Response({'error': '记录不存在'}, status=status.HTTP_404_NOT_FOUND)
        record.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MapDataView(views.APIView):
    """地图展示数据 — 省份热力 + 城市气泡"""

    permission_classes = [AllowAny]

    def get(self, request):
        year_from = request.query_params.get('year_from')
        year_to = request.query_params.get('year_to')
        if year_from:
            year_from = int(year_from)
        if year_to:
            year_to = int(year_to)
        data = MapDataService.get_map_data(year_from, year_to)
        return Response(data)


class TravelStatsView(views.APIView):
    """旅行统计总览"""

    permission_classes = [AllowAny]

    def get(self, request):
        year_from = request.query_params.get('year_from')
        year_to = request.query_params.get('year_to')
        if year_from:
            year_from = int(year_from)
        if year_to:
            year_to = int(year_to)
        data = TravelStatsService.get_stats(year_from, year_to)
        return Response(data)


class ProvinceListView(views.APIView):
    """到访省份列表"""

    permission_classes = [AllowAny]

    def get(self, _request):
        records = TravelRecord.objects.all().values_list('parentnode', flat=True).distinct()
        provinces = set()
        for p in records:
            if not p:
                continue
            prov = get_province(p)
            if prov:
                provinces.add(prov)
            elif p.endswith('市'):
                prov = get_province(p)
                if prov:
                    provinces.add(prov)
        result = [{'province': p} for p in sorted(provinces)]
        return Response(result)


class YearListView(views.APIView):
    """旅行年份列表"""

    permission_classes = [AllowAny]

    def get(self, _request):
        years = (
            TravelRecord.objects
            .filter(tyear__isnull=False)
            .values_list('tyear', flat=True)
            .distinct()
            .order_by('-tyear')
        )
        return Response([{'year': y} for y in years])


class TravelPlanViewSet(ModelViewSet):
    """旅行计划 CRUD + 明细 + 统计"""

    queryset = TravelPlan.objects.all()
    serializer_class = TravelPlanSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return TravelPlan.objects.filter(user_id=1)

    def perform_create(self, serializer):
        plan = serializer.save(user_id=1)
        items_data = self.request.data.get('items', [])
        for item_data in items_data:
            TravelPlanItem.objects.create(plan=plan, **item_data)
        TravelPlanService.recalculate_total(plan)

    def perform_update(self, serializer):
        plan = serializer.save()
        # 编辑时带 items 则整体替换明细，未带（如仅改状态）则保留
        items_data = self.request.data.get('items')
        if items_data is not None:
            # 记录旧明细的心愿关联（按 类型|名称 复原），被移除的心愿回退为「想去」
            old_links = {f'{i.item_type}|{i.name}': i.wish_id for i in plan.items.all() if i.wish_id}
            plan.items.all().delete()
            for item_data in items_data:
                item = TravelPlanItem.objects.create(plan=plan, **item_data)
                if not item.wish_id:
                    wid = old_links.get(f'{item.item_type}|{item.name}')
                    if wid:
                        item.wish_id = wid
                        item.save(update_fields=['wish'])
            new_wish_ids = {i.wish_id for i in plan.items.all() if i.wish_id}
            for wid in set(old_links.values()) - new_wish_ids:
                w = TravelWish.objects.filter(id=wid, status='已列入计划').first()
                if w:
                    w.status = '想去'
                    w.save(update_fields=['status'])
        TravelPlanService.recalculate_total(plan)

    @action(detail=True, methods=['get'])
    def items(self, request, pk=None):
        """计划子项列表"""
        plan = self.get_object()
        items = plan.items.all()
        return Response(TravelPlanItemSerializer(items, many=True).data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """统计所有计划费用"""
        return Response(TravelPlanService.get_stats())

    @action(detail=False, methods=['post'], url_path='route-preview')
    def route_preview(self, request):
        """路线 → 计划 预检：每站可带入的「想去」心愿"""
        destinations = [str(d).strip() for d in (request.data.get('destinations') or []) if str(d).strip()]
        if not destinations:
            return Response({'error': '至少需要一个目的地'}, status=status.HTTP_400_BAD_REQUEST)

        buckets: dict[str, list[TravelWish]] = defaultdict(list)
        for w in TravelWish.objects.filter(user_id=1, status='想去').order_by('category', 'name'):
            buckets[place_key(w.city, w.province)].append(w)

        stations = []
        for dest in destinations:
            matched = buckets.get(place_key(dest, ''), [])
            stations.append({
                'city': dest,
                'wish_count': len(matched),
                'wishes': [
                    {
                        'id': w.id,
                        'name': w.name,
                        'category': w.category,
                        'is_food': w.category in WISH_FOOD_CATEGORIES,
                    }
                    for w in matched[:30]
                ],
            })
        return Response({'stations': stations})

    @action(detail=False, methods=['post'], url_path='from-route')
    def from_route(self, request):
        """由路线推演生成旅行计划（可把选中的本城心愿一并带入计划）"""
        origin = (request.data.get('origin') or '').strip()
        destinations = [str(d).strip() for d in (request.data.get('destinations') or []) if str(d).strip()]
        if not destinations:
            return Response({'error': '至少需要一个目的地'}, status=status.HTTP_400_BAD_REQUEST)

        route_name = (request.data.get('name') or '').strip()
        if not route_name:
            route_name = f'{destinations[0]}等 {len(destinations)} 站'
        destination = destinations[-1]

        raw_start = request.data.get('start_date')
        start_date = parse_date(str(raw_start)) if raw_start else None
        if raw_start and not start_date:
            return Response({'error': '出发日期格式应为 YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)

        route_desc = f'{" → ".join([origin] + destinations) if origin else " → ".join(destinations)}'
        plan = TravelPlan.objects.create(
            user_id=1,
            name=route_name,
            destination=destination,
            start_date=start_date,
            status='计划中',
            notes=f'由路线推演生成：{route_desc}',
        )

        sort = 0
        wish_ids = request.data.get('wish_ids') or []
        attached: list[TravelWish] = []
        if wish_ids:
            wishes = list(TravelWish.objects.filter(id__in=wish_ids, user_id=1))
            order = {wid: idx for idx, wid in enumerate(wish_ids)}
            wishes.sort(key=lambda w: order.get(w.id, 999))
            for w in wishes:
                sort += 1
                TravelPlanItem.objects.create(
                    plan=plan,
                    wish=w,
                    item_type='food' if w.category in WISH_FOOD_CATEGORIES else 'scenic',
                    name=w.name,
                    sort_order=sort,
                )
                attached.append(w)
        else:
            # 未选心愿时，为每个目的地建一条占位项，便于在计划页继续细化
            for dest in destinations:
                sort += 1
                TravelPlanItem.objects.create(
                    plan=plan, item_type='scenic', name=dest,
                    sort_order=sort, notes='待细化',
                )

        if attached:
            TravelWish.objects.filter(
                id__in=[w.id for w in attached], status='想去',
            ).update(status='已列入计划')

        TravelPlanService.recalculate_total(plan)
        return Response(TravelPlanSerializer(plan).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='toggle-item')
    def toggle_item(self, request, pk=None):
        """勾选/取消子项完成"""
        item_id = request.data.get('item_id')
        if not item_id:
            return Response({'error': '缺少 item_id'}, status=status.HTTP_400_BAD_REQUEST)
        plan = self.get_object()
        try:
            item = plan.items.get(id=item_id)
        except TravelPlanItem.DoesNotExist:
            return Response({'error': '子项不存在'}, status=status.HTTP_404_NOT_FOUND)
        item.is_completed = not item.is_completed
        item.completed_at = timezone.now() if item.is_completed else None
        item.save()
        # 打卡联动心愿状态
        if item.wish_id:
            if item.is_completed:
                item.wish.status = '已打卡'
                item.wish.visited_at = timezone.localdate()
            else:
                item.wish.status = '已列入计划'
                item.wish.visited_at = None
            item.wish.save(update_fields=['status', 'visited_at'])
        return Response(TravelPlanItemSerializer(item).data)


class TravelWishViewSet(ModelViewSet):
    """旅行心愿单 CRUD + 加入计划 + 打卡"""

    queryset = TravelWish.objects.all()
    serializer_class = TravelWishSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        qs = TravelWish.objects.filter(user_id=1)
        category = self.request.query_params.get('category')
        status_q = self.request.query_params.get('status')
        province = self.request.query_params.get('province')
        city = self.request.query_params.get('city')
        search = self.request.query_params.get('search')
        if category:
            qs = qs.filter(category=category)
        if status_q:
            qs = qs.filter(status=status_q)
        if province:
            qs = qs.filter(province=province)
        if city:
            qs = qs.filter(city=city)
        if search:
            qs = qs.filter(name__icontains=search)
        return qs

    def perform_create(self, serializer):
        wish = serializer.save(user_id=1)
        if wish.lng is None or wish.lat is None:
            prov, lng, lat = resolve_wish_coords(wish.name, wish.city, wish.province)
            updates = {}
            if wish.lng is None and lng is not None:
                updates['lng'] = lng
            if wish.lat is None and lat is not None:
                updates['lat'] = lat
            if not wish.province and prov:
                updates['province'] = prov
            if updates:
                TravelWish.objects.filter(id=wish.id).update(**updates)
                for k, v in updates.items():
                    setattr(wish, k, v)

    @action(detail=True, methods=['post'])
    def mark_visited(self, request, pk=None):
        """打卡 / 取消打卡"""
        wish = self.get_object()
        if wish.status == '已打卡':
            # 取消打卡：有计划关联回到「已列入计划」，否则「想去」
            wish.status = '已列入计划' if wish.plan_items.exists() else '想去'
            wish.visited_at = None
        else:
            wish.status = '已打卡'
            wish.visited_at = request.data.get('visited_at') or timezone.localdate()
        wish.save(update_fields=['status', 'visited_at', 'updated_at'])
        return Response(TravelWishSerializer(wish).data)

    @action(detail=True, methods=['post'])
    def record_visit(self, request, pk=None):
        """打卡并记录：打卡日期 / 星级评分 / 打卡评价 / 是否值得反复

        已打卡的心愿再次调用即「修改记录」，未打卡的调用即「打卡 + 记录」。
        """
        wish = self.get_object()
        data = request.data
        fields = {'status', 'updated_at'}

        if 'visited_at' in data:
            raw = data.get('visited_at')
            if raw:
                parsed = parse_date(str(raw))
                if not parsed:
                    return Response({'error': '打卡日期格式应为 YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)
                wish.visited_at = parsed
            else:
                wish.visited_at = None
            fields.add('visited_at')
        if wish.visited_at is None:
            wish.visited_at = timezone.localdate()
            fields.add('visited_at')

        if 'visit_rating' in data:
            raw = data.get('visit_rating')
            if raw in (None, '', 'null'):
                wish.visit_rating = None
            else:
                try:
                    rating = int(raw)
                except (TypeError, ValueError):
                    rating = -1
                if rating < 1 or rating > 5:
                    return Response({'error': '评分应为 1-5 的整数'}, status=status.HTTP_400_BAD_REQUEST)
                wish.visit_rating = rating
            fields.add('visit_rating')

        if 'visit_notes' in data:
            wish.visit_notes = (data.get('visit_notes') or '').strip()
            fields.add('visit_notes')

        if 'worth_revisit' in data:
            raw = data.get('worth_revisit')
            wish.worth_revisit = raw is True or str(raw).lower() in ('true', '1', 'yes')
            fields.add('worth_revisit')

        if 'visit_plan' in data:
            raw_plan = data.get('visit_plan')
            if raw_plan in (None, '', 'null'):
                wish.visit_plan = None
            else:
                plan = TravelPlan.objects.filter(id=raw_plan, user_id=1).first()
                if not plan:
                    return Response({'error': '所属行程不存在'}, status=status.HTTP_404_NOT_FOUND)
                wish.visit_plan = plan
            fields.add('visit_plan')

        wish.status = '已打卡'
        wish.save(update_fields=sorted(fields))
        return Response(TravelWishSerializer(wish).data)

    @action(detail=True, methods=['post'])
    def add_to_plan(self, request, pk=None):
        """把心愿加入旅行计划（可指定已有计划，否则自动新建）"""
        wish = self.get_object()
        plan_id = request.data.get('plan_id')
        if plan_id:
            plan = TravelPlan.objects.filter(id=plan_id, user_id=1).first()
            if not plan:
                return Response({'error': '计划不存在'}, status=status.HTTP_404_NOT_FOUND)
        else:
            dest = wish.city or wish.province or ''
            plan = TravelPlan.objects.create(
                user_id=1,
                name=f'{dest}之旅' if dest else '未命名行程',
                destination=dest,
                start_date=request.data.get('start_date') or None,
                status='计划中',
                notes='由旅行心愿单一键加入',
            )
        if plan.items.filter(wish=wish).exists():
            return Response({'error': '该心愿已在此计划中'}, status=status.HTTP_400_BAD_REQUEST)
        item_type = 'food' if wish.category in WISH_FOOD_CATEGORIES else 'scenic'
        next_sort = (plan.items.aggregate(m=Max('sort_order'))['m'] or 0) + 1
        item = TravelPlanItem.objects.create(
            plan=plan, wish=wish, item_type=item_type,
            name=wish.name, sort_order=next_sort,
        )
        TravelPlanService.recalculate_total(plan)
        if wish.status == '想去':
            wish.status = '已列入计划'
            wish.save(update_fields=['status'])
        return Response({
            'plan': TravelPlanSerializer(plan).data,
            'item': TravelPlanItemSerializer(item).data,
        })

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """心愿统计：状态 × 分类"""
        qs = self.get_queryset()
        by_status = {s: qs.filter(status=s).count() for s, _ in TravelWish.STATUS_CHOICES}
        by_category = {c: qs.filter(category=c).count() for c, _ in TravelWish.CATEGORY_CHOICES}
        located = qs.filter(lng__isnull=False, lat__isnull=False).count()
        return Response({'total': qs.count(), 'located': located, 'by_status': by_status, 'by_category': by_category})


class TripLogView(views.APIView):
    """行程日志 — 已打卡心愿按「日期 + 地点」聚合为一天一张卡

    只读；打卡不直接写旅行记录表，沉淀由 consolidate 显式触发。
    """

    permission_classes = [AllowAny]

    def get(self, request):
        raw_from = request.query_params.get('from')
        raw_to = request.query_params.get('to')
        date_from = parse_date(str(raw_from)) if raw_from else None
        date_to = parse_date(str(raw_to)) if raw_to else None
        if raw_from and not date_from:
            return Response({'error': 'from 日期格式应为 YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)
        if raw_to and not date_to:
            return Response({'error': 'to 日期格式应为 YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)

        plan_id = request.query_params.get('plan')
        city = request.query_params.get('city')
        data = TripLogService.build(
            date_from=date_from,
            date_to=date_to,
            plan_id=int(plan_id) if plan_id else None,
            city=city or None,
        )
        return Response(data)


class TripLogConsolidateView(views.APIView):
    """把某天某地的打卡清单沉淀为一条旅行足迹（只新增记录，不改动存量）"""

    permission_classes = [AllowAny]

    def post(self, request):
        raw_date = request.data.get('date')
        if not raw_date:
            return Response({'error': '缺少 date（YYYY-MM-DD）'}, status=status.HTTP_400_BAD_REQUEST)
        visit_date = parse_date(str(raw_date))
        if not visit_date:
            return Response({'error': '日期格式应为 YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)

        city = (request.data.get('city') or '').strip()

        candidates = list(
            TravelWish.objects.filter(
                user_id=1, status='已打卡', visited_at=visit_date, visit_record_id__isnull=True,
            ).order_by('category', 'name')
        )
        if city:
            target = place_key(city, '')
            candidates = [w for w in candidates if place_key(w.city, w.province) == target]
        if not candidates:
            return Response({'error': '该日期没有待沉淀的打卡记录'}, status=status.HTTP_400_BAD_REQUEST)

        first = candidates[0]
        place = (city or first.city or first.province or '').strip()
        province = first.province or (get_province(place) or '')

        # 坐标：优先取打卡点均值，其次查城市坐标
        lngs = [float(w.lng) for w in candidates if w.lng is not None]
        lats = [float(w.lat) for w in candidates if w.lat is not None]
        if lngs and lats:
            longitude = round(sum(lngs) / len(lngs), 6)
            latitude = round(sum(lats) / len(lats), 6)
        else:
            coord = get_coordinates(place) or get_coordinates(first.city or '')
            latitude, longitude = (coord[0], coord[1]) if coord else (None, None)

        # 摘要（tremark 限 255）
        summary = request.data.get('tremark') or '、'.join(w.name for w in candidates)
        summary = summary.strip()[:255]
        if not summary:
            summary = f'{place}打卡'

        ratings = [w.visit_rating for w in candidates if w.visit_rating]
        payload = {'user_id': 1}

        raw_rating = request.data.get('rating')
        if raw_rating in (None, '', 'null'):
            payload['rating'] = round(sum(ratings) / len(ratings)) if ratings else None
        else:
            try:
                rating = int(raw_rating)
            except (TypeError, ValueError):
                return Response({'error': '满意度应为 1-5 的整数'}, status=status.HTTP_400_BAD_REQUEST)
            if rating < 1 or rating > 5:
                return Response({'error': '满意度应为 1-5 的整数'}, status=status.HTTP_400_BAD_REQUEST)
            payload['rating'] = rating

        raw_cost = request.data.get('tcost')
        if raw_cost in (None, '', 'null'):
            payload['tcost'] = None
        else:
            try:
                payload['tcost'] = float(raw_cost)
            except (TypeError, ValueError):
                return Response({'error': '花费应为数字'}, status=status.HTTP_400_BAD_REQUEST)

        raw_days = request.data.get('duration_days')
        if raw_days in (None, '', 'null'):
            payload['duration_days'] = 1
        else:
            try:
                payload['duration_days'] = max(1, int(raw_days))
            except (TypeError, ValueError):
                return Response({'error': '停留天数应为整数'}, status=status.HTTP_400_BAD_REQUEST)

        record = TravelRecord.objects.create(
            parentnode=province or None,
            tname=place or None,
            district=first.district or '',
            tyear=visit_date.year,
            ttime=visit_date,
            tremark=summary,
            companions=(request.data.get('companions') or '').strip()[:200],
            latitude=latitude,
            longitude=longitude,
            **payload,
        )

        TravelWish.objects.filter(id__in=[w.id for w in candidates]).update(visit_record_id=record.tid)

        return Response({
            'record': TravelRecordSerializer(record).data,
            'consolidated_ids': [w.id for w in candidates],
            'count': len(candidates),
        }, status=status.HTTP_201_CREATED)
