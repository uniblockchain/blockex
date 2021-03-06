from django.shortcuts import render
from django.db.models import Sum, Count, Avg
from django.core.exceptions import ObjectDoesNotExist
import json

# Create your views here.
from .models import *
from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework.status import HTTP_200_OK
from .serializers import *
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from datetime import datetime, timedelta
from django.utils import timezone
from dateutil import parser
from rest_framework.parsers import JSONParser

import redis
import io

_redis = redis.Redis(host='localhost', port=6379, db=0)

class BlockViewSet(viewsets.ModelViewSet):
    queryset = Block.objects.all().order_by('-height')
    serializer_class = BlockSerializer


@api_view(['GET'])
def get_block_range(request):
    range = int(request.GET['range'])
    graph_data = False

    if range == 1:
        graph_data = _redis.get("daily_graph_data")
    if range == 7:
        graph_data = _redis.get("weekly_graph_data")
    if range == 30:
        graph_data = _redis.get("monthly_graph_data")
    if range == 365:
        graph_data = _redis.get("yearly_graph_data")
    if range == 0:
        graph_data = _redis.get("all_graph_data")

    if graph_data:
        stream = io.BytesIO(graph_data)
        result = JSONParser().parse(stream)
    else:
        latest_block_height = _redis.get('latest_block_height')
        if not latest_block_height:
            latest_block = Block.objects.latest('height')
            latest_block_height = int(latest_block.height)
            _redis.set('latest_block_height', latest_block_height)

        if range > 0:
            from_height = int(latest_block_height) - 4 * 1440
        else:
            from_height = 0
        to_height = int(latest_block_height) + 1

        blocks = Block.objects.filter(height__gte=from_height, height__lt=to_height).order_by('height')

        hour_offset = timedelta(hours=int(1))
        start_date = parser.parse(BlockHeaderSerializer(blocks.first()).data['timestamp'])
        end_date = parser.parse(BlockHeaderSerializer(blocks.last()).data['timestamp'])
        date_with_offset = start_date + hour_offset

        result = {
            'items': [],
            'avg_blocks': 0
        }

        while start_date < end_date:
            offset_blocks = blocks.filter(timestamp__gte=start_date, timestamp__lt=date_with_offset)

            avg_diff = offset_blocks.aggregate(Avg('difficulty'))['difficulty__avg']
            fee = offset_blocks.aggregate(Sum('fee'))['fee__sum']
            fixed = 60
            hashrate = avg_diff / 60
            date = BlockHeaderSerializer(offset_blocks.last()).data['timestamp']
            blocks_count = offset_blocks.count()

            result['items'].append({
                'fee': fee,
                'difficulty': avg_diff,
                'fixed': fixed,
                'hashrate': hashrate,
                'date': date,
                'blocks_count': blocks_count
            })

            start_date = date_with_offset
            date_with_offset += hour_offset

        result['avg_blocks'] = blocks.count() / len(result['items'])

        if range == 1:
            _redis.set('daily_graph_data', JSONRenderer().render(result))
        if range == 7:
            _redis.set('weekly_graph_data', JSONRenderer().render(result))
        if range == 30:
            _redis.set('monthly_graph_data', JSONRenderer().render(result))
        if range == 365:
            _redis.set('yearly_graph_data', JSONRenderer().render(result))
        if range == 0:
            _redis.set('all_graph_data', JSONRenderer().render(result))

    return Response(result, status=HTTP_200_OK)


@api_view(['GET'])
def get_block(request):
    b = Block.objects.get(hash=request.GET['hash'])
    serializer = BlockSerializer(b)
    return Response(serializer.data, status=HTTP_200_OK)


@api_view(['GET'])
def search(request):
    q = request.GET['q']

    if q:
        try:
            b = Block.objects.get(height=q)
        except (ValueError, ObjectDoesNotExist):
            try:
                kernel_by_id = Kernel.objects.get(kernel_id=q)
                serialized_kernel = KernelSerializer(kernel_by_id)
                if serialized_kernel:
                    b = Block.objects.get(id=serialized_kernel.data['block_id'])
            except ObjectDoesNotExist:
                try:
                    b = Block.objects.get(hash=q)
                except ObjectDoesNotExist:
                    return Response({'found': False}, status=HTTP_200_OK)
        serializer = BlockSerializer(b)
        return Response(serializer.data, status=HTTP_200_OK)

    return Response({'found': False}, status=HTTP_200_OK)


