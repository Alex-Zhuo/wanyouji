# coding: utf-8
from __future__ import unicode_literals
from django.db import models
from django.utils import timezone
from decimal import Decimal
from express.models import Division
import logging
from django.db import close_old_connections

from ticket.models import SessionInfo, TiktokUser
from django.conf import settings
from django.http import HttpResponse
import xlwt

log = logging.getLogger(__name__)


def export_record(queryset):
    from statistical.admin import _write_row_by_xlwt
    response = HttpResponse(content_type='application/vnd.ms-excel')
    response['Content-Disposition'] = 'attachment; filename="{}.{}.xls"'.format('每日代理销售记录',
                                                                                timezone.now().strftime('%Y%m%d%H%M%S'))
    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet('每日代理销售记录')
    row_index = 1
    _write_row_by_xlwt(ws, [u'演出项目', u'场次开演时间', u'代理', '统计日期', '销售渠道', u'实付金额', u'佣金'], row_index)
    row_index += 1
    for inst in queryset:
        data = [inst['title'], inst['start_at'], inst['agent'],
                inst['date_at'], inst['source_type'],
                inst['total_amount'], inst['commission_amount']]
        _write_row_by_xlwt(ws, data, row_index)
        row_index += 1
    _write_row_by_xlwt(ws, ['END'], row_index)
    wb.save(response)
    return response


def export_cps_record(queryset):
    from statistical.admin import _write_row_by_xlwt
    response = HttpResponse(content_type='application/vnd.ms-excel')
    response['Content-Disposition'] = 'attachment; filename="{}.{}.xls"'.format('每日达人销售记录',
                                                                                timezone.now().strftime('%Y%m%d%H%M%S'))
    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet('每日达人销售记录')
    row_index = 1
    _write_row_by_xlwt(ws, [u'演出项目', u'场次开演时间', u'带货达人', u'平台', u'统计日期', u'销售渠道', u'实付金额', u'佣金'], row_index)
    row_index += 1
    for inst in queryset:
        data = [inst['title'], inst['start_at'], inst['agent'], inst['platform'],
                inst['date_at'], inst['source_type'],
                inst['total_amount'], inst['commission_amount']]
        _write_row_by_xlwt(ws, data, row_index)
        row_index += 1
    _write_row_by_xlwt(ws, ['END'], row_index)
    wb.save(response)
    return response


