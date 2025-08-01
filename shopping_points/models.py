# coding: utf-8
from __future__ import unicode_literals
import logging
from decimal import Decimal
import pysnooper
from django.conf import settings
from django.db import models
from django.db.models import F, Sum
from django.db.models.aggregates import Max
from django.db.transaction import atomic
from django.utils import timezone
from express.models import Division
from mall.models import User, CardRecord, MembershipCard, MemberCardRecord, TheaterCardOrder
from restframework_ext.exceptions import CustomAPIException
from restframework_ext.models import ReceiptAbstract
from mall.pay_service import get_default_pay_client
from ticket.models import Venues, ShowType

logger = logging.getLogger(__name__)
biz_log = logging.getLogger('biz')

# Create your models here.
NEO = object()


class DateDetailAbstract(models.Model):
    create_at = models.DateTimeField(u'创建时间', auto_now_add=True)
    update_at = models.DateTimeField(u'更新时间', auto_now=True)

    class Meta:
        abstract = True


class UserAccountLevel(models.Model):
    name = models.CharField('名称', max_length=32)
    grade = models.IntegerField('Lv', unique=True, help_text='整数, 比如1, 2, 等级顺序从低到高, 越大级别越高')
    slug = models.CharField('识别标识', max_length=10, null=True, help_text='识别序号(请勿修改)')
    share_ratio = models.DecimalField('分销奖比率', max_digits=13, decimal_places=1, default=0, help_text='70为70%')
    team_ratio = models.DecimalField('团队奖比率', max_digits=13, decimal_places=1, default=0, help_text='70为70%')
    card_ratio = models.DecimalField('会员卡分销奖比率', max_digits=13, decimal_places=1, default=0, help_text='70为70%')
    theater_ratio = models.DecimalField('剧场会员卡分销比率', max_digits=13, decimal_places=1, default=0, help_text='70为70%',editable=False)

    class Meta:
        verbose_name_plural = verbose_name = '代理等级'
        ordering = ['grade']

    def __str__(self):
        return self.name

    def get_index(self):
        query_set = self.__class__.objects.all()
        for index, item in enumerate(query_set):
            if item == self:
                return index + 1

    @classmethod
    def agent_level(cls):
        return cls.objects.filter(is_agent=True)

    @classmethod
    def levels(cls):
        return UserAccountLevel.objects.all()

    @classmethod
    def config_levels(cls, levels):
        for k, v in levels.items():
            cls.objects.filter(pk=k).update(**v)

    slug_fs = 'fs'

    @classmethod
    def fs(cls):
        return cls.objects.filter(slug=cls.slug_fs).first()


