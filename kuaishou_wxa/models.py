# coding: utf-8
from __future__ import unicode_literals

from django.core.validators import validate_image_file_extension
from django.db import models
from datetime import datetime
from django.conf import settings
import logging
from random import sample

from common.config import IMAGE_FIELD_PREFIX
from express.models import Division
from mall.models import User
from common.utils import get_config
from django.db import close_old_connections
from django.db.models import Q, F
from kuaishou_wxa.api import get_ks_wxa
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.transaction import atomic
from restframework_ext.exceptions import CustomAPIException
from ticket.models import tiktok_goods_url, TicketOrder
import json

log = logging.getLogger(__name__)
poi_notify_url = '/api/ks/ks_auth_notify/'
ks_path = tiktok_goods_url  # 小程序路劲
order_notify_url = '/api/ks/ks_order_notify/'


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


class KShouWxa(models.Model):
    name = models.CharField('名称', max_length=50, null=True)
    app_id = models.CharField('app_id', max_length=50)
    app_secret = models.CharField('app_secret', max_length=50, null=True)

    class Meta:
        verbose_name_plural = verbose_name = '快手授权小程序'

    def __str__(self):
        return self.name

    @classmethod
    def get(cls):
        return cls.objects.first()


class KShouPlatform(models.Model):
    component_app_id = models.CharField('第三方应用appid', max_length=50, help_text='开发资料-开发者ID')
    component_app_secret = models.CharField('第三方应用secret', max_length=50, help_text='开发资料-开发者ID', null=True)
    component_token = models.CharField('消息校检Token', max_length=100)
    component_key = models.CharField('消息加密Key', max_length=100)
    api_url = models.CharField('请求url', max_length=50)

    class Meta:
        verbose_name_plural = verbose_name = '快手小程序第三方平台'

    def __str__(self):
        return self.component_app_id

    @classmethod
    def get(cls):
        return cls.objects.first()


class KShouLife(models.Model):
    app_id = models.CharField('app_id', max_length=50, help_text='开发资料-开发者ID')
    app_secret = models.CharField('app_secret', max_length=50, help_text='开发资料-开发者ID')

    class Meta:
        verbose_name_plural = verbose_name = '快手生活服务平台'

    @classmethod
    def get(cls):
        return cls.objects.first()


class KsUser(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='用户', on_delete=models.CASCADE)
    openid_ks = models.CharField('快手小程序openid', max_length=50, null=True, unique=True, db_index=True)
    session_key = models.CharField('快手小程序session_key', max_length=50, null=True)

    class Meta:
        verbose_name_plural = verbose_name = '快手小程序用户'

    @classmethod
    def ks_user(cls, user):
        return cls.objects.filter(user=user).first()

    @classmethod
    def create_record(cls, openid_ks):
        user_name = 'ks{}'.format(User.gen_username())
        user = User.objects.create(username=user_name)
        inst = cls.objects.create(openid_ks=openid_ks, user=user)
        return user, inst

    @classmethod
    @atomic
    def check_user_ks(cls, mobile, login_user, request):
        # 抖音快手合并用户
        user = User.mobile_get_user(mobile)
        uu = login_user
        from restframework_ext.permissions import get_token
        token = get_token(request)
        if user and user.id != uu.id:
            has_bind = cls.objects.filter(user=user)
            if has_bind:
                raise CustomAPIException('绑定失败，该手机号已绑定快手账号。请勿重复绑定')
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
            ks_user = cls.objects.filter(user_id=uu.id).first()
            if ks_user:
                ks_user.user = user
                ks_user.save(update_fields=['user'])
            uu = user
            user.refresh_user_cache(token)
        else:
            uu.set_info(mobile)
        return uu