class TotalStatistical(models.Model):
    user_num = models.IntegerField('总用户数', default=0)
    super_card_num = models.IntegerField('超级会员数', default=0)
    super_amount = models.DecimalField('超级会员卡总收款', max_digits=13, decimal_places=2, default=0)
    super_order_num = models.IntegerField('超级会员卡订单数', default=0)
    super_rest_amount = models.DecimalField('超级会员卡余额', max_digits=13, decimal_places=2, default=0)
    year_card_num = models.IntegerField('VIP会员数', default=0)
    session_num = models.IntegerField('总场次数', default=0)
    dy_amount = models.DecimalField('抖音总票房', max_digits=13, decimal_places=2, default=0)
    wx_amount = models.DecimalField('微信总票房', max_digits=13, decimal_places=2, default=0)
    dy_live_order_num = models.IntegerField('抖音直播间订单数', default=0, help_text='下单渠道数量')
    dy_video_order_num = models.IntegerField('抖音短视频订单数', default=0, help_text='下单渠道数量')
    dy_order_num = models.IntegerField('抖音小程序订单数', default=0, help_text='下单渠道数量')
    wx_order_num = models.IntegerField('微信小程序订单数', default=0, help_text='下单渠道数量')
    refund_num = models.IntegerField('退款订单总数', default=0)
    refund_amount = models.DecimalField('退款总额', max_digits=13, decimal_places=2, default=0)
    agent_num = models.IntegerField('代理人数', default=0)
    withdraw_amount = models.DecimalField('已提现佣金', max_digits=13, decimal_places=2, default=0)
    total_award_amount = models.DecimalField('总佣金', max_digits=13, decimal_places=2, default=0)
    share_award_amount = models.DecimalField('分销奖总数', max_digits=13, decimal_places=2, default=0)
    group_award_amount = models.DecimalField('团队奖总数', max_digits=13, decimal_places=2, default=0)

    class Meta:
        verbose_name_plural = verbose_name = '总数据统计'

    @classmethod
    def get_inst(cls):
        inst = cls.objects.first()
        if not inst:
            inst = cls.objects.create(user_num=0)
        return inst

    @classmethod
    def task_change_data(cls):
        close_old_connections()
        from caches import get_pika_redis, stl_user_num, stl_session_num, stl_agent_num, stl_super_card_num, \
            stl_super_amount, stl_super_order_num, stl_super_rest_amount, stl_year_card_num, stl_dy_amount, \
            stl_wx_amount, stl_dy_live_order_num, stl_dy_video_order_num, stl_dy_order_num, stl_wx_order_num, \
            stl_refund_num, stl_refund_amount, stl_share_award_amount, stl_group_award_amount, stl_withdraw_amount, \
            stl_total_award_amount
        with get_pika_redis() as redis:
            inst = cls.get_inst()
            user_num = redis.get(stl_user_num) or 0
            inst.user_num = int(user_num)
            super_card_num = redis.get(stl_super_card_num) or 0
            inst.super_card_num = int(super_card_num)
            super_amount = redis.get(stl_super_amount) or 0
            inst.super_amount = float(super_amount)
            super_order_num = redis.get(stl_super_order_num) or 0
            inst.super_order_num = int(super_order_num)
            super_rest_amount = redis.get(stl_super_rest_amount) or 0
            inst.super_rest_amount = float(super_rest_amount)
            year_card_num = redis.get(stl_year_card_num) or 0
            inst.year_card_num = int(year_card_num)
            session_num = redis.get(stl_session_num) or 0
            inst.session_num = int(session_num)
            dy_amount = redis.get(stl_dy_amount) or 0
            inst.dy_amount = float(dy_amount)
            wx_amount = redis.get(stl_wx_amount) or 0
            inst.wx_amount = float(wx_amount)
            dy_live_order_num = redis.get(stl_dy_live_order_num) or 0
            inst.dy_live_order_num = int(dy_live_order_num)
            dy_video_order_num = redis.get(stl_dy_video_order_num) or 0
            inst.dy_video_order_num = int(dy_video_order_num)
            dy_order_num = redis.get(stl_dy_order_num) or 0
            inst.dy_order_num = int(dy_order_num)
            wx_order_num = redis.get(stl_wx_order_num) or 0
            inst.wx_order_num = int(wx_order_num)
            refund_num = redis.get(stl_refund_num) or 0
            inst.refund_num = int(refund_num)
            stl_refund_amount = redis.get(stl_refund_amount) or 0
            inst.refund_amount = float(stl_refund_amount)
            agent_num = redis.get(stl_agent_num) or 0
            inst.agent_num = int(agent_num)
            withdraw_amount = redis.get(stl_withdraw_amount) or 0
            inst.withdraw_amount = float(withdraw_amount)
            total_award_amount = redis.get(stl_total_award_amount) or 0
            share_award_amount = redis.get(stl_share_award_amount) or 0
            group_award_amount = redis.get(stl_group_award_amount) or 0
            inst.total_award_amount = float(total_award_amount)
            inst.share_award_amount = float(share_award_amount)
            inst.group_award_amount = float(group_award_amount)
            inst.save(update_fields=[f.name for f in TotalStatistical._meta.fields if f.name not in ['id']])

    @classmethod
    def add_user_num(cls, num=1):
        from caches import get_pika_redis, stl_user_num
        with get_pika_redis() as redis:
            redis.incr(stl_user_num, num)

    @classmethod
    def add_session_num(cls, num=1):
        from caches import get_pika_redis, stl_session_num
        with get_pika_redis() as redis:
            redis.incr(stl_session_num, num)

    @classmethod
    def add_agent_num(cls, num=1):
        from caches import get_pika_redis, stl_agent_num
        with get_pika_redis() as redis:
            redis.incr(stl_agent_num, num)

    @classmethod
    def change_super_card_stl(cls, order_num=0, card_num=0, amount=0, rest_amount=0):
        try:
            from caches import get_pika_redis, stl_super_card_num, stl_super_amount, stl_super_order_num, \
                stl_super_rest_amount
            with get_pika_redis() as redis:
                if card_num != 0:
                    redis.incrbyfloat(stl_super_card_num, card_num)
                if amount != 0:
                    redis.incrbyfloat(stl_super_amount, float(amount))
                if order_num != 0:
                    redis.incrbyfloat(stl_super_order_num, order_num)
                if rest_amount != 0:
                    redis.incrbyfloat(stl_super_rest_amount, float(rest_amount))
        except Exception as e:
            log.error('change_super_card_stl fail')

    @classmethod
    def change_year_card_stl(cls, num=0):
        try:
            from caches import get_pika_redis, stl_year_card_num
            with get_pika_redis() as redis:
                if num != 0:
                    redis.incrbyfloat(stl_year_card_num, num)
        except Exception  as e:
            log.error('change_year_card_stl fail')

    @classmethod
    def change_ticket_order_stl(cls, dy_amount=0, wx_amount=0, dy_live_order_num=0, dy_video_order_num=0,
                                dy_order_num=0, wx_order_num=0):
        try:
            from caches import get_pika_redis, stl_dy_amount, stl_wx_amount, stl_dy_live_order_num, \
                stl_dy_video_order_num, stl_dy_order_num, stl_wx_order_num
            with get_pika_redis() as redis:
                if dy_amount != 0:
                    redis.incrbyfloat(stl_dy_amount, float(dy_amount))
                if wx_amount != 0:
                    redis.incrbyfloat(stl_wx_amount, float(wx_amount))
                if dy_live_order_num != 0:
                    redis.incrbyfloat(stl_dy_live_order_num, dy_live_order_num)
                if dy_video_order_num != 0:
                    redis.incrbyfloat(stl_dy_video_order_num, dy_video_order_num)
                if dy_order_num != 0:
                    redis.incrbyfloat(stl_dy_order_num, dy_order_num)
                if wx_order_num != 0:
                    redis.incrbyfloat(stl_wx_order_num, wx_order_num)
        except Exception as e:
            log.error('change_ticket_order_stl fail')

    @classmethod
    def change_ticket_refund_stl(cls, refund_num=0, refund_amount=0):
        try:
            from caches import get_pika_redis, stl_refund_num, stl_refund_amount
            with get_pika_redis() as redis:
                if refund_num != 0:
                    redis.incrbyfloat(stl_refund_num, refund_num)
                if refund_amount != 0:
                    redis.incrbyfloat(stl_refund_amount, float(refund_amount))
        except Exception  as e:
            log.error('change_ticket_refund_stl fail')

    @classmethod
    def change_award_stl(cls, share_award_amount=0, group_award_amount=0, withdraw_amount=0, total_award_amount=0):
        try:
            from caches import get_pika_redis, stl_share_award_amount, stl_group_award_amount, stl_withdraw_amount, \
                stl_total_award_amount
            with get_pika_redis() as redis:
                if stl_share_award_amount != 0:
                    redis.incrbyfloat(stl_share_award_amount, float(share_award_amount))
                if stl_group_award_amount != 0:
                    redis.incrbyfloat(stl_group_award_amount, float(group_award_amount))
                if withdraw_amount != 0:
                    redis.incrbyfloat(stl_withdraw_amount, float(withdraw_amount))
                if total_award_amount != 0:
                    redis.incrbyfloat(stl_total_award_amount, float(total_award_amount))
        except Exception  as e:
            log.error('change_award_stl fail')


