# coding=utf-8
from __future__ import unicode_literals

from django.core.exceptions import ValidationError
from django.core.validators import validate_image_file_extension, FileExtensionValidator
from django.db import models

from common.config import IMAGE_FIELD_PREFIX, FILE_FIELD_PREFIX, VIDEO_EXT_LIST


class SubPages(models.Model):
    page_name = models.CharField('页面名称', max_length=50)
    page_code = models.CharField('页面代码(唯一)', unique=True, max_length=30, blank=True)
    add_to_index = models.BooleanField('添加到首页', default=False)
    seq = models.IntegerField('排序号', default=0)
    share_desc = models.CharField('分享描述', max_length=200, null=True)
    share_image = models.ImageField('分享展示图片', null=True, upload_to=f'{IMAGE_FIELD_PREFIX}/mall/share',
                                    validators=[validate_image_file_extension])
    TYPE_APP = 0
    TYPE_LP = 1
    type = models.SmallIntegerField('终端类型', default=0, choices=[(0, 'APP端'), (1, '小程序端')])

    class Meta:
        verbose_name_plural = verbose_name = '装修页面'
        ordering = ['-seq']

    def __str__(self):
        return self.page_name

    def set_page_code(self):
        if not self.page_code:
            self.page_code = 'p{}'.format(str(self.id).zfill(4))
            self.save(update_fields=['page_code'])


class Resource(models.Model):
    code = models.IntegerField('资源编号', unique=True)
    name = models.CharField('名称', max_length=30)
    STATUS_ON = 1
    STATUS_OFF = 0
    STATUS_CHOICES = ((STATUS_ON, u'上架'), (STATUS_OFF, u'下架'))
    status = models.IntegerField(u'状态', choices=STATUS_CHOICES, default=STATUS_ON)

    class Meta:
        verbose_name_plural = verbose_name = '多媒体资源'
        ordering = ['-pk']

    def __str__(self):
        return '%s:%s' % (self.code, self.name)

    def set_status(self, status):
        self.status = status
        self.save(update_fields=['status'])


class ResourceImageItem(models.Model):
    resource = models.ForeignKey(Resource, verbose_name='所属资源', related_name='items', on_delete=models.CASCADE)
    url = models.CharField('链接', null=True, blank=True, max_length=100)
    image = models.ImageField('图片', null=True, blank=True, upload_to=f'{IMAGE_FIELD_PREFIX}/mall/res',
                              validators=[validate_image_file_extension])
    is_dy_show = models.BooleanField('是否抖音显示', default=True)

    class Meta:
        verbose_name_plural = verbose_name = '资源项'
        ordering = ['-pk']


def validate_file_size(value):
    filesize = value.size

    if filesize > 838860:
        raise ValidationError("图片必须小于800kb")
    else:
        return value


class MediaType(models.Model):
    name = models.CharField('名称', max_length=30)
    code = models.CharField('资源编号', unique=True, max_length=10)

    class Meta:
        verbose_name_plural = verbose_name = '视频资源类型'


class OpenScreenMedia(models.Model):
    image = models.ImageField('图片', upload_to=f'{IMAGE_FIELD_PREFIX}/media/video',
                              validators=[validate_image_file_extension], null=True, blank=True)
    video = models.FileField('视频', upload_to=f'{FILE_FIELD_PREFIX}/media/video',
                             validators=[FileExtensionValidator(allowed_extensions=VIDEO_EXT_LIST)], null=True,
                             blank=True)
    media_type = models.ForeignKey(MediaType, verbose_name='视频资源类型', null=True, on_delete=models.PROTECT)
    seconds = models.PositiveSmallIntegerField('视频时间长度(秒)', default=0, help_text='单位：秒，传视频时必填')

    is_use = models.BooleanField('是否使用', default=True)

    class Meta:
        verbose_name_plural = verbose_name = '视频资源'