@api_view(['GET'])
def get_status(request):
    b = _redis.get('latest_block')

    if b:
        stream = io.BytesIO(b)
        data = JSONParser().parse(stream)
    else:
        b = Block.objects.latest('height')
        serializer = BlockHeaderSerializer(b)
        _redis.set('latest_block', JSONRenderer().render(serializer.data))
        data = serializer.data

    coins_in_circulation_mined = _redis.get('coins_in_circulation_mined')
    if coins_in_circulation_mined:
        data['coins_in_circulation_mined'] = coins_in_circulation_mined
    else:
        te = Block.objects.all().aggregate(Sum('subsidy'))
        coins_in_circulation_mined = int(te['subsidy__sum']) * 10**-8
        _redis.set('coins_in_circulation_mined', coins_in_circulation_mined)
        data['coins_in_circulation_mined'] = coins_in_circulation_mined

    coins_in_circulation_treasury = _redis.get('coins_in_circulation_treasury')
    if not coins_in_circulation_treasury:
        coins_in_circulation_treasury = 0

    data['coins_in_circulation_treasury'] = coins_in_circulation_treasury
    data['total_coins_in_circulation'] = float(coins_in_circulation_mined) + float(coins_in_circulation_treasury)
    data['next_treasury_emission_block_height'] = _redis.get('next_treasury_emission_height')
    data['next_treasury_emission_coin_amount'] = _redis.get('next_treasury_coin_amount')
    data['total_emission'] = _redis.get('total_coins_emission')

    return Response(data, status=HTTP_200_OK)


@api_view(['GET'])
def get_major_block(request):
    access_key = 'E9B60D665A110DD4AAE1D36AF633FF25ED932CFED0413FF005C58A986BA7794A'
    key = request.GET['key']

    if key and key == access_key:
        period = request.GET.get('period')
        blocks = Block.objects.all()
        if period:
            created_at_to = datetime.now(tz=timezone.utc)
            created_at_from = datetime.now(tz=timezone.utc) - timedelta(hours=int(period))
            blocks = blocks.filter(created_at__gte=created_at_from, created_at__lt=created_at_to)

        block = blocks.annotate(summ=Count('outputs', distinct=True) + Count('inputs', distinct=True)
                                     + Count('kernels', distinct=True)).latest('summ')
        serializer = BlockSerializer(block)
        return Response(serializer.data, status=HTTP_200_OK)
    else:
        return Response({'Incorrect access key'}, status=404)


@api_view(['GET'])
def get_coins_in_circulation_mined(request):
    coins_in_circulation = _redis.get('coins_in_circulation_mined')
    if not coins_in_circulation:
        te = Block.objects.all().aggregate(Sum('subsidy'))
        coins_in_circulation = int(te['subsidy__sum']) * 10 ** -8
        _redis.set('coins_in_circulation_mined', coins_in_circulation)
    return Response(json.loads(coins_in_circulation), status=HTTP_200_OK)


@api_view(['GET'])
def get_coins_in_circulation_treasury(request):
    coins_in_circulation_treasury = _redis.get('coins_in_circulation_treasury')
    if not coins_in_circulation_treasury:
        return Response({'Something went wrong'}, status=404)
    return Response(json.loads(coins_in_circulation_treasury), status=HTTP_200_OK)


@api_view(['GET'])
def get_total_coins_in_circulation(request):
    total_coins_in_circulation = _redis.get('total_coins_in_circulation')
    if not total_coins_in_circulation:
        coins_in_circulation_mined = _redis.get('coins_in_circulation_mined')
        if not coins_in_circulation_mined:
            te = Block.objects.all().aggregate(Sum('subsidy'))
            coins_in_circulation_mined = int(te['subsidy__sum']) * 10 ** -8
            _redis.set('coins_in_circulation_mined', coins_in_circulation_mined)
            total_coins_in_circulation = coins_in_circulation_mined
        coins_in_circulation_treasury = _redis.get('coins_in_circulation_treasury')
        if coins_in_circulation_treasury:
            total_coins_in_circulation = float(coins_in_circulation_mined) + float(coins_in_circulation_treasury)

    _redis.set('total_coins_in_circulation', total_coins_in_circulation)
    return Response(float(total_coins_in_circulation), status=HTTP_200_OK)


@api_view(['GET'])
def get_next_treasury_emission_block_height(request):
    next_treasury_emission_height = _redis.get('next_treasury_emission_height')
    if not next_treasury_emission_height:
        return Response({'Something went wrong'}, status=404)
    return Response(json.loads(next_treasury_emission_height), status=HTTP_200_OK)


@api_view(['GET'])
def get_next_treasury_emission_coin_amount(request):
    next_treasury_coin_amount = _redis.get('next_treasury_coin_amount')
    if not next_treasury_coin_amount:
        return Response({'Something went wrong'}, status=404)
    return Response(json.loads(next_treasury_coin_amount), status=HTTP_200_OK)


@api_view(['GET'])
def get_total_emission(request):
    total_coins_emission =_redis.get('total_coins_emission')
    if not total_coins_emission:
        return Response({'Something went wrong'}, status=404)
    return Response(json.loads(total_coins_emission), status=HTTP_200_OK)


@api_view(['GET'])
def get_block_by_kernel(request):
    kernel_id = request.GET['kernel_id']

    if kernel_id:
        try:
            kernel_by_id = Kernel.objects.get(kernel_id=kernel_id)
            serialized_kernel = KernelSerializer(kernel_by_id)
            if serialized_kernel:
                block = Block.objects.get(id=serialized_kernel.data['block_id'])
                serializer = BlockSerializer(block)
                return Response({'block': serializer.data['height']}, status=HTTP_200_OK)
        except ObjectDoesNotExist:
            return Response({'Incorrect kernel id'}, status=404)
    else:
        return Response({'Incorrect kernel id'}, status=404)