class CityStatistical(models.Model):
    city = models.ForeignKey(Division, verbose_name='城市', on_delete=models.CASCADE,
                             limit_choices_to=models.Q(type=Division.TYPE_CITY), db_index=True)
    order_num = models.IntegerField('订单数', default=0)
    total_amount = models.DecimalField('总实付金额', max_digits=13, decimal_places=2, default=0)

    class Meta:
        verbose_name_plural = verbose_name = '城市数据统计'

    @classmethod
    def get_inst(cls, city):
        inst, _ = cls.objects.get_or_create(city_id=city.id)
        return inst

    @classmethod
    def change_order_sum(cls, city, num, amount):
        inst = cls.get_inst(city)
        from caches import get_pika_redis, city_order_sum
        with get_pika_redis() as redis:
            redis.lpush(city_order_sum, '{}_{}_{}'.format(inst.id, num, float(amount)))

    @classmethod
    def task_add_order_sum(cls):
        close_old_connections()
        from caches import get_pika_redis, city_order_sum
        with get_pika_redis() as redis:
            dd = redis.lindex(city_order_sum, 0)
            total_list = dict()
            i = 0
            while dd and i < 200:
                i += 1
                dd = redis.rpop(city_order_sum)
                id, num, amount = dd.split('_')
                if total_list.get(str(id)):
                    total_list[str(id)]['order_num'] += int(num)
                    total_list[str(id)]['total_amount'] += Decimal(amount)
                else:
                    total_list[str(id)] = dict(order_num=int(num), total_amount=Decimal(amount))
            for key, data in total_list.items():
                self = cls.objects.filter(id=int(key)).first()
                if self:
                    self.order_num += data['order_num']
                    self.total_amount += data['total_amount']
                    self.save(update_fields=['order_num', 'total_amount'])


