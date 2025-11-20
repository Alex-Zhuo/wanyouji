# coding=utf-8
from django.core.validators import validate_image_file_extension, FileExtensionValidator
from django.db import models

from common.config import IMAGE_FIELD_PREFIX, FILE_FIELD_PREFIX
from mp.models import WeiXinPayConfig
from restframework_ext.models import UseShortNoAbstract, ReceiptAbstract
from django.utils import timezone
from random import sample
from django.conf import settings
import simplejson as json
import logging
from django.core.exceptions import ValidationError
from restframework_ext.exceptions import CustomAPIException
from django.db import close_old_connections
from django.db.transaction import atomic
from caches import get_redis_name, run_with_lock
from django.db.models import F
from datetime import timedelta
from typing import List, Optional
from blind_box.stock_updater import prsc, StockModel

SR_COUPON = 1
SR_TICKET = 2
SR_CODE = 3
SR_GOOD = 4
PRIZE_SOURCE_TYPE_CHOICES = ((SR_COUPON, '消费券'), (SR_TICKET, '纸质票'), (SR_CODE, '券码'), (SR_GOOD, '实物奖品'))
notify_url = '/api/lottery/receipt/notify/'
refund_notify_url = '/api/lottery/receipt/refund_notify/'

log = logging.getLogger(__name__)


def cancel_minutes_limit(value):
    if value < 5:
        raise ValidationError("必须大于等于5分钟")
    else:
        return value


def price_his_no(tail_length=3):
    """
    使用当前时间(datetime)生成随机字符串,可以作为订单号
    :return:
    """
    now = timezone.now()
    return '%s%s' % (now.strftime('%Y%m%d%H%M%S%f'), ''.join(sample(list(map(str, range(0, 10))), tail_length)))


def blind_refund_no(tail_length=3):
    """
    使用当前时间(datetime)生成随机字符串,可以作为订单号
    :return:
    """
    now = timezone.now()
    return 'BR%s%s' % (now.strftime('%Y%m%d%H%M%S%f'), ''.join(sample(list(map(str, range(0, 10))), tail_length)))


class BlindBasic(models.Model):
    price_per_lottery = models.DecimalField('一次抽奖机会价格', max_digits=13, decimal_places=2)
    auto_cancel_minutes = models.PositiveSmallIntegerField('自动取消盲盒订单分钟数', default=10,
                                                           help_text='订单创建时间开始多少分钟后未支付自动取消订单',
                                                           validators=[cancel_minutes_limit])
    box_rule = models.TextField('盲盒规则', max_length=2000, null=True)
    wheel_rule = models.TextField('转盘规则', max_length=2000, null=True)

    class Meta:
        verbose_name_plural = verbose_name = '盲盒转盘配置'

    @classmethod
    def get(cls):
        return cls.objects.first()


class BlindReceipt(ReceiptAbstract):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=u'用户', null=True, on_delete=models.SET_NULL)
    BIZ_BLIND = 1
    BIZ_LOTTERY = 2
    BIZ_CHOICES = [(BIZ_BLIND, '盲盒订单'), (BIZ_LOTTERY, '转盘订单')]
    biz = models.SmallIntegerField('业务类型', default=BIZ_BLIND, choices=BIZ_CHOICES)
    attachment = models.TextField('附加数据', null=True, blank=True, help_text='请勿修改此字段')
    wx_pay_config = models.ForeignKey(WeiXinPayConfig, verbose_name='微信支付', blank=True, null=True,
                                      on_delete=models.SET_NULL)
    pay_end_at = models.DateTimeField('支付截止时间', null=True)

    class Meta:
        ordering = ['-pk']
        verbose_name = verbose_name_plural = '支付记录'

    def __str__(self):
        return f"{str(self.user)} - {self.amount}元"

    @classmethod
    def create_record(cls, amount, user, pay_type, biz, wx_pay_config=None, pay_end_at=None):
        return cls.objects.create(amount=amount, user=user, pay_type=pay_type, biz=biz, wx_pay_config=wx_pay_config,
                                  pay_end_at=pay_end_at)

    def get_notify_url(self):
        return notify_url

    @property
    def pay_client(self):
        from mall.pay_service import get_mp_pay_client
        return get_mp_pay_client(self.pay_type, self.wx_pay_config)

    @property
    def paid(self):
        return self.status == self.STATUS_FINISHED

    def get_pay_order_info(self):
        return dict(body='消费卷支付记录订单', user_id=self.get_user_id())

    def get_user_id(self):
        if self.pay_type == self.PAY_WeiXin_LP:
            return self.user.lp_openid
        else:
            log.error('unsupported pay_type: %s' % self.pay_type)
            raise CustomAPIException('不支持的支付类型')

    def update_info(self):
        from mall.pay_service import get_mp_pay_client
        from wechatpy import WeChatPayException
        c = get_mp_pay_client(self.pay_type, self.wx_pay_config)
        try:
            res = c.query_order(self)
            if res:
                self.transaction_id = res.get('transaction_id')
                self.save(update_fields=['transaction_id'])
        except WeChatPayException as e:
            log.error(e)

    @classmethod
    def available_pay_types(self):
        return [self.PAY_WeiXin_LP]

    def biz_paid(self):
        """
        付款成功时,根据业务类型决定处理方法
        :return:
        """
        if self.biz == self.BIZ_BLIND:
            self.blind_receipt.set_paid()
        elif self.biz == self.BIZ_LOTTERY:
            self.lottery_receipt.set_paid()
        else:
            log.fatal('unkonw biz: %s, of receipt: %s' % (self.biz, self.pk))

    def set_paid(self, pay_type=ReceiptAbstract.PAY_WeiXin_LP, transaction_id=None):
        if self.paid:
            return
        self.status = self.STATUS_FINISHED
        self.pay_type = pay_type
        self.transaction_id = transaction_id if transaction_id else self.transaction_id
        self.save(update_fields=['status', 'transaction_id'])
        self.biz_paid()


