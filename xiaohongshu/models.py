# coding: utf-8
from __future__ import unicode_literals
from django.db import models
from datetime import timedelta
from django.conf import settings
import logging
from random import sample
from mall.models import User
from common.utils import get_config
from django.core.exceptions import ValidationError
from django.utils import timezone
from restframework_ext.exceptions import CustomAPIException
from ticket.models import tiktok_goods_url, tiktok_order_detail_url, TicketOrder, TicketFile, TicketUserCode, \
    SessionInfo, TicketOrderRefund
import json
from typing import List, Dict
from django.db.transaction import atomic

log = logging.getLogger(__name__)
xhs_good_path = tiktok_goods_url
xhs_order_detail_path = tiktok_order_detail_url


def file_size(value):
    limit = 1024 * 1024
    if value.size > limit:
        raise ValidationError('图片大小不能超过1M')
    if value.width != value.height:
        raise ValidationError('要求长宽比1:1')


def randomstrwithdatetime_settle(tail_length=6):
    """
    使用当前时间(datetime)生成随机字符串,可以作为订单号
    :return:
    """
    now = timezone.now()
    return 'ST%s%s' % (now.strftime('%Y%m%d%H%M%S'), ''.join(sample(list(map(str, range(0, 10))), tail_length)))


class XiaoHongShuWxa(models.Model):
    name = models.CharField('名称', max_length=50, null=True)
    app_id = models.CharField('app_id', max_length=50)
    app_secret = models.CharField('app_secret', max_length=50, null=True)
    s_token = models.CharField('消息校检Token', max_length=100)
    encodingAesKey = models.CharField('消息加密Key', max_length=100, help_text='encodingAesKey')

    class Meta:
        verbose_name_plural = verbose_name = '小红书小程序'

    def __str__(self):
        return self.name

    @classmethod
    def get(cls):
        return cls.objects.first()


class XhsPoi(models.Model):
    name = models.CharField('poi名称', max_length=100)
    poi_id = models.CharField('poiid', max_length=50)
    address = models.CharField('地址', max_length=200)
    lat = models.FloatField('纬度', default=0)
    lng = models.FloatField('经度', default=0)

    class Meta:
        verbose_name_plural = verbose_name = '小红书poi'

    def __str__(self):
        return '{}({})'.format(self.name, self.poi_id)

    @classmethod
    def get_poi_list(cls, page_no=1):
        from xiaohongshu.api import get_xhs_wxa
        client = get_xhs_wxa()
        ret = client.poi_list(page_no)
        if ret.get('data') and ret['data'].get('total'):
            update_list = []
            dd = ret['data']
            for data in dd['list']:
                inst, _ = cls.objects.get_or_create(poi_id=data['poi_id'])
                inst.name = data['name']
                inst.address = data['address']
                inst.lat = data['latitude']
                inst.lng = data['longitude']
                update_list.append(inst)
            if update_list:
                cls.objects.bulk_update(update_list, ['name', 'address', 'lat', 'lng'])
            if dd['total'] > page_no * 100 and page_no <= 100:
                cls.get_poi_list(page_no + 1)


class XhsUser(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, verbose_name='用户', on_delete=models.CASCADE,
                                related_name='xhs_user')
    openid_xhs = models.CharField('openid', max_length=100, unique=True, db_index=True)
    session_key = models.CharField('session_key', max_length=50, null=True)

    class Meta:
        verbose_name_plural = verbose_name = '小红书小程序用户'

    @classmethod
    def xhs_user(cls, user: User):
        if hasattr(user, 'xhs_user'):
            return user.xhs_user
        return None

    @classmethod
    def create_record(cls, openid_xhs):
        user_name = 'xhs{}'.format(User.gen_username())
        user = User.objects.create(username=user_name)
        inst = cls.objects.create(openid_xhs=openid_xhs, user=user)
        return user, inst

    @classmethod
    @atomic
    def check_user_xhs(cls, mobile, login_user, request):
        # 抖音快手合并用户
        user = User.mobile_get_user(mobile)
        uu = login_user
        from restframework_ext.permissions import get_token
        token = get_token(request)
        if user and user.id != uu.id:
            has_bind = cls.objects.filter(user=user)
            if has_bind:
                raise CustomAPIException('绑定失败，该手机号已绑定小红书账号。请勿重复绑定')
            fields = []
            log.debug(user.id)
            log.debug(uu.id)
            if not user.parent and uu.parent:
                # 旧用户上级为空而且当前用户有上级
                fields = fields + ['parent', 'parent_at']
            if fields:
                for fd in fields:
                    setattr(user, fd, getattr(uu, fd))
            uu.set_delete()
            user.save(update_fields=fields)
            # 新的最新推荐人，覆盖到旧的上面
            from mall.user_cache import change_new_parent
            change_new_parent(uu.id, user.id)
            xhs_user = cls.objects.filter(user_id=uu.id).first()
            if xhs_user:
                xhs_user.user = user
                xhs_user.save(update_fields=['user'])
            uu = user
            user.refresh_user_cache(token)
        else:
            uu.set_info(mobile)
        return uu


