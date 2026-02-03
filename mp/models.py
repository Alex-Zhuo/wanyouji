# coding: utf-8
from __future__ import unicode_literals
from django.core.exceptions import ValidationError
from django.core.validators import validate_image_file_extension, FileExtensionValidator
from django.db import models

# Create your models here.
from common.config import FILE_FIELD_PREFIX, IMAGE_FIELD_PREFIX


class MsgTemplate(models.Model):
    template_short_id = models.CharField(verbose_name='模板编号', max_length=64, unique=True, help_text='模板消息的short_id')
    template_id = models.CharField(verbose_name='模板id', max_length=128,
                                   help_text='用于发送通知的加密ID，同一模板short_id与公众号(小程序）加密一个ID')
    title = models.CharField('标题', max_length=50, null=True, blank=True)
    template_group = models.CharField('消息组', max_length=30, null=True, blank=True,
                                      help_text='归属同一消息组的不同类型模板，属于面向同一业务场景的模板，比如订单支付成功场景，小程序和公众号可以各有一个模板，但是对应同一个组')
    TYPE_WEAPP = 1
    TYPE_MP = 0
    type = models.SmallIntegerField('模板类型', choices=[(TYPE_MP, '公众号'), (TYPE_WEAPP, '小程序')], default=0)

    class Meta:
        verbose_name = verbose_name_plural = '微信模板消息'

    def send(self, open_id, data, url):
        from mp.wechat_client import get_mp_client
        client = get_mp_client()
        if not self.template_id:
            template_id = client.get_template_id(self.template_short_id)
            if not template_id:
                return
            self.template_id = template_id
            self.save(update_fields=['template_id'])
        client.send_template_msg(open_id, self.template_id, data, url)


class SystemWxMP(models.Model):
    name = models.CharField('名字', max_length=50)
    app_id = models.CharField('app_id', max_length=50)
    app_secret = models.CharField('app_secret', max_length=50)

    class Meta:
        verbose_name_plural = verbose_name = '微信小程序'

    def __unicode__(self):
        return self.name

    @classmethod
    def get(cls):
        return cls.objects.first()


# class SystemWxShop(models.Model):
#     name = models.CharField('名字', max_length=50)
#     app_id = models.CharField('app_id', max_length=50)
#     app_secret = models.CharField('app_secret', max_length=50)
#
#     class Meta:
#         verbose_name_plural = verbose_name = '微信视频号小店'
#
#     def __unicode__(self):
#         return self.name
#
#     @classmethod
#     def get(cls):
#         return cls.objects.first()


class SystemDouYin(models.Model):
    account_name = models.CharField('商家名', max_length=50, null=True, help_text='来客后台账户名称')
    account_id = models.CharField('商户ID', max_length=50, null=True, help_text='来客后台右上角的账户ID')
    client_key = models.CharField('应用标识', max_length=50, help_text='client_key')
    client_secret = models.CharField('应用秘钥', max_length=50, help_text='client_secret')

    class Meta:
        verbose_name_plural = verbose_name = '抖音服务平台'

    def __unicode__(self):
        return self.account_name

    @classmethod
    def get(cls):
        return cls.objects.first()


class SystemDouYinMP(models.Model):
    name = models.CharField('名字', max_length=50)
    app_id = models.CharField('app_id', max_length=50)
    app_secret = models.CharField('app_secret', max_length=50)
    salt = models.CharField('SALT', max_length=50, help_text='退款用,能力-支付-支付方式管理-支付设置里的SALT', null=True, blank=True,
                            editable=False)
    token = models.CharField('token', max_length=50, help_text='退款用,能力-支付-支付方式管理-支付设置里的token', null=True, blank=True,
                             editable=False)

    class Meta:
        verbose_name_plural = verbose_name = '抖音小程序'

    def __unicode__(self):
        return self.name

    @classmethod
    def get(cls):
        return cls.objects.first()