class Prize(UseShortNoAbstract):
    title = models.CharField('名称', max_length=128)
    STATUS_OFF = 2
    STATUS_ON = 1
    STATUS_CHOICES = ((STATUS_OFF, U'下架'), (STATUS_ON, U'上架'))
    status = models.IntegerField(u'状态', choices=STATUS_CHOICES, default=STATUS_ON, help_text='下架后则不会被抽中')
    source_type = models.PositiveSmallIntegerField('奖品类型', choices=PRIZE_SOURCE_TYPE_CHOICES, default=SR_COUPON)
    coupon = models.ForeignKey('coupon.Coupon', verbose_name='消费卷', null=True, blank=True, on_delete=models.SET_NULL,
                               help_text='消费卷类型时选填')
    RA_COMMON = 1
    RA_RARE = 2
    RA_HIDDEN = 3
    RARE_TYPE_CHOICES = ((RA_COMMON, '普通款'), (RA_RARE, '稀有款'), (RA_HIDDEN, '隐藏款'))
    rare_type = models.PositiveSmallIntegerField('稀有类型', choices=RARE_TYPE_CHOICES, default=RA_COMMON)
    amount = models.DecimalField('价值', max_digits=13, decimal_places=2, default=0)
    desc = models.TextField('描述', max_length=1000)
    instruction = models.TextField('兑奖说明')
    stock = models.IntegerField('库存数量', default=0)
    weight = models.PositiveSmallIntegerField('权重数', default=0)
    head_image = models.ImageField('奖品头图', upload_to=f'{IMAGE_FIELD_PREFIX}/blind/prize/head',
                                   validators=[validate_image_file_extension], null=True, blank=True)
    display_order = models.PositiveSmallIntegerField('排序', default=0, help_text='越大排越前')
    create_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name_plural = verbose_name = '奖品'
        ordering = ['-display_order', '-pk']

    def __str__(self):
        return self.title

    @classmethod
    def prize_update_stock_from_redis(cls):
        close_old_connections()
        prsc.persist()

    def prize_change_stock(self, mul):
        ret = True
        # prize_upd = []
        # prize_upd.append((self.pk, mul, 0))
        # succ1, tfc_result = prsc.batch_incr(prize_upd)
        succ1, tfc_result = prsc.incr(self.pk, mul, ceiling=0)
        if succ1:
            prsc.record_update_ts(self.id)
            # prsc.batch_record_update_ts(prsc.resolve_ids(tfc_result))
        else:
            log.warning(f"奖品 incr failed,{self.pk}")
            # 库存不足
            ret = False
        return ret

    def prize_redis_stock(self, stock=None):
        # 初始化库存
        if stock == None:
            stock = self.stock
        prsc.append_cache(StockModel(_id=self.id, stock=stock))

    def prize_del_redis_stock(self):
        prsc.remove(self.id)


class PrizeDetailImage(models.Model):
    """奖品详情介绍图附表"""
    prize = models.ForeignKey(Prize, verbose_name='奖品', on_delete=models.CASCADE, related_name='detail_images')
    image = models.ImageField('图片', upload_to=f'{IMAGE_FIELD_PREFIX}/blind/prize/detail',
                              validators=[validate_image_file_extension])

    class Meta:
        verbose_name_plural = verbose_name = '奖品详情图'
        ordering = ['pk']

    def __str__(self):
        return str(self.id)