class UserAccount(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, verbose_name='用户', related_name='user_account',
                                on_delete=models.CASCADE)
    point_balance = models.DecimalField('积分余额', default=0, max_digits=15, decimal_places=2, editable=False)
    commission_balance = models.DecimalField('佣金余额', default=0, max_digits=15, decimal_places=2)
    total_commission_balance = models.DecimalField('总佣金', default=0, max_digits=15, decimal_places=2)
    UA_DEFAULT = 0
    UA_FANS = 1
    UA_INSPECTOR = 2
    UA_AGENT = 3
    flag = models.SmallIntegerField('会员身份', choices=[(UA_FANS, '粉丝'), (UA_INSPECTOR, '验票员'),
                                                     (UA_AGENT, '代理')], default=UA_FANS)
    MG_DEFAULT = 0
    MG_SALE = 1
    manager = models.SmallIntegerField('改价身份', choices=[(MG_DEFAULT, '无'), (MG_SALE, '销售经理')], default=MG_DEFAULT)
    level = models.ForeignKey(UserAccountLevel, verbose_name='代理等级', null=True, blank=True, on_delete=models.SET_NULL)
    venue = models.ManyToManyField(Venues, verbose_name='场馆', blank=True)
    promote_venue = models.ForeignKey(Venues, verbose_name='运营推广门店', null=True, blank=True,
                                      related_name='promote_venue', on_delete=models.SET_NULL)
    team_starter_account = models.ForeignKey('self', verbose_name='团队初始人账号', related_name='team_members',
                                             null=True, blank=True, editable=False, on_delete=models.SET_NULL)
    inviter = models.ForeignKey('self', verbose_name='邀请人', null=True, help_text='平级邀请时设置，是上级和邀请人的区别',
                                related_name='invites', blank=True, on_delete=models.SET_NULL, editable=False)
    bind_parent_day = models.DateField('绑定上级日期', null=True, blank=True, editable=False)
    version = models.IntegerField('版本', default=0, editable=False)

    class Meta:
        verbose_name = '用户账户'
        verbose_name_plural = verbose_name
        ordering = ['id']

    def __str__(self):
        return '{}({})'.format(str(self.user), self.user.id)

    def clean(self):
        if self.flag in UserAccount.agent_flags() and not self.user.mobile:
            from django.core.exceptions import ValidationError
            raise ValidationError('已绑定手机号的用户才能设置会员身份')

    @classmethod
    def agent_flags(cls):
        # 最新代理人缓存
        return [cls.UA_AGENT, cls.UA_INSPECTOR]

    def can_change_amount(self):
        return self.manager == self.MG_SALE

    def get_discount(self):
        mc = MembershipCard.get()
        if mc:
            inst = CardRecord.objects.filter(user=self.user).first()
            if inst and inst.deadline_at and inst.deadline_at >= timezone.now().date():
                return mc.discount / 100
        return 1

    def is_agent(self):
        return self.flag in UserAccount.agent_flags()

    def commission_stats(self):
        return dict(commission_balance=self.commission_balance, commission_withdraw_sum=self.commission_withdraw_sum(),
                    unsettle=self.get_unsettle())

    def stat_consume_total(self, consume_total):
        """
        :param sales_delta:
        :return:
        """
        UserAccount.objects.filter(pk=self.id, consume_total=self.consume_total).update(
            consume_total=models.F('consume_total') + consume_total)

    def back_consume_total(self, total_sales):
        self.consume_total = self.consume_total - total_sales
        self.save(update_fields=['consume_total'])

    def set_parent_day(self, date):
        self.bind_parent_day = date
        self.save(update_fields=['bind_parent_day'])

    def can_withdraw(self, amount):
        useraccount = self
        if not useraccount.level:
            raise CustomAPIException('您没有提现资格')
        from mp.models import BasicConfig
        bc = BasicConfig.get()
        # if useraccount.commission_balance < useraccount.level.balance_floor:
        #     raise CustomAPIException('余额需满%s才可提现' % useraccount.level.balance_floor)
        if amount is not None:
            amount = Decimal(amount).quantize(Decimal('0.0'))
        else:
            # 最大可提额
            amount = useraccount.commission_balance

        if bc:
            if amount < Decimal(bc.withdraw_min):
                raise CustomAPIException('提现金额需大于提现额{}'.format(bc.withdraw_min))
        # withdraw_fees_ratio = bc.withdraw_fees_ratio if bc else 0
        withdraw_fees_ratio = 0
        if withdraw_fees_ratio > 0:
            total = (amount * (Decimal('1.0') + withdraw_fees_ratio)).quantize(Decimal('0.0'))
            if total > useraccount.commission_balance:
                total = useraccount.commission_balance
                actual = (total / (Decimal('1.0') + withdraw_fees_ratio)).quantize(Decimal('0.0'))
                fee = total - actual
            else:
                actual = amount
                fee = (amount * withdraw_fees_ratio).quantize(Decimal('0.0'))
        else:
            actual = total = amount
            fee = 0
        return total, actual, fee

    def level_name(self):
        return self.level.name if self.level else '顾客'

    @classmethod
    def get_max_seq(cls, starter):
        max_seq = cls.objects.filter(team_starter_account=starter).aggregate(Max('team_card_number')).popitem()[1] or 0
        return max_seq + 1

    def is_top_level(self):
        if not self.level:
            return False
        return True if self.level.grade == UserAccountLevel.objects.all().aggregate(Max('grade')).popitem()[1] \
            else False

    @classmethod
    @atomic
    def create(cls, user):
        account = cls.objects.create(user=user)
        if user.parent:
            account.team_starter_account = user.parent.user_account.team_starter_account
        else:
            account.team_starter_account = account
        account.save(update_fields=['team_starter_account'])
        return account

    def update_point_balance(self, amount, secure=True):
        """
        扣除积分余额
        :param amount:
        :param secure:
        :return:
        """
        self.refresh_from_db(fields=['point_balance', 'version'])
        if secure:
            if self.__class__.objects.filter(version=self.version,
                                             pk=self.pk, point_balance__gte=-amount).update(version=F('version') + 1,
                                                                                            point_balance=F(
                                                                                                'point_balance') + amount) <= 0:
                raise CustomAPIException('积分余额不足')
        else:
            if self.__class__.objects.filter(version=self.version,
                                             pk=self.pk).update(version=F('version') + 1,
                                                                point_balance=F(
                                                                    'point_balance') + amount) <= 0:
                raise CustomAPIException('更新积分失败')
        self.refresh_from_db(fields=['point_balance', 'version'])

    def update_commission_balance_withdraw(self, amount):
        self.refresh_from_db(fields=['commission_balance', 'version'])
        if self.__class__.objects.filter(version=self.version,
                                         pk=self.pk, commission_balance__gte=-amount).update(
            version=F('version') + 1,
            commission_balance=F(
                'commission_balance') + amount) <= 0:
            raise CustomAPIException('余额不足或更新错误')
        self.del_account_cache()

    def del_account_cache(self):
        from caches import account_info_cache_key
        from django.core.cache import cache
        key = account_info_cache_key.format(self.user_id)
        cache.delete(key)

    def get_commission_balance_val(self, amount, show_type=None, add_total_commission=True):
        now = timezone.now()
        return '{}_{}_{}_{}_{}_{}_{}'.format(now.year, now.month, now.day, self.id, show_type.id if show_type else 0,
                                             float(amount),
                                             1 if add_total_commission else 2)

    def update_commission_balance(self, amount, show_type=None, add_total_commission=True):
        """
        更改销量
        """
        from caches import get_redis, commission_balance_key
        redis = get_redis()
        val = self.get_commission_balance_val(amount, show_type, add_total_commission)
        redis.lpush(commission_balance_key, val)

    @classmethod
    def task_add_commission_balance(cls):
        from caches import get_redis, commission_balance_key
        redis = get_redis()
        amount_list = redis.lrange(commission_balance_key, 0, -1)
        if amount_list:
            data_dict = dict()
            total_commission_dict = dict()
            for value in amount_list:
                val = redis.rpop(commission_balance_key)
                if val:
                    year, month, day, account_id, show_type_id, amount, add_total_commission = val.split('_')
                    key = str(account_id)
                    if data_dict.get(key):
                        data_dict[key] += float(amount)
                    else:
                        data_dict[key] = float(amount)
                    if int(add_total_commission) == 1:
                        total_key = '{}_{}_{}_{}'.format(year, month, account_id, show_type_id)
                        if total_commission_dict.get(total_key):
                            total_commission_dict[total_key] += float(amount)
                        else:
                            total_commission_dict[total_key] = float(amount)
            if data_dict:
                for key, value in data_dict.items():
                    account_id = int(key)
                    account = cls.objects.filter(id=int(account_id)).first()
                    if account:
                        account.commission_balance += Decimal(value)
                        account.total_commission_balance += Decimal(value)
                        account.save(update_fields=['commission_balance', 'total_commission_balance'])
            if total_commission_dict:
                for key, value in total_commission_dict.items():
                    year, month, account_id, show_type_id = key.split('_')
                    show_type = None
                    if show_type_id:
                        show_type = ShowType.objects.filter(id=int(show_type_id)).first()
                    umr = UserCommissionMonthRecord.get_inst(int(account_id), show_type, int(year), int(month))
                    umr.amount += Decimal(value)
                    umr.save(update_fields=['amount'])

    def get_unsettle(self):
        return UserCommissionChangeRecord.objects.filter(account=self,
                                                         status=UserCommissionChangeRecord.STATUS_UNSETTLE).aggregate(
            sum=Sum('amount'))['sum'] or Decimal('0.0')  # .to_eng_string()

    def commission_withdraw_sum(self):
        return self.commissionwithdraw_set.filter().aggregate(total=Sum('amount'))['total'] or 0

    def point_withdraw_sum(self):
        return self.pointwithdraw_set.filter(
            status=PointWithdraw.STAT_APPROVED).aggregate(total=Sum('amount'))['total'] or 0

    def get_award_amount(self):
        return UserCommissionChangeRecord.objects.filter(
            account=self,
            status=UserCommissionChangeRecord.STATUS_CAN_WITHDRAW).aggregate(total=Sum('amount'))['total'] or 0

    def get_direct_nums(self, require_level):
        return UserAccount.objects.filter(user__parent=self.user, level__grade__gte=require_level.grade).count()

    def get_correct_level(self):
        for level in UserAccountLevel.objects.order_by('-grade'):
            if level.upgrade_check(self):
                return level

    def refresh_level(self):
        level = self.get_correct_level()
        old = self.level
        self.level = level
        self.save(update_fields=['level'])
        if old != level:
            if self.user.parent:
                self.user.parent.user_account.refresh_level()

    @classmethod
    def find_high_level_ancestor(cls, account, level):
        """
        从查找account开始找级别大于level的用户账户
        :param account:
        :param level:
        :return:
        """

        def callback(current, _):
            current = current.user_account
            if current.level.grade > level.grade:
                return False, current
            else:
                # 继续查找下一个
                return True, None

        return account.user.secure_iterate_parents(callback)

    def withdraw_receipt_account(self):
        return ';'.join([ac.show() for ac in self.receipt_accounts.all()])

    def set_level(self, level):
        self.level = level
        self.save(update_fields=['level'])