class DayStatistical(models.Model):
    create_at = models.DateField('日期', db_index=True, unique=True)
    order_num = models.IntegerField('订单数', default=0)
    total_amount = models.DecimalField('总实付金额', max_digits=13, decimal_places=2, default=0)

    class Meta:
        verbose_name_plural = verbose_name = '每日数据统计'
        ordering = ['-create_at']

    def __str__(self):
        return str(self.create_at)

    @classmethod
    def get_inst(cls, create_at=None):
        dd = create_at if create_at else timezone.now().date()
        inst, _ = cls.objects.get_or_create(create_at=dd)
        return inst

    @classmethod
    def change_order_sum(cls, create_at, num, amount):
        inst = cls.get_inst(create_at)
        from caches import get_pika_redis, day_order_sum
        with get_pika_redis() as redis:
            redis.lpush(day_order_sum, '{}_{}_{}'.format(inst.id, num, float(amount)))

    @classmethod
    def task_add_order_sum(cls):
        from caches import get_pika_redis, day_order_sum
        with get_pika_redis() as redis:
            dd = redis.lindex(day_order_sum, 0)
            total_list = dict()
            i = 0
            while dd and i < 200:
                i += 1
                dd = redis.rpop(day_order_sum)
                id, num, amount = dd.split('_')
                if total_list.get(str(id)):
                    total_list[str(id)]['order_num'] += int(num)
                    total_list[str(id)]['total_amount'] += Decimal(amount)
                else:
                    total_list[str(id)] = dict(order_num=int(num), total_amount=Decimal(amount))
            for key, data in total_list.items():
                self = cls.objects.filter(id=int(key)).first()
                if self:
                    self.order_num += data['order_num']
                    self.total_amount += data['total_amount']
                    self.save(update_fields=['order_num', 'total_amount'])


class MonthSales(models.Model):
    year = models.IntegerField('年份')
    month = models.IntegerField('月份')
    order_num = models.IntegerField('订单数', default=0)
    total_amount = models.DecimalField('总票房', max_digits=13, decimal_places=2, default=0)

    class Meta:
        verbose_name_plural = verbose_name = '月度票房统计'
        unique_together = ['year', 'month']

    @classmethod
    def get_inst(cls, create_at=None):
        dd = create_at if create_at else timezone.now().date()
        year = dd.year
        month = dd.month
        inst, _ = cls.objects.get_or_create(year=year, month=month)
        return inst

    @classmethod
    def change_order_sum(cls, create_at, num, amount):
        inst = cls.get_inst(create_at)
        from caches import get_pika_redis, month_order_sum
        with get_pika_redis() as redis:
            redis.lpush(month_order_sum, '{}_{}_{}'.format(inst.id, num, float(amount)))

    @classmethod
    def task_add_order_sum(cls):
        from caches import get_pika_redis, month_order_sum
        with get_pika_redis() as redis:
            dd = redis.lindex(month_order_sum, 0)
            total_list = dict()
            i = 0
            while dd and i < 200:
                i += 1
                dd = redis.rpop(month_order_sum)
                id, num, amount = dd.split('_')
                if total_list.get(str(id)):
                    total_list[str(id)]['order_num'] += int(num)
                    total_list[str(id)]['total_amount'] += Decimal(amount)
                else:
                    total_list[str(id)] = dict(order_num=int(num), total_amount=Decimal(amount))
            for key, data in total_list.items():
                self = cls.objects.filter(id=int(key)).first()
                if self:
                    self.order_num += data['order_num']
                    self.total_amount += data['total_amount']
                    self.save(update_fields=['order_num', 'total_amount'])