class BlindBox(UseShortNoAbstract):
    title = models.CharField('名称', max_length=128)
    STATUS_OFF = 2
    STATUS_ON = 1
    STATUS_CHOICES = ((STATUS_OFF, '下架'), (STATUS_ON, '上架'))
    status = models.IntegerField(u'状态', choices=STATUS_CHOICES, default=STATUS_ON, help_text='下架后则不会被抽中')
    GR_THREE = 3
    GR_SIX = 6
    GR_NINE = 9
    GR_CHOICES = ((GR_THREE, '3格'), (GR_SIX, '6格'), (GR_NINE, '9格'))
    grids_num = models.PositiveSmallIntegerField(u'格子数', choices=GR_CHOICES, default=GR_THREE)
    TYPE_COMMON = 1
    TYPE_RARE = 2
    TYPE_HIDDEN = 3
    TYPE_CHOICES = ((TYPE_COMMON, '普通'), (TYPE_RARE, '稀有'), (TYPE_HIDDEN, '隐藏'))
    type = models.PositiveSmallIntegerField('类型', choices=TYPE_CHOICES, default=TYPE_COMMON)
    price = models.DecimalField('价格', max_digits=13, decimal_places=2, default=0)
    original_price = models.DecimalField('原价', max_digits=13, decimal_places=2, default=0)
    stock = models.IntegerField('盲盒库存数量', default=0)
    desc = models.TextField('描述说明', max_length=1000, help_text='副标题的意思')
    rare_weight_multiple = models.PositiveSmallIntegerField('稀有款权重倍数', default=1)
    hidden_weight_multiple = models.PositiveSmallIntegerField('隐藏款权重倍数', default=1)
    logo = models.ImageField('盲盒封面图', upload_to=f'{IMAGE_FIELD_PREFIX}/blind/box',
                             validators=[validate_image_file_extension])
    display_order = models.PositiveSmallIntegerField('排序', default=0, help_text='越大排越前')
    create_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name_plural = verbose_name = '盲盒'
        ordering = ['-display_order', '-pk']

    def __str__(self):
        return self.title

    @classmethod
    def blind_box_update_stock_from_redis(cls):
        close_old_connections()
        from blind_box.stock_updater import bdbc
        bdbc.persist()

    def blind_box_change_stock(self, mul):
        ret = True
        from blind_box.stock_updater import bdbc
        succ1, tfc_result = bdbc.incr(self.pk, mul, ceiling=0)
        if succ1:
            bdbc.record_update_ts(self.id)
        else:
            log.warning(f"盲盒 incr failed,{self.pk}")
            # 库存不足
            ret = False
        return ret

    def blind_box_redis_stock(self, stock=None):
        # 初始化库存
        from blind_box.stock_updater import bdbc, StockModel
        if stock == None:
            stock = self.stock
        bdbc.append_cache(StockModel(_id=self.id, stock=stock))

    def blind_box_del_redis_stock(self):
        from blind_box.stock_updater import bdbc
        bdbc.remove(self.id)

    def draw_blind_box_prizes(self) -> List[Prize]:
        from blind_box.lottery_utils import weighted_random_choice
        """
        盲盒抽奖
        每个格抽出的奖品不重复，下一格抽取时需要去掉上一格的奖品
        奖品权重数×类型倍数/去掉本次开盒已抽出的奖品后，剩余库存不为0的奖品权重数总和
        并发安全处理：
        1. 使用事务保证原子性
        2. 记录所有已扣减的库存，失败时回滚
        3. 库存扣减失败时循环重试，直到成功或没有候选奖品
        """
        blind_box = self
        grids_num = blind_box.grids_num
        drawn_prize = []  # 本次开盒已抽出的奖品列表
        deducted_stocks = []  # 已扣减的库存记录，格式: [(prize_id, 数量), ...]
        try:
            # 检查奖品池库存
            available_prizes = Prize.objects.filter(status=Prize.STATUS_ON, stock__gt=0)
            available_count = available_prizes.count()
            if available_count < grids_num:
                raise Exception("奖品库存不足，请稍后再试！")
            # 可用奖品池
            candidates = []
            for prize in available_prizes:
                # 检查库存（从redis实时获取）
                stock = prsc.get_stock(prize.id)
                if not stock or int(stock) <= 0:
                    continue
                # 计算权重：奖品权重数 × 类型倍数
                # 普通款：权重 = 奖品权重数
                # 稀有款：权重 = 奖品权重数 × 稀有款权重倍数
                # 隐藏款：权重 = 奖品权重数 × 隐藏款权重倍数
                base_weight = prize.weight
                if prize.rare_type == Prize.RA_RARE:
                    weight = base_weight * blind_box.rare_weight_multiple
                elif prize.rare_type == Prize.RA_HIDDEN:
                    weight = base_weight * blind_box.hidden_weight_multiple
                else:
                    weight = base_weight
                # 权重必须大于0才能参与抽奖
                if weight > 0:
                    candidates.append({
                        'item': prize,
                        'weight': weight
                    })
            if len(candidates) < grids_num:
                log.error(f"奖品不足")
                raise Exception(f"奖品库存不足，请稍后再试.")
            for i in list(range(grids_num)):
                # 获取可抽取的奖品（排除本次开盒已抽出的奖品）
                # 循环尝试抽取，直到成功或没有候选奖品
                selected_prize = None
                success = False
                max_retries = len(candidates)  # 最多重试次数等于候选奖品数量
                retry_count = 0

                while not success and retry_count < max_retries:
                    # 根据权重随机选择
                    # 概率计算公式：奖品权重数×类型倍数 / 去掉本次开盒已抽出的奖品后，剩余库存不为0的奖品权重数总和
                    # weighted_random_choice函数内部会计算总权重作为分母
                    selected_prize, prize_index = weighted_random_choice(candidates)
                    if not selected_prize:
                        log.error(f"抽奖失败，无法完成第 {i + 1} 格抽奖")
                        raise Exception(f"奖品库存不足，请稍后再试..")
                    # 减少库存（使用incr方法，ceiling=0表示减后必须>=0，原子操作保证并发安全）
                    success, new_stock = prsc.incr(selected_prize.id, -1, ceiling=0)
                    # 去掉已经抽奖过的
                    candidates.pop(prize_index)
                    # candidates = [c for c in candidates if c['item'].id != selected_prize.id]
                    if not success:
                        # 如果减库存失败（可能被其他请求并发减掉了），从候选列表中移除该奖品，继续重试
                        log.warning(f"奖品 {selected_prize.id} 库存不足，尝试重新抽取（第 {retry_count + 1} 次重试）")
                        # 删除掉没有库存的奖品
                        if len(candidates) < grids_num:
                            log.error(f"奖品不足。")
                            raise Exception(f"奖品库存不足，请稍后再试！")
                        retry_count += 1
                    else:
                        # 库存扣减成功，记录已扣减的库存
                        deducted_stocks.append(selected_prize.id)
                        prsc.record_update_ts(selected_prize.id)
                if not success:
                    raise Exception(f"奖品库存不足，请稍后再试！！")
                # 添加到已抽中列表
                drawn_prize.append(selected_prize)
            # 确保抽取的奖品数量等于格子数
            if len(drawn_prize) != grids_num:
                log.error(f"盲盒 {blind_box.id} 抽奖异常：期望 {grids_num} 个奖品，实际 {len(drawn_prize)} 个")
                raise Exception("抽奖失败，请稍后重试。。")
            return drawn_prize

        except Exception as e:
            # 如果抽奖过程中出现任何异常，回滚所有已扣减的库存
            if deducted_stocks:
                log.warning(f"盲盒 {blind_box.id} 抽奖失败，开始回滚已扣减的库存，共 {len(deducted_stocks)} 个奖品")
                for prize_id in deducted_stocks:
                    try:
                        # 回滚库存（加回库存）
                        prsc.incr(prize_id, 1, ceiling=Ellipsis)
                        prsc.record_update_ts(prize_id)
                        log.info(f"已回滚奖品 {prize_id} 的库存")
                    except Exception as rollback_error:
                        log.error(f"回滚奖品 {prize_id} 库存失败: {rollback_error}")
            # 重新抛出异常
            raise

    @classmethod
    def test_draw_prize(cls, test_count=10000):
        blind_box = cls.objects.first()
        available_prizes = Prize.objects.filter(status=Prize.STATUS_ON, stock__gt=0)
        # 可用奖品池
        candidates = []
        for prize in available_prizes:
            # 检查库存（从redis实时获取）
            stock = prsc.get_stock(prize.id)
            if not stock or int(stock) <= 0:
                continue
            # 计算权重：奖品权重数 × 类型倍数
            # 普通款：权重 = 奖品权重数
            # 稀有款：权重 = 奖品权重数 × 稀有款权重倍数
            # 隐藏款：权重 = 奖品权重数 × 隐藏款权重倍数
            base_weight = prize.weight
            if prize.rare_type == Prize.RA_RARE:
                weight = base_weight * blind_box.rare_weight_multiple
            elif prize.rare_type == Prize.RA_HIDDEN:
                weight = base_weight * blind_box.hidden_weight_multiple
            else:
                weight = base_weight
            # 权重必须大于0才能参与抽奖
            if weight > 0:
                candidates.append({
                    'item': prize,
                    'weight': weight
                })
        from blind_box.lottery_utils import weighted_random_choice, calculate_probabilities_prize
        probabilities = calculate_probabilities_prize(candidates)
        print("各奖品的理论概率：")
        for prize, prob in probabilities.items():
            print(f"{prize}: {prob:.4f} ({prob * 100:.2f}%)")
        print("\n进行10000次抽奖测试：")
        # 进行多次抽奖测试
        results = {}
        # 测试手动实现的方法
        results_manual = {}
        for _ in range(test_count):
            selected, index = weighted_random_choice(candidates)
            if selected:
                results_manual[selected.title] = results_manual.get(selected.title, 0) + 1
                results[index] = results.get(index, 0) + 1
        # 输出测试结果
        for prize, count in results_manual.items():
            actual_prob = count / test_count
            theoretical_prob = probabilities[prize]
            print(f"{prize}: 出现{count}次, 实际概率: {actual_prob:.4f}, 理论概率: {theoretical_prob:.4f}")
        print(results)


