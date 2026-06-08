"""初始化城市坐标数据 + 为现有记录添加地理编码"""

from django.core.management.base import BaseCommand

from apps.travel.models import ChinaCityCoord, TravelRecord
from apps.travel.services import CITY_COORDS, CITY_TO_PROVINCE, DISTRICT_TO_CITY, get_coordinates


class Command(BaseCommand):
    help = '初始化城市坐标 + 地理编码现有旅行记录'

    def handle(self, *args, **options):
        # 1. 填充城市坐标表
        self.stdout.write('填充城市坐标表...')
        count = 0
        for prov, cities in CITY_COORDS.items():
            for city, (lat, lng) in cities.items():
                ChinaCityCoord.objects.update_or_create(
                    city=city,
                    defaults={
                        'province': prov,
                        'latitude': lat,
                        'longitude': lng,
                        'level': 1 if city == prov.replace('省', '').replace('市', '') else 2,
                    },
                )
                count += 1
        self.stdout.write(self.style.SUCCESS(f'  写入 {count} 条城市坐标'))

        # 2. 为现有旅行记录补全坐标
        self.stdout.write('为旅行记录补全地理编码...')
        updated = 0
        for record in TravelRecord.objects.all():
            lat_lng = None
            # 先查 tname
            if record.tname:
                lat_lng = get_coordinates(record.tname)
            # 再查 parentnode
            if not lat_lng and record.parentnode:
                lat_lng = get_coordinates(record.parentnode)

            if lat_lng:
                record.latitude = lat_lng[0]
                record.longitude = lat_lng[1]
                record.save(update_fields=['latitude', 'longitude'])
                updated += 1

        self.stdout.write(self.style.SUCCESS(f'  更新 {updated} 条记录坐标'))
        self.stdout.write(self.style.SUCCESS('完成！'))