class XhsShowCategoryAbstract(models.Model):
    category_id = models.CharField(verbose_name='类目ID', null=True, max_length=50, help_text='小红书类目ID', unique=True)
    name = models.CharField(max_length=20, verbose_name='类目名称')

    class Meta:
        abstract = True

    def __str__(self):
        return self.name


class XhsShowTopCategory(XhsShowCategoryAbstract):
    class Meta:
        verbose_name_plural = verbose_name = '小红书一级类目'

    @property
    def secondarys(self):
        return self.xhs_secondary


class XhsShowSecondaryCategory(XhsShowCategoryAbstract):
    superior = models.ForeignKey(XhsShowTopCategory, verbose_name='一级分类', related_name='xhs_secondary',
                                 on_delete=models.CASCADE)

    class Meta:
        verbose_name_plural = verbose_name = '小红书二级类目'

    def __str__(self):
        return '%s=>%s' % (self.superior.name, self.name)


class XhsShowThirdCategory(XhsShowCategoryAbstract):
    second = models.ForeignKey(XhsShowSecondaryCategory, verbose_name='二级分类', related_name='xhs_third',
                               on_delete=models.CASCADE)

    class Meta:
        verbose_name_plural = verbose_name = '小红书三级类目'

    def __str__(self):
        return '%s=>%s' % (self.second.name, self.name)

    @classmethod
    def init_category(cls):
        """
        休闲娱乐	演出	专业剧场
        'categories': [{'name_path': '休闲娱乐 > 演出 > 专业剧场',
   'category_id': '65a612ad7a2f640001c40e23'}]}

        """
        # name = '专业剧场'
        # from xiaohongshu.api import get_xhs_wxa
        # xhs_wxa = get_xhs_wxa()
        # ret = xhs_wxa.category_search(name)
        superior, _ = XhsShowTopCategory.objects.get_or_create(name='休闲娱乐')
        second, _ = XhsShowSecondaryCategory.objects.get_or_create(name='演出', superior=superior)
        cls.objects.get_or_create(name='专业剧场', second=second, category_id='65a612ad7a2f640001c40e23')


class XhsShow(models.Model):
    show = models.OneToOneField('ticket.ShowProject', verbose_name='演出项目', related_name='xhs_show',
                                on_delete=models.CASCADE)
    short_title = models.CharField('短标题', max_length=12)

    class Meta:
        verbose_name_plural = verbose_name = '小红书配置'