class BlindBoxCarouselImage(models.Model):
    """盲盒详情轮播图"""
    blind_box = models.ForeignKey(BlindBox, verbose_name='盲盒', on_delete=models.CASCADE, related_name='carousel_images')
    image = models.ImageField('图片', upload_to=f'{IMAGE_FIELD_PREFIX}/blind/box/carousel',
                              validators=[validate_image_file_extension])

    class Meta:
        verbose_name_plural = verbose_name = '盲盒详情轮播图'
        ordering = ['pk']

    def __str__(self):
        return str(self.id)


class BlindBoxDetailImage(models.Model):
    """盲盒详情介绍图附表"""
    blind_box = models.ForeignKey(BlindBox, verbose_name='盲盒', on_delete=models.CASCADE, related_name='detail_images')
    image = models.ImageField('图片', upload_to=f'{IMAGE_FIELD_PREFIX}/blind/box/detail',
                              validators=[validate_image_file_extension])

    class Meta:
        verbose_name_plural = verbose_name = '盲盒详情图'
        ordering = ['pk']

    def __str__(self):
        return str(self.id)


class BlindBoxOrder(models.Model):
    ST_DEFAULT = 1
    ST_PAID = 2
    ST_CANCEL = 3
    ST_REFUNDING = 4
    ST_REFUNDED = 5
    PAYMENT_STATUS = (
        (ST_DEFAULT, '未付款'),
        (ST_PAID, '已支付'),
        (ST_CANCEL, '已取消'),
        (ST_REFUNDING, '退款中'),
        (ST_REFUNDED, '已退款'),
    )
    order_no = models.CharField('订单号', max_length=128, unique=True, default=price_his_no, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, verbose_name='用户', null=True)
    blind_box = models.ForeignKey(BlindBox, on_delete=models.SET_NULL, verbose_name='盲盒', null=True)
    mobile = models.CharField('手机号', max_length=20)
    status = models.PositiveSmallIntegerField('状态', choices=PAYMENT_STATUS, default=ST_DEFAULT)
    amount = models.DecimalField('实付金额', max_digits=10, decimal_places=2)
    refund_amount = models.DecimalField('已退款金额', max_digits=10, decimal_places=2, default=0)
    receipt = models.OneToOneField(BlindReceipt, verbose_name='收款记录', on_delete=models.SET_NULL, null=True,
                                   related_name='blind_receipt')
    wx_pay_config = models.ForeignKey(WeiXinPayConfig, verbose_name='微信支付', blank=True, null=True,
                                      on_delete=models.SET_NULL)
    pay_type = models.SmallIntegerField('付款类型', choices=BlindReceipt.PAY_CHOICES, default=BlindReceipt.PAY_NOT_SET)
    create_at = models.DateTimeField('创建时间', auto_now_add=True)
    pay_at = models.DateTimeField('支付时间', null=True, blank=True)
    refund_at = models.DateTimeField('退款完成时间', null=True, blank=True)
    transaction_id = models.CharField('交易号', max_length=100, null=True, blank=True)
    snapshot = models.TextField('盲盒快照', help_text='下单时保存的快照', editable=False)
    pay_end_at = models.DateTimeField('支付截止时间', null=True)

    class Meta:
        verbose_name = verbose_name_plural = '盲盒订单'
        ordering = ['-pk']

    def __str__(self):
        return self.order_no

    @classmethod
    def can_refund_status(cls):
        return [cls.ST_PAID]

    def push_refund(self, amount):
        self.refund_amount += amount
        self.status = self.ST_REFUNDING
        self.save(update_fields=['refund_amount', 'status'])

    def set_refunded(self):
        self.refund_at = timezone.now()
        self.status = self.ST_REFUNDED
        self.save(update_fields=['status', 'refund_at'])
        # 退款成功后返还库存
        self.return_prize_stock()

    @atomic
    def set_paid(self):
        if self.status in [self.ST_DEFAULT, self.ST_CANCEL]:
            self.status = self.ST_PAID
            self.transaction_id = self.receipt.transaction_id
            self.pay_at = timezone.now()
            self.save(update_fields=['status', 'pay_at', 'transaction_id'])
            self.change_prize_status()

    def change_prize_status(self):
        self.blind_box_items.exclude(source_type=SR_COUPON).update(status=WinningRecordAbstract.ST_PENDING_RECEIVE)
        bb_qs = self.blind_box_items.filter(source_type=SR_COUPON)
        from coupon.models import UserCouponRecord
        for bb in bb_qs:
            if bb.prize and bb.prize.coupon:
                coupon = bb.prize.coupon
                try:
                    UserCouponRecord.create_record(self.user.id, coupon, win_prize_no=bb.no)
                except Exception as e:
                    log.error('盲盒付款发放消费券失败')
                    log.error(e)
                    pass

    @classmethod
    def get_snapshot(cls, blind_box: BlindBox):
        from blind_box.serializers import BlindBoxSnapshotSerializer
        data = BlindBoxSnapshotSerializer(blind_box).data
        data['price'] = float(data['price'])
        data['original_price'] = float(data['original_price'])
        return json.dumps(data)

    @classmethod
    def auto_cancel_task(cls):
        close_old_connections()
        # 延迟两分钟自动取消
        pay_end_at = timezone.now() - timedelta(minutes=2)
        qs = cls.objects.filter(status=cls.ST_DEFAULT, pay_end_at__lt=pay_end_at)
        for obj in qs:
            obj.set_cancel()

    def set_cancel(self):
        if self.status == self.ST_DEFAULT:
            receipt = self.receipt
            if receipt.pay_type == receipt.PAY_WeiXin_LP:
                receipt.query_status(self.order_no)
            if receipt.paid:
                receipt.biz_paid()
                return False, '取消失败订单已付款'
            self.status = self.ST_CANCEL
            self.cancel_at = timezone.now()
            self.save(update_fields=['status', 'cancel_at'])
            # 归还库存
            self.return_prize_stock()
        return True, ''

    def return_prize_stock(self):
        # 归还盲盒库存
        if self.blind_box:
            self.blind_box.blind_box_change_stock(1)
        # 奖品明细无效
        for item in self.blind_box_items.all():
            prize = item.prize
            prize.set_invalid()

    def do_refund(self, refund_amount, refund_reason=None):
        st, msg, obj = BlindOrderRefund.create_record(self, source_type=BlindOrderRefund.SR_BLIND_BOX,
                                                      amount=refund_amount, refund_reason=refund_reason)
        return st, msg