class ChangeAddAbstract(DateDetailAbstract):
    account = models.ForeignKey(UserAccount, verbose_name='用户账户', null=True, on_delete=models.SET_NULL)
    amount = models.DecimalField('金额', default=0, max_digits=15, decimal_places=2)
    desc = models.CharField('描述', max_length=200, null=True, blank=True)
    extra_info = models.CharField('额外信息', max_length=200, null=True, blank=True, editable=False)

    def __str__(self):
        return '{}: {}'.format(self.account, self.amount)

    class Meta:
        abstract = True

    def update_balance(self):
        raise NotImplementedError()


class UserPointChangeRecord(ChangeAddAbstract):
    SOURCE_TYPE_CONSUME_AWARD = 0
    SOURCE_TYPE_CONSUME = 6
    SOURCE_TYPE_SIGN = 7
    SOURCE_TYPE_BACK = 8
    SOURCE_TYPE_CHOICES = ((SOURCE_TYPE_CONSUME_AWARD, '分销奖'), (SOURCE_TYPE_CONSUME, '消费'), (SOURCE_TYPE_SIGN, '签到赠送'),
                           (SOURCE_TYPE_BACK, '返还'))
    source_type = models.IntegerField(choices=SOURCE_TYPE_CHOICES, verbose_name='类型', default=SOURCE_TYPE_CONSUME_AWARD)
    amount = models.DecimalField('积分', default=0, max_digits=15, decimal_places=2)
    account = models.ForeignKey(UserAccount, verbose_name='用户账户', null=True, related_name='points',
                                on_delete=models.SET_NULL)
    STATUS_UNSETTLE = 3
    STATUS_CAN_WITHDRAW = 1
    STATUS_INVALID = 2
    STATUS_CHOICES = (
        (STATUS_UNSETTLE, u'未结算'), (STATUS_CAN_WITHDRAW, '已结算'), (STATUS_INVALID, '无效'))
    status = models.IntegerField(u'状态', choices=STATUS_CHOICES, default=STATUS_UNSETTLE)
    create_at = models.DateTimeField(u'创建时间', auto_now_add=True, editable=True)
    desc = models.CharField('描述', max_length=200, null=True, blank=True)

    class Meta:
        verbose_name = '积分明细'
        verbose_name_plural = verbose_name

    @classmethod
    def set_status(cls, status, order):
        if status == cls.STATUS_CAN_WITHDRAW:
            qs = cls.objects.filter(order=order, status=cls.STATUS_UNSETTLE)
            for record in qs:
                record.status = cls.STATUS_CAN_WITHDRAW
                record.save(update_fields=['status'])
                if record.amount > 0:
                    record.account.update_point_balance(record.amount)
        elif status == cls.STATUS_INVALID:
            qs = cls.objects.filter(order=order, status=cls.STATUS_UNSETTLE)
            qs.update(status=cls.STATUS_INVALID)
            # for record in qs:
            #     record.status = cls.STATUS_INVALID
            #     record.save(update_fields=['status'])

    @classmethod
    @atomic
    def transfer(cls, source, to, amount):
        """
        转赠消费金
        :param source:
        :param to:
        :param amount:
        :return:
        """
        o = cls.objects.create(account=source, amount=-amount, source_type=cls.SOURCE_TYPE_CONSUME_AWARD,
                               desc=u'我转给%s' % to.user.last_name or to.user.first_name)

        source.update_point_balance(-amount, True)
        cls.objects.create(account=to, amount=amount, source_type=cls.SOURCE_TYPE_CONSUME_AWARD,
                           desc=u'%s转给我' % source.user.last_name or source.user.first_name)
        to.update_point_balance(amount, True)
        return o

    def update_balance(self):
        self.account.update_point_balance(self.amount)

    @classmethod
    def add_record(cls, account, amount, source_type, desc, status, extra_info=None):
        """
        :param source_type:
        :param amount:
        :param desc:
        :return:
        """
        inst = cls.objects.create(account=account, source_type=source_type, amount=amount, desc=desc,
                                  extra_info=extra_info, status=status)
        if status == cls.STATUS_CAN_WITHDRAW:
            inst.update_balance()