class SessionSum(models.Model):
    session = models.ForeignKey(SessionInfo, verbose_name='场次', on_delete=models.CASCADE)
    commission_amount = models.DecimalField('场次总佣金', max_digits=13, decimal_places=2, default=0)

    class Meta:
        verbose_name_plural = verbose_name = '场次销售统计'

    def __str__(self):
        return str(self.session)

    @classmethod
    def get_inst(cls, session):
        inst, _ = cls.objects.get_or_create(session_id=session.id)
        return inst

    def add_commission_amount(self, commission_amount):
        self.commission_amount += commission_amount
        self.save(update_fields=['commission_amount'])


class SessionAgentSum(models.Model):
    record = models.ForeignKey(SessionSum, verbose_name='场次销售统计', on_delete=models.CASCADE)
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='代理', on_delete=models.CASCADE)
    amount = models.DecimalField('实付金额', max_digits=13, decimal_places=2, default=0)
    c_amount = models.DecimalField('佣金', max_digits=13, decimal_places=2, default=0)

    class Meta:
        verbose_name_plural = verbose_name = '代理销售记录'

    def __str__(self):
        return str(self.agent)

    @classmethod
    def change_record(cls, session, amount, c_amount, agent):
        record = SessionSum.get_inst(session)
        inst, create = cls.objects.get_or_create(record=record, agent=agent)
        inst.amount += amount
        inst.c_amount += c_amount
        inst.save(update_fields=['amount', 'c_amount'])
        record.add_commission_amount(c_amount)


class SessionAgentDaySum(models.Model):
    session = models.ForeignKey(SessionInfo, verbose_name='场次', on_delete=models.CASCADE)
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='代理', on_delete=models.CASCADE)
    ST_VIDEO = 1
    ST_LIVE = 2
    ST_DY = 3
    ST_WX = 4
    ST_CHOICES = ((ST_WX, U'微信搜索购买'), (ST_LIVE, U'抖音直播间'), (ST_VIDEO, U'抖音短视频'), (ST_DY, U'抖音搜索购票'))
    source_type = models.IntegerField(u'销售渠道', choices=ST_CHOICES, default=ST_WX)
    amount = models.DecimalField('实付金额', max_digits=13, decimal_places=2, default=0)
    c_amount = models.DecimalField('佣金', max_digits=13, decimal_places=2, default=0)
    create_at = models.DateField('统计日期')

    class Meta:
        verbose_name_plural = verbose_name = '每日代理销售记录'
        ordering = ['-create_at']

    def change_amount(self, amount=0, c_amount=0):
        if amount != 0 or c_amount != 0:
            from caches import get_pika_redis, session_agent_sum_key
            with get_pika_redis() as redis:
                redis.lpush(session_agent_sum_key,
                            '{}_{}_{}'.format(self.id, float(amount), float(c_amount)))

    @classmethod
    def task_add_session_agent_day_sum(cls):
        from caches import get_pika_redis, session_agent_sum_key
        with get_pika_redis() as redis:
            dd = redis.lindex(session_agent_sum_key, 0)
            i = 0
            total_list = dict()
            while dd and i < 200:
                i += 1
                dd = redis.rpop(session_agent_sum_key)
                id, amount, c_amount = dd.split('_')
                if total_list.get(str(id)):
                    total_list[str(id)]['amount'] += Decimal(amount)
                    total_list[str(id)]['c_amount'] += Decimal(c_amount)
                else:
                    total_list[str(id)] = dict(amount=Decimal(amount),
                                               c_amount=Decimal(c_amount))
            for key, data in total_list.items():
                self = cls.objects.filter(id=int(key)).first()
                if self:
                    self.c_amount += data['c_amount']
                    self.amount += data['amount']
                    self.save(update_fields=['c_amount', 'amount'])
                    SessionAgentSum.change_record(self.session, data['amount'], data['c_amount'],
                                                  self.agent)

    @classmethod
    def change_record(cls, session, agent, create_at, source_type, c_amount=0, amount=0):
        if c_amount != 0 or amount != 0:
            try:
                inst, _ = cls.objects.get_or_create(session=session, agent=agent, create_at=create_at,
                                                    source_type=source_type)
                inst.change_amount(amount, c_amount)
            except Exception as e:
                log.error('代理销售统计失败')


