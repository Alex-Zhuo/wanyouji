# coding=utf-8
from __future__ import unicode_literals

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from restframework_ext.exceptions import CustomAPIException


# Create your models here.


class IFee(object):
    def items_manager(self):
        """

        :return:
        """
        raise NotImplementedError()

    def find(self, division):
        """
        根据区域查找对应的配置项
        :param division:
        :return:
        """
        im = self.items_manager()
        specify_match = []
        default_match = []
        for item in im.all():
            if specify_match:
                break
            division_default = True
            # 没设置区域的配置项目为默认配置
            for div in item.divisions.all():
                division_default = False
                if div.include(division):
                    specify_match.append(item)
                    break
            else:
                if division_default:
                    default_match.append(item)
        matched = specify_match or default_match
        l = len(matched)
        if l == 1:
            return matched.pop()
        elif l == 0:
            return
        elif l > 1:
            raise CustomAPIException('系统错误, 找到一个以上的匹配的邮费选项, 请联系客服')

    def is_excluded(self, division):
        for div in self.exclude_divisions.all():
            if div.include(division):
                return True
        else:
            return False

    def get_fee(self, division, multiply):
        """
        根据要发的目的地和货品数量来计算邮费
        :param division: class Division
        :param multiply: 数量, 有可能是件、重量等
        :return:
        """
        if multiply <= 0:
            raise ValueError('货品数量必须大于0')
        item = self.find(division)
        return item.get_fee(multiply) if item else 0


class ItemFee(object):
    def get_fee(self, multiply):
        """

        :param multiply:
        :return:
        """
        raise NotImplementedError()


class Division(models.Model):
    """
    一个合法地址, 应该是 [province, [city, [county]]], 即不能出现, 低级区域存在, 而高级区域不存在的情况, 例如
    广东省天河区、广州市天河区、天河区都是非法的
    """
    province = models.CharField('省', max_length=32)
    province_alias = models.CharField('省别名', max_length=100, null=True, blank=True, help_text='多个时用井号分割')
    city = models.CharField("市", max_length=32, null=True, blank=True)
    county = models.CharField('县', max_length=32, null=True, blank=True)
    TYPE_PROV = 0
    TYPE_CITY = 1
    TYPE_COUNTY = 2
    type = models.SmallIntegerField('级别', choices=[(0, '省'), (1, '市'), (2, '区(县)')], null=True)
    is_use = models.BooleanField('是否使用', default=True)

    def clean(self):
        if self.county and not self.city:
            raise ValidationError(dict(county=ValidationError('在设置了县的情况下,必需设置市')))

    class Meta:
        verbose_name_plural = verbose_name = '行政区划'
        unique_together = ('province', 'city', 'county')
        ordering = ['province', 'city', 'county']

    @classmethod
    def add_prov(cls, province):
        """

        :param province:
        :return:
        """
        _, created = cls.objects.get_or_create(province=province, type=cls.TYPE_PROV)
        return _

    @classmethod
    def add_city(cls, province, city):
        """

        :param province:
        :return:
        """
        _, created = cls.objects.get_or_create(province=province, city=city, type=cls.TYPE_CITY)
        return _

    @classmethod
    def add_county(cls, province, city, county):
        """

        :param province:
        :return:
        """
        _, created = cls.objects.get_or_create(county=county, province=province, city=city, type=cls.TYPE_COUNTY)
        return _

    @classmethod
    def load_prov(cls, province):
        """
        查询省
        :param province:
        :return:
        返回第一个找到的省,找不到则返回空
        """
        try:
            return cls.objects.get(province=province, type=cls.TYPE_PROV)
        except cls.DoesNotExist:
            return
        except cls.MultipleObjectsReturned:
            return cls.objects.filter(province=province, type=cls.TYPE_PROV).order_by('pk').first()

    def refresh_type(self):
        if self.county:
            if self.type != self.TYPE_COUNTY:
                self.type = self.TYPE_COUNTY
                self.save(update_fields=['type'])
        elif self.city:
            if self.type != self.TYPE_CITY:
                self.type = self.TYPE_CITY
                self.save(update_fields=['type'])
        else:
            if self.type != self.TYPE_PROV:
                self.type = self.TYPE_PROV
                self.save(update_fields=['type'])

    @classmethod
    def init_type(cls):
        for d in cls.objects.all():
            if d.county:
                d.type = 2
            elif d.city:
                d.type = 1
            else:
                d.type = 0
            d.save(update_fields=['type'])

    # @staticmethod
    # def autocomplete_search_fields():
    #     return 'city',

    @property
    def null(self):
        """
        是否为空区域
        :return:
        """
        return not (self.province or self.city or self.county)

    def is_valid(self, raise_exception=False):
        if self.county:
            ret = bool(self.city and self.province)
        elif self.city:
            ret = bool(self.province)
        else:
            ret = True
        if not ret and raise_exception:
            raise ValidationError('地址非法')
        return True

    def include(self, division):
        """
        本区域是否包含(相等也是包含)目标区域
        :param division:
        :return:
        """
        map(lambda o: o.is_valid(True), [self, division])

        if self.null or division.null:
            # 只要有一方为空, 则不存在包含关系
            return False
        if self.province == division.province or \
                (division.province in self.province_alias.split('#') if self.province_alias else False):
            if self.city:
                if self.city == division.city:
                    return not self.county or self.county == division.county
                else:
                    return False
            else:
                return True
        else:
            return False

    def __str__(self):
        s = ''
        if self.province:
            s += self.province
        if self.city:
            s += self.city
        if self.county:
            s += self.county
        return s