class WithdrawAbstract(models.Model):
    PAY_TYPE_BANK = 1
    PAY_TYPE_COMPANY = 2
    PAY_TYPE_OFFLINE = 3
    PAY_TYPE_CHOICES = ((PAY_TYPE_OFFLINE, '线下打款'),)
    account = models.ForeignKey(UserAccount, verbose_name='用户账户', on_delete=models.CASCADE)
    amount = models.DecimalField('金额', max_digits=13, decimal_places=1, default=0)
    pay_type = models.IntegerField('支付方式', choices=PAY_TYPE_CHOICES, default=PAY_TYPE_OFFLINE)
    create_at = models.DateTimeField(u'申请时间', auto_now_add=True)
    approve_at = models.DateTimeField(u'提现时间', null=True)
    reject_at = models.DateTimeField(u'拒绝时间', null=True, blank=True)
    STAT_SUBMIT = 0
    STAT_APPROVED = 1
    STAT_REJECT = 2
    status = models.SmallIntegerField('状态',
                                      choices=[(STAT_SUBMIT, '提现中'), (STAT_APPROVED, '已提现'), (STAT_REJECT, '已拒绝')],
                                      default=STAT_SUBMIT)
    balance = models.DecimalField('提现后余额', max_digits=13, decimal_places=1, default=0)
    trade_no = models.CharField('交易单号', null=True, blank=True, default=None, max_length=64)
    fees = models.DecimalField('手续费', max_digits=13, decimal_places=2, default=0)
    remark = models.TextField('备注', null=True, blank=True)

    class Meta:
        ordering = ['-create_at']
        abstract = True

    def approve(self):
        raise NotImplementedError()

    def __str__(self):
        return '{}'.format(self.account)


