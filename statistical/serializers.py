# -*- coding: utf-8 -*-

from rest_framework import serializers

from statistical.models import TotalStatistical, CityStatistical, MonthSales, DayStatistical
from datetime import timedelta
from django.utils import timezone

from ticket.models import SessionInfo
from ticket.serializers import PKtoNoSerializer


class CityStatisticalSerializer(serializers.ModelSerializer):
    city_name = serializers.SerializerMethodField()

    def get_city_name(self, obj):
        return obj.city.city

    class Meta:
        model = CityStatistical
        fields = ['city_name', 'order_num', 'total_amount']


class MonthSalesSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonthSales
        fields = ['year', 'month', 'order_num', 'total_amount']


class DayStatisticalSerializer(serializers.ModelSerializer):
    class Meta:
        model = DayStatistical
        fields = ['create_at', 'order_num', 'total_amount']


class TotalStatisticalSerializer(serializers.ModelSerializer):
    city_data = serializers.SerializerMethodField()
    month_data = serializers.SerializerMethodField()
    day_data = serializers.SerializerMethodField()
    other_data = serializers.SerializerMethodField()

    def get_city_data(self, obj):
        qs = CityStatistical.objects.filter(order_num__gt=0).order_by('-order_num')[:7]
        data = CityStatisticalSerializer(qs, many=True).data
        return data

    def get_month_data(self, obj):
        qs = MonthSales.objects.filter(order_num__gt=0).order_by('-year', '-month')[:6]
        data = MonthSalesSerializer(qs, many=True).data
        return data

    def get_day_data(self, obj):
        qs = DayStatistical.objects.filter(order_num__gt=0)[:7]
        data = DayStatisticalSerializer(qs, many=True).data
        return data

    def get_other_data(self, obj):
        data = dict(week_session_num=0, month_session_num=0, total_amount=obj.dy_amount + obj.wx_amount,
                    un_withdraw_amount=obj.total_award_amount - obj.withdraw_amount)
        from ticket.models import SessionInfo
        from common.qrutils import get_current_week
        from common.dateutils import get_month_day
        monday = get_current_week()
        end_date = monday + timedelta(days=7)
        now = timezone.now()
        start_at, end_at = get_month_day(now.year, now.month, 1)
        data['week_session_num'] = SessionInfo.objects.filter(start_at__gte=monday, start_at__lt=end_date,
                                                              is_delete=False).count()
        data['month_session_num'] = SessionInfo.objects.filter(start_at__gte=start_at, start_at__lt=end_at,
                                                               is_delete=False).count()

        return data

    class Meta:
        model = TotalStatistical
        fields = '__all__'

# 后台用的不用改no
class SessionSearchListSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()

    def get_title(self, obj):
        return str(obj.show)

    class Meta:
        model = SessionInfo
        fields = ['id', 'no', 'title', 'start_at']