class XhsGoodsConfig(models.Model):
    session = models.OneToOneField('ticket.SessionInfo', verbose_name='场次', related_name='xhs_session',
                                   on_delete=models.CASCADE)
    xhs_product_id = models.CharField('产品ID', null=True, max_length=10, editable=False)
    category = models.ForeignKey(XhsShowThirdCategory, verbose_name='演出类型', on_delete=models.CASCADE)
    poi_list = models.ManyToManyField(XhsPoi, verbose_name='小红书poi')
    need_push = models.BooleanField('是否需要推送到小红书', default=True)
    STATUS_ON = 1
    STATUS_OFF = 0
    STATUS_CHOICES = ((STATUS_ON, u'上架'), (STATUS_OFF, u'下架'))
    status = models.IntegerField(u'状态', choices=STATUS_CHOICES, default=STATUS_ON)
    PUSH_DEFAULT = 1
    PUSH_APPROVE = 2
    PUSH_SUCCESS = 3
    PUSH_NEED = 4
    PUSH_FAIL = 5
    PUSH_AUTH_FAIL = 6
    PUSH_CHOICES = (
        (PUSH_DEFAULT, u'待推送'), (PUSH_APPROVE, u'审核中'), (PUSH_SUCCESS, u'审核完成'),
        (PUSH_FAIL, u'推送失败'), (PUSH_AUTH_FAIL, u'审核失败'))
    push_status = models.IntegerField(u'小红书推送状态', choices=PUSH_CHOICES, default=PUSH_DEFAULT)
    fail_msg = models.TextField('推送错误信息', max_length=1000, null=True, blank=True)
    push_at = models.DateTimeField('推送时间', null=True, blank=True)

    class Meta:
        verbose_name_plural = verbose_name = '小红书场次配置'

    def __str__(self):
        return str(self.id)

    @classmethod
    def get_session_qs(cls, session_qs):
        # 小红书不支持运费
        return session_qs.filter(xhs_session__status=cls.STATUS_ON, xhs_session__push_status=cls.PUSH_SUCCESS,
                                 is_paper=False)

    @classmethod
    def xhs_show_calendar(cls, session_qs):
        xhs_qs = cls.get_session_qs(session_qs)
        xhs_data = dict()
        for inst in xhs_qs:
            d_key = inst.start_at.strftime('%Y-%m-%d')
            xhs_data[d_key] = xhs_data[d_key] + 1 if xhs_data.get(d_key) else 1
        return xhs_data

    @classmethod
    def get_session(cls, out_product_id: str):
        return cls.objects.filter(xhs_product_id=out_product_id).first()

    def set_approve(self, push_status, fail_msg=None):
        self.push_status = push_status
        self.fail_msg = fail_msg
        self.save(update_fields=['push_status', 'fail_msg'])
        if push_status == self.PUSH_SUCCESS:
            self.session.change_show_calendar()

    @property
    def product_id(self):
        if self.xhs_product_id:
            return self.xhs_product_id
        product_id = self.session.get_session_out_id()
        if not self.xhs_product_id:
            self.xhs_product_id = product_id
            self.save(update_fields=['xhs_product_id'])
        return product_id

    def re_push(self):
        self.fail_msg = None
        self.push_status = self.PUSH_DEFAULT
        self.save(update_fields=['fail_msg', 'push_status'])

    def push_status_to_xhs(self, status):
        # 更改状态
        if self.push_status != self.PUSH_SUCCESS:
            return False, '审核通过才能操作'
        from xiaohongshu.api import get_xhs_wxa
        xhs = get_xhs_wxa()
        # try:
        out_sku_ids = []
        session = self.session
        t_qs = TicketFile.objects.filter(session_id=session.id, is_xhs=True)
        if not t_qs or t_qs.filter(push_xhs=False):
            # 新的票档推审核,或者没有推小红书的
            self.re_push()
            # 新的票档推审核
            # self.re_push()
            return False, '操作成功，自动重新推送'
        for tf in t_qs:
            if (status == self.STATUS_ON and tf.status) or status == self.STATUS_OFF:
                out_sku_ids.append(tf.get_out_id())
        xhs.batch_change_sku_status(status, out_sku_ids)
        self.status = status
        self.save(update_fields=['status'])
        # except Exception as e:
        #     raise ValidationError(e)
        return True, None

    # def check_push_status(self):
    #     # 查询状态
    #     from xiaohongshu.api import get_xhs_wxa
    #     xhs = get_xhs_wxa()
    #     ret = xhs.get_product(self.product_id)

    @classmethod
    def session_push_to_xhs(cls):
        # 商品首次上传/审核未通过重新上传
        qs = cls.objects.filter(need_push=True, push_status=cls.PUSH_DEFAULT)
        for inst in qs:
            ret, msg = inst.push_to_xhs()
            inst.update_push_xhs(ret, msg)

    def update_push_xhs(self, ret: bool, msg: str):
        inst = self
        inst.push_at = timezone.now()
        fields = ['push_at']
        if not ret:
            inst.fail_msg = msg
            inst.push_status = self.PUSH_FAIL
            fields = fields + ['fail_msg', 'push_status']
        else:
            if inst.push_status != self.PUSH_SUCCESS:
                inst.fail_msg = None
                inst.push_status = self.PUSH_APPROVE
                fields = fields + ['fail_msg', 'push_status']
        inst.save(update_fields=fields)

    def push_to_xhs(self):
        from xiaohongshu.api import get_xhs_wxa
        xhs = get_xhs_wxa()
        inst = self
        session = inst.session
        show = session.show
        try:
            config = get_config()
            top_image = '{}{}'.format(config['template_url'], show.logo_mobile.url)
            # notify_url = '{}{}'.format(config['template_url'], poi_notify_url)
            good_path = '/{}?id={}'.format(xhs_good_path, show.id)
            name = session.title or show.title
            short_title = name[:12]
            if hasattr(show, 'xhs_show'):
                short_title = show.xhs_show.short_title
            skus_list = []
            t_qs = TicketFile.objects.filter(session_id=session.id).order_by('price')
            if not t_qs:
                return False, '未配置推送的票档'
            for tf in t_qs:
                sku = tf.get_xhs_sku_data(top_image)
                status = self.STATUS_OFF
                if tf.is_xhs and self.status == self.STATUS_ON and tf.status:
                    status = self.STATUS_ON
                sku['status'] = status
                skus_list.append(sku)
            poi_id_list = list(self.poi_list.all().values_list('poi_id', flat=True))
            ret = xhs.upsert_product(out_product_id=self.product_id, name=session.get_dy_product_name(),
                                     short_title=short_title, desc=show.content, category_id=self.category.category_id,
                                     top_image=top_image, path=good_path, create_at=self.session.create_at,
                                     skus=skus_list, poi_id_list=poi_id_list)
            t_qs.update(push_xhs=True)
            return True, None
        except Exception as e:
            log.error(e)
            return False, e

    @classmethod
    def check_approve_task(cls):
        """
        商品审核状态, PASS: 审核通过,REJECT:审核拒绝,AUDITING:待审核
        """
        qs = cls.objects.filter(push_status=cls.PUSH_APPROVE)
        from xiaohongshu.api import get_xhs_wxa
        xhs = get_xhs_wxa()
        for inst in qs:
            try:
                ret = xhs.get_product(inst.xhs_product_id)
                audit_status = ret.get('audit_status')
                if audit_status:
                    fail_msg = None
                    push_status = None
                    if audit_status == 'PASS':
                        push_status = XhsGoodsConfig.PUSH_SUCCESS
                    elif audit_status == 'REJECT':
                        push_status = XhsGoodsConfig.PUSH_AUTH_FAIL
                        if ret.get('audit_info') and ret['audit_info'].get('reject_reason'):
                            fail_msg = ret['audit_info'].get('reject_reason')
                    if push_status:
                        inst.set_approve(push_status, fail_msg)
            except Exception as e:
                log.error(e)
                break