class WithdrawActionMixin(object):
    @classmethod
    def deduction_balance(cls, account, amount):
        raise NotImplementedError()

    @classmethod
    @atomic
    def create(cls, account, amount, fees=0):
        try:
            balance = cls.deduction_balance(account, amount + fees)
            return cls.objects.create(amount=amount, account=account, balance=balance, fees=fees)
        except Exception as e:
            logger.error(e)
            raise CustomAPIException('提现错误')


class CommissionWithdraw(WithdrawAbstract, WithdrawActionMixin):
    @classmethod
    def deduction_balance(cls, account, amount):
        if amount <= 0:
            raise CustomAPIException('提现金额不能小于0')
        account.update_commission_balance_withdraw(-amount)
        account.refresh_from_db(fields=['commission_balance'])
        return account.commission_balance

    class Meta(WithdrawAbstract.Meta):
        verbose_name = verbose_name_plural = '佣金提现记录'

    @atomic
    def approve(self):
        if self.status == self.STAT_APPROVED or self.trade_no:
            return
        if self.pay_type == self.PAY_TYPE_BANK:
            receipt_account = ReceiptAccount.objects.filter(account=self.account,
                                                            account_type=ReceiptAccount.TYPE_BANK).first()
            if not receipt_account:
                return
            if receipt_account.bank_code and receipt_account.account_name and receipt_account.account_no:
                res = get_default_pay_client().transfer_to_bank(amount=self.amount, bank_no=receipt_account.account_no,
                                                                true_name=receipt_account.account_name,
                                                                bank_code=receipt_account.bank_code, desc='佣金提现打款',
                                                                partner_trade_no=None)
                if res.get('return_code') == 'SUCCESS' and res.get('result_code') == 'SUCCESS':
                    self.trade_no = res.get('partner_trade_no')
                    self.status = self.STAT_APPROVED
                    self.save(update_fields=['status', 'trade_no'])
        elif self.pay_type == self.PAY_TYPE_COMPANY:
            result = get_default_pay_client().transfer_pay(self.account.user.openid, self.amount, self.id, '佣金提现打款')
            return_code = result.get('return_code')
            result_code = result.get('result_code')
            wx_pay_no = result.get('payment_no', None)
            if result_code == return_code == 'SUCCESS':
                self.status = self.STAT_APPROVED
                self.trade_no = wx_pay_no
                self.save(update_fields=['status', 'trade_no'])