class KsStore(models.Model):
    name = models.CharField('店铺名称', max_length=100)
    city = models.ForeignKey(Division, verbose_name='城市', null=True, on_delete=models.SET_NULL,
                             limit_choices_to=models.Q(type=1))
    wxa = models.ForeignKey(KShouWxa, verbose_name='抖音小程序', null=True, editable=False, on_delete=models.SET_NULL)

    class Meta:
        verbose_name_plural = verbose_name = '快手店铺'

    def __str__(self):
        return self.name

    def get_poi_list(self):
        from kuaishou_wxa.api import get_ks_wxa
        wxa = get_ks_wxa()
        ret = wxa.get_poi_list(self.name, str(self.city))
        update_list = []
        create_list = []
        for poi in ret['data']:
            inst = KsPoi.objects.filter(store_id=self.id, poi_id=poi['poiId']).first()
            if inst:
                inst.name = poi['poiName']
                inst.city = poi['city']
                inst.address = poi['address']
                inst.lat = poi['lat']
                inst.lng = poi['lng']
                update_list.append(inst)
            else:
                create_list.append(KsPoi(store_id=self.id, poi_id=poi['poiId'], name=poi['poiName'], city=poi['city'],
                                         address=poi['address'], lat=poi['lat'], lng=poi['lng']))
        if create_list:
            KsPoi.objects.bulk_create(create_list)
        if update_list:
            KsPoi.objects.bulk_update(update_list, ['name', 'city', 'address', 'lat', 'lng'])


class KsPoi(models.Model):
    store = models.ForeignKey(KsStore, verbose_name='快手店铺', on_delete=models.CASCADE)
    name = models.CharField('poi名称', max_length=100)
    poi_id = models.CharField('poiid', max_length=50)
    city = models.CharField('城市', max_length=10)
    address = models.CharField('地址', max_length=200)
    lat = models.FloatField('纬度', default=0)
    lng = models.FloatField('经度', default=0)
    is_merge = models.BooleanField('是否被快手合并', default=False, editable=False, null=True, blank=True)
    new_poi_id = models.CharField('合并后新poiid', max_length=50, editable=False, null=True, blank=True)

    class Meta:
        verbose_name_plural = verbose_name = '快手poi'

    def __str__(self):
        return '{}({})'.format(self.name, self.poi_id)


class KsPoiQualityLabels(models.Model):
    title = models.CharField('内容', max_length=10)
    val = models.IntegerField('值')

    class Meta:
        verbose_name_plural = verbose_name = 'poi品质标签'

    def __str__(self):
        return self.title

    @classmethod
    def init_record(cls):
        data_list = [[1, '网红'], [2, '热卖'], [3, '大牌'], [4, '热门'], [5, '网友推荐']]
        for dd in data_list:
            cls.objects.get_or_create(title=dd[1], val=dd[0])


