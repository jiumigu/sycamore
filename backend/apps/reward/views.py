from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView

from django.db import models

from .models import GiftList, RewardPool, RewardTransaction
from .serializers import (
    GiftExchangeSerializer,
    GiftListSerializer,
    GiftStatsSerializer,
    RewardPoolSerializer,
    RewardSourceStatsSerializer,
    RewardTransactionSerializer,
)
from .services import RewardPoolService


class RewardPoolView(APIView):
    """奖励池概览"""

    def get(self, request):
        data = RewardPoolService.get_pool()
        serializer = RewardPoolSerializer(data)
        return Response(serializer.data)


class RewardTransactionListView(APIView):
    """奖励流水列表"""

    def get(self, request):
        tx_type = request.query_params.get('type')
        source_type = request.query_params.get('source_type')
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))

        qs = RewardTransaction.objects.all()
        if tx_type:
            qs = qs.filter(transaction_type=tx_type)
        if source_type:
            qs = qs.filter(source_type=source_type)

        total = qs.count()
        offset = (page - 1) * page_size
        items = qs[offset:offset + page_size]

        serializer = RewardTransactionSerializer(items, many=True)
        return Response({
            'items': serializer.data,
            'total': total,
            'page': page,
            'page_size': page_size,
        })

    def post(self, request):
        """手动新增奖励流水"""
        from decimal import Decimal
        amount = Decimal(str(request.data.get('amount', 0)))
        if amount <= 0:
            return Response({'error': '金额必须大于0'}, status=status.HTTP_400_BAD_REQUEST)

        tx = RewardPoolService.add_reward(
            source_id=request.data.get('source_id', 0),
            source_type=request.data.get('source_type', 'manual'),
            amount=amount,
            transaction_type=request.data.get('transaction_type', 'manual_add'),
            description=request.data.get('description', ''),
        )
        serializer = RewardTransactionSerializer(tx)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class RewardTransactionDeleteView(APIView):
    """删除奖励流水——同步扣回奖励池余额"""

    def delete(self, request, pk):
        try:
            tx = RewardTransaction.objects.get(pk=pk)
        except RewardTransaction.DoesNotExist:
            return Response({'error': '流水不存在'}, status=status.HTTP_404_NOT_FOUND)

        # 扣回奖励池余额
        pool = RewardPool.objects.first()
        if pool:
            # 🔴 按流水方向回退：正数只影响「累计获得」，负数只影响「累计提取」。
            #    原写法 `total_earned = total_earned - tx.amount` 对负数流水等于**加** ——
            #    删掉一条 -11350.90 的礼物兑换流水，会让「累计获得」凭空涨一万多；
            #    同时 total_withdrawn 从头到尾没有回退。2026-10-23 实查：
            #    池字段 22,092.00 / 21,395.90，流水实际 12,063.00 / 11,378.00，
            #    且 earned - withdrawn = 696.10 ≠ 余额 685.00（id 1~379 但只剩 360 条 ⇒ 删过 19 条）。
            if tx.amount > 0:
                pool.total_earned = models.F('total_earned') - tx.amount
            else:
                pool.total_withdrawn = models.F('total_withdrawn') - abs(tx.amount)
            pool.balance = models.F('balance') - tx.amount
            pool.save()

        tx.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RewardSourceStatsView(APIView):
    """奖励来源统计"""

    def get(self, request):
        data = RewardPoolService.get_stats_by_source()
        serializer = RewardSourceStatsSerializer(data)
        return Response(serializer.data)


# ────────── 礼物清单 ──────────

class GiftListView(APIView):
    """礼物列表"""

    def get(self, request):
        qs = GiftList.objects.all()
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        category = request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)
        qs = qs.order_by('priority', '-created_at')
        serializer = GiftListSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = GiftListSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        gift = serializer.save()
        RewardPoolService._check_gift_availability()
        result = GiftListSerializer(gift)
        return Response(result.data, status=status.HTTP_201_CREATED)


class GiftDetailView(APIView):
    """礼物详情/更新/删除"""

    def get_object(self, pk):
        try:
            return GiftList.objects.get(pk=pk)
        except GiftList.DoesNotExist:
            return None

    def get(self, request, pk):
        gift = self.get_object(pk)
        if not gift:
            return Response({'error': '礼物不存在'}, status=404)
        serializer = GiftListSerializer(gift)
        return Response(serializer.data)

    def put(self, request, pk):
        gift = self.get_object(pk)
        if not gift:
            return Response({'error': '礼物不存在'}, status=404)
        serializer = GiftListSerializer(gift, data=request.data, partial=False)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        gift = serializer.save()
        RewardPoolService._check_gift_availability()
        result = GiftListSerializer(gift)
        return Response(result.data)

    def patch(self, request, pk):
        gift = self.get_object(pk)
        if not gift:
            return Response({'error': '礼物不存在'}, status=404)
        serializer = GiftListSerializer(gift, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        gift = serializer.save()
        RewardPoolService._check_gift_availability()
        result = GiftListSerializer(gift)
        return Response(result.data)

    def delete(self, request, pk):
        gift = self.get_object(pk)
        if not gift:
            return Response({'error': '礼物不存在'}, status=404)
        gift.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class GiftRedeemView(APIView):
    """兑换礼物"""

    def post(self, request, pk):
        try:
            gift = GiftList.objects.get(pk=pk)
        except GiftList.DoesNotExist:
            return Response({'error': '礼物不存在'}, status=404)

        serializer = GiftExchangeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = RewardPoolService.exchange_gift(
                gift_id=pk,
                actual_reward=serializer.validated_data.get('actual_reward'),
            )
            return Response(result)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class GiftCancelView(APIView):
    """取消礼物（仅允许 pending/waiting 状态）"""

    def post(self, request, pk):
        try:
            gift = GiftList.objects.get(pk=pk)
        except GiftList.DoesNotExist:
            return Response({'error': '礼物不存在'}, status=404)

        if gift.status not in ('pending', 'waiting'):
            return Response({'error': f'当前状态为 {gift.get_status_display()}，不可取消'}, status=400)

        gift.status = 'cancelled'
        gift.save(update_fields=['status'])
        serializer = GiftListSerializer(gift)
        return Response(serializer.data)


class GiftStatsView(APIView):
    """礼物统计"""

    def get(self, request):
        data = RewardPoolService.get_gift_stats()
        serializer = GiftStatsSerializer(data)
        return Response(serializer.data)