def winning_record_no(tail_length=3):
    """
    使用当前时间(datetime)生成中奖序号
    :return:
    """
    now = timezone.now()
    return 'WR%s%s' % (now.strftime('%Y%m%d%H%M%S%f'), ''.join(sample(list(map(str, range(0, 10))), tail_length)))


class WinningRecordAbstract(models.Model):
    ST_UNPAID = 1  # 待领取
    ST_PENDING_RECEIVE = 2  # 待领取
    ST_PENDING_SHIP = 3  # 待发货
    ST_PENDING_RECEIPT = 4  # 待收货
    ST_COMPLETED = 5  # 已完成
    ST_INVALID = 6  # 无效
    STATUS_CHOICES = (
        (ST_UNPAID, '未付款'),
        (ST_PENDING_RECEIVE, '待领取'),
        (ST_PENDING_SHIP, '待发货'),
        (ST_PENDING_RECEIPT, '待收货'),
        (ST_COMPLETED, '已完成'),
        (ST_INVALID, '无效'),
    )
    no = models.CharField('中奖序号', max_length=128, unique=True, default=winning_record_no, db_index=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='中奖用户', on_delete=models.SET_NULL, null=True)
    mobile = models.CharField('手机号', max_length=20)
    express_address = models.CharField('送货地址', max_length=200, null=True, blank=True)
    express_phone = models.CharField('收货联系人电话', max_length=11, null=True, blank=True)
    express_user_name = models.CharField('收货姓名', max_length=11, null=True, blank=True)
    prize = models.ForeignKey(Prize, verbose_name='奖品', on_delete=models.SET_NULL, null=True)
    source_type = models.PositiveSmallIntegerField('奖品类型', choices=PRIZE_SOURCE_TYPE_CHOICES, default=SR_COUPON)
    remark = models.TextField('备注', blank=True, max_length=1000, null=True)
    status = models.PositiveSmallIntegerField('状态', choices=STATUS_CHOICES, default=ST_UNPAID)
    express_no = models.CharField('快递单号', max_length=50, blank=True, null=True)
    express_company_code = models.CharField('快递公司编码', max_length=30, blank=True, null=True)
    express_company_name = models.CharField('快递公司', max_length=50, blank=True, null=True)
    winning_at = models.DateTimeField('中奖时间', auto_now_add=True)
    receive_at = models.DateTimeField('领取时间', null=True, blank=True)
    ship_at = models.DateTimeField('发货时间', null=True, blank=True)
    complete_at = models.DateTimeField('完成时间', null=True, blank=True)
    snapshot = models.TextField('奖品快照', help_text='中奖时保存的快照', editable=False)

    class Meta:
        abstract = True

    def __str__(self):
        return self.no

    @classmethod
    def get_snapshot(cls, prize: Prize):
        from blind_box.serializers import PrizeSnapshotSerializer
        data = PrizeSnapshotSerializer(prize).data
        data['amount'] = float(data['amount'])
        return json.dumps(data)

    def set_invalid(self):
        """
        取消订单或者退款设为无效
        """
        self.status = self.ST_INVALID
        self.save(update_fields=['status'])
        # 归还库存
        if self.prize:
            self.prize.prize_change_stock(1)

    def set_completed(self):
        """设置为已完成"""
        self.status = self.ST_COMPLETED
        self.complete_at = timezone.now()
        self.save(update_fields=['status', 'complete_at'])

    def set_received(self):
        """设置为已领取（客服操作后调用）"""
        if self.status == self.ST_PENDING_RECEIVE:
            self.status = self.ST_COMPLETED
            self.receive_at = timezone.now()
            self.save(update_fields=['status', 'receive_at'])

    def set_shipped(self, express_no=None, express_company_code=None, express_company_name=None):
        """设置为已发货"""
        self.status = self.ST_PENDING_RECEIPT
        self.ship_at = timezone.now()
        if express_no:
            self.express_no = express_no
        if express_company_code:
            self.express_company_code = express_company_code
        if express_company_name:
            self.express_company_name = express_company_name
        self.save(update_fields=['status', 'ship_at', 'express_no', 'express_company_code', 'express_company_name'])