class KsPoiService(models.Model):
    kspoi = models.OneToOneField(KsPoi, verbose_name='快手poi', on_delete=models.CASCADE, help_text='已被合并的不能选择')
    poi_id = models.CharField('poiid', max_length=50, editable=False)
    wxa = models.ForeignKey(KShouWxa, verbose_name='抖音小程序', null=True, editable=False, on_delete=models.SET_NULL)
    QR_DEFAULT = 0
    QR_CHAIN = 1
    QR_CHAIN_NET = 2
    QR_AREA = 3
    QR_CHOICES = ((QR_DEFAULT, '未定义'), (QR_CHAIN, '全国连锁店'), (QR_CHAIN_NET, '城市连锁店&城市网红店'), (QR_AREA, '区域店铺'))
    grade_label = models.IntegerField(u'poi等级标签', choices=QR_CHOICES, default=QR_DEFAULT, editable=False)
    quality_labels = models.ManyToManyField(KsPoiQualityLabels, verbose_name='poi品质标签', blank=True)
    ST_DEFAULT = 'DEFAULT'
    ST_APPROVING = 'APPROVING'
    ST_PASS = 'PASS'
    ST_REJECT = 'REJECT'
    ST_COMBINE = 'COMBINE'
    ST_CHOICES = (
        (ST_DEFAULT, '待审核'), (ST_APPROVING, '审核中'), (ST_PASS, '审核通过'), (ST_REJECT, '审核拒绝'), (ST_COMBINE, '已作废'))
    status = models.CharField(u'抖音自动核销状态', choices=ST_CHOICES, default=ST_DEFAULT, max_length=10,
                              help_text='当被快手合并后，变为作废状态')
    reject_reason = models.TextField('审核未通过的原因', null=True, blank=True)
    create_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name_plural = verbose_name = 'poi挂载记录'
        ordering = ['-pk']

    def __str__(self):
        return str(self.kspoi)

    @classmethod
    def update_status(cls, poi_id, app_id, status, reject_reason):
        inst = cls.objects.filter(poi_id=poi_id, wxa__app_id=app_id).first()
        if inst:
            inst.status = status
            inst.reject_reason = reject_reason
            inst.save(update_fields=['status', 'reject_reason'])
            return True
        return False

    def poi_mount(self, is_update=False):
        from kuaishou_wxa.api import get_ks_wxa
        ks = get_ks_wxa()
        config = get_config()
        notify_url = '{}{}'.format(config['template_url'], poi_notify_url)
        quality_labels = list(self.quality_labels.all().values_list('val', flat=True))
        ret, need_auth = ks.poi_mount(self.poi_id, notify_url, quality_labels=quality_labels,
                                      grade_label=self.grade_label,
                                      is_update=is_update)
        if need_auth:
            self.status = self.ST_APPROVING
        else:
            self.status = self.ST_PASS
        self.reject_reason = None
        self.save(update_fields=['status', 'reject_reason'])

    @classmethod
    def change_status(cls, poi_ids):
        from kuaishou_wxa.api import get_ks_wxa
        ks = get_ks_wxa()
        ret = ks.poi_check(poi_ids)
        for dd in ret['data']:
            if dd['code'] == 1:
                cls.update_status(dd['poiId'], dd['appId'], dd['status'], dd['reason'])

    @classmethod
    def poi_merge(cls, old_poi_id, new_poi_id):
        old_qs = cls.objects.filter(poi_id=old_poi_id)
        if old_qs:
            poi = KsPoi.objects.filter(poi_id=new_poi_id).first()
            if poi:
                old_qs.update(status=cls.ST_COMBINE)
                for inst in old_qs:
                    inst.kspoi.is_merge = True
                    inst.kspoi.new_poi_id = new_poi_id
                    inst.kspoi.save(update_fields=['is_merge', 'new_poi_id'])
            goods_list = KsGoodsConfig.objects.filter(poi=old_qs.first())
            for good in goods_list:
                # 重新挂载
                good.poi = poi
                good.save(update_fields=['poi'])
                good.push_to_ks(is_update=True)


class KsShowCategoryAbstract(models.Model):
    category_id = models.CharField(verbose_name='类目ID', null=True, max_length=10, help_text='抖音类目ID', unique=True)
    name = models.CharField(max_length=20, verbose_name='类目名称')

    class Meta:
        abstract = True

    def __str__(self):
        return self.name


class KsShowTopCategory(KsShowCategoryAbstract):
    class Meta:
        verbose_name_plural = verbose_name = '快手一级类目'

    @property
    def secondarys(self):
        return self.ks_secondary


class KsShowSecondaryCategory(KsShowCategoryAbstract):
    superior = models.ForeignKey(KsShowTopCategory, verbose_name='一级分类', related_name='ks_secondary',
                                 on_delete=models.CASCADE)

    class Meta:
        verbose_name_plural = verbose_name = '快手二级类目'

    def __str__(self):
        return '%s=>%s' % (self.superior.name, self.name)


class KsShowThirdCategory(KsShowCategoryAbstract):
    second = models.ForeignKey(KsShowSecondaryCategory, verbose_name='二级分类', related_name='ks_third',
                               on_delete=models.CASCADE)
    enable = models.BooleanField('类目是否开放', default=True)

    class Meta:
        verbose_name_plural = verbose_name = '快手三级类目'

    def __str__(self):
        return '%s=>%s' % (self.second.name, self.name)


class KsGoodsImage(models.Model):
    show = models.OneToOneField('ticket.ShowProject', verbose_name='演出项目', related_name='ks_show',
                                on_delete=models.CASCADE)
    cover_img = models.ImageField(u'宣传海报', upload_to=f'{IMAGE_FIELD_PREFIX}/ticket/shows/ks',
                                  validators=[file_size, validate_image_file_extension], help_text='要求长宽比1:1')
    ks_img_id = models.CharField('快手图片img_id', null=True, blank=True, max_length=50)

    class Meta:
        verbose_name_plural = verbose_name = '快手配置'

    def ks_upload_image(self):
        client = get_ks_wxa()
        config = get_config()
        ks_img_id = client.upload_image('{}{}'.format(config['template_url'], self.cover_img.url))
        self.ks_img_id = ks_img_id
        self.save(update_fields=['ks_img_id'])