class SystemMP(models.Model):
    type_unauthorized_sub = 0
    type_unauthorized_serv = 1
    type_authorized_sub = 2
    type_authorized_serv = 3
    type_choices = ((type_unauthorized_sub, '订阅号'), (type_unauthorized_serv, '服务号'),
                    (type_authorized_sub, '认证订阅号'), (type_authorized_serv, '认证服务号'))
    type = models.IntegerField('账号类型', choices=type_choices, default=type_authorized_serv)
    name = models.CharField('名字', max_length=50)
    wx_id = models.CharField('微信号', max_length=20, null=True, blank=True)
    app_id = models.CharField('app_id', max_length=50)
    app_secret = models.CharField('app_secret', max_length=50)
    origin_id = models.CharField('原始ID', max_length=50, unique=True)
    token = models.CharField('token', max_length=50)
    EncodingAESKey = models.CharField('EncodingAESKey', max_length=200)
    avatar = models.ImageField('公众号头像', upload_to=f'{IMAGE_FIELD_PREFIX}/wx', null=True, blank=True,
                               validators=[validate_image_file_extension])
    qr_code = models.ImageField('二维码', upload_to=f'{IMAGE_FIELD_PREFIX}/wx', null=True, blank=True,
                                validators=[validate_image_file_extension])
    user_head = models.CharField('被邀请人消息标题', max_length=100, null=True, blank=True)
    user_end = models.CharField('被邀请人消息结尾', max_length=100, null=True, blank=True)
    parent_head = models.CharField('推荐人消息标题', max_length=100, null=True, blank=True)
    parent_end = models.CharField('推荐人消息结尾', max_length=100, null=True, blank=True)
    share_img = models.ImageField('分享背景图', upload_to=f'{IMAGE_FIELD_PREFIX}/wx', null=True, blank=True,
                                  validators=[validate_image_file_extension])

    class Meta:
        verbose_name_plural = verbose_name = '系统公众号'

    def __str__(self):
        return self.name

    @classmethod
    def get(cls):
        return cls.objects.first()


class WeiXinPayConfig(models.Model):
    title = models.CharField('名称', max_length=50, null=True, blank=True)
    CONFIG_TYPE_MP = 1
    CONFIG_TYPE_APP = 2
    CONFIG_TYPE_LP = 3
    CONFIG_TYPE_CHOICES = ((CONFIG_TYPE_LP, '小程序支付'),)
    config_type = models.IntegerField('配置类型', default=CONFIG_TYPE_MP, choices=CONFIG_TYPE_CHOICES)
    is_on = models.BooleanField('开启', default=True)
    is_default = models.BooleanField('是否默认', default=False)
    app_id = models.CharField('APPID', max_length=32)
    pay_shop_id = models.CharField('微信商户号', max_length=32)
    sub_mch_id = models.CharField('子商户号', max_length=32, null=True, blank=True)
    pay_api_key = models.CharField('微信商户API密钥', max_length=64)
    mch_cert = models.FileField('商户证书', upload_to=f'{FILE_FIELD_PREFIX}/wx/wx_cert',
                                help_text='请上传文件:apiclient_cert.pem',
                                validators=[FileExtensionValidator(allowed_extensions=['pem'])])
    mch_key = models.FileField('商户证书秘钥', upload_to=f'{FILE_FIELD_PREFIX}/wx/wx_cert',
                               help_text='请上传文件:apiclient_key.pem',
                               validators=[FileExtensionValidator(allowed_extensions=['pem'])])

    class Meta:
        verbose_name_plural = verbose_name = '微信支付配置'

    def __str__(self):
        return self.title or self.get_config_type_display()

    def clean(self):
        if self.is_default:
            WeiXinPayConfig.objects.exclude(id=self.id).update(is_default=False)

    @classmethod
    def get_default(cls):
        return cls.objects.filter(is_default=True, is_on=True).first()


def validate_file_size(value):
    filesize = value.size

    if filesize > 838860:
        raise ValidationError("图片必须小于800kb")
    else:
        return value


class ShareQrcodeBackground(models.Model):
    image = models.ImageField('图片', upload_to=f'{IMAGE_FIELD_PREFIX}/mall/qr_bk',
                              validators=[validate_file_size, validate_image_file_extension],
                              help_text='尺寸要求: 750 * 1372,必须是这个尺寸,大小不超过800kb')
    enable = models.BooleanField('生效', default=False)
    ver = models.IntegerField(editable=False, default=6)

    class Meta:
        verbose_name_plural = verbose_name = '二维码背景图片'

    def __str__(self):
        return '{}'.format(self.image)

    @classmethod
    def get(cls, raise_exception=False):
        """

        :return:
        """
        o = cls.objects.filter(enable=True).order_by('-ver').first()
        if not o:
            if raise_exception:
                from restframework_ext.exceptions import CustomAPIException
                raise CustomAPIException('没有设置分享码背景')
            else:
                return
        return o

    def enable_bg(self):
        self.__class__.objects.update(enable=False)
        self.enable = True
        self.ver = (self.__class__.objects.aggregate(max=models.Max('ver'))['max'] or 0) + 1
        self.save(update_fields=['enable', 'ver'])


def auto_cancel_minutes_limit(value):
    if value < 5:
        raise ValidationError("必须大于等于5分钟")
    else:
        return value