class SessionAgentRecord(models.Model):
    class Meta:
        verbose_name_plural = verbose_name = '代理销售查询'


class SessionCpsDaySum(models.Model):
    session = models.ForeignKey(SessionInfo, verbose_name='场次', on_delete=models.CASCADE)
    tiktok_nickname = models.CharField('达人抖音昵称', max_length=50, null=True, blank=True)
    tiktok_douyinid = models.CharField('达人抖音号', max_length=50, null=True, blank=True)
    ST_VIDEO = 1
    ST_LIVE = 2
    ST_CHOICES = ((ST_LIVE, U'直播间'), (ST_VIDEO, U'短视频'))
    source_type = models.IntegerField(u'销售渠道', choices=ST_CHOICES, default=ST_LIVE)
    platform = models.IntegerField('平台', choices=TiktokUser.ST_CHOICES, default=TiktokUser.ST_DY)
    amount = models.DecimalField('实付金额', max_digits=13, decimal_places=2, default=0)
    c_amount = models.DecimalField('佣金', max_digits=13, decimal_places=2, default=0)
    create_at = models.DateField('统计日期')

    class Meta:
        verbose_name_plural = verbose_name = '每日达人销售记录'
        ordering = ['-create_at']

    def change_cps_amount(self, amount=0, c_amount=0):
        if amount != 0 or c_amount != 0:
            from caches import get_pika_redis, session_cps_sum_key
            with get_pika_redis() as redis:
                redis.lpush(session_cps_sum_key,
                            '{}_{}_{}'.format(self.id, float(amount), float(c_amount)))

    @classmethod
    def task_add_session_cps_day_sum(cls):
        from caches import get_pika_redis, session_cps_sum_key
        with get_pika_redis() as redis:
            dd = redis.lindex(session_cps_sum_key, 0)
            total_list = dict()
            i = 0
            while dd and i < 200:
                i += 1
                dd = redis.rpop(session_cps_sum_key)
                id, amount, c_amount = dd.split('_')
                if total_list.get(str(id)):
                    total_list[str(id)]['amount'] += Decimal(amount)
                    total_list[str(id)]['c_amount'] += Decimal(c_amount)
                else:
                    total_list[str(id)] = dict(amount=Decimal(amount),
                                               c_amount=Decimal(c_amount))
            for key, data in total_list.items():
                self = cls.objects.filter(id=int(key)).first()
                if self:
                    self.c_amount += data['c_amount']
                    self.amount += data['amount']
                    self.save(update_fields=['c_amount', 'amount'])

    @classmethod
    def change_cps_record(cls, session, tiktok_douyinid, tiktok_nickname, create_at, source_type, platform, c_amount=0,
                          amount=0):
        if c_amount != 0 or amount != 0:
            try:
                inst, create = cls.objects.get_or_create(session=session, tiktok_douyinid=tiktok_douyinid,
                                                         create_at=create_at,
                                                         platform=platform,
                                                         source_type=source_type)
                if create:
                    inst.tiktok_nickname = tiktok_nickname
                    inst.save(update_fields=['tiktok_nickname'])
                inst.change_cps_amount(amount, c_amount)
            except Exception as e:
                log.error('代理销售统计失败')


class SessionCpsRecord(models.Model):
    class Meta:
        verbose_name_plural = verbose_name = '达人销售查询'