class BlindBoxWinningRecordManager(models.Manager):
    def get_queryset(self):
        return super(BlindBoxWinningRecordManager, self).get_queryset().exclude(status=WinningRecordAbstract.ST_UNPAID)


class BlindBoxWinningRecord(WinningRecordAbstract):
    blind_box_order = models.ForeignKey(BlindBoxOrder, on_delete=models.SET_NULL, verbose_name='盲盒订单',
                                        related_name='blind_box_items',
                                        null=True, blank=True)
    blind_box = models.ForeignKey(BlindBox, verbose_name='盲盒', on_delete=models.SET_NULL, null=True, blank=True)
    blind_box_title = models.CharField('盲盒名称', max_length=128)
    # objects = BlindBoxWinningRecordManager()

    class Meta:
        verbose_name_plural = verbose_name = '盲盒中奖记录'
        ordering = ['-pk']


class WinningRecordShipmentReceipt(models.Model):
    """中奖记录发货回执"""
    create_at = models.DateTimeField('创建时间', auto_now_add=True)
    operator = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='操作用户', on_delete=models.SET_NULL, null=True)
    receipt_file = models.FileField('回执文件', upload_to=f'{FILE_FIELD_PREFIX}/blind/shipment_receipt', validators=[
        FileExtensionValidator(allowed_extensions=['xlsx'])], help_text='只支持xlsx')
    remark = models.TextField('备注', blank=True)

    class Meta:
        verbose_name_plural = verbose_name = '中奖记录发货回执'
        ordering = ['-pk']

    def __str__(self):
        return f"{self.create_at.strftime('%Y-%m-%d %H:%M:%S')} - {self.operator}"


class WheelActivity(UseShortNoAbstract):
    """转盘活动"""
    STATUS_OFF = 2
    STATUS_ON = 1
    STATUS_CHOICES = ((STATUS_OFF, '下架'), (STATUS_ON, '上架'))
    name = models.CharField('标题', max_length=128)
    title_image = models.ImageField('标题图', upload_to=f'{IMAGE_FIELD_PREFIX}/wheel',
                                    validators=[validate_image_file_extension], null=True)
    bg_image = models.ImageField('背景图', upload_to=f'{IMAGE_FIELD_PREFIX}/wheel',
                                 validators=[validate_image_file_extension], null=True)
    status = models.PositiveSmallIntegerField('状态', choices=STATUS_CHOICES, default=STATUS_ON, help_text='最多一个上架')
    description = models.TextField('活动说明', blank=True)
    create_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name_plural = verbose_name = '转盘活动'
        ordering = ['-pk']

    def __str__(self):
        return self.name

    def clean(self):
        if self.status == self.STATUS_ON:
            WheelActivity.objects.filter(status=self.STATUS_ON).exclude(pk=self.pk).update(status=self.STATUS_OFF)


class WheelSection(UseShortNoAbstract):
    """转盘片区附表"""
    wheel_activity = models.ForeignKey(WheelActivity, verbose_name='转盘活动', on_delete=models.CASCADE,
                                       related_name='sections')
    prize = models.ForeignKey(Prize, verbose_name='关联奖品', on_delete=models.SET_NULL, null=True, blank=True)
    thank_image = models.ImageField('谢谢参与头图', upload_to=f'{IMAGE_FIELD_PREFIX}/wheel/section',
                                    validators=[validate_image_file_extension], null=True, blank=True)
    is_no_prize = models.BooleanField('是否谢谢参与', default=False, help_text='勾选后则该片区不中奖')
    weight = models.PositiveSmallIntegerField('权重数', default=0)
    winning_tip = models.CharField('中奖提示语', max_length=200, blank=True)
    is_enabled = models.BooleanField('是否启用', default=True, help_text='不勾选时转盘不显示该片区，计算概率时不看该片区')

    class Meta:
        verbose_name_plural = verbose_name = '转盘片区'
        ordering = ['pk']

    def __str__(self):
        return str(self.no)


def lottery_purchase_order_no(tail_length=3):
    """
    使用当前时间(datetime)生成抽奖次数购买订单号
    :return:
    """
    now = timezone.now()
    return 'LP%s%s' % (now.strftime('%Y%m%d%H%M%S%f'), ''.join(sample(list(map(str, range(0, 10))), tail_length)))


class LotteryPurchaseRecord(models.Model):
    """抽奖次数购买记录"""
    ST_UNPAID = 1
    ST_PAID = 2  # 已完成
    ST_CANCELED = 3  # 已取消
    ST_REFUNDING = 4
    ST_REFUNDED = 5
    STATUS_CHOICES = (
        (ST_UNPAID, '未支付'),
        (ST_PAID, '已付款'),
        (ST_CANCELED, '已取消'),
        (ST_REFUNDING, '退款中'),
        (ST_REFUNDED, '已退款'),
    )
    order_no = models.CharField('订单号', max_length=128, unique=True, default=lottery_purchase_order_no, db_index=True)
    receipt = models.OneToOneField(BlindReceipt, verbose_name='收款记录', on_delete=models.SET_NULL, null=True,
                                   related_name='lottery_receipt')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='用户', on_delete=models.SET_NULL, null=True)
    mobile = models.CharField('手机号', max_length=20)
    purchase_count = models.PositiveIntegerField('购买次数')
    amount = models.DecimalField('实付金额', max_digits=13, decimal_places=2)
    refund_amount = models.DecimalField('已退款金额', max_digits=10, decimal_places=2, default=0)
    status = models.PositiveSmallIntegerField('状态', choices=STATUS_CHOICES, default=ST_PAID)
    create_at = models.DateTimeField('下单时间', auto_now_add=True)
    pay_at = models.DateTimeField('支付时间', null=True, blank=True)
    wx_pay_config = models.ForeignKey(WeiXinPayConfig, verbose_name='微信支付', blank=True, null=True,
                                      on_delete=models.SET_NULL)
    pay_type = models.SmallIntegerField('付款类型', choices=BlindReceipt.PAY_CHOICES, default=BlindReceipt.PAY_NOT_SET)
    refund_at = models.DateTimeField('退款完成时间', null=True, blank=True)
    cancel_at = models.DateTimeField('取消时间', null=True, blank=True)
    snapshot = models.TextField('转盘快照', help_text='下单时保存的快照', editable=False)
    transaction_id = models.CharField('微信支付单号', max_length=32, null=True, blank=True)

    class Meta:
        verbose_name_plural = verbose_name = '抽奖次数购买记录'
        ordering = ['-pk']

    def __str__(self):
        return self.order_no

    @classmethod
    def get_snapshot(cls, wheel_activity: WheelActivity):
        from blind_box.serializers import WheelActivityBasicSerializer
        data = WheelActivityBasicSerializer(wheel_activity).data
        return json.dumps(data)

    @atomic
    def set_paid(self):
        if self.status in [self.ST_UNPAID, self.ST_CANCELED]:
            self.status = self.ST_PAID
            self.transaction_id = self.receipt.transaction_id
            self.pay_at = timezone.now()
            self.save(update_fields=['status', 'pay_at', 'transaction_id'])

    @classmethod
    def can_refund_status(cls):
        return [cls.ST_PAID]

    def push_refund(self, amount):
        self.refund_amount += amount
        self.status = self.ST_REFUNDING
        self.save(update_fields=['refund_amount', 'status'])
        # 申请退款时减抽奖次数
        self.return_lottery_times()

    def set_refunded(self):
        self.refund_at = timezone.now()
        self.status = self.ST_REFUNDED
        self.save(update_fields=['status', 'refund_at'])

    def return_lottery_times(self):
        if self.user:
            ult = UserLotteryTimes.get_or_create_record(self.user)
            ult.update_times(-1, True)