class BasicConfig(models.Model):
    mall_name = models.CharField('系统名称', max_length=32, null=True, blank=True)
    official_site_name = models.CharField('官网名称', max_length=32, null=True, blank=True, editable=False)
    wx_share_title = models.CharField('微信分享标题', max_length=32, null=True, blank=True)
    wx_share_desc = models.CharField('微信分享描述', max_length=64, null=True, blank=True)
    wx_share_img = models.ImageField('微信分享图片', upload_to=f'{IMAGE_FIELD_PREFIX}/mp/basic', null=True, blank=True,
                                     validators=[validate_image_file_extension])
    venue_mobile = models.CharField('场馆客服电话', max_length=20, null=True, blank=True)
    custom_work_at = models.CharField('客服服务时间', max_length=50, null=True, blank=True)
    platform_mobile = models.CharField('平台客服电话', max_length=20, null=True, blank=True)
    maizuo_mobile = models.CharField('麦座同步失败通知手机', max_length=20, null=True, blank=True, editable=False)
    tiktok_kf = models.CharField('抖音客服ID', max_length=100, null=True, blank=True, editable=False)
    service_agreement = models.FileField('服务协议', upload_to=f'{FILE_FIELD_PREFIX}/basic', help_text='只能上传pdf或word',
                                         null=True, blank=True,
                                         validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx'])])
    realname_agreement = models.FileField('实名须知', upload_to=f'{FILE_FIELD_PREFIX}/basic', help_text='只能上传pdf或word',
                                          null=True, blank=True,
                                          validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx'])])
    agent_agreement = models.FileField('Ai智能体协议', upload_to=f'{FILE_FIELD_PREFIX}/basic', help_text='只能上传pdf或word',
                                       null=True, blank=True,
                                       validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx'])])
    withdraw_min = models.IntegerField('最低提现金额', default=100)
    auto_cancel_minutes = models.IntegerField('自动关闭订单分钟数', default=5, help_text='订单创建时间开始多少分钟后未支付自动取消订单，解锁位置',
                                              validators=[auto_cancel_minutes_limit])
    withdraw_fees_ratio = models.IntegerField('手续费率', default=1, help_text='填入5为5%', editable=False)
    business_img = models.ImageField('商户合作图片', upload_to=f'{IMAGE_FIELD_PREFIX}/mp/basic', null=True, blank=True,
                                     validators=[validate_image_file_extension])
    goodsindex = models.IntegerField('商品显示配置(技术人员使用)', default=1, editable=False)
    plateindex = models.IntegerField('模块显示配置(技术人员使用)', default=0, editable=False)

    class Meta:
        verbose_name_plural = verbose_name = '系统基本配置'

    def __str__(self):
        return self.mall_name

    @classmethod
    def get(cls):
        return cls.objects.first()

    @classmethod
    def get_pay_expire_seconds(cls):
        basic = cls.get()
        pay_expire_seconds = (basic.auto_cancel_minutes - 1) * 60 if basic else 300
        if pay_expire_seconds <= 0:
            pay_expire_seconds = 300
        return pay_expire_seconds


class ServiceConfig(models.Model):
    bind_day = models.IntegerField('粉丝解绑天数', default=30)

    class Meta:
        verbose_name_plural = verbose_name = '服务配置项'

    @classmethod
    def get(cls):
        return cls.objects.first()


class ReturnAddress(models.Model):
    name = models.CharField('收件人', max_length=32, null=True, blank=True)
    mobile = models.CharField('电话', max_length=32, null=True, blank=True)
    address = models.CharField('详细地址题', max_length=32, null=True, blank=True)

    class Meta:
        verbose_name_plural = verbose_name = '退货回寄地址设置'

    def __str__(self):
        return self.name

    @classmethod
    def get(cls):
        return cls.objects.first()


class WxMenu(ReturnAddress):
    class Meta:
        verbose_name_plural = verbose_name = '公众号菜单'
        proxy = True


class DouYinPayConfig(models.Model):
    title = models.CharField('名称', max_length=32)
    merchant_uid = models.CharField('收款商户号', max_length=32)
    is_default = models.BooleanField('是否默认', default=False, editable=False)

    class Meta:
        verbose_name_plural = verbose_name = '抖音支付配置'

    def __str__(self):
        return self.title

    # def clean(self):
    #     if self.is_default:
    #         DouYinPayConfig.objects.exclude(id=self.id).update(is_default=False)

    @classmethod
    def get_default(cls):
        return cls.objects.filter(merchant_uid='72789245768543296350').first()


class DouYinImages(models.Model):
    basic = models.ForeignKey(BasicConfig, verbose_name=u'商城基本配置', null=True, on_delete=models.SET_NULL)
    title = models.CharField('名称', max_length=20)
    image = models.ImageField(u'图片', upload_to=f'{IMAGE_FIELD_PREFIX}/mp/basic',
                              validators=[validate_image_file_extension])

    class Meta:
        verbose_name_plural = verbose_name = u'抖音主体证件'

    def __str__(self):
        return self.title


class MaiZuoAccount(models.Model):
    name = models.CharField('用户名', max_length=50)
    password = models.CharField('密码', max_length=50)

    class Meta:
        verbose_name_plural = verbose_name = '麦座账户'

    def __str__(self):
        return self.name