class KsGoodsConfig(models.Model):
    session = models.OneToOneField('ticket.SessionInfo', verbose_name='场次', related_name='ks_session',
                                   on_delete=models.CASCADE)
    ks_product_id = models.CharField('产品ID', null=True, max_length=10, editable=False)
    poi = models.ForeignKey(KsPoiService, verbose_name='poi', help_text='需选择审核成功的记录，不然推商品和销售会失败',
                            on_delete=models.SET_NULL, null=True,
                            limit_choices_to=models.Q(status=KsPoiService.ST_PASS))
    category = models.ForeignKey(KsShowThirdCategory, verbose_name='节目分类', on_delete=models.CASCADE)
    full_price = models.DecimalField('原价', max_digits=13, decimal_places=2, default=0)
    sold_count = models.IntegerField('销量', default=0, help_text='给快手设置默认销量')
    promotion_commission_rate = models.IntegerField('分销佣金比例(万分数)', default=0,
                                                    help_text='如100表示佣金为万分之一百，即1% 注意：佣金比例＜2800，即佣金比例小于28%')
    need_push = models.BooleanField('是否需要推送到快手', default=True)
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
        (PUSH_DEFAULT, u'待推送'), (PUSH_NEED, u'已推送'), (PUSH_APPROVE, u'审核中'), (PUSH_SUCCESS, u'审核完成'),
        (PUSH_FAIL, u'推送失败'), (PUSH_AUTH_FAIL, u'审核失败'))
    push_status = models.IntegerField(u'快手推送状态', choices=PUSH_CHOICES, default=PUSH_DEFAULT)
    fail_msg = models.TextField('推送错误信息', max_length=1000, null=True, blank=True)
    audit_id = models.CharField('快手返回审核id', max_length=50, null=True, blank=True, editable=False)
    is_lock = models.BooleanField('是否快手锁定', default=False, editable=False, help_text='锁定期间不允许调用商品对接/编辑接口,到达截止时间自动解锁')
    lock_end_at = models.DateTimeField('锁定截止时间', null=True, blank=True, editable=False)
    lock_reason = models.TextField('锁定的原因', max_length=1000, null=True, blank=True, editable=False)
    push_at = models.DateTimeField('推送时间', null=True, blank=True)
    has_success_push = models.BooleanField('是否已推送成功', default=False)

    class Meta:
        verbose_name_plural = verbose_name = '快手商品配置'

    def __str__(self):
        return self.audit_id or str(self.id)

    @classmethod
    def get_session_qs(cls, session_qs):
        return session_qs.filter(ks_session__status=cls.STATUS_ON, ks_session__push_status=cls.PUSH_SUCCESS)

    @classmethod
    def ks_show_calendar(cls, session_qs):
        ks_qs = cls.get_session_qs(session_qs)
        ks_data = dict()
        for inst in ks_qs:
            d_key = inst.start_at.strftime('%Y-%m-%d')
            ks_data[d_key] = ks_data[d_key] + 1 if ks_data.get(d_key) else 1
        return ks_data

    @property
    def product_id(self):
        if self.ks_product_id:
            return self.ks_product_id
        product_id = self.session.get_session_out_id()
        if not self.ks_product_id:
            self.ks_product_id = product_id
            self.save(update_fields=['ks_product_id'])
        return product_id

    def re_push(self):
        if self.push_status == self.PUSH_AUTH_FAIL:
            self.audit_id = None
        self.fail_msg = None
        self.push_status = self.PUSH_DEFAULT
        self.save(update_fields=['audit_id', 'fail_msg', 'push_status'])

    def push_status_to_ks(self, status):
        # 更改状态
        ks = get_ks_wxa()
        # try:
        ks.update_product_status(self.poi.poi_id, self.product_id, status)
        self.status = status
        self.save(update_fields=['status'])
        # except Exception as e:
        #     raise ValidationError(e)

    def check_push_status(self):
        # 查询状态
        ks = get_ks_wxa()
        param = [{
            "poi_id": self.poi.poi_id,
            "product_id": self.product_id}]
        ret = ks.check_service_status(param)
        dd = ret['data'][0]
        #  "status": "PASSED",  // DEFAULT:待审核 PASSED:通过(上线) REJECT:拒绝 OFFLINE:下线
        if dd['code'] == 1:
            fields = ['push_status']
            if dd['status'] == 'PASSED':
                self.push_status = self.PUSH_SUCCESS
                self.status = self.STATUS_ON
                fields.append('status')
            elif dd['status'] == 'DEFAULT':
                self.push_status = self.PUSH_APPROVE
            elif dd['status'] == 'REJECT':
                self.push_status = self.PUSH_AUTH_FAIL
            elif dd['status'] == 'OFFLINE':
                self.push_status = self.PUSH_SUCCESS
                self.status = self.STATUS_OFF
                fields.append('status')
            self.save(update_fields=fields)

    @classmethod
    def set_approve(cls, product_id, message, reject_reason, audit_id):
        inst = cls.objects.filter(ks_product_id=product_id, audit_id=audit_id).first()
        if inst:
            inst.fail_msg = reject_reason
            if message == "PASSED":
                inst.push_status = cls.PUSH_SUCCESS

            else:
                inst.push_status = cls.PUSH_FAIL
            inst.save(update_fields=['fail_msg', 'push_status'])
            return True
        return False

    @classmethod
    def product_operation(cls, operation_type, poi_id, product_id, lock_endtime, reason):
        lock_end_at = datetime.fromtimestamp(int(lock_endtime / 1000))
        qs = cls.objects.filter(poi__poi_id=poi_id, ks_product_id=product_id)
        if operation_type == 'LOCK':
            qs.update(is_lock=True, lock_end_at=lock_end_at, lock_reason=reason)
        else:
            qs.update(is_lock=False, lock_end_at=None, lock_reason=None)

    @classmethod
    def session_push_to_ks(cls):
        # 商品首次上传/审核未通过重新上传
        close_old_connections()
        qs = cls.objects.filter(is_lock=False, need_push=True, push_status=cls.PUSH_DEFAULT)
        for inst in qs:
            is_update = inst.has_success_push
            ret, msg = inst.push_to_ks(is_update)
            inst.push_at = timezone.now()
            fields = ['push_at']
            if not ret:
                inst.fail_msg = msg
                inst.push_status = cls.PUSH_FAIL
                fields = fields + ['fail_msg', 'push_status']
            else:
                inst.has_success_push = True
                fields.append('has_success_push')
                if inst.push_status != cls.PUSH_SUCCESS:
                    inst.fail_msg = None
                    inst.push_status = cls.PUSH_NEED
                    fields = fields + ['fail_msg', 'push_status']
            inst.save(update_fields=fields)

    def push_to_ks(self, is_update=False):
        ks = get_ks_wxa()
        inst = self
        session = inst.session
        show = session.show
        label_list = list(show.flag.all().values_list('title', flat=True))
        img_inst = KsGoodsImage.objects.filter(show=show).first()
        if not img_inst or not img_inst.ks_img_id:
            return False, '快手图片未配置'
        try:
            config = get_config()
            cover_img_url = '{}{}'.format(config['template_url'], img_inst.cover_img.url)
            notify_url = '{}{}'.format(config['template_url'], poi_notify_url)
            good_path = '/{}?id={}'.format(ks_path, show.id)
            sold_start_time = session.dy_sale_time if session.dy_sale_time else show.sale_time
            ret = ks.product_mount(inst.poi.poi_id, inst.product_id, session.get_dy_product_name(),
                                   inst.category.category_id,
                                   cover_img_url, good_path, sold_start_time, session.end_at,
                                   inst.full_price * 100,
                                   inst.sold_count, inst.promotion_commission_rate, notify_url, label_list,
                                   is_update)
            fields = []
            if ret['data'].get('auditId'):
                inst.audit_id = ret['data']['auditId']
                fields = ['audit_id']
            if is_update and not ret['data']['needAudit']:
                inst.push_status = self.PUSH_SUCCESS
                fields.append('push_status')
            if fields:
                inst.save(update_fields=fields)
            return True, None
        except Exception as e:
            log.error(e)
            return False, e