class UserLotteryTimes(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, verbose_name='用户', on_delete=models.SET_NULL, null=True)
    mobile = models.CharField('手机号', null=True, max_length=20)
    times = models.IntegerField('剩余转盘次数', default=0)
    total_times = models.IntegerField('总转盘次数', default=0)
    version = models.PositiveIntegerField('版本', default=0, editable=False)
    create_at = models.DateTimeField('创建时间', auto_now_add=True)
    update_at = models.DateTimeField('更新时间', null=True, blank=True)

    class Meta:
        verbose_name_plural = verbose_name = '用户转盘次数'
        ordering = ['-pk']

    @classmethod
    def get_or_create_record(cls, user):
        obj, _ = cls.objects.get_or_create(user=user)
        return obj

    def update_times(self, times, add_total=True):
        """
        转盘次数
        """
        st = True
        key = get_redis_name('lot_times{}'.format(self.id))
        with run_with_lock(key, 3, 3) as got:
            if got:
                self.refresh_from_db(fields=['times', 'version', 'total_times'])
                qs = self.__class__.objects.filter(version=self.version, pk=self.pk)
                if not add_total:
                    ret = qs.update(version=F('version') + 1, times=F('times') + times)
                else:
                    ret = qs.update(version=F('version') + 1, times=F('times') + times,
                                    total_times=F('total_times') + times)
                if ret <= 0:
                    st = False
                    log.error('转盘抽奖次数，更新失败,{},{},{}'.format(self.id, times, add_total))
            else:
                log.error('转盘抽奖次数，更新失败,{},{},{}'.format(self.id, times, add_total))
                st = False
        return st


class UserLotteryRecord(models.Model):
    no = models.CharField('编号', max_length=128, unique=True, default=price_his_no, db_index=True, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, verbose_name='用户', on_delete=models.SET_NULL, null=True)
    mobile = models.CharField('手机号', null=True, max_length=20)
    wheel_activity = models.ForeignKey(WheelActivity, verbose_name='转盘活动', on_delete=models.SET_NULL, null=True)
    is_prize = models.BooleanField('是否中奖', default=False)
    snapshot = models.TextField('转盘快照', help_text='下单时保存的快照', editable=False)
    create_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name_plural = verbose_name = '用户转盘抽奖记录'
        ordering = ['-pk']

    def __str__(self):
        return self.no

    @classmethod
    def get_snapshot(cls, wheel_activity: WheelActivity):
        from blind_box.serializers import WheelActivityBasicSerializer
        data = WheelActivityBasicSerializer(wheel_activity).data
        return json.dumps(data)

    @classmethod
    def create_record(cls, user, wheel_activity: WheelActivity, is_prize=False):
        snapshot = cls.get_snapshot(wheel_activity)
        cls.objects.create(user=user, wheel_activity=wheel_activity, mobile=user.mobile, is_prize=is_prize,
                           snapshot=snapshot)


class WheelWinningRecord(WinningRecordAbstract):
    lottery_record = models.ForeignKey(UserLotteryRecord, on_delete=models.SET_NULL, verbose_name='转盘抽奖记录',
                                       related_name='lottery_items',
                                       null=True, blank=True)
    wheel_activity = models.ForeignKey(WheelActivity, verbose_name='转盘活动', on_delete=models.SET_NULL, null=True)
    wheel_name = models.CharField('转盘名称', max_length=128)

    class Meta:
        verbose_name_plural = verbose_name = '转盘中奖记录'
        ordering = ['-pk']