class Template(models.Model, IFee):
    name = models.CharField('名称', max_length=32)

    FEE_TYPE_MULTIPLY = 0
    FEE_TYPE_GRADIENT = 1
    FEE_TYPE_CHOICES = [(FEE_TYPE_MULTIPLY, '按量计费'), ]
    fee_type = models.IntegerField('计费类型', choices=FEE_TYPE_CHOICES, default=FEE_TYPE_MULTIPLY, editable=False)
    exclude_divisions = models.ManyToManyField(Division, verbose_name='不发货区域', blank=True,
                                               limit_choices_to=models.Q(type__in=[0, 1]))
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name='所属商铺账号', null=True, blank=True, editable=False,
                             on_delete=models.SET_NULL)

    def items_manager(self):
        if self.fee_type == self.FEE_TYPE_MULTIPLY:
            return self.vitems
        elif self.fee_type == self.FEE_TYPE_GRADIENT:
            return self.gitems

    class Meta:
        verbose_name_plural = verbose_name = '邮费模板'

    def __str__(self):
        return self.name


class VolumeChargeItem(models.Model):
    way = models.ForeignKey(Template, verbose_name='按量计费', related_name='vitems', on_delete=models.CASCADE)
    divisions = models.ManyToManyField(Division, verbose_name='行政区划', help_text='为空表示默认区域, 即所有没单独设置的区域, 使用此规则',
                                       blank=True, limit_choices_to=models.Q(type__in=[0, 1]))
    free_multiply = models.DecimalField('免邮数量', max_digits=9, decimal_places=1, help_text='该数量以下(含)免邮费', default=0,
                                        editable=False)
    unit_price = models.DecimalField('单价', max_digits=9, decimal_places=1)

    class Meta:
        verbose_name = verbose_name_plural = '城市邮费配置'

    def get_fee(self, multiply):
        if self.free_multiply >= multiply:
            return 0
        else:
            return self.unit_price * (multiply - self.free_multiply)

    def __str__(self):
        if self.id:
            df = self.divisions.first()
            return "{}, 免邮: {}, 单价: {}".format(str(df) + "等地区" if df else "所有地区", self.free_multiply, self.unit_price)
        else:
            return ''


class GradientChargeItem(models.Model, ItemFee):
    way = models.ForeignKey(Template, verbose_name='梯度计费', related_name='gitems', on_delete=models.CASCADE)
    free_multiply = models.DecimalField('免邮数量', max_digits=9, decimal_places=1, default=0,
                                        help_text='该数量以下(含)免邮费, 0代表没有')
    divisions = models.ManyToManyField(Division, verbose_name='区域列表', related_name='gitem', blank=True,
                                       limit_choices_to=models.Q(type__in=[0, 1]))

    class Meta:
        verbose_name = verbose_name_plural = '梯度计费配置项'

    def get_fee(self, multiply):
        if self.free_multiply >= multiply:
            return 0
        else:
            ran = self.ranges.get(left__lte=multiply, right__gt=multiply)
            return ran.fee

    def __str__(self):
        if self.id:
            df = self.divisions.first()
            return "{}, 免邮: {}".format(str(df) + "等地区" if df else "所有地区", self.free_multiply)
        else:
            return ''


class GradientRange(models.Model):
    item = models.ForeignKey(GradientChargeItem, verbose_name='梯度计费配置项', related_name='ranges',
                             on_delete=models.CASCADE)
    left = models.DecimalField('大于', max_digits=9, decimal_places=1, help_text='大于(含)多少', default=0)
    right = models.DecimalField('小于', max_digits=9, decimal_places=1, help_text='小于(不含)多少, 且右值要大于左值', default=0)
    fee = models.DecimalField('金额', max_digits=9, decimal_places=1, help_text='邮费金额')

    class Meta:
        verbose_name = verbose_name_plural = '梯度范围'

    def __str__(self):
        return "大于等于(>=){}, 小于(<){}, 邮费: {}".format(self.left, self.right, self.fee)


class ExpressCompany(models.Model):
    code = models.CharField(u'编码', max_length=30, help_text=u'快递公司编码')
    name = models.CharField(u'公司名称', max_length=50, help_text=u'快递公司名称')
    display_order = models.IntegerField('排序号', default=0, help_text='越大越前', editable=False)

    class Meta:
        verbose_name_plural = verbose_name = u'快递公司'
        ordering = ('-display_order',)

    def __str__(self):
        return self.name