class KsOrderSettleRecord(models.Model):
    order = models.ForeignKey('ticket.TicketOrder', verbose_name='订单', on_delete=models.CASCADE)
    order_no = models.CharField(u'订单号', max_length=128, db_index=True, editable=False, null=True)
    out_settle_no = models.CharField(u'结算单号', max_length=100, default=randomstrwithdatetime_settle, unique=True,
                                     db_index=True)
    reason = models.CharField('结算描述', max_length=100, null=True)
    settle_amount = models.DecimalField(u'申请结算金额', max_digits=13, decimal_places=2, default=0)
    amount = models.DecimalField(u'实际结算金额', max_digits=13, decimal_places=2, default=0)
    STATUS_DEFAULT = 'DEFAULT'
    STATUS_PROCESSING = 'SETTLE_PROCESSING'
    STATUS_SUCCESS = 'SETTLE_SUCCESS'
    STATUS_FAILED = 'SETTLE_FAILED'
    STATUS_CHOICES = (
        (STATUS_DEFAULT, U'未结算'), (STATUS_PROCESSING, U'结算中'), (STATUS_SUCCESS, U'成功'), (STATUS_FAILED, U'失败'))
    settle_status = models.CharField(u'状态', choices=STATUS_CHOICES, default=STATUS_DEFAULT, max_length=30)
    settle_no = models.CharField('快手结算单号', max_length=50, null=True, blank=True)
    error_msg = models.CharField('错误信息', max_length=1000, null=True, blank=True)
    create_at = models.DateTimeField('申请结算时间', null=True)

    class Meta:
        verbose_name_plural = verbose_name = '订单结算记录'
        ordering = ['-pk']

    @classmethod
    def settle_order(cls):
        close_old_connections()
        from mall.models import Receipt
        from datetime import timedelta
        settle_at = timezone.now() - timedelta(days=4) - timedelta(hours=1)
        qs = KsOrderReportRecord.objects.filter(ks_settle=KsOrderReportRecord.ST_DEFAULT,
                                                push_status=KsOrderReportRecord.STATUS_FINISH,
                                                update_at__lt=settle_at)
        for re_order in qs:
            inst, _ = cls.objects.get_or_create(order_id=re_order.order.id)
            st = inst.push_settle(re_order.order)
            if st:
                re_order.ks_settle = KsOrderReportRecord.ST_SUCCESS
            else:
                re_order.ks_settle = KsOrderReportRecord.ST_FAIL
            re_order.save(update_fields=['ks_settle'])

    def push_settle(self, order):
        client = get_ks_wxa()
        config = get_config()
        reason = '系统自动结算'
        notify_url = '{}{}'.format(config['template_url'], order_notify_url)
        ks_user = KsUser.ks_user(order.user)
        st = False
        try:
            settle_no = client.order_settle(order.order_no, self.out_settle_no, reason, notify_url,
                                            int(order.actual_amount * 100),
                                            order.multiply, ks_user.openid_ks)
            self.settle_no = settle_no
            self.order_no = order.order_no
            self.settle_status = self.STATUS_PROCESSING
            self.reason = reason
            self.settle_amount = order.actual_amount
            self.create_at = timezone.now()
            self.save(update_fields=['order_no', 'reason', 'settle_amount', 'create_at', 'settle_no', 'settle_status'])
            st = True
        except Exception as e:
            self.error_msg = str(e)
            self.settle_status = self.STATUS_FAILED
            self.create_at = timezone.now()
            self.save(update_fields=['error_msg', 'settle_status', 'create_at'])
        return st

    def set_fail(self):
        self.settle_status = self.STATUS_FAILED
        self.save(update_fields=['settle_status'])

    def set_finished(self, settle_amount):
        self.settle_status = self.STATUS_SUCCESS
        self.amount = settle_amount
        self.save(update_fields=['settle_status', 'amount'])

    @classmethod
    def ks_create_order(cls, order):
        ks_wxa = get_ks_wxa()
        ks_user = KsUser.ks_user(order.user)
        if not ks_user:
            raise CustomAPIException('请先登录快手')
        session = order.session
        show = session.show
        from mp.models import BasicConfig
        basic = BasicConfig.get()
        # 订单过期时间，单位秒，300s - 172800s
        expire_time = basic.auto_cancel_minutes * 60 if basic.auto_cancel_minutes >= 5 else 300
        config = get_config()
        notify_url = '{}{}'.format(config['template_url'], order_notify_url)
        from ticket.models import tiktok_order_detail_url
        tiktok_goods_url = '/{}?id={}&order_no={}'.format(tiktok_order_detail_url, order.id, order.order_no)
        order_info = ks_wxa.create_order(order.order_no, ks_user.openid_ks, order.actual_amount, order.title,
                                         show.content,
                                         expire_time, str(order.id), notify_url, session.get_session_out_id(),
                                         tiktok_goods_url,
                                         order.multiply)
        order.ks_order_no = order_info['order_no']
        order.save(update_fields=['ks_order_no'])
        return order_info

    @classmethod
    def ks_refund(cls, refund):
        order = refund.order
        # 下单有，这里必有
        ks_user = KsUser.ks_user(order.user)
        ks_wxa = get_ks_wxa()
        config = get_config()
        notify_url = '{}{}'.format(config['template_url'], order_notify_url)
        try:
            refund_no = ks_wxa.apply_refund(order.order_no, refund.out_refund_no, refund.return_reason or '客服要求退款',
                                            notify_url,
                                            int(refund.refund_amount * 100), order.multiply, ks_user.openid_ks)
            refund.refund_id = refund_no
            refund.save(update_fields=['refund_id'])
            return True
        except Exception as e:
            refund.status = refund.STATUS_PAY_FAILED
            refund.error_msg = str(e)
            refund.save(update_fields=['status', 'error_msg'])
        return False

    def query_settle(self):
        # SETTLE_PROCESSING-处理中，SETTLE_SUCCESS-成功，SETTLE_FAILED-失败
        ks_wxa = get_ks_wxa()
        ret = ks_wxa.query_settle(self.out_settle_no)
        status = ret['settle_status']
        if status == 'SETTLE_FAILED':
            self.set_fail()
        elif status == 'SETTLE_SUCCESS':
            self.set_finished(ret['settle_amount'] / 100)

    @classmethod
    def ks_query_status(cls, order):
        wxa = get_ks_wxa()
        has_pay, payment_info = wxa.query_status(order.order_no)
        if has_pay:
            from mall.models import Receipt
            receipt = order.receipt
            # 查询接口没有transaction_id，只有回调的时候才有
            receipt.set_paid(transaction_id=payment_info['ks_order_no'])

    @classmethod
    def ks_check_cps(cls):
        close_old_connections()
        from mall.models import Receipt
        order_qs = TicketOrder.objects.filter(pay_type=Receipt.PAY_KS, source_type=TicketOrder.SOURCE_DEFAULT,
                                              status__in=[TicketOrder.STATUS_PAID, TicketOrder.STATUS_FINISH])
        wxa = get_ks_wxa()
        for order in order_qs:
            has_pay, payment_info = wxa.query_status(order.order_no)
            if has_pay:
                extra_info = payment_info.get('extra_info')
                enable_promotion = payment_info.get('enable_promotion')
                promotion_amount = payment_info.get('promotion_amount')
                need_send_award = True
                if extra_info:
                    extra_info = json.loads(extra_info)
                    item_type = extra_info.get('item_type', None)
                    if item_type == 'VIDEO':
                        order.source_type = TicketOrder.SOURCE_VIDEO
                        need_send_award = False
                    elif item_type == 'LIVE':
                        order.source_type = TicketOrder.SOURCE_LIVE
                        need_send_award = False
                    else:
                        order.source_type = TicketOrder.SOURCE_NO
                    order.tiktok_douyinid = extra_info.get('author_id', None)
                    order.tiktok_commission_amount = promotion_amount / 100 if promotion_amount > 0 else 0
                    order.save(update_fields=['source_type', 'tiktok_douyinid', 'tiktok_commission_amount'])
                if need_send_award:
                    order.send_award()