class UserCommissionMonthRecord(models.Model):
    account = models.ForeignKey(UserAccount, verbose_name='用户账户', on_delete=models.CASCADE)
    STATUS_UNSETTLE = 0
    STATUS_CAN_WITHDRAW = 1
    STATUS_INVALID = 3
    STATUS_CHOICES = ((STATUS_UNSETTLE, u'未结算'), (STATUS_CAN_WITHDRAW, '已发放'), (STATUS_INVALID, '无效'))
    status = models.IntegerField(u'状态', choices=STATUS_CHOICES, default=STATUS_UNSETTLE, editable=False)
    show_type = models.ForeignKey(ShowType, verbose_name='节目分类', on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField('金额', default=0, max_digits=15, decimal_places=2)
    year = models.PositiveIntegerField('年份')
    month = models.PositiveIntegerField('月份')

    class Meta:
        verbose_name = '佣金月度记录'
        verbose_name_plural = verbose_name
        # unique_together = ['account', 'year', 'month']
        ordering = ['-year', '-month', '-amount']

    def __str__(self):
        return str(self.account)

    @classmethod
    def get_inst(cls, account_id, show_type=None, year=0, month=0):
        if not year:
            year = timezone.now().year
        if not month:
            month = timezone.now().month
        inst, _ = cls.objects.get_or_create(account_id=account_id, year=year, month=month, show_type=show_type)
        return inst


class UserCommissionChangeRecord(ChangeAddAbstract):
    SOURCE_TYPE_SHARE_AWARD = 1
    SOURCE_TYPE_GROUP = 2
    SOURCE_TYPE_REFUND = 3
    SOURCE_TYPE_CARD = 4
    SOURCE_TYPE_THEATER_CARD = 5
    SOURCE_TYPE_CHOICES = (
        (SOURCE_TYPE_SHARE_AWARD, '分销奖'), (SOURCE_TYPE_GROUP, '团队奖'), (SOURCE_TYPE_REFUND, '退款扣除'),
        (SOURCE_TYPE_CARD, '会员卡销售'))
    source_type = models.IntegerField(choices=SOURCE_TYPE_CHOICES, verbose_name='类型', default=SOURCE_TYPE_SHARE_AWARD)
    STATUS_UNSETTLE = 0
    STATUS_CAN_WITHDRAW = 1
    STATUS_INVALID = 3
    STATUS_USE = 4
    STATUS_CHOICES = (
        (STATUS_UNSETTLE, u'未结算'), (STATUS_CAN_WITHDRAW, '已结算'), (STATUS_INVALID, '无效'))
    status = models.IntegerField(u'状态', choices=STATUS_CHOICES, default=STATUS_UNSETTLE)
    order = models.ForeignKey('ticket.TicketOrder', verbose_name='订单', null=True, blank=True, related_name='com_order',
                              on_delete=models.SET_NULL)
    card_order = models.ForeignKey(MemberCardRecord, verbose_name='会员卡购买记录', null=True, blank=True,
                                   related_name='card_order', on_delete=models.SET_NULL)
    theater_order = models.ForeignKey(TheaterCardOrder, verbose_name='剧场会员卡订单', null=True, blank=True,
                                      on_delete=models.SET_NULL)
    account = models.ForeignKey(UserAccount, verbose_name='用户账户', null=True, related_name='com_account',
                                on_delete=models.SET_NULL)
    show_type = models.ForeignKey(ShowType, verbose_name='节目分类', on_delete=models.SET_NULL, null=True, blank=True)
    create_at = models.DateTimeField(u'创建时间', auto_now_add=True, editable=True)

    class Meta:
        verbose_name = '佣金明细'
        verbose_name_plural = verbose_name
        ordering = ['-pk']

    def settle(self):
        self.status = UserCommissionChangeRecord.STATUS_CAN_WITHDRAW
        self.save(update_fields=['status'])
        self.secure_update_balance()

    @classmethod
    def record_to_balance_source_types(cls):
        """
        返回需要计入佣金余额的奖励类型
        :return:
        """
        return [cls.SOURCE_TYPE_GROUP, cls.SOURCE_TYPE_SHARE_AWARD]

    def update_balance(self):
        self.account.update_commission_balance(self.amount, show_type=self.show_type)

    def secure_update_balance(self):
        """
        入账,当状态不是可提现时,不入
        :return:
        """
        if self.status == self.STATUS_CAN_WITHDRAW:
            self.account.update_commission_balance(self.amount, show_type=self.show_type)
        return self

    @classmethod
    def award_source_type(cls):
        return [cls.SOURCE_TYPE_GROUP, cls.SOURCE_TYPE_SHARE_AWARD, cls.SOURCE_TYPE_CARD, cls.SOURCE_TYPE_THEATER_CARD]

    @classmethod
    @atomic
    def add_record(cls, account, amount, source_type, desc, status=STATUS_UNSETTLE, order=None, extra_info=None,
                   card_order=None, refund_source_type=None, **kwargs):
        """
        增加记录
        :param order:
        :param source_type:
        :param account:
        :param amount:
        :param desc:
        :return:
        """
        show_type = None
        if order and order.session and order.session.show and order.session.show.show_type:
            show_type = order.session.show.show_type
        from common.utils import quantize
        amount = quantize(amount, 2)
        r = cls.objects.create(source_type=source_type, amount=amount, account=account, desc=desc, order=order,
                               mobile=account.user.mobile,
                               extra_info=extra_info, status=status, show_type=show_type, card_order=card_order,
                               **kwargs)
        if status == cls.STATUS_CAN_WITHDRAW:
            r.update_balance()
            from statistical.models import TotalStatistical
            if refund_source_type:
                type = refund_source_type
                amount = -amount
            else:
                type = source_type
            share_award_amount = 0
            group_award_amount = 0
            total_award_amount = 0
            if type == cls.SOURCE_TYPE_SHARE_AWARD:
                share_award_amount = amount
            elif type == cls.SOURCE_TYPE_GROUP:
                group_award_amount = amount
            if source_type in cls.award_source_type():
                # 增加或减少
                total_award_amount = amount
            TotalStatistical.change_award_stl(share_award_amount=share_award_amount,
                                              group_award_amount=group_award_amount,
                                              total_award_amount=total_award_amount)
        return r


class PointWithdraw(WithdrawAbstract, WithdrawActionMixin):
    @classmethod
    def deduction_balance(cls, account, amount):
        account.update_point_balance(-amount)
        account.refresh_from_db(fields=['point_balance'])
        return account.point_balance

    amount = models.DecimalField('积分', max_digits=13, decimal_places=1, default=0)
    STAT_SUBMIT = 0
    STAT_APPROVED = 1
    status = models.SmallIntegerField('状态', choices=[(STAT_SUBMIT, '回购中'), (STAT_APPROVED, '已回购')], default=STAT_SUBMIT)

    class Meta(WithdrawAbstract.Meta):
        verbose_name = verbose_name_plural = '积分提现'

    def approve(self):
        if self.status == self.STAT_APPROVED:
            return
        self.status = self.STAT_APPROVED
        self.save(update_fields=['status'])


class ReceiptAccount(DateDetailAbstract):
    TYPE_BANK = 0
    TYPE_ALIPAY = 1
    TYPE_CHOICES = ((TYPE_BANK, '银行'), (TYPE_ALIPAY, '支付宝'))
    account_type = models.IntegerField(verbose_name='账户类型', choices=TYPE_CHOICES, default=TYPE_BANK)
    account = models.ForeignKey(UserAccount, verbose_name='用户账户', related_name='receipt_accounts', null=True,
                                on_delete=models.SET_NULL)
    account_name = models.CharField('开户人', max_length=30)
    account_no = models.CharField('账户号码', max_length=50)
    bank_name = models.CharField('银行名称', max_length=100, null=True, blank=True)
    bank_code = models.CharField('银行编号', max_length=10, null=True, blank=True)

    class Meta:
        verbose_name = '用户收款账号'
        verbose_name_plural = verbose_name

    def __str__(self):
        return '{}, {}'.format(self.account, self.account_no)

    def show(self):
        """
        显示账户
        :return:
        """
        return '%s, %s, %s' % (self.get_account_type_display(), self.account_no, self.account_name)


class TransferBalanceRecord(DateDetailAbstract):
    amount = models.DecimalField('金额', max_digits=13, decimal_places=1, default=0)
    source = models.ForeignKey(UserAccount, verbose_name='转赠人', on_delete=models.CASCADE)
    to = models.ForeignKey(UserAccount, verbose_name='受赠人', null=True, blank=True, related_name='in_trans',
                           on_delete=models.SET_NULL)
    STAT_UNCONFIRMED = 0
    STAT_CONFIRMED = 1
    STAT_CHOICES = [(STAT_UNCONFIRMED, '待确认'), (STAT_CONFIRMED, '已确认')]
    status = models.SmallIntegerField('状态', choices=STAT_CHOICES, default=STAT_UNCONFIRMED)
    remark = models.CharField('备注', max_length=30, null=True, blank=True)
    confirm_at = models.DateTimeField('确认于', null=True, blank=True)

    class Meta:
        verbose_name_plural = verbose_name = '转赠记录'
        ordering = ['-id']

    @classmethod
    @atomic
    def create(cls, amount, source, to):
        """
        创建转赠记录
        :param amount:
        :param source:
        :param to:
        :return:
        """
        source.update_commission_balance(-amount)
        if to:
            to.update_commission_balance(amount)
        return cls.objects.create(source=source, to=to, amount=amount)

    def confirm(self):
        self.status = self.STAT_CONFIRMED
        self.save(update_fields=['status'])