class XhsOrder(models.Model):
    ticket_order = models.OneToOneField(TicketOrder, verbose_name='订单', on_delete=models.CASCADE,
                                        related_name='xhs_order')
    session = models.ForeignKey(SessionInfo, verbose_name=u'场次', on_delete=models.CASCADE)
    order_id = models.CharField('小红书订单id', max_length=100, db_index=True)
    open_id = models.CharField('小红书用户openid', max_length=100)
    pay_snapshot = models.TextField('支付参数', max_length=1000, editable=False)
    item_snapshot = models.TextField('下单票档规格', editable=False)

    class Meta:
        verbose_name_plural = verbose_name = '小红书订单'
        ordering = ['-pk']

    def __str__(self):
        return self.order_id

    @classmethod
    def get_order(cls, order_no: str):
        return cls.objects.filter(ticket_order__order_no=order_no).first()

    @classmethod
    def push_order(cls, ticket_order: TicketOrder, session_seat_list: list = None, seat_dict: dict = None):
        xhs_user = XhsUser.xhs_user(ticket_order.user)
        if not xhs_user:
            raise CustomAPIException('请先授权小红书登录后再支付')
        from xiaohongshu.api import get_xhs_wxa
        xhs = get_xhs_wxa()
        order_detail_path = '/{}?id={}&order_no={}'.format(xhs_order_detail_path, ticket_order.id,
                                                           ticket_order.order_no)
        from mp.models import BasicConfig
        basic = BasicConfig.get()
        expire_minutes = basic.auto_cancel_minutes if basic.auto_cancel_minutes >= 5 else 5
        expire_at = ticket_order.create_at + timedelta(minutes=expire_minutes)
        out_order_id = ticket_order.order_no
        product_infos, seat_dict = cls.get_xhs_product_infos(ticket_order.session.get_session_out_id(),
                                                             session_seat_list, seat_dict)
        ret = xhs.order_upsert(out_order_id=out_order_id, open_id=xhs_user.openid_xhs, path=order_detail_path,
                               create_at=ticket_order.create_at, expire_at=expire_at,
                               freight_price=int(ticket_order.express_fee * 100),
                               product_infos=product_infos, order_price=int(ticket_order.actual_amount * 100),
                               discount_price=0)
        if ret.get('order_id'):
            pay_snapshot = json.dumps(ret)
            item_snapshot = json.dumps(dict(seat_dict=seat_dict))
            cls.objects.create(ticket_order=ticket_order, session=ticket_order.session, open_id=xhs_user.openid_xhs,
                               order_id=ret['order_id'],
                               pay_snapshot=pay_snapshot, item_snapshot=item_snapshot)
            return dict(payToken=ret['pay_token'], orderId=ret['order_id'])
        raise CustomAPIException('小红书下单失败支付')

    @classmethod
    def get_xhs_product_infos(cls, out_product_id: str, session_seat_list: list = None, seat_dict: dict = None):
        """
        关于订单价格计算
        单个商品的 real_price 价格等于 sale_price 减去所有 discount_infos 价格之和
        订单总价 order_price 等于所有商品的 real_price 价格总和加上 freight_price 价格，再加上所有 extra_price_infos 的价格总和
        """
        if not seat_dict:
            seat_dict = dict()
            if session_seat_list:
                for seat in session_seat_list:
                    if seat_dict.get(str(seat.ticket_level.id)):
                        seat_dict[str(seat.ticket_level.id)] += 1
                    else:
                        seat_dict[str(seat.ticket_level.id)] = 1
        product_infos = []
        for level_id, quantity in seat_dict.items():
            tf = TicketFile.objects.get(id=int(level_id))
            sale_price = int(tf.price * 100) * quantity
            discount_price = 0
            real_price = sale_price - discount_price
            sku_info = {
                "out_product_id": out_product_id,
                "out_sku_id": tf.get_out_id(),
                "num": quantity,
                "sale_price": sale_price,
                "real_price": real_price
                # "discount_infos": [
                #     {
                #         "name": "string",
                #         "price": 0,
                #         "num": 0
                #     }
                # ]
            }
            product_infos.append(sku_info)
        return product_infos, seat_dict

    def query_pay_token(self):
        from xiaohongshu.api import get_xhs_wxa
        xhs = get_xhs_wxa()
        ret = xhs.query_pay_token(self.ticket_order.order_no, self.open_id)
        return ret

    def get_order_detail(self):
        from xiaohongshu.api import get_xhs_wxa
        xhs = get_xhs_wxa()
        ret = xhs.order_detail(self.ticket_order.order_no, self.open_id)
        return ret

    def query_status(self, is_detail=False):
        ret = self.get_order_detail()
        if ret['code'] == 0 and ret['success'] and ret['data']['order_status'] in [6, 7]:
            if is_detail:
                return True, ret['data']
            return True, ret['data'].get('third_trade_no')
        return False, None

    @classmethod
    def xhs_refund(cls, refund: TicketOrderRefund):
        """部分退只能执行一次退款,分开多次退的逻辑不支持"""
        try:
            from math import ceil
            ticket_order = refund.order
            xhs_order = ticket_order.xhs_order
            if not hasattr(ticket_order, 'xhs_order'):
                raise CustomAPIException('找不到满足退款状态的小红书订单')
            # 下单有，这里必有
            from xiaohongshu.api import get_xhs_wxa
            xhs = get_xhs_wxa()
            refund_voucher_detail = []
            product_infos = []
            item_snapshot = json.loads(xhs_order.item_snapshot)
            product_infos_list, _ = cls.get_xhs_product_infos(ticket_order.session.get_session_out_id(),
                                                              item_snapshot.get('session_seat_list', None),
                                                              item_snapshot.get('seat_dict', None))
            refund_price = int(refund.refund_amount * 100)
            rest_amount = refund_price
            all_refund = False
            st, xhs_order_detail = xhs_order.query_status(is_detail=True)
            if not st:
                raise CustomAPIException('找不到满足退款状态的小红书订单')
            if refund.refund_amount == ticket_order.actual_amount:
                all_refund = True
            for info in product_infos_list:
                if rest_amount <= 0:
                    break
                # 单价
                price = info['real_price'] / info['num']
                data = {
                    "out_product_id": info['out_product_id'],
                    "out_sku_id": info['out_sku_id'],
                    "num": info['num'],
                    "price": info['real_price']
                }
                if not all_refund:
                    # 部分退，需要判断价格是否包含关系
                    if rest_amount > info['real_price']:
                        if rest_amount <= info['real_price'] * info['num']:
                            data['price'] = rest_amount
                    else:
                        data['num'] = ceil(rest_amount / price)
                        data['price'] = rest_amount
                    rest_amount -= data['price']
                v_total_price = data['price']
                for voucher in xhs_order_detail['voucher_infos']:
                    if not voucher.get('is_use', False) and voucher['pay_amount'] == info['real_price'] / info['num']:
                        refund_price = voucher['pay_amount'] if voucher[
                                                                    'pay_amount'] <= v_total_price else v_total_price
                        refund_voucher_detail.append(
                            dict(voucher_code=voucher['voucher_code'], refund_price=refund_price))
                        voucher['is_use'] = True
                        v_total_price -= refund_price
                    if v_total_price <= 0:
                        break
                product_infos.append(data)
            xhs.create_refund(out_order_id=ticket_order.order_no, out_refund_no=refund.out_refund_no,
                              open_id=ticket_order.xhs_order.open_id, create_at=refund.create_at,
                              refund_price=refund_price, product_infos=product_infos,
                              refund_voucher_detail=refund_voucher_detail,
                              reason=refund.return_reason or '客服要求退款')
            return True
        except Exception as e:
            refund.status = refund.STATUS_PAY_FAILED
            refund.error_msg = str(e)
            refund.save(update_fields=['status', 'error_msg'])
        return False

    def query_refund(self, out_refund_no: str):
        from xiaohongshu.api import get_xhs_wxa
        xhs = get_xhs_wxa()
        ticket_order = self.ticket_order
        msg = ''
        try:
            ret = xhs.query_refund(out_order_id=ticket_order.order_no, open_id=self.open_id,
                                   out_refund_no=out_refund_no)
            if ret['code'] == 0 and ret['success']:
                data = ret['data']
                """status 售后单状态，1-处理中 2-成功 3-失败"""
                st_dict = {1: '处理中', 2: '成功', 3: '失败'}
                msg += '退款原因:{}，退款金额:{},状态:{}'.format(data['reason'], data['price_info']['refund_price'] / 100,
                                                      st_dict[int(data['status'])])
            else:
                msg = ret['msg']
        except Exception as e:
            msg = '订单不存在退款'
        return msg

    def check_settle_info(self):
        """
        查询cps，订单详情里没有
        cps_amount 只有总的cps佣金，看不到具体的用户
        """
        from xiaohongshu.api import get_xhs_wxa
        xhs = get_xhs_wxa()
        ret = xhs.check_settle_info(order_id=self.ticket_order.order_no)
        settle_status_dict = {0: '不需要结算', 1: '初始化', 2: '可结算', 3: '结算中', 4: '已结算', 5: '结算失败', 6: '结算冲抵'}
        # ret['data']['order_settles'][0]['transaction_settle_status']