class KsOrderReportRecord(models.Model):
    order = models.ForeignKey('ticket.TicketOrder', verbose_name='订单', on_delete=models.CASCADE)
    order_no = models.CharField(u'订单号', max_length=128, db_index=True, editable=False)
    STATUS_DEFAULT = 0
    STATUS_UNPAID = 1
    STATUS_PAID = 2
    STATUS_CANCELED = 3
    STATUS_FINISH = 4
    STATUS_REFUNDING = 5
    STATUS_REFUNDED = 6
    STATUS_OVER_TIME = 7
    STATUS_CHOICES = ((STATUS_UNPAID, '待推送'), (STATUS_FINISH, '已完成'))
    status = models.IntegerField(u'状态', choices=STATUS_CHOICES, default=STATUS_DEFAULT)
    push_status = models.IntegerField(u'已推送状态', choices=STATUS_CHOICES, default=STATUS_DEFAULT)
    ST_DEFAULT = 0
    ST_SUCCESS = 1
    ST_FAIL = 2
    ST_CHOICES = ((ST_DEFAULT, '待结算'), (ST_SUCCESS, '已结算'), (ST_FAIL, '结算失败'))
    ks_settle = models.IntegerField(u'结算状态', choices=ST_CHOICES, default=ST_DEFAULT)
    error_msg = models.CharField('错误信息', max_length=1000, null=True, blank=True)
    update_at = models.DateTimeField('最新推送时间', null=True, blank=True)

    class Meta:
        verbose_name_plural = verbose_name = '订单同步记录'
        ordering = ['-pk']

    @classmethod
    def ks_report(cls, order):
        # 只有已核销才需要推送
        inst, _ = cls.objects.get_or_create(order=order, order_no=order.order_no)
        inst.set_status(order.status)
        return inst

    def set_status(self, status, change_push_status=False):
        fields = ['status']
        self.status = status
        if change_push_status:
            # 推送成功后需要修改状态
            self.push_status = status
            self.update_at = timezone.now()
            fields = fields + ['push_status', 'update_at']
        self.save(update_fields=fields)

    @classmethod
    def report_status(cls):
        return [cls.STATUS_PAID, cls.STATUS_FINISH, cls.STATUS_REFUNDING, cls.STATUS_REFUNDED]

    @classmethod
    def ks_order_report_task(cls):
        # 快手推送已核销状态，满3天后可发起结算
        from caches import with_redis, auth_report_order_ks_key
        from mall.models import Receipt
        with with_redis() as redis:
            if redis.setnx(auth_report_order_ks_key, 1):
                redis.expire(auth_report_order_ks_key, 300)
                try:
                    close_old_connections()
                    qs = TicketOrder.objects.filter(pay_type=Receipt.PAY_KS, session__end_at__lt=timezone.now(),
                                                    status__in=[TicketOrder.STATUS_PAID, TicketOrder.STATUS_FINISH],
                                                    ks_report=TicketOrder.CHECK_DEFAULT)
                    for order in qs:
                        order.set_finish()
                        order.ks_report = TicketOrder.CHECK_FAIL
                        inst = cls.ks_report(order)
                        st, msg = inst.order_report()
                        if st:
                            order.ks_report = TicketOrder.CHECK_SUCCESS
                        order.save(update_fields=['ks_report'])
                finally:
                    redis.delete(auth_report_order_ks_key)

    def order_report(self):
        # 只有已核销才需要推送
        inst = self
        order = self.order
        if inst.status != self.push_status:
            # 下单有，这里必有
            st = False
            # if order.status == order.STATUS_PAID:
            #     status = 10
            # elif order.status == order.STATUS_REFUNDING:
            #     status = 4
            # elif order.status == order.STATUS_REFUNDED:
            #     status = 6
            if order.status == order.STATUS_FINISH:
                status = 11
            else:
                return st, '订单不是已完成状态'
            msg = ''
            if status:
                ks_user = KsUser.ks_user(order.user)
                ks_wxa = get_ks_wxa()
                from ticket.models import tiktok_order_detail_url
                session = order.session
                show = session.show
                ks_good = KsGoodsImage.objects.filter(show=show).first()
                poi = session.ks_session.poi.kspoi
                order_detail_url = '/{}?id={}&order_no={}'.format(tiktok_order_detail_url, order.id, order.order_no)
                try:
                    ks_wxa.order_report(order.order_no, ks_user.openid_ks, order.create_at, status,
                                        order_detail_url,
                                        ks_good.ks_img_id, poi.poi_id, session.get_session_out_id(),
                                        session.ks_session.category.category_id, str(poi.store.city))
                    st = True
                    inst.set_status(order.status, True)
                except Exception as e:
                    log.error(e)
                    msg = str(e)
            inst.error_msg = msg
            inst.save(update_fields=['error_msg'])
            return st, msg