class BlindOrderRefund(models.Model):
    SR_BLIND_BOX = 1
    SR_LOTTERY = 2
    SOURCE_TYPE_CHOICES = ((SR_BLIND_BOX, '盲盒订单'), (SR_LOTTERY, '转盘次数'))
    source_type = models.PositiveSmallIntegerField('订单类型', choices=SOURCE_TYPE_CHOICES, default=SR_BLIND_BOX)
    order_no = models.CharField(u'订单号', max_length=128)
    out_refund_no = models.CharField(u'退款单号', max_length=64, default=blind_refund_no, unique=True, db_index=True)
    STATUS_DEFAULT = 1
    STATUS_PAYING = 2
    STATUS_PAY_FAILED = 3
    STATUS_FINISHED = 4
    STATUS_CANCELED = 5
    STATUS_CHOICES = (
        (STATUS_DEFAULT, '待退款'), (STATUS_PAYING, '退款支付中'), (STATUS_PAY_FAILED, '退款支付失败'), (STATUS_FINISHED, '已完成'),
        (STATUS_CANCELED, '已拒绝'))
    status = models.IntegerField('状态', choices=STATUS_CHOICES, default=STATUS_DEFAULT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='用户', on_delete=models.SET_NULL, null=True)
    refund_amount = models.DecimalField(u'退款金额', max_digits=13, decimal_places=2, default=0)
    refund_reason = models.CharField('退款原因', max_length=200, null=True, blank=True)
    amount = models.DecimalField(u'实退金额', max_digits=13, decimal_places=2, default=0)
    error_msg = models.CharField('退款返回信息', max_length=1000, null=True, blank=True)
    transaction_id = models.CharField('交易号', max_length=100, null=True, blank=True)
    refund_id = models.CharField('退款方退款单号', max_length=32, null=True, blank=True)
    return_code = models.CharField('微信通信结果', max_length=20, null=True, blank=True)
    result_code = models.CharField('微信返回结果', max_length=20, null=True, blank=True)
    create_at = models.DateTimeField('创建时间', auto_now_add=True)
    confirm_at = models.DateTimeField('确认时间', null=True, blank=True)
    finish_at = models.DateTimeField('完成时间', null=True, blank=True)
    op_user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='操作退款用户', on_delete=models.SET_NULL, null=True,
                                blank=True, related_name='+')
    blind_box_order = models.ForeignKey(BlindBoxOrder, verbose_name='盲盒订单', on_delete=models.SET_NULL, null=True,
                                        blank=True)
    lottery_order = models.ForeignKey(LotteryPurchaseRecord, on_delete=models.SET_NULL, verbose_name='转盘次数购买记录',
                                      null=True, blank=True)

    class Meta:
        verbose_name_plural = verbose_name = '退款记录'
        ordering = ['-pk']

    def get_refund_notify_url(self):
        return refund_notify_url

    @classmethod
    def create_record(cls, order, source_type, amount, refund_reason=None):
        receipt = order.receipt
        refund_amount = amount if amount > 0 else order.amount
        if receipt.status == BlindReceipt.STATUS_FINISHED and receipt.transaction_id:
            lottery_order = None
            blind_box_order = None
            if source_type == cls.SR_BLIND_BOX:
                blind_box_order = order
            elif source_type == cls.SR_LOTTERY:
                lottery_order = order
            inst = cls.objects.create(user=order.user, blind_box_order=blind_box_order, lottery_order=lottery_order,
                                      refund_amount=refund_amount, source_type=source_type,
                                      order_no=order.order_no,
                                      refund_reason=refund_reason, transaction_id=receipt.transaction_id)
            order.push_refund(refund_amount)
            return True, '', inst
        else:
            return False, '该订单未付款不能退款', None

    @atomic
    def set_confirm(self, request, op_user=None):
        try:
            st = self.wx_refund(request)
            msg = self.error_msg
            if st:
                self.status = self.STATUS_PAYING
                self.confirm_at = timezone.now()
                self.op_user = op_user
                self.save(update_fields=['status', 'confirm_at', 'op_user'])
            return st, msg
        except Exception as e:
            self.status = self.STATUS_PAY_FAILED
            self.confirm_at = timezone.now()
            self.error_msg = str(e)
            self.op_user = op_user
            self.save(update_fields=['status', 'confirm_at', 'op_user'])
            log.error(e)
            return False, str(e)

    @classmethod
    def can_confirm_status(cls):
        return [cls.STATUS_DEFAULT, cls.STATUS_PAY_FAILED]

    # @classmethod
    # def user_refund(cls, order, op_user=None, reason=None):
    #     st, msg, inst = cls.create_record(order, reason)
    #     if st:
    #         st, msg = inst.set_confirm(op_user)
    #     if not st:
    #         raise CustomAPIException(msg)

    def get_refund_order(self):
        order = None
        if self.source_type == self.SR_BLIND_BOX:
            order = self.blind_box_order
        elif self.source_type == self.SR_LOTTERY:
            order = self.lottery_order
        return order

    def wx_refund(self, request):
        order = self.get_refund_order()
        if not order:
            raise CustomAPIException('退款订单找不到')
        receipt = order.receipt
        if not receipt.transaction_id:
            receipt.update_info()
        from mall.pay_service import get_mp_pay_client
        mp_pay_client = get_mp_pay_client(receipt.pay_type, receipt.wx_pay_config)
        refund_notify_url = request.build_absolute_uri(self.get_refund_notify_url())
        result = mp_pay_client.new_refund(self, notify_url=refund_notify_url)
        self.return_code = result.get('return_code')
        self.result_code = result.get('result_code')
        self.error_msg = '{}, {}'.format(result.get('return_msg'), result.get('err_code_des'))
        self.refund_id = result.get('refund_id', None)
        self.save(update_fields=['return_code', 'result_code', 'error_msg', 'refund_id'])
        if self.return_code == self.result_code == 'SUCCESS':
            return True
        return False

    def set_cancel(self, op_user):
        self.status = self.STATUS_CANCELED
        self.confirm_at = timezone.now()
        self.op_user = op_user
        self.save(update_fields=['status', 'confirm_at', 'op_user'])
        self.return_order_status()

    def return_order_status(self):
        order = self.get_refund_order()
        if order and order.refund_amount > 0:
            order.status = order.ST_PAID
            order.refund_amount -= self.refund_amount
            order.save(update_fields=['status', 'refund_amount'])

    def set_fail(self, msg=None):
        self.status = self.STATUS_PAY_FAILED
        self.finish_at = timezone.now()
        self.error_msg = msg
        self.save(update_fields=['status', 'error_msg', 'finish_at'])
        # self.return_order_status()

    def set_finished(self, amount):
        """
        设置为完成:
        1.在退款支付通知回调中
        2.后台手动
        :return:
        """
        from decimal import Decimal
        self.status = self.STATUS_FINISHED
        self.finish_at = timezone.now()
        self.amount = Decimal(amount) / 100
        self.save(update_fields=['status', 'finish_at', 'amount'])
        order = self.get_refund_order()
        if order:
            order.set_refunded()