class XhsVoucherCodeRecord(models.Model):
    ticket_code = models.OneToOneField('ticket.TicketUserCode', verbose_name='演出票(座位)信息', on_delete=models.CASCADE,
                                       related_name='xhs_code')
    ticket_order = models.ForeignKey(TicketOrder, verbose_name='订单', on_delete=models.CASCADE)
    voucher_code = models.CharField('检票码', max_length=100, db_index=True)
    xhs_check = models.BooleanField('是否推送核销', default=False)
    msg = models.CharField('核销返回', max_length=500, null=True, blank=True)

    class Meta:
        verbose_name_plural = verbose_name = '小红书核销码'
        unique_together = ['ticket_code', 'voucher_code']

    @classmethod
    def get_or_create_record(cls, ticket_code: TicketUserCode, voucher_code: str):
        inst, _ = cls.objects.get_or_create(ticket_code=ticket_code, voucher_code=voucher_code,
                                            ticket_order=ticket_code.order)
        return inst

    @classmethod
    def order_create(cls, voucher_infos: List[Dict], ticket_order: TicketOrder):
        code_qs = TicketUserCode.objects.filter(order_id=ticket_order.id)
        i = 0
        for code in code_qs:
            cls.get_or_create_record(code, voucher_infos[i]['VoucherCode'])
            i = i + 1

    @classmethod
    def xhs_auto_verify_code(cls):
        """
        小红书任务核销二维码,结束的场次自动推核销
        """
        qs = XhsOrder.objects.filter(ticket_order__auto_check=TicketOrder.CHECK_DEFAULT,
                                     session__end_at__lt=timezone.now(),
                                     ticket_order__status__in=[TicketOrder.STATUS_PAID, TicketOrder.STATUS_FINISH])
        from xiaohongshu.api import get_xhs_wxa
        xhs = get_xhs_wxa()
        for xhs_order in qs:
            auto_check = TicketOrder.CHECK_SUCCESS
            order = xhs_order.ticket_order
            code_qs = XhsVoucherCodeRecord.objects.filter(ticket_order_id=order.id, xhs_check=False)
            for code in code_qs:
                # 单码核销
                try:
                    voucher_infos = [{"voucher_code": code.voucher_code}]
                    ret = xhs.verify_code(order.order_no, voucher_infos=voucher_infos)
                    if ret['code'] != 0 or not ret['success']:
                        log.error('小红书自动核销失败,{},{}'.format(ret['msg'], order.order_no))
                        msg = ret['msg']
                        auto_check = TicketOrder.CHECK_FAIL
                    else:
                        msg = '小红书自动核销成功'
                    code.xhs_check = True
                    code.msg = msg
                    code.save(update_fields=['xhs_check', 'msg'])
                    code.ticket_code.push_at = timezone.now()
                    update_fields = ['push_at']
                    if code.ticket_code.status == TicketUserCode.STATUS_DEFAULT:
                        code.ticket_code.status = TicketUserCode.STATUS_OVER_TIME
                        update_fields.append('status')
                    code.ticket_code.save(update_fields=update_fields)
                except Exception as e:
                    log.error(e)
            # 按订单核销，不可行
            # ret = xhs.verify_code(order.order_no, voucher_infos=[])
            # if ret['code'] != 0 or not ret['success']:
            #     log.error('小红书自动核销失败,{},{}'.format(ret['msg'], order.order_no))
            #     msg = ret['msg']
            #     auto_check = TicketOrder.CHECK_FAIL
            # else:
            #     msg = '小红书自动核销成功'
            # code_qs = XhsVoucherCodeRecord.objects.filter(ticket_order_id=order.id)
            # code_qs.update(xhs_check=True, msg=msg)
            # ticket_code_ids = list(code_qs.values_list('ticket_code_id', flat=True))
            # t_code_qs = TicketUserCode.objects.filter(id__in=ticket_code_ids)
            # t_code_qs.update(push_at=timezone.now())
            # t_code_qs.filter(status=TicketUserCode.STATUS_DEFAULT).update(status=TicketUserCode.STATUS_OVER_TIME)

            # 有一个码核销失败，当订单核销失败
            order.auto_check = auto_check
            order.save(update_fields=['auto_check'])
            xhs_order.ticket_order.set_finish()
